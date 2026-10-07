# Handoff voor Claude Code — Batch D: Sentry voor backend en frontend (zonder persoonsgegevens) + `/health` met build-sha

Context: `claude/executieplan-fase-0-1.md` (Batch D, taak 1.7). Batch A t/m C zijn klaar. Waarom nu: de volgende batches (E: MFA en control plane, F: provisioning) bouwen op productie zonder staging, en fouten worden tot nu toe alleen met de hand gevonden (ook de CSP-bug werd zo ontdekt). Sentry moet fouten zichtbaar maken **zonder dat er klantinhoud of persoonsgegevens naar een derde partij gaan**: Valqeron is verwerker, en Sentry wordt een sub-verwerker. Dat is de hoofdeis van deze batch; de rest is bijzaak.

**Start pas als Dennis in zijn prompt beide DSN's meegeeft** (backend-project en frontend-project, EU-regio). Een DSN is geen wachtwoord en mag in de chat staan, maar de backend-DSN komt nooit in git.

Standaardafspraken: begin met `git status`/`git diff` in beide repo's (drift-check), commit snel na groene tests, eindig met testeisen en CLAUDE.md-update. **Twee losse delen in deze volgorde:** eerst deel 1 (backend + nginx-CSP), dan deel 2 (frontend). De CSP-wijziging moet live zijn vóórdat de frontend met Sentry uitkomt, anders blokkeert de browser de meldingen.

Geheugenzorg: de droplet heeft weinig vrij RAM (mediaan 118 MB bij 1 worker; een grotere droplet is nog een open beslissing van Dennis). `sentry-sdk` kost geheugen. Meet het verschil (zie deel 1, punt 8) en stop als het niet past.

---

## Deel 1 — Backend (repo `ai-governance-os`)

1. **Dependency.** Voeg `sentry-sdk[fastapi]` toe aan `requirements.txt`, met een exacte versie die zowel op Python 3.9 (CI/lokaal) als 3.12 (productie) installeert. Controleer beide.
2. **Nieuwe module `app/core/observability.py`** met `init_sentry()`, aan te roepen in `app/main.py` direct na `load_dotenv()` en vóór het aanmaken van de app. Doet niets als `SENTRY_DSN` leeg of afwezig is (tests, CI en lokaal sturen dus nooit iets). Instellingen, allemaal verplicht:
   - `send_default_pii=False`
   - `max_request_body_size="never"` (request-bodies bevatten klanttekst voor de workflows)
   - `include_local_variables=False` (frame-variabelen kunnen klanttekst bevatten)
   - `traces_sample_rate=0`, geen profiling, geen performance-metingen: alleen fouten
   - `max_breadcrumbs=0` (log- en SQL-regels als breadcrumbs kunnen inhoud bevatten)
   - `environment` uit `ENVIRONMENT`, `release` = de build-sha uit punt 4
   - **Integraties nalopen:** print bij het bouwen welke integraties automatisch aan staan (Starlette/FastAPI, logging, SQLAlchemy, httpx/requests, OpenAI, enz.). De `LoggingIntegration` zet je op `level=None, event_level=None` (log-regels worden geen events en geen breadcrumbs; de bestaande global handler logt `exc` als tekst). Zet elke integratie uit of in de veilige stand die prompts, SQL-parameters of response-bodies zou kunnen meesturen (met name de OpenAI-integratie: geen prompts).
   - `before_send`: verwijder `request.data`, `request.cookies`, `request.headers`, `request.query_string`, `user`, `extra` en `contexts` behalve de technische runtime-contexten; kort `exception.values[].value` in tot maximaal 200 tekens en maskeer e-mailadressen en lange cijferreeksen met een eenvoudige regex. Wat er overblijft is exceptietype, bestandsnaam en functienaam.
   - Optioneel en alleen als het zonder risico voor het gedrag kan: tag `organization_id` (een gewoon getal, geen persoonsgegeven) zodat fouten per tenant te filteren zijn. Als het de auth-afhankelijkheid moet wijzigen: sla het over en noteer het.
