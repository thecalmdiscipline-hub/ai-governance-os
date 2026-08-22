# Valqeron — Projectstatus (levend document)

> **Doel:** dit bestand is de actuele stand van zaken voor Valqeron, zodat elke Claude-sessie (Claude Code of de app) direct context heeft zonder handmatige uitleg.
>
> **Hoe bijwerken:** zeg na een sessie "update CLAUDE.md". Claude moet dan: (1) de git-history en gewijzigde bestanden sinds de laatste log-entry bekijken, (2) secties 2–7 verifiëren tegen de actuele code (niet tegen dit document zelf — code is de bron van waarheid), (3) sectie 6 aanvullen met een nieuwe regel, (4) sectie 7 herschrijven naar de nieuwe eerstvolgende actie. Structuur van dit bestand niet wijzigen zonder expliciet verzoek.
>
> **Laatst geverifieerd tegen code:** 2026-08-11

---

## 1. Project overzicht

**Valqeron** is een B2B SaaS-platform dat bedrijven helpt AI-systemen gecontroleerd te deployen, besturen en monitoren via een centrale "control layer" (Valqeron Core). Propositie: *gecontroleerde AI in plaats van gefragmenteerde tools* — governance, audit-logging, risicobeheer en 10 kant-en-klare AI-workflows in één omgeving, gepositioneerd richting EU AI Act / ISO 27001 / ISO 42001-compliance.

- **Doelgroep:** B2B, met name bedrijven vanaf €1M+ jaaromzet die operationele AI-automatisering willen met oversight (zie ICP-tekst in `app/workflows/implementations/sales_lead_qualification.py:37`).
- **Stack:** FastAPI + PostgreSQL (prod) / SQLite (dev/test) + OpenAI (`gpt-4o-mini`). Multi-tenant via `organization_id` op elke tabel (single-tenant-per-organisatie isolatie, geen aparte databases).
- **Frontend:** React 18 via CDN (Babel standalone, geen build tooling), geserveerd als static files door FastAPI. `app/static/app.jsx`.

### Pricing (3 tiers) — bron: `app/static/app.jsx:112-208`, ongewijzigd t.o.v. analyse van 2026-05-15

| Tier | Setup | Maandelijks | Voorwaarde |
|---|---|---|---|
| Starter | €4.500 | €1.250/mnd | Workflows los bij te kopen |
| Business | €8.500 | €2.500/mnd | Min. 3 workflows |
| Enterprise | Vanaf €15.000 | Vanaf €5.000/mnd | Min. 5 workflows |

Losse workflow-pricing: €750–€12.500/maand per module (Meeting Assistant goedkoopst, ISO/EU AI Act Layer duurst). Volledige tabel: `docs/analyse/valqeron-systeemanalyse-2026-05-15.md` §4.

**Let op:** dit is uitsluitend frontend-copy. Er is geen backend billing/subscription-logica — zie sectie 4.

---

## 2. Infrastructuur status

