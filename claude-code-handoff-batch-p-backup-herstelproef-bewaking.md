# Hand-off Batch P — back-up, herstelproef en schijf-/uptimebewaking

Auteur: Cowork (architect). Uitvoerder: Claude Code, **één sessie**. Datum: 7 okt 2026. Repo: `ai-governance-os`. Productie: `/opt/valqeron` op `164.92.221.90` (`valqeron-prod-v2`, 3,9 GB RAM, Postgres lokaal op dezelfde machine).

## Waarom

Er is **geen back-up en geen herstelproef**. Dat is het grootste gat uit de ISO-opzet (`claude/iso-27001-42001-opzet-valqeron.md`, ISO 27001 A.8.13) en een voorwaarde voor elke verwerkersovereenkomst. Dit batch levert: (P1) een dagelijkse, versleutelde database-back-up met bewaartermijn, (P2) een geautomatiseerde herstelproef naar een wegwerpdatabase, (P3) een schijfalarm en een uptime-controle. Geen applicatiecode, geen migraties, geen wijziging aan auth, MFA, provisioning of de ops-code.

## Dennis levert eerst (zonder dit start Claude Code alleen P1-lokaal en P2; zie de poorten)

Geheimen zet Claude Code **niet** zelf weg (de classifier blokkeert dat en het is ook niet de bedoeling). Dennis doet deze vier dingen, elk met een genummerde handleiding van Cowork als hij erom vraagt:

1. **Sleutelpaar voor de versleuteling (`age`).** Dennis maakt op zijn **eigen Mac** een sleutelpaar. De **publieke** sleutel (begint met `age1…`) plakt hij in de opdracht aan Claude Code; die is niet geheim. De **geheime** sleutel blijft op zijn Mac en in zijn wachtwoordmanager; ze komt nooit op de server en nooit in een chat. Zonder geheime sleutel is geen enkele back-up te lezen: bewaar twee kopieën op verschillende plekken.
2. **Off-site bestemming kiezen en aanmaken.** Voorstel: een DigitalOcean Space (S3-compatibel) in een regio in de EU, of een andere S3-compatibele opslag naar keuze; een bucket met een eigen, beperkte sleutel die alleen schrijven en lijsten mag, en bij voorkeur versiebeheer of "object lock" tegen wissen. Dennis vermeldt aan Claude Code alleen: de naam van de bucket, het endpoint en de regio.
3. **Toegangssleutels van die bucket op de server zetten door Dennis zelf**, in een bestand dat alleen root kan lezen (`/etc/valqeron/backup.env`, rechten `600`), met de variabelen die de hand-off in P1 noemt. Claude Code schrijft dat bestand niet en leest het niet voor in het rapport.
4. **Uptime-dienst kiezen** (bijv. een gratis externe uptimemonitor) en het meldadres (e-mail of push) instellen; Dennis maakt het account aan. Claude Code levert alleen de lijst met te controleren URL's en de verwachte antwoorden.

**Poorten:** Zonder punt 1: niets bouwen, melden. Zonder punt 2 en 3: P1 draait alleen **lokaal** op de server (`/var/backups/valqeron/`) met de duidelijke waarschuwing in rapport en CLAUDE.md dat dit **geen echte back-up is** (zelfde schijf, zelfde machine); P2 en P3 worden wel gebouwd. Zonder punt 4: P3 levert alleen het schijfalarm.

## Vooraf besloten (niet opnieuw voorleggen)

