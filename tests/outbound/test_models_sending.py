"""
Milestone 1b — Sending / Reply model tests

Dekt:
- test_create_touchpoint
- test_touchpoint_without_prospect_fails
- test_create_reply_with_touchpoint
- test_create_reply_without_touchpoint
- test_create_reply_classification
- test_reply_classifications_relationship
"""
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.outbound.models.campaign import OutboundCampaign
from app.outbound.models.company import OutboundCompany
from app.outbound.models.prospect import OutboundProspect
from app.outbound.models.reply import OutboundReply
from app.outbound.models.reply_classification import OutboundReplyClassification
from app.outbound.models.touchpoint import OutboundTouchpoint


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 5, 27, 9, 0, 0, tzinfo=timezone.utc)
_FUTURE = datetime(2026, 5, 28, 8, 0, 0, tzinfo=timezone.utc)


def _make_company(session, org_id: int) -> OutboundCompany:
    company = OutboundCompany(organization_id=org_id, name="Acme M1b BV")
    session.add(company)
    session.commit()
    session.refresh(company)
    return company


def _make_prospect(session, org_id: int, company_id: str) -> OutboundProspect:
    prospect = OutboundProspect(
        organization_id=org_id,
        company_id=company_id,
        first_name="Jan",
        last_name="Jansen",
        email="jan@acme-m1b.nl",
        person_rank=1,
    )
    session.add(prospect)
    session.commit()
    session.refresh(prospect)
    return prospect


def _make_campaign(session, org_id: int) -> OutboundCampaign:
    campaign = OutboundCampaign(organization_id=org_id, name="M1b Test Campaign")
    session.add(campaign)
    session.commit()
    session.refresh(campaign)
    return campaign


def _make_touchpoint(session, org_id: int, campaign_id: str, prospect_id: str) -> OutboundTouchpoint:
    tp = OutboundTouchpoint(
        organization_id=org_id,
        campaign_id=campaign_id,
        prospect_id=prospect_id,
        sequence_step=1,
        channel="email",
        subject="Hallo Jan, samenwerking?",
        body_text="Beste Jan, ...",
        scheduled_at=_FUTURE,
    )
    session.add(tp)
    session.commit()
    session.refresh(tp)
    return tp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_create_touchpoint(session, test_org):
    """Touchpoint met geldige campaign + prospect wordt correct opgeslagen."""
    company = _make_company(session, test_org.id)
    prospect = _make_prospect(session, test_org.id, company.id)
    campaign = _make_campaign(session, test_org.id)

    tp = OutboundTouchpoint(
        organization_id=test_org.id,
        campaign_id=campaign.id,
        prospect_id=prospect.id,
        sequence_step=1,
        channel="email",
        subject="Q3 outreach stap 1",
        body_text="Hallo, ik neem contact op...",
        scheduled_at=_FUTURE,
    )
    session.add(tp)
    session.commit()
    session.refresh(tp)

    assert tp.id is not None
    assert len(tp.id) == 36
    assert tp.campaign_id == campaign.id
    assert tp.prospect_id == prospect.id
    assert tp.sequence_step == 1
    assert tp.channel == "email"
    assert tp.status == "scheduled"
    assert tp.sent_at is None
    assert tp.created_at is not None


def test_touchpoint_without_prospect_fails(session, test_org):
    """Touchpoint zonder prospect_id (NOT NULL) geeft IntegrityError."""
    campaign = _make_campaign(session, test_org.id)

    tp = OutboundTouchpoint(
        organization_id=test_org.id,
        campaign_id=campaign.id,
        prospect_id=None,  # verplicht veld — moet falen
        sequence_step=1,
        channel="email",
        subject="Test",
        body_text="Test body",
        scheduled_at=_FUTURE,
    )
    session.add(tp)
    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()


