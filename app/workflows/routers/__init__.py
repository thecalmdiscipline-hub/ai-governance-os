from fastapi import APIRouter

router = APIRouter(prefix="/workflows", tags=["workflows"])

def _safe_include(module_path: str):
    try:
        mod = __import__(module_path, fromlist=["router"])
        r = getattr(mod, "router", None)
        if r is not None:
            router.include_router(r)
    except Exception:
        pass

_safe_include("app.workflows.routers.customer_support")
_safe_include("app.workflows.routers.document_knowledge")
_safe_include("app.workflows.routers.sales_lead_qualification")
_safe_include("app.workflows.routers.quote_contract_generator")
_safe_include("app.workflows.routers.meeting_agenda_assistant")
_safe_include("app.workflows.routers.marketing_automation")
_safe_include("app.workflows.routers.invoice_processing")
_safe_include("app.workflows.routers.compliance_monitoring")
_safe_include("app.workflows.routers.hr_recruitment")
_safe_include("app.workflows.routers.business_intelligence")
