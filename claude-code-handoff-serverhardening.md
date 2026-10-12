# Hand-off Serverhardening (B3 en B4) — SSH-aanscherping, fail2ban, kernel-update met één herstart, beperkte deploygebruiker (frontend)

Auteur: Cowork (architect). Uitvoerder: Claude Code, **één sessie, alleen overdag en alleen terwijl Dennis aanwezig is** (kans op uitsluiten). Datum: 12 okt 2026. Repo: `ai-governance-os` (scripts en documentatie) en voor S3 ook `ai-governance-frontend`. Productie: `164.92.221.90` (`valqeron-prod-v2`). WERKLIJST-rij 10, status `WACHT OP DENNIS` tot Dennis in de chat **letterlijk** `SNAPSHOT=ja` zegt; **Cowork zet de rij dan op `OPEN`, Claude Code nooit.**

## Waarom

Uit CLAUDE.md §5: (1) een aanhoudende SSH-scanstorm op poort 22 (~1100 mislukte pogingen per 15 minuten; maakte de frontend-Deploy van 22 sep drie keer flaky), `fail2ban` is niet geïnstalleerd; (2) beide deploysleutels loggen in als `root`, terwijl de frontend-pijplijn alleen naar `/opt/valqeron-frontend` schrijft; (3) de kernel-metapakketten (`linux-image/headers-virtual-generic`) zijn bij de update van 6 okt "kept back" gebleven (een gewone `upgrade` installeert geen nieuwe afhankelijkheden). Hardening verlaagt risico R03 uit het ISMS-risicoregister (`claude/isms-uitwerking-valqeron.md`, ISO 27001 8.20 en 8.2).

## Dennis levert eerst (poorten)

1. **Snapshot van de droplet** (DigitalOcean-paneel, handleiding `claude/b3-handleiding-serverhardening.md`), en in de chat het woord `SNAPSHOT=ja` plus het tijdstip. **Zonder dit begint Claude Code niet** aan S1 (bewust ook niet "alleen fail2ban"); lees alleen en meld.
2. **Dennis blijft beschikbaar** tot het rapport klaar is, met een **tweede terminalvenster en zijn DigitalOcean-paneel open** (de console van de droplet is de noodingang als SSH ooit onbereikbaar is).
3. Voor **S3 (beperkte deploygebruiker)**: een **nieuw sleutelpaar** dat Dennis op zijn Mac maakt; hij noemt alleen de **publieke** sleutel (`ssh-ed25519 AAAA…`) in de opdracht. De privésleutel gaat nooit in een chat of bestand; Dennis zet haar zelf als GitHub-secret in de frontend-repo (handleiding `claude/b4-handleiding-deploysleutel.md`). Staat de publieke sleutel er niet: S3 wordt overgeslagen en gemeld.

## Vooraf besloten (niet opnieuw voorleggen)

