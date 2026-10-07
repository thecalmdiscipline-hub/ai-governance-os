# Hand-off Batch O4 — evidence aanmaken in de Governance-tab (metadata, geen bestandsupload)

Auteur: Cowork (architect). Uitvoerder: Claude Code, **één sessie**. Datum: 7 okt 2026. Kan **zonder toezicht**: lees de stopregels. Repo's: `ai-governance-os` en `ai-governance-frontend`. Vervolg op Batch O (O1, O2, O3 zijn KLAAR; O2 gaf het patroon `OR`-scoping via risico of incident).

## Waarom

De Governance-tab toont al een Evidence-sectie (alleen lezen). Voor ISO-bewijsvoering en de klantdemo moet een klant (en Valqeron zelf) een bewijsstuk **registreren**: wat is het, waar hoort het bij, wie is eigenaar, wanneer is het bijgewerkt. Dit batch bouwt **uitsluitend het registreren van metadata**. Geen bestandsupload en geen opslag van documentinhoud.

## Vooraf besloten (niet opnieuw voorleggen)

- **Alleen metadata, geen bestanden.** Geen upload, geen opslag van bestandsinhoud, geen externe opslag. Een bewijsstuk heeft een titel, een korte beschrijving en een **verwijzing** (vrije tekst, bijvoorbeeld "Policy v1.2 in the customer's own document system"); het portaal toont expliciet "Describe where the evidence is kept. Do not paste documents or personal data here."
- **Migraties: standaard geen.** Gebruik de bestaande kolommen van `Evidence`. Lijkt er toch een nieuwe kolom nodig (bijvoorbeeld eigenaar of datum): **stop en meld** welke; zet de regel dan zelf op `WACHT OP DENNIS` in `WERKLIJST.md` en schrijf in het HERVAT-BLOK wat je nodig hebt. Bouw dan niets van de migratie.
- **Eigen organisatie, altijd:** `organization_id` uit het token, nooit uit de aanroep. Een bewijsstuk hangt aan een risico en/of incident van de **eigen** organisatie, volgens hetzelfde `or_(...)`-patroon als het bestaande `/evidence` en O2. Vreemd of onbekend id: `404`.
- **Padnaam:** bestaand `/evidence` (`POST` en `PATCH` erbij; `GET` blijft). Controleer in Fase 0 welke velden het model heeft (titel, type, beschrijving, status, koppelingen) en gebruik **alleen** die. `extra="forbid"`, `422` bij fouten, lengtegrenzen volgens de kolommen.
- **Rollen:** zoals O1/O2/O3 (geen extra rolcheck); meld wat je kiest.
- **Geen tekstinhoud in logs, auditregels of Sentry.** Auditregel: soort actie (`evidence_created` / `evidence_updated`), object-id en welke velden zijn gewijzigd. Nooit titel, beschrijving of verwijzing.
- Verwijderen: **niet** bouwen.
- Auth, MFA, provisioning, ops-code en alle andere endpoints blijven onaangeroerd. Geen nieuwe zware dependencies; hergebruik het formulier- en tabontwerp van O1, O2 en O3.

## Werkwijze

0. **Hervatten:** lees eerst het HERVAT-BLOK in `CLAUDE.md` en `WERKLIJST.md`; ga door bij de eerste onvoltooide stap. Elke stap is veilig opnieuw te draaien.
1. `git pull` in beide repo's, `git status`, `git diff` (drift-check; verwacht de laatste commits van O2 en Batch H, backend `e79a1e0` of nieuwer). Meld afwijkingen.
2. **Fase 0 (alleen lezen), eerste alinea van je rapport:** de echte kolommen, lengtes en toegestane waarden van `Evidence`; bestaande endpoints, rollen en tests voor evidence in `governance.py`; hoe de Governance-tab evidence nu toont; of een nieuw veld nodig lijkt (zie hierboven). Wijkt iets af: stoppen en melden.
3. Kleine losse commits; na elke push CI en Deploy controleren (`DEPLOY CHECK OK`).

## Bouw

1. **Backend:** `POST /evidence` en `PATCH /evidence/{id}` (alleen velden die bestaan; koppeling bij aanmaken, niet verplaatsbaar naar een andere organisatie). `GET` ongewijzigd.
2. **Portaal:** knop "Add evidence" op de Governance-tab, ook vanuit een risico- of incidentrij, en bewerken per bewijsstuk; veldfouten, terugrollen bij fout, dezelfde stijl als O1 tot en met O3; korte waarschuwing "Describe where the evidence is kept. Do not paste documents or personal data here."

## Tests

Backend: succes, validatie (`422`), vreemd of onbekend id (`404`), isolatie (organisatie B kan niets bij A, ook niet via een risico- of incident-id van A), alle koppelingscombinaties volgens het `/evidence`-patroon, auditregel zonder tekst, `/audit/verify` `valid` na elke schrijfactie. Portaal: formulier, veldfouten, terugrollen, geen klantgegevens in `localStorage`, `console` of Sentry. `pytest -q -m "not codex"` (nu 462), `npm test` (nu 153), lint met `--max-warnings=0` volledig groen.

## Productiecheck

Server-side gemunt token, alleen in geheugen, niet printen. **Eén wegwerp-bewijsstuk op organisatie 1** (`TEST (7 okt), mag worden gesloten of genegeerd`), gekoppeld aan het O1-testincident of het O3-testrisico dat al bestaat, één keer bijgewerkt met `PATCH`; meld het. Verwijderen kan niet; laat het staan en noem het. Organisatie 2 krijgt `404` en ziet niets; `/audit/verify` `valid` voor alle vijf organisaties; de Governance-tab rendert zonder CSP-fouten of gefaalde requests. Organisatie 5 (Atlas Demo B.V.) blijft ongemoeid.

## Stopvoorwaarden

Stop en meld als: een migratie of nieuw veld nodig lijkt; auth, MFA, provisioning of ops-code geraakt wordt; `organization_id` uit de aanroep zou komen; tekstinhoud in een log, auditregel of Sentry zou komen; een isolatietest faalt; tests rood; een Deploy twee keer achter elkaar faalt; de classifier iets blokkeert (niet omzeilen); de schijf boven 80%. Bij een **gebruikslimiet**: werk het HERVAT-BLOK bij, commit, push en stop netjes; Dennis typt later "continue".

## Rapport

Fase 0-bevindingen en afwijkingen; commits (hash en doel), CI-/Deploy-run-id's; testaantallen vóór en na; productiecheck per stap; beslissingen die je zelf nam; CLAUDE.md (§2, §5, §6, §7) en READMEs bijgewerkt met commit-hash; HERVAT-BLOK en `WERKLIJST.md` (status `KLAAR`) bijgewerkt.