- **Alleen de database in P1**, via `pg_dump -Fc` als de Postgres-gebruiker met peer-authenticatie (`sudo -u postgres pg_dump valqeron`). Dus **geen databasewachtwoord nodig**, niets uit `.env` lezen, niets in een bestand zetten.
- **Versleuteling met een publieke sleutel (`age`)**: de server kan versleutelen maar niet ontsleutelen. Installeer het pakket `age` via apt (de enige toegestane serverwijziging in dit batch naast de units en scripts hieronder; geen `upgrade`, geen herstart).
- **Niet in de back-up, bewust:** de productie-`.env` en andere geheimen. Die hoort Dennis apart en offline te bewaren (wachtwoordmanager). Meld in CLAUDE.md dat dit een open punt blijft: een herstel op een nieuwe server vraagt eerst de handmatige terugplaatsing van de `.env` en de deploysleutels.
- **Geüploade documenten** (de map met klantbestanden, bepaal de plek in Fase 0): **in P1 meenemen als aparte versleutelde `tar.zst`** als die bestaat en kleiner is dan 20% van de vrije schijf; anders alleen melden en een voorstel doen.
- **Bewaartermijn** (lokaal en off-site): 14 dagelijkse, 8 wekelijkse (zondag), 6 maandelijkse (eerste van de maand). Oudere weg, behalve de laatste succesvolle back-up (die nooit).
- **Tijd:** dagelijks 03:15 UTC via een `systemd`-timer (niet cron), met `Persistent=true`. Memory-zuinig: `nice`/`ionice`, één dump tegelijk.
- **Herstelproef (P2):** wekelijks, zondag 04:30 UTC, in een **wegwerpdatabase** met een duidelijk eigen naam (`valqeron_restore_test`), die altijd weer wordt verwijderd. Nooit in de echte database, nooit op de echte poort van de app, nooit met productiegebruikers.
- **Ontsleutelen gebeurt niet op de server.** De wekelijkse herstelproef op de server controleert daarom de **dump zelf** (de plain dump wordt vóór de versleuteling in een pipe naar de wegwerpdatabase gelezen), en controleert op het versleutelde bestand alleen de aanwezigheid, de grootte en een checksum. De volledige keten *back-up ontsleutelen en terugzetten* test **Dennis zelf** op zijn Mac met zijn geheime sleutel: eenmalig nu (zie Rapport) en daarna elk kwartaal. Cowork schrijft de handleiding in gewoon Nederlands als Claude Code klaar is.
- Geen databasewijzigingen, geen schema-wijzigingen, geen wijziging in `valqeron.service` of nginx.

## Werkwijze

1. `git pull` in `ai-governance-os`, `git status` en `git diff` (drift-check; verwacht Batch N/O-commits of nieuwer). Meld afwijkingen.
2. **Fase 0 (alleen lezen), eerste alinea van je rapport:** `psql`-versie en databasegrootte (`pg_database_size`), vrije schijf (`df -h /`), waar de geüploade documenten staan en hoe groot ze zijn, welke systemd-units en timers nu bestaan, welke dump-/back-upfuncties er al in `scripts/` zitten (verwacht: geen), of `age` beschikbaar is in apt, `ionice`/`nice` aanwezig, of er een `/etc/valqeron/` is. Wijkt iets af van dit document: stoppen en melden.
3. Kleine losse commits; na elke push CI en Deploy controleren (`DEPLOY CHECK OK`).

## P1 — dagelijkse versleutelde back-up met bewaartermijn

