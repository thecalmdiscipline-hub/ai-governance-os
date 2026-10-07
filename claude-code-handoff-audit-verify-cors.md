# Handoff voor Claude Code — Batch A: `/audit/verify` repareren (per-tenant keten) + CORS `PUT`

Context: `claude/dogfood-portal-onboarding-plan.md` (bevindingen B3 en B4) en `claude/executieplan-fase-0-1.md` (Batch A) in het projectdocument. Dennis heeft op 19 sep 2026 akkoord gegeven op Fase 0 en 1 als onderdeel van 100%-gereedheid. Dit is de eerste batch: twee kleine, onafhankelijke correcties. **Twee losse commits** (eerst CORS, dan audit), zodat één ervan los teruggedraaid kan worden.

Standaardafspraken blijven gelden: de taak eindigt met expliciete testeisen en een CLAUDE.md-update (onderaan). Begin met `git status`/`git diff` (drift-check, zie CLAUDE.md sectie 7) en commit zo snel mogelijk na groene tests.

---

## Deel 1 — CORS: `PUT` toestaan

**Probleem:** `app/core/middleware.py` staat `allow_methods=["GET","POST","PATCH","DELETE","OPTIONS"]` toe, maar `app/api/governance.py` heeft `PUT /corrective-actions/{action_id}/status`. Een browser (portaal op `app.valqeron.com`) krijgt daar een mislukte preflight op.

**Doen:**
1. Voeg `"PUT"` toe aan `allow_methods`. Verder niets aan CORS wijzigen (origins blijven zoals ze zijn).
2. Controleer `nginx/sites/*.conf` en `nginx/snippets/common.conf` op eigen `Access-Control-*`-headers of `limit_except`-regels die `PUT` alsnog blokkeren of CORS-headers dubbel zetten. Als je iets vindt: **niet blind aanpassen**, eerst terugkoppelen in CLAUDE.md sectie 4/6.
3. Test (nieuw bestand `tests/test_cors.py`): een `OPTIONS`-preflight op `/corrective-actions/1/status` met `Origin: https://app.valqeron.com` en `Access-Control-Request-Method: PUT` geeft 200 en `access-control-allow-methods` bevat `PUT`; dezelfde preflight met `Origin: https://evil.example` geeft géén `access-control-allow-origin`.

---

## Deel 2 — `/audit/verify`: schrijf- en verificatiekant gelijktrekken, per-tenant keten

### Bewijs (gereproduceerd door Cowork tegen de echte code, SQLite)
- `create_audit_log()` (`app/core/audit.py`) berekent `record_hash` met **HMAC-SHA256** (`generate_hmac_signature`, sleutel `AUDIT_SECRET_KEY`) en neemt `previous_hash` van de **globaal laatste** regel (over alle organisaties).
- `verify_audit_chain()` (`app/api/audit.py`) herberekent met **gewone `hashlib.sha256`** (geen sleutel) en eist per organisatie een aaneengesloten id-reeks.
- Resultaat: één tenant, drie regels geschreven via `create_audit_log` → `{"status":"compromised","message":"Hash mismatch detected"}`. Met twee tenants die door elkaar schrijven ook. Er is geen test voor `/audit/verify` en het portaal roept het niet aan, dus het viel nooit op.

### Ontwerp (besluit D6 — geen schemawijziging, geen herschrijven van historie)
Audit-logs zijn immutable (ORM-events blokkeren update/delete) en er staan al productierijen in de oude globale keten. Daarom een **"epoch"-markering zonder nieuwe kolom**:

1. **Schrijven (`create_audit_log`)**, signatuur en gedrag richting aanroepers ongewijzigd (incl. `db.commit()` aan het eind):
   - Neem een rijlock op de organisatie (`db.query(Organization).filter(Organization.id == organization_id).with_for_update().first()`), zodat gelijktijdige schrijvers voor dezelfde organisatie niet dezelfde `previous_hash` lezen (fork). Op SQLite is `FOR UPDATE` een no-op; dat is prima voor tests.
   - Bestaat er voor deze organisatie nog geen marker-rij (`entity_type="audit_chain"`, `action="chain_v2_started"`, `entity_id=0`, `performed_by="system"`, `details="Per-organization audit chain (v2) started; earlier records belong to the legacy global chain"`), maak die dan eerst aan met `previous_hash=None`.
   - `previous_hash` = `record_hash` van de **laatste rij van deze organisatie** (na de marker is dat altijd een v2-rij). `record_hash` blijft **HMAC-SHA256 over exact dezelfde `raw_string`-opbouw als nu** (dat houdt de oude rijen per-rij verifieerbaar).
2. **Verifiëren (`verify_audit_chain`)**, per organisatie, rijen op `id` oplopend:
   - Rijen **vóór** de marker (legacy): alleen per rij controleren dat `record_hash` == HMAC van de eigen velden inclusief opgeslagen `previous_hash` (vergelijk met `hmac.compare_digest`). Schakeling naar vorige rij is niet te controleren (die wijst de globale keten in). Rijen zonder `record_hash` tellen als `legacy_rows_unverifiable`, niet als compromised.
   - Rijen **vanaf** de marker (v2): marker moet `previous_hash is None` hebben; elke volgende rij moet `previous_hash ==` de `record_hash` van de vorige rij hebben én een kloppende HMAC. **De id-contiguïteitscheck vervalt** (ids zijn globaal, dus per organisatie nooit aaneengesloten).
   - Geen marker en geen rijen: `valid`. Alleen legacy-rijen: `valid` met `chain_v2_started: false`.
   - Response houdt `status` en `message` (compat), en krijgt extra velden `chain_v2_started`, `legacy_rows_checked`, `legacy_rows_unverifiable`, `chain_rows_checked`; bij `compromised` ook `log_id`.
