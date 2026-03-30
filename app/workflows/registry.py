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
}

WORKFLOW_REGISTRY = WORKFLOWS