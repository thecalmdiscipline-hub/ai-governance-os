# Ontwerp: scope-codes, instellingen per bedrijf, provisioning en integratielaag

Fase A van `docs/bouwopdracht-scope-en-integraties.md`. Alleen onderzoek en ontwerp: er is **geen code gewijzigd**.
Branch: `feat/scope-documenten`. Datum: 2026-11-23.

> **Belangrijke beperking.** De bronspecificatie `claude/scope-documenten-specificatie.md` (project "AI business") staat
> niet op deze Mac (gezocht op de hele schijf). Dit ontwerp is daarom alleen gebaseerd op de samenvatting van de
> besluiten in §1 en de fasebeschrijvingen in §2 van de bouwopdracht. Besluiten die daar niet staan (bijvoorbeeld V1,
> V25, V26, V28 en V32 en hoger) kan ik niet in de code plaatsen. Zie §9 (vragen).

---

## 1. Huidige situatie (wat de code nu doet)

### 1.1 Documenten

| Onderdeel | Bestand | Wat het nu doet |
|---|---|---|
| Model | `app/models/document.py` | `documents`: id, organization_id, uploaded_by_user_id, filename, stored_name (uniek), path, content_type, size, created_at. **Geen** scope-code, documenttype, status, versie of archief-vlag. |
| Upload | `app/api/documents.py` `POST /documents/upload` | Elke ingelogde gebruiker van de organisatie mag uploaden, ook een `auditor`. Geen validatie op naam of inhoud. Bestand naar `uploaded_documents/org_<id>/<uuid>_<naam>`. Auditregel `uploaded`. |
| Opslag | `app/services/document_storage.py` | `save_uploaded_document()` doet zelf een `commit`. Wordt ook gebruikt door de Microsoft-sync en (eigen code) door provisioning. |
| Lezen | `app/services/document_reader.py` | Tekst uit `.txt/.md/.csv/.json/.pdf/.docx`; al het andere geeft `None`. Kale `except:`-blokken. |
| Verwijderen | `DELETE /documents/{id}` | **Harde verwijdering**: bestand van schijf en rij uit de database, ook als het document in een eerdere run is gebruikt. Auditregel `deleted`. |
| Preview | `GET /documents/{id}/preview` | Eerste 4000 tekens. |

### 1.2 Workflows en documenten

- `app/workflows/services/runner.py` roept elke workflow aan als `fn(payload={..., "org_id": org_id}, user_id=...)`, slaat een
  `WorkflowRun` op en schrijft één auditregel: `Workflow <key> executed with status ok`. **Geen documentnamen, geen codes, geen
  instantie, geen AI-systeem.**
- Alleen `document_knowledge` leest documenten (`_load_documents`):
  - met expliciete `documents` (lijst met `stored_name`): alle documenten van de organisatie met die namen;
  - zonder selectie: de **5 nieuwste documenten van de hele organisatie**, ongeacht inhoud of soort;
  - max 5 documenten, 6000 tekens per document (`_MAX_DOCS`, `_MAX_CHARS_PER_DOC`);
  - `answer.document_snippets` geeft de **eerste 500 tekens ruwe, niet-geanonimiseerde tekst** terug.
- `compliance_monitoring`, `sales_lead_qualification` en `hr_recruitment` lezen **geen** opgeslagen documenten. Compliance krijgt
  `policy_text` in de aanvraag zelf. De bouwopdracht (Fase C, V21) gaat ervan uit dat deze workflows een documentfilter krijgen;
  dat is dus **nieuw gedrag**, geen aanpassing van bestaand gedrag.
- Vaste waarden staan in elke implementatie: `_MODEL = "gpt-4o-mini"` (alle 10), `temperature` (0,0 tot 0,4), system-prompts
  als constante, en in `sales_lead_qualification._qualify` de grenzen 80 en 50.
- De `compliance_monitoring`-functie heeft een parameter `org_id` die de runner nooit vult (de runner geeft `org_id` alleen in
  `payload` mee). Geen bug vandaag, maar wel nodig om op te letten bij de documentfilter.

### 1.3 Modules, tiers, AI-systemen

- `app/services/module_access.py`: `BASE_MODULES` (core + 10), koppeling workflow-key naar module-key, `has_workflow_access()`.
- `app/services/tenant_modules.py`: de enige plek met de tierregels (blijft zo, V15).
- `ai_systems` heeft **geen** verwijzing naar een workflow. Provisioning maakt per workflowmodule een `AISystem` met als naam de
  modulenaam; de koppeling is alleen via die naam. `workflow_runs` heeft geen `ai_system_id`.

