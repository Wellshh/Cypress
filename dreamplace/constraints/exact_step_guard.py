"""Transactional optimizer-step guard for exact placement constraints."""

from __future__ import annotations

import copy
import hashlib
import math
import time
from dataclasses import dataclass

import torch


@dataclass(frozen=True)
class _ParameterReference:
    group_index: int
    parameter_index: int


@dataclass(frozen=True)
class ExactValidationProvenance:
    """Bind one exact report to the tensor bytes that produced it."""

    position: torch.Tensor
    report: dict
    source: str

    @classmethod
    def capture(cls, position, report, source):
        if not torch.is_tensor(position):
            raise TypeError("exact validation provenance requires a tensor")
        if not isinstance(report, dict):
            raise TypeError("exact validation provenance requires a report")
        source = str(source)
        if not source:
            raise ValueError("exact validation provenance requires a source")
        return cls(
            position=position.detach().clone(),
            report=copy.deepcopy(report),
            source=source,
        )


def _parameter_layout(optimizer):
    layout = []
    references = {}
    for group_index, group in enumerate(optimizer.param_groups):
        group_parameters = []
        for parameter_index, parameter in enumerate(group["params"]):
            identity = id(parameter)
            if identity in references:
                raise ValueError("optimizer parameter appears in more than one group")
            reference = _ParameterReference(group_index, parameter_index)
            references[identity] = reference
            group_parameters.append(parameter)
        layout.append(tuple(group_parameters))
    return tuple(layout), references


def _clone_tensor(value):
    clone = value.detach().clone()
    if value.requires_grad:
        clone.requires_grad_(True)
    return clone


def _snapshot_value(value, parameter_references):
    reference = parameter_references.get(id(value))
    if reference is not None:
        return reference
    if torch.is_tensor(value):
        return _clone_tensor(value)
    if isinstance(value, dict):
        return {
            copy.deepcopy(key): _snapshot_value(item, parameter_references)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_snapshot_value(item, parameter_references) for item in value]
    if isinstance(value, tuple):
        return tuple(_snapshot_value(item, parameter_references) for item in value)
    return copy.deepcopy(value)


def _restore_value(value, parameter_layout):
    if isinstance(value, _ParameterReference):
        return parameter_layout[value.group_index][value.parameter_index]
    if torch.is_tensor(value):
        return _clone_tensor(value)
    if isinstance(value, dict):
        return {
            copy.deepcopy(key): _restore_value(item, parameter_layout)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_restore_value(item, parameter_layout) for item in value]
    if isinstance(value, tuple):
        return tuple(_restore_value(item, parameter_layout) for item in value)
    return copy.deepcopy(value)


def _digest_update(digest, value, parameter_references):
    reference = parameter_references.get(id(value))
    if reference is not None:
        digest.update(
            ("parameter:%d:%d" % (reference.group_index, reference.parameter_index)).encode()
        )
        return
    if torch.is_tensor(value):
        tensor = value.detach().contiguous()
        digest.update(b"tensor:")
        digest.update(str(tensor.dtype).encode())
        digest.update(str(tuple(tensor.shape)).encode())
        digest.update(str(tensor.device).encode())
        digest.update(str(bool(value.requires_grad)).encode())
        digest.update(tensor.reshape(-1).view(torch.uint8).cpu().numpy().tobytes())
        return
    if isinstance(value, dict):
        digest.update(b"dict:")
        for key in sorted(value, key=lambda item: (type(item).__name__, repr(item))):
            _digest_update(digest, key, parameter_references)
            _digest_update(digest, value[key], parameter_references)
        return
    if isinstance(value, (list, tuple)):
        digest.update(("%s:" % type(value).__name__).encode())
        for item in value:
            _digest_update(digest, item, parameter_references)
        return
    digest.update(
        ("%s:%r" % (type(value).__name__, value)).encode("utf-8", errors="backslashreplace")
    )


def tensor_sha256(tensor):
    digest = hashlib.sha256()
    _digest_update(digest, tensor, {})
    return digest.hexdigest()


