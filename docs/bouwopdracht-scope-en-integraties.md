# Bouwopdracht: scope-documenten, bedrijfsinstellingen en integratielaag

Voor: Claude Code in de repo `ai-governance-os`.
Bron van de beslissingen: `claude/scope-documenten-specificatie.md` (project "AI business"). Lees die eerst.
Opdrachtgever: Dennis. Bij twijfel: stoppen en vragen, niet raden.

## 0. Harde regels (niet onderhandelbaar)

1. **Werk op een eigen branch**, bijvoorbeeld `feat/scope-documenten`. Maak nooit commits op `main`.
2. **Push nooit naar `main`.** Elke push die CI doorstaat, deployt automatisch naar productie (zie CLAUDE.md, sectie 2, CD). Pushen naar de branch mag, mergen naar `main` alleen na akkoord van Dennis.
3. **Geen productie-acties**: geen SSH, geen `deploy.sh`, geen migraties op de productiedatabase, geen wijzigingen op de server.
4. **Geen geheimen**: lees, print of commit nooit `.env`, sleutels, tokens of `backup.env`. Voeg geen echte waarden toe aan code, tests of fixtures.
5. **Geen nieuwe dependencies** zonder vooraf te melden. Noem elke nieuwe package in je verslag.
6. **Niets verwijderen** van bestaande data of code zonder dat het in deze opdracht staat.
7. **Elke stap is klein en afsluitbaar**: tests groen, dan commit, dan volgende stap. Bij een rood test: stoppen, niet doorbouwen.
8. Werk `CLAUDE.md` pas bij als Dennis erom vraagt ("update CLAUDE.md").

## 1. Doel

Een platform waarin:
- documenten een verplichte scope-code hebben, en een workflow alleen documenten met zijn eigen code leest;
- elke workflow-instantie per bedrijf volledig instelbaar is (toon, taal, documentset, velden, drempels, prompts, model, integraties);
- bedrijven automatisch worden ingericht (provisioning zonder handmatige stap);
- een integratielaag bestaat waarmee een workflow per bedrijf mail en agenda kan gebruiken, met goedkeuring voor elke uitgaande actie.

Beslissingen van Dennis, samengevat:
- Scope-code in bestandsnaam én bovenaan de inhoud; upload zonder code wordt geweigerd; de code is na upload vast.
- Automatische koppeling op documenttype (V2); zonder selectie alleen eigen-code-documenten (V3).
- Eén document kan meerdere codes hebben (V4).
- Alles instelbaar per bedrijf (V9, V10 gewijzigd, V13 gewijzigd).
- Inrichting nu oppakken, volledig automatisch (V16 gewijzigd).
- Historische runs blijven zonder AI-systeem; nieuwe runs zijn verplicht gekoppeld (V31 gewijzigd).
- Code in database telt; naam en inhoud zijn een controle bij upload (voorstel 4, akkoord).
- Providers: Microsoft 365 en Google tegelijk. Mailbox: eigen mailbox van de klant én een adres van Valqeron per bedrijf, per bedrijf instelbaar.
- Scope-test is verplicht bij elke wijziging (V17). HR-data nooit in niet-HR-workflow (V18).

## 2. Fasen

Elke fase eindigt met een verslag (zie §5) en wacht op Dennis voordat de volgende begint.

### Fase A: Onderzoek en ontwerp (geen codewijziging)

- Lees: `app/models/*`, `app/services/document_*.py`, `app/services/module_access.py`, `app/services/tenant_modules.py`, `app/workflows/implementations/*.py`, `app/workflows/services/runner.py`, `app/api/governance.py` (35 KB), `app/api/documents.py`, `app/api/microsoft.py`, `app/services/microsoft/*`, `app/services/support_mail.py`, `app/services/provisioning*.py`, de tests in `tests/`.
- Schrijf `docs/ontwerp-scope-en-integraties.md` met: datamodel, migratieplan, API-wijzigingen, en per besluit uit de specificatie waar het in de code landt.
- Leg vast welke tests er nu zijn en welke het gedrag van documenten raken.
- Stop. Dennis leest het ontwerp en keurt het goed.

### Fase B: Scope-codes en documenttoegang

Doel: geen document meer zonder code; geen workflow leest buiten zijn code.

