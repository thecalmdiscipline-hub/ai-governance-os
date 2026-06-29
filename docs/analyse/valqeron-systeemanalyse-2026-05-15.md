# Valqeron Systeemanalyse
*Datum: 2026-05-15 | Auteur: Systeem-architect analyse*

---

## 1. Samenvatting (max 10 regels)

Valqeron is een B2B SaaS-platform dat bedrijven helpt AI-systemen te deployen, besturen en monitoren via een centrale "control layer" genaamd Valqeron Core. De propositie is: gecontroleerde AI in plaats van gefragmenteerde tools. Het platform is gebouwd op FastAPI + PostgreSQL + OpenAI (GPT-4o-mini) en draait als single-tenant per organisatie via multi-tenant database-isolatie (`organization_id` op elke tabel). Er zijn 10 AI-workflows (van Sales Qualification tot Compliance Monitoring). Pricing loopt van €4.500 setup + €1.250/maand (Starter) tot €15.000+ setup + €5.000+/maand (Enterprise), met workflows afzonderlijk geprijsd op €750–€12.500/maand. Er is **geen** email/SMTP-infrastructuur aanwezig — geen ESP-integratie, geen transactionele mailer, geen outbound email-capability. De enige externe integratie is Microsoft Graph (OneDrive/SharePoint file sync + OAuth). Er zijn geen CRM-, payment- of calendar-integraties in de codebase aangetroffen.

---

## 2. Propositie & Product

### Wat doet Valqeron concreet?
Valqeron biedt een gestructureerde omgeving voor bedrijven om AI-systemen te registreren, risico's te beheren, compliance te borgen en AI-workflows te draaien. Alles draait door Valqeron Core, dat governance, audit-logging, policy-beheer en module-toegang regelt.

Bronnen:
- `app/static/index.html:9` — meta description: "Valqeron builds controlled AI systems for businesses through a premium, structured environment."
- `app/static/app.jsx:489-494` — hero copy: "Controlled AI systems for serious businesses. One environment. Clear oversight."

### Welk probleem lost het op?
Gefragmenteerde AI-tools zonder governance, geen audittrail, geen centrale oversight, compliance-risico (EU AI Act, ISO 27001, ISO 42001).

Bronnen:
- `app/static/app.jsx:561-576` — "Valqeron delivers a structured operating environment for AI systems — designed to replace fragmented automations with control, clarity, and measurable business impact."
- `app/static/app.jsx:601-606` — referentie aan EU AI Act, ISO 27001, ISO 42001

### Tastbaar resultaat voor klant
- Audit trail voor elke AI-handeling (immutable log chain)
- Gecentraliseerde AI-system registry met risk scores en lifecycle stages
- 10 AI-workflows die direct werken op eigen documenten
- Tenant-isolatie: iedere organisatie ziet alleen eigen data

### Modules & Features
10 geregistreerde modules/workflows (`app/services/module_access.py:8-85`):

| Module key | Workflow key | Omschrijving |
|---|---|---|
| core | — | Governance, audit, oversight, control layer |
| document_intelligence | document_knowledge | Document upload, preview, extractie |
| compliance_monitor | compliance_monitoring | Policy-overzicht, compliance tracking |
| customer_support_ai | customer_support | Support workflow automatisering |
| sales_qualification_ai | sales_lead_qualification | Lead intake, scoring (0-100), ICP matching |
| invoice_processing_ai | invoice_processing | Invoice extractie en validatie |
| hr_recruitment_ai | hr_recruitment | Kandidaat screening en samenvatting |
| marketing_automation_ai | marketing_automation | Campaign strategie en automation |
| meeting_agenda_assistant | meeting_agenda_assistant | Meeting prep en agenda structurering |
| quote_contract_generator | quote_contract_generator | Quote/contract draft generatie |
| business_intelligence | business_intelligence | Executive insights en data lineage |

Governance-laag (naast workflows):
- AI System Registry (CRUD met risk_category, lifecycle_stage, conformity_assessed)
- AI Risk Engine (risk_level: high/medium/low, automatische rollback bij open high risks)
- AI Incident Management
- AI Policy Engine (purpose, principles, risk_commitment, monitoring_commitment)
- Evidence module (koppeling risk ↔ document)
- Corrective Actions (met status tracking)
- Production Approval workflow
- Document management (upload, preview, download, delete)
- Immutable audit log chain (blockchain-stijl HMAC hashing)