### 1.4 Rollen

`users.role` in {admin, auditor, operator} (`app/api/users.py`). `require_role()` laat één rol door (plus super-admin). Er is
nog geen helper voor "admin of operator".

### 1.5 Microsoft-integratie (bevestigd, zie ook CLAUDE.md §5)

- `microsoft_tokens.access_token`/`refresh_token` zijn een gewone `String`: **niet versleuteld**.
- `GET /microsoft/callback` eist een Bearer-token (werkt niet bij een browser-redirect van Microsoft), negeert `state` en
  **slaat het token niet op** (`del db`).
- `GET /microsoft/status` geeft altijd `connected: False`.
- `POST /microsoft/files/list` en `/sync` gebruiken een token uit de body vóór het opgeslagen token.
- `sync_onedrive_to_documents` gebruikt `drives/me/items/...` (ongeldig pad) en slikt elke fout in.
- Scopes: alleen `offline_access`, `Files.Read`, `User.Read`. Mail en agenda vragen nieuwe scopes (zie §6).
- Er is geen Google-code.

### 1.6 Provisioning

`app/services/provisioning.py` (`POST /ops/tenants/provision` en `scripts/provision_tenant.py`): één transactie voor organisatie,
eerste admin, modules, `AIPolicy`, per workflow een `AISystem` + `AIRisk`, optioneel demodocument; idempotent via
`provisioning_requests`. Audit en demo-run na de commit. **Let op:** het demodocument wordt met eigen code toegevoegd (niet via
`save_uploaded_document`); dat moet in Fase B ook een scope-code krijgen.

### 1.7 Support-mail

`app/services/support_mail.py`: alleen Valqeron-interne meldingen via Resend. Blijft ongewijzigd (bouwopdracht E7).

### 1.8 Overig van belang

- `create_audit_log()` doet zelf een `commit` (CLAUDE.md §5). Meerdere schrijfacties die samen moeten slagen: eerst alles
  wegschrijven en committen, daarna pas auditregels.
- Lokaal en in CI wordt het schema via `Base.metadata.create_all()` gebouwd, niet via Alembic. Een nieuw model moet daarom
  ook in `app/models/__init__.py` worden geïmporteerd. Productie gebruikt Alembic (head `3352c2c44255`).
- FK-kolommen toevoegen aan een bestaande tabel moet via `op.batch_alter_table()` (SQLite), zoals in O2.

---

## 2. Datamodel (voorstel)

Alle nieuwe tabellen hebben `organization_id` waar ze tenant-data bevatten. Elke query filtert op
`current_user.organization_id`, nooit op een waarde uit de aanvraag.

### 2.1 Fase B: scope-codes en documenten

**Nieuwe tabel `scope_codes`** (de lijst toegestane codes, zodat een code geen vrije tekst is)

| kolom | type | opmerking |
|---|---|---|
| code | String, PK | bijv. `CS`, `HR`, `COMP`, `SALES`, `GEDEELD` (lijst: vraag 2) |
| description | String | |
| is_shared | Boolean | een gedeelde code mag door elke workflow worden gelezen (V3/V4) |
| is_restricted | Boolean | bijv. HR: alleen leesbaar door de HR-workflow (V18) |

Alternatief: de codes in een configuratiebestand (`app/core/scope_codes.py`) in plaats van een tabel. **Voorstel: config-bestand**,
want de lijst is per platform, niet per bedrijf, en een wijziging hoort door een review te gaan. Dan vervalt deze tabel.

**Nieuwe tabel `document_scope_codes`** (V4: één document, meerdere codes)

| kolom | type | opmerking |
|---|---|---|
| id | Integer PK | |
| document_id | FK `documents.id`, index | |
| code | String, index | moet in de toegestane lijst staan |
| assigned_by | String | gebruikersnaam of `system:auto` |
| assigned_at | DateTime | |
| unique | (document_id, code) | |

Codes zijn na upload vast (V7): er is geen endpoint om ze te wijzigen. Enige uitzondering: het eenmalig indelen van bestaande
documenten zonder code (V27), alleen door een admin, en alleen zolang het document nog geen code heeft.

**Nieuwe kolommen op `documents`** (additief, nullable of met default)

| kolom | type | opmerking |
|---|---|---|
| document_type | String, nullable | gebruikt voor automatische toewijzing (V2) |
| status | String, default `active`, server_default `active` | `active` / `archived` / `unclassified` |
| archived_at | DateTime, nullable | |
| replaces_document_id | FK `documents.id`, nullable | V30: nieuwe versie wijst naar de oude |
| version | Integer, default 1 | |

