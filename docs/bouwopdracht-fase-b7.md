# Bouwopdracht B7: archiveren van bestaande documenten en terugzetroute

Voor: Claude Code in `ai-governance-os`.
Branch: `feat/scope-documenten` (bevat B1 t/m B6, laatste commit `99a3b44`, alembic-head `bab4f26df0b0`).
Lees eerst: `docs/verslag-fase-b.md`, `docs/scope-codes.md`, `docs/migratie-legacy-documenten.md`, en §0 van `docs/bouwopdracht-scope-en-integraties.md`.

## 0. Harde regels

1. **Alleen code en tests.** Niets op productie: geen SSH, geen deploy, geen migratie op productie.
2. **Niet pushen en niet mergen naar `main`.** Commits op de branch mag.
3. Geen geheimen lezen of printen (`.env`, `backup.env`, sleutels).
4. Geen nieuwe dependencies zonder melding.
5. Eerst test, dan commit. Test rood = stoppen.
6. Geen gedrag bouwen dat hier niet staat. Twijfel = stoppen en vragen.

## 1. Besluiten (Dennis, 24 nov 2026)

- **Alle bestaande documenten worden gearchiveerd.** Geen rij en geen bestand wordt verwijderd. Daarna lezen workflows alleen nieuwe, gecodeerde documenten. Geen overgangsregel, geen `LEGACY_UNCODED_ORGS`.
- **Geen lijst van documenten voor klanten 1 en 2.** Archiveren gaat door zonder die afstemming.
- **Terugzetten van archief** kan per document: codeer via `PATCH /documents/{id}/scope` en zet op `coded`. Alleen Valqeron-beheerders (zie B5a in de bouwopdracht).
- **Archief downloaden:** alleen Valqeron, tenzij de vlag `archive_download_enabled` voor die organisatie aan staat (B5b).
- **Verwijderen:** alleen admin en operator. Auditor en member mogen niet verwijderen.
- **Een PDF zonder tekstlaag** wordt geweigerd bij upload. Dat is acceptabel voor nu; geen handmatige route.
- **V2, automatische codevoorstellen:** een upload krijgt een voorgestelde code op basis van documenttype of trefwoorden. De uploader moet die bevestigen. Zonder bevestiging wordt de upload geweigerd (V5 blijft gelden). Voorstellen komen uit één regelbestand, `config/document_scope_rules.yaml`, niet uit de router.
- **De acht keuzes in §5 van `docs/verslag-fase-b.md` zijn geaccepteerd**, inclusief dat een super-admin met MFA ook mag uploaden.

## 2. Taken

### T1: archiveren (migratie)

- Nieuwe alembic-migratie op de huidige head `bab4f26df0b0`.
- Zet alle rijen in `documents` met `scope_status` ongelijk aan `archived` op `archived`. Geen `DELETE`, geen bestandsverplaatsing.
- De downgrade zet de status terug naar wat ervoor stond. De migratie moet daarvoor de oude status bewaren, bijvoorbeeld in een kolom `scope_status_before_archive`, of het bestand waarin dit zit moet expliciet uitleggen dat downgrade de oorspronkelijke status niet terugzet.
- **Test op SQLite én PostgreSQL.** SQLite alleen is niet genoeg: productie draait op PostgreSQL. Gebruik een tijdelijke PostgreSQL-database in de test (bijvoorbeeld via testcontainers of een `DATABASE_URL` voor de testrun). Geen verbinding met productie.

### T2: terugzetroute

- `PATCH /documents/{id}/scope` accepteert nu ook `archived` → `coded`, alleen voor Valqeron-beheerders (B5a).
- Bij terugzetten worden de codes gevalideerd (V7 blijft gelden: codes zijn vast na de eerste toewijzing).
- Auditregel in de HQ-keten en in de organisatie van het document (`log_ops_action`), zoals nu bij B5.
- Het document telt daarna als `coded` en wordt door de filter gelezen als de code klopt.

### T3: V2, codevoorstellen

- Bestand `config/document_scope_rules.yaml`: per regel een voorwaarde (documenttype of trefwoord) en één of meer voorgestelde codes.
- Een nieuw endpoint `POST /documents/scope-suggestion` geeft voor een upload de voorgestelde codes terug. Het slaat niets op.
- De upload-route blijft ongewijzigd: de uploader stuurt de bevestigde codes mee. Zonder bevestigde code: 422 (zoals nu).
- Yaml wordt geladen met `yaml.safe_load`. Geen nieuwe dependency: PyYAML staat al in de venv; meld dat in het verslag.
- Ongeldige regel (onbekende code) in het yaml-bestand: laden faalt luid bij start, niet stil.

### T4: verwijderen

- `DELETE /documents/{id}`: alleen admin en operator van de eigen organisatie. Auditor en member: 403.
- Gebruikte documenten blijven gearchiveerd, niet verwijderd (V29, bestaand gedrag).

## 3. Tests (verplicht)

1. Migratie op PostgreSQL: alle rijen `archived`, aantal rijen gelijk, geen bestand verplaatst.
2. Migratie op SQLite: idem.
3. Na migratie leest geen workflow een archiefdocument, ook niet met de juiste code.
4. `PATCH` van `archived` → `coded` door Valqeron-beheerder: 200, daarna leest de juiste workflow het document.
5. `PATCH` van `archived` → `coded` door klantadmin: 403.
6. `PATCH` met een onbekende code: 422, status blijft `archived`.
7. Terugzetten zonder MFA-token: 403.
8. Auditregel bestaat in HQ-keten én in de organisatie na terugzetten.
9. Voorstel-endpoint: document met een PDF zonder tekstlaag krijgt geen voorstel en wordt bij upload geweigerd.
10. Voorstel-endpoint: trefwoord uit de yaml geeft de voorgestelde code; geen match geeft lege lijst.
11. Upload zonder bevestigde code, ook als er een voorstel is: 422.
12. Yaml met onbekende code: laden faalt bij start, met duidelijke melding.
13. `DELETE` door auditor en member: 403; door admin en operator: 200.
14. Regressie: `sales_lead_qualification` en `compliance_monitoring` zonder documenten werken nog.

Draai `pytest -m "not codex"` vóór en na. Vorige stand: 585 geslaagd, 1 uitgesloten.

## 4. Verslag

Schrijf `docs/verslag-fase-b7.md` met:
- Commits op de branch, en de alembic-head na deze migratie.
- Testaantallen vóór en na, en welke tests op PostgreSQL zijn gedraaid.
- Hoe de downgrade de oorspronkelijke status behandelt.
- Nieuwe dependencies (verwacht: geen).
- Frontend-gevolgen die nieuw zijn.
- Bevestiging: niets gepusht naar `main`, geen productie-acties.

Stop daarna. Niet deployen, niet mergen. Dennis beslist.

## 5. Let op voor productie (niet nu uitvoeren)

Productie-uitrol van B7 volgt apart, pas nadat Dennis het verslag heeft gelezen en de off-site back-up werkt (de access-key in `backup.env` wordt nu afgewezen; zie CLAUDE.md sectie 2, Batch P). Zonder werkende back-up geen migratie op productie.