- **Geen wijziging aan de SSH-poort, geen wijziging aan de ufw-regels** (22/80/443 blijven; GitHub-runners hebben geen vast IP, dus geen IP-beperking). Geen wijziging aan applicatiecode, database, nginx, `valqeron.service`, auth, MFA of provisioning.
- **Sleutel-authenticatie blijft altijd werken.** Wachtwoord-inlog via SSH uitzetten mag alleen als je **eerst bewijst** dat de huidige sessie en een **tweede, nieuwe** sessie met sleutel werken (zie volgorde). Zet `PermitRootLogin` op `prohibit-password` (niet op `no`: de beide huidige deploysleutels zijn nu root-sleutels; `no` pas na S3 en bevestiging van Dennis, **niet in dit batch**).
- **Veilige volgorde bij elke sshd-wijziging:** (a) bewaar de huidige config als `/etc/ssh/sshd_config.d/…`-drop-in en een kopie van het origineel in `/root/sshd-config-backup-JJJJMMDD/` (alleen configuratie, geen sleutels); (b) `sshd -t` (syntaxis) en `sshd -T` (effectieve instellingen) tonen; (c) **houd de bestaande SSH-sessie open**; (d) `systemctl reload ssh` (**reload, geen restart**); (e) open vanaf Dennis' kant of via een tweede sessie een **nieuwe** verbinding met sleutel en bevestig dat ze werkt vóór je de eerste sessie sluit; (f) bij een mislukking: draai de drop-in terug uit de kopie, reload, meld. De DigitalOcean-console en de snapshot zijn het vangnet.
- **fail2ban:** apt-pakket `fail2ban`, standaard jail `sshd` met backend `systemd`: `maxretry=5`, `findtime=10m`, `bantime=1h`, `recidive` (7 dagen na 3 bans binnen een dag). `ignoreip` bevat `127.0.0.1/8 ::1` en het IP-adres dat Dennis in de chat noemt (**een IP-adres van Dennis mag in de lokale config, niet in git**). Een geslaagde sleutel-inlog telt niet als mislukking, dus een legitieme Deploy wordt niet verbannen; controleer dat in de test hieronder.
- **sshd-instellingen:** `PasswordAuthentication no` (alleen na de bewijsstap), `KbdInteractiveAuthentication no`, `PermitEmptyPasswords no`, `MaxAuthTries 3`, `LoginGraceTime 30`, `MaxStartups 30:30:100` (verruimt de throttling die de Deploy deed falen; fail2ban vangt de storm op), `X11Forwarding no`. Niet meer dan dit.
- **Kernel-update en één herstart:** alleen na S1 en na een groene controle (zie S2). Installeer de kernel-metapakketten expliciet (`apt-get install linux-image-virtual linux-headers-virtual`, of de exacte pakketnamen uit `apt list --upgradable`; geen `dist-upgrade`, geen `full-upgrade`, geen releasewissel). Dan **één** `reboot`. Dennis is aanwezig.
- **Back-up bestaat nog niet** (Batch P wacht op Dennis' leveringen); de snapshot is hier het enige herstelpunt. Meld dat in het rapport.

## Werkwijze

0. **Hervatten:** lees het HERVAT-BLOK in `CLAUDE.md` en `WERKLIJST.md`; ga door bij de eerste onvoltooide stap. Elke stap is veilig opnieuw te draaien.
1. `git pull`, `git status`, `git diff` (drift-check). Meld afwijkingen.
2. **Fase 0 (alleen lezen), eerste alinea van je rapport:** `uname -r` en `/var/run/reboot-required` (+ `reboot-required.pkgs`); `apt list --upgradable` (verwacht alleen de kernel-metapakketten en eventueel nieuwe routine-updates); `sshd -T | grep -E 'passwordauthentication|permitrootlogin|maxauthtries|maxstartups|logingracetime|pubkeyauthentication'`; of `/etc/ssh/sshd_config.d/` bestaat en wat erin staat (let op de cloud-init-drop-in `50-cloud-init.conf`: die kan `PasswordAuthentication` overschrijven); `ufw status verbose`; de huidige inhoud van `/root/.ssh/authorized_keys` **alleen als aantal regels en comments, niet de sleutels zelf**; `df -h /` (stop boven 80%); `free -m`; `systemctl is-active valqeron nginx postgresql redis-server`; `/health` en de laatste Deploy; `fail2ban`-aanwezigheid; hoe `deploy.yml` in beide repo's inlogt (gebruiker, secret-namen, welke commando's op de server draaien). Wijkt iets af van dit document: stoppen en melden.
3. Kleine losse stappen; rapporteer na elke stap kort in het HERVAT-BLOK.

## S1 — fail2ban en sshd-aanscherping

1. Controleer de poort (`SNAPSHOT=ja` staat in de opdracht) en de vijf controles: schijf < 80%, vier diensten actief, `/health` 200, laatste Deploy `DEPLOY CHECK OK`, Dennis bevestigt dat zijn tweede terminalvenster en het DO-paneel open staan.
2. `apt-get install -y fail2ban`; zet `/etc/fail2ban/jail.d/valqeron.local` (jail `sshd`, `recidive`, waarden hierboven); `fail2ban-client -t` (configuratietest); dan `systemctl enable --now fail2ban`; `fail2ban-client status sshd` toont de jail.
3. Wacht ten minste 10 minuten en toon **alleen aantallen**: aantal verbannen IP's, aantal mislukte pogingen; geen IP-lijsten in het rapport.
4. **Bewijsstap sleutel-inlog:** Dennis opent een **nieuwe** SSH-sessie met sleutel (zoals hij altijd inlogt) en meldt dat het werkt. Pas dan verder.
5. sshd-drop-in `/etc/ssh/sshd_config.d/99-valqeron-hardening.conf` met de waarden hierboven (volgorde-regel: een latere drop-in wint niet altijd; controleer met `sshd -T` of de effectieve waarde klopt, en noem de bestandsnaam die `PasswordAuthentication` echt bepaalt). `sshd -t`, `sshd -T`, `systemctl reload ssh`, nieuwe verbinding met sleutel (Dennis), pas dan de eerste sessie loslaten.
6. **Test van fail2ban en de Deploy:** trigger via `workflow_dispatch` een **frontend-Deploy** en een **backend-Deploy** (of wacht op de eerstvolgende); beide moeten slagen met `DEPLOY CHECK OK` en mogen niet in `fail2ban-client status sshd` verschijnen als verbannen. Mislukt een Deploy door de nieuwe instellingen: zet de drop-in terug (volgorde-regel f), meld.