Bestaande rijen krijgen `status = unclassified` (V27). Een workflow leest alleen `status = active`.

**Nieuwe tabel `workflow_run_documents`** (V19 en V29: welke documenten zijn in welke run gebruikt)

| kolom | type | opmerking |
|---|---|---|
| id | Integer PK | |
| workflow_run_id | FK `workflow_runs.id`, index | |
| document_id | FK `documents.id`, index | |
| filename | String | kopie op het moment van de run |
| codes | String (JSON-lijst) | kopie op het moment van de run |

Hiermee kan `DELETE /documents/{id}` bepalen of een document ooit is gebruikt (dan archiveren in plaats van verwijderen, V29).

**Configuratiebestand voor automatische toewijzing (V2):** `app/core/document_scope_rules.py` (of een YAML-bestand dat daar
wordt ingelezen). Inhoud: `document_type → [codes]` en `workflow_key → [codes die deze workflow mag lezen]`. Niet in de router.

### 2.2 Fase C: instellingen per bedrijf

**Nieuwe tabel `workflow_instances`**

| kolom | type | opmerking |
|---|---|---|
| id | Integer PK | |
| organization_id | FK, index | |
| workflow_key | String | moet in de registry staan |
| name | String | V12, uniek per organisatie |
| status | String | `active` / `disabled` (V14) |
| ai_system_id | FK `ai_systems.id`, nullable in de database | verplicht voor nieuwe runs (V31), in de code afgedwongen |
| created_at, updated_at | DateTime | |

**Nieuwe tabel `workflow_settings`**

| kolom | type | opmerking |
|---|---|---|
| id | Integer PK | |
| instance_id | FK `workflow_instances.id`, index | |
| key | String | `tone`, `language`, `document_codes`, `fields`, `thresholds`, `prompt_parts`, `model`, `temperature`, `integrations` |
| value | Text (JSON) | |
| version | Integer | elke wijziging = nieuwe rij met hogere versie, nooit overschrijven (voor audit en reproduceerbaarheid) |
| created_at, created_by | | |

De actieve waarde is de rij met de hoogste versie per (instance_id, key). Een run legt de gebruikte versies vast (zie hieronder).

**Nieuwe kolommen op `workflow_runs`**: `instance_id` (FK, nullable), `ai_system_id` (FK, nullable), `settings_snapshot`
(Text/JSON, nullable). Historische runs blijven `NULL` (voorstel 3, V31).

**Schema-validatie per instelling:** in code, één bestand `app/workflows/settings_schema.py` met per workflow een Pydantic-model
(standaardwaarden = de huidige constanten). Ongeldige waarde: 422. **Modellen:** vaste lijst `APPROVED_MODELS` in hetzelfde bestand
(vandaag alleen `gpt-4o-mini`; uitbreiden vraagt een codewijziging en review).

### 2.3 Fase D: provisioning

Geen nieuwe tabel. Nieuw configuratiebestand `app/core/provisioning_tiers.py` (of uitbreiding van `provisioning_defaults.py`):
per tier de standaardinstellingen per workflow. `provision_tenant()` maakt daarnaast per workflowmodule een `workflow_instance`
met standaardinstellingen en koppelt die aan het `AISystem` dat het nu al maakt. Idempotentie via `provisioning_requests` blijft.

### 2.4 Fase E: integraties

**Nieuwe tabel `connections`** (vervangt `microsoft_tokens`)

| kolom | type | opmerking |
|---|---|---|
| id | Integer PK | |
| organization_id | FK, index | |
| provider | String | `microsoft` / `google` |
| mailbox_kind | String | `customer` (eigen mailbox van de klant) / `valqeron` (adres van Valqeron per bedrijf) |
| account_label | String | bijv. het e-mailadres; geen geheim |
| access_token_enc | Text | Fernet met `CONNECTION_ENCRYPTION_KEY` |
| refresh_token_enc | Text | idem |
| expires_at | DateTime | |
| scopes | Text (JSON) | |
| status | String | `active` / `needs_reconnect` / `revoked` |
| last_refreshed_at | DateTime | |
| created_by_user_id | FK | |

**Nieuwe tabel `oauth_states`** (korte levensduur): state, organization_id, user_id, provider, created_at, used_at. Lost het
probleem op dat de callback nu een Bearer-token eist: de callback koppelt de terugkeer aan de organisatie via de opgeslagen state.

**Nieuwe tabel `outbound_actions`** (de goedkeuringswachtrij, E6; niet te verwarren met de bestaande `outbound_*`-tabellen van
de Outbound Engine, daarom voorstel naam `pending_actions`)

