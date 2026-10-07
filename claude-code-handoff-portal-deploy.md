# Handoff voor Claude Code — klantportaal live zetten + AVG-anonimisering afronden

Twee onafhankelijke stukken werk staan klaar in de working tree en wachten op jou (shell/git/npm-toegang die de Cowork-sessie niet heeft). **Doe Track A eerst** — het is actief zichtbaar voor elke bezoeker van `app.valqeron.com` en is wat Dennis vandaag expliciet heeft gevraagd. Track B (Presidio/AVG-anonimisering) was al langer klaar en kan gewoon aansluitend.

Beide tracks raken (deels) dezelfde repo (`ai-governance-os`); `git status`/`git diff` toont ze samen. Prima om in één commit te combineren of in twee losse commits — zolang beide vóór de volgende push meegaan.

---

## Track A — klantportaal live op `app.valqeron.com`, oude marketing-SPA overal weg

### Context

`app.valqeron.com`, `api.valqeron.com` en `compliance.valqeron.com` tonen momenteel allemaal nog de oude marketing/product-SPA (`app/static/app.jsx`, React 18 via CDN/Babel-standalone). Er bestaat een apart, echt klantportaal (`ai-governance-frontend`, Vite + React 19 + TypeScript, **geen git-repository**) dat nooit gedeployed is. Dennis heeft expliciet besloten: `app.valqeron.com` wordt het échte portaal; de marketing-SPA verdwijnt overal (`app.`/`api.`/`compliance.valqeron.com`); `compliance.valqeron.com` wordt een pure JSON-API zonder pagina; de bestaande, aparte marketingsite op `valqeron.com`/`www.valqeron.com` (Strato-hosting, buiten deze repo) blijft ongewijzigd.

### Stap 1 — `ai-governance-os` (git-repo, normale flow)

1. `git status` / `git diff` — bevestig dat precies deze bestanden gewijzigd zijn:
   - `app/main.py` — `/static`-mount, `/core`-route en de HTML-response op `/` zijn verwijderd; `/` en `/api/status` geven nu alleen JSON terug.
   - `nginx/sites/app.valqeron.com.conf` — volledig herschreven: was een FastAPI-reverse-proxy met een steeds terugkerende CSP-buglijn (Babel-standalone/CDN-scripts vereisten `unsafe-inline` + `unpkg.com`), is nu een static-file-server voor een Vite-build met een simpele CSP (`script-src 'self'` volstaat — geen CDN/inline-scripts meer nodig).
   - `nginx/sites/api.valqeron.com.conf`, `nginx/sites/compliance.valqeron.com.conf` — alleen de verklarende header-comment bijgewerkt, geen functionele wijziging.
2. `pytest -q` — bevestig groen (geen Python-logicawijziging buiten `main.py`, maar toch checken; de eerdere run in de cloud-sandbox gaf 0 nieuwe fails t.o.v. de bekende 19 pre-existing/environmental).
3. Commit + push naar `origin/main`. Dit deployt zichzelf via de bestaande CI/CD-pijplijn (`.github/workflows/deploy.yml`) en verwijdert de marketing-SPA meteen van alle drie domeinen, onafhankelijk van stap 2 hieronder.

### Stap 2 — `ai-governance-frontend` (géén git-repo — dit is handwerk)

`ai-governance-frontend` heeft geen `.git`-map, dus dit gaat niet via de CI/CD-pijplijn. Een eenmalige handmatige build + kopie is nodig:

a. Maak `.env.production` aan in de root van `ai-governance-frontend` (dit bestand kon niet automatisch vanuit de Cowork-sessie geschreven worden — de remote-bestandstools weigeren principieel schrijven naar `.env*`-bestanden):
```
VITE_API_BASE=https://api.valqeron.com
```

b. Controleer voor de zekerheid dat deze twee bestanden er al staan (ze zijn al vanuit de Cowork-sessie naar de Mac geschreven) en klopt met het volgende:
   - `src/lib/api.ts` — `API_BASE` moet `import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8001'` zijn, **niet** de oude hardcoded `'http://127.0.0.1:8001'`. (Dit was een echte, productie-brekende bug: zonder deze fix zou elke bezoeker naar zijn eigen `localhost` proberen te praten in plaats van naar `api.valqeron.com`.)
   - `src/vite-env.d.ts` bestaat en declareert `ImportMetaEnv.VITE_API_BASE: string`.
   - `index.html` heeft `<title>Valqeron</title>` (was de Vite-default).

c. `npm install` (indien nodig) en `npm run build` — dit produceert een `dist/`-map.

