# Hand-off Batch Q — maandrapportage per tenant (MVP, NL en EN, alleen tellingen)

Auteur: Cowork (architect). Uitvoerder: Claude Code, **één sessie, meerdere fasen**. Datum: 12 okt 2026. Kan **zonder toezicht**: lees de stopregels. Repo: `ai-governance-os` (map `tools/report/`, scripts in `scripts/`). Ontwerp en motivering: `claude/maandrapportage-ontwerp.md` (project) — dit document is de uitvoerbare versie. **Voorwaarde:** Batch M (handout-generator) is `KLAAR`, zodat stijl, rendering en kwaliteitscontroles hergebruikt worden. Cowork zet de WERKLIJST-rij op `OPEN` zodra dat zo is.

## Waarom

De onboarding-taak "Eerste maandelijkse gebruiksrapportage verstuurd" (klantzichtbaar, `standard-v1`, taak 8,2) en het pakket ("monthly usage reporting") beloven een maandrapport. Er is **geen rapportagefunctie** (CLAUDE.md: geen treffers op usage-/maandrapportage; er is ook geen jobqueue of planner). Dit batch levert een alleen-lezen datascript en een renderer, **alleen tellingen en statussen, nooit klantinhoud**. Dennis verstuurt de rapporten zelf. Er wordt **niets verzonden** en niets in het portaal gebouwd.

## Vooraf besloten (niet opnieuw voorleggen)

- **Alleen tellingen en statussen.** Geen run-uitvoer, documentnamen, gebruikersnamen, e-mailadressen, bedragen, kandidaten of vrije tekst. Geen aantallen per persoon, alleen totalen.
- **Geen taalmodel in de rapportketen.** Tekst komt uit sjablonen en cijfers. Het blok "Volgende stappen" (2 tot 3 zinnen) komt uit een per-klant configbestand dat Dennis zelf invult; ontbreekt het, dan blijft het blok leeg met de standaardzin ("Neem contact op voor een bespreking van deze cijfers").
- **Geen migratie, geen nieuwe kolom, geen wijziging aan auth, MFA, provisioning, ops-code of bestaande endpoints.** "Laatste login" is bewust **geen** onderdeel (er is geen bron). Zit het cijfer toch in iemands verwachting: niet bouwen, melden.
- **Alleen lezen op productie:** `SELECT COUNT` en `GROUP BY` via een bestaand alleen-lezen pad of op de server; een server-side gemunt token **alleen in geheugen**, nooit in een bestand of log, nooit geprint. Het script schrijft niets naar de database. Geen auditregel (Dennis besliste dit niet; standaard **nee**).
- **Periode:** kalendermaand `JJJJ-MM`; het script weigert als de rapportdatum niet ná het einde van de periode ligt.
- **Uitvoer:** PDF NL en EN, A4, dezelfde lichte, printvriendelijke stijl als de handout (`docs/handout/handout-inhoud-concept.md` §5, tokens uit het portaal). Bestandsnaam `Valqeron-Maandrapport_<tenant-slug>_<JJJJ-MM>_<nl|en>.pdf` in een **gitignored** map (hergebruik `handouts/` of maak `reports/`; meld welke). Het tussen-JSON (alleen cijfers) staat daar ook en niet in git.
- **Concept-markering:** zolang `contact.json` ontbreekt (zie Batch M) draagt het rapport op elke pagina "CONCEPT, contactgegevens ontbreken" / "DRAFT, contact details missing" en maakt de generator geen definitieve uitvoer.
- **Eerste doeltenant:** organisatie 1 (HQ, eigen register). Voorbeeldrapporten alleen voor organisatie 1 en voor de fictieve demotenant organisatie 5 ("Atlas Demo B.V."); **nooit** voor organisatie 2, 3 of 4 of een echte klant tenzij Dennis dat vraagt.
- **Dennis verstuurt zelf**, via zijn eigen e-mail; Valqeron heeft geen e-mailautomatisering voor klantrapporten.

## Werkwijze

