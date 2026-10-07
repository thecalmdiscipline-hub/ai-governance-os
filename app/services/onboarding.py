"""
Onboarding templates and projects (Batch I, Fase 2.2): a project copies its tasks from a named,
versioned template at creation time, so later template edits never change a running project.

STANDARD_V1_TASKS is the single source of truth for the 'standard-v1' template's content — both
scripts/seed_onboarding_templates.py (which writes OnboardingTemplate/OnboardingTemplateTask rows)
and create_project_from_template() (which copies them into a project) go through this module, so
there is one place that encodes the Client Onboarding Playbook's 8 phases.
"""
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.onboarding_project import OnboardingProject
from app.models.onboarding_task import OnboardingTask
from app.models.onboarding_template import OnboardingTemplate
from app.models.onboarding_template_task import OnboardingTemplateTask

STANDARD_V1_KEY = "standard-v1"
STANDARD_V1_NAME = "Standard client onboarding"
STANDARD_V1_VERSION = "1"

PROJECT_STATUSES = ("active", "paused", "completed", "cancelled")
TASK_STATUSES = ("todo", "doing", "done", "skipped", "blocked")
# A project is considered "in progress" (blocks starting a second one for the same account) while
# in either of these — only completed/cancelled free up a new project.
_OPEN_PROJECT_STATUSES = ("active", "paused")

# (phase, position, title, owner, customer_visible) — owner is "valqeron" | "customer" | "both".
# Derived from the Client Onboarding Playbook (19 sep), as given in the hand-off's Deel 2 table.
STANDARD_V1_TASKS: List[Tuple[int, int, str, str, bool]] = [
    # Phase 1 — Lead & kwalificatie
    (1, 1, "Lead vastleggen: bron, bedrijf, contact", "valqeron", False),
    (1, 2, "Kwalificeren op ICP: omzet, sector, AI-volwassenheid, compliance-druk", "valqeron", False),
    (1, 3, "Tier voorstellen en relevante workflows noteren", "valqeron", False),
    # Phase 2 — Voorstel, contract & DPA
    (2, 1, "Voorstel opstellen: tier, workflows, implementatiefee, maandbedrag", "valqeron", False),
    (2, 2, "Voorstel akkoord", "customer", True),
    (2, 3, "DPA getekend", "both", True),
    (2, 4, "Gegevens van de klant ontvangen: bedrijfsnaam, land, sector, eerste beheerder, rollen overige gebruikers", "customer", True),
    # Phase 3 — Kickoff (task at position 1 anchors the "kickoff" metric — see get_project_metrics())
    (3, 1, "Kickoff call plannen", "both", True),
    (3, 2, "Doelen en scope bevestigen per workflow", "both", True),
    (3, 3, "Technisch contactpersoon en rollen toewijzen: admin, auditor, operator", "customer", True),
    (3, 4, "Go-live datum vastleggen", "both", True),
    # Phase 4 — Technische provisioning
    (4, 1, "Organisatie, beheerder en modules aanmaken via provisioning, met tier-check", "valqeron", False),
    (4, 2, "Eenmalig wachtwoord via een apart, veilig kanaal overgedragen", "valqeron", False),
    (4, 3, "Standaard AIPolicy vastgelegd", "valqeron", False),
    (4, 4, "PII-anonimisering bevestigd voor het datatype van deze klant", "valqeron", False),
    # Phase 5 — Configuratie & data
    (5, 1, "Eerste documenten handmatig geüpload", "both", True),
    (5, 2, "Voorbeeldresultaat klaargezet", "valqeron", False),
    (5, 3, "Risicoregister initieel gevuld: één AIRisk-rij per actieve workflow", "valqeron", False),
    # Phase 6 — Training & overdracht
    (6, 1, "Trainingssessie gepland", "both", True),
    (6, 2, "Training gegeven met de Client Portal Guide", "valqeron", True),
    (6, 3, "Rollen en resultaten beoordelen uitgelegd", "valqeron", True),
    # Phase 7 — Go-live verificatie (last task's completion anchors the "kickoff-to-golive" / phase-7 metric)
    (7, 1, "Elke actieve module minstens één keer gedraaid", "valqeron", False),
    (7, 2, "Resultaat samen met de klant bekeken en beoordeeld", "both", True),
    (7, 3, "Run zichtbaar in de audit trail en /audit/verify is valid voor de organisatie", "valqeron", False),
    (7, 4, 'Dashboard toont "Core active and ready"', "valqeron", False),
    # Phase 8 — Nazorg (last task's completion anchors the "total" metric)
    (8, 1, "Eerste-week check-in", "valqeron", True),
    (8, 2, "Eerste maandelijkse gebruiksrapportage verstuurd", "valqeron", True),
    (8, 3, "Kwartaal-risicoregister-review ingepland", "valqeron", False),
]