| kolom | type | opmerking |
|---|---|---|
| id | Integer PK | |
| organization_id | FK, index | |
| instance_id | FK `workflow_instances.id` | |
| connection_id | FK `connections.id` | moet van dezelfde organisatie zijn |
| kind | String | `send_mail` / `create_event` |
| payload | Text (JSON) | concept; mogelijk persoonsgegevens, zie §8 |
| status | String | `pending_approval` / `approved` / `sent` / `failed` / `rejected` |
| approved_by_user_id, approved_at | | alleen admin |
| sent_at, error_code | | korte, generieke foutcode, zoals bij support-mail |

**Nieuwe tabel `mail_poll_state`**: connection_id, laatst verwerkte bericht-id/tijd (voor polling, E5).

**Fase F:** nieuwe tabel `support_tickets` (organization_id, instance_id, source `mail`/`api`, externe bericht-id, onderwerp,
triage-resultaat, status, pending_action_id). Detail volgt in Fase F.

---

## 3. Migratieplan

Eén Alembic-migratie per fase, alles additief, getest up én down op SQLite (via `batch_alter_table` waar een FK aan een bestaande
tabel komt) en op een lege Postgres in een lokale container of CI (niet op productie, regel 3).

| Fase | Migratie | Inhoud | Data |
|---|---|---|---|
| B | `scope_codes_documents` | `document_scope_codes`, `workflow_run_documents`; kolommen op `documents` | alle bestaande documenten → `status = 'unclassified'`, geen code (V27) |
| C | `workflow_instances_settings` | `workflow_instances`, `workflow_settings`; kolommen `instance_id`, `ai_system_id`, `settings_snapshot` op `workflow_runs` (nullable) | historische runs blijven `NULL` |
| C | `backfill_workflow_instances` (los, apart te draaien script, geen migratie) | per bestaande organisatie en actieve workflowmodule een instantie met standaardinstellingen, gekoppeld aan het bestaande `AISystem` met dezelfde naam (of een nieuw als er geen is) | zonder dit kan na Fase C niemand meer een run starten (V31). Dry-run eerst, zoals `seed_modules.py` |
| E | `connections_and_approvals` | `connections`, `oauth_states`, `pending_actions`, `mail_poll_state` | `microsoft_tokens` heeft op productie 0 rijen (CLAUDE.md §5): geen datamigratie nodig; de tabel wordt pas in een latere migratie verwijderd, na akkoord (regel 6) |
| F | `support_tickets` | nieuwe tabel | geen |

**Gevolg voor productie na Fase B:** alle bestaande documenten zijn ongeclassificeerd, dus `document_knowledge` vindt niets tot een
admin ze indeelt. Op productie zijn dat o.a. de demo-documenten van org 3, 4 en 5. Dat is bedoeld (V27), maar moet vóór de merge
naar `main` worden aangekondigd, met een script om ze in te delen.

---

## 4. API-wijzigingen

### Fase B
- `POST /documents/upload`: alleen `admin` en `operator` (V6, nieuwe helper `require_any_role`). Optioneel formulierveld
  `document_type`. Validatie (V5):
  1. code uit de bestandsnaam (voorstel patroon: `<CODE>_<naam>.<ext>`, of meerdere: `<CODE1>+<CODE2>_<naam>`; zie vraag 3);
  2. code uit de eerste regels van de inhoud (voorstel: een regel `Scope: CODE[, CODE]` binnen de eerste 5 niet-lege regels);
  3. beide aanwezig en gelijk, en alle codes toegestaan; anders `422` met een duidelijke foutcode
     (`scope_code_missing`, `scope_code_mismatch`, `scope_code_unknown`), en er wordt niets opgeslagen;
  4. aanvullen met automatische codes uit `document_type` (V2);
  5. de codes in de database zijn leidend (voorstel 4).
  - Bestandstypen zonder leesbare tekst (bijv. afbeeldingen): kunnen geen code in de inhoud hebben → geweigerd (vraag 4).
- `POST /documents/{id}/replace` (V30): nieuwe versie; oude krijgt `status = archived`, nieuwe `replaces_document_id`.
  Codes moeten gelijk zijn aan die van de oude versie (V7).
- `DELETE /documents/{id}`: als het document in `workflow_run_documents` staat → archiveren (200, `archived: true`); anders
  zoals nu verwijderen (V29).
