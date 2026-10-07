# Handoff voor Claude Code — Batch C: `ai-governance-frontend` onder git + CI/CD naar `app.valqeron.com`

Context: `claude/dogfood-portal-onboarding-plan.md` (taak 1.8) en `claude/executieplan-fase-0-1.md` (Batch C) in het projectdocument. Het klantportaal (`ai-governance-frontend`, Vite + React 19 + TypeScript) is handmatig gebouwd en gekopieerd naar de server (zie `claude-code-handoff-portal-deploy.md`, Track A stap 2) en heeft **geen git-repo en geen CI/CD**. Elke wijziging is handwerk zonder terugvalpunt. Alle latere batches (control-plane-tab, supportverzoek-slice) bouwen in dit portaal, dus dit moet eerst netjes staan. Batch C is onafhankelijk van Batch B en mag parallel of ervoor.

Standaardafspraken blijven gelden: testeisen en CLAUDE.md-update onderaan. Begin met een read-only inventarisatie voordat je iets pusht.

---

## Wat Dennis zelf doet (jij kunt dit niet, wacht op zijn melding)

1. Een **private** GitHub-repo aanmaken onder `thecalmdiscipline-hub`, naam `ai-governance-frontend` (leeg, zonder README/license/.gitignore, om een merge-conflict bij de eerste push te voorkomen).
2. In die nieuwe repo onder Settings → Secrets and variables → Actions dezelfde deployconfiguratie zetten als in `ai-governance-os`: secret `DEPLOY_SSH_KEY`, variabelen `DEPLOY_HOST` en `DEPLOY_USER`. Gebruik bij voorkeur een **aparte deploy-key** met alleen rechten op `/opt/valqeron-frontend` (zie stap 4), niet de sleutel van de backend.

Als de repo of de secrets ontbreken: doe alles t/m stap 3 lokaal, stop bij de eerste push en meld aan Dennis wat er nog nodig is.

## Stap 1 — Lokale inventarisatie (read-only)

1. In de map `ai-governance-frontend`: `git status` moet bevestigen dat er geen `.git` is (`git rev-parse` faalt). Maak niets stuk.
2. Controleer `.gitignore`: bevat `node_modules`, `dist`, `*.local`. **`.env` en `.env.*` staan er niet in.** Bekijk de inhoud van `.env` en `.env.production` (`.env.production` bevat volgens onze info alleen `VITE_API_BASE=https://api.valqeron.com`, dat is geen geheim en mag in git; controleer dat `.env` **geen** geheimen bevat: API-sleutels, tokens, wachtwoorden). Alles wat geheim is: niet committen, in `.gitignore` zetten en aan Dennis melden. Voeg `.env` (lokale dev) desnoods toe aan `.gitignore` en laat `.env.production` bewust wel tracken, met een korte opmerking in de README.
3. Zoek in `src/` en de rest van de map naar hardgecodeerde geheimen of credentials (`grep -R -n -i -E "password|secret|token|api[_-]?key|Bearer "`); het bestand `DEMO_USERS.md` (indien aanwezig) bevat mogelijk demo-wachtwoorden: **niet in git zetten** zonder dat Dennis dat akkoord vindt; zet het in `.gitignore` of laat het weg uit de eerste commit en meld het.
4. **Vergelijk de lokale build met wat live staat.** Draai `npm ci && npm run build` lokaal, haal `https://app.valqeron.com/` op en vergelijk de bestandsnamen/hashes van de assets (`/assets/index-*.js`, `*.css`) met de lokale `dist/`. Als de live-versie afwijkt van de lokale bronnen (iemand heeft handmatig iets anders gedeployed): **stop en rapporteer** in plaats van de live-versie te overschrijven met iets anders.
5. Draai `npm run lint` en noteer de uitkomst. Falende lint is geen blokkade voor de eerste commit, maar de CI-stap voor lint alleen aanzetten als het schoon is; anders lint als niet-blokkerende stap markeren en de fouten in CLAUDE.md noteren.

## Stap 2 — Git initialiseren en eerste commit

1. `git init -b main`, controleer met `git status` **precies** wat er wordt toegevoegd (geen `dist/`, geen `node_modules/`, geen geheimen), dan één eerste commit ("Initial import of ai-governance-frontend, as deployed on 2026-09-18"). Wees expliciet met `git add <paden>` in plaats van blind `git add .`.
2. Voeg een korte `README.md` toe: wat het is, `npm ci`, `npm run dev`, `npm run build`, waar het wordt gedeployed (`app.valqeron.com`, `/opt/valqeron-frontend/dist`), en dat `VITE_API_BASE` bij build wordt ingebakken.
3. Zet de remote pas op de repo van Dennis en push naar `main` **nadat** hij bevestigd heeft dat die bestaat en dat hij de secrets heeft gezet.

## Stap 3 — GitHub Actions: CI

Nieuw bestand `.github/workflows/ci.yml`, op `push` en `pull_request` naar `main`:

1. `actions/checkout`, `actions/setup-node` (Node-versie: kijk wat lokaal gebruikt wordt en pin die; Vite 8 vereist een recente Node), `npm ci` (met npm-cache).
2. `npm run lint` (zie stap 1.5 over blokkerend of niet) en `npm run build` (bevat `tsc -b`, dus typefouten breken de build).
3. Upload `dist/` als workflow-artifact, zodat de deploy-job hetzelfde artifact gebruikt en er niet opnieuw wordt gebouwd.

