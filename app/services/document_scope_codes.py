"""The single source of truth for scope codes (docs/scope-codes.md §3 and §4).

Nothing else in the codebase may hardcode a scope code: import from here.
New codes are added only here (and through review), never via an upload (scope-codes.md §4).
"""
from typing import Dict, FrozenSet

# The code every workflow may read (V3, B3b: a separate code, never implicit).
SHARED_CODE = "gedeeld"

# Exclusive code (V18, B3a): never combined with another code, read only by its own workflow.
EXCLUSIVE_CODES: FrozenSet[str] = frozenset({"hr"})

# Workflow key (registry) -> the workflow's own scope code (scope-codes.md §3).
WORKFLOW_SCOPE_CODES: Dict[str, str] = {
    "document_knowledge": "kennis",
    "customer_support": "support",
    "sales_lead_qualification": "sales",
    "quote_contract_generator": "contract",
    "meeting_agenda_assistant": "meeting",
    "marketing_automation": "marketing",
    "invoice_processing": "factuur",
    "compliance_monitoring": "compliance",
    "hr_recruitment": "hr",
    "business_intelligence": "bi",
}

# Document codes with their meaning (scope-codes.md §4).
DOCUMENT_SCOPE_CODES: Dict[str, str] = {
    SHARED_CODE: "Bedrijfsbreed: beleid, handboek, algemene voorwaarden",
    "kennis": "Algemene kennisdocumenten",
    "support": "Klantenservice-kennis, FAQ, productdocs",
    "sales": "Prijslijsten, productfiches, ICP",
    "contract": "Sjablonen voor offertes en contracten",
    "meeting": "Agenda's, notulen, vergaderstukken",
    "marketing": "Campagnemateriaal, merkrichtlijnen",
    "factuur": "Facturen en inkoopdocumenten",
    "compliance": "Beleid, procedures, audit-bewijs",
    "hr": "Personeels- en wervingsdocumenten",
    "bi": "Rapportages en KPI's",
}

ALLOWED_CODES: FrozenSet[str] = frozenset(DOCUMENT_SCOPE_CODES)
