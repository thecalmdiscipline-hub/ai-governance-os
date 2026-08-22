# Deploy Recovery — 165.22.204.23 (api./compliance.valqeron.com)

**Status op 2026-08-19:** vanuit deze omgeving is er **geen** toegang tot de droplet — geen `doctl`
geïnstalleerd, geen DigitalOcean API-token in `.env`, en de lokale SSH-key (`~/.ssh/id_ed25519`,
fingerprint `SHA256:CKXgE3WqnAxCorYUu3cfcr0f30e6R2SbeAMYYCYhWWk`) kreeg een `Operation timed out`
op poort 22 — dus zelfs als deze key ooit was toegevoegd, is er nu geen antwoord van de host.
`curl -I https://compliance.valqeron.com/` en `https://api.valqeron.com/health` timeoutten beide
na 10s (connectie komt niet tot stand, geen HTTP-response, geen RST). Dit bevestigt de eerdere
bevinding in `CLAUDE.md` sectie 2/5: de droplet reageert op geen enkel getest protocol.

Er is dus **geen root cause vanuit deze sessie vast te stellen** — het kan een uitgezette/gedecommissioneerde
droplet zijn, een crashte VM, of een DigitalOcean cloud firewall die alle inbound verkeer blokkeert
(inclusief SSH). Onderstaande stappen moeten door Dennis zelf via de DigitalOcean-webconsole
(cloud.digitalocean.com) worden uitgevoerd, omdat er geen programmatische toegang beschikbaar is.

---

## Stap a — Checken of de droplet aan staat

1. Log in op https://cloud.digitalocean.com
2. Ga naar **Droplets** in het linkermenu.
3. Zoek de droplet met IP `165.22.204.23` (waarschijnlijk genaamd iets als `valqeron`, `valqeron-prod` of vergelijkbaar).
4. Kijk naar de status-indicator:
   - **Groen "Active"** → de VM zelf draait; het probleem zit in de OS/services óf in de firewall (ga naar stap c/d hieronder).
   - **Grijs/"Off"** → de droplet is uitgeschakeld. Klik **Power On** (rechtsboven, of via het "⋮"-menu naast de droplet in het overzicht).
   - **Droplet bestaat niet meer / is niet te vinden** → dan is hij op enig moment verwijderd. Dat is geen "restart"-scenario meer maar een her-provisioning — meld dit terug, want dan is `scripts/setup_server.sh` opnieuw nodig op een nieuwe droplet, en moeten DNS-records (A-records voor `api.`, `app.`, `compliance.valqeron.com`) worden bijgewerkt naar het nieuwe IP.

Kijk ook meteen op het tabblad **Graphs** van de droplet (CPU/Disk/Bandwidth) — een vlakke lijn op 0% over de laatste dagen is een sterke aanwijzing dat de VM al langere tijd stil staat of uit is.

---

## Stap b — Inloggen via de DigitalOcean recovery console (niet SSH)

SSH werkt niet vanaf hier, dus gebruik de browser-based console die DigitalOcean altijd aanbiedt, ongeacht firewall-instellingen:

1. Open de droplet-detailpagina (klik op de droplet-naam in het overzicht).
2. Klik op de tab **Access** in het linkermenu van de droplet-pagina.
3. Klik op **Launch Droplet Console** (soms genaamd "Launch Recovery Console"). Dit opent een terminal-venster in de browser die rechtstreeks op de VM inlogt via DigitalOcean's eigen infrastructuur — dit werkt zelfs als de firewall alle SSH-verkeer van buitenaf blokkeert.
4. Log in als `root` met het wachtwoord dat je hebt ingesteld bij het aanmaken van de droplet, of gebruik **Reset Root Password** op dezelfde Access-pagina als je het wachtwoord niet meer weet (DigitalOcean mailt dan een tijdelijk wachtwoord, en je moet de droplet daarna rebooten om het door te laten voeren).

---

## Stap c — Status checken in de recovery console

Zodra je een prompt hebt in de recovery console, draai deze commando's één voor één:

```bash
# 1. Leeft de machine, en hoe lang staat hij al aan/uit?
uptime

# 2. Draait de Valqeron-service?
systemctl status valqeron --no-pager

# 3. Recente logs van de service (laatste 100 regels)
journalctl -u valqeron -n 100 --no-pager

# 4. Draait nginx?
systemctl status nginx --no-pager

# 5. Is de nginx-config geldig?
nginx -t

# 6. Luistert er iets op poort 8000 (de FastAPI-app) en 80/443 (nginx)?
ss -tlnp | grep -E ':8000|:80|:443'

# 7. Is de firewall op OS-niveau (ufw) actief en wat laat hij door?
ufw status verbose

# 8. Draait Redis (verplicht in productie, zie CLAUDE.md sectie 2)?
systemctl status redis-server --no-pager
```