def optimizer_transition_sha256(optimizer):
    """Hash parameters, gradients, group controls, and optimizer state."""
    digest = hashlib.sha256()
    parameter_layout, references = _parameter_layout(optimizer)
    digest.update(type(optimizer).__qualname__.encode())
    for group_index, (group, parameters) in enumerate(
        zip(optimizer.param_groups, parameter_layout)
    ):
        digest.update(("group:%d" % group_index).encode())
        for parameter in parameters:
            _digest_update(digest, parameter.detach(), {})
            _digest_update(digest, parameter.grad, references)
        controls = {key: value for key, value in group.items() if key != "params"}
        _digest_update(digest, controls, references)
    state_rows = []
    for parameter, state in optimizer.state.items():
        reference = references.get(id(parameter))
        if reference is None:
            raise ValueError("optimizer state belongs to an unknown parameter")
        state_rows.append((reference, state))
    for reference, state in sorted(
        state_rows, key=lambda row: (row[0].group_index, row[0].parameter_index)
    ):
        _digest_update(digest, reference, references)
        _digest_update(digest, state, references)
    return digest.hexdigest()


class OptimizerTransitionSnapshot:
    """Restorable optimizer transition state, including custom group tensors."""

    def __init__(self, optimizer, tracked_position):
        self.parameter_layout, references = _parameter_layout(optimizer)
        self.parameter_values = {
            references[id(parameter)]: parameter.detach().clone()
            for group in self.parameter_layout
            for parameter in group
        }
        self.parameter_gradients = {
            references[id(parameter)]: (
                None if parameter.grad is None else parameter.grad.detach().clone()
            )
            for group in self.parameter_layout
            for parameter in group
        }
        self.group_values = [
            _snapshot_value(
                {key: value for key, value in group.items() if key != "params"},
                references,
            )
            for group in optimizer.param_groups
        ]
        self.state_values = []
        for parameter, state in optimizer.state.items():
            reference = references.get(id(parameter))
            if reference is None:
                raise ValueError("optimizer state belongs to an unknown parameter")
            self.state_values.append(
                (reference, _snapshot_value(state, references))
            )
        self.position_sha256 = tensor_sha256(tracked_position)
        self.optimizer_sha256 = optimizer_transition_sha256(optimizer)

    def _validated_layout(self, optimizer):
        current_layout, _ = _parameter_layout(optimizer)
        if len(current_layout) != len(self.parameter_layout):
            raise RuntimeError("optimizer parameter-group count changed during guarded step")
        for expected_group, current_group in zip(
            self.parameter_layout, current_layout
        ):
            if len(expected_group) != len(current_group) or any(
                expected is not current
                for expected, current in zip(expected_group, current_group)
            ):
                raise RuntimeError("optimizer parameter identity changed during guarded step")
        return current_layout

    def restore(self, optimizer, tracked_position):
        parameter_layout = self._validated_layout(optimizer)
        with torch.no_grad():
            for reference, value in self.parameter_values.items():
                parameter = parameter_layout[reference.group_index][
                    reference.parameter_index
                ]
                parameter.copy_(value)
        for reference, gradient in self.parameter_gradients.items():
            parameter = parameter_layout[reference.group_index][
                reference.parameter_index
            ]
            if gradient is None:
                parameter.grad = None
            elif parameter.grad is None:
                parameter.grad = gradient.detach().clone()
            else:
                parameter.grad.detach().copy_(gradient)

        for group, values in zip(optimizer.param_groups, self.group_values):
            parameters = group["params"]
            group.clear()
            group["params"] = parameters
            group.update(_restore_value(values, parameter_layout))
        optimizer.state.clear()
        for reference, state in self.state_values:
            parameter = parameter_layout[reference.group_index][
                reference.parameter_index
            ]
            optimizer.state[parameter] = _restore_value(state, parameter_layout)

        position_sha256 = tensor_sha256(tracked_position)
        optimizer_sha256 = optimizer_transition_sha256(optimizer)
        return {
            "position_before_sha256": self.position_sha256,
            "position_after_sha256": position_sha256,
            "position_restored": position_sha256 == self.position_sha256,
            "optimizer_before_sha256": self.optimizer_sha256,
            "optimizer_after_sha256": optimizer_sha256,
            "optimizer_restored": optimizer_sha256 == self.optimizer_sha256,
        }


