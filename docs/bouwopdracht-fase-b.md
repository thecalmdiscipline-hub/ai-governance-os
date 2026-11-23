# Bouwopdracht Fase B: scope-codes en documenttoegang

Voor: Claude Code in `ai-governance-os`.
Branch: `feat/scope-documenten` (bestaat al, commit `ec713c6` = fase A). Werk daar, niet op `main`.
Lees eerst: `docs/ontwerp-scope-en-integraties.md`, `docs/scope-codes.md`, `docs/migratie-legacy-documenten.md`, en §0 van `docs/bouwopdracht-scope-en-integraties.md` (harde regels gelden ongewijzigd).

## 0. Harde regels

1. Niet pushen naar `main`. Push naar de branch mag pas na akkoord van Dennis.
2. Geen productie-acties: geen SSH, geen deploy, geen migratie op productie.
3. Geen geheimen lezen of printen (`.env`, `backup.env`, sleutels).
4. Geen nieuwe dependencies zonder melding.
5. Elke wijziging: eerst test, dan commit. Test rood = stoppen.
6. Gedrag dat verandert voor bestaande klanten: alleen in de migratie en het verslag, nooit stilzwijgend.

## 1. Besluiten die je moet uitvoeren (uit de 35 vragen)

Zie `docs/scope-codes.md` voor de codes en het formaat. Hier de regels:

- **V1**: scope-code staat in de bestandsnaam `[scope=...]` én op de eerste regel van de inhoud `scope: ...`. Verschil = weigeren.
- **V2**: automatische koppeling op documenttype. Regels in één configuratiebestand (`config/document_scope_rules.yaml`), niet in de router.
- **V3**: zonder selectie leest een workflow alleen documenten met zijn eigen code of `gedeeld`.
- **V4**: meerdere codes per document mogelijk. Minimaal één.
- **V5**: upload zonder code, of met een onbekende code, wordt geweigerd.
- **V6**: admin en operator mogen uploaden. Auditor en member mogen dat niet.
- **V7**: codes zijn na upload vast.
- **V8**: snippets niet meer in het antwoord.
- **V18**: `hr`-documenten worden alleen door workflow `hr` gelezen. Bij combinatie met `gedeeld`: weigeren (voorstel, zie beslispunt B3).
- **V19**: auditregel per run met documentnamen en codes.
- **V20**: limiet 5 documenten en 6000 tekens blijft.
- **V21**: `sales_lead_qualification` en `compliance_monitoring` krijgen dezelfde documentfilter als `document_knowledge`. Hun prompt krijgt de documenten erbij. Dit is nieuw gedrag: test dat het verzoek zonder documenten nog gewoon werkt.
- **V22**: elke uitvoer bevat `sources` (documentnamen en codes).
- **V29**: document dat in een run is gebruikt wordt niet verwijderd, alleen gearchiveerd (`scope_status=archived`).
- **V30**: nieuwe versie vervangt; oude wordt gearchiveerd.

## 2. Implementatie

### B1: datamodel en migratie

- Tabel `document_scope_codes` (document_id, code, created_at). Unieke sleutel (document_id, code).
- Kolom `documents.scope_status`: `uncoded` | `coded` | `archived`. Bestaande rijen: `uncoded`.
- Tabel `workflow_documents_access` NIET aanmaken; de workflow-code komt uit de registry, niet uit de database.
- Migratie met `alembic revision`, nooit handmatig in de database.
- Tests op SQLite: migratie omhoog en omlaag.

### B2: scope-codes en validatie

- Module `app/services/document_scope.py`:
  - `parse_scope_from_filename(name) -> set[str] | None`
  - `parse_scope_from_content(text) -> set[str] | None` (eerste niet-lege regel, `scope:`-prefix)
  - `validate_scopes(codes) -> None` (raise als een code onbekend is)
  - `effective_scope(doc) -> set[str]`
- Codes komen uit één bron: `app/services/document_scope_codes.py` (de lijst uit `docs/scope-codes.md` §3 en §4). Nergens anders hardcoded.
- Upload-route (`api/documents.py`): valideren vóór het wegschrijven van het bestand. Bij weigering geen bestand op schijf.

### B3: toegang in de runner

- Functie `allowed_document_codes(workflow_key) -> set[str]`: `{workflow_code, "gedeeld"}`.
- Filter: `Document.scope_status == "coded"` en de effectieve codes hebben een overlap met `allowed_document_codes`. Eén gedeelde filterfunctie voor alle vier workflows (`document_knowledge`, `sales_lead_qualification`, `compliance_monitoring`, plus de andere die documenten gaan lezen).
- `hr`-regel: een document met `hr` wordt door `allowed_document_codes("hr_recruitment")` alleen gelezen als het niet ook `gedeeld` heeft. Dit is het voorstel; Dennis beslist (B3 hieronder).
- De filter staat op één plek, in `app/services/document_access.py`. Geen workflow bouwt zijn eigen query.

### B4: snippets en bronnen

- `document_snippets` uit `document_knowledge` verwijderen uit de response (V8).
- Elke workflow die documenten leest voegt `sources` toe: `[{filename, codes}]` (V22).

### B5: rechten

- `POST /documents/upload`: rollen `admin` en `operator` (V6). Overig: 403.
- `DELETE /documents/{id}`: als het document in een run is gebruikt, archiveren in plaats van verwijderen (V29). Bepaal "gebruikt" via `workflow_runs.input_payload`/`output_payload` of, beter, een nieuwe tabel `document_usage` die bij elke run wordt gevuld (zie B6). Kies de nieuwe tabel; dat is betrouwbaarder.
- `PATCH /documents/{id}/scope`: alleen Valqeron-beheerders (zie B5a), alleen bij `uncoded`, codes worden gevalideerd (V7).