- Nieuw model of velden: `document_scope_codes` (document_id, code). Eén document, meerdere codes (V4).
- Upload-validatie: code uit bestandsnaam en uit de eerste regels van de inhoud. Verschil = weigeren. Zonder code = weigeren (V5).
- Automatische toewijzing op documenttype (V2): regels in één configuratiebestand, niet hardcoded in de router.
- Rechten: admin en operator mogen uploaden (V6). Codes zijn na upload vast (V7).
- `document_knowledge`: alleen documenten met de code van deze workflow of een gedeelde code (V3, V4). Zonder selectie: dezelfde filter.
- Snippets niet meer tonen (V8). Limiet 5 documenten en 6000 tekens blijft (V20).
- Verwijderen: als een document in een eerdere run is gebruikt, alleen archiveren (V29). Nieuwe versie vervangt, oude wordt gearchiveerd (V30).
- Auditlog: per run de gebruikte documentnamen en codes (V19).
- Bestaande documenten krijgen handmatig een code (V27). Een migratie zet ze op "geen code", zodat ze niet worden gebruikt tot een admin ze indeelt.

**Tests verplicht (V17):**
- Een document zonder code wordt geweigerd bij upload.
- Een document met een code die niet in de bestandsnaam staat, wordt geweigerd.
- `document_knowledge` met code A leest nooit een document met alleen code B.
- Een gearchiveerd document wordt niet meer gebruikt.
- HR-code in een niet-HR-workflow: geweigerd.
- Auditregel per run bevat documentnamen en codes.

### Fase C: Instellingen per bedrijf (alles instelbaar)

Doel: de vaste waarden uit de code halen en per workflow-instantie opslaan.

- Model `workflow_instances`: id, organization_id, workflow_key, naam (V12), status, ai_system_id (verplicht voor nieuwe runs, V31).
- Model `workflow_settings`: instance_id, sleutel, waarde (JSON), versie. Instelbaar: toon, taal, documentset, velden, drempels, prompt-onderdelen, model (V11).
- Modelkeuze uit een vaste lijst van goedgekeurde modellen; niet vrij invulbaar.
- `sales_lead_qualification`: score-grenzen (80, 50) uit de instellingen, niet uit `_qualify`.
- `compliance_monitoring`: documenten lezen met eigen code (V21).
- `sales_lead_qualification` en `compliance_monitoring` krijgen dezelfde documentfilter als `document_knowledge` (V21).
- Bronnen altijd in de uitvoer (V22). Lage zekerheid: antwoord tonen (V23), goedkeuring vereist (V24).
- Uitzetten van een instantie: runs blijven, nieuwe runs geblokkeerd (V14).
- Tiers blijven zoals ze nu zijn (V15). Tierregels blijven in `tenant_modules.py`.
- Historische runs blijven zonder `ai_system_id` (voorstel 3). Migratie voegt de kolom nullable toe.

**Tests verplicht:**
- Twee instanties van dezelfde workflow met verschillende drempels geven verschillende uitkomsten.
- Een instantie met model X gebruikt model X, niet het standaardmodel.
- Ongeldig model of ongeldige waarde: 422.
- Uitgezette instantie: nieuwe run geweigerd, oude run zichtbaar.
- Nieuwe run zonder `ai_system_id`: geweigerd.

### Fase D: Automatische provisioning (V16)

- Bestaande `POST /ops/tenants/provision` gebruiken. Nieuw: een configuratie per tier die de instellingen en de modules vastlegt.
- Voor elk nieuw bedrijf: organisatie, eerste admin, modules, workflow-instanties met standaardinstellingen, één AI-systeem per instantie.
- Idempotent blijven (`provisioning_requests`).
- Geen portaalscherm in deze fase; de ops-API volstaat.

### Fase E: Integratielaag (mail en agenda)

**Doel:** een workflow per bedrijf kan mail lezen, een concept maken, versturen na goedkeuring, en agenda raadplegen en afspraken maken.