| Component | Status | Details | Gereedheid |
|---|---|---|---|
| Backend (FastAPI) | Live (code) | `app/main.py`, routers voor auth/governance/audit/documents/workflows/microsoft | 🟢 Hoog |
| Database (Postgres) | Gepland/config | `DATABASE_URL` in `.env.example` wijst naar Postgres; lokaal draait dev via SQLite (`dev.db`, `test.db`). Geen bewijs in repo van een daadwerkelijk draaiende productie-Postgres | 🟡 Onbevestigd |
| Auth (JWT + bcrypt) | Live (code) | `python-jose` + `passlib[bcrypt]`, startup-checks op `SECRET_KEY`/`AUDIT_SECRET_KEY` | 🟢 Hoog |
| Rate limiting (Redis) | Live (code), verplicht in prod | `app/core/rate_limiter.py`; `ENVIRONMENT=production` faalt bij startup zonder bereikbare Redis | 🟢 Hoog |
| Audit trail | Live (code) | Immutable HMAC-chained log, update/delete geblokkeerd via SQLAlchemy events (`app/models/audit_log.py:43-48`) | 🟢 Hoog |
| Reverse proxy (Nginx) | Config aanwezig, **niet bevestigd live** | `nginx/valqeron.conf` routeert `api.`/`app.`/`compliance.valqeron.com` naar 165.22.204.23. Opnieuw extern getest op 2026-08-19 (SSH poort 22, `curl -I` op `api.` en `compliance.valqeron.com`): alles timeout zonder RST, zelfde beeld als 2026-08-11 — geen regressie, maar ook geen verbetering | 🔴 Onbevestigd — waarschijnlijk offline |
| Systemd service | Config aanwezig, **niet bevestigd live** | `systemd/valqeron.service` — uvicorn, 2 workers, restart-policy. Zelfde onbereikbaarheid als hierboven; geen extern bewijs dat dit proces draait. Er is geen toegang vanuit deze omgeving om dit direct te diagnosticeren (geen `doctl`, geen DO API-token in `.env`, lokale SSH-key kreeg `Operation timed out` op poort 22) — herstelstappen voor Dennis via de DO-webconsole staan in `DEPLOY_RECOVERY.md` (2026-08-19) | 🔴 Onbevestigd — waarschijnlijk offline |
| Deploy-script | Aanwezig | `scripts/deploy.sh` — git pull + pip install + alembic upgrade + systemctl restart + health-check met auto-rollback | 🟢 Hoog (als script) |
| CI (GitHub Actions) | Live | `.github/workflows/ci.yml` — pytest op SQLite in-memory, Python 3.9, `OPENAI_API_KEY` is nu een dummy testwaarde (echte calls zijn gemockt, zie Testsuite-rij) | 🟢 Hoog |
| Testsuite | **Groen** | Alle tests slagen (`pytest -q`, 2x achter elkaar geverifieerd op 2026-08-11, exit 0 beide keren). OpenAI-calls zijn volledig gemockt via een autouse fixture in `tests/conftest.py` — 0 requests naar `api.openai.com` in de testrun | 🟢 Hoog |
| **Live marketing-site (valqeron.com)** | **Live, maar alleen statisch** | `valqeron.com`/`app.valqeron.com` → ander IP (217.160.0.147, Apache/shared hosting, vermoedelijk IONOS) dan de repo-config beschrijft. Serveert wél de exacte HTML/JSX uit `app/static/`, maar `/health` en `/api/status` geven 404 — de FastAPI-backend draait daar niet. Bezoekers zien dus alleen de marketing-pagina, geen werkend platform | 🟡 Static-only |
| Job queue / async workers | **Ontbreekt** | Geen Celery/RQ/APScheduler. Alle workflow-runs zijn synchrone HTTP-calls | 🔴 Ontbreekt |
| Email/SMTP | **Ontbreekt** | Geen ESP-integratie, geen `smtplib`/SendGrid/Postmark/Resend/SES, geen templates | 🔴 Ontbreekt |
| Payment/billing | **Ontbreekt** | Geen Stripe/Mollie/Paddle, geen subscription-logica | 🔴 Ontbreekt |
| AVG-anonimisering (Presidio) | **Ontbreekt** | Geen `presidio` of vergelijkbare PII-detectie/anonimisering in `requirements.txt` of code | 🔴 Ontbreekt |
| Microsoft Graph (OneDrive/SharePoint) | Live | `app/integrations/microsoft/graph_client.py`, OAuth + file sync | 🟢 Hoog |
| Outbound Engine (datamodel) | In opbouw | 9 tabellen (companies, prospects, campaigns, touchpoints, replies, reply_classifications, scheduled_calls, region_policies, suppression_list) via Alembic-migraties M1a–M1c. **Geen routers, geen services, geen ESP-integratie** — puur datamodel | 🟡 Fase 1/4 |

Legenda gereedheid: 🟢 werkt en is geverifieerd in code · 🟡 aanwezig maar niet vanuit repo te bevestigen als live/werkend · 🔴 ontbreekt volledig.

---

