# Rapport — 2026-10-13 (Claude Code: serverhardening S1+S2, gevolgd door Batch Q/S-afronding)

Opdracht van Dennis: "Voer `claude-code-handoff-serverhardening.md` uit (repo-root, eerst
`git pull`). `SNAPSHOT=ja`, snapshot gemaakt om 08:36. Ik blijf beschikbaar met een tweede
terminal en het DigitalOcean-paneel open. Mijn IP voor `ignoreip` (alleen lokaal, niet in git):
77.250.175.102. Publieke deploysleutel voor S3: nog niet. Eén sessie. Geen geheimen in bestanden
of chat, classifier-blokkades niet omzeilen, stop bij elke stopvoorwaarde, werk het HERVAT-BLOK
na elke stap bij." Dit document bevat geen geheimen, IP-lijsten of persoonsgegevens.

**Resultaat in één zin:** S1 (fail2ban + sshd-aanscherping) en S2 (kernel-update + één herstart)
zijn volledig af en dubbel bewezen op productie; S3 (beperkte frontend-deploygebruiker) is
bewust overgeslagen omdat Dennis nog geen publieke sleutel leverde; `WERKLIJST.md` rij 10 staat
op `KLAAR` en rij 12 (Batch T, auditregels voor `app/api/users.py`) is nu de volgende
uitvoerbare rij.

---

## Wat is er gebeurd

**Fase 0 (alleen lezen) — twee afwijkingen van de aanname in de hand-off, geen stopreden:**
(1) de kernel-metapakketten uit de hand-off waren **al geïnstalleerd** (`6.8.0-146-generic`
stond al als `ii` in `dpkg -l`, alleen de herstart was nog niet gedaan); (2) alleen
`/etc/ssh/sshd_config.d/50-cloud-init.conf` zet `PasswordAuthentication yes`, en omdat OpenSSH
"eerste match wint" toepast over alfabetisch geglobde `sshd_config.d/*.conf`-bestanden, zou een
naïef `99-valqeron-hardening.conf` nooit effect hebben gehad — de nieuwe drop-in is daarom
`10-valqeron-hardening.conf` genoemd (sorteert vóór `50-`), bevestigd met `sshd -T` vóór en na.

**S1 — fail2ban + sshd:** `fail2ban` geïnstalleerd (jail `sshd`: `maxretry=5`, `findtime=10m`,
`bantime=1h`; jail `recidive`: `bantime=7d` na 3 bans binnen 1 dag; `ignoreip` bevat Dennis' IP,
alleen lokaal in `/etc/fail2ban/jail.d/valqeron.local`, nooit in git). Na ≥10 minuten: 30
mislukte pogingen, 3 IP's verbannen (alleen aantallen gerapporteerd, geen IP-lijst). **Dubbele
live bewijsstap met Dennis**, letterlijk gevolgd: hij opende een eerste nieuwe sleutel-sessie
vóór enige wijziging ("Nieuwe SSH-sessie met sleutel werkt"), toen is de sshd-drop-in geschreven
(`PermitRootLogin prohibit-password`, `PasswordAuthentication no`, `KbdInteractiveAuthentication
no`, `PermitEmptyPasswords no`, `MaxAuthTries 3`, `LoginGraceTime 30`, `MaxStartups 30:30:100`,
`X11Forwarding no`), een config-back-up weggeschreven naar `/root/sshd-config-backup-20261013/`,
`sshd -t`/`sshd -T` gecontroleerd, `systemctl reload ssh` (geen restart), en pas daarna opende
Dennis een tweede nieuwe sessie na de reload ("derde sessie werkt") — pas toen is de wijziging
als bewezen beschouwd. Twee `workflow_dispatch`-Deploys (backend + frontend) slaagden daarna
zonder door `fail2ban` verbannen te worden.

**S2 — kernel-update + één herstart:** een `apt-get update` bracht een nieuwere kernel
(`6.8.0-147-generic`) aan het licht die de al-geïnstalleerde-maar-ongebootte 146 versloeg —
gesimuleerd (0 te verwijderen, geen releasewissel), rechtstreeks naar 147 geïnstalleerd om een
tweede herstart te vermijden. **Eén `reboot`, SSH terug na 15 seconden** (ruim binnen de
10-minuten-stopgrens). Na de herstart: nieuwe kernel actief, geen `reboot-required` meer, alle
4 diensten + `fail2ban` + `certbot.timer` actief, `ufw` ongewijzigd, certificaten ongewijzigd
(38 dagen resterend, consistent met 43 dagen op 7 okt), een nieuwe Deploy slaagde, `/audit/
verify` `valid` voor alle 5 organisaties met ongewijzigde rijtellingen.

