#!/usr/bin/env python3
"""Replay an exact-site result through native HPWL/RSMT evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
from argparse import Namespace
from pathlib import Path

import numpy as np
import torch

from analyze_quality_bound import (
    _baseline_positions,
    _load_context,
    _override_manual_baseline_endpoints,
    _select_fixed_endpoints,
)
from run_matrix import parse_final_ppa, parse_placement


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BASELINE_RESULT = (
    ROOT
    / "results/m336/baseline_warmstart_smoke/baseline/baseline-result.json"
)


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(content)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_json_atomic(path: Path, data) -> None:
    _write_text_atomic(
        path, json.dumps(data, indent=2, sort_keys=True) + "\n"
    )


def _write_placement_atomic(placedb, path: Path, node_x, node_y) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        placedb.write_pl(None, str(temporary), node_x, node_y)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _copy_atomic(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(
        f".{destination.name}.{os.getpid()}.tmp"
    )
    try:
        shutil.copyfile(source, temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _result_positions(data, placedb, context, bookshelf_dir):
    selected_sites = data.get("selected_sites") or {}
    expected_refdes = {constraint.refdes for constraint in context.constraints}
    if set(selected_sites) != expected_refdes:
        missing = sorted(expected_refdes - set(selected_sites))
        extra = sorted(set(selected_sites) - expected_refdes)
        raise ValueError(
            f"selected-site identity mismatch: missing={missing} extra={extra}"
        )

    baseline_x, baseline_y = _baseline_positions(
        placedb, bookshelf_dir / "m336.baseline.pl"
    )
    fixed_x, fixed_y = _select_fixed_endpoints(
        context, baseline_x, baseline_y, "runtime"
    )
    fixed_x, fixed_y = _override_manual_baseline_endpoints(
        context,
        placedb,
        baseline_x,
        baseline_y,
        fixed_x,
        fixed_y,
        data.get("manual_baseline_endpoints", []),
    )

    controlled_ids = {constraint.node_id for constraint in context.constraints}
    node_x = np.asarray(placedb.node_x, dtype=np.float64).copy()
    node_y = np.asarray(placedb.node_y, dtype=np.float64).copy()
    node_x[: placedb.num_physical_nodes] = baseline_x
    node_y[: placedb.num_physical_nodes] = baseline_y
    for node_id in range(placedb.num_physical_nodes):
        if node_id not in controlled_ids:
            node_x[node_id] = fixed_x[node_id]
            node_y[node_id] = fixed_y[node_id]
    for constraint in context.constraints:
        center = np.asarray(
            selected_sites[constraint.refdes]["center"], dtype=np.float64
        )
        if center.shape != (2,) or not np.all(np.isfinite(center)):
            raise ValueError(f"invalid center for {constraint.refdes}")
        node_x[constraint.node_id] = center[0] - constraint.node_width / 2
        node_y[constraint.node_id] = center[1] - constraint.node_height / 2
    return node_x, node_y


def _coordinate_replay_audit(input_path: Path, output_path: Path) -> dict:
    expected = parse_placement(input_path)
    actual = parse_placement(output_path)
    if set(expected) != set(actual):
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        raise ValueError(
            f"native replay identity mismatch: missing={missing} extra={extra}"
        )
    worst_refdes = None
    max_error = 0.0
    for refdes in sorted(expected):
        error = max(
            abs(expected[refdes][axis] - actual[refdes][axis])
            for axis in (0, 1)
        )
        if error > max_error:
            max_error = error
            worst_refdes = refdes
    return {
        "component_count": len(expected),
        "max_coordinate_error": max_error,
        "worst_refdes": worst_refdes,
    }


def _serialized_positions(placedb, placement_path: Path):
    placement = parse_placement(placement_path)
    names = [
        name.decode("utf-8") if isinstance(name, bytes) else str(name)
        for name in placedb.node_names[: placedb.num_physical_nodes]
    ]
    missing = sorted(set(names) - set(placement))
    if missing:
        raise ValueError(f"serialized placement is missing nodes: {missing}")
    node_x = np.asarray(placedb.node_x, dtype=np.float64).copy()
    node_y = np.asarray(placedb.node_y, dtype=np.float64).copy()
    for node_id, name in enumerate(names):
        node_x[node_id], node_y[node_id] = placement[name]
    return node_x, node_y


def score(args) -> dict:
    source = json.loads(args.result.read_text())
    if source.get("status") not in {"FEASIBLE", "OPTIMAL"}:
        raise ValueError("exact-site result has no feasible incumbent")
    if not source.get("candidate_domain_overlap_model_exact"):
        raise ValueError("exact-site result used a relaxed collision model")
    if source.get("certification_required"):
        raise ValueError("exact-site result requires fixed certification")
    if source.get("objective_mode") == "hpwl":
        objective_audit = source.get("objective_replay_audit")
        if not objective_audit or not objective_audit.get("passed"):
            raise ValueError(
                "HPWL-optimized result failed objective replay audit"
            )

    required_fields = {
        "assignment_json",
        "grid_mm",
        "hpwl",
        "selected_sites",
    }
    missing_fields = sorted(required_fields - set(source))
    if missing_fields:
        raise ValueError(
            f"exact-site result is missing fields: {missing_fields}"
        )
    assignment = Path(source["assignment_json"]).resolve()
    context_args = Namespace(
        output_dir=args.output_dir / "context",
        assignment=assignment,
        grid_mm=float(source["grid_mm"]),
        clearance_mm=0.0,
        bookshelf_dir=args.bookshelf_dir,
    )
    placedb, context = _load_context(context_args)
    node_x, node_y = _result_positions(
        source, placedb, context, args.bookshelf_dir
    )
    position = torch.from_numpy(np.concatenate((node_x, node_y)))
    legality = context.exact_report(position, placedb)
    if legality["keepin_violation_count"] or legality["overlap_pair_count"]:
        raise ValueError("exact-site result failed independent exact legality")

    reconstructed_hpwl = float(placedb.hpwl(node_x, node_y))
    reported_hpwl = float(source["hpwl"])
    hpwl_error = abs(reconstructed_hpwl - reported_hpwl)
    if hpwl_error > 1e-5:
        raise ValueError(
            "reconstructed HPWL does not match exact-site result: "
            f"error={hpwl_error}"
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    placement_path = args.output_dir / "m336.native.pl"
    _write_placement_atomic(placedb, placement_path, node_x, node_y)
    serialized_x, serialized_y = _serialized_positions(
        placedb, placement_path
    )
    serialized_position = torch.from_numpy(
        np.concatenate((serialized_x, serialized_y))
    )
    serialized_legality = context.exact_report(
        serialized_position, placedb
    )
    if (
        serialized_legality["keepin_violation_count"]
        or serialized_legality["overlap_pair_count"]
    ):
        raise ValueError("serialized placement failed exact legality")
    serialized_hpwl = float(placedb.hpwl(serialized_x, serialized_y))
    bookshelf = args.bookshelf_dir
    for filename in ("m336.nodes", "m336.nets", "m336.scl"):
        _copy_atomic(bookshelf / filename, args.output_dir / filename)
    aux_path = args.output_dir / "m336.native.aux"
    _write_text_atomic(
        aux_path,
        "RowBasedPlacement : m336.nodes m336.nets "
        "m336.native.pl m336.scl\n",
    )

    baseline = json.loads(args.baseline_result.read_text())
    baseline_config = ROOT / baseline["artifacts"]["config"]
    config = json.loads(baseline_config.read_text())
    native_dir = args.output_dir / "native"
    config.update(
        {
            "aux_input": str(aux_path.resolve()),
            "deterministic_flag": 1,
            "evaluate_pl": 0,
            "global_place_flag": 0,
            "plot_flag": 0,
            "result_dir": str(native_dir.resolve()),
        }
    )
    config_path = args.output_dir / "placement.json"
    _write_json_atomic(config_path, config)

    command = [args.python, str(args.placer), str(config_path)]
    environment = os.environ.copy()
    environment.update(
        {
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "PYTHONFAULTHANDLER": "1",
            "PYTHONPATH": str(ROOT / "install"),
        }
    )
    completed = subprocess.run(
        command,
        cwd=args.output_dir,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    process_log = args.output_dir / "process.log"
    _write_text_atomic(process_log, completed.stdout)
    if completed.returncode:
        raise RuntimeError(
            f"native scoring exited {completed.returncode}; see {process_log}"
        )

    logs = list(native_dir.rglob("DREAMPlace.log"))
    placements = list(native_dir.rglob("*.gp.pl"))
    if len(logs) != 1 or len(placements) != 1:
        raise RuntimeError(
            "native scoring emitted unexpected artifacts: "
            f"logs={logs} placements={placements}"
        )
    ppa = parse_final_ppa(logs[0].read_text())
    replay_audit = _coordinate_replay_audit(placement_path, placements[0])
    if replay_audit["max_coordinate_error"] > 1e-9:
        raise ValueError(f"native scoring moved the placement: {replay_audit}")

    baseline_hpwl = float(baseline["metrics"]["hpwl"])
    baseline_rsmt = float(baseline["metrics"]["rsmt"])
    native_hpwl = float(ppa["hpwl"])
    native_rsmt = float(ppa["rsmt"])
    if (
        not math.isfinite(native_hpwl)
        or not math.isfinite(native_rsmt)
        or native_hpwl <= 0
        or native_rsmt <= 0
    ):
        raise ValueError(
            f"native scorer returned invalid metrics: hpwl={native_hpwl} "
            f"rsmt={native_rsmt}"
        )
    native_hpwl_error = abs(native_hpwl - serialized_hpwl)
    native_hpwl_tolerance = max(1e-3, abs(serialized_hpwl) * 1e-6)
    if native_hpwl_error > native_hpwl_tolerance:
        raise ValueError(
            "native HPWL does not match the serialized placement: "
            f"error={native_hpwl_error} tolerance={native_hpwl_tolerance}"
        )
    normalized_score = 2.0 / (
        native_hpwl / baseline_hpwl + native_rsmt / baseline_rsmt
    )
    result = {
        "schema": "m336_exact_site_native_score_v1",
        "source_result": str(args.result),
        "source_result_sha256": _sha256(args.result),
        "input_sha256": {
            "baseline_result": _sha256(args.baseline_result),
            "baseline_config": _sha256(baseline_config),
            "bookshelf_nodes": _sha256(bookshelf / "m336.nodes"),
            "bookshelf_nets": _sha256(bookshelf / "m336.nets"),
            "bookshelf_scl": _sha256(bookshelf / "m336.scl"),
            "placer": _sha256(args.placer),
        },
        "assignment": str(assignment),
        "assignment_sha256": _sha256(assignment),
        "placement": str(placement_path),
        "placement_sha256": _sha256(placement_path),
        "command": command,
        "legality": legality,
        "serialized_legality": serialized_legality,
        "coordinate_replay_audit": replay_audit,
        "metrics": {
            "reconstructed_hpwl": reconstructed_hpwl,
            "serialized_hpwl": serialized_hpwl,
            "serialization_hpwl_error": abs(
                serialized_hpwl - reconstructed_hpwl
            ),
            "reported_hpwl": reported_hpwl,
            "reconstructed_hpwl_error": hpwl_error,
            "native_hpwl": native_hpwl,
            "native_hpwl_error": native_hpwl_error,
            "native_hpwl_tolerance": native_hpwl_tolerance,
            "native_rsmt": native_rsmt,
            "baseline_hpwl": baseline_hpwl,
            "baseline_rsmt": baseline_rsmt,
            "normalized_quality_score": normalized_score,
            "minimum_score": args.minimum_score,
            "score_pass": normalized_score + 1e-12 >= args.minimum_score,
        },
        "artifacts": {
            "aux": str(aux_path),
            "config": str(config_path),
            "log": str(logs[0]),
            "native_placement": str(placements[0]),
            "process_log": str(process_log),
        },
    }
    _write_json_atomic(args.output_dir / "result.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--bookshelf-dir",
        type=Path,
        default=ROOT / "results/m336/bookshelf",
    )
    parser.add_argument(
        "--baseline-result", type=Path, default=DEFAULT_BASELINE_RESULT
    )
    parser.add_argument("--minimum-score", type=float, default=1.0)
    parser.add_argument("--python", default="python3.11")
    parser.add_argument(
        "--placer", type=Path, default=ROOT / "install/dreamplace/Placer.py"
    )
    args = parser.parse_args()
    args.result = args.result.resolve()
    args.output_dir = args.output_dir.resolve()
    args.bookshelf_dir = args.bookshelf_dir.resolve()
    args.baseline_result = args.baseline_result.resolve()
    args.placer = args.placer.resolve()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        parser.error(f"--output-dir must be empty: {args.output_dir}")
    for path in (
        args.result,
        args.baseline_result,
        args.placer,
        args.bookshelf_dir / "m336.aux",
        args.bookshelf_dir / "m336.baseline.pl",
    ):
        if not path.exists():
            parser.error(f"required input does not exist: {path}")
    if args.minimum_score <= 0:
        parser.error("--minimum-score must be positive")

    result = score(args)
    print(json.dumps(result["metrics"], indent=2, sort_keys=True))
    return 0 if result["metrics"]["score_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