## 3. AI workflows

Alle 10 workflows draaien op OpenAI `gpt-4o-mini`, synchroon via `/workflows/{workflow_key}/run`. Registry/module-koppeling: `app/services/module_access.py`.

| Workflow key | Module | Omschrijving | Implementatie | Testresultaat |
|---|---|---|---|---|
| `sales_lead_qualification` | sales_qualification_ai | Lead intake, scoring 0-100, ICP-matching | `app/workflows/implementations/sales_lead_qualification.py` | 🟢 Groen |
| `document_knowledge` | document_intelligence | Document-Q&A op geüploade bestanden | `app/workflows/implementations/document_knowledge.py` | 🟢 Groen |
| `invoice_processing` | invoice_processing_ai | Factuur-extractie en validatie | `app/workflows/implementations/invoice_processing.py` | 🟢 Groen |
| `compliance_monitoring` | compliance_monitor | Policy-overzicht, compliance tracking | `app/workflows/implementations/compliance_monitoring.py` | 🟢 Groen |
| `customer_support` | customer_support_ai | Support-automatisering | `app/workflows/implementations/customer_support.py` | 🟢 Groen |
| `hr_recruitment` | hr_recruitment_ai | Kandidaat-screening en samenvatting | `app/workflows/implementations/hr_recruitment.py` | 🟢 Groen |
| `marketing_automation` | marketing_automation | Campagnestrategie | `app/workflows/implementations/marketing_automation.py` | 🟢 Groen |
| `meeting_agenda_assistant` | meeting_agenda_assistant | Meeting-prep en agenda | `app/workflows/implementations/meeting_agenda_assistant.py` | 🟢 Groen |
| `quote_contract_generator` | quote_contract_generator | Quote/contract-drafts | `app/workflows/implementations/quote_contract_generator.py` | 🟢 Groen |
| `business_intelligence` | business_intelligence | Executive insights, data lineage | `app/workflows/implementations/business_intelligence.py` | 🟢 Groen |

Alle 6 eerder falende tests + de kapotte `sales_lead_qualification`-importtest zijn op 2026-08-11 gefixt (zie sectie 6 voor root causes per test — een mix van echte stale assertions en test-setupbugs, geen enkele bleek een echte bug in de workflow-logica zelf op te leveren, op één latente stale-assertion in `sales_lead_qualification_impl` na die door de importfout verborgen zat).

**OpenAI-calls zijn gemockt.** Een autouse pytest-fixture in `tests/conftest.py` patcht `openai.OpenAI` voor elke test met een generieke, realistische default-respons; tests die op specifieke LLM-inhoud assertsen (invoice, document_knowledge, business_intelligence, customer_support) hebben een eigen override via `mock_openai_response(monkeypatch, {...})`. Geverifieerd: 0 requests naar `api.openai.com` tijdens een volledige testrun. CI heeft nu een dummy `OPENAI_API_KEY` zodat de workflow-tests daar ook meedraaien (via de guard `if not api_key`, niet via een echte call).

Input/output-schema's per workflow zijn niet los gedocumenteerd — zie de `run()`-functie in elk implementatiebestand voor het verwachte `payload`-formaat.

---

## 4. Openstaande kritieke acties (prioriteitsvolgorde)

Volgorde is een inschatting op basis van wat er in de code ontbreekt en wat sales/compliance blokkeert. Tijdsinschattingen zijn indicaties, geen harde toezeggingen — pas aan waar je betere info hebt.

1. **AVG-anonimiseringslaag (Presidio of vergelijkbaar)**
   Status: niet gestart — niets in de codebase.
   Geschat: 1–2 weken engineering (integratie in document-upload- en workflow-pipeline, PII-detectie vóór LLM-calls, tests).
   Nodig: keuze tussen Microsoft Presidio (open source, self-hosted) of managed alternatief; engineering-capaciteit.