### USP's & Differentiators
- `app/static/app.jsx:211-223` — "Controlled systems", "Modular evolution", "Operational clarity"
- Automatische rollback bij open high-risk AI-systemen in production (`app/core/governance.py:1-54`)
- Immutable audit logs (update/delete blokkering via SQLAlchemy events) (`app/models/audit_log.py:43-48`)
- Multi-tenant isolatie vanaf dag 1
- Compliance-aligned aan EU AI Act, ISO 27001, ISO 42001 (`app/static/app.jsx:601-606`)

---

## 3. Ideal Customer Profile (uit data)

### Klant-entiteiten in datamodel
Primaire entiteit: `organizations` (`app/models/organization.py`)
- Velden: `id`, `name`, `max_review_age_days` (default 30), `required_production_approvals` (default 1), `country`, `sector`
- Relaties: ai_systems, audit_logs, ai_policies, documents

Gebruiker: `users` (`app/models/user.py`)
- Rollen: `admin`, `auditor`, `operator`
- Velden: `is_super_admin`, `is_active`, `failed_login_attempts`, `account_locked_until`

### Segmentatie
Uit de pricing copy (`app/static/app.jsx:113-140`):
- **Starter**: kleine bedrijven die starten met AI
- **Business**: bedrijven met €1M+ omzet die operationele automatisering willen
- **Enterprise**: grotere organisaties met compliance, governance en integratie-behoeften

Sales Qualification ICP (`app/workflows/implementations/sales_lead_qualification.py:37`): "B2B sales qualification AI for enterprise companies with €1M+ annual revenue."

### Geschatte omvang klantenbestand
Huidige demostaat: 2 tenants (org_1, org_2 — zie `DEMO_USERS.md`, `uploaded_documents/`). Dit zijn demo/test-tenants, geen echte klanten aantoonbaar in codebase. `status_export/` en `status_export_customer2/` zijn lokale snapshot-exports voor demo-doeleinden.

---

## 4. Prijsmodel & Dealwaarde

### Plannen & Tiers
Uit `app/static/app.jsx:112-208`:

**Platform packages:**
| Tier | Setup | Maandelijks | Minimum |
|---|---|---|---|
| Starter | €4.500 | €1.250/maand | Workflows apart |
| Business | €8.500 | €2.500/maand | Min. 3 workflows |
| Enterprise | Vanaf €15.000 | Vanaf €5.000/maand | Min. 5 workflows |

**Workflow pricing (afzonderlijk):**
| Workflow | Maandelijks |
|---|---|
| Document Knowledge AI | €950–€1.750 |
| Full Document Audit AI | €1.500–€3.000 |
| Customer Support AI | €2.000–€5.000 |
| Sales Qualification AI | €1.750–€4.500 |
| Quote & Contract AI | €2.000–€5.000 |
| Invoice Processing AI | €1.500–€4.000 |
| Marketing Automation AI | €1.500–€4.000 |
| Business Intelligence AI | €2.500–€6.000 |
| HR Recruitment AI | €1.500–€4.000 |
| Meeting Assistant AI | €750–€2.000 |
| Compliance Monitoring AI | €3.000–€7.500 |
| Governance & Risk AI | €3.500–€8.500 |
| ISO / EU AI Act Layer | €5.000–€12.500 |

### Payment integraties
**GEEN DATA** — geen Stripe, Mollie, Paddle of andere payment-integratie aangetroffen in de codebase. Pricing staat alleen in de marketing-frontend, geen backend billing-logica.

### Gemiddelde dealwaarde (indien zichtbaar)
Business tier (meest gepromoot): €8.500 setup + min. €2.500 + min. 3 workflows (bijv. 3 x €2.000) = €8.500 setup + €8.500/maand. Jaardeal: ~€110.000. Enterprise kan oplopen tot €100.000+ setup + €50.000–€100.000+/jaar.

---

## 5. Social Proof / Cases

**GEEN DATA** — geen testimonials, logo-walls, case study pages, klantlogo's of referentieklanten aangetroffen in de codebase. De marketing-frontend (`app/static/app.jsx`) bevat uitsluitend generieke propositionele copy zonder klantnamen of quotes.

---

## 6. Technische Architectuur

### Stack
- **Runtime**: Python 3.9
- **Web framework**: FastAPI 0.128.8 (`requirements.txt:6`)
- **ASGI server**: Uvicorn 0.39.0 (`requirements.txt:18`), 2 workers in productie (`systemd/valqeron.service:26`)
- **ORM**: SQLAlchemy 2.0.46 (`requirements.txt:14`)
- **Migrations**: Alembic 1.16.5 (`alembic/`)
- **Auth**: JWT (python-jose 3.3.0) + bcrypt (passlib 1.7.4)
- **AI**: OpenAI SDK >=2.0.0, model `gpt-4o-mini` (`requirements.txt:24`, `app/workflows/implementations/sales_lead_qualification.py:35`)
- **Validation**: Pydantic v2 2.12.5