0. **Hervatten:** lees eerst het HERVAT-BLOK in `CLAUDE.md` en `WERKLIJST.md`; ga door bij de eerste onvoltooide fase. Elke fase is veilig opnieuw te draaien (vaste uitvoernamen).
1. `git pull`, `git status`, `git diff` (drift-check; verwacht Batch M in `CLAUDE.md` als `KLAAR`). Meld afwijkingen.
2. **Fase 0 (alleen lezen), eerste alinea van je rapport:** de echte kolommen en statuswaarden van `workflow_runs` (module- of workflowsleutel, status, tijdstip, `organization_id`), `documents` (organisatie, aanmaakdatum), `support_requests` (organisatie, status `new/in_progress/done`, aanmaakdatum), `ai_incidents`, `corrective_actions` (status, `due_date` sinds Batch O2), `ai_risks`, `ai_systems`, `audit_logs` (organisatie, tijdstip); of `GET /workflows/dashboard` de tellingen per maand kan geven; of er al een alleen-lezen pad per tenant bestaat voor tellingen; hoe de handout-pijplijn rendert (Jinja, headless Chromium, stijl, kwaliteitscontroles, `contact.json`-poort); welke modules actief zijn per tenant (`GET /ops/tenants/{id}/modules` of de tenant-tabel); of `workflow_runs.status` de waarde "degraded" kent en hoe. **Wijkt iets af van het ontwerp: stoppen en melden; verzin geen kolom en leid geen cijfer af uit vrije tekst.**
3. Kleine losse commits per fase; na elke push CI en Deploy controleren (`DEPLOY CHECK OK`) waar van toepassing (dit batch raakt productie alleen lezend; Deploy-wijzigingen zijn alleen scripts en `tools/`).

## Bouw

**Q1 — Data.** `scripts/monthly_report_data.py --org <id> --month JJJJ-MM [--out <pad>]`: alleen `SELECT` met `COUNT` en `GROUP BY`; schrijft een klein JSON-bestand met uitsluitend de cijfers volgens de tabel hieronder (sleutels vast, geen tekst uit klantdata). Drukt dezelfde cijfers ook als leesbare tekst in de console voor een handmatige steekproef.

| # | Onderdeel | Cijfer | Bron (Fase 0 bevestigt) |
|---|---|---|---|
| 1 | Voorblad | tenantnaam, tier, periode, taal, opmaakdatum | tenantrij of ops-tenantgegevens; alleen metadata |
| 2 | Runs per module | aantal runs per actieve module en totaal | `workflow_runs` gegroepeerd per module en maand |
| 3 | Succes en fouten | aantal geslaagd, mislukt en "degraded" per module | `workflow_runs.status`; zet de uitleg van "degraded" op het rapport: de anonimisering was niet beschikbaar en het verzoek ging niet naar het model |
| 4 | Documenten | totaal en nieuw in de maand | `documents`; alleen als Document Knowledge actief is |
| 5 | Supportverzoeken | ingediend in de maand, afgehandeld (`done`) | `support_requests`; nooit onderwerp of bericht |
| 6 | Governance | open incidenten, openstaande corrigerende maatregelen (en verlopen deadlines), aantal AI-systemen en risico's | governance-tabellen; alleen tellingen per status |
| 7 | Auditlog | aantal geregistreerde acties in de maand; integriteit `valid` of `niet valid` op rapportdatum | telling `audit_logs`; `/audit/verify` (alleen lezen) |
| 8 | Onboarding | voortgang per fase, alleen zolang het traject loopt | `/onboarding/progress`-logica of de tabellen |
| 9 | Volgende stappen | 2 tot 3 vaste zinnen uit config | `tools/report/config/<tenant>.json` |

**Q2 — Renderer.** `tools/report/template_nl.html` en `template_en.html`; `scripts/generate_monthly_report.py --data <json> --lang nl|en --out <map> [--contact contact.json] [--next-steps <config>]`. Eén A4-pagina plus bijlage; per cijfer een bronvermelding in een voetnoot ("Bron: runs-register, telling per module"). Gebruik de handout-pijplijn (zelfde tokens, kop- en voettekst, afbreekregels, rendercheck).

