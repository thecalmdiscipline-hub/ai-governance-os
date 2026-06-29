# Milestone 1b — Rapport: Sending/Reply Tabellen

**Datum:** 2026-05-27  
**Status:** ✅ Volledig geslaagd  
**Migratie revision ID:** `9d1ec3bfd078`

---

## Aangemaakte bestanden

### Models (`app/outbound/models/`)
| Bestand | Class | Beschrijving |
|---|---|---|
| `touchpoint.py` | `OutboundTouchpoint` | Scheduled/sent email touchpoints per prospect per campaign |
| `reply.py` | `OutboundReply` | Inbound replies ontvangen via ESP, koppeling aan touchpoint optioneel |
| `reply_classification.py` | `OutboundReplyClassification` | AI- of human-classificatie van een reply (label + confidence + reasoning) |
| `__init__.py` | _(updated)_ | Exporteert alle 6 outbound models |

### Schemas (`app/outbound/schemas/`)
| Bestand | Schemas |
|---|---|
| `touchpoint.py` | `TouchpointCreate`, `TouchpointUpdate`, `TouchpointRead` |
| `reply.py` | `ReplyCreate`, `ReplyUpdate`, `ReplyRead` |
| `reply_classification.py` | `ReplyClassificationCreate`, `ReplyClassificationUpdate`, `ReplyClassificationRead` |
| `__init__.py` | _(updated)_ — exporteert alle 9 nieuwe schemas |

### Migratie (`alembic/versions/`)
| Bestand | Revision |
|---|---|
| `9d1ec3bfd078_outbound_m1b_sending_reply_tables.py` | `9d1ec3bfd078` (down: `29172df93ce9`) |

FK-volgorde upgrade: `outbound_touchpoints` → `outbound_replies` → `outbound_reply_classifications`  
FK-volgorde downgrade: omgekeerd.

### Tests (`tests/outbound/`)
| Bestand | Tests |
|---|---|
| `test_models_sending.py` | 6 nieuwe tests |

---

## Alembic upgrade output

```
INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 29172df93ce9 -> 9d1ec3bfd078, outbound_m1b_sending_reply_tables
```

---

## pytest output

### Nieuwe tests (`tests/outbound/test_models_sending.py`)

```
collected 6 items

tests/outbound/test_models_sending.py ......                             [100%]

============================== 6 passed in 0.30s ===============================
```

### Volledige outbound suite (`tests/outbound/`)

```
collected 11 items

tests/outbound/test_models_core.py .....                                 [ 45%]
tests/outbound/test_models_sending.py ......                             [100%]

============================== 11 passed in 0.36s ===============================
```

**M1b:** 6 passed | **Totaal:** 11 passed (M1a: 5 + M1b: 6)

---

## Enum-namen (geen conflict met M1a)

| Enum naam | Waarden |
|---|---|
| `outbound_touchpoint_channel` | `email` |
| `outbound_touchpoint_status` | `scheduled`, `sent`, `delivered`, `bounced`, `failed` |
| `outbound_reply_label` | `A_rejection`, `B_interested`, `C_ready`, `needs_review`, `ooo`, `forwarded`, `question`, `referral`, `hostile`, `unsubscribe` |
| `outbound_reply_classified_by` | `llm`, `human` |

---

## Design-keuzes

- `touchpoint_id` en `prospect_id` in `OutboundReply` zijn **nullable** — inbound replies kunnen soms niet teruggekoppeld worden aan een specifiek touchpoint.
- `OutboundTouchpoint.channel` is nu slechts `email`; uitbreidbaar naar `linkedin`, `phone` in een toekomstige migratie.
- `confidence` (Float) heeft geen DB-level CHECK constraint voor 0.0–1.0; validatie gebeurt in de applicatielaag (Pydantic).
- `DateTime(timezone=True)` gebruikt voor alle timestamp-kolommen — compatibel met zowel SQLite (tests) als PostgreSQL (productie).

---

## BANANENSCHIL

Geen bananenschillen geregistreerd — alle stappen voltooid zonder fouten.

---

## Volgende stap (M1c / M1d)

Milestone 1b is de basis voor:
- **M1c**: CRUD service-laag + repositories voor touchpoints, replies, classifications
- **M1d**: Alembic-testmigratie voor productie PostgreSQL + integratietests
