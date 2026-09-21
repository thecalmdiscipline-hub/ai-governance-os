# Deploy, terugrollen en herstel — Valqeron

Bijgewerkt op 2026-09-21. Alles hieronder is gecontroleerd op de server (`ssh root@164.92.221.90`) of in de repo's; wat ik niet kon controleren staat er expliciet als zodanig bij. Dit document vervangt het oude herstelplan voor de verwijderde droplet `165.22.204.23`.

## 1. Wat draait waar

- **Server:** droplet `valqeron-prod-v2`, IP `164.92.221.90`, Ubuntu 24.04, 3,9 GB RAM, 2 vCPU, 4 GB swap. De firewall (`ufw`) laat alleen poort 22, 80 en 443 binnen.
- **Domeinen** (allemaal op deze server, nginx per domein in `/etc/nginx/sites-enabled/`): `api.valqeron.com` en `compliance.valqeron.com` (de backend-API), `app.valqeron.com` (het klantportaal). De marketingsite `valqeron.com` staat op een andere host en hoort hier niet bij.
- **Services** (`systemctl status <naam>`): `valqeron` (de API: één uvicorn-proces op `127.0.0.1:8000`, gebruiker `www-data`), `nginx`, `postgresql`, `redis-server`. Certificaten (Let's Encrypt) worden automatisch vernieuwd door `certbot.timer`; ze waren op 2026-09-21 nog 59 dagen geldig.
- **Mappen:** `/opt/valqeron` (backend-code, `venv/`, het geheime bestand `.env`, en `BUILD_SHA`) en `/opt/valqeron-frontend` (de map `releases/` met één map per portaalversie en de symlink `dist` naar de actieve versie).
- **Geheimen** staan nooit in git: `.env` staat alleen op de server, de deploy-sleutels staan als GitHub-secret en op Dennis' Mac (`~/.ssh/valqeron_deploy_key` voor de backend, `~/.ssh/valqeron-frontend-deploy` voor het portaal).

## 2. Backend deployen (gaat vanzelf)

1. Een push naar `main` van `ai-governance-os` start **CI** (`.github/workflows/ci.yml`: de tests).
2. Is CI groen, dan start **Deploy** (`.github/workflows/deploy.yml`). Die logt via SSH in op de server en draait `cd /opt/valqeron && git pull origin main && bash scripts/deploy.sh`.
3. `scripts/deploy.sh` doet, in deze volgorde: vorige commit onthouden, `git pull`, Python-pakketten installeren, `.env` controleren (`SECRET_KEY`, `DATABASE_URL`, `OPENAI_API_KEY`, `REDIS_URL` moeten gevuld zijn), databasemigraties (`alembic upgrade head`), `seed_modules.py`, het bestand `BUILD_SHA` schrijven, `valqeron` herstarten, de nginx-configs uit `nginx/sites/` synchroniseren (en nginx herladen als er iets veranderd is), en tot 90 seconden wachten tot `http://localhost:8000/health` `status: ok` geeft.
4. Daarna controleert Deploy nog van buitenaf `https://compliance.valqeron.com/health` en `https://api.valqeron.com/health`.
5. **Mislukt er iets** (bijvoorbeeld de health-check of `nginx -t`), dan zet het script de code met `git reset --hard` terug naar de vorige commit, schrijft `BUILD_SHA` opnieuw en herstart de service. **Databasemigraties worden niet teruggedraaid**; dat moet je zo nodig met de hand doen (`cd /opt/valqeron && venv/bin/python -m alembic downgrade -1`).
6. Controle na een deploy: `curl -s https://api.valqeron.com/health` toont `"status":"ok"` en `build_sha` (de korte commit die nu draait).

Met de hand deployen (bijvoorbeeld als GitHub niet werkt): `ssh root@164.92.221.90`, dan `cd /opt/valqeron && git pull origin main && bash scripts/deploy.sh`.

## 3. Portaal (frontend) deployen en terugrollen

1. Een push naar `main` van `ai-governance-frontend` start **CI** (lint, tests, build) en daarna **Deploy**. Deploy neemt de build uit CI (er wordt niet opnieuw gebouwd), zet die in `/opt/valqeron-frontend/releases/<commit>/`, verlegt de symlink `dist` naar die map (nginx hoeft niet te herladen), ruimt oude releases op (de laatste 5 blijven, plus de actieve, de vorige en `initial`) en laat een headless browser controleren dat het loginscherm laadt zonder fouten. Faalt die controle, dan draait Deploy zelf terug naar de vorige release.
2. **Handmatig terugrollen** (vanuit een kopie van de frontend-repo op de Mac): `DEPLOY_TARGET=root@164.92.221.90 DEPLOY_SSH_KEY_FILE=~/.ssh/valqeron-frontend-deploy scripts/rollback.sh --list` toont de releases (de actieve met een `*`); `... scripts/rollback.sh <commit>` zet die release actief. `initial` is de handmatige versie van vóór git. Het script verlegt alleen de symlink en verwijdert niets.
3. Zonder het script, op de server: `cd /opt/valqeron-frontend && ln -sfn releases/<commit> dist.tmp && mv -T dist.tmp dist`.

## 4. De systemd-unit synchroniseren (handmatig)

`deploy.sh` synct de nginx-configs maar **niet** `systemd/valqeron.service`. Heb je die in de repo gewijzigd, doe dan na de deploy: `ssh root@164.92.221.90 'cd /opt/valqeron && cp systemd/valqeron.service /etc/systemd/system/valqeron.service && systemctl daemon-reload && systemctl restart valqeron'` en controleer `/health` (de start duurt ongeveer 15 tot 25 seconden). Nu zijn de unit op de server en in de repo identiek (gecontroleerd met `diff`).

## 5. Buitengesloten door tweestapsverificatie (MFA)

Alleen als je geen toegang meer hebt tot je authenticator-app én je back-upcodes kwijt bent:

1. `ssh root@164.92.221.90` en dan `cd /opt/valqeron`.
2. Eerst kijken wat er zou gebeuren (er wordt niets gewijzigd): `venv/bin/python scripts/mfa_reset.py --username dennis_admin --dry-run`
3. Echt uitvoeren: `venv/bin/python scripts/mfa_reset.py --username dennis_admin`
4. Log daarna in met alleen je wachtwoord en schrijf MFA opnieuw in via de Account-pagina van het portaal.

Ben je super-admin, dan blijft die rol staan, maar je hebt pas weer toegang tot `/ops` na een nieuwe inschrijving en een nieuwe login met een code. **Is `MFA_ENCRYPTION_KEY` in `/opt/valqeron/.env` kwijt of veranderd**, dan zijn alle opgeslagen MFA-geheimen onleesbaar en krijgen gebruikers met MFA bij het inloggen een 503-melding. Zet de oude sleutel terug uit een back-up van `.env` en herstart met `systemctl restart valqeron`; heb je die niet, maak dan een nieuwe (`venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`), zet hem als `MFA_ENCRYPTION_KEY=` in `.env`, herstart, en draai `mfa_reset.py` voor elke gebruiker die MFA had. Gebruikers zonder MFA kunnen in de tussentijd gewoon inloggen.

## 6. Waar Sentry staat

Foutmeldingen gaan naar Sentry (EU-regio, één organisatie met twee projecten): `valqeron-backend` en `valqeron-portal`. De backend-DSN staat alleen in `/opt/valqeron/.env` (`SENTRY_DSN`); de portaal-DSN staat als GitHub-variabele `VITE_SENTRY_DSN` in de frontend-repo en wordt bij de build in het portaal gezet. Er gaan alleen technische gegevens naartoe (type fout, bestands- en functienamen, een gemaskeerd bericht, de build-sha als release), nooit klantinhoud of gebruikersgegevens. Een fout die je in Sentry ziet, kun je in de server-log terugvinden met `journalctl -u valqeron` rond hetzelfde tijdstip.

## 7. Wat te doen bij een 502 of een niet-bereikbare site

Een 502 van nginx betekent dat nginx draait maar de API niet antwoordt. **Direct na een deploy of herstart is een 502 normaal**: de API laadt bij het opstarten de anonimiseringsmodellen en is dan ongeveer 15 tot 25 seconden niet bereikbaar. Wacht een minuut en probeer opnieuw. Blijft het 502, ga dan op de server na:

1. `systemctl status valqeron` (draait de API?) en `journalctl -u valqeron -n 100 --no-pager` (staat er een fout of een `Traceback` in?).
2. `curl -s http://127.0.0.1:8000/health` op de server zelf. Werkt dat wel maar de site niet, kijk dan naar nginx: `nginx -t`, `systemctl status nginx` en `/var/log/nginx/error.log`.
3. Geeft `/health` een `503` of `degraded`: controleer de database met `pg_isready` (moet "accepting connections" zeggen) en Redis met `redis-cli ping` (moet `PONG` geven); herstart zo nodig `postgresql` of `redis-server`.
4. Weinig geheugen? `free -m` (kolom "available") en `dmesg -T | grep -i -E "out of memory|killed process"`. De API gebruikt ongeveer 1,9 GB.
5. Herstart de API: `systemctl restart valqeron` en wacht tot `curl -s http://127.0.0.1:8000/health` `ok` geeft.
6. Begon het na een deploy? Kijk in GitHub Actions naar de laatste Deploy-run; het script rolt zelf terug bij een mislukte health-check. Anders: zet een oudere versie terug met `git reset --hard <commit>` in `/opt/valqeron` en herstart (schrijf daarna ook `git rev-parse --short HEAD > BUILD_SHA`), of maak een revert-commit en laat CI/Deploy lopen.

**Reageert de server helemaal niet** (ook SSH niet): kijk in het DigitalOcean-paneel of de droplet aan staat en start hem zo nodig; daar is een browserconsole om in te loggen als SSH niet werkt. *(Dit deel is niet vanuit deze omgeving getest; ik heb geen toegang tot het DigitalOcean-paneel.)* In het verleden bleek een droplet definitief verwijderd te zijn na een verlopen betaaltermijn (2026-08-22). Een nieuwe server opzetten gaat met `scripts/setup_server.sh` op een kale Ubuntu 24.04, waarna de A-records van `api.`, `app.` en `compliance.valqeron.com` naar het nieuwe IP moeten wijzen; dat script is voor de huidige droplet gebruikt maar sindsdien niet opnieuw uitgevoerd.
