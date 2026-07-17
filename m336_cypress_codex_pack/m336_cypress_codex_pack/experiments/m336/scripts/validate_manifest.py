#!/usr/bin/env python3
"""Validate the self-contained M336 experiment inputs without Cypress or GPU."""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "input"


def load(name: str):
    path = INPUT / name
    with path.open("r", encoding="utf-8") as f:
        return json.load(f), path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def main() -> int:
    clusters, cluster_path = load("m336_clusters.json")
    geometry, geometry_path = load("pcb_geometry_keepin.json")
    assignment, assignment_path = load("m336_region_assignment.seed.json")

    rows = clusters["clusters"]
    members = [m for row in rows for m in row["members"]]
    unique_members = set(members)

    if len(rows) != clusters["enumerated_statistics"]["enumerated_module_count"]:
        fail("enumerated module count does not match rows")
    if len(members) != clusters["enumerated_statistics"]["enumerated_clustered_components"]:
        fail("clustered member count does not match")
    if len(unique_members) != len(members):
        duplicates = [m for m, count in Counter(members).items() if count > 1]
        fail(f"cluster members are duplicated: {duplicates}")

    for row in rows:
        if row["anchor_refdes"] not in row["members"]:
            fail(f"anchor missing from members: {row['module_id']}")

    symbols = {
        s.get("refdes"): s
        for s in geometry.get("symbols", [])
        if s.get("refdes")
    }
    missing = sorted(unique_members - symbols.keys())
    if missing:
        fail(f"cluster refdes missing from geometry: {missing}")

    region_ids = {
        f"{entry['placement_side'].lower()}_{index}"
        for entry in geometry.get("component_placeable_regions", [])
        for index, _ in enumerate(entry.get("shapes", []))
    }
    for row in assignment["assignments"]:
        if row["proposed_region_id"] not in region_ids:
            fail(f"assignment references unknown region: {row['proposed_region_id']}")
        for refdes in row["member_refdes"]:
            if refdes not in unique_members:
                fail(f"assignment references non-cluster member: {refdes}")
            side = symbols[refdes]["layer"].upper()
            if side != row["placement_side"]:
                fail(
                    f"side mismatch for {refdes}: symbol={side}, assignment={row['placement_side']}"
                )

    expected_assignment_members = [
        m for row in assignment["assignments"] for m in row["member_refdes"]
    ]
    if Counter(expected_assignment_members) != Counter(members):
        fail("assignment rows do not cover cluster members exactly once")

    declared = clusters["declared_statistics"]["declared_module_count"]
    enumerated = len(rows)

    print("M336 input validation: PASS")
    print(f"  enumerated modules: {enumerated}")
    print(f"  declared modules:   {declared}")
    print(f"  clustered members:  {len(members)}")
    print(f"  unique members:     {len(unique_members)}")
    print(f"  assignment rows:    {len(assignment['assignments'])}")
    print(f"  region IDs:         {sorted(region_ids)}")
    print(f"  geometry symbols:   {len(symbols)}")
    print(f"  geometry nets:      {len(geometry.get('nets', []))}")
    print(f"  cluster sha256:     {sha256(cluster_path)}")
    print(f"  geometry sha256:    {sha256(geometry_path)}")
    print(f"  assignment sha256:  {sha256(assignment_path)}")

    if declared != enumerated:
        print(
            "WARNING: declared module count is 27 but the supplied table enumerates "
            f"{enumerated}. The enumerated rows contain the declared 125 clustered members. "
            "Do not invent missing modules.",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