3. **Global exception handler.** `app/main.py` heeft `@app.exception_handler(Exception)`, en dat kan ertoe leiden dat Sentry de fout niet ziet. **Bewijs met een test** of de fout gecaptured wordt; zo niet, roep `sentry_sdk.capture_exception(exc)` aan in de handler (zonder dubbele events en zonder het antwoord aan de klant te veranderen: dat blijft `internal_server_error`).
4. **Build-sha en `/health`.** `scripts/deploy.sh` schrijft na de `git pull` (en vóór de service-restart) de korte sha naar `/opt/valqeron/BUILD_SHA` (niet in git; zet het in `.gitignore`; schrijf hem ook opnieuw bij een rollback). De app leest dat bestand één keer bij opstart, met de fallback `"unknown"`. `/health` blijft `{"status": "ok", ...}` teruggeven (deploy.sh en `deploy.yml` parsen dat veld) en krijgt er `build_sha` bij. Lees eerst `app/api/health.py`; verander niets aan wat het nu controleert. Controleer dat de service-gebruiker het bestand kan lezen (`ProtectSystem=strict`, gebruiker `www-data`).
5. **`.env.example`:** voeg `SENTRY_DSN=` toe, leeg, met een korte comment. De echte backend-DSN zet je in de productie-`.env` (niet in git).
6. **Tests** (nieuw bestand, bijvoorbeeld `tests/test_observability.py`), zonder netwerk, met een nep-transport:
   - Zonder `SENTRY_DSN` wordt de SDK niet actief.
   - Een POST met een body die `test.person@example.com` bevat, naar een route die een fout gooit, geeft een event waarin **die string nergens voorkomt** (serialiseer het hele event naar JSON en zoek erin), ook niet in stackframes, request of exceptietekst.
   - `before_send` verwijdert cookies, `authorization`-header, query string en `user`.
   - `/health` bevat `status: "ok"` én `build_sha`.
   - De global handler geeft nog steeds de bestaande 500-respons.
   - Alle bestaande tests blijven groen (nu 147; noteer het nieuwe totaal).
7. **Deploy** via de normale CI en Deploy; controleer beide via de GitHub Actions-API. Zet de backend-DSN in de productie-`.env` vóór of tijdens die deploy (via SSH, zoals eerder). Denk aan het ~25 s-502-venster bij een herstart.
8. **Geheugenmeting:** resident geheugen van het uvicorn-proces en beschikbaar RAM vóór en na (zelfde sampler als bij Batch B, na koude start en na 2 PII-runs op de demo-tenant). **Stopvoorwaarde:** blijft beschikbaar RAM structureel onder ~100 MB of wordt er een proces gekilld: zet `SENTRY_DSN` terug leeg, herstart, en rapporteer de getallen aan Dennis. Niet zelf varianten proberen.
9. **Live test met een script**, geen endpoint: `scripts/sentry_smoke.py`, op de server met de productie-omgeving, dat één testfout stuurt met een nep-e-mailadres in het bericht en in een lokale variabele, met de tag `smoke_test`, en `flush()` aanroept. Stuur maximaal één testevent. Meld Dennis dat hij het event in Sentry moet openen en controleren dat het nep-adres nergens zichtbaar is (hij stuurt jou een screenshot).
10. **nginx-CSP voor de frontend:** in `nginx/sites/app.valqeron.com.conf` moet `connect-src` **precies één host** erbij krijgen: de Sentry-ingest-host uit de frontend-DSN (bijvoorbeeld `https://o<id>.ingest.de.sentry.io`), geen wildcard. Doe dit als eigen commit en laat het live komen vóór deel 2 (deploy.sh synct nginx en herlaadt). Verifieer de nieuwe header op productie met een echte fetch van de headers én, na deel 2, met de browsercheck.

## Deel 2 — Frontend (repo `ai-governance-frontend`)

