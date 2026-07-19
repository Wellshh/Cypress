#!/usr/bin/env python3
"""Export a self-contained, portable M336 exact-site checkpoint."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path


SCHEMA = "m336_exact_site_checkpoint_v1"


def resolve_result_path(result_path: Path, value: str | Path) -> Path:
    """Resolve metadata paths relative to the result that declares them."""
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = Path(result_path).parent / path
    return path.resolve()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_json(value) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_certificate(source: dict) -> None:
    if source.get("status") not in {"FEASIBLE", "OPTIMAL"}:
        raise ValueError("checkpoint source has no feasible incumbent")
    if not source.get("candidate_domain_overlap_model_exact"):
        raise ValueError("checkpoint source used a relaxed collision model")
    if source.get("certification_required"):
        raise ValueError("checkpoint source still requires certification")
    replay = source.get("objective_replay_audit", {})
    replay_required = source.get("objective_mode") in {
        "hpwl",
        "hpwl_feasibility",
    }
    if replay_required and not replay.get("passed"):
        raise ValueError("checkpoint source failed objective replay")
    legality = source.get("legality", {})
    if legality.get("keepin_violation_count") or legality.get(
        "overlap_pair_count"
    ):
        raise ValueError("checkpoint source failed exact legality")
    for field in ("assignment_json", "placement", "selected_sites"):
        if not source.get(field):
            raise ValueError(f"checkpoint source is missing {field}")


def export_checkpoint(
    result_path: Path,
    output_dir: Path,
    assignment_path: Path | None = None,
    quality_guide_path: Path | None = None,
) -> dict:
    result_path = Path(result_path).resolve()
    output_dir = Path(output_dir).resolve()
    source = json.loads(result_path.read_text())
    _validate_certificate(source)

    assignment_path = (
        Path(assignment_path).resolve()
        if assignment_path is not None
        else resolve_result_path(result_path, source["assignment_json"])
    )
    placement_path = resolve_result_path(result_path, source["placement"])
    quality_guide_path = (
        Path(quality_guide_path).resolve()
        if quality_guide_path is not None
        else None
    )
    required_files = [result_path, assignment_path, placement_path]
    if quality_guide_path is not None:
        required_files.append(quality_guide_path)
    missing = [str(path) for path in required_files if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            f"checkpoint dependencies are missing: {missing}"
        )
    if output_dir.exists():
        raise FileExistsError(f"checkpoint output already exists: {output_dir}")

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{output_dir.name}.", dir=output_dir.parent
        )
    )
    try:
        original_name = "certificate.original.json"
        certificate_name = "certificate.json"
        assignment_name = "assignment.json"
        placement_name = "placement.pl"
        guide_name = "quality-guide.json"

        shutil.copyfile(result_path, staging / original_name)
        shutil.copyfile(assignment_path, staging / assignment_name)
        shutil.copyfile(placement_path, staging / placement_name)
        if quality_guide_path is not None:
            shutil.copyfile(quality_guide_path, staging / guide_name)

        portable = dict(source)
        portable["assignment_json"] = assignment_name
        portable["placement"] = placement_name
        portable["checkpoint"] = {
            "schema": SCHEMA,
            "original_result_sha256": sha256_file(result_path),
            "original_placement_sha256": sha256_file(placement_path),
            "quality_guide": (
                guide_name if quality_guide_path is not None else None
            ),
            "selected_sites_sha256": _sha256_json(source["selected_sites"]),
        }
        (staging / certificate_name).write_text(
            json.dumps(portable, indent=2, sort_keys=True) + "\n"
        )

        artifact_names = [
            original_name,
            certificate_name,
            assignment_name,
            placement_name,
        ]
        if quality_guide_path is not None:
            artifact_names.append(guide_name)
        manifest = {
            "schema": SCHEMA,
            "entrypoint": certificate_name,
            "files": {
                name: {"sha256": sha256_file(staging / name)}
                for name in artifact_names
            },
            "selected_sites_sha256": _sha256_json(source["selected_sites"]),
        }
        (staging / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        )
        staging.replace(output_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return manifest


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--assignment", type=Path)
    parser.add_argument("--quality-guide", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = export_checkpoint(
        args.result,
        args.output_dir,
        assignment_path=args.assignment,
        quality_guide_path=args.quality_guide,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
