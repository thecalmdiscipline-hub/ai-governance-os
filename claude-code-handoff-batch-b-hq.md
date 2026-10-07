# Handoff voor Claude Code — Batch B: productie inventariseren, HQ-tenant vaststellen, worker-crash diagnosticeren

Context: `claude/dogfood-portal-onboarding-plan.md` (taak 0.7, besluit D1) en `claude/executieplan-fase-0-1.md` (Batch B) in het projectdocument. Batch A is af (commits `64bf1ac`, `bd53e81`, `836404c`). Dit is de eerste batch met een **beslismoment voor Dennis**: welke organisatie in productie wordt "Valqeron HQ" (tenant 0)? Jij mag dat niet zelf beslissen. Deze taak heeft daarom **twee fasen met een harde stop ertussen**.

Standaardafspraken blijven gelden: begin met `git status`/`git diff` (drift-check, CLAUDE.md sectie 7), eindig met testeisen + CLAUDE.md-update (onderaan). Fase 1 en 2 hieronder zijn **read-only** op productie tot Dennis expliciet kiest.

---

## Fase 1 — Read-only inventarisatie van productie (geen schrijfacties)

Zelfde aanpak als bij de PII-verificatie en de audit-HMAC-controle van Batch A: via SSH, een eenmalig script dat alleen `SELECT` doet. Geen wijzigingen, geen commits van dit script met echte data erin.

Rapporteer, per organisatie:

1. `id`, `name`, land, sector (indien kolommen bestaan), aanmaakdatum indien beschikbaar.
2. Aantal gebruikers per organisatie, met per gebruiker: `username`, rol, actief ja/nee. **Nooit wachtwoord(hash)-waarden tonen of loggen.**
3. Actieve modules per organisatie (`TenantModule.is_active=True`), en welke van de 11 `BASE_MODULES` ontbreken.
4. Rijaantallen per organisatie in de tabellen waar bedrijfsdata staat (workflow-runs / documenten / audit_logs / corrective actions of wat er bestaat). Doel: kunnen zien of een organisatie **echte klantdata** bevat of alleen test/demodata. Toon aantallen, geen inhoud.
5. Bestaat er een organisatie "ISO Cert International"? (Er ligt een aparte hand-off `claude-code-handoff-iso-cert-demo-org.md` van een andere Cowork-sessie; onbekend of die al is uitgevoerd.) Noteer ja/nee + id. Als die hand-off nog niet is uitgevoerd: **doe die hier niet mee**, dat is een aparte opdracht van Dennis.
6. Is er in `.env` op productie al een `HQ_ORGANIZATION_ID`? (Alleen zeggen of de sleutel bestaat en de waarde; het is geen geheim.) Verwacht: nee.

Geef bij de rapportage een korte **aanbeveling** voor de HQ-keuze, gebaseerd op de data:
- Als org 1 ("Valqeron / tenant 1") alleen eigen/test-data bevat en geen klantdata: aanbeveling = org 1 wordt HQ. Dat is het meest logisch en het goedkoopst.
- Als org 1 wel klant- of prospectdata bevat, of gebruikers heeft die geen Valqeron-medewerker zijn: aanbeveling = nieuwe aparte HQ-organisatie, want tenant 0 moet schoon zijn (besluit D1/D5: het HQ ziet nooit per ongeluk klantcontent).
- Noem expliciet wat je niet kon vaststellen.

## Fase 2 — Read-only diagnose van de uvicorn-worker-crash

Bij Batch A crashte op productie een uvicorn-worker (502) nadat spaCy was geladen; dat staat in CLAUDE.md sectie 5 als onverklaard risico. Dit is een echt risico voor Batch E/F (control plane) omdat de eerste request per worker na elke deploy het lazy spaCy-model laadt. Doel hier: **verklaren, niet fixen.**

Verzamel (allemaal read-only):

1. `journalctl -u valqeron --since <tijdstip Batch A-deploy - 30 min>` rond het crashmoment: exit-code/signaal van de worker (SIGKILL = waarschijnlijk OOM-killer, SIGSEGV = native-library-crash, Python-traceback = applicatiefout).
2. `dmesg -T | grep -i -E "killed process|out of memory|oom"` (en `journalctl -k` als dmesg beperkt is).
3. Geheugenbeeld nu: `free -m`, `swapon --show`, `systemctl status valqeron` (geheugen/tasks), RSS per uvicorn-proces (`ps -o pid,rss,cmd -C uvicorn` of vergelijkbaar), **vóór** en **na** één request die spaCy triggert (bijv. één PII-verwerkende workflow-run op de demo-tenant, dat is een bestaande, onschuldige actie). Noteer hoeveel MB het laden van de modellen per worker kost en hoe lang het duurt.
4. Configuratie ter referentie: `systemd/valqeron.service` heeft `--workers 2`, `Restart=always`, `RestartSec=5`, geen geheugenlimiet. Droplet: 1,9 GB RAM + 4 GB swap. Python-versie in de venv en de versies van `spacy`, `thinc`, `presidio-analyzer` (`pip list | grep -i -E "spacy|thinc|presidio|numpy"`).
5. Kwantitatieve conclusie: past `2 workers × RSS-na-model-laad` in RAM? Zo niet, hoeveel swap wordt er dan gebruikt en is dat de plausibele oorzaak?