## S2 — kernel-update en één herstart

Voorwaarden: S1 klaar of expliciet door Dennis overgeslagen; vijf controles groen; Dennis aanwezig.

1. `apt-get update`; toon `apt list --upgradable`; **simuleer** met `apt-get -s install linux-image-virtual linux-headers-virtual` (of de exacte pakketnamen): moet 0 te verwijderen pakketten tonen, geen releasewissel.
2. Installeer met `DEBIAN_FRONTEND=noninteractive apt-get -y -o Dpkg::Options::=--force-confold install …`. Let op `needrestart` (die herstartte op 6 okt automatisch `postgresql`): `/health` mag even `degraded` tonen en moet binnen ~10 s weer `ok` zijn; meld het als dat zo is.
3. Controleer dat de nieuwe kernel in `/boot` staat en dat `grub` hem als standaard heeft (alleen lezen).
4. **Eén `reboot`.** Meet de tijd tot SSH terug is (verwachting ~35 s, stop-grens 10 minuten: gebeurt dat niet, **stop en meld; Dennis gebruikt de DO-console of herstelt de snapshot**).
5. Controleer: `uname -r` (nieuwe kernel), geen `/var/run/reboot-required` meer, vier diensten actief (let op de opstartvolgorde: `valqeron` heeft `Wants=postgresql redis` en `Restart=always`), `fail2ban` actief, `ufw` actief met dezelfde regels, `/health` `ok`, certbot-timer actief, certificaten ongewijzigd, `scripts/check_cert_expiry.py` toont dezelfde dagen minus verstreken tijd, één Deploy via `workflow_dispatch` slaagt met `DEPLOY CHECK OK`, `/audit/verify` `valid` voor alle vijf organisaties.

## S3 — beperkte deploygebruiker voor de frontend (alleen met Dennis' publieke sleutel in de opdracht)

Doel: de frontend-pijplijn logt niet meer in als `root`. De backend-pijplijn blijft in dit batch op `root` (die draait `scripts/deploy.sh` met `systemctl`/`nginx`; een beperkte backend-gebruiker is een apart ontwerp, noteer het als open punt).