**Wat te verwachten / hoe te interpreteren:**
- Als `systemctl status valqeron` **"inactive (dead)"** of **"failed"** toont → de service is gestopt of gecrasht. Ga naar Stap d.
- Als `ss -tlnp` niets toont op poort 8000 → de uvicorn-workers draaien niet, ook al zegt systemd misschien "active" (kan een stuck/zombie state zijn) → herstart alsnog (Stap d).
- Als nginx niet draait of `nginx -t` een fout geeft → `systemctl restart nginx` na het oplossen van de config-fout uit de foutmelding.
- Als `ufw status` alles blokkeert behalve wat er expliciet is toegestaan, en poort 80/443 niet in de allow-lijst staat → dat verklaart waarom extern verkeer (inclusief de sandbox-test van gisteren) nergens aankomt, ook al draait de service prima lokaal. Fix: `ufw allow 80/tcp && ufw allow 443/tcp && ufw allow 22/tcp` (pas aan naar wat je daadwerkelijk open wilt hebben) gevolgd door `ufw reload`.

---

## Stap d — Service(s) herstarten

```bash
# Herstart de Valqeron-app
systemctl restart valqeron
sleep 2
systemctl status valqeron --no-pager

# Herstart nginx (alleen als nginx -t hierboven geen fouten gaf)
systemctl restart nginx
systemctl status nginx --no-pager

# Lokale check vanaf de droplet zelf — moet een HTTP-response geven, geen timeout
curl -I http://127.0.0.1:8000/health
curl -I http://127.0.0.1/
```

Als `curl -I http://127.0.0.1:8000/health` vanaf de droplet zelf wél een response geeft, maar
`https://api.valqeron.com/health` van buitenaf nog steeds timeout, dan zit het probleem **niet**
in de applicatie maar in de **DigitalOcean Cloud Firewall** (netwerkniveau, niet `ufw` op de VM zelf) — zie Stap 4 hieronder.

---

## Stap 4 — DigitalOcean Cloud Firewall checken

Dit is een aparte laag bovenop de droplet (niet hetzelfde als `ufw` binnenin de VM) en kan
inbound verkeer blokkeren nog vóórdat het de VM bereikt — dit zou verklaren waarom zowel de
SSH-test als de HTTP-tests van gisteren en vandaag zonder enige respons (geen RST, pure timeout)
bleven hangen, wat typisch is voor "silently dropped by a cloud firewall" in plaats van "poort dicht op de VM".

1. Ga in het linkermenu naar **Networking → Firewalls**.
2. Kijk of er een firewall gekoppeld is aan de `165.22.204.23`-droplet.
   - **Geen firewall gekoppeld** → dan is dit niet de oorzaak, ga terug naar Stap c/d.
   - **Wel gekoppeld** → open 'm en controleer de **Inbound Rules**:
     - Staat poort 22 (SSH) open voor "All IPv4/IPv6" of een specifieke IP-range? Als je eigen IP (of dat van deze sandbox-omgeving) niet in de allowlist staat, wordt SSH stilletjes gedropt — dat verklaart de `Operation timed out` hierboven.
     - Staat poort 80 en 443 (HTTP/HTTPS) open voor "All IPv4/IPv6"? Zo niet, voeg een inbound rule toe: **HTTP** (poort 80) en **HTTPS** (poort 443), source = "All IPv4" + "All IPv6".
3. Sla de firewall-rules op — wijzigingen zijn direct actief, geen reboot nodig.

---

## Verificatie (vanaf je eigen laptop of deze sandbox-omgeving, niet vanaf de droplet)

Zodra bovenstaande stappen zijn doorlopen:

```bash
curl -I https://compliance.valqeron.com/
curl -I https://api.valqeron.com/health
```

Beide moeten een HTTP-statuscode teruggeven (200, 301, 404 — maakt niet uit, als het maar geen
timeout meer is). Meld het resultaat terug zodat `CLAUDE.md` sectie 2 bijgewerkt kan worden naar
een bevestigde live-status.

---

## Als de droplet niet meer bestaat of niet meer te herstellen is

Als blijkt dat de droplet is verwijderd of zo beschadigd is dat een reset nodig is:
1. Nieuwe droplet aanmaken (Ubuntu, zelfde specs als voorheen).
2. `scripts/setup_server.sh` gebruiken als basis voor de herinrichting (installeert nginx, certbot, de systemd-service, etc. — zie comments bovenin dat script voor de volgorde).
3. DNS A-records voor `api.`, `app.`, `compliance.valqeron.com` bijwerken naar het nieuwe IP bij je DNS-provider.
4. `.env` met productie-secrets (die zijn niet in de repo, zie `.env.example` voor de vereiste keys) opnieuw op de nieuwe droplet zetten.
5. `scripts/deploy.sh` draaien om de app te deployen.
