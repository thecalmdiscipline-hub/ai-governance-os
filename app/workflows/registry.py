def normalize_workflow_key_impl(key: str) -> str:
    return (key or '').strip().lower().replace('-', '_')

from typing import Any, Callable, Dict, Optional

from app.workflows.implementations import (
    customer_support_run,
    document_knowledge_run,
    sales_lead_qualification_run,
    quote_contract_generator,
    meeting_agenda_assistant,
    marketing_automation,
    invoice_processing,
    compliance_monitoring,
    hr_recruitment,
    business_intelligence,
)

WORKFLOWS: Dict[str, Callable[..., Dict[str, Any]]] = {
    "customer_support": customer_support_run,
    "document_knowledge": document_knowledge_run,
    "sales_lead_qualification": sales_lead_qualification_run,
    "quote_contract_generator": quote_contract_generator,
    "meeting_agenda_assistant": meeting_agenda_assistant,
    "marketing_automation": marketing_automation,
    "invoice_processing": invoice_processing,
    "compliance_monitoring": compliance_monitoring,
    "hr_recruitment": hr_recruitment,
    "business_intelligence": business_intelligence,
}

WORKFLOW_REGISTRY = WORKFLOWS


def normalize_workflow_key(key: str) -> str:
    return normalize_workflow_key_impl(key)
