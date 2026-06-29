"""
Milestone 1c — Governance / Booking model tests

Dekt:
- test_create_scheduled_call
- test_scheduled_call_without_prospect_fails
- test_create_region_policy
- test_unique_country_per_org_fails
- test_create_suppression_entry
- test_unique_email_per_org_fails
"""
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.outbound.models.company import OutboundCompany
from app.outbound.models.prospect import OutboundProspect
from app.outbound.models.region_policy import OutboundRegionPolicy
from app.outbound.models.scheduled_call import OutboundScheduledCall
from app.outbound.models.suppression_list import OutboundSuppressionListEntry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FUTURE = datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc)


def _make_prospect(session, org_id: int) -> OutboundProspect:
    company = OutboundCompany(organization_id=org_id, name="Acme M1c BV")
    session.add(company)
    session.commit()
    session.refresh(company)

    prospect = OutboundProspect(
        organization_id=org_id,
        company_id=company.id,
        first_name="Karin",
        last_name="de Vries",
        email="karin@acme-m1c.nl",
        person_rank=1,
    )
    session.add(prospect)
    session.commit()
    session.refresh(prospect)
    return prospect


# ---------------------------------------------------------------------------
# Tests — OutboundScheduledCall
# ---------------------------------------------------------------------------


def test_create_scheduled_call(session, test_org):
    """Scheduled call met geldige prospect en call_type intake_b wordt correct opgeslagen."""
    prospect = _make_prospect(session, test_org.id)

    call = OutboundScheduledCall(
        organization_id=test_org.id,
        prospect_id=prospect.id,
        call_type="intake_b",
        scheduled_at=_FUTURE,
        duration_minutes=30,
        meeting_platform="zoom",
        meeting_link="https://zoom.us/j/123456789",
        calcom_event_id="calcom-evt-001",
    )
    session.add(call)
    session.commit()
    session.refresh(call)

    assert call.id is not None
    assert len(call.id) == 36
    assert call.prospect_id == prospect.id
    assert call.call_type == "intake_b"
    assert call.duration_minutes == 30
    assert call.meeting_platform == "zoom"
    assert call.calcom_event_id == "calcom-evt-001"
    assert call.status == "scheduled"
    assert call.notes is None
    assert call.created_at is not None
    assert call.updated_at is not None


def test_scheduled_call_without_prospect_fails(session, test_org):
    """Scheduled call zonder prospect_id (NOT NULL) geeft IntegrityError."""
    call = OutboundScheduledCall(
        organization_id=test_org.id,
        prospect_id=None,  # verplicht — moet falen
        call_type="sales_c",
        scheduled_at=_FUTURE,
        duration_minutes=45,
        meeting_platform="google_meet",
        meeting_link="https://meet.google.com/abc-def-ghi",
    )
    session.add(call)
    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()


# ---------------------------------------------------------------------------
# Tests — OutboundRegionPolicy
# ---------------------------------------------------------------------------


def test_create_region_policy(session, test_org):
    """Region policy voor NL met allowed=True en legal_basis_text wordt opgeslagen."""
    policy = OutboundRegionPolicy(
        organization_id=test_org.id,
        country_code="NL",
        region_name="Nederland",
        allowed=True,
        legal_basis_text="Verwerking op basis van gerechtvaardigd belang (AVG art. 6.1.f). "
                         "Opt-out altijd mogelijk via unsubscribe-link.",
    )
    session.add(policy)
    session.commit()
    session.refresh(policy)

    assert policy.id is not None
    assert len(policy.id) == 36
    assert policy.country_code == "NL"
    assert policy.region_name == "Nederland"
    assert policy.allowed is True
    assert "AVG" in policy.legal_basis_text
    assert policy.footer_template_id is None
    assert policy.created_at is not None


def test_unique_country_per_org_fails(session, test_org):
    """Twee region-policies met zelfde org+country geeft IntegrityError."""
    policy1 = OutboundRegionPolicy(
        organization_id=test_org.id,
        country_code="NL",
        region_name="Nederland eerste",
        allowed=True,
        legal_basis_text="Basis 1",
    )
    session.add(policy1)
    session.commit()

    policy2 = OutboundRegionPolicy(
        organization_id=test_org.id,
        country_code="NL",  # duplicaat — moet falen
        region_name="Nederland tweede",
        allowed=False,
        legal_basis_text="Basis 2",
    )
    session.add(policy2)
    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()


# ---------------------------------------------------------------------------
# Tests — OutboundSuppressionListEntry
# ---------------------------------------------------------------------------


def test_create_suppression_entry(session, test_org):
    """Suppression-entry met reason=unsubscribed wordt correct opgeslagen."""
    entry = OutboundSuppressionListEntry(
        organization_id=test_org.id,
        email="afmelden@example.nl",
        reason="unsubscribed",
        source="footer-link",
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)

    assert entry.id is not None
    assert len(entry.id) == 36
    assert entry.email == "afmelden@example.nl"
    assert entry.reason == "unsubscribed"
    assert entry.source == "footer-link"
    assert entry.added_at is not None


def test_unique_email_per_org_fails(session, test_org):
    """Duplicaat org+email in suppression_list geeft IntegrityError."""
    entry1 = OutboundSuppressionListEntry(
        organization_id=test_org.id,
        email="dup@example.nl",
        reason="hard_bounce",
    )
    session.add(entry1)
    session.commit()

    entry2 = OutboundSuppressionListEntry(
        organization_id=test_org.id,
        email="dup@example.nl",  # duplicaat — moet falen
        reason="manual",
    )
    session.add(entry2)
    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()