2. **Verwerkersovereenkomst (DPA)**
   Status: geen enkel spoor in de repo (logisch — dit is een juridisch document, geen code). Kan hier niet geverifieerd worden.
   Geschat: afhankelijk van jurist — dagen tot weken.
   Nodig: juridisch advies, sub-verwerkers in kaart brengen (OpenAI, Microsoft Graph, hostingpartij).

3. **Betaalsysteem**
   Status: niet gestart — pricing bestaat alleen als tekst in `app/static/app.jsx`, geen Stripe/Mollie/subscription-backend, geen facturatie.
   Geschat: 2–4 weken voor een basale Stripe/Mollie-integratie met subscriptions + facturen.
   Nodig: keuze payment provider, backend billing-model (metered per workflow? flat per tier?), koppeling aan module-access.

4. **Verzekering**
   Status: buiten de codebase — puur zakelijk/verzekeringstechnisch, niet te verifiëren vanuit de repo.
   Geschat: n.v.t. (geen engineering).
   Nodig: input van Dennis / verzekeringsadviseur.

5. **Website-update**
   Status: marketing-copy en pricing in `app/static/app.jsx` zijn ongewijzigd sinds de systeemanalyse van 2026-05-15. Geen social proof, geen cases/testimonials in de code (bevestigd: "GEEN DATA" in analyse §5). **Nieuw op 2026-08-11:** de live `valqeron.com` serveert deze marketing-HTML wel, maar via een andere host (Apache/shared hosting) dan de FastAPI-backend uit deze repo — `/health` en `/api/status` geven daar 404. Bezoekers zien dus alleen statische marketing-copy; er zit geen werkend platform achter. Zie ook de nieuwe infra-rij in sectie 2 en het risico in sectie 5.
   Geschat: afhankelijk van scope (nieuwe copy, cases toevoegen, outbound-CTA's) — plus uitzoeken hoe de statische site en de FastAPI-backend zich tot elkaar verhouden, voordat er inhoudelijk werk aan de copy zinvol is.
   Nodig: content/beslissing over wat er moet veranderen; eerst duidelijkheid over de deploy-situatie (zie sectie 5, risico "Productie-infra onbereikbaar").

**Ook noemenswaardig (niet in oorspronkelijke lijst, wel blokkerend):**
- Geen job queue — blokkeert async workflows zoals de Outbound Engine (email-sequenties vereisen achtergrondverwerking).

---

## 5. Risico's

| Risico | Ernst | Huidig risico | Mitigatie |
|---|---|---|---|
| Geen AVG-anonimisering vóór LLM-calls | Kritiek | Documenten/leads met persoonsgegevens gaan ongefilterd naar OpenAI | Presidio-laag inbouwen vóór elke externe LLM-call (zie actie 1) |
| Geen verwerkersovereenkomst | Kritiek (juridisch) | Platform verwerkt klantdata zonder vastgelegde verwerkersafspraken | DPA opstellen met sub-verwerkers (OpenAI, Microsoft) benoemd |
| Geen billing-backend | Hoog (business) | Sales kan wel tekenen, maar er is geen geautomatiseerde facturatie/incasso | Payment-integratie (actie 3) |
| Geen job queue | Hoog | Alles synchroon; blokkeert schaalbare outbound-email-sequenties en lange workflow-runs | Celery/RQ + Redis (Redis is al aanwezig) of APScheduler |
| Geen unsubscribe/suppression bij outbound | Kritiek (compliance, zodra outbound live gaat) | `outbound_suppression_list`-tabel bestaat al (M1c) maar er is geen sending-laag die 'm gebruikt | Suppression-check verplicht maken vóór elke send zodra ESP gekoppeld wordt |
| **Productie-infra onbereikbaar** | **Hoog (business)** | Herbevestigd op 2026-08-19 (zie sectie 6): `api.valqeron.com` en `compliance.valqeron.com` (beide → 165.22.204.23) beantwoorden nog steeds geen enkele TCP-connect op poort 22 en geven een timeout op HTTP(S) — geen bewijs dat de FastAPI-backend uit deze repo ergens publiek draait. Vanuit deze omgeving is geen directe toegang (geen `doctl`, geen DO-token, SSH-key krijgt geen verbinding) om dit zelf op te lossen. De live `valqeron.com`/`app.valqeron.com` (ander IP, Apache/shared hosting) serveert alleen de statische marketing-HTML; `/health` en `/api/status` geven daar 404. Als er nu een demo of verkoopgesprek zou plaatsvinden, is er niets werkends om te tonen buiten lokaal | Dennis volgt `DEPLOY_RECOVERY.md` (repo-root, 2026-08-19) via de DigitalOcean-webconsole: droplet-status/power-state checken, recovery console i.p.v. SSH, services herstarten, en de DigitalOcean Cloud Firewall controleren (aparte netwerklaag die dit "silent timeout" kan veroorzaken) |
| Geen payment/CRM/email/calendar-integraties | Hoog (voor Outbound Engine) | Outbound Engine heeft alleen een datamodel, geen ESP/CRM/calendar-koppeling | Zie `docs/analyse/valqeron-systeemanalyse-2026-05-15.md` §10-12 voor het volledige gat-overzicht |

---

## 6. Recente wijzigingen log

*(Nieuwste bovenaan. Voeg na elke sessie een regel toe.)*

- **2026-08-21** — De ongecommitte testfixes van 2026-08-11 (zie regel hieronder) waren tot nu toe alleen lokaal aanwezig in de working tree; gecommit als `aca0bb3` ("Fix testsuite: mock OpenAI calls, add dummy CI key, correct stale tests") en gepusht naar `origin/main`. Root causes samengevat in de commitmessage: (1) geen OpenAI-mocking → nondeterministische/netwerkafhankelijke workflow-tests, opgelost met een autouse fixture in `tests/conftest.py` plus een `mock_openai_response()`-override voor tests die op specifieke LLM-inhoud assertsen; (2) CI had geen `OPENAI_API_KEY`, waardoor workflow-implementaties de "niet geconfigureerd"-degraded-path namen — opgelost met een expliciet gelabelde dummy (niet-geheime) key in `.github/workflows/ci.yml`; (3) 4 tests met verouderde assertions; (4) 1 test met DB-pollutie tussen lokale testruns (UNIQUE-constraint op `stored_name`), opgelost met een idempotente `ensure_document()`-helper; (5) 1 test die impliciet op ambient DB-state leunde. Push werd initieel geweigerd door GitHub ("refusing to allow a Personal Access Token to create or update workflow ... without `workflow` scope") omdat de commit `.github/workflows/ci.yml` wijzigt — opgelost door de PAT-scope uit te breiden. Na de commit `pytest -q -m "not codex"` tweemaal achtereen gedraaid: 62 tests, beide keren exit code 0, working tree voor tracked files schoon (`git status --short` zonder gewijzigde/staged bestanden, los van bestaande untracked bestanden zoals lokale test-uploads in `uploaded_documents/`).
- **2026-08-19** — Prioriteit-1-onderzoek naar de onbereikbare productieserver (165.22.204.23): vanuit deze omgeving is er geen enkele toegang om zelf te diagnosticeren of herstellen — geen `doctl` geïnstalleerd, geen DigitalOcean API-token gevonden in `.env`/`.env.example`, en de enige lokale SSH-key gaf `Operation timed out` op poort 22 (geen verbinding, dus ook niet te bepalen of de key geautoriseerd zou zijn). Herbevestigd via `curl -I` op `https://compliance.valqeron.com/` en `https://api.valqeron.com/health`: beide timeouten na 10s zonder enige respons — zelfde beeld als de externe test van 2026-08-11, geen verandering. Omdat directe toegang ontbreekt, is er een zelfstandig uit te voeren herstelplan geschreven: `DEPLOY_RECOVERY.md` (repo-root) — stappenplan voor Dennis via de DigitalOcean-webconsole (droplet-status checken, recovery console i.p.v. SSH, `systemctl`/`nginx -t`/poort-checks, service herstarten, en het checken van de DigitalOcean Cloud Firewall als aparte netwerklaag die dit type "silent timeout zonder RST" kan veroorzaken).
- **2026-08-11** — Alle 6 falende tests + de kapotte `sales_lead_qualification`-importtest gefixt (root causes: 4 stale/verouderde tests, 1 test-DB-pollutieprobleem, 1 test die impliciet op ambient DB-state leunde — geen enkele workflow zelf bleek een echte logicabug te hebben). OpenAI-calls in de hele testsuite zijn nu gemockt (autouse fixture in `tests/conftest.py`); CI heeft een dummy `OPENAI_API_KEY` zodat de workflow-tests daar ook meedraaien. Onafhankelijk extern geverifieerd: 165.22.204.23 (`api.`/`compliance.valqeron.com`) is niet bereikbaar op geen enkele geteste poort; de live `valqeron.com` blijkt een andere, aparte Apache-host die alleen statische marketing-HTML serveert, niet de FastAPI-backend.
- **2026-08-11** — CLAUDE.md aangemaakt als levend statusdocument, geverifieerd tegen actuele code (pricing, infra, workflows, tests, outbound-engine-stand).
- **2026-06-29** — Outbound Engine M1a–M1c: 9 tabellen (companies, prospects, campaigns, touchpoints, replies, reply_classifications, scheduled_calls, region_policies, suppression_list), schemas, Alembic-migraties, 17 tests. Alleen datamodel — geen routers/services.
- **2026-05-15** — Security fixes + performance-optimalisaties. Zelfde dag: systeemanalyse-document opgesteld (`docs/analyse/valqeron-systeemanalyse-2026-05-15.md`), basis voor dit document.
- **2026-05-13** — Alle 9 (van de 10) workflows geüpgraded naar echte AI-implementaties (van stub naar OpenAI-calls).
- **2026-05-12** — Platform-optimalisaties: security, governance, deployment.
- **2026-04-12** — Multi-tenant demo-state flow voor tenant 1 en tenant 2 (portal reset, smoke tests, tenant-isolatie-tests).
- **2026-04-03/05** — Workflow-registry genormaliseerd; individuele workflow-implementaties (sales, customer support, document knowledge, quote/contract, meeting agenda) gebouwd.

---

## 7. Volgende stap

Testsuite is gefixt (sectie 3/6) — dat blocker is weg. De meest urgente open vraag is nu **niet** engineering, maar de productie-infra: er is momenteel geen extern bewijs dat het platform ergens publiek draait (zie het risico "Productie-infra onbereikbaar" in sectie 5), en vanuit deze coding-omgeving is er geen toegang om dit zelf te diagnosticeren of herstellen (geen `doctl`, geen DO-token, SSH-key kreeg geen verbinding — zie sectie 6, 2026-08-19). Dat is business-kritiek als er op korte termijn een demo of verkoopgesprek gepland staat.

1. **Actie ligt nu bij Dennis:** volg `DEPLOY_RECOVERY.md` (repo-root) via de DigitalOcean-webconsole — droplet-power-state checken, recovery console gebruiken (SSH werkt niet van buitenaf), services herstarten, en de DigitalOcean Cloud Firewall checken (aparte netwerklaag die dit type "silent timeout zonder RST" kan verklaren).
2. Meld het resultaat terug (werkt `curl -I https://compliance.valqeron.com/` weer, en wat bleek de oorzaak: uitgezette droplet, gecrashte service, of firewall-regel?) zodat sectie 2 van dit document een eerlijke "live" status kan tonen in plaats van "onbevestigd", en `nginx/valqeron.conf`/`systemd/valqeron.service` (of de daadwerkelijke huidige hostingpartij) consistent gemaakt kunnen worden met de werkelijke situatie.

Daarna pas door naar prioriteit 1 uit sectie 4 (AVG-anonimiseringslaag) — dat blijft het enige kritieke punt dat zuiver engineering-werk is en zonder externe afhankelijkheden (jurist, verzekeraar, payment-provider-keuze, hosting-uitzoekwerk) gestart kan worden.