d. Op de server (`valqeron-prod-v2`, 164.92.221.90, root via SSH):
   - Maak `/opt/valqeron-frontend` aan als die nog niet bestaat, met eigenaarschap vergelijkbaar met `/opt/valqeron` (check hoe dat daar precies staat, waarschijnlijk `www-data` of `root` — consistent houden).
   - Kopieer de lokale `dist/`-inhoud naar `/opt/valqeron-frontend/dist` (bijv. `scp -r dist/* root@164.92.221.90:/opt/valqeron-frontend/dist/` of `rsync`).
   - `nginx -t && systemctl reload nginx` (de nieuwe `nginx/sites/app.valqeron.com.conf` komt al mee via stap 1's auto-deploy, maar de `dist/`-map zelf moet hier los naartoe — die zit niet in git).

### Stap 3 — Verifiëren (echte browsercheck, niet alleen curl)

- `app.valqeron.com` moet het portaal tonen (login-scherm), niet de marketing-copy. Test in te loggen met een bestaande demo-user (zie `DEMO_USERS.md` in `ai-governance-frontend`) om te bevestigen dat het portaal ook echt met `api.valqeron.com` praat (en niet blijft hangen op de oude `localhost`-bug).
- `api.valqeron.com/` en `compliance.valqeron.com/` moeten platte JSON teruggeven (`{"service": ..., "status": "ok"}`), geen HTML meer.
- Belangrijke les uit eerdere CSP-fixes op dit domein: een `curl -I`-check op de headers is niet genoeg — controleer de daadwerkelijk gerenderde pagina (browserconsole vrij van CSP-violations, zichtbare content in `#root`).

### Stap 4 — Optioneel, aanbevolen

`ai-governance-frontend` heeft geen git-repo en dus geen CI/CD — elke volgende wijziging daar vereist dezelfde handmatige build+kopie-stap. Overweeg de build+kopie toe te voegen aan `scripts/deploy.sh` (of een apart script) zodat dit niet elke keer opnieuw handwerk is. Niet verplicht voor deze hand-off, wel het overwegen waard.

---

## Track B — AVG-anonimiseringslaag (Presidio), overgedragen uit een eerdere sessie

Alle code staat al klaar in de working tree, gebouwd en getest in een aparte cloud-sandbox (niet op de Mac zelf).

1. `git status`/`git diff` — bevestig: `app/core/pii_anonymizer.py` (nieuw), de 10 bestanden onder `app/workflows/implementations/`, `tests/conftest.py`, `tests/test_pii_anonymizer.py` (nieuw), `tests/workflows/test_pii_anonymizer_wiring.py` (nieuw), `requirements.txt`.
2. `pip install -r requirements.txt` in de échte Mac-omgeving (`venv/`) — **let op:** dit downloadt nu ook ~1 GB aan spaCy-taalmodellen (`nl_core_news_lg`/`en_core_web_lg`) via directe wheel-URLs vanaf GitHub releases. Bij een 404 op een wheel-URL: zie de toelichting in `requirements.txt` zelf.
3. `pytest -q` — bevestig groen in de échte repo-omgeving (de eerdere verificatie liep in een losse cloud-sandbox met een eigen virtualenv — nuttig om de logica te bewijzen, geen vervanging voor een run in de daadwerkelijke omgeving).
4. Commit + push naar `origin/main`. **Let op CI:** vanaf deze commit downloadt élke CI-run ook de ~1 GB aan spaCy-modellen — na de push controleren dat de CI-run niet tegen een timeout aanloopt (GitHub Actions' standaard-timeout is ruim, dus waarschijnlijk geen probleem, maar niet eerder gebeurd met deze repo).
5. Zodra CI op `main` slaagt, deployt `.github/workflows/deploy.yml` zichzelf naar `valqeron-prod-v2` — inclusief dezelfde `pip install`-stap op de server (reken op een merkbaar langere deploy-run). Bevestig via de Actions-tab dat de deploy-run daadwerkelijk slaagt (niet aannemen). Daarna: een workflow-run end-to-end testen (echte login + `POST /workflows/business-intelligence/run` met tekst die evident persoonsgegevens bevat) en in de server-logs bevestigen dat `pii_anonymizer: workflow=... — N entiteit(en) geanonimiseerd` verschijnt vóór de OpenAI-call.

**Wat dit oplost:** vóór deze wijziging ging tekst met persoonsgegevens ongefilterd naar OpenAI in alle 10 workflows. Na deze wijziging wordt PII (namen, e-mail, telefoon, IBAN, creditcard, BSN, IP, locatie) verplicht geanonimiseerd vóór elke externe LLM-call, fail-closed (bij een initialisatiefout van Presidio/spaCy valt de workflow terug op het bestaande "degraded"-antwoordpad in plaats van ongefilterde tekst te versturen).

---

## Na afloop: CLAUDE.md bijwerken

Beide tracks zijn in CLAUDE.md (repo-root) al uitgebreid gedocumenteerd vanuit de Cowork-sessie (secties 1, 2, 4, 5, 6, 7) — inclusief een expliciete "Track A / Track B"-sectie 7 met dezelfde stappen als hierboven. Werk sectie 6 (changelog) bij met een nieuwe regel voor wat jij hebt uitgevoerd (commits, testresultaten, eventuele afwijkingen van het plan hierboven), en herschrijf sectie 7 ("Volgende stap") naar wat er na deze hand-off nog open staat — volgens het gebruikelijke protocol bovenaan dat bestand.