def test_create_reply_with_touchpoint(session, test_org):
    """Reply gekoppeld aan een bestaand touchpoint wordt correct opgeslagen."""
    company = _make_company(session, test_org.id)
    prospect = _make_prospect(session, test_org.id, company.id)
    campaign = _make_campaign(session, test_org.id)
    tp = _make_touchpoint(session, test_org.id, campaign.id, prospect.id)

    reply = OutboundReply(
        organization_id=test_org.id,
        touchpoint_id=tp.id,
        prospect_id=prospect.id,
        from_email="jan@acme-m1b.nl",
        subject="Re: Q3 outreach",
        body_text="Dank voor uw bericht...",
        received_at=_NOW,
    )
    session.add(reply)
    session.commit()
    session.refresh(reply)

    assert reply.id is not None
    assert len(reply.id) == 36
    assert reply.touchpoint_id == tp.id
    assert reply.prospect_id == prospect.id
    assert reply.from_email == "jan@acme-m1b.nl"
    assert reply.created_at is not None


def test_create_reply_without_touchpoint(session, test_org):
    """Reply zonder touchpoint_id (nullable FK) mag wél worden opgeslagen."""
    reply = OutboundReply(
        organization_id=test_org.id,
        touchpoint_id=None,  # nullable — OK
        prospect_id=None,    # nullable — OK
        from_email="onbekend@extern.nl",
        body_text="Graag afmelden van jullie lijst.",
        received_at=_NOW,
    )
    session.add(reply)
    session.commit()
    session.refresh(reply)

    assert reply.id is not None
    assert reply.touchpoint_id is None
    assert reply.prospect_id is None
    assert reply.from_email == "onbekend@extern.nl"


def test_create_reply_classification(session, test_org):
    """ReplyClassification met confidence 0.92 wordt correct opgeslagen."""
    reply = OutboundReply(
        organization_id=test_org.id,
        from_email="jan@acme-m1b.nl",
        body_text="Ja, stuur maar meer info.",
        received_at=_NOW,
    )
    session.add(reply)
    session.commit()
    session.refresh(reply)

    clf = OutboundReplyClassification(
        organization_id=test_org.id,
        reply_id=reply.id,
        label="B_interested",
        confidence=0.92,
        reasoning="Prospect vraagt om meer informatie, duidelijk koopsignaal.",
        classified_by="llm",
        model="claude-sonnet-4-6",
        tokens_used=312,
    )
    session.add(clf)
    session.commit()
    session.refresh(clf)

    assert clf.id is not None
    assert len(clf.id) == 36
    assert clf.reply_id == reply.id
    assert clf.label == "B_interested"
    assert abs(clf.confidence - 0.92) < 1e-6
    assert clf.classified_by == "llm"
    assert clf.model == "claude-sonnet-4-6"
    assert clf.tokens_used == 312
    assert clf.reviewed_by_user_id is None
    assert clf.created_at is not None


def test_reply_classifications_relationship(session, test_org):
    """reply.classifications geeft een lijst van bijbehorende classificaties."""
    reply = OutboundReply(
        organization_id=test_org.id,
        from_email="jan@acme-m1b.nl",
        body_text="Ik ga ermee akkoord.",
        received_at=_NOW,
    )
    session.add(reply)
    session.commit()
    session.refresh(reply)

    clf1 = OutboundReplyClassification(
        organization_id=test_org.id,
        reply_id=reply.id,
        label="C_ready",
        confidence=0.97,
        reasoning="Prospect bevestigt expliciet akkoord.",
        classified_by="llm",
    )
    clf2 = OutboundReplyClassification(
        organization_id=test_org.id,
        reply_id=reply.id,
        label="B_interested",
        confidence=0.85,
        reasoning="Alternatieve interpretatie: geïnteresseerd.",
        classified_by="human",
    )
    session.add_all([clf1, clf2])
    session.commit()

    session.expire(reply)
    session.refresh(reply)

    assert isinstance(reply.classifications, list)
    assert len(reply.classifications) == 2
    labels = {c.label for c in reply.classifications}
    assert "C_ready" in labels
    assert "B_interested" in labels