Ontwerp (uit specificatie §4, vastgelegd als eisen):
1. **Verbindingsrecord** `connections`: organization_id, provider (microsoft|google), account-label, versleutelde tokens (Fernet, eigen sleutel `CONNECTION_ENCRYPTION_KEY`, net als MFA), scopes, status, laatst vernieuwd. De bestaande `microsoft_tokens`-tabel wordt hierin opgenomen; niet dubbel bewaren.
2. **Providerlaag** `app/integrations/<provider>/`: vaste interface `MailClient` (list_inbox, get_message, create_draft, send_draft) en `CalendarClient` (free_busy, create_event). Microsoft via Graph, Google via Gmail/Calendar API. Geen SDK zonder melding (zie regel 5).
3. **OAuth-stroom afmaken**: de callback slaat het token op in `connections` (nu niet). `/microsoft/status` leest echte status. Dezelfde stroom voor Google.
4. **Instelling per instantie**: welke verbinding, welke mailbox, welke agenda, welke sjablonen, of verzenden goedkeuring vereist (standaard ja).
5. **Ingang**: binnenkomende mail komt via polling per verbinding (eerste keuze; webhooks later). Vereist een job-mechanisme. **Let op:** CLAUDE.md sectie 2 zegt "Job queue: ontbreekt". Stel eerst een eenvoudige scheduler voor (bijvoorbeeld een systemd-timer die een CLI-commando aanroept) en leg de keuze voor aan Dennis. Geen Celery zonder akkoord.
6. **Goedkeuring**: elke uitgaande mail en elke afspraak komt in een wachtrij met status `pending_approval`. Alleen na goedkeuring door een admin wordt verzonden. Dit is de enige route naar buiten.
7. **Support-mail** (`support_mail.py`): blijft zoals het is voor Valqeron-intern. Klantmail gaat via de providerlaag, niet via deze functie.

**Tests verplicht:**
- Verbinding van bedrijf A is nooit bruikbaar voor bedrijf B (tenant-isolatie).
- Tokens staan versleuteld in de database; test op de ruwe kolomwaarde.
- Uitgaande mail zonder goedkeuring wordt niet verstuurd (ook niet bij fouten: falen dicht).
- Providers worden in tests gemockt; geen echte netwerkcalls in CI.
- Verlopen token: vernieuwen; mislukt vernieuwen: status `needs_reconnect`, geen stille fout.

### Fase F: Customer-service-workflow end-to-end

- `customer_support` uitbreiden: ticket wordt opgeslagen (nu niet), inkomende mail wordt een ticket, triage zoals nu, concept-antwoord in de wachtrij (Fase E).
- Agenda-actie alleen als de instelling dat aanzet.
- Dezelfde regels: scope-code, bronnen in uitvoer, goedkeuring voor verzending.

## 3. Wat jij (Dennis) moet beslissen of leveren, voordat het kan

- Akkoord op de job-mechanisme-keuze in Fase E (stap 5).
- Een Google Cloud- en Microsoft Entra-app (client-ID en secret) voor de OAuth-stroom. Die komen in de productie-`.env`, niet in de repo.
- `CONNECTION_ENCRYPTION_KEY` in de server-`.env` (een aparte sleutel, niet `MFA_ENCRYPTION_KEY`); Claude Code genereert die niet op de server.
- De off-site back-up (CLAUDE.md, sectie 2, Batch P): de access-key staat nog fout. Eerst oplossen voordat de integratielaag live gaat, want die slaat tokens op.

## 4. Bekende risico's uit het onderzoek

- `microsoft_tokens` slaat tokens **niet** versleuteld op (`String` kolom). Fase E vervangt dat.
- De OAuth-callback in `api/microsoft.py` slaat het token niet op. Fase E moet dat repareren.
- Er is geen job queue. Polling en goedkeuringswachtrijen hebben een scheduler nodig.
- `support_mail.py` heet "e-mail" maar is alleen voor Valqeron-meldingen; verwar het niet met klantmail.
- Frontend (`ai-governance-frontend`) is niet onderzocht. Documentpagina en instellingenpagina zijn een aparte opdracht, na Fase C.
- De tests zijn niet gelezen. Fase A moet vaststellen welke groen zijn voordat er iets wijzigt.

## 5. Verslag per fase

Schrijf na elke fase `docs/verslag-fase-<letter>.md` met:
- Wat is gedaan (bestanden, commits op de branch).
- Testresultaten (`pytest -q` met aantallen, vóór en na).
- Nieuwe dependencies.
- Wat niet is gedaan en waarom.
- Vragen voor Dennis.
- Expliciete bevestiging: niets gepusht naar `main`, geen productie-acties.

## 6. Eerste stap

Begin met **Fase A**. Lees de bronnen uit §2, schrijf het ontwerp, en stop. Geen codewijziging in Fase A.