### B5a: Valqeron-beheerders

- Een Valqeron-beheerder is een gebruiker in de HQ-organisatie met de vlag `is_valqeron_admin`, die door Valqeron wordt toegekend (eerst Dennis en Rayvanno; later anderen die Valqeron aanwijst).
- De vlag wordt alleen gezet via een ops-endpoint (`PUT /ops/staff/{user_id}`), met `require_ops_access`, dubbele auditregel via `log_ops_action`, en nooit via de klant-API.
- Zonder de vlag: 403 op alle code-beheerroutes. Met de vlag: alleen met een MFA-geverifieerd token (zelfde regel als super-admin).
- Gebruik de bestaande super-admin-controle als voorbeeld; voeg niet een tweede systeem van rechten toe.
- Test: een klantadmin (andere organisatie, ook admin-rol) krijgt 403 op `PATCH /documents/{id}/scope` en op codelijst-beheer.

### B6: auditlog per run

- Tabel `document_usage` (run_id, document_id, codes, created_at). Gevuld door de runner na de run, in dezelfde transactie als `workflow_runs`.
- Auditregel `workflow_run_documents` met de documentnamen en codes (V19).

### B7: migratie van bestaande documenten

Volg `docs/migratie-legacy-documenten.md`:
- Stap 1: kolom `scope_status` toevoegen met default `uncoded`. Geen gedragswijziging in de lees-route.
- Stap 2 (vervangt de uitzondering): een migratie zet **alle bestaande documenten op `archived`**. Geen rij wordt verwijderd, geen bestand verplaatst. Na deze migratie zijn alle oude documenten zichtbaar in het archief en worden ze door geen workflow gelezen. Dit is het besluit van Dennis: archiveren, alles fris opstarten.
- Stap 3: `LEGACY_UNCODED_ORGS` wordt **niet** gebouwd.
- Stap 4: script `scripts/assign_document_scopes.py` is niet meer nodig voor de migratie. Als Valqeron later oude documenten wil terughalen, codeert Valqeron ze één voor één via `PATCH /documents/{id}/scope` en zet ze van `archived` op `coded`. Daarvoor moet de archief-terugzetroute bestaan; die bouw je in B7, niet het script.
- **Deze batch implementeert de migratie (archiveren) en de terugzetroute in code. Niets wordt op productie uitgevoerd.**

### B8: frontend (niet in deze batch)

Niet aanraken. Het portaal breekt na deze batch: snippets verdwijnen, en upload zonder code faalt. Dat is bekend. Frontend-aanpassing is een aparte opdracht (Fase C-frontend).

## 3. Beslissingen van Dennis

- **B3a (beantwoord)**: `hr` is exclusief. Upload met `hr` plus een andere code wordt geweigerd. Een document met `hr` wordt alleen door workflow `hr` gelezen.
- **B3b (beantwoord)**: `gedeeld` is een aparte code. Geen impliciete scope voor documenten zonder code.
- **B3c (beantwoord)**: alleen Valqeron-beheerders mogen codes toewijzen aan documenten en de codelijst beheren. Dat zijn Dennis, Rayvanno, of een door Valqeron aangewezen persoon. Organisatie-admins van klanten krijgen dit recht niet. Het recht wordt door Valqeron toegekend (zie B5a).
- **B3d (beantwoord)**: geen `LEGACY_UNCODED_ORGS`-uitzondering. Alle bestaande documenten gaan naar `archived` (zie B7). Vanaf nu start alles vers: alleen nieuwe, gecodeerde uploads worden gelezen.

Gevolg voor de demo-organisaties 3, 4 en 5: hun workflows lezen geen documenten tot er nieuwe, gecodeerde documenten zijn geüpload. Dat is bedoeld.

## 4. Tests (verplicht, vóór commit van B3 en verder)

1. Upload zonder code: 422, geen bestand op schijf.
2. Upload met code in naam maar niet in inhoud: 422.
3. Upload met onbekende code: 422.
4. `document_knowledge` met code `sales` leest nooit een document met alleen `hr`.
5. `hr_recruitment` leest geen document met `sales`.
6. Document met `gedeeld` wordt door alle workflows gelezen.
7. `uncoded` document wordt door geen workflow gelezen (behalve via `LEGACY_UNCODED_ORGS` binnen de einddatum).
8. `archived` document wordt niet gelezen.
9. Een gebruikte document wordt bij DELETE gearchiveerd, niet verwijderd.
10. Elke run schrijft `document_usage` en een auditregel.
11. `sales_lead_qualification` zonder documenten geeft nog steeds een uitvoer (regressie).
12. `compliance_monitoring` zonder documenten geeft nog steeds een uitvoer (regressie).
13. Snippets staan niet in de response.
14. Auditor en member mogen niet uploaden (403).
15. Script `assign_document_scopes.py` dry-run wijzigt niets (test op een kopie van de database).

Draai `pytest -q` vóór en na. Rapporteer het aantal (vorige stand: 528 geslaagd, 1 uitgesloten).

## 5. Verslag

Schrijf `docs/verslag-fase-b.md` met:
- Commits op de branch.
- Testaantallen vóór en na.
- Nieuwe dependencies (verwacht: geen).
- Wat niet is gedaan en waarom.
- Beslispunten B3a–B3d: wat je hebt gebruikt en of Dennis het nog moet bevestigen.
- Frontend-gevolgen: welke schermen breken (verwacht: documentpagina, workflow-snippets).
- Bevestiging: niets gepusht naar `main`, geen productie-acties.

Stop na het verslag. Geen fase C.
