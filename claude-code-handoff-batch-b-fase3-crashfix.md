# Handoff voor Claude Code — Batch B afronden: HQ inrichten (fase 3) + worker-crash oplossen

Context: jouw rapport van 20 sep 2026 (CLAUDE.md sectie 6/7, HEAD `7ab51a4`), `claude/executieplan-fase-0-1.md` (Batch B). Goed werk: de diagnose (healthcheck-kill van de uvicorn-supervisor, 6 s na model-load, geen OOM en geen segfault) corrigeert mijn eerdere hypothesen, en de constatering dat productie op Python 3.12.3 draait terwijl CI/lokaal 3.9 gebruikt is nuttig.

**Deze hand-off geldt pas nadat Dennis in zijn prompt schrijft dat hij akkoord is met de keuzes hieronder.** Die keuzes zijn een advies van Cowork; Dennis heeft ze bevestigd of aangepast in zijn bericht. Wijkt zijn bericht af van dit bestand, dan gaat zijn bericht voor.

Standaardafspraken gelden: begin met `git status`/`git diff` (drift-check), commit snel na groene tests, en eindig met testeisen en een CLAUDE.md-update. **Twee losse commits**, deel 1 vóór deel 2, zodat elk apart teruggedraaid kan worden.

---

## Keuzes (advies Cowork, te bevestigen door Dennis)

1. **HQ = org 1 "Valqeron".** Bevestigd door jouw inventarisatie: alleen eigen/testdata, 0 klantdata, alleen Valqeron-gebruikers.
2. **`admin` (onbekend wachtwoord) wordt gedeactiveerd, niet verwijderd** (`is_active=False`; omkeerbaar). Een account met de voorspelbare naam `admin` en een onbekend wachtwoord is de zwakste schakel in wat tenant 0 wordt.
3. **Nog géén super-admin.** Dit wijkt af van jouw voorstel en is bewust. Reden: fase 3 heeft `is_super_admin` niet nodig (modules toekennen en `.env` zetten gaan via een script/serverconfiguratie), maar een super-admin heeft nu al cross-tenant macht via bestaande code (`get_org_scoped_org`-uitzondering, `POST /organizations`, `POST /users` met `organization_id`) en er is nog geen MFA (dat komt in Batch E). De `is_super_admin`-vlag komt daarom in Batch E, samen met MFA. Zet hem dus **nu op niemand**.
4. **Crash-oplossing: opties 1 + 2 + 3 uit jouw rapport gecombineerd:** `--workers 1`, `--timeout-worker-healthcheck 60` (vangnet), en warm-up van de modellen bij opstart. Redenering: 1 vCPU en 1,97 GB RAM, dus een tweede worker geeft geen parallelisme maar verdubbelt het geheugen. Een grotere droplet (optie 4) blijft een open beslissing van Dennis; jouw meting na deze fix levert daar de cijfers voor.

---

## Deel 1 — HQ inrichten (org 1), commit 1

1. **Script:** nieuw, klein, idempotent, in de stijl van `scripts/seed_modules.py`, bijvoorbeeld `scripts/setup_hq_tenant.py` met `--organization-id` en een **`--dry-run`** die eerst toont wat er zou veranderen. Geen geheimen in het script; het mag in git.
   - Zet de 6 ontbrekende `TenantModule`-rijen actief (`customer_support_ai`, `hr_recruitment_ai`, `invoice_processing_ai`, `marketing_automation_ai`, `meeting_agenda_assistant`, `quote_contract_generator`), zodat org 1 op **11 van 11** staat. Gebruik de bestaande `BASE_MODULES`/`TenantModule`; raak geen andere organisatie aan; tweede run wijzigt niets.
   - Deactiveer user `admin` in org 1 (geen delete). **Controleer eerst** met een zoekopdracht in repo, `scripts/`, tests, `.env.example`, CI-workflows en docs of ergens de productielogin `admin` wordt gebruikt (smoke-scripts, CI, monitoring). Wordt hij ergens gebruikt: stop en rapporteer, niet zelf oplossen.
   - Elke wijziging schrijft een auditregel via `create_audit_log` (`performed_by="system"`).
   - Zet **geen** `is_super_admin` en pas de organisatienaam niet aan.
2. **Config-toegang:** `HQ_ORGANIZATION_ID` lezen in de bestaande config-module: niet gezet → `None`; geldig getal → `int`; ongeldige waarde → duidelijke fout. Unit-tests voor die drie gevallen. Nog nergens gebruiken; dat komt in Batch E/F. Voeg de sleutel toe aan `.env.example` zonder echte waarde.
3. **Productie:** na een groene CI en Deploy: draai het script eerst met `--dry-run`, dan echt. Zet `HQ_ORGANIZATION_ID=1` in de productie-`.env` (niet in git). De service hoeft hiervoor niet apart herstart te worden als deel 2 direct volgt; herstart anders één keer.
4. **Verificatie (echt, niet aannemen):**
   - `POST /login` als `dennis_admin` tegen `https://api.valqeron.com` → slaagt.
   - `POST /login` als `admin` → mislukt (401/403).
   - Org 1 toont 11 actieve modules (via het bestaande modules-endpoint of een read-only query).
   - `GET /audit/verify` voor org 1 → `valid`, `chain_rows_checked` ≥ 2 (marker + de auditregels van het script), `legacy_rows_checked` ≥ 1.
   - Org 2 en de andere gebruikers zijn ongewijzigd (kort tellen).

