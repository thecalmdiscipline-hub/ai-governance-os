"""
Milestone 1a — Core model tests

Dekt:
- test_create_company
- test_create_prospect_with_company
- test_create_prospect_without_company_fails
- test_create_campaign
- test_company_prospects_relationship
"""
import pytest
from sqlalchemy.exc import IntegrityError

from app.outbound.models.company import OutboundCompany
from app.outbound.models.prospect import OutboundProspect
from app.outbound.models.campaign import OutboundCampaign


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_company(org_id: int, name: str = "Acme BV") -> OutboundCompany:
    return OutboundCompany(
        organization_id=org_id,
        name=name,
    )


def _make_prospect(org_id: int, company_id: str, email: str = "jan@acme.nl") -> OutboundProspect:
    return OutboundProspect(
        organization_id=org_id,
        company_id=company_id,
        first_name="Jan",
        last_name="Jansen",
        email=email,
        person_rank=1,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_create_company(session, test_org):
    """Minimale velden zijn voldoende om een company op te slaan."""
    company = _make_company(test_org.id)
    session.add(company)
    session.commit()
    session.refresh(company)

    assert company.id is not None
    assert len(company.id) == 36  # UUID-formaat "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    assert company.name == "Acme BV"
    assert company.organization_id == test_org.id
    assert company.status == "pending"
    assert company.created_at is not None
    assert company.updated_at is not None


def test_create_prospect_with_company(session, test_org):
    """Prospect aanmaken met een geldige company FK werkt."""
    company = _make_company(test_org.id, name="Beta Corp")
    session.add(company)
    session.commit()
    session.refresh(company)

    prospect = _make_prospect(test_org.id, company.id, email="contact@beta.nl")
    session.add(prospect)
    session.commit()
    session.refresh(prospect)

    assert prospect.id is not None
    assert len(prospect.id) == 36
    assert prospect.company_id == company.id
    assert prospect.first_name == "Jan"
    assert prospect.sequence_state == "pending"
    assert prospect.person_rank == 1


def test_create_prospect_without_company_fails(session, test_org):
    """Prospect zonder company_id mag niet opgeslagen worden (NOT NULL constraint)."""
    prospect = OutboundProspect(
        organization_id=test_org.id,
        company_id=None,  # verplicht veld — moet falen
        first_name="Jane",
        last_name="Doe",
        email="jane@test.nl",
        person_rank=1,
    )
    session.add(prospect)
    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()


def test_create_campaign(session, test_org):
    """Minimale velden zijn voldoende om een campaign op te slaan."""
    campaign = OutboundCampaign(
        organization_id=test_org.id,
        name="Q3 Cold Outreach",
    )
    session.add(campaign)
    session.commit()
    session.refresh(campaign)

    assert campaign.id is not None
    assert len(campaign.id) == 36
    assert campaign.name == "Q3 Cold Outreach"
    assert campaign.organization_id == test_org.id
    assert campaign.status == "draft"
    assert campaign.campaign_type == "cold"
    assert campaign.created_at is not None


def test_company_prospects_relationship(session, test_org):
    """company.prospects geeft een lijst van bijbehorende OutboundProspect objecten."""
    company = _make_company(test_org.id, name="Gamma BV")
    session.add(company)
    session.commit()
    session.refresh(company)

    p1 = _make_prospect(test_org.id, company.id, email="p1@gamma.nl")
    p2 = _make_prospect(test_org.id, company.id, email="p2@gamma.nl")
    session.add_all([p1, p2])
    session.commit()

    # Ververs company vanuit DB zodat de relationship geladen wordt
    session.expire(company)
    session.refresh(company)

    assert isinstance(company.prospects, list)
    assert len(company.prospects) == 2
    emails = {p.email for p in company.prospects}
    assert "p1@gamma.nl" in emails
    assert "p2@gamma.nl" in emails
