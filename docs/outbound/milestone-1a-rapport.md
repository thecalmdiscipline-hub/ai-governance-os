# Milestone 1a — Core Models Rapport
*Datum: 2026-05-25 | Auteur: Senior Backend Developer (Claude)*

---

## Status: ✅ VOLTOOID

Alle 5 tests slagen. Migratie toegepast op `test.db` (SQLite via `.env DATABASE_URL`).

---

## Aangemaakte bestanden

### Directories & `__init__.py`
| Bestand | Omschrijving |
|---|---|
| `app/outbound/__init__.py` | Module-root voor de Outbound Engine |
| `app/outbound/models/__init__.py` | Exporteert `OutboundCompany`, `OutboundProspect`, `OutboundCampaign` |
| `app/outbound/schemas/__init__.py` | Exporteert alle Create/Update/Read schema's |
| `tests/outbound/__init__.py` | Test package marker |

### SQLAlchemy Models
| Bestand | Model | Tabel |
|---|---|---|
| `app/outbound/models/company.py` | `OutboundCompany` | `outbound_companies` |
| `app/outbound/models/prospect.py` | `OutboundProspect` | `outbound_prospects` |
| `app/outbound/models/campaign.py` | `OutboundCampaign` | `outbound_campaigns` |

### Pydantic v2 Schemas
| Bestand | Schemas |
|---|---|
| `app/outbound/schemas/company.py` | `OutboundCompanyCreate`, `OutboundCompanyUpdate`, `OutboundCompanyRead` |
| `app/outbound/schemas/prospect.py` | `OutboundProspectCreate`, `OutboundProspectUpdate`, `OutboundProspectRead` |
| `app/outbound/schemas/campaign.py` | `OutboundCampaignCreate`, `OutboundCampaignUpdate`, `OutboundCampaignRead` |

### Alembic Migraties
| Bestand | Beschrijving |
|---|---|
| `alembic/versions/557050adf97b_merge_heads_pre_outbound.py` | Merge van bestaande dubbele heads (`06a3ddd7e042` + `b7e4d92f1a38`) |
| `alembic/versions/29172df93ce9_outbound_m1a_core_entities.py` | Handmatige migratie: aanmaken 3 tabellen + indexes |

### Tests
| Bestand | Omschrijving |
|---|---|
| `tests/outbound/conftest.py` | Fixtures: `db_engine` (in-memory SQLite + FK pragma), `session`, `test_org` |
| `tests/outbound/test_models_core.py` | 5 test cases voor de drie core modellen |

### Gewijzigde bestanden
| Bestand | Wijziging |
|---|---|
| `app/models/__init__.py` | Outbound models geïmporteerd zodat Alembic ze via `from app.models import *` ziet |
| `.env` | `AUDIT_SECRET_KEY` toegevoegd (was vereist door root `conftest.py` → `app.main`) |

---

## Alembic upgrade output

```
INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
INFO  [alembic.runtime.migration] Running upgrade f3a21c8b9d05 -> 06a3ddd7e042, add performance indexes
INFO  [alembic.runtime.migration] Running upgrade 06a3ddd7e042, b7e4d92f1a38 -> 557050adf97b, merge_heads_pre_outbound
INFO  [alembic.runtime.migration] Running upgrade 557050adf97b -> 29172df93ce9, outbound_m1a_core_entities
```

---

## pytest output samenvatting

```
collected 5 items

tests/outbound/test_models_core.py .....                                 [100%]

============================== 5 passed in 0.20s ===============================
```

**5 passed, 0 failed, 0 errors.**

---

## Ontwerpbeslissingen

| Beslissing | Motivatie |
|---|---|
| `String(36)` voor UUID primary keys | Bestaande codebase gebruikt Integer PKs maar taak specificeert UUID. `String(36)` werkt op SQLite én PostgreSQL zonder extra extensions. |
| `func.now()` als `server_default` | Consistente timestamp-generatie op databaseniveau voor `created_at`/`updated_at`. |
| `PRAGMA foreign_keys=ON` in test fixture | SQLite enforces FK constraints niet standaard. Event listener op engine-connect inschakelt dit zodat `test_create_prospect_without_company_fails` de juiste `IntegrityError` gooit. |
| Merge-revisie vóór outbound-revisie | Codebase had twee divergente heads (`06a3ddd7e042` en `b7e4d92f1a38`). Merge als aparte stap houdt de outbound-migratie clean. |
| Named Enum types met dialect-check in downgrade | `sa.Enum(name=...)` maakt native types op PostgreSQL. Downgrade checkt dialect zodat SQLite-runs niet proberen een type te droppen. |

---

## BANANENSCHIL-locaties

*Geen.* Alle stappen zijn succesvol afgerond zonder blokkades.

---

## Scope (strikte afbakening Milestone 1a)

- ✅ 3 tabellen + schemas + migratie + tests
- ❌ Geen routers aangemaakt
- ❌ Geen `app/main.py` wijzigingen
- ❌ Geen andere tabellen (email_sequences, activities, etc. — voor latere milestones)