3. `audit-export` en `GET /audit` blijven functioneel ongewijzigd. De markerrij verschijnt als gewone regel in de lijst (dat is acceptabel en bedoeld).
4. **Geen Alembic-migratie nodig.** Optioneel, alleen als het zonder risico kan: een index op `audit_logs(organization_id, id)` via aparte migratie (`scripts/deploy.sh` draait `alembic upgrade head` vóór de service-restart, maar migraties worden niet automatisch teruggedraaid, dus uitsluitend additief/nullable werk). De code mag er niet van afhangen.

### Vóór het pushen — read-only controle op productie (verplicht)
Legacy-verificatie is alleen zinvol als de huidige `AUDIT_SECRET_KEY` dezelfde is als toen de bestaande productierijen werden geschreven. Draai (via SSH, zelfde aanpak als bij de PII-verificatie, **geen schrijfacties**) een script dat voor élke organisatie in productie de per-rij-HMAC-controle uitvoert en de aantallen rapporteert. Als er rijen niet kloppen: **stop, push niets, en rapporteer aan Dennis** (mogelijk sleutelrotatie of echte manipulatie; dat is zijn beslissing).

### Tests (nieuw bestand `tests/test_audit_chain.py`; gebruik verse organisaties, niet org 1, de in-memory-DB wordt door de suite gedeeld)
1. Eén tenant, meerdere logs via `create_audit_log` → verify = `valid`, `chain_rows_checked` ≥ 2 (marker + logs).
2. Twee tenants die door elkaar schrijven → beide `valid`.
3. Manipulatie: wijzig `details` van een v2-rij met **raw SQL** (`UPDATE ...`, omzeilt de ORM-events) → `compromised` met juiste `log_id`.
4. Verwijdering: verwijder een middelste v2-rij met raw SQL → `compromised`.
5. Legacy: schrijf rijen met het **oude algoritme** (globale `previous_hash`, HMAC) direct in `audit_logs`, schrijf daarna nieuwe via `create_audit_log` → `valid`, `legacy_rows_checked` > 0; manipuleer een legacy-rij (raw SQL) → `compromised`.
6. Roundtrip: schrijf → `commit` → `expire_all`/nieuwe sessie → verify blijft `valid` (timestamp-formattering moet hetzelfde blijven).
7. Endpoint-test via `TestClient` op `/audit/verify` (auth zoals `tests/test_audit_endpoint.py`), voor tenant met en zonder marker.
8. Alle bestaande tests blijven groen (`pytest -q -m "not codex"`, nu 112; het nieuwe totaal noteren in CLAUDE.md).

### Na deploy (verplicht, nog voor je "klaar" meldt)
- Controleer via de GitHub Actions-API dat CI én Deploy daadwerkelijk groen zijn (les uit sectie 5), niet alleen lokaal.
- Productie: voer één onschuldige audit-genererende actie uit op de demo-tenant (bijv. één workflow-run via rechtstreekse functie-aanroep, zoals eerder) en draai daarna de verificatie voor die organisatie en voor org 1: verwacht `valid`, met `legacy_rows_checked` > 0 en `chain_rows_checked` ≥ 2 voor de tenant waar je zojuist schreef. Plak de echte uitvoer in CLAUDE.md sectie 6.
- Controleer de CORS-preflight op productie: `curl -i -X OPTIONS https://api.valqeron.com/corrective-actions/1/status -H 'Origin: https://app.valqeron.com' -H 'Access-Control-Request-Method: PUT'` → 200 met `PUT` in `access-control-allow-methods`.

## Niet doen
- Geen bestaande auditrijen wijzigen of verwijderen. Geen schemawijziging die code-afhankelijk is. Geen wijzigingen buiten `app/core/audit.py`, `app/api/audit.py`, `app/core/middleware.py` en de nieuwe tests (tenzij de nginx-controle iets vraagt: dan eerst terugkoppelen).
- Niet stilzwijgend afwijken van het ontwerp; als iets in de praktijk niet klopt (bijv. productie-legacy rijen verifiëren niet), stoppen en terugkoppelen.

## Afsluiting (verplicht)
1. **Testeisen:** alle nieuwe tests uit deel 1 en 2 groen; volledige suite groen lokaal én in CI; productiecontroles hierboven uitgevoerd en uitvoer vastgelegd.
2. **CLAUDE.md bijwerken:** sectie 5 (risicorij "audit-verify" toevoegen en meteen als opgelost markeren, of open laten als iets blokkeert), sectie 6 (nieuwe regel per commit, met commit-hashes en de echte productie-uitvoer), sectie 7 (eerstvolgende stap: Batch B uit `claude/executieplan-fase-0-1.md`: productie-organisaties inventariseren en HQ-tenant vaststellen, en `ai-governance-frontend` in git + CI/CD). Verifieer na de commit dat de CLAUDE.md-wijziging daadwerkelijk blijft staan (drift-patroon).
