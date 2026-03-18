from app.workflows.routers.customer_support import router as customer_support
from app.workflows.routers.document_knowledge import router as document_knowledge
from app.workflows.routers.sales_lead_qualification import router as sales_lead_qualification
from app.workflows.routers.quote_contract_generator import router as quote_contract_generator
from app.workflows.routers.meeting_agenda_assistant import router as meeting_agenda_assistant
from app.workflows.routers.marketing_automation import router as marketing_automation
from app.workflows.routers.invoice_processing import router as invoice_processing
from app.workflows.routers.compliance_monitoring import router as compliance_monitoring
from app.workflows.routers.hr_recruitment import router as hr_recruitment
from app.workflows.routers.business_intelligence import router as business_intelligence

ALL_WORKFLOW_ROUTERS = [
    customer_support,
    document_knowledge,
    sales_lead_qualification,
    quote_contract_generator,
    meeting_agenda_assistant,
    marketing_automation,
    invoice_processing,
    compliance_monitoring,
    hr_recruitment,
    business_intelligence,
]