## Deel 2 — Worker-crash oplossen, commit 2

1. **systemd-unit** (`systemd/valqeron.service`): `--workers 1` en `--timeout-worker-healthcheck 60`. Werkt de vlag niet samen met `--workers 1`, laat hem weg en meld dat. **Controleer hoe een wijziging aan de unit-file op de server komt** (kopieert `scripts/deploy.sh` hem en doet `daemon-reload`, of niet?); neem dat niet aan. Als de deploy de unit niet synchroniseert: doe het handmatig en noteer de procedure in CLAUDE.md.
2. **Warm-up bij opstart:** laad de Presidio-analyzer en spaCy-modellen in de FastAPI-lifespan via de bestaande init-functie, vóór de app verkeer accepteert. Regels:
   - Faalt de warm-up, dan **niet crashen of in een loop herstarten**: log een duidelijke ERROR en start toch; het bestaande fail-closed-gedrag op het requestpad blijft ongewijzigd.
   - **Niet in tests en CI:** achter een aan/uit-instelling die standaard uit staat en alleen in productie aan gaat (bijvoorbeeld een env-variabele). De testsuite mag niet trager worden of modellen laden. Voeg een test toe dat de warm-up bij "uit" niets laadt en bij "aan" de init-functie precies één keer aanroept (mock).
3. **deploy.sh en deploy.yml:** de start duurt nu waarschijnlijk 20–40 s door de model-load op 1 vCPU. Zorg dat de health-check na de restart **met retry** wacht (bijvoorbeeld tot 90 s), zodat een normale start niet als mislukte deploy telt en de rollback-/foutlogica niet onterecht afgaat. Meet en rapporteer het venster waarin nginx 502 geeft tijdens een deploy.
4. **Acceptatiemeting (herhaal jouw fase-2-opzet):** na de deploy, met dezelfde sampler (1 s-interval): koude start tot `/health` ok; daarna 6 opeenvolgende PII-verwerkende workflowruns op de demo-tenant (org 2). Verwacht: geen enkele kill in `journalctl`, geen 502, eerste request niet merkbaar trager dan de rest, resident geheugen van het ene proces, beschikbaar RAM en swapgebruik. Meet ook hoe lang `/health` en één gewoon endpoint duren **terwijl** een workflowrun bezig is (1 worker: blokkeert native code de andere requests?).
5. **Stopvoorwaarde:** wordt er na de fix toch een proces gekilld, blijft beschikbaar RAM structureel onder ~100 MB, of blokkeren gewone requests seconden lang tijdens een run: **stop, rapporteer de getallen en probeer geen extra varianten.** Of de droplet groter wordt is Dennis' beslissing en kost geld.

## Niet doen
- Geen super-admin aanmaken of `is_super_admin` zetten. Geen accounts verwijderen. Geen wachtwoord(hash)s of klantinhoud in output of logs; wachtwoorden die je genereert rechtstreeks aan Dennis, nooit in git.
- Het spaCy-model niet wijzigen (eerder door Dennis vastgesteld ontwerp), geen Python-upgrade, geen wijziging aan CI-Pythonversie in deze taak; dat laatste komt als apart punt terug.
- Geen ISO Cert-demo-org aanmaken (aparte opdracht).
- Niet stilzwijgend afwijken van dit bestand; als iets niet klopt, stoppen en terugkoppelen.

## Afsluiting (verplicht)
1. **Testeisen:** volledige suite groen lokaal én in CI (`pytest -q -m "not codex"`, huidig 122; noteer het nieuwe totaal), inclusief de nieuwe tests voor de config-toegang en de warm-up-schakelaar. Na elke deploy: CI én Deploy groen via de GitHub Actions-API controleren. De productieverificaties uit deel 1 en de acceptatiemeting uit deel 2 met echte uitvoer vastleggen.
2. **CLAUDE.md bijwerken:** sectie 5 (crash-risicorij: opgelost of niet, met de meetgetallen; nieuwe risicorij "productie Python 3.12 versus CI/lokaal 3.9", nog niet aangepakt), sectie 6 (nieuwe regels per commit met hashes en de echte uitvoer), sectie 7 (volgende stap: Batch C; Batch D pas na Dennis' melding). Verifieer na de commit dat de CLAUDE.md-wijziging blijft staan (drift-patroon).
3. **Rapporteer aan Dennis** in het kort: wat is gewijzigd, de meetgetallen vóór en na, en of een grotere droplet nog nodig lijkt.
