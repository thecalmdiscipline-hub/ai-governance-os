"""
Default texts created for every newly provisioned tenant (Batch F). One file on purpose, so the wording can be
reviewed and adjusted without touching the provisioning logic.

Language: English, like the existing generator behind POST /ai-policy (governance.py), whose four sentences
these templates extend. Every text starts with STANDARD_NOTICE so nobody mistakes it for a finished
assessment: these are starting points that the client must review.

Risk levels are "medium" on purpose: a "high" risk is immutable except for a super-admin (see
DELETE /ai-risks), which is not what a starter template should impose.
"""
from typing import Dict

STANDARD_NOTICE = "Standard template, to be reviewed by the client."

# ---- AIPolicy (one per organization) --------------------------------------------------------------

def policy_texts(organization_name: str) -> Dict[str, str]:
    return {
        "purpose": f"{STANDARD_NOTICE} {organization_name} uses AI responsibly and only for purposes it has defined and documented.",
        "principles": f"{STANDARD_NOTICE} Transparency, human oversight, risk-based control and data minimisation.",
        "risk_commitment": f"{STANDARD_NOTICE} All AI systems undergo a documented risk assessment before use and are reviewed regularly.",
        "monitoring_commitment": f"{STANDARD_NOTICE} AI systems are monitored continuously; incidents are recorded and followed up.",
    }


# ---- AISystem (one per enabled workflow; AIRisk hangs off an AISystem) -------------------------------

SYSTEM_PURPOSE = f"{STANDARD_NOTICE} Describe here the business purpose of this AI use case."

# ---- AIRisk (one starter risk per enabled workflow), keyed by module key -----------------------------

_GENERIC_MITIGATION = (
    "Have a person review the output before it is used or sent on; record incidents; review this risk at least once a year."
)

# module_key -> (title, specific description, specific mitigation)
STARTER_RISKS: Dict[str, tuple] = {
    "document_intelligence": (
        "Answers may be inaccurate or based on the wrong document",
        "Answers to document questions can be wrong, incomplete or drawn from an outdated file.",
        "Check answers against the cited source document; keep the document set current.",
    ),
    "compliance_monitor": (
        "Compliance findings may be incomplete",
        "Automated compliance overviews can miss obligations or misjudge a control.",
        "Treat the output as decision support; a responsible person confirms every finding.",
    ),
    "customer_support_ai": (
        "Support triage or suggested replies may be wrong",
        "A ticket can be classified with the wrong priority or receive an unsuitable suggested reply.",
        "A support agent reviews suggested replies before they reach a customer.",
    ),
    "sales_qualification_ai": (
        "Lead scores may be biased or inaccurate",
        "Qualification scores can reflect bias in the input data or misjudge a lead.",
        "Review scores regularly against real outcomes; do not use them as the only basis for a decision.",
    ),
    "invoice_processing_ai": (
        "Extracted invoice data may be wrong",
        "Amounts, dates or supplier details can be extracted incorrectly.",
        "Verify extracted values against the source invoice before booking or paying.",
    ),
    "hr_recruitment_ai": (
        "Candidate screening may be unfair or biased",
        "Candidate summaries and recommendations can be biased and affect people.",
        "A recruiter decides; the output is only a first screening step. Review outcomes for bias.",
    ),
    "marketing_automation_ai": (
        "Generated marketing content may be inaccurate or off-brand",
        "Campaign text can contain wrong claims or an inappropriate tone.",
        "Review and approve content before publication.",
    ),
    "meeting_agenda_assistant": (
        "Agendas or summaries may omit or misstate points",
        "Generated agendas can leave out topics or misrepresent earlier discussions.",
        "The meeting owner reviews the agenda before it is shared.",
    ),
    "quote_contract_generator": (
        "Generated quotes or contract drafts may contain errors",
        "Draft terms, prices or clauses can be wrong or legally unsuitable.",
        "A responsible person (and, for contracts, legal review) approves every draft before it is sent.",
    ),
    "business_intelligence": (
        "Insights may be based on incomplete or misread data",
        "Generated insights can misinterpret the data or the question.",
        "Cross-check key figures against the underlying data before acting on them.",
    ),
}


def starter_risk(module_key: str) -> Dict[str, str]:
    title, description, mitigation = STARTER_RISKS[module_key]
    return {
        "title": title,
        "description": f"{STANDARD_NOTICE} {description}",
        "risk_level": "medium",
        "mitigation": f"{STANDARD_NOTICE} {mitigation} {_GENERIC_MITIGATION}",
    }


# ---- Demo document (optional; fictitious, contains no personal data) ----------------------------------

DEMO_DOCUMENT_FILENAME = "welcome-sample-document.txt"
DEMO_DOCUMENT_TEXT = (
    "Sample document (fictitious)\n\n"
    "This file was added automatically when your Valqeron environment was set up, so you can try the document "
    "features straight away. It contains no real business or personal information and can be deleted at any time.\n\n"
    "Example content: our office is open on weekdays from 9:00 to 17:00. Invoices are paid within 30 days. "
    "Support requests are answered within one working day.\n"
)

# ---- Demo run (optional, costs OpenAI money) -----------------------------------------------------------

# workflow_key -> input; the first workflow in this order that the tenant has enabled is run.
DEMO_RUN_ORDER = ("customer_support", "business_intelligence")
DEMO_RUN_INPUTS = {
    "customer_support": {"issue": "Sample request: how do I change the delivery address of an order?"},
    "business_intelligence": {"question": "Sample question: which three KPIs should a small services company track monthly?"},
}
