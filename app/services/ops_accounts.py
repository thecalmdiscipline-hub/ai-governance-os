"""
OpsAccount status machine (Batch I, Fase 2.1).

Pipeline: lead -> qualified -> proposal -> contract -> onboarding -> live. A transition is allowed
if the new status is strictly LATER in that sequence than the current one (skipping stages ahead
is allowed — real pipelines don't always pass through every stage — but moving backward never is).
'lost' is reachable from any pre-live pipeline status; 'churned' only from 'live'. 'lost' and
'churned' are terminal: no further transitions out of them. Setting the same status again is a
no-op (not an error), mirroring PATCH /ops/support-requests/{id}'s "only act if it actually
changes" convention.
"""
from typing import Optional

PIPELINE = ("lead", "qualified", "proposal", "contract", "onboarding", "live")
TERMINAL = ("lost", "churned")
ALL_STATUSES = PIPELINE + TERMINAL


def is_valid_status(value: str) -> bool:
    return value in ALL_STATUSES


def validate_transition(old_status: str, new_status: str) -> Optional[str]:
    """Returns None if the transition is allowed, or a short machine-readable reason if not."""
    if old_status == new_status:
        return None  # no-op, always allowed

    if old_status in TERMINAL:
        return "status_is_terminal"

    if new_status == "lost":
        return None if old_status in PIPELINE and old_status != "live" else "invalid_transition"

    if new_status == "churned":
        return None if old_status == "live" else "invalid_transition"

    if old_status not in PIPELINE or new_status not in PIPELINE:
        return "invalid_transition"

    return None if PIPELINE.index(new_status) > PIPELINE.index(old_status) else "invalid_transition"
