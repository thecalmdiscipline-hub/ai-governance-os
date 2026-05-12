from typing import Dict, List, Set

from sqlalchemy.orm import Session

from app.models.tenant_module import TenantModule
from app.models.user import User

BASE_MODULES = [
    {
        "name": "Valqeron Core",
        "key": "core",
        "type": "core",
        "description": "The central control layer for governance, monitoring, audit visibility and AI oversight.",
    },
    {
        "name": "Document Intelligence",
        "key": "document_intelligence",
        "type": "workflow",
        "workflow_key": "document_knowledge",
        "description": "Document upload, review, preview and document-based insights.",
    },
    {
        "name": "Compliance Monitor",
        "key": "compliance_monitor",
        "type": "workflow",
        "workflow_key": "compliance_monitoring",
        "description": "Compliance visibility, policy oversight and control tracking.",
    },
    {
        "name": "Customer Support AI",
        "key": "customer_support_ai",
        "type": "workflow",
        "workflow_key": "customer_support",
        "description": "Support workflow automation and service response handling.",
    },
    {
        "name": "Sales Qualification AI",
        "key": "sales_qualification_ai",
        "type": "workflow",
        "workflow_key": "sales_lead_qualification",
        "description": "Lead intake, qualification and prioritization support.",
    },
    {
        "name": "Invoice Processing AI",
        "key": "invoice_processing_ai",
        "type": "workflow",
        "workflow_key": "invoice_processing",
        "description": "Invoice handling, extraction and structured processing.",
    },
    {
        "name": "HR Recruitment AI",
        "key": "hr_recruitment_ai",
        "type": "workflow",
        "workflow_key": "hr_recruitment",
        "description": "Recruitment workflow support and candidate processing.",
    },
    {
        "name": "Marketing Automation AI",
        "key": "marketing_automation_ai",
        "type": "workflow",
        "workflow_key": "marketing_automation",
        "description": "Marketing workflow support and campaign automation assistance.",
    },
    {
        "name": "Meeting Agenda Assistant",
        "key": "meeting_agenda_assistant",
        "type": "workflow",
        "workflow_key": "meeting_agenda_assistant",
        "description": "Meeting preparation and agenda structuring assistance.",
    },
    {
        "name": "Quote & Contract Generator",
        "key": "quote_contract_generator",
        "type": "workflow",
        "workflow_key": "quote_contract_generator",
        "description": "Quote and contract draft generation support.",
    },
    {
        "name": "Business Intelligence",
        "key": "business_intelligence",
        "type": "workflow",
        "workflow_key": "business_intelligence",
        "description": "Structured business insight and decision-support workflows.",
    },
]

_WORKFLOW_KEY_TO_MODULE_KEY: Dict[str, str] = {
    m["workflow_key"]: m["key"]
    for m in BASE_MODULES
    if m.get("workflow_key")
}


def _get_active_module_keys(db: Session, organization_id: int) -> Set[str]:
    rows = (
        db.query(TenantModule)
        .filter(
            TenantModule.organization_id == organization_id,
            TenantModule.is_active == True,
        )
        .all()
    )
    return {row.module_key for row in rows}


def get_modules_for_user(user: User, db: Session) -> List[Dict]:
    active_keys = _get_active_module_keys(db, user.organization_id or 0)

    return [
        {
            "name": m["name"],
            "key": m["key"],
            "type": m["type"],
            "description": m["description"],
            "workflow_key": m.get("workflow_key"),
            "active": m["key"] in active_keys,
        }
        for m in BASE_MODULES
    ]


def has_module_access(user: User, module_key: str, db: Session) -> bool:
    active_keys = _get_active_module_keys(db, user.organization_id or 0)
    return module_key in active_keys


def has_workflow_access(user: User, workflow_key: str, db: Session) -> bool:
    module_key = _WORKFLOW_KEY_TO_MODULE_KEY.get(workflow_key)
    if not module_key:
        return False
    return has_module_access(user, module_key, db)
