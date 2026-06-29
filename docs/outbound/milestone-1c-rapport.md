# Milestone 1c — Rapport: Governance/Booking Tabellen

**Datum:** 2026-05-27  
**Status:** ✅ Volledig geslaagd  
**Migratie revision ID:** `010738c8a744`

---

## Aangemaakte bestanden

### Models (`app/outbound/models/`)
| Bestand | Class | Beschrijving |
|---|---|---|
| `scheduled_call.py` | `OutboundScheduledCall` | Cal.com-gekoppelde gesprekken met prospect (intake_b / sales_c) |
| `region_policy.py` | `OutboundRegionPolicy` | Per-land AVG/GDPR-beleid met unique constraint op org+country |
| `suppression_list.py` | `OutboundSuppressionListEntry` | Opt-out/bounce/DNC-lijst met unique constraint op org+email |
| `__init__.py` | _(updated)_ | Exporteert alle 9 outbound models |

### Schemas (`app/outbound/schemas/`)
| Bestand | Schemas |
|---|---|
| `scheduled_call.py` | `ScheduledCallCreate`, `ScheduledCallUpdate`, `ScheduledCallRead` |
| `region_policy.py` | `RegionPolicyCreate`, `RegionPolicyUpdate`, `RegionPolicyRead` |
| `suppression_list.py` | `SuppressionListEntryCreate`, `SuppressionListEntryRead` _(geen Update — entries worden alleen toegevoegd/verwijderd)_ |
| `__init__.py` | _(updated)_ — exporteert alle 8 nieuwe schemas (+ 9 uit M1a/M1b) |

### Migratie (`alembic/versions/`)
| Bestand | Revision |
|---|---|
| `010738c8a744_outbound_m1c_governance_booking_tables.py` | `010738c8a744` (down: `9d1ec3bfd078`) |

Geen onderlinge FK-afhankelijkheid tussen de drie nieuwe tabellen — volgorde in upgrade/downgrade is vrij gekozen.

### Tests (`tests/outbound/`)
| Bestand | Tests |
|---|---|
| `test_models_governance.py` | 6 nieuwe tests |

---

## Alembic upgrade output

```
INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 9d1ec3bfd078 -> 010738c8a744, outbound_m1c_governance_booking_tables
```

---

## pytest output

### Nieuwe tests (`tests/outbound/test_models_governance.py`)

```
collected 6 items

tests/outbound/test_models_governance.py ......                          [100%]

============================== 6 passed in 0.24s ===============================
```

### Volledige outbound suite (`tests/outbound/`)

```
collected 17 items

tests/outbound/test_models_core.py .....                                 [ 29%]
tests/outbound/test_models_governance.py ......                          [ 64%]
tests/outbound/test_models_sending.py ......                             [100%]

============================== 17 passed in 0.53s ===============================
```

**M1c:** 6 passed | **Totaal:** 17 passed (M1a: 5 + M1b: 6 + M1c: 6)

---

## Enum-namen (geen conflict met M1a/M1b)

| Enum naam | Waarden |
|---|---|
| `outbound_call_type` | `intake_b`, `sales_c` |
| `outbound_meeting_platform` | `zoom`, `google_meet`, `teams`, `whereby` |
| `outbound_call_status` | `scheduled`, `completed`, `no_show`, `cancelled`, `rescheduled` |
| `outbound_suppression_reason` | `unsubscribed`, `hard_bounce`, `manual`, `spam_complaint`, `dnc_list` |

---

## UniqueConstraints

| Tabel | Constraint naam | Kolommen |
|---|---|---|
| `outbound_region_policies` | `uq_region_policy_org_country` | `organization_id`, `country_code` |
| `outbound_suppression_list` | `uq_suppression_org_email` | `organization_id`, `email` |

Beide constraints zijn getest via `test_unique_country_per_org_fails` en `test_unique_email_per_org_fails`.

---

## Design-keuzes

- `SuppressionListEntry` heeft **geen Update-schema** — suppression entries worden nooit gewijzigd, alleen toegevoegd of verwijderd (audit-trail principe).
- `OutboundRegionPolicy.allowed` default `False` (server_default `"false"`) — opt-in beleid, landen zijn geblokkeerd tenzij expliciet toegestaan.
- `calcom_event_id` geïndexeerd voor snelle webhook-lookup vanuit Cal.com callbacks.
- `added_at` in suppression list gebruikt `server_default=func.now()` zonder `updated_at` — immutable record.

---

## BANANENSCHIL

Geen bananenschillen — alle stappen voltooid zonder fouten op de eerste poging.

---

## Overzicht 9 outbound tabellen (M1a + M1b + M1c)

| Milestone | Tabel | Model |
|---|---|---|
| M1a | `outbound_companies` | `OutboundCompany` |
| M1a | `outbound_prospects` | `OutboundProspect` |
| M1a | `outbound_campaigns` | `OutboundCampaign` |
| M1b | `outbound_touchpoints` | `OutboundTouchpoint` |
| M1b | `outbound_replies` | `OutboundReply` |
| M1b | `outbound_reply_classifications` | `OutboundReplyClassification` |
| M1c | `outbound_scheduled_calls` | `OutboundScheduledCall` |
| M1c | `outbound_region_policies` | `OutboundRegionPolicy` |
| M1c | `outbound_suppression_list` | `OutboundSuppressionListEntry` |

## Volgende stap (M1d)

Milestone 1c completeert het datamodel. M1d is het finale deel:
- Service-laag / repositories voor alle 9 tabellen
- of integratietests op PostgreSQL
- of routers + API endpoints