- `POST /documents/{id}/classify` (alleen admin, alleen bij `status = unclassified`): eenmalig codes toekennen (V27).
- `GET /documents` en detail: velden `codes`, `status`, `document_type`, `version` erbij (additief).
- `document_knowledge`: zie §5. `answer.document_snippets` verdwijnt uit de uitvoer (V8). Dit raakt de frontend
  (`ai-governance-frontend`, ResultsPage/DocumentsPage); de frontend-aanpassing is een aparte opdracht.
- `POST /ops/tenants/provision` met demodocument: het demodocument krijgt de code `GEDEELD` (of een andere, vraag 2).
- Microsoft-sync (`POST /microsoft/sync`) gebruikt `save_uploaded_document` zonder code: in Fase B ofwel blokkeren
  (voorstel: het endpoint geeft `409 scope_code_required` tot Fase E), ofwel geïmporteerde bestanden als `unclassified` opslaan.

### Fase C
- `GET /workflow-instances`, `GET /workflow-instances/{id}`, `POST /workflow-instances` (admin), `PATCH .../{id}` (naam, status),
  `GET/PUT /workflow-instances/{id}/settings` (admin; 422 bij ongeldige waarde of onbekend model).
- Workflow-run-routers (`/workflows/<key>/run`): nieuw veld `instance_id` in de body. Zonder `instance_id`: als de organisatie
  precies één actieve instantie van die workflow heeft, die gebruiken; anders 422 (zo blijven bestaande clients werken; vraag 6).
  Uitgezette instantie: 409 `instance_disabled` (V14). Instantie zonder `ai_system_id`: 409 `ai_system_required` (V31).
- `run_workflow()` krijgt `instance_id`, laadt de instellingen, geeft ze via `payload["settings"]` aan de implementatie en slaat
  `instance_id`, `ai_system_id`, `settings_snapshot` en de gebruikte documenten op.
- Uitvoer van documentlezende workflows bevat altijd `sources` (V22). Bij `confidence = low`: antwoord tonen (V23) en
  `requires_approval: true` (V24). Wat "goedkeuring" bij een gewone run inhoudt (wie, waar zichtbaar) is nog niet gespecificeerd
  (vraag 7).

### Fase D
- `POST /ops/tenants/provision`: response krijgt `counts.workflow_instances`. Geen nieuwe velden in de aanvraag (tierconfiguratie
  bepaalt de standaardwaarden); optioneel later een veld `settings_overrides`.

### Fase E
- `POST /integrations/{provider}/connect` (admin) → autorisatie-URL met opgeslagen state.
- `GET /integrations/{provider}/callback` (**zonder** Bearer-token; state bewijst de organisatie) → token versleuteld opslaan,
  redirect naar het portaal.
- `GET /integrations/connections`, `DELETE /integrations/connections/{id}` (admin).
- `GET /pending-actions`, `POST /pending-actions/{id}/approve`, `.../reject` (alleen admin). Approve verstuurt; bij een fout
  blijft de status `failed`, nooit stil opnieuw.
- Het bestaande `/microsoft/*`-router wordt vervangen. Voorstel: behouden achter de feature-vlag tot de nieuwe stroom live is,
  daarna verwijderen (vraag aan Dennis, regel 6).

---

## 5. Documentfilter (kern van Fase B, V3/V4/V18)

Eén functie, gedeeld door alle documentlezende workflows: `app/services/document_access.py`:

```
allowed_documents(db, organization_id, workflow_key, instance_id=None, explicit_ids=None) -> list[Document]
```

1. alleen `documents.organization_id == organization_id` en `status == 'active'`;
2. toegestane codes = codes van de workflow (uit `document_scope_rules`) ∪ gedeelde codes; in Fase C overschreven/versmald
   door de instelling `document_codes` van de instantie (nooit verruimd buiten wat de regels toestaan);
3. een document wordt gelezen als het **minstens één** toegestane code heeft (vraag 5: of juist alle codes moeten passen);
4. een document met een beperkte code (HR) wordt **nooit** gelezen door een workflow die die code niet zelf heeft, ook niet
   als het daarnaast een gedeelde code heeft (V18); dit is een harde extra regel ná stap 3;
5. expliciete selectie: alleen binnen het resultaat van 1 t/m 4; een geselecteerd document daarbuiten → 422
   `document_not_in_scope` (niet stil overslaan, zodat een gebruiker weet waarom);
6. zonder selectie: dezelfde filter, nieuwste eerst, max 5 (V20);
7. de runner schrijft per run een `workflow_run_documents`-rij en zet in de auditregel de documentnamen en codes (V19).
   Let op: bestandsnamen kunnen persoonsgegevens bevatten; de auditregel is per tenant en alleen voor de eigen organisatie
   zichtbaar, maar dit is wel een bewuste keuze die Dennis moet bevestigen (vraag 8).

Workflows die in Fase C documenten gaan lezen (`compliance_monitoring`, `sales_lead_qualification`, V21) gebruiken dezelfde
functie. Voor `compliance_monitoring` blijft `policy_text` uit de aanvraag werken; documenten komen erbij.

---

## 6. Integratielaag (Fase E), aanvullende ontwerpkeuzes

- **Interface** in `app/integrations/base.py`: `MailClient` (list_inbox, get_message, create_draft, send_draft) en
  `CalendarClient` (free_busy, create_event). Implementaties `app/integrations/microsoft/` (Graph) en `app/integrations/google/`
  (Gmail/Calendar REST). Voorstel: **alleen `httpx`** (al aanwezig), geen Google- of Microsoft-SDK, zodat er geen nieuwe
  dependency nodig is. `cryptography` (Fernet) is al aanwezig.
- **Sleutelhelper**: generaliseer het Fernet-patroon uit `app/core/mfa.py` naar `app/core/crypto.py` met een sleutelnaam als
  parameter, zodat `CONNECTION_ENCRYPTION_KEY` en `MFA_ENCRYPTION_KEY` dezelfde code gebruiken maar nooit dezelfde sleutel.
  Zonder sleutel: integraties geven 503, de rest van de app werkt (zelfde gedrag als MFA).
- **Scopes**: Microsoft `Mail.ReadWrite`, `Mail.Send`, `Calendars.ReadWrite`, `offline_access`, `User.Read`; Google
  `gmail.modify`, `gmail.send`, `calendar.events`, `calendar.freebusy`. Google eist voor `gmail.modify`/`gmail.send` een
  verificatie van de app (restricted scopes, mogelijk met een externe beveiligingsbeoordeling); dat kost tijd en is een
  zakelijke stap voor Dennis (vraag 10).
- **Valqeron-mailbox per bedrijf**: technisch ook een `connection` (provider microsoft of google), maar dan op een
  Valqeron-account. Of dat een gedeelde mailbox met aliassen is of een apart account per bedrijf, bepaalt wat de OAuth-stroom
  moet kunnen (vraag 11).
- **Token vernieuwen**: vóór elk gebruik als `expires_at` binnen 5 minuten valt; mislukt → `status = needs_reconnect`,
  auditregel, geen stille fout.
- **Scheduler (E5) — voorstel ter beslissing**: een systemd-timer (zelfde patroon als `valqeron-backup.timer` uit Batch P) die
  elke 2 tot 5 minuten `python scripts/poll_mailboxes.py` draait. Het script verwerkt per actieve verbinding nieuwe berichten,
  met een lock (Postgres advisory lock of een lockbestand) zodat twee runs elkaar niet overlappen. Geen Celery, geen nieuwe
  dependency. Nadeel: alles in één proces per tick; bij veel bedrijven later een echte queue (Redis is al aanwezig, RQ zou een
  nieuwe dependency zijn). **Akkoord van Dennis nodig.**
- **Goedkeuring falen dicht**: de enige code die `send_draft`/`create_event` aanroept is de approve-handler, die eerst de status
  in de database van `approved` naar `sending` zet (atomaire update met een `WHERE status = 'approved'`), pas dan verstuurt.
  Geen andere route roept de providerlaag aan voor uitgaande acties; een test controleert dat met een grep-achtige
  structuurtest, zoals in Batch P.

---

## 7. Besluiten en waar ze in de code landen

Alleen de besluiten die in de bouwopdracht staan. De volledige V-lijst ontbreekt (zie vraag 1).

