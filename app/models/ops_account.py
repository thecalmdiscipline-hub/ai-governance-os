from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint

from app.db.base import Base


class OpsAccount(Base):
    """A customer/prospect tracked by Valqeron HQ staff (Batch I, Fase 2.1). Global table — not
    tenant-scoped, only ever reachable via /ops/*. Customers never read this table (see
    app/api/ops_accounts.py); it has nothing to do with the public, unauthenticated
    app.models.contact_submission.ContactSubmission (the marketing "Contact us" form)."""

    __tablename__ = "ops_accounts"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    country = Column(String(2), nullable=True)
    sector = Column(String(120), nullable=True)

    # lead | qualified | proposal | contract | onboarding | live | lost | churned
    status = Column(String, nullable=False, default="lead")
    source = Column(String, nullable=True)  # inbound | outbound | referral | manual
    proposed_tier = Column(String, nullable=True)  # starter | business | enterprise

    primary_contact_name = Column(String(120), nullable=True)
    primary_contact_email = Column(String(254), nullable=True)

    # Set once, via POST /ops/accounts/{id}/link-organization — the account's real, provisioned tenant.
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)

    # Only populated if this account originated from an Outbound Engine company row (optional link,
    # Fase 1-4 datamodel only — no outbound sending exists yet). OutboundCompany.id is a UUID string.
    outbound_company_id = Column(String(36), ForeignKey("outbound_companies.id"), nullable=True)

    notes = Column(String(1000), nullable=True)  # free text the operator wrote; never in logs/audit/Sentry

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_ops_accounts_organization_id"),
    )