## Stap 4 — Server-voorbereiding en deploy-workflow

Spiegel het bestaande patroon van `ai-governance-os/.github/workflows/deploy.yml` (workflow_run na groene CI + `workflow_dispatch`, SSH-known_hosts uit `vars.DEPLOY_HOST`, sleutel uit `secrets.DEPLOY_SSH_KEY`).

**Server (eenmalig, via SSH; controleer eerst de huidige staat, neem niets aan):**
1. Bekijk eigenaar/rechten van `/opt/valqeron-frontend` en `/opt/valqeron-frontend/dist`, en wie nginx draait (`www-data`). Nginx moet de bestanden kunnen lezen; de deploy-gebruiker moet er kunnen schrijven.
2. Zet de deploy om naar **atomaire release-mappen**: `/opt/valqeron-frontend/releases/<git-sha>/` en een symlink `/opt/valqeron-frontend/dist` → actieve release. Nginx (`root /opt/valqeron-frontend/dist;`) hoeft niet te wijzigen; symlinks worden gevolgd. Omdat `dist` nu een **echte map** is, doe de migratie voorzichtig: verplaats de huidige `dist` eerst naar `releases/initial` (met `mv -n`, nooit `rm`), maak daarna de symlink, controleer `curl -I https://app.valqeron.com/` = 200 en de pagina rendert. Bewaar de laatste 5 releases; ruim oudere op (verwijderen op de server kan alleen als de deploy-gebruiker dat mag; anders laten staan en noteren).
3. Wisselen van release = `ln -sfn` naar een tijdelijke symlink en dan `mv -T` (atomair). Geen nginx-reload nodig voor statische files.
4. **Rollback** = symlink terugzetten naar de vorige release. Zet dat als `workflow_dispatch`-input of als klein script in de repo (`scripts/rollback.sh <sha>`), en documenteer het in de README.

**Deploy-workflow (`.github/workflows/deploy.yml`):**
1. Draait pas na groene CI op `main` (of handmatig). Download het `dist`-artifact van die CI-run.
2. `rsync -az --delete` naar `/opt/valqeron-frontend/releases/<sha>/` via SSH, dan de symlink-swap, dan opruimen van releases ouder dan de laatste 5.
3. **Post-deploy check met een echte headless browser** (Playwright/Chromium op de runner; les uit sectie 4/6 van CLAUDE.md: `curl -I` is niet genoeg). Test: `https://app.valqeron.com/` laadt, er is zichtbare content in `#root` (login-formulier), en de console bevat **geen CSP-violations of mislukte requests**. Faalt de check, dan draait de workflow automatisch de symlink terug naar de vorige release en faalt zichtbaar.
4. Daarna `curl` op `https://app.valqeron.com/` en `https://api.valqeron.com/health` (net als het backend-deploy-workflow).

## Stap 5 — Eerste echte CI/CD-run

1. Push naar `main`, controleer via de GitHub Actions-API dat **CI én Deploy groen zijn** (niet aannemen; zie CLAUDE.md sectie 5).
2. Bevestig op productie dat de actieve release de verwachte sha is en dat `app.valqeron.com` hetzelfde toont als vóór de migratie. Test in de browser (headless) het login-scherm; inloggen met een demo-user alleen als Dennis toestemming geeft voor het gebruiken van demo-credentials (die staan niet in git).
3. Test de rollback één keer bewust (terug naar `initial`, controleer, weer vooruit) zodat je weet dat hij werkt vóórdat je hem nodig hebt.

## Niet doen
- Geen geheimen, `node_modules`, `dist` of `DEMO_USERS.md` met wachtwoorden in git. Geen `.env`-bestanden overschrijven.
- Geen `rm -rf` op de server voor `/opt/valqeron-frontend`; verplaats met `mv -n`.
- Geen wijzigingen aan de portaal-functionaliteit in deze batch. Alleen versiebeheer, CI/CD en deploy. (De control-plane-tab en het supportverzoek komen in Batch E–G.)
- Geen wijzigingen aan `nginx/sites/app.valqeron.com.conf` in `ai-governance-os` tenzij strikt nodig; als het nodig blijkt, eerst terugkoppelen.
- Niet stilzwijgend afwijken; als iets niet klopt (bijv. de live-assets wijken af van de lokale build), stoppen en terugkoppelen.

## Afsluiting (verplicht)
1. **Testeisen:** `npm ci`, `npm run build` (tsc + vite) groen lokaal én in CI; lint-uitkomst gedocumenteerd; eerste deploy-run groen in de Actions-API; headless browser-check op productie geslaagd (rendert, geen CSP-violations); rollback één keer getest. Als er testtooling voor de frontend ontbreekt: noteer dat als risico in CLAUDE.md, bouw het niet in deze batch.
2. **CLAUDE.md bijwerken** (in `ai-governance-os`, het gedeelde geheugen): sectie 2/4 (frontend heeft nu eigen repo + pijplijn, met pad, release-structuur en rollback-procedure), sectie 5 (risico "frontend zonder git/CI" als opgelost markeren; eventuele nieuwe risico's), sectie 6 (nieuwe regel met repo-URL, commit-hashes, CI/Deploy-run-ids en de echte uitvoer van de browsercheck), sectie 7 (volgende stap: Batch D uit `claude/executieplan-fase-0-1.md`). Verifieer na de commit dat de wijziging blijft staan (drift-patroon).