def _scalar(value):
    if torch.is_tensor(value):
        if value.numel() != 1:
            raise ValueError("optimizer step size must be scalar")
        return float(value.detach().cpu().item())
    return float(value)


def optimizer_step_size_summary(optimizer):
    learning_rates = [_scalar(group["lr"]) for group in optimizer.param_groups]
    nesterov_alpha = [
        [_scalar(alpha) for alpha in group.get("alpha_k", ()) if alpha is not None]
        for group in optimizer.param_groups
    ]
    active_alpha = [value for group in nesterov_alpha for value in group]
    return {
        "learning_rates": learning_rates,
        "nesterov_alpha": nesterov_alpha,
        "effective_step_size": (
            active_alpha[0] if len(active_alpha) == 1 else learning_rates[0]
        ),
    }


def scale_optimizer_step_size(optimizer, factor):
    factor = float(factor)
    if not math.isfinite(factor) or factor <= 0 or factor > 1:
        raise ValueError("optimizer step backoff factor must be in (0, 1]")
    with torch.no_grad():
        for group in optimizer.param_groups:
            learning_rate = group["lr"]
            if torch.is_tensor(learning_rate):
                group["lr"] = learning_rate.detach().clone().mul_(factor)
            else:
                group["lr"] = float(learning_rate) * factor
            for alpha in group.get("alpha_k", ()):
                if alpha is not None:
                    alpha.mul_(factor)
    return optimizer_step_size_summary(optimizer)


def _is_legal(report):
    return not report["overlap_pair_count"] and not report["keepin_violation_count"]


def _overlap_pair_key(row):
    return (
        row.get("kind"),
        row.get("first_refdes"),
        row.get("second_refdes"),
    )


def _provenance_report(evidence, key, position):
    provenance = evidence.get(key)
    if provenance is None:
        return None, None
    if not isinstance(provenance, ExactValidationProvenance):
        raise TypeError("%s must be exact validation provenance" % key)
    snapshot = provenance.position
    if snapshot.shape != position.shape:
        raise RuntimeError("%s shape mismatch" % key)
    if snapshot.dtype != position.dtype:
        raise RuntimeError("%s dtype mismatch" % key)
    if snapshot.device != position.device:
        raise RuntimeError("%s device mismatch" % key)
    if not torch.equal(snapshot, position):
        raise RuntimeError("%s coordinate mismatch" % key)
    return copy.deepcopy(provenance.report), provenance.source


class ExactStepGuardFailure(RuntimeError):
    def __init__(self, reason, before, attempts, timing=None):
        super().__init__("exact accepted-step guard failed: %s" % reason)
        self.reason = str(reason)
        self.before = before
        self.attempts = attempts
        self.timing = {} if timing is None else dict(timing)


