# Hand-off Batch I — Fase 2.1 + 2.2: accounts en onboarding in tenant 0 (alleen backend)

Auteur: Cowork (architect). Uitvoerder: Claude Code, **één sessie**. Datum: 6 okt 2026.
Repo: `ai-governance-os` (backend). Het portaal (Fase 2.3) komt pas na mijn akkoord.
Start pas **nadat** `claude-code-handoff-batch-g-deel4-resend-activeren.md` is afgerond en in CLAUDE.md staat.

## Doel

Valqeron werkt zelf in het platform (tenant 0 = HQ = org 1). Na deze batch kan een super-admin met MFA, via `/ops/*`, klanten en prospects als **account** vastleggen, er een **onboardingproject** voor starten uit het Client Onboarding Playbook (8 fasen), taken bijwerken, en de doorlooptijd per fase en van kickoff tot go-live berekenen. Dit levert ook de meting van readiness-punt 5 (kickoff → klaar). Geen portaalwijziging, geen klantzichtbare endpoints, geen automatische koppeling met andere workflows (dat is Fase 2.4).

Taak-ID's uit `claude/executieplan-fase-0-1.md` / `claude/dogfood-portal-onboarding-plan.md`: 2.1 en 2.2.

## Vooraf besloten (niet opnieuw voorleggen)

- Gewone organisatie in dezelfde database (D1), control plane in dezelfde backend onder `/ops/*` (D2), alleen `require_ops_access` (super-admin + HQ org 1 + MFA-claim + actief).
- Elke schrijfactie via `log_ops_action` (dubbele audit: HQ-keten, en de keten van de bron-organisatie zodra het account aan een organisatie gekoppeld is). **Alleen ids en statuswaarden in auditdetails**, nooit vrije tekst, contactgegevens of notities.
- Klanten lezen **nooit** uit deze tabellen. Er komt geen endpoint buiten `/ops/*`. De velden `customer_visible` en `owner` worden alleen opgeslagen; ze krijgen pas betekenis in Fase 3.1.
- Alleen additieve migraties. Geen nieuwe zware dependencies.
- **Geen Microsoft 365-taak in het sjabloon:** de integratie is uitgeschakeld (optie C). Documenten gaan handmatig.
- Persoonsgegevens: de tabellen bevatten alleen zakelijke contactgegevens. Contactnaam en e-mail komen niet in logs, auditdetails of Sentry-events (controleer `sentryScrub` en logformatters met een test).

## Werkwijze (vaste afspraken)

1. `git status` en `git diff` (drift-check, verwacht de commit van de Resend-batch of nieuwer). Meld afwijkingen.
2. **Fase 0 (alleen lezen), resultaat in de eerste alinea van je rapport:** hoe `require_ops_access`, `log_ops_action` en de bestaande `/ops/*`-routers (tenants, provisioning, support-requests) zijn opgebouwd en welke patronen je hergebruikt; of `outbound_companies` bestaat en hoe `companies` heet in het datamodel (voor het optionele veld `outbound_company_id`); hoe migraties en seed-scripts in dit project worden aangepakt. Wijkt iets af van dit document: stoppen en melden.
3. Kleine losse commits; na elke push CI én Deploy controleren via de GitHub Actions-API, plus een echte functionele check op productie.

## Deel 1 — Datamodel (migratie, additief)

Alle tabellen zijn globaal (HQ leest ze); geen `organization_id` als tenantfilter, wel een optionele koppeling.

**`ops_accounts`**: `id`, `name` (verplicht, ≤200), `country` (≤2), `sector` (≤120), `status` (`lead` | `qualified` | `proposal` | `contract` | `onboarding` | `live` | `lost` | `churned`, standaard `lead`), `source` (`inbound` | `outbound` | `referral` | `manual`), `proposed_tier` (`starter` | `business` | `enterprise`, nullable), `primary_contact_name` (nullable, ≤120), `primary_contact_email` (nullable, ≤254, gevalideerd), `organization_id` (nullable, uniek, FK naar de geprovisioneerde organisatie), `outbound_company_id` (nullable, alleen als de tabel bestaat; anders weglaten en melden), `notes` (nullable, ≤1000; in het veld zelf geen klantinhoud), `created_at`, `updated_at`.

**`onboarding_templates`**: `id`, `key` (uniek, bijv. `standard-v1`), `name`, `version`, `is_active`.
**`onboarding_template_tasks`**: `id`, `template_id`, `phase` (1–8), `position`, `title` (≤200), `owner` (`valqeron` | `customer` | `both`), `customer_visible` (bool), `description` (nullable).
**`onboarding_projects`**: `id`, `account_id`, `template_key`, `template_version`, `status` (`active` | `paused` | `completed` | `cancelled`), `target_golive_date` (nullable), `started_at`, `completed_at` (nullable), `created_by_user_id`.
**`onboarding_tasks`**: `id`, `project_id`, `phase`, `position`, `title`, `owner`, `customer_visible`, `status` (`todo` | `doing` | `done` | `skipped` | `blocked`), `started_at` (nullable), `completed_at` (nullable), `completed_by_user_id` (nullable), `note` (nullable, ≤500).

Een project **kopieert** de taken uit het sjabloon (latere sjabloonwijzigingen veranderen lopende projecten niet). Indexen op `account_id`, `project_id`, `status`.

## Deel 2 — Sjabloon `standard-v1` (seed)

Seed idempotent via `scripts/seed_onboarding_templates.py` (met `--dry-run`), zonder bestaande rijen te overschrijven. Inhoud, afgeleid van het Playbook (19 sep):

| Fase | Taken (eigenaar; V = klantzichtbaar) |
|---|---|
| 1 Lead & kwalificatie | Lead vastleggen: bron, bedrijf, contact (valqeron) · Kwalificeren op ICP: omzet, sector, AI-volwassenheid, compliance-druk (valqeron) · Tier voorstellen en relevante workflows noteren (valqeron) |
| 2 Voorstel, contract & DPA | Voorstel opstellen: tier, workflows, implementatiefee, maandbedrag (valqeron) · Voorstel akkoord (customer, V) · DPA getekend (both, V) · Gegevens van de klant ontvangen: bedrijfsnaam, land, sector, eerste beheerder, rollen overige gebruikers (customer, V) |
| 3 Kickoff | Kickoff call plannen (both, V) · Doelen en scope bevestigen per workflow (both, V) · Technisch contactpersoon en rollen toewijzen: admin, auditor, operator (customer, V) · Go-live datum vastleggen (both, V) |
| 4 Technische provisioning | Organisatie, beheerder en modules aanmaken via provisioning, met tier-check (valqeron) · Eenmalig wachtwoord via een apart, veilig kanaal overgedragen (valqeron) · Standaard AIPolicy vastgelegd (valqeron) · PII-anonimisering bevestigd voor het datatype van deze klant (valqeron) |
| 5 Configuratie & data | Eerste documenten handmatig geüpload (both, V) · Voorbeeldresultaat klaargezet (valqeron) · Risicoregister initieel gevuld: één AIRisk-rij per actieve workflow (valqeron) |
| 6 Training & overdracht | Trainingssessie gepland (both, V) · Training gegeven met de Client Portal Guide (valqeron, V) · Rollen en resultaten beoordelen uitgelegd (valqeron, V) |
| 7 Go-live verificatie | Elke actieve module minstens één keer gedraaid (valqeron) · Resultaat samen met de klant bekeken en beoordeeld (both, V) · Run zichtbaar in de audit trail en `/audit/verify` is `valid` voor de organisatie (valqeron) · Dashboard toont "Core active and ready" (valqeron) |
| 8 Nazorg | Eerste-week check-in (valqeron, V) · Eerste maandelijkse gebruiksrapportage verstuurd (valqeron, V) · Kwartaal-risicoregister-review ingepland (valqeron) |

## Deel 3 — Endpoints (alle onder `/ops/*`, `require_ops_access`)

- `GET /ops/accounts` (filter op `status`, zoeken op naam), `POST /ops/accounts`, `GET /ops/accounts/{id}`, `PATCH /ops/accounts/{id}` (alleen de velden hierboven; `organization_id` en `status` alleen via de volgende twee regels).
- `POST /ops/accounts/{id}/link-organization` (body: `organization_id`): koppelt een bestaande organisatie, weigert dubbele koppeling (409) en onbekende organisatie (404). Dit is een bewuste, aparte stap; het `provision`-endpoint blijft ongewijzigd (de wizard in 2.3 koppelt later).
- `POST /ops/accounts/{id}/status` (body: nieuwe status): toegestane overgangen alleen vooruit via `lead → qualified → proposal → contract → onboarding → live`, plus `lost` vanuit elke status vóór `live` en `churned` vanuit `live`. Andere overgangen geven 409. Elke overgang is een auditregel (alleen oude en nieuwe status).
- `GET /ops/onboarding/templates`; `POST /ops/accounts/{id}/onboarding` (start een project uit `standard-v1`, maximaal één actief project per account, 409 anders); `GET /ops/onboarding/projects` (filter op `status`, `account_id`); `GET /ops/onboarding/projects/{id}` (met taken per fase); `PATCH /ops/onboarding/projects/{id}` (alleen `target_golive_date`, `status`).
- `PATCH /ops/onboarding/tasks/{id}` (alleen `status` en `note`). Bij overgang naar `doing` wordt `started_at` gezet (eerste keer), bij `done` of `skipped` `completed_at` en `completed_by_user_id`. Bij `done` terug naar `todo` worden die velden gewist. Auditregel zonder notitietekst.
- `GET /ops/onboarding/projects/{id}/metrics`: per fase `started_at` (eerste taak aangeraakt), `completed_at` (laatste taak klaar, alleen als alle taken `done` of `skipped` zijn) en doorlooptijd in dagen; plus **kickoff-naar-go-live**: van het afronden van de eerste taak van fase 3 tot en met het afronden van fase 7 (null zolang dat niet kan), en **totaal** van `started_at` tot fase 8 afgerond. Alleen berekening, geen opslag.

Rate-limiting zoals bij de andere `/ops`-routes. Geen verwijderendpoints (alleen statussen).

## Deel 4 — Tests

Zonder netwerk, in de bestaande testopzet. Minimaal: gewone admin en klant-token krijgen 403 op alle nieuwe routes; super-admin zonder MFA-claim 403; met beide 200; accountstatusovergangen (toegestaan en verboden); link-organization (dubbel, onbekend); één actief project per account; taken uit sjabloon gekopieerd en sjabloonwijziging raakt lopend project niet; taakstatus zet en wist tijdstempels correct; metrics (lege fase, deels klaar, alles klaar, kickoff-naar-go-live met bekende tijdstippen); **dubbele auditregels** (HQ en gekoppelde organisatie) met `/audit/verify` `valid` voor beide; **geen contactgegevens of notities** in auditdetails, logregels of een geserialiseerd Sentry-event; migratie draait op lege Postgres en `alembic current` = nieuwe head; seed-script idempotent. Bestaande tests blijven groen; `pytest -q` volledig groen.

## Deel 5 — Productiecheck (met server-side gemunt token voor `dennis_admin` met MFA-claim, alleen in geheugen, niet geprint)

1. Migratie en seed-script op productie (eerst `--dry-run`). Meld namen en aantallen.
2. `POST /ops/accounts`: maak het account **"ISO CERT INTERNATIONAL LTD"** aan (land GB, sector "Certification body", bron `inbound`, status `lead`, **zonder** contactnaam of e-mail) en koppel org 4 (`link-organization`). Dit is bewust het eerste echte account: org 4 is hun demo-omgeving.
3. Start een onboardingproject uit `standard-v1`; zet precies **twee** taken van fase 1 op `done`; haal `/metrics` op en rapporteer de uitvoer (geen persoonsgegevens).
4. `/audit/verify` is `valid` voor org 1 (HQ) én org 4; er staan auditregels in beide ketens.
5. Een klant-token (bijvoorbeeld `customer2_admin`, server-side gemunt) krijgt 403 op `GET /ops/accounts`.
6. **Niets verwijderen.** Laat het account en het project staan (Dennis gebruikt ze in Fase 2.3).

## STOP na de backend

Na groene CI en Deploy en de productiecheck: **stop, rapporteer en wacht** op mijn melding voor Fase 2.3 (portaal). Begin er niet zelf aan.

## Stopvoorwaarden

Stop en meld als: een bestaand patroon afwijkt van dit document; een wijziging auth, MFA, provisioning of andere organisaties zou raken; een migratie niet additief kan; tests rood worden; contactgegevens of notities in een log, auditregel of Sentry-event zouden komen; een Deploy faalt (de pijplijn draait zelf terug; meld het); de classifier iets blokkeert (niet omzeilen, melden).

## Rapport

Fase 0-bevindingen en afwijkingen; commits (hash en doel), CI- en Deploy-run-id's; migratie (alleen namen en aantallen); nieuwe endpoints en scripts; testaantallen vóór en na; productiecheck per stap (verwacht, gezien, uitvoer zonder geheimen); beslissingen die je zelf hebt genomen; CLAUDE.md-update (§2, §5, §6, §7) met commit-hash.