| Besluit | Inhoud (volgens de bouwopdracht) | Waar in de code | Fase |
|---|---|---|---|
| V2 | Automatische koppeling op documenttype | `app/core/document_scope_rules.py`, upload in `app/api/documents.py` | B |
| V3 | Zonder selectie alleen eigen-code-documenten | `app/services/document_access.py`, `document_knowledge._load_documents` | B |
| V4 | Eén document, meerdere codes | `document_scope_codes` | B |
| V5 | Code in naam én inhoud; zonder code weigeren | upload-validatie, nieuwe helper `app/services/scope_code_parser.py` | B |
| V6 | Admin en operator mogen uploaden | `require_any_role("admin","operator")` in `app/api/dependencies.py` | B |
| V7 | Code na upload vast | geen wijzig-endpoint; replace vereist gelijke codes | B |
| V8 | Snippets niet meer tonen | `document_knowledge` uitvoer | B |
| V9, V10, V13 | Alles instelbaar per bedrijf | `workflow_instances`, `workflow_settings`, `settings_schema.py` | C |
| V11 | Instelbaar: toon, taal, documentset, velden, drempels, prompts, model | `settings_schema.py`, elke implementatie leest `payload["settings"]` | C |
| V12 | Naam per instantie | `workflow_instances.name` | C |
| V14 | Uitzetten: runs blijven, nieuwe geblokkeerd | runner + `status` | C |
| V15 | Tiers blijven | `tenant_modules.py` ongewijzigd | C |
| V16 | Inrichting volledig automatisch | `provisioning.py` + tierconfiguratie | D |
| V17 | Scope-test verplicht bij elke wijziging | nieuw testbestand `tests/test_document_scope.py`; voorstel: CI-stap die faalt als dat bestand ontbreekt of wordt overgeslagen | B |
| V18 | HR-data nooit in niet-HR-workflow | `is_restricted` + harde regel in `document_access.py` | B |
| V19 | Auditregel per run met documentnamen en codes | runner + `workflow_run_documents` | B |
| V20 | Max 5 documenten, 6000 tekens | blijft in `document_knowledge` (later instelbaar binnen die grens?) | B |
| V21 | Sales en compliance dezelfde documentfilter | `document_access.py` in beide implementaties | C |
| V22 | Bronnen altijd in de uitvoer | uitvoerschema van documentlezende workflows | C |
| V23, V24 | Lage zekerheid: tonen, goedkeuring vereist | uitvoerveld `requires_approval`; goedkeuringsflow onduidelijk (vraag 7) | C |
| V27 | Bestaande documenten handmatig indelen | migratie → `unclassified`; `POST /documents/{id}/classify` | B |
| V29 | Gebruikt document alleen archiveren | `DELETE /documents/{id}` + `workflow_run_documents` | B |
| V30 | Nieuwe versie vervangt, oude archiveren | `POST /documents/{id}/replace` | B |
| V31 | Historische runs zonder AI-systeem; nieuwe verplicht | nullable kolom + check in runner | C |
| Voorstel 3 | Kolom nullable | migratie Fase C | C |
| Voorstel 4 | Code in database telt | `document_scope_codes` leidend, naam/inhoud alleen bij upload | B |
| Providers | Microsoft én Google, klantmailbox én Valqeron-adres | `connections.provider`, `connections.mailbox_kind` | E |

---

## 8. Risico's en aandachtspunten uit het onderzoek

1. **Breaking change voor bestaande documenten**: na Fase B leest geen enkele workflow nog een bestaand document tot het is
   ingedeeld (zie §3). Plus: de Microsoft-sync en provisioning maken documenten zonder code.
2. **Breaking change voor bestaande tests**: 9 testbestanden uploaden of lezen documenten zonder code (zie §10). Die moeten in
   Fase B worden aangepast (bestandsnamen en inhoud met code), niet verwijderd.
3. **Breaking change voor de frontend**: `document_snippets` verdwijnt; upload vraagt een code in de bestandsnaam; na Fase C
   moet de run een `instance_id` kunnen meesturen. De frontend is niet onderzocht (bouwopdracht §4).
4. **Na Fase C kan zonder backfill niemand meer een run starten** (V31). De backfill hoort in dezelfde merge als Fase C.
5. **Persoonsgegevens in de goedkeuringswachtrij en tickets** (Fase E/F): mailinhoud wordt opgeslagen. Bewaartermijn,
   verwijdering en de DPA-sub-verwerkerslijst (Google, Microsoft als mailprovider) moeten bekend zijn vóór livegang.
6. **PII-anonimisering**: klantmail die naar OpenAI gaat valt onder dezelfde verplichte anonimisering; concept-antwoorden
   moeten `restore_placeholders` gebruiken (zoals Batch J).
7. **`create_audit_log()` commit zelf**: de runner moet eerst run + `workflow_run_documents` committen, dan pas de audit.
8. **Off-site back-up staat nog fout** (Batch P). Bouwopdracht §3 noemt dit terecht als voorwaarde vóór livegang van Fase E.
9. **Google-appverificatie** voor Gmail-scopes kan weken duren (zie §6).

---

## 9. Vragen voor Dennis (vóór Fase B)

1. De bronspecificatie `claude/scope-documenten-specificatie.md` staat niet op deze Mac. Kun je hem in de repo zetten (bijv.
   `docs/scope-documenten-specificatie.md`), zodat ik de ontbrekende besluiten kan plaatsen?