### Backend
FastAPI-applicatie met routers voor: auth, governance, audit, documents, users, microsoft, workflows. Entrypoint: `app/main.py`. Startup security checks op SECRET_KEY en AUDIT_SECRET_KEY. Global exception handler. CORS via middleware.

API-structuur (`app/main.py:103-123`):
- `/login` — JWT auth
- `/organizations`, `/systems`, `/risks`, `/incidents`, `/policies` — governance CRUD
- `/documents/` — upload/download/delete
- `/audit/` — immutable audit trail
- `/workflows/{workflow_key}/run` — AI workflow execution
- `/microsoft/` — OAuth + Graph API sync
- `/health` — health check

### Frontend
React 18 (CDN, geen build tooling) met Babel standalone. Twee pagina's: HomePage en CorePage. Client-side routing via `window.location.pathname`. Serveert via FastAPI StaticFiles. Geen Next.js, geen Vite, geen bundler.

- `app/static/index.html` — entry point
- `app/static/app.jsx` — volledige React applicatie (1057 regels)
- `app/static/styles.css` — styling

### Database
- **Productie**: PostgreSQL (`DATABASE_URL=postgresql://...` in `.env.example:11`)
- **Tests/CI**: SQLite in-memory (`DATABASE_URL: "sqlite+pysqlite:///:memory:"` in `.github/workflows/ci.yml:34`)
- **Lokaal dev**: `dev.db` (SQLite) aanwezig in root

Schema-tabellen (uit modellen en migraties):
- `organizations`, `users`, `ai_systems`, `ai_risks`, `ai_incidents`, `ai_policies`
- `corrective_actions`, `evidence`, `production_approvals`
- `audit_logs` (immutable, HMAC-chained)
- `documents`, `workflow_runs`
- `tenant_modules` (per-org module activation)
- `contact_submissions`
- `microsoft_documents`, `microsoft_tokens`

### Queue/Cron
**GEEN DATA** — geen Celery, RQ, APScheduler, Cron of background task queue aangetroffen. Alle workflow-runs zijn synchrone HTTP-aanroepen. Geen asynchrone job-verwerking.