1. **Dependency** `@sentry/react`, exacte versie, volgens de huidige Sentry-documentatie voor React 19 (let op de manier om fouten van `createRoot` te vangen).
2. **Init in `src/main.tsx`**, vóór het renderen, alleen als `import.meta.env.VITE_SENTRY_DSN` gezet is (lokale dev stuurt dus niets). Instellingen, allemaal verplicht: `sendDefaultPii: false`, **geen Session Replay** (dat zou schermen met klantdata opnemen), geen feedback-widget, geen tracing, `maxBreadcrumbs: 0`, `environment: 'production'`, `release` = `VITE_BUILD_SHA`. `beforeSend` als pure functie (bijvoorbeeld in `src/lib/sentryScrub.ts`): verwijder `request`, `user`, `extra`; kort berichten in tot 200 tekens en maskeer e-mailadressen. Geen zichtbare UI-wijziging (geen foutscherm toevoegen zonder overleg).
3. **Build-omgeving.** Pas `.github/workflows/ci.yml` aan zodat de build-stap `VITE_SENTRY_DSN: ${{ vars.VITE_SENTRY_DSN }}` en `VITE_BUILD_SHA: ${{ github.sha }}` krijgt. Zet de GitHub-variabele `VITE_SENTRY_DSN` in de frontend-repo met `gh variable set` (`gh` is opnieuw ingelogd) op de frontend-DSN uit Dennis' prompt. Zet de DSN **niet** in `.env.production`. Controleer dat `deploy.yml` en `scripts/verify-deploy.mjs` blijven werken nu de bundelnaam bij elke build verandert (de verwachte bundel komt uit het artifact).
4. **Test** (de eerste frontendtest, bewust klein): de scrub-functie is puur; zet de kleinste testopzet neer (bijvoorbeeld vitest) alleen daarvoor en draai die als aparte stap in CI. Testcases: een e-mailadres in het bericht wordt gemaskeerd, `request` en `user` verdwijnen, een lang bericht wordt ingekort. Verder geen testuitbreiding in deze batch.
5. **Live test op productie na de deploy**, met de bestaande headless browsercheck: laad `https://app.valqeron.com/`, en veroorzaak een onafgevangen fout via `page.evaluate(() => setTimeout(() => { throw new Error('sentry-frontend-smoke-test') }, 0))`. Verwacht: een netwerkverzoek naar de Sentry-host met een succesvolle respons, **geen CSP-violations**, en de normale controle van `verify-deploy.mjs` blijft slagen. Maximaal één testfout. Niet inloggen met demo-credentials zonder Dennis' toestemming.
6. **Source maps: niet in deze batch.** Zonder ze zijn stacktraces geminimaliseerd; uploaden vraagt een Sentry-auth-token als GitHub-secret. Noteer dat als optionele vervolgstap in CLAUDE.md; Dennis besluit later.

## Niet doen
- Geen Session Replay, Performance, Profiling of user feedback. Geen `send_default_pii=True`. Geen breadcrumbs. Geen request-bodies. Geen frame-variabelen.
- Geen backend-DSN, geen Sentry-auth-token en geen andere geheimen in git of in CLAUDE.md. De frontend-DSN staat in de GitHub-variabele, niet in de repo.
- Geen wildcard in de CSP (`*.sentry.io`), alleen de ene ingest-host.
- Niet meer dan één testevent per kant sturen (quota) en niet herhalen zonder reden.
- Niet stilzwijgend afwijken; als iets in de praktijk niet klopt (bijvoorbeeld een integratie die je niet veilig krijgt, of de handler die niet te vangen is), stoppen en terugkoppelen.

## Afsluiting (verplicht)
1. **Testeisen:** backend-suite groen lokaal én in CI met de nieuwe tests (inclusief de test dat een nep-e-mailadres nergens in het event voorkomt); frontend-CI groen (build, de nieuwe scrub-test); CI én Deploy in beide repo's groen via de Actions-API; `/health` toont `build_sha` en `status: ok`; twee live testevents (backend-script en frontend-browsercheck) zijn in Sentry aangekomen, en Dennis heeft bevestigd dat er geen persoonsgegevens in staan; geheugenmeting vóór en na is gerapporteerd.
2. **CLAUDE.md bijwerken** (`ai-governance-os`): sectie 2/4 (Sentry-configuratie, wat wel en niet wordt gestuurd, waar de DSN's staan, build-sha-mechanisme), sectie 5 (nieuwe risicorij: Sentry is sub-verwerker en moet op de DPA-lijst; source maps ontbreken; eventuele restrisico's zoals exceptietekst), sectie 6 (regel per commit, met hashes, run-ids en de geheugengetallen), sectie 7 (volgende stap: Batch E; eerst de droplet-beslissing van Dennis). Verifieer na de commit dat de wijziging blijft staan (drift-patroon).
3. **Rapporteer aan Dennis** kort: wat is gewijzigd, de geheugengetallen, en wat hij in Sentry moet controleren.