- `scripts/backup_db.sh` (bash, `set -euo pipefail`): leest de publieke sleutel uit `/etc/valqeron/backup.pub` (**door Dennis' opdracht neergezet; geen geheim**, Claude Code mag dit bestand zelf schrijven als Dennis de publieke sleutel in de opdracht noemt) en, **als aanwezig**, de off-site-instellingen uit `/etc/valqeron/backup.env`.
- Stappen: schijfcheck (stop en meld als vrije ruimte kleiner is dan 2× de databasegrootte of schijf boven 80%); `sudo -u postgres pg_dump -Fc valqeron | age -r "$PUBKEY" > /var/backups/valqeron/db-JJJJ-MM-DDTUU.dump.age`; checksum (`sha256sum`); grootte controleren (een dump kleiner dan een ondergrens, bijv. 10 KB, geldt als mislukt); bewaartermijn toepassen (14/8/6); **als off-site-instellingen aanwezig zijn:** uploaden met een S3-compatibele client die in apt of pip beschikbaar is (voorstel: `rclone` of `aws-cli`, kies de lichtste en meld je keuze), upload verifiëren (grootte of checksum van het object), en pas daarna lokaal opruimen volgens de bewaartermijn.
- Rechten: `/var/backups/valqeron` map `700`, bestanden `600`, eigenaar `root` (of een eigen `backup`-gebruiker, jouw keuze, meld die).
- Een **statusbestand** `/var/lib/valqeron/backup-status.json` (tijdstip, uitkomst, grootte, checksum, off-site ja/nee, **geen** inhoud en geen namen) en een logregel in de journal. Geen databaseinhoud, geen tabelnamen met aantallen in logs, geen geheimen.
- Units: `systemd/valqeron-backup.service` en `systemd/valqeron-backup.timer` in de repo (`systemd/` bestaat al); installeren op de server met `cp`, `systemctl daemon-reload`, `systemctl enable --now valqeron-backup.timer`. **Geen herstart van `valqeron.service`.**
- Draai de back-up één keer met de hand en controleer: bestand staat er, rechten kloppen, `age --decrypt` is niet mogelijk op de server (er is geen geheime sleutel; dat is de bedoeling), statusbestand zegt `ok`.
- Als de geüploade documenten worden meegenomen: aparte `tar --zstd` naar dezelfde `age`-pipe, zelfde bewaartermijn.

## P2 — geautomatiseerde herstelproef (wekelijks)

- `scripts/restore_test.sh`: maakt `valqeron_restore_test` (eigenaar de Postgres-gebruiker, **niet** de app-rol), zet daarin een verse plain-`pg_dump` van de live database (`sudo -u postgres pg_dump -Fc valqeron | sudo -u postgres pg_restore -d valqeron_restore_test --no-owner`), vergelijkt **alleen tellingen** (aantal rijen in `organizations`, `users`, `audit_logs`, `workflow_runs`, `documents`, `ai_systems`) tussen live en herstelde kopie (kleine afwijking door gelijktijdige schrijfacties is toegestaan en wordt gemeld; een afwijking van meer dan 1% of een ontbrekende tabel is een **mislukte proef**), verwijdert de wegwerpdatabase **altijd** (ook bij een fout; gebruik een `trap`), en schrijft de uitkomst naar `/var/lib/valqeron/restore-test-status.json` (tijdstip, uitkomst, duur, aantal tabellen). Geen rijinhoud in de logs.
- Eerste schijfcheck: onvoldoende ruimte (vrije schijf < 2,5× databasegrootte) of schijf > 80% = de proef wordt **overgeslagen en gemeld**, niet geforceerd.
- Controleer ook dat de back-upbestanden **recent** zijn: de nieuwste lokale back-up is niet ouder dan 36 uur, anders `waarschuwing` in het statusbestand.
- Timer: `systemd/valqeron-restore-test.service` en `.timer` (zondag 04:30 UTC).
- Draai één keer met de hand: uitkomst `ok`, wegwerpdatabase is weg (`\l`), statusbestand klopt, **de echte database is ongewijzigd** (tellingen vóór en na gelijk, `/audit/verify` `valid` voor org 1).

## P3 — schijfalarm en uptime

- **Schijf:** `scripts/disk_alarm.sh` + `systemd/valqeron-disk-alarm.service/.timer` (elk uur): meet `df /` en de grootste map onder `/var/backups`, `/opt/valqeron`, `/var/log` (alleen groottes); boven **80%** `waarschuwing`, boven **90%** `kritiek`; schrijf de uitkomst naar een statusbestand en de journal. **Melding naar Dennis:** gebruik het bestaande Resend-pad van de app alleen als dat zonder een geheim in een nieuw bestand te zetten of zonder het te printen kan (bijv. via een kleine bestaande functie in de app die de server zelf uitvoert onder zijn eigen omgeving). Blokkeert de classifier dit, of is er geen pad zonder geheim aan te raken: **niet omzeilen**; lever dan alleen de statusbestanden en de journalregel en meld dat de melding naar Dennis een actie van hem is (bijv. via de externe uptime-dienst, zie hieronder).
- **Uptime:** lever een lijst voor de externe uptime-dienst die Dennis kiest: `GET https://api.valqeron.com/health` (verwacht 200 en `"status":"ok"`), `GET https://app.valqeron.com/` (verwacht 200), certificaatvervaldatum van `api.`/`app.`/`compliance.valqeron.com` (alarm bij < 21 dagen; huidige vervaldatum 2026-11-20). Claude Code maakt **geen** account en zet geen sleutels.
- **Nieuw kleine eindpunt (alleen als er een goede plek voor is, anders niet bouwen):** `/health` bestaat al; breid het niet uit zonder reden. Als blijkt dat `/health` een achtergebleven dump niet kan zien: **laat het zo**, de statusbestanden zijn voldoende voor nu.

## Tests

Waar het kan, testbare logica (bewaartermijnfunctie 14/8/6, bestandsnaam- en datumlogica, drempelwaarden 80/90%, ondergrens van de dump, de volgorde "eerst uploaden, dan opruimen") in een klein Python-hulpmodule met tests (`pytest -q -m "not codex"` volledig groen), of als `bats`/shelltests als dat al in de repo past. Het bash-script zelf wordt op de server gecontroleerd (zie productiecheck).

## Productiecheck (zo veel mogelijk alleen lezen; de enige schrijfacties zijn de eigen back-upbestanden, het statusbestand en de wegwerpdatabase)

1. `systemctl list-timers` toont de drie timers en de volgende run; `systemctl status` van de drie services is `inactive (dead)` met laatste uitkomst `success` na de handmatige run.
2. Handmatige run P1: bestand en rechten, grootte, statusbestand `ok`; **een tweede run** binnen hetzelfde uur schrijft een nieuw bestand zonder het eerste te overschrijven; de bewaartermijn verwijdert niets te vroeg (test op een kopie in een tijdelijke map, niet op de echte back-ups).
3. Handmatige run P2: zie hierboven. Daarna `psql -l`: geen `valqeron_restore_test`.
4. De app is er niet van beïnvloed: `/health` 200 vóór en na, `valqeron.service` niet herstart (uptime van de unit ongewijzigd), geen groei in latency die je kunt zien, schijf < 80%.
5. **Eenmalige ontsleutelingsproef doet Dennis** met de bestanden die Claude Code aanwijst; Claude Code ontsleutelt niets.

## Stopvoorwaarden

Stop en meld als: de publieke sleutel ontbreekt of niet met `age1` begint; een geheim in een bestand of chat zou moeten (classifier-blok niet omzeilen); een migratie of schemawijziging nodig lijkt; auth, MFA, provisioning of ops-code geraakt wordt; een dump groter is dan de vrije ruimte laat; de schijf boven 80% komt; een back-up of herstelproef de app merkbaar vertraagt (`/health` > 2 s); een Deploy twee keer achter elkaar faalt (de pijplijn draait zelf terug); er iets gedaan zou moeten worden met een andere server of database; of apt iets anders wil installeren dan `age` en afhankelijkheden. Is P1 klaar en blokkeert P2 of P3: lever P1 af en meld de rest.

## Rapport

Fase 0-bevindingen en afwijkingen; commits (hash en doel) en CI-/Deploy-run-id's; per onderdeel (P1 t/m P3) wat is afgerond; welke poorten waren dicht (publieke sleutel, off-site, uptime) en wat dus **niet** is gedaan; grootte van de database en de eerste back-up, duur van back-up en herstelproef, schijfgebruik vóór en na; wat er **niet** in de back-up zit (`.env`, deploysleutels) en wat Dennis dus apart moet bewaren; CLAUDE.md (§2, §5, §6, §7) en READMEs bijgewerkt met commit-hash, inclusief de open punten "geen off-site back-up" (als punt 2/3 ontbrak) en "ontsleutelingsproef door Dennis, elk kwartaal".

---

## Conceptprompt voor Claude Code (korte versie)

> Voer `claude-code-handoff-batch-p-backup-herstelproef-bewaking.md` uit (staat in de repo-root; eerst `git pull`). Publieke `age`-sleutel: `age1…` [**Dennis plakt hier zijn publieke sleutel**]. Off-site bestemming: [bucketnaam, endpoint, regio — **of** "nog niet"]. Credentials staan [wel/nog niet] in `/etc/valqeron/backup.env` (door mij gezet). Uptime-dienst: [gekozen/nog niet]. Eén sessie. Geen migraties, geen herstart van de app, geen geheimen in bestanden of chat, classifier-blokkades niet omzeilen. Rapporteer volgens de hand-off en werk CLAUDE.md bij.