1. Fase 0: lees `ai-governance-frontend/.github/workflows/deploy.yml` en bepaal **exact** welke commando's op de server draaien (rsync naar `releases/<sha>/`, symlink-swap, opruimen van oude releases, eventueel een nginx-reload). **Is er root nodig voor iets anders dan schrijven in `/opt/valqeron-frontend` (bijvoorbeeld `nginx -s reload`): stop S3 en meld; niet oplossen met `sudo`-regels.**
2. Server: gebruiker `valqeron-fe` (geen wachtwoord, geen sudo, shell `/bin/bash` of `/usr/sbin/nologin` als dat met `rsync` over SSH werkt, kies en meld), eigenaar van `/opt/valqeron-frontend` (alleen die map; controleer de huidige eigenaar en rechten vóór `chown`, en meld welke bestanden veranderen); `~valqeron-fe/.ssh/authorized_keys` met Dennis' publieke sleutel en de opties `no-port-forwarding,no-agent-forwarding,no-X11-forwarding,no-pty`.
3. Frontend-repo, **in een aparte branch en commit** (`deploy-user-fe`): in `deploy.yml` de SSH-gebruiker van `root` naar `valqeron-fe` en, als de workflow `rsync --chown` of vergelijkbaar gebruikt, dat aanpassen; secret-**namen** niet wijzigen (`DEPLOY_SSH_KEY` blijft de naam; Dennis vervangt de **waarde** zelf). Merge pas **nadat** Dennis het secret heeft vervangen en dat in de chat bevestigt (handleiding B4); test daarna met `workflow_dispatch`: Deploy slaagt met `DEPLOY CHECK OK` en de live site laadt zonder CSP-fouten.
4. Nadat de nieuwe deploy bewezen werkt: **geef Dennis het commando om de oude frontend-sleutelregel (comment `frontend-ci`) uit `/root/.ssh/authorized_keys` te verwijderen**; **Claude Code verwijdert hem niet zelf** (Dennis' beslissing, na een tweede succesvolle Deploy). Dezelfde regel voor het oude GitHub-secret.

## Tests en lint

Geen applicatiecode, dus geen nieuwe pytest. Wel: `pytest -q -m "not codex"` en de portaaltests blijven groen als er in de repo's iets wijzigt (alleen `deploy.yml` en documentatie). Voeg `scripts/hardening_check.sh` toe (alleen lezen: toont `sshd -T`-waarden, `fail2ban-client status sshd` als aantallen, `uname -r`, reboot-required, ufw-status) zodat Cowork en Dennis dezelfde controle kunnen herhalen; geen geheimen, geen IP-lijsten.

## Productiecontrole (alleen lezen, behalve wat in S1 t/m S3 staat)

Na elke stap: `/health` `ok`; `DEPLOY CHECK OK` bij de testdeploys; `/audit/verify` `valid` voor alle vijf organisaties aan het eind; organisaties 1 t/m 5 ongewijzigd; een gewone inlog van een testgebruiker werkt (server-side token in geheugen, niet printen); geen wijziging aan wachtwoorden of gebruikers.

## Stopvoorwaarden

Stop en meld als: de snapshot-poort niet is gehaald of Dennis niet aanwezig is; een sshd-test (`sshd -t`) faalt of een nieuwe sleutel-sessie niet lukt (draai terug volgens regel f); de schijf boven 80% komt; apt iets wil verwijderen of een releasewissel voorstelt; de herstart langer dan 10 minuten duurt; een Deploy twee keer achter elkaar faalt; er een geheim (sleutel, wachtwoord, IP-lijst) in een bestand, log of chat zou moeten; de classifier iets blokkeert (niet omzeilen); S3 root nodig lijkt; iets gedaan zou moeten worden aan een andere server of aan de database. Bij een **gebruikslimiet**: werk het HERVAT-BLOK bij (welke stap S1 t/m S3, wat is al geïnstalleerd en actief, **of de herstart al is gedaan**), commit, push en stop netjes; Dennis typt later `continue`. **Een herstart wordt nooit half herhaald: staat er geen `reboot-required` meer, dan is hij gedaan.**

## Rapport

Fase 0-bevindingen en afwijkingen; per stap (S1, S2, S3) wat is gedaan en bewezen; aantallen van `fail2ban` (verbannen, mislukte pogingen) zonder IP-lijsten; effectieve sshd-waarden; kernelversie vóór en na; duur van de herstart; Deploy-run-id's; `/audit/verify` per organisatie; wat bewust **niet** is gedaan (SSH-poort, ufw, `PermitRootLogin no`, beperkte backend-deploygebruiker, back-up) en de open punten; CLAUDE.md (§2, §5, §6, §7) bijgewerkt met commit-hash; HERVAT-BLOK en `WERKLIJST.md` (status `KLAAR`) bijgewerkt; `NACHTRAPPORT.md`.

---

## Conceptprompt voor Claude Code (korte versie, Dennis plakt)

> Voer `claude-code-handoff-serverhardening.md` uit (repo-root, eerst `git pull`). `SNAPSHOT=ja`, snapshot gemaakt om [tijdstip]. Ik blijf beschikbaar met een tweede terminal en het DigitalOcean-paneel open. Mijn IP voor `ignoreip` (alleen lokaal, niet in git): [IP]. Publieke deploysleutel voor S3: [ssh-ed25519 AAAA… **of** "nog niet"]. Eén sessie. Geen geheimen in bestanden of chat, classifier-blokkades niet omzeilen, stop bij elke stopvoorwaarde, werk het HERVAT-BLOK na elke stap bij.
