from fastapi import APIRouter

from .customer_support import router as customer_support_router
from .document_knowledge import router as document_knowledge_router
from .sales_lead_qualification import router as sales_lead_qualification_router
from .quote_contract_generator import router as quote_contract_generator_router
from .meeting_agenda_assistant import router as meeting_agenda_assistant_router
from .marketing_automation import router as marketing_automation_router
from .invoice_processing import router as invoice_processing_router
from .compliance_monitoring import router as compliance_monitoring_router
from .hr_recruitment import router as hr_recruitment_router
from .business_intelligence import router as business_intelligence_router

router = APIRouter(prefix="/workflows", tags=["workflows"])

router.include_router(business_intelligence_router)
router.include_router(compliance_monitoring_router)
router.include_router(customer_support_router)
router.include_router(document_knowledge_router)
router.include_router(hr_recruitment_router)
router.include_router(invoice_processing_router)
router.include_router(marketing_automation_router)
router.include_router(meeting_agenda_assistant_router)
router.include_router(quote_contract_generator_router)
router.include_router(sales_lead_qualification_router)
