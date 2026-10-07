# Hand-off Batch O — governance: schrijfkant voor incidenten, corrigerende maatregelen en risico's

Auteur: Cowork (architect). Uitvoerder: Claude Code, **één sessie**, na Batch N. Datum: 7 okt 2026. Kan **zonder toezicht** worden uitgevoerd: lees de stopregels. Repo's: `ai-governance-os` en `ai-governance-frontend`.

## Doel

De Governance-tab (Batch L Deel B) is nu alleen leesbaar, op de statuswissel van corrigerende maatregelen na. Een klant (en Valqeron zelf in tenant 0) moet **incidenten kunnen registreren, corrigerende maatregelen kunnen aanmaken, en risico's kunnen aanmaken en bijwerken**. Dat maakt "incident- en actieopvolging" aantoonbaar en is de basis voor het bewijs bij ISO 27001/42001 (taak 4.5, stap 2). Evidence-bestanden uploaden valt **buiten** dit batch.

## Vooraf besloten (niet opnieuw voorleggen)

- **Eigen organisatie, altijd:** `organization_id` komt uit het token, nooit uit de aanroep; andere organisatie of onbekend id geeft `404`. Een `AIRisk` en een incident hangen aan een `AISystem` van de eigen organisatie; controleer dat het gekozen systeem bij de eigen organisatie hoort.
- **Rollen:** schrijven alleen met dezelfde rol die nu ook de status van een corrigerende maatregel mag wijzigen (lees dat in Fase 0 en meld wat je hebt gekozen); lezen blijft zoals het is.
- **Geen migraties.** Alleen bestaande tabellen en kolommen. Ontbreekt een veld dat het scherm nodig heeft: stop en meld; verzin geen kolom.
- **Geen tekstinhoud in logs, auditregels of Sentry.** Auditregels bevatten alleen soort actie, object-id en bij een statuswissel oud en nieuw status. Geen titel, beschrijving of mitigatietekst.
- Validatie met `extra="forbid"`, lengtegrenzen volgens de kolommen (lees ze), `422` bij fouten, `404` bij vreemd of onbekend id.
- Bestaande endpoints, auth, MFA, provisioning en de ops-code blijven onaangeroerd. Geen nieuwe zware dependencies; hergebruik het bestaande ontwerp en de tabstructuur.
- Verwijderen: **niet** bouwen (ook geen "annuleren"); een `high`-risico blijft alleen door een super-admin te verwijderen, zoals nu.

## Werkwijze

1. `git pull` in beide repo's, `git status` en `git diff` (drift-check; verwacht de commits van Batch N of nieuwer). Meld afwijkingen.
2. **Fase 0 (alleen lezen), eerste alinea van je rapport:** de echte velden en toegestane waarden van `AIIncident`, `CorrectiveAction`, `AIRisk` en hun relaties (aan welk object hangt een maatregel: incident, risico, beide?), de bestaande endpoints en rollen in `governance.py`, en hoe de Governance-tab nu data laadt. Wijkt iets af van dit document: stoppen en melden.
3. Kleine losse commits; na elke push CI en Deploy controleren (GitHub Actions-API, `DEPLOY CHECK OK`), plus een echte functionele check op productie waar genoemd.

## Volgorde (lever per stap af; stop bij een batchgrens in plaats van half werk)

**O1 — Incidenten.** `POST /incidents` (en `PATCH /incidents/{id}` voor status en lopende velden volgens het model): titel, beschrijving, ernst (volgens de toegestane waarden), gekoppeld AI-systeem (optioneel, eigen organisatie), datum ontdekt. Portaal: knop "Incident registreren" op de Governance-tab, formulier met veldfouten, statuswissel met terugdraaien bij fout.

**O2 — Corrigerende maatregelen.** `POST /corrective-actions`: titel, beschrijving, eigenaar (tekst, geen persoonsgegevens afdwingen), deadline, koppeling aan een eigen incident of risico (volgens Fase 0). De bestaande statuswissel blijft. Portaal: "Maatregel toevoegen" bij een incident of risico.

**O3 — Risico's.** `POST /risks` en `PATCH /risks/{id}`: systeem, titel, beschrijving, mitigatie, niveau (`low`/`medium`/`high`). Een niveau verlagen van `high` mag niet door een gewone admin (volg het bestaande verwijderbeleid; meld wat je kiest). Portaal: aanmaken en bewerken.

## Tests

Backend per endpoint: succes, validatie (`422`), vreemd of onbekend id (`404`), **isolatie** (organisatie B kan niets bij A, ook niet via een systeem- of risico-id van A), rol-afdwinging, auditregel zonder tekst, `/audit/verify` `valid` na elke schrijfactie. Portaal: formulieren, veldfouten, terugdraaien bij fout, geen klantgegevens in `localStorage`, `console` of een Sentry-event (met de bestaande scrub-opzet). `pytest -q -m "not codex"`, `npm test`, lint met `--max-warnings=0` volledig groen.

## Productiecheck (alleen lezen)

Server-side gemunt token voor een bestaande demo-gebruiker (in geheugen, niet printen, wachtwoorden niet resetten of aanraken). **Schrijf niets op productie voor deze check, behalve één eigen wegwerp-aanroep, en alleen op tenant 0 (org 1) als dat nodig is** om te bewijzen dat de schrijfpaden werken: dan maak je één incident met een duidelijke titel `TEST (7 okt), mag worden gesloten` en sluit het direct daarna met de bestaande statuswissel; meld het. Kan dat niet zonder iets te omzeilen, sla het over en laat de tests de dekking zijn. Controleer verder: een gebruiker van een andere organisatie ziet niets en krijgt `404`; de Governance-tab rendert de formulieren zonder CSP-fouten of gefaalde requests.

## Stopvoorwaarden

Stop en meld als: een migratie of nieuw veld nodig lijkt; auth, MFA, provisioning of de ops-code geraakt wordt; een aanroep `organization_id` uit de aanroep zou halen; tekstinhoud in een log, auditregel of Sentry-event zou komen; een isolatietest faalt; tests rood worden; een Deploy twee keer achter elkaar faalt (de pijplijn draait zelf terug, meld het); de classifier iets blokkeert (niet omzeilen); de schijf boven 80% komt. Is O1 klaar en blokkeert O2: lever O1 af en meld de rest.

## Rapport

Fase 0-bevindingen en afwijkingen; commits per repo (hash en doel), CI- en Deploy-run-id's; per onderdeel (O1 t/m O3) wat is afgerond; testaantallen vóór en na; productiecheck per stap (verwacht, gezien, geen geheimen of persoonsgegevens); beslissingen die je zelf hebt genomen; CLAUDE.md (§2, §5, §6, §7) en READMEs bijgewerkt met commit-hash.
