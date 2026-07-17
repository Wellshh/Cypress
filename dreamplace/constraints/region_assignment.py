"""Cluster validation, side splitting, and fixed region assignment."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Sequence, Tuple


@dataclass(frozen=True)
class Cluster:
    group_id: str
    page: int
    anchor_refdes: str
    members: Tuple[str, ...]


@dataclass(frozen=True)
class SideSubgroup:
    group_id: str
    subgroup_id: str
    page: int
    anchor_refdes: str
    side: str
    members: Tuple[str, ...]


@dataclass(frozen=True)
class RegionAssignment:
    subgroup: SideSubgroup
    region_id: str
    source_status: str


def load_clusters(path) -> Tuple[Cluster, ...]:
    with Path(path).open() as stream:
        data = json.load(stream)
    rows = data.get("clusters", [])
    clusters = []
    seen_members = set()
    for row in rows:
        members = tuple(row["members"])
        anchor = row["anchor_refdes"]
        if anchor not in members:
            raise ValueError("cluster anchor %s is not a member" % anchor)
        duplicates = seen_members.intersection(members)
        if duplicates:
            raise ValueError("cluster members are not unique: %s" % sorted(duplicates))
        if len(set(members)) != len(members):
            raise ValueError("duplicate member inside %s" % row["module_id"])
        if row.get("member_count") != len(members):
            raise ValueError("member count mismatch in %s" % row["module_id"])
        seen_members.update(members)
        clusters.append(
            Cluster(
                group_id=row["module_id"],
                page=int(row["page"]),
                anchor_refdes=anchor,
                members=members,
            )
        )

    enumerated = data.get("enumerated_statistics", {})
    declared_members = enumerated.get("clustered_components")
    if declared_members is not None and int(declared_members) != len(seen_members):
        raise ValueError("enumerated clustered member count does not match rows")
    return tuple(clusters)


def split_side_subgroups(
    clusters: Sequence[Cluster], component_sides: Mapping[str, str]
) -> Tuple[SideSubgroup, ...]:
    subgroups = []
    for cluster in clusters:
        by_side: Dict[str, list] = {}
        for refdes in cluster.members:
            if refdes not in component_sides:
                raise KeyError("cluster member missing from geometry: %s" % refdes)
            side = component_sides[refdes].upper()
            if side not in {"TOP", "BOTTOM"}:
                raise ValueError("unsupported component side for %s: %s" % (refdes, side))
            by_side.setdefault(side, []).append(refdes)
        for side in sorted(by_side):
            subgroups.append(
                SideSubgroup(
                    group_id=cluster.group_id,
                    subgroup_id="%s__%s" % (cluster.group_id, side.lower()),
                    page=cluster.page,
                    anchor_refdes=cluster.anchor_refdes,
                    side=side,
                    members=tuple(by_side[side]),
                )
            )
    return tuple(subgroups)


def load_region_assignments(
    path,
    subgroups: Sequence[SideSubgroup],
    region_sides: Mapping[str, str],
) -> Tuple[RegionAssignment, ...]:
    with Path(path).open() as stream:
        data = json.load(stream)
    rows = {row["subgroup_id"]: row for row in data.get("assignments", [])}
    expected = {subgroup.subgroup_id for subgroup in subgroups}
    missing = expected - rows.keys()
    extra = rows.keys() - expected
    if missing or extra:
        raise ValueError(
            "assignment/subgroup mismatch; missing=%s extra=%s"
            % (sorted(missing), sorted(extra))
        )

    assignments = []
    for subgroup in subgroups:
        row = rows[subgroup.subgroup_id]
        if tuple(row["member_refdes"]) != subgroup.members:
            raise ValueError("assignment member order/content mismatch: %s" % subgroup.subgroup_id)
        if row["anchor_refdes"] != subgroup.anchor_refdes:
            raise ValueError("assignment anchor mismatch: %s" % subgroup.subgroup_id)
        region_id = row["proposed_region_id"]
        if region_id not in region_sides:
            raise ValueError("assignment references unknown region: %s" % region_id)
        if region_sides[region_id].upper() != subgroup.side:
            raise ValueError(
                "assignment side mismatch for %s: %s versus %s"
                % (subgroup.subgroup_id, subgroup.side, region_sides[region_id])
            )
        assignments.append(
            RegionAssignment(
                subgroup=subgroup,
                region_id=region_id,
                source_status=row.get("status", "unknown"),
            )
        )
    return tuple(assignments)