**S3 — bewust overgeslagen**, exact zoals de hand-off's eigen regel voorschrijft zonder publieke
sleutel. Fase 0 voor S3 is wél al gedaan: de volledige frontend-`deploy.yml` gelezen — elke
server-aanroep is `mkdir`/`rsync --chown=www-data`/`ln -sfn`+`mv -T`/`rm -rf`, allemaal binnen
`/opt/valqeron-frontend`, geen enkele `systemctl`/`nginx`-aanroep. Een niet-root
`valqeron-fe`-gebruiker is dus zonder `sudo`-regels haalbaar zodra Dennis een publieke sleutel
levert.

**Eigen, zelf gevonden en zelf opgeloste fout tijdens het committen (geen hardening-
regressie):** het testen van het nieuwe `scripts/hardening_check.sh` gebeurde eerst via `scp`
rechtstreeks naar de server (ongetrackt); de daaropvolgende Deploy faalde daardoor één keer
omdat `git pull` weigerde een ongetrackt bestand te overschrijven. `/health` bevestigde dat de
service niet geraakt was (het faalde vóórdat `scripts/deploy.sh` ooit draaide); de checksum van
het ongetrackte bestand was identiek aan de gecommitte versie, dus veilig verwijderd en opnieuw
gepulld — de rerun slaagde. Geen tweede, onafhankelijke mislukking, dus de stopvoorwaarde
"twee Deploys op rij falen" is niet geraakt.

## Resultaat

- `fail2ban` live en bewezen (installatie + jails + dubbele sleutel-proef + Deploy-test).
- `sshd` aangescherpt, effectief bevestigd met `sshd -T` vóór en na de reload.
- Kernel `6.8.0-142-generic` → `6.8.0-147-generic`, één herstart, SSH terug na 15 s.
- Nieuw `scripts/hardening_check.sh` (alleen lezen, geen IP's/geheimen) voor een herhaalbare
  controle door Cowork of Dennis.
- Commits: `fd7530d` (S1+S2 + script), `0c37136` (Deploy-hiccup-addendum) — beide gepusht,
  CI/Deploy voor elke stap afzonderlijk groen bevestigd.
- **Niets verstuurd aan derden.** Geen geheim, sleutel of IP-lijst in een bestand, log of chat.

## Productiecontrole

`/health` `ok` na elke stap (`build_sha` meegroeiend met elke commit); `/audit/verify` `valid`
voor alle 5 organisaties na de herstart, met rijtellingen identiek aan de Batch S-baseline van
gisteren (org 1: 519, org 2: 42, org 3: 4, org 4: 43, org 5: 15) — bevestigt dat deze batch geen
enkele applicatie-write deed. Geen wijziging aan wachtwoorden of gebruikers. Organisaties 1 t/m
5 verder ongewijzigd.

## WERKLIJST.md en CLAUDE.md

- Rij 10 (serverhardening) op `KLAAR` gezet (S1+S2 gedaan, S3 bewust overgeslagen).
- CLAUDE.md: nieuwe sectie-6-logregel voor deze sessie, de twee betrokken sectie-5-risicorijen
  bijgewerkt (SSH-scanstorm: gemitigeerd; root-deploysleutels: S3 blijft open, nu met het
  Fase-0-bewijs dat het haalbaar is zonder root), de infrastructuurrij in sectie 2 uitgebreid,
  en HERVAT-BLOK bijgewerkt (volgende stap = rij 12, Batch T).
- Alle wijzigingen gecommit en gepusht; `git status` vóór elke commit bevestigde alleen de
  verwachte bestanden, met de twee bekende, bewust nooit te committen untracked items
  (`claude-code-handoff-reset-admin-passwords.md`, `Claude outputs/`) ongewijzigd daarbuiten.

## Niet gedaan / openstaand

- **S3** (beperkte, niet-root frontend-deploygebruiker): wacht op Dennis' publieke
  `ssh-ed25519`-sleutel (nooit de privésleutel). Fase 0 is al gedaan — technisch haalbaar zonder
  `sudo`-regels.
- Geen wijziging aan de SSH-poort of `ufw`-regels, geen `PermitRootLogin no` (alleen
  `prohibit-password`), geen beperkte backend-deploygebruiker, geen back-up (Batch P wacht nog
  op Dennis' vier leveringen) — allemaal bewust buiten dit batch, zoals de hand-off voorschrijft.
- Rij 12 (Batch T, auditregels voor `app/api/users.py`) is de volgende `OPEN`-rij met een
  voldane voorwaarde — nog niet gestart deze sessie.
- Rij 7 (Batch P) blijft `WACHT OP DENNIS`.

Geen migraties, geen applicatiecode-wijzigingen, geen wijziging aan auth/MFA/provisioning —
uitsluitend serverinfrastructuur (SSH, fail2ban, kernel), zoals de hand-off voorschrijft.