KICKOFF_PHASE = 3
GOLIVE_PHASE = 7
FINAL_PHASE = 8

# English titles for the 14 customer_visible standard-v1 tasks (Batch N1, 2026-10-07). Keyed by
# (phase, position), not by the stored (Dutch) title, so a later edit to the stored text doesn't
# silently break the lookup. Read-only translation at response time — app/api/onboarding.py's
# GET /onboarding/progress falls back to the stored title when a key is missing (e.g. a future
# customer_visible task added here without an English translation yet); the ops-tab and the
# stored OnboardingTask rows themselves stay Dutch, unchanged. No migration, no rewritten rows.
CUSTOMER_TASK_TITLES_EN: Dict[Tuple[int, int], str] = {
    (2, 2): "Proposal approved",
    (2, 3): "DPA signed",
    (2, 4): "Company details received: company name, country, sector, first administrator, roles of other users",
    (3, 1): "Kickoff call scheduled",
    (3, 2): "Goals and scope confirmed per workflow",
    (3, 3): "Technical contact and roles assigned: admin, auditor, operator",
    (3, 4): "Go-live date agreed",
    (5, 1): "First documents uploaded",
    (6, 1): "Training session scheduled",
    (6, 2): "Training delivered with the Client Portal Guide",
    (6, 3): "Roles and reviewing results explained",
    (7, 2): "Result reviewed together with you",
    (8, 1): "First-week check-in",
    (8, 2): "First monthly usage report sent",
}


def seed_standard_v1(db: Session, dry_run: bool = False) -> Dict[str, object]:
    """Idempotent, insert-only: creates the 'standard-v1' template + its tasks if they don't exist
    yet. Never overwrites an existing template or its tasks (mirrors scripts/seed_modules.py)."""
    existing = db.query(OnboardingTemplate).filter(OnboardingTemplate.key == STANDARD_V1_KEY).first()
    if existing is not None:
        task_count = db.query(OnboardingTemplateTask).filter(OnboardingTemplateTask.template_id == existing.id).count()
        return {"created": False, "template_id": existing.id, "tasks_inserted": 0, "existing_tasks": task_count}

    if dry_run:
        return {"created": True, "template_id": None, "tasks_inserted": len(STANDARD_V1_TASKS), "existing_tasks": 0}

    template = OnboardingTemplate(key=STANDARD_V1_KEY, name=STANDARD_V1_NAME, version=STANDARD_V1_VERSION, is_active=True)
    db.add(template)
    db.flush()  # assigns template.id without committing yet

    for phase, position, title, owner, customer_visible in STANDARD_V1_TASKS:
        db.add(
            OnboardingTemplateTask(
                template_id=template.id,
                phase=phase,
                position=position,
                title=title,
                owner=owner,
                customer_visible=customer_visible,
            )
        )
    db.commit()
    return {"created": True, "template_id": template.id, "tasks_inserted": len(STANDARD_V1_TASKS), "existing_tasks": 0}


class OnboardingError(Exception):
    def __init__(self, status: int, code: str):
        super().__init__(code)
        self.status = status
        self.code = code