**Q3 — Kwaliteitscontroles (blokkerend, in `tools/report/checks.py`).**
1. **Verboden woorden** (zoals handout, NL en EN, ontkenningen toegestaan) plus specifiek: geen "we monitoren continu", "alles veilig", "voldoet aan", "gegarandeerd", "volledig", "automatisch", "gecertificeerd", "AI-prestaties", "besparing".
2. **Bronvermelding:** elk cijfer heeft een bron (tabel, filter, periode); geen bron = geen cijfer.
3. **Geen klantinhoud:** een test scant de gegenereerde PDF-tekst **en** het JSON-bestand op e-mailadressen, telefoonnummers, namen uit de demodata, bestandsnamen en `<…>`-placeholders; een treffer breekt de build.
4. **Periodecontrole:** rapportdatum ligt na het einde van de periode, anders weigert het script.
5. **Rendercheck:** pagina's naar PNG; geen lege pagina's, geen losse onderschriften, geen kop als laatste regel.
6. **Steekproef:** het script drukt twee cijfers ook als tekst; Claude Code vergelijkt ze met een eigen, handmatige telling in de database (alleen lezen) en noemt het resultaat in het rapport.
7. **Contactpoort:** ontbreekt `contact.json`, dan alleen concept met markering op elke pagina.

**Q4 — Voorbeelden.** Genereer voor organisatie 1 (en de demotenant organisatie 5) over de laatste volledige kalendermaand een rapport in NL en EN. Zet `reports/LEES-MIJ-DENNIS.md` met: wat is gecontroleerd, wat Dennis moet lezen vóór verzending, de openstaande beslissingen uit het ontwerp (§7: cijferlijst akkoord? eerste rapportmaand per klant; verzendmoment; wat staat in de DPA over rapportage; bewaartermijn lokale rapporten, voorstel 24 maanden). Geen geheimen.

## Tests

`pytest -q -m "not codex"` volledig groen, plus nieuwe tests voor: de periodecontrole, de afwezigheid van klantinhoud (tests met een gevulde testdatabase met herkenbare nepdata), het verboden-woordenfilter, de volledigheid van bronvermeldingen, en dat een lege maand (nul runs) een geldig rapport met nullen oplevert. Lint volgens het project. Geen portaaltests (geen portaalwijziging).

## Productiecheck (alleen lezen)

De tellingen voor organisatie 1 vergelijken met een handmatige telling; `/audit/verify` `valid` voor alle vijf organisaties; organisaties 1 t/m 5 ongewijzigd; geen nieuwe rijen, geen nieuwe gebruikers; geen schrijfacties.

## Stopvoorwaarden

Stop en meld als: een migratie of nieuwe kolom nodig lijkt; een cijfer uit vrije tekst of uit run-uitvoer zou moeten komen; een token, wachtwoord of geheim in een bestand, log of chat zou moeten; de classifier iets blokkeert (niet omzeilen); een claim in een zin geen bron heeft; tests rood; een Deploy twee keer achter elkaar faalt; de schijf boven 80%; een rapport voor een andere organisatie dan 1 of 5 gevraagd lijkt. Bij een **gebruikslimiet**: werk het HERVAT-BLOK bij (welke fase Q1 t/m Q4, welke bestanden bestaan), commit, push en stop netjes; Dennis typt later `continue`.

## Rapport

Fase 0-bevindingen en afwijkingen van het ontwerp; commits (hash en doel), CI-/Deploy-run-id's; testaantallen vóór en na; per kwaliteitscontrole wat hij vond; de uitkomst van de steekproef; paginatal per voorbeeld-PDF; welke cijfers uit de lijst **niet** konden en waarom; Dennis' openstaande beslissingen; CLAUDE.md (§2, §5, §6, §7) bijgewerkt met commit-hash; HERVAT-BLOK en `WERKLIJST.md` (status `KLAAR`) bijgewerkt. Geen PDF's in git, niets verzonden.