class ExactAcceptedStepGuard:
    """Reject exact-illegal optimizer transitions and retry with bounded steps."""

    def __init__(
        self,
        validator,
        backoff=0.5,
        max_retries=4,
        barrier_diagnostics=None,
        attempt_metadata=None,
    ):
        self.validator = validator
        self.backoff = float(backoff)
        self.max_retries = int(max_retries)
        self.barrier_diagnostics = barrier_diagnostics
        self.attempt_metadata = attempt_metadata
        if not math.isfinite(self.backoff) or not 0 < self.backoff < 1:
            raise ValueError("exact-step guard backoff must be in (0, 1)")
        if self.max_retries < 0:
            raise ValueError("exact-step guard retries must be non-negative")
        self._accepted_cache = None

    def run(self, position, optimizer, attempt_fn):
        snapshot_started = time.perf_counter()
        snapshot = OptimizerTransitionSnapshot(optimizer, position)
        snapshot_seconds = time.perf_counter() - snapshot_started
        if (
            self._accepted_cache is not None
            and self._accepted_cache[0] == snapshot.position_sha256
        ):
            before = copy.deepcopy(self._accepted_cache[1])
            before_validation_seconds = 0.0
        else:
            before_started = time.perf_counter()
            before = self.validator(position)
            before_validation_seconds = time.perf_counter() - before_started
        timing = {
            "snapshot_seconds": snapshot_seconds,
            "before_validation_seconds": before_validation_seconds,
            "proposal_validation_seconds": 0.0,
            "projected_validation_seconds": 0.0,
            "barrier_diagnostic_seconds": 0.0,
            "metadata_seconds": 0.0,
            "rollback_seconds": 0.0,
            "optimizer_attempt_seconds": 0.0,
        }
        if not _is_legal(before):
            raise ExactStepGuardFailure("illegal_start", before, [], timing)

        before_pairs = {
            _overlap_pair_key(row) for row in before.get("overlap_pairs", ())
        }
        attempts = []
        for retry_index in range(self.max_retries + 1):
            if retry_index:
                scale_optimizer_step_size(
                    optimizer, self.backoff ** retry_index
                )
            attempt_started = time.perf_counter()
            state_before_sha256 = optimizer_transition_sha256(optimizer)
            position_before_sha256 = tensor_sha256(position)
            step_size = optimizer_step_size_summary(optimizer)
            optimizer_attempt_seconds = 0.0
            try:
                optimizer_attempt_started = time.perf_counter()
                evidence = attempt_fn()
                optimizer_attempt_seconds = (
                    time.perf_counter() - optimizer_attempt_started
                )
                timing["optimizer_attempt_seconds"] += optimizer_attempt_seconds
                proposal = evidence["proposal_position"]
                accepted = evidence["accepted_position"]
                if proposal is None or accepted is None:
                    raise RuntimeError("guarded optimizer attempt lacks coordinates")
                if (
                    evidence.get("proposal_validation_provenance") is not None
                    and evidence.get("accepted_validation_provenance") is None
                ):
                    raise RuntimeError(
                        "proposal validation provenance requires accepted "
                        "provenance"
                    )
                proposal_validation_started = time.perf_counter()
                proposal_report, proposal_validation_source = (
                    _provenance_report(
                        evidence,
                        "proposal_validation_provenance",
                        proposal,
                    )
                )
                if proposal_report is None:
                    proposal_report = self.validator(proposal)
                proposal_validation_seconds = (
                    time.perf_counter() - proposal_validation_started
                )
                timing["proposal_validation_seconds"] += (
                    proposal_validation_seconds
                )
                accepted_validation_started = time.perf_counter()
                accepted_report, accepted_validation_source = (
                    _provenance_report(
                        evidence,
                        "accepted_validation_provenance",
                        accepted,
                    )
                )
                if accepted_report is not None:
                    projected_validation_seconds = (
                        time.perf_counter() - accepted_validation_started
                    )
                elif torch.equal(proposal, accepted):
                    accepted_report = copy.deepcopy(proposal_report)
                    projected_validation_seconds = (
                        time.perf_counter() - accepted_validation_started
                    )
                else:
                    accepted_report = self.validator(accepted)
                    projected_validation_seconds = (
                        time.perf_counter() - accepted_validation_started
                    )
                timing["projected_validation_seconds"] += (
                    projected_validation_seconds
                )
                barrier_started = time.perf_counter()
                barrier = (
                    self.barrier_diagnostics(accepted)
                    if self.barrier_diagnostics is not None
                    else None
                )
                barrier_seconds = time.perf_counter() - barrier_started
                timing["barrier_diagnostic_seconds"] += barrier_seconds
                metadata_started = time.perf_counter()
                metadata = (
                    self.attempt_metadata(evidence)
                    if self.attempt_metadata is not None
                    else {}
                )
                metadata_seconds = time.perf_counter() - metadata_started
                timing["metadata_seconds"] += metadata_seconds
            except Exception as error:
                rollback_started = time.perf_counter()
                rollback = snapshot.restore(optimizer, position)
                rollback_seconds = time.perf_counter() - rollback_started
                timing["rollback_seconds"] += rollback_seconds
                attempts.append(
                    {
                        "retry_index": retry_index,
                        "accepted": False,
                        "reason": "attempt_exception",
                        "exception": "%s: %s" % (type(error).__name__, error),
                        "step_size": step_size,
                        "position_before_sha256": position_before_sha256,
                        "optimizer_before_sha256": state_before_sha256,
                        "rollback": rollback,
                        "optimizer_attempt_seconds": optimizer_attempt_seconds,
                        "rollback_seconds": rollback_seconds,
                        "elapsed_seconds": time.perf_counter() - attempt_started,
                    }
                )
                raise ExactStepGuardFailure(
                    "attempt_exception", before, attempts, timing
                ) from error

            new_pairs = [
                row
                for row in accepted_report.get("overlap_pairs", ())
                if _overlap_pair_key(row) not in before_pairs
            ]
            legal = _is_legal(accepted_report)
            attempt = {
                "retry_index": retry_index,
                "accepted": legal,
                "reason": "accepted" if legal else "exact_illegal_candidate",
                "step_size": step_size,
                "position_before_sha256": position_before_sha256,
                "optimizer_before_sha256": state_before_sha256,
                "position_after_sha256": tensor_sha256(position),
                "optimizer_after_sha256": optimizer_transition_sha256(optimizer),
                "before": before,
                "proposal": proposal_report,
                "projected": accepted_report,
                "new_overlap_pairs": new_pairs[:16],
                "barrier": barrier,
                "optimizer_attempt_seconds": optimizer_attempt_seconds,
                "proposal_validation_seconds": proposal_validation_seconds,
                "projected_validation_seconds": projected_validation_seconds,
                "barrier_diagnostic_seconds": barrier_seconds,
                "metadata_seconds": metadata_seconds,
                "elapsed_seconds": time.perf_counter() - attempt_started,
                **metadata,
            }
            if (
                proposal_validation_source is not None
                or accepted_validation_source is not None
            ):
                attempt.update(
                    {
                        "proposal_validation_cache_hit": (
                            proposal_validation_source is not None
                        ),
                        "proposal_validation_source": (
                            proposal_validation_source
                        ),
                        "accepted_validation_cache_hit": (
                            accepted_validation_source is not None
                        ),
                        "accepted_validation_source": (
                            accepted_validation_source
                        ),
                    }
                )
            attempts.append(attempt)
            if legal:
                self._accepted_cache = (
                    tensor_sha256(position),
                    copy.deepcopy(accepted_report),
                )
                return {
                    "attempts": attempts,
                    "accepted_report": accepted_report,
                    "step_evidence": evidence,
                    "snapshot_seconds": snapshot_seconds,
                    "timing": {
                        **timing,
                        "guard_overhead_seconds": sum(
                            value
                            for key, value in timing.items()
                            if key != "optimizer_attempt_seconds"
                        ),
                    },
                    "total_seconds": sum(
                        row["elapsed_seconds"] for row in attempts
                    )
                    + snapshot_seconds,
                }

            rollback_started = time.perf_counter()
            rollback = snapshot.restore(optimizer, position)
            rollback_seconds = time.perf_counter() - rollback_started
            timing["rollback_seconds"] += rollback_seconds
            attempt["rollback"] = rollback
            attempt["rollback_seconds"] = rollback_seconds
            if not rollback["position_restored"] or not rollback[
                "optimizer_restored"
            ]:
                raise ExactStepGuardFailure(
                    "rollback_mismatch", before, attempts, timing
                )

        raise ExactStepGuardFailure("retry_exhausted", before, attempts, timing)