def create_project_from_template(
    db: Session, account_id: int, created_by_user_id: int, template_key: str = STANDARD_V1_KEY
) -> OnboardingProject:
    """Starts a new onboarding project for an account, copying the named template's tasks.

    Raises OnboardingError(409, "project_already_active") if the account already has a project in
    an open status (active or paused — see _OPEN_PROJECT_STATUSES). Raises
    OnboardingError(404, "template_not_found") for an unknown/inactive template key.
    """
    existing_open = (
        db.query(OnboardingProject)
        .filter(OnboardingProject.account_id == account_id, OnboardingProject.status.in_(_OPEN_PROJECT_STATUSES))
        .first()
    )
    if existing_open is not None:
        raise OnboardingError(409, "project_already_active")

    template = (
        db.query(OnboardingTemplate)
        .filter(OnboardingTemplate.key == template_key, OnboardingTemplate.is_active.is_(True))
        .first()
    )
    if template is None:
        raise OnboardingError(404, "template_not_found")

    template_tasks = (
        db.query(OnboardingTemplateTask)
        .filter(OnboardingTemplateTask.template_id == template.id)
        .order_by(OnboardingTemplateTask.phase, OnboardingTemplateTask.position)
        .all()
    )

    project = OnboardingProject(
        account_id=account_id,
        template_key=template.key,
        template_version=template.version,
        status="active",
        started_at=datetime.utcnow(),
        created_by_user_id=created_by_user_id,
    )
    db.add(project)
    db.flush()

    for t in template_tasks:
        db.add(
            OnboardingTask(
                project_id=project.id,
                phase=t.phase,
                position=t.position,
                title=t.title,
                owner=t.owner,
                customer_visible=t.customer_visible,
                status="todo",
            )
        )
    db.commit()
    db.refresh(project)
    return project


def apply_task_status(task: OnboardingTask, new_status: str, actor_user_id: Optional[int]) -> None:
    """Applies the timestamp side-effects of a task status change. Does not commit or audit —
    callers (the router) do that, since they also need the old status for the audit line."""
    now = datetime.utcnow()
    if new_status == "doing" and task.started_at is None:
        task.started_at = now
    if new_status in ("done", "skipped"):
        task.completed_at = now
        task.completed_by_user_id = actor_user_id
    if new_status == "todo":
        task.completed_at = None
        task.completed_by_user_id = None
    task.status = new_status


def _phase_window(tasks: List[OnboardingTask], phase: int) -> Tuple[Optional[datetime], Optional[datetime]]:
    """(started_at, completed_at) for one phase's tasks: started_at is the earliest of any task's
    started_at/completed_at in that phase ("first task touched"); completed_at is the latest
    completed_at, but ONLY if every task in the phase is done or skipped — otherwise None. An empty
    phase (no tasks) returns (None, None)."""
    phase_tasks = [t for t in tasks if t.phase == phase]
    if not phase_tasks:
        return None, None

    touches = [t.started_at for t in phase_tasks if t.started_at] + [t.completed_at for t in phase_tasks if t.completed_at]
    started = min(touches) if touches else None

    all_closed = all(t.status in ("done", "skipped") for t in phase_tasks)
    completed_values = [t.completed_at for t in phase_tasks if t.completed_at]
    completed = max(completed_values) if (all_closed and completed_values) else None

    return started, completed


def _duration_days(start: Optional[datetime], end: Optional[datetime]) -> Optional[int]:
    if start is None or end is None:
        return None
    return (end - start).days


def get_project_metrics(project: OnboardingProject, tasks: List[OnboardingTask]) -> Dict[str, object]:
    """Per-phase started_at/completed_at/duration, plus kickoff-to-golive and total — see the
    module docstring and the hand-off's Deel 3 for the exact definitions. Pure calculation, no
    database writes."""
    phases = {}
    for phase in range(1, FINAL_PHASE + 1):
        started, completed = _phase_window(tasks, phase)
        phases[str(phase)] = {
            "started_at": started.isoformat() if started else None,
            "completed_at": completed.isoformat() if completed else None,
            "duration_days": _duration_days(started, completed),
        }

    # Kickoff: from the completion of phase 3's FIRST task (position 1) ...
    kickoff_task = next((t for t in tasks if t.phase == KICKOFF_PHASE and t.position == 1), None)
    kickoff_start = kickoff_task.completed_at if kickoff_task else None
    # ... to phase 7 fully completed.
    _, golive_completed = _phase_window(tasks, GOLIVE_PHASE)
    kickoff_to_golive_days = _duration_days(kickoff_start, golive_completed)

    # Total: from the project's own started_at to phase 8 fully completed.
    _, final_completed = _phase_window(tasks, FINAL_PHASE)
    total_days = _duration_days(project.started_at, final_completed)

    return {
        "project_id": project.id,
        "phases": phases,
        "kickoff_to_golive_days": kickoff_to_golive_days,
        "total_days": total_days,
    }
