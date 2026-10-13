# Rapport — 2026-10-13 (Claude Code: Batch P, back-up/herstelproef/schijfalarm)

Opdracht van Dennis: "continue" — volgens de vaste opdracht ("Lees `WERKLIJST.md` en het
HERVAT-BLOK in `CLAUDE.md`... Voer de eerste regel met status `OPEN` uit waarvan de voorwaarde
klaar is..."). `WERKLIJST.md` was buiten deze sessie om bijgewerkt: Cowork had rij 7 (Batch P)
op `OPEN` gezet, met de eerste twee van de vier door Dennis geleverde punten (publieke
`age`-sleutel en de off-site-bestemming) en met de twee resterende punten expliciet "nog niet".
Dit document bevat geen geheimen, IP-lijsten of persoonsgegevens.

**Resultaat in één zin:** P1 (dagelijkse versleutelde back-up), P2 (wekelijkse geautomatiseerde
herstelproef) en P3 (uurlijks schijfalarm) zijn volledig gebouwd en op productie bewezen; rij 7
staat op `WACHT OP DENNIS` (niet `KLAAR`) omdat de off-site-upload en de externe uptime-melding
nog op twee leveringen van Dennis wachten — alles daarvoor is al klaar en getest.

---

## Wat is er gebeurd

**Fase 0 (alleen lezen):** database `valqeron` is 11 MB, `uploaded_documents` 576 KB (ruim onder
de 20%-grens voor de documentenbundel), schijf 15% vol. Geen bestaande back-up-infrastructuur.
**Belangrijke bevinding:** `aws-cli` is op Ubuntu 24.04 niet via apt beschikbaar — `rclone` wel
(1.60.1), dus die keuze gemaakt (de hand-off liet dit bewust open). `pg_dump` via peer-auth als
`postgres` werkt zonder wachtwoord, zoals voorgeschreven.

**P1** (`scripts/backup_db.sh` + timer, dagelijks 03:15 UTC): `pg_dump` versleuteld met de
publieke `age`-sleutel, lokaal opgeslagen (`700`/`600`, eigenaar `root`). Off-site via `rclone`
met een volledig env-var-gedreven S3-remote — alleen als `/etc/valqeron/backup.env` bestaat
(nog niet); zonder dat bestand een duidelijke "geen echte back-up"-waarschuwing. GFS-
bewaartermijn (14 dagelijks/8 wekelijks/6 maandelijks/altijd de laatste) in een eigen, getest
Python-module. **Eigen, gemelde afwijking:** de hand-off's voorbeeldbestandsnaam had alleen
uur-granulariteit, maar zijn eigen productiecheck eist dat een tweede run binnen hetzelfde uur
nooit overschrijft — opgelost met volledige uur-minuut-seconde-precisie in de bestandsnaam.

**P2** (`scripts/restore_test.sh` + timer, wekelijks zondag 04:30 UTC): een verse `pg_dump`/
`pg_restore` naar een wegwerpdatabase (nooit de versleutelde back-up zelf — ontsleutelen gebeurt
nooit op de server), rijtellingen over 6 tabellen met 1% tolerantie, de wegwerpdatabase wordt
altijd verwijderd via een `trap`, ook bij een fout.

**P3** (`scripts/disk_alarm.sh` + timer, elk uur): `df`-drempels 80%/90%, hergebruikt de
al-bestaande, al-geconfigureerde Resend-functie van de app voor een e-mailalarm — geen nieuw
geheim, niets geprint.

**Tests:** 24 nieuwe tests (19 puur-functioneel voor de bewaartermijn/drempel-/staleness-/
rijtelling-logica, 5 structurele checks op de scripts zelf — o.a. dat upload vóór opruimen
gebeurt, zoals de hand-off letterlijk vraagt). Backend-suite 504 → 528, volledig groen. Eigen
testfout gevonden en gefixt (te weinig vuldata in één test, geen productiebug).

## Resultaat

- Gecommit `2e3ec51` (dertien bestanden: de Python-module, de CLI-shim, drie bash-scripts, zes
  systemd-units, twee testbestanden). CI `38393107496`/Deploy `38393302466`, beide groen.
- Op productie: `age`+`rclone` geïnstalleerd (geen andere pakketten, geen herstart nodig), drie
  timers `enabled`+`active`. Alle drie handmatig gedraaid en bewezen: P1 twee keer binnen 18
  seconden zonder overschrijving + bewaartermijn getest tegen 40 synthetische bestanden in een
  losse tijdelijke map (nooit de echte back-ups); P2 6 tabellen `ok`, wegwerpdatabase bevestigd
  weg; P3 `ok` bij 15% plus één apart, duidelijk gelabeld TEST-e-mailbericht via de bestaande
  Resend-functie, bevestigd `sent` — het tijdelijke testscript is van zowel de Mac als de server
  verwijderd.
- `valqeron.service` niet herstart door P1/P2/P3 zelf; `/health` ok voor/tijdens/na; schijf 15%
  voor/na; latency normaal (~100ms).
- **Niets verstuurd aan derden** buiten die ene, bewust gelabelde TEST-e-mail naar Dennis' eigen,
  al-bestaande supportadres (geen nieuw geheim, geen nieuwe ontvanger).

## Productiecontrole

Zie "Resultaat" hierboven — alle items uit de hand-off's eigen productiecheck-sectie zijn
afgevinkt, behalve item 5 ("eenmalige ontsleutelingsproef"), die expliciet Dennis' eigen taak is
met zijn geheime sleutel op zijn eigen Mac.

## WERKLIJST.md en CLAUDE.md

- Rij 7 (Batch P) van `OPEN` naar **`WACHT OP DENNIS`** gezet — bewust niet `KLAAR`, want de
  hand-off's eigen rapport-instructie vraagt om de openstaande poorten te melden, en de off-site-
  back-up bestaat nog niet echt.
- CLAUDE.md: nieuwe infrastructuurrij in sectie 2, een nieuwe risicorij in sectie 5 (gedeeltelijk
  opgelost, twee punten open), een nieuwe sectie-6-logregel, en het HERVAT-BLOK bijgewerkt
  (volgende stap = rij 12, Batch T).
- Alle wijzigingen gecommit (`2e3ec51`, `1ffbe2a`) en gepusht; CI voor beide groen.

## Variabelennamen en lijst voor Dennis

**Off-site (`/etc/valqeron/backup.env`, 600, root:root — door Dennis zelf te zetten, Claude Code
schrijft of leest dit bestand niet):**
```
RCLONE_CONFIG_VALQERONBACKUP_ACCESS_KEY_ID=...
RCLONE_CONFIG_VALQERONBACKUP_SECRET_ACCESS_KEY=...
```
Precies deze twee — bucket (`valqeron-backups`), endpoint (`ams3.digitaloceanspaces.com`) en
regio (`ams3`) staan al niet-geheim in het script zelf.

**Externe uptime-dienst (Dennis kiest en zet zelf het account/meldadres op):**
- `GET https://api.valqeron.com/health` — verwacht `200`, `"status":"ok"`
- `GET https://app.valqeron.com/` — verwacht `200`
- Certificaatvervaldatum van `api.`/`app.`/`compliance.valqeron.com` — alarm bij < 21 dagen
  (huidige vervaldatum: 2026-11-20)

## Niet gedaan / openstaand

- **Off-site-upload:** wacht op `/etc/valqeron/backup.env`. Tot die tijd is elke back-up
  lokaal-alleen (zelfde schijf, zelfde machine) — duidelijk gelogd als zodanig.
- **Externe uptime-melding:** Claude Code maakt bewust geen account aan bij een uptime-dienst.
- **Eenmalige volledige ontsleutelingsproef** (back-up ontsleutelen + terugzetten): expliciet
  Dennis' eigen taak, met zijn geheime sleutel op zijn eigen Mac — nu, en daarna elk kwartaal.
- Rij 12 (Batch T, auditregels voor `app/api/users.py`) is de volgende `OPEN`-rij — niet gestart
  deze sessie.

Geen migraties, geen applicatiecodewijzigingen, geen wijziging aan auth/MFA/provisioning/
ops-code, geen wijziging aan `valqeron.service` of nginx — exact zoals de hand-off voorschrijft.
