# Hand-off Batch O3 — risico's aanmaken en bijwerken (Governance-tab)

Auteur: Cowork (architect). Uitvoerder: Claude Code, **één sessie**. Datum: 7 okt 2026. Kan **zonder toezicht**: lees de stopregels. Repo's: `ai-governance-os` en `ai-governance-frontend`. Vervolg op Batch O (O1 klaar: `bc8aa33`, `4f86403`; O2 wacht op een apart akkoord voor een migratie, zie `claude-code-handoff-batch-o2-corrigerende-maatregelen.md`).

## Waarom

Uit het nachtrapport: `AIRisk` heeft alle kolommen die nodig zijn, dus O3 was zelf niet geblokkeerd en is alleen blijven liggen vanwege de batchbrede stopregel. O3 is een eigen, kleine opdracht zonder migratie.

## Vooraf besloten (niet opnieuw voorleggen)

- **Geen migraties.** Alleen bestaande tabellen en kolommen. Lijkt er toch een nieuw veld nodig: stop en meld.
- **Eigen organisatie, altijd:** `organization_id` uit het token, nooit uit de aanroep. Een `AIRisk` hangt aan een `AISystem`; het gekozen systeem moet bij de eigen organisatie horen. Vreemd of onbekend id: `404`.
- **Rollen:** zoals O1 (geen extra rolcheck, gelijk aan `PUT /corrective-actions/{id}/status`); meld wat je kiest.
- **Padnaam:** gebruik het bestaande `/ai-risks` (zoals O1 `/ai-incidents` gebruikte), niet het letterlijke `/risks`. Meld het.
- **Velden:** `ai_system_id` (verplicht bij aanmaken), `title`, `description`, `mitigation` (volgens de echte kolommen), `level` (`low`/`medium`/`high`). Lengtegrenzen volgens de kolommen (lees ze), `extra="forbid"`, `422` bij fouten.
- **Niveau verlagen van `high`:** mag niet door een gewone admin, volg het bestaande verwijderbeleid voor `high`-risico's (alleen super-admin). Meld wat je kiest.
- **Geen tekstinhoud in logs, auditregels of Sentry.** Auditregel bevat alleen soort actie, object-id, welke velden zijn gewijzigd en bij een niveauwijziging oud en nieuw niveau (geen titel, beschrijving of mitigatietekst).
- Verwijderen: **niet** bouwen.
- Bestaande endpoints, auth, MFA, provisioning en de ops-code blijven onaangeroerd. Geen nieuwe zware dependencies; hergebruik het formulier- en tabontwerp van O1.

## Werkwijze

0. **Hervatten:** lees eerst het HERVAT-BLOK in `CLAUDE.md` en `WERKLIJST.md`. Ga door bij de eerste onvoltooide stap. Elke stap is veilig opnieuw te draaien.
1. `git pull` in beide repo's, `git status` en `git diff` (drift-check; verwacht `c8ee957` / `6cc419a` of nieuwer). Meld afwijkingen.
2. **Fase 0 (alleen lezen), eerste alinea van je rapport:** de echte kolommen, lengtes en toegestane waarden van `AIRisk`; bestaande endpoints en rollen in `governance.py` voor risico's; hoe de Governance-tab de risico's nu laadt en toont (O1 en L Deel B). Wijkt iets af: stoppen en melden.
3. Kleine losse commits; na elke push CI en Deploy controleren (`DEPLOY CHECK OK`).

## Bouw

**Backend:** `POST /ai-risks` en `PATCH /ai-risks/{id}` (titel, beschrijving, mitigatie, niveau; systeem alleen bij aanmaken, niet te verplaatsen naar een ander systeem). **Portaal:** knop "Add risk" op de Governance-tab en bewerken per risico, met veldfouten, terugrollen bij fout en dezelfde stijl als O1.

## Tests

Backend: succes, validatie (`422`), vreemd of onbekend id (`404`), isolatie (organisatie B kan niets bij A, ook niet via een systeem- of risico-id van A), niveaubeleid, auditregel zonder tekst, `/audit/verify` `valid` na elke schrijfactie. Portaal: formulier, veldfouten, terugrollen, geen klantgegevens in `localStorage`, `console` of Sentry. `pytest -q -m "not codex"`, `npm test`, lint met `--max-warnings=0` volledig groen.

## Productiecheck

Server-side gemunt token, alleen in geheugen, niet printen. **Eén wegwerp-risico op organisatie 1** met een duidelijke titel `TEST (7 okt), mag worden verwijderd`, gekoppeld aan een bestaand org-1-systeem, **laagste niveau (`low`)** zodat het door een admin weer te verwijderen is; werk het één keer bij met `PATCH` en meld het. Controleer verder: organisatie 2 krijgt `404` en ziet niets; `/audit/verify` `valid` voor org 1; de Governance-tab rendert zonder CSP-fouten of gefaalde requests. Kan het wegwerp-risico niet verwijderd worden zonder iets te omzeilen, laat het staan en meld het.

## Stopvoorwaarden

Stop en meld als: een migratie of nieuw veld nodig lijkt; auth, MFA, provisioning of ops-code geraakt wordt; `organization_id` uit de aanroep zou komen; tekstinhoud in een log, auditregel of Sentry-event zou komen; een isolatietest faalt; tests rood worden; een Deploy twee keer achter elkaar faalt; de classifier iets blokkeert (niet omzeilen); de schijf boven 80% komt. Bij een **gebruikslimiet**: werk het HERVAT-BLOK bij, commit, push en stop netjes; Dennis typt later "continue".

## Rapport

Fase 0-bevindingen en afwijkingen; commits (hash en doel), CI-/Deploy-run-id's; testaantallen vóór en na (nu 423 en 142); productiecheck per stap (verwacht, gezien); beslissingen die je zelf nam; CLAUDE.md (§2, §5, §6, §7) en READMEs bijgewerkt met commit-hash; HERVAT-BLOK en `WERKLIJST.md` (status `KLAAR`) bijgewerkt.
