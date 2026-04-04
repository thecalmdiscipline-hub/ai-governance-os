def normalize_workflow_key_impl(key: str) -> str:
    return (key or '').strip().lower().replace('-', '_')

from typing import Any, Callable, Dict, Optional

def _stub(workflow: str) -> Callable[..., Dict[str, Any]]:
    def _fn(payload: Dict[str, Any], user_id: Optional[int] = None) -> Dict[str, Any]:
        return {
            "workflow": workflow,
            "status": "stub_ok",
            "received": payload,
            "user_id": user_id,
        }
    return _fn

from app.workflows.implementations.sales_lead_qualification import sales_lead_qualification_run
WORKFLOWS: Dict[str, Callable[..., Dict[str, Any]]] = {
    "customer_support": _stub("customer_support"),
    "document_knowledge": _stub("document_knowledge"),
    "sales_lead_qualification": _stub("sales_lead_qualification"),
    "quote_contract_generator": _stub("quote_contract_generator"),
    "meeting_agenda_assistant": _stub("meeting_agenda_assistant"),
    "marketing_automation": _stub("marketing_automation"),
    "invoice_processing": _stub("invoice_processing"),
    "compliance_monitoring": _stub("compliance_monitoring"),
    "hr_recruitment": _stub("hr_recruitment"),
    "business_intelligence": _stub("business_intelligence"),
    "sales_lead_qualification": sales_lead_qualification_run,
}

WORKFLOW_REGISTRY = WORKFLOWS

def normalize_workflow_key(key: str) -> str:
    return normalize_workflow_key_impl(key)
# IMPLEMENTATION OVERRIDES (auto)
try:
    from app.workflows.implementations import customer_support_run
    WORKFLOWS["customer_support"] = customer_support_run
    WORKFLOW_REGISTRY["customer_support"] = customer_support_run
except Exception:
    pass
try:
    from app.workflows.implementations import document_knowledge_run
    WORKFLOWS["document_knowledge"] = document_knowledge_run
    WORKFLOW_REGISTRY["document_knowledge"] = document_knowledge_run
except Exception:
    pass