Werk-hypothesen (nog niet geverifieerd, niet als feit rapporteren): (a) 2 workers × ~1,5 GB modellen op 1,9 GB RAM → OOM-killer of swap-thrashing; (b) native-library-instabiliteit van spaCy/thinc op de gebruikte Python-versie; (c) iets anders. Zeg per hypothese of je bewijs voor of tegen hebt gevonden.

Geef daarna **opties met afwegingen, zonder ze uit te voeren**, bijvoorbeeld: warm-up van de modellen bij opstart (dan crasht het bij deploy in plaats van bij de eerste klantrequest), `--workers 1`, een grotere droplet, of een kleiner spaCy-model. Dennis kiest; dit raakt kosten.

---

## STOP — rapporteer aan Dennis en wacht op zijn keuze

Lever één rapport (in CLAUDE.md sectie 6 én als antwoord aan Dennis) met: de inventarisatie uit fase 1, de HQ-aanbeveling, de diagnose uit fase 2 met opties. **Doe daarna niets op productie tot Dennis schrijft welke organisatie HQ wordt** ("org 1" of "nieuwe org") en of hij een van de crash-opties wil.

## Fase 3 — Pas ná Dennis' keuze: HQ inrichten

Alleen via bestaande endpoints/functies, geen nieuwe code voor het inrichten zelf:

1. **Als org 1:** controleer dat de naam klopt (bijv. "Valqeron HQ" — pas alleen de naam aan als Dennis dat wil), zorg dat **alle 11 `BASE_MODULES`** actief zijn (`TenantModule`, `is_active=True`), en dat er een super-admin/admin-gebruiker van Valqeron in zit.
   **Als nieuwe org:** maak hem aan via het bestaande `POST /organizations` (super-admin) of de bestaande functie daarachter, kies het eerstvolgende vrije `organization_id` (controleer eerst, neem niets aan), wijs alle 11 modules toe en maak minimaal één admin-gebruiker aan via `POST /users` of het bestaande patroon (zoals bij `dennis_admin`/`customer2_admin` op 18 sep).
2. Wachtwoorden: zelf genereren en **rechtstreeks aan Dennis geven (chat), nooit in CLAUDE.md, in deze hand-off of in een ander git-getrackt bestand.**
3. Zet `HQ_ORGANIZATION_ID=<id>` in de productie-`.env` (niet in git), en voeg de sleutel toe aan `.env.example` **zonder waarde** (of met een placeholder) als dat bestand bestaat. Voeg een kleine, geteste config-toegang toe in de bestaande config-module als die er nog niet is (lezen van `HQ_ORGANIZATION_ID`, `None` als niet gezet). Verder geen gebruik ervan bouwen: dat komt in Batch E/F.
4. Herstart de service pas na controle dat er geen deploy loopt, en controleer daarna `https://api.valqeron.com/health`.
5. Verifieer met een **echte** `POST /login` tegen `https://api.valqeron.com` met de HQ-admin, en `GET /audit/verify` voor de HQ-organisatie: verwacht `valid`. Niet alleen aannemen dat de DB-write is gelukt.

## Niet doen
- Geen schrijfacties op productie in fase 1 en 2. Geen wachtwoord(hash)s in output of logbestanden. Geen klantcontent (alleen aantallen).
- Geen bestaande organisaties, gebruikers of audit-regels wijzigen of verwijderen. Geen crash-oplossing doorvoeren zonder Dennis' keuze.
- Niet de ISO Cert-demo-org aanmaken in het kader van deze taak.
- Niet stilzwijgend afwijken; als iets niet klopt met deze beschrijving, stoppen en terugkoppelen.

## Afsluiting (verplicht)
1. **Testeisen:** volledige suite groen lokaal én in CI (`pytest -q -m "not codex"`, huidig totaal 122; noteer het nieuwe totaal). Als je een config-toegang voor `HQ_ORGANIZATION_ID` toevoegt: unit-tests voor "niet gezet → None", "gezet → int", "ongeldige waarde → duidelijke fout". Na deploy: CI én Deploy groen via de GitHub Actions-API controleren, niet alleen lokaal.
2. **CLAUDE.md bijwerken:** sectie 5 (crash-risicorij: diagnose, status open/opgelost, gekozen optie), sectie 6 (inventarisatie-samenvatting zonder gevoelige data, HQ-besluit met organization_id, echte login/verify-uitvoer), sectie 7 (volgende stap: Batch C uit `claude/executieplan-fase-0-1.md`, en Batch D). Verifieer na de commit dat de CLAUDE.md-wijziging blijft staan (drift-patroon).