2. Welke scope-codes bestaan er, welke zijn gedeeld, welke beperkt (HR)? Codes in een configuratiebestand (voorstel) of in de
   database?
3. Exact formaat van de code in de bestandsnaam (voorstel `CS_handleiding.pdf`, meerdere `CS+GEDEELD_handleiding.pdf`) en in de
   inhoud (voorstel een regel `Scope: CS, GEDEELD` binnen de eerste 5 niet-lege regels)?
4. Bestanden zonder leesbare tekst (afbeeldingen, gescande PDF zonder tekstlaag): weigeren (voorstel) of alleen op bestandsnaam
   toestaan?
5. Een document met codes {CS, HR}: leesbaar voor de CS-workflow? Voorstel: nee, HR is beperkend en wint altijd.
6. Mogen bestaande clients een run starten zonder `instance_id` als er precies één instantie is (voorstel), of wordt
   `instance_id` meteen verplicht?
7. V24 "goedkeuring vereist" bij lage zekerheid: wie keurt goed, en wat gebeurt er vóór de goedkeuring met het antwoord?
8. Documentnamen in de auditregel (V19) kunnen persoonsgegevens bevatten. Akkoord, of alleen document-id's en codes?
9. Mag `/microsoft/*` na Fase E worden verwijderd en `microsoft_tokens` worden gedropt (0 rijen op productie)?
10. Google-appverificatie voor Gmail-scopes: start jij die? Zonder verificatie werkt het alleen voor testgebruikers.
11. Valqeron-adres per bedrijf: één gedeelde mailbox met aliassen, of een eigen account per bedrijf?
12. Akkoord met de systemd-timer als scheduler voor polling (§6), of liever eerst iets anders?
13. Mag de frontend in Fase B tijdelijk kapot zijn op het punt "snippets" en "upload zonder code", of moet de frontend-aanpassing
    in dezelfde release mee (dan eerst een frontend-opdracht)?

---

## 10. Tests: huidige stand

Baseline (`pytest -q -m "not codex"`, lokaal, branch `feat/scope-documenten`, vóór elke wijziging): zie
`docs/verslag-fase-a.md` voor de exacte aantallen.

**Testbestanden die het gedrag van documenten raken** (moeten in Fase B worden aangepast):

| Bestand | Tests | Wat het raakt |
|---|---|---|
| `tests/test_documents_upload.py` | 1 | upload zonder code (`test_document.txt`) → wordt na Fase B 422 |
| `tests/test_documents_db_persistence.py` | 1 | idem |
| `tests/test_documents_preview.py` | 1 | idem |
| `tests/test_documents_audit_log.py` | 1 | upload + harde delete + auditregel `deleted` |
| `tests/test_documents_detail_download_delete.py` | 1 | upload + harde delete |
| `tests/test_customer2_isolation.py` | 1 | upload zonder code, isolatie tussen tenants |
| `tests/test_document_knowledge_reads_uploaded_text.py` | 1 | `Document` direct in de database zonder code; assert op `document_snippets` (V8) |
| `tests/test_document_knowledge_auto_selects_recent_documents.py` | 1 | automatische selectie van nieuwste documenten (V3 verandert dit) |
| `tests/workflows/test_document_knowledge_impl.py` | 1 | `Document` zonder code |
| `tests/workflows/test_document_knowledge.py` | 1 | route-niveau |
| `tests/workflows/test_pii_restore_wiring.py` | 9 (1 relevant) | document_knowledge-variant met `Document` zonder code |
| `tests/workflows/test_pii_anonymizer_wiring.py` | 4 | spioneert op anonimisering in alle 10 workflows |
| `tests/test_ops_provisioning.py` | 12 | demodocument zonder code |
| `tests/test_microsoft_sync_service.py`, `test_microsoft_sync_route.py`, `test_microsoft_files_list.py`, `test_microsoft_routes.py`, `test_microsoft_document_sync.py` | 1 + 1 + 4 + 2 + 1 | Microsoft-routes en sync die documenten zonder code maakt; Fase E vervangt dit |

Raakt **instellingen/modellen** (Fase C): alle `tests/workflows/test_*_impl.py` (vaste `gpt-4o-mini`), en
`tests/workflows/test_sales_lead_qualification*.py` (grenzen 80/50).

**Ontbrekende tests vandaag**: geen enkele test op tenant-isolatie van `document_knowledge` (dat een document van organisatie B
nooit in een run van organisatie A komt); geen test dat een `auditor` niet kan uploaden (dat kan nu wél). Beide komen in Fase B.
