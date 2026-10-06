# Hand-off Batch K — serverhygiëne: deploy.sh, testaccount, updates en herstart

Auteur: Cowork (architect). Uitvoerder: Claude Code, **één sessie**. Datum: 6 okt 2026 (avond). Mogelijk **zonder toezicht** uitgevoerd (nachtrun): lees de stopregels.
Repo: `ai-governance-os`. Productie: `/opt/valqeron` op `164.92.221.90`.

## Doel

1. De oorzaak van de volle schijf (65 GB pip-cache op 6 okt) structureel wegnemen.
2. Het wegwerp-testaccount "ZZ Provisioning Wizard Test" (id 2, status `contract`, ongekoppeld) uit de actieve lijst halen.
3. De open serverupdates (39) installeren en de server herstarten (CLAUDE.md: herstart vereist), mét controles ervoor en erna.

## Vooraf besloten (niet opnieuw voorleggen)

- Oplossing voor de cache: `--no-cache-dir` bij elke `pip install` in `scripts/deploy.sh` (en, als aanwezig, in andere scripts die op de server `pip install` draaien). Geen periodieke cron, geen andere wijziging in de deploy-logica.
- Account id 1 (ISO CERT INTERNATIONAL LTD) en org 1 t/m 4 blijven onaangeroerd. Alleen account id 2 wordt aangepast, via de bestaande API, niet via SQL.
- Het herstarten gebeurt **maximaal één keer**. Een tweede herstart alleen met toestemming van Dennis.
- Geen releasewijziging (`do-release-upgrade`), geen `dist-upgrade` dat pakketten verwijdert, geen Python-versiewissel, geen wijziging aan systemd-units, nginx-configuratie of `.env`.

## Werkwijze

1. `git status` en `git diff` (drift-check; verwacht `72135ea` of nieuwer). Meld afwijkingen.
2. Kleine losse commits; na elke push CI en Deploy controleren (GitHub Actions-API, `DEPLOY CHECK OK`).

## K1 — `--no-cache-dir`

- Zoek alle `pip install`-aanroepen in `scripts/` en in de CI/deploy-workflow die op de server draaien. Voeg `--no-cache-dir` toe. Pas niets anders aan.
- Draai eerst de tests; push; controleer CI en Deploy.
- Controleer daarna op de server (alleen lezen): `du -sh /root/.cache/pip` (en andere `.cache`-mappen van de deployuser) vóór en ná de Deploy; de groei mag niet meer optreden. Voer eenmalig `pip cache purge` uit als er nog cache staat (dat is opruimen van onze eigen cache, geen gebruikersdata). Rapporteer `df -h /` vóór en ná.

## K2 — testaccount id 2 afsluiten

- Met een server-side gemunt token voor `dennis_admin` (MFA-claim, alleen in geheugen, niet printen, niets achterlaten): `POST /ops/accounts/2/status` naar `lost`; zet daarna (als `PATCH` het toestaat) de notitie op: `TESTACCOUNT (wizardcheck 6 okt 2026). Niet gebruiken.`
- Controleer: account id 2 staat op `lost`, account id 1 ongewijzigd (status en 28 taken, 2 `done`), nog steeds 4 organisaties.
- Kan dit niet zonder iets te omzeilen (classifier, tokenmunting): sla K2 over en meld het.

## K3 — updates en herstart

**Poort:** voer K3 **alleen** uit als de opdracht van Dennis letterlijk `SNAPSHOT=ja` bevat (hij heeft dan een snapshot of back-up van de droplet gemaakt). Staat dat er niet, sla K3 over, meld "K3 overgeslagen: geen snapshot-bevestiging" en ga door met de rest.

**Controles vooraf (alleen lezen). Is er één rood: niet herstarten, melden:**
1. `df -h /` is onder 80%.
2. Alle diensten staan op `enabled` én `active` volgens de echte unitnamen op de server (verwacht: de app-service `valqeron`, nginx, postgresql, redis). Controleer met `systemctl is-enabled` en `systemctl is-active`. **Let op:** de app start in productie niet zonder bereikbare Redis (`ENVIRONMENT=production`); controleer in de unit van `valqeron` dat Redis vóór de app start (`After=`/`Requires=`) of dat `Restart=always` (of `on-failure`) staat, zodat een opstartvolgorde-race zichzelf herstelt. Ontbreekt beide: niet herstarten, melden.
3. De certificaatvernieuwing (certbot timer of cron) is `enabled`; noteer de vervaldatum (2026-11-20).
4. `/health` geeft 200 met de verwachte `build_sha`; noteer de huidige `uptime`.
5. `apt list --upgradable` (aantal en namen, geen versies hoeven in het rapport); `/var/run/reboot-required` aanwezig of niet.

**Uitvoeren:**
1. `apt-get update`, daarna `DEBIAN_FRONTEND=noninteractive apt-get -y -o Dpkg::Options::=--force-confold upgrade` (dus **geen** `dist-upgrade`). Wil apt pakketten verwijderen of blijven er vragen over: stoppen en melden.
2. Herstart één keer (`reboot`). Wacht tot SSH weer reageert (poll maximaal 10 minuten, elke 15 s).
3. Controles erna: `uptime` is kort; alle diensten `active`; Redis antwoordt; `/health` 200 met dezelfde `build_sha`; `https://app.valqeron.com` laadt (HTTP 200 op de index); `/ops/whoami` zonder token geeft `401` of `403` (niet `5xx`).
4. Start de laatste Deploy-workflow opnieuw (re-run) en controleer `DEPLOY CHECK OK`: dit bewijst dat de pijplijn na de herstart nog werkt.
5. Is de app na 10 minuten nog niet gezond: één keer `systemctl restart valqeron` (geen tweede reboot). Daarna nog niet gezond: **stop alles, doe niets meer, schrijf wat je zag in het rapport** (productie herstellen is dan werk voor Dennis met de snapshot).

## Stopvoorwaarden (nachtrun, geen toezicht)

Stop en meld (en ga niet door met latere batches) als: een controle vooraf rood is; apt iets verwijdert of een vraag stelt; de app na de herstart niet gezond wordt; een Deploy twee keer achter elkaar faalt; tests rood worden; de classifier iets blokkeert (niet omzeilen); iets auth, MFA, provisioning of een andere organisatie zou raken; er een migratie nodig lijkt.

## Rapport (ook als nachtrapport)

Drift-check; K1: commit, CI/Deploy-run, `du`/`df` vóór en ná; K2: uitkomst; K3: overgeslagen of uitgevoerd, aantal geïnstalleerde updates, tijdstip herstart, controles erna (verwacht en gezien), Deploy-run na de herstart; **CLAUDE.md** (§2, §5, §6, §7) bijgewerkt met commit-hash: pip-cacheprobleem opgelost, updates en herstart gedaan (datum, kernelversie), testaccount `lost`. Verwijder de punten "herstart vereist/39 updates" en "periodieke pip cache purge" uit de open lijst.