### Hosting & CI/CD
- **Server**: Linux VPS, systemd service (`systemd/valqeron.service`)
- **Reverse proxy**: Nginx met SSL (Certbot/Let's Encrypt) (`nginx/valqeron.conf`)
- **Domeinen**: `api.valqeron.com` (FastAPI :8000), `app.valqeron.com` (frontend :3000), `compliance.valqeron.com` (:8001)
- **Deploy**: `scripts/deploy.sh` — git pull + pip install + alembic upgrade + systemctl restart + health check met automatische rollback
- **CI**: GitHub Actions (`.github/workflows/ci.yml`) — pytest op SQLite, Python 3.9, geen OPENAI_API_KEY vereist in CI

---

## 7. Bestaande Integraties

| Integratie | Type | Status | Bewijs |
|---|---|---|---|
| OpenAI (GPT-4o-mini) | AI/LLM | Actief, production | `requirements.txt:24`, alle `app/workflows/implementations/*.py` |
| Microsoft Graph API | OAuth + Files | Actief, production | `app/integrations/microsoft/graph_client.py`, `app/services/microsoft/` |
| Microsoft OAuth | Auth | Actief | `app/services/microsoft/oauth.py`, `app/core/microsoft_config.py` |
| Redis | Rate limiting | Actief (verplicht in prod) | `requirements.txt:21`, `.env.example:13`, `app/core/rate_limiter.py` |
| PostgreSQL | Database | Actief, production | `requirements.txt:11`, `.env.example:11` |

**GEEN** integraties aangetroffen voor:
- Email (SendGrid, Mailgun, Postmark, Resend, SES, SMTP)
- Payment (Stripe, Mollie, Paddle)
- Calendar (Calendly, Google Calendar, Outlook Calendar)
- CRM (HubSpot, Pipedrive, Salesforce)
- Lead enrichment (Apollo, Hunter, Clearbit, LinkedIn)

---

## 8. Mail-infrastructuur (huidige staat)

### ESP/SMTP configuratie
**GEEN DATA** — geen enkele email-sending library of ESP-integratie aangetroffen in requirements.txt, .env.example of enige Python-file. De codebase bevat geen `smtplib`, `fastapi-mail`, `sendgrid`, `mailgun`, `resend`, `ses`, of vergelijkbare imports.

### Email templates & mailer services
**GEEN DATA** — geen email templates (HTML of tekst), geen mailer service klasse, geen email-queue.

### DKIM/SPF/DMARC documentatie
**GEEN DATA** — geen DNS-configuratie of email-authenticatiedocumentatie aanwezig.

### Verzendende domeinen/inboxen
**GEEN DATA** — geen geconfigureerde sending domain. Enige domein-referenties zijn voor CORS/nginx: `app.valqeron.com`, `api.valqeron.com`, `compliance.valqeron.com`.

**Conclusie**: De volledige email-infrastructuur ontbreekt. Er is geen enkele transactionele email (welkomstmail, password reset, notificaties) geïmplementeerd.

---

## 9. Agenda & Calls

**GEEN DATA** — geen Calendly, Google Calendar, Outlook Calendar, Zoom, Teams of scheduling integratie aangetroffen. De enige CTA voor demos zijn mailto-achtige contactformulier-knoppen die doorsturen naar `#contact-form` op de homepage, waarbij gegevens worden opgeslagen in de `contact_submissions` tabel (`app/main.py:156-166`, `app/models/contact_submission.py`).

Het contactformulier slaat op: `name`, `email`, `company`, `message`, `created_at`. Er is geen geautomatiseerde opvolging of routing vanuit dit formulier.

---

## 10. Voorgestelde plek voor module "Outbound Engine"

### Architectuurlocatie
```
app/
  outbound/
    __init__.py
    models/           # SQLAlchemy models
    schemas/          # Pydantic input/output schemas
    routers/          # FastAPI routers
    services/         # Business logic
      prospect_enrichment.py
      email_sender.py
      sequence_runner.py
      reply_classifier.py
    implementations/  # LLM-calls (conform workflow-patroon)
      personalization.py
      reply_classification.py
```

Dit sluit aan op het bestaande patroon: `app/workflows/` heeft exact dezelfde structuur (models, schemas, routers, services, implementations). De outbound engine wordt een parallelle module naast workflows.

### Datamodel-uitbreiding (nieuwe tabellen)

**Prospect** — contact die bereikt moet worden
```sql
prospects (
  id, organization_id FK,
  first_name, last_name, email, title,
  company_id FK, linkedin_url,
  enrichment_data JSONB,
  status VARCHAR,  -- new / enriched / in_sequence / replied / disqualified
  created_at, updated_at
)
```

**Company** — bedrijfs-entiteit (ICP-matching)
```sql
companies (
  id, organization_id FK,
  name, domain, industry, employee_count, annual_revenue,
  country, linkedin_url, website,
  icp_score INTEGER,  -- 0-100, berekend door LLM (conform sales_lead_qualification patroon)
  created_at, updated_at
)
```

**Campaign** — outbound campagne
```sql
campaigns (
  id, organization_id FK,
  name, description, status,  -- draft / active / paused / completed
  campaign_type VARCHAR,  -- cold / warm / reactivation
  target_icp JSONB,  -- ICP-criteria voor deze campagne
  created_by_user_id FK,
  created_at, updated_at
)
```

**Touchpoint** — individueel contactmoment in een sequentie
```sql
touchpoints (
  id, campaign_id FK, prospect_id FK,
  sequence_step INTEGER,  -- 1, 2, 3, ...
  channel VARCHAR,  -- email / linkedin / phone
  subject VARCHAR, body TEXT,
  scheduled_at DATETIME, sent_at DATETIME,
  status VARCHAR,  -- scheduled / sent / delivered / bounced / failed
  esp_message_id VARCHAR,  -- extern ID van de ESP
  created_at
)
```

**Reply** — inkomende reactie
```sql
replies (
  id, touchpoint_id FK, prospect_id FK,
  body TEXT, received_at DATETIME,
  raw_headers TEXT,
  classification_id FK,
  created_at
)
```

**Classification** — AI-classificatie van reply
```sql
reply_classifications (
  id, reply_id FK,
  label VARCHAR,  -- interested / not_interested / out_of_office / referral / question / unsubscribe
  confidence FLOAT,
  reasoning TEXT,
  classified_by VARCHAR,  -- "llm" / "human"
  model VARCHAR,
  tokens_used INTEGER,
  created_at
)
```

**ScheduledCall** — gebookde call na positieve reply
```sql
scheduled_calls (
  id, prospect_id FK, organization_id FK,
  scheduled_at DATETIME, duration_minutes INTEGER,
  meeting_link VARCHAR, notes TEXT,
  status VARCHAR,  -- scheduled / completed / no_show / cancelled
  created_by_user_id FK,
  created_at
)
```

### Hoe het past in de architectuur
- Tenant-isolatie: `organization_id` op alle nieuwe tabellen (conform bestaand patroon)
- Audit logging: `create_audit_log()` aanroepen bij elke send/reply/classification (conform `app/core/audit.py`)
- Module-access: nieuwe module keys toevoegen aan `BASE_MODULES` in `app/services/module_access.py`
- LLM-calls: conform het `sales_lead_qualification` patroon — OpenAI client, `gpt-4o-mini`, JSON response format, fallback bij failure
- Alembic-migratie: nieuwe versie in `alembic/versions/`
- Router-registratie: in `app/main.py` naast bestaande routers

---

## 11. Gaps & Risico's

| Gap | Ernst | Toelichting | Bestand |
|---|---|---|---|
| Geen ESP/SMTP | Kritiek | Geen email-sending capability aanwezig. Vereist integratie van bijv. Resend, SendGrid of Postmark + configuratie van sending domain, DKIM, SPF. | GEEN DATA |
| Geen job queue | Hoog | Alle code is synchroon. Email-sequenties vereisen een async task queue (Celery + Redis, of APScheduler). Redis is al aanwezig voor rate limiting. | `requirements.txt:21` |
| Geen reply-ingest | Hoog | Er is geen webhook-endpoint voor inkomende emails. Vereist ESP-inbound parsing (bijv. SendGrid Inbound Parse, Postmark Inbound). | GEEN DATA |
| Geen calendar-integratie | Hoog | Geen Calendly of Google Calendar koppeling. ScheduledCall-entiteit kan worden aangemaakt maar niet automatisch gebookt. | GEEN DATA |
| Geen payment/billing | Middel | Pricing staat alleen in de frontend. Geen subscription management, geen metered billing voor email-volume. | GEEN DATA |
| Geen CRM/enrichment | Middel | Geen Apollo, Hunter of Clearbit. Prospect-data moet manueel aangeleverd of via CSV-import komen. | GEEN DATA |
| Geen LinkedIn-integratie | Middel | LinkedIn is als touchpoint-channel voorzien maar er is geen API-integratie. | GEEN DATA |
| Frontend is SPA zonder SSR | Laag | React via CDN zonder bundler — schaalbaar genoeg voor marketing maar bevat geen dashboard-views voor een outbound engine. Een admin-interface voor campagnebeheer moet nog worden gebouwd. | `app/static/index.html` |
| Geen unsubscribe-mechanisme | Kritiek (compliance) | Bij outbound email is een one-click unsubscribe wettelijk verplicht (CAN-SPAM, GDPR). Er is geen unsubscribe-endpoint of suppression list. | GEEN DATA |
| Geen bounce-verwerking | Hoog | Geen bounce-handling logica. Hard bounces moeten uit de sequentie worden verwijderd. | GEEN DATA |

---

## 12. Open vragen voor Dennis

1. Welke ESP ga je gebruiken voor outbound? (Resend, SendGrid, Postmark, of zelfbeheerde SMTP via bijv. Amazon SES)
2. Is er een dedicated sending domain beschikbaar voor outbound (bijv. `mail.valqeron.com` of apart warmup-domein)?
3. Moet de outbound engine prospectdata zelf verrijken (via Apollo/Hunter/Clay API) of wordt dat manueel aangeleverd (CSV-upload)?
4. Is LinkedIn als touchpoint-channel in scope voor V1, of alleen email?
5. Moet de reply-classificatie volledig automatisch opvolgen (bijv. auto-book Calendly) of alleen classificeren en een melding sturen naar de sales-rep?
6. Wordt de outbound engine alleen gebruikt voor Valqeron's eigen sales, of ook als te verkopen module aan klanten?
7. Is er een warmup-strategie voor het sending domain (bijv. via Mailreach of Lemwarm), of ga je direct koud versturen?
8. Wat is de gewenste daily sending volume per campagne? (Dit bepaalt ESP-tier en warmup-periode)
9. Zijn er al prospect-lijsten beschikbaar (bijv. ICP-bedrijven met contacten), of moet de prospecting pipeline ook worden gebouwd?
10. Moet er een GDPR/AVG-compliant opt-out en data retention policy worden ingebouwd vanuit de start?
