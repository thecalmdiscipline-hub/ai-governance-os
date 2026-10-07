# Hand-off Batch O2 — corrigerende maatregelen aanmaken (met kleine, additieve migratie)

Auteur: Cowork (architect). Uitvoerder: Claude Code, **één sessie**. Datum: 7 okt 2026. **Status: WACHT OP DENNIS (akkoord op de migratie).** Start pas als `WERKLIJST.md` deze opdracht op `OPEN` zet. Repo's: `ai-governance-os` en `ai-governance-frontend`.

## Waarom

Uit het nachtrapport van 7 okt: `CorrectiveAction` heeft vier kolommen (`title`, `description`, `status`, `ai_risk_id`); het scherm en de ISO-bewijsvoering (incident-opvolging) vragen om een eigenaar, een deadline en een koppeling aan een incident. Zonder die velden is "corrigerende maatregel" geen opvolging.

## Vooraf besloten (na Dennis' akkoord; niet opnieuw voorleggen)

- **Eén additieve migratie** (de standaardregel van het project: alleen additief en nullable): drie nieuwe **nullable** kolommen op `CorrectiveAction`: `owner` (korte tekst, lees de gangbare lengte; vrije tekst, **geen persoonsgegevens afdwingen of valideren**, de UI waarschuwt dat het een rol of teamnaam moet zijn), `due_date` (datum), `ai_incident_id` (verwijzing naar `AIIncident`, nullable, met index). Bestaande rijen blijven ongewijzigd (alles `NULL`). Geen backfill, geen `NOT NULL`, geen wijziging aan andere tabellen.
- **Migratieprocedure:** nieuwe Alembic-revisie; lees eerst `alembic/versions/` en de notitie in CLAUDE.md over de eerste migratie en `setup_server.sh` (`create_all()` plus `stamp`); controleer dat de revisie lineair aansluit op de huidige `head` (`alembic heads` toont één head). Test de migratie op een kopie/lege SQLite én met `alembic upgrade head` zoals de deploy dat doet; draai `downgrade` lokaal één keer om te bewijzen dat terugdraaien werkt. **Controleer vóór de deploy hoe de migratie op productie wordt uitgevoerd** (CLAUDE.md §2 Deploy-script) en volg exact dat pad; voer niets handmatig op de server uit buiten dat pad.
- **Eigen organisatie, altijd:** `organization_id` uit het token. Een nieuwe maatregel hangt aan een risico en/of incident van de **eigen** organisatie (via het gekoppelde `AISystem`); vreemd of onbekend id: `404`.
- Padnaam: bestaand `/corrective-actions` (`POST` erbij, `GET` uitbreiden met de nieuwe velden); `PUT /corrective-actions/{id}/status` blijft. `extra="forbid"`, `422` bij fouten.
- Rollen zoals O1 (geen extra rolcheck); meld wat je kiest.
- **Geen tekstinhoud in logs, auditregels of Sentry**; de auditregel bevat alleen soort actie, id en welke velden zijn gewijzigd.
- Verwijderen en annuleren: niet bouwen.

## Werkwijze

0. **Hervatten:** lees eerst het HERVAT-BLOK in `CLAUDE.md` en `WERKLIJST.md`; ga door bij de eerste onvoltooide stap; elke stap is veilig opnieuw te draaien.
1. `git pull` in beide repo's, drift-check (verwacht de commits van O3 of nieuwer). Meld afwijkingen.
2. **Fase 0 (alleen lezen), eerste alinea van je rapport:** de echte kolommen van `CorrectiveAction`, `AIRisk`, `AIIncident`; bestaande endpoints en tests; huidige `alembic heads`; hoe Deploy de migratie toepast; of er al een veld met een andere naam bestaat (bijv. `owner`/`deadline` onder een andere naam). Wijkt iets af: stoppen en melden.
3. Kleine losse commits; na elke push CI en Deploy controleren.

## Bouw

1. **Migratie en model** (O2a): drie nullable kolommen, index op `ai_incident_id`; modeltest; migratie-test (up en down).
2. **Backend** (O2b): `POST /corrective-actions` (titel, beschrijving, optioneel risico en/of incident, eigenaar, einddatum; status start op de bestaande beginwaarde), `GET` geeft de nieuwe velden terug, optioneel filter `?ai_incident_id=`; de statuswissel blijft werken.
3. **Portaal** (O2c): "Add corrective action" bij een incident en bij een risico op de Governance-tab, velden voor eigenaar (met korte waarschuwing "role or team, no personal data") en einddatum, veldfouten, terugrollen bij fout; een verlopen einddatum met niet-gesloten status krijgt een duidelijke markering (alleen weergave).

## Tests

Backend: succes, validatie (`422`), vreemd of onbekend id (`404`), **isolatie** (organisatie B kan niets bij A, ook niet via een incident- of risico-id van A), auditregel zonder tekst, `/audit/verify` `valid`, migratie up/down, bestaande rijen blijven leesbaar met `NULL`. Portaal: formulier, veldfouten, terugrollen, geen klantgegevens in `localStorage`, `console` of Sentry. Alles volledig groen, lint `--max-warnings=0`.

## Productiecheck

Server-side gemunt token in geheugen, niet printen. Na de Deploy: de migratie is toegepast (alleen lezen: `alembic current` of de bestaande gezondheidscontrole), bestaande maatregelen zijn ongewijzigd leesbaar, `/audit/verify` `valid` voor alle bestaande organisaties. **Eén wegwerp-maatregel op organisatie 1** (`TEST (7 okt), mag worden gesloten`, gekoppeld aan het testincident van O1), meteen gesloten met de statuswissel; meld het. Organisatie 2 krijgt `404`. Governance-tab rendert zonder CSP-fouten.

## Stopvoorwaarden

Stop en meld als: de migratie meer dan deze drie nullable kolommen vraagt; `alembic heads` meer dan één head toont; `downgrade` niet werkt; de productiemigratie via een ander pad moet dan het bestaande deploypad; auth, MFA, provisioning of ops-code geraakt wordt; tekstinhoud in een log, auditregel of Sentry zou komen; een isolatietest faalt; tests rood; een Deploy twee keer achter elkaar faalt; de classifier iets blokkeert (niet omzeilen); de schijf boven 80%. Is de migratie niet veilig deploybaar: lever O2a (migratie en test) niet af naar productie en meld het. Bij een **gebruikslimiet**: HERVAT-BLOK bijwerken, commit, push, stop netjes.

## Rapport

Fase 0-bevindingen en afwijkingen; commits (hash en doel), CI-/Deploy-run-id's; migratie-revisie-id en wat die doet; testaantallen vóór en na; productiecheck per stap; beslissingen die je zelf nam; CLAUDE.md (§2, §5, §6, §7) en READMEs bijgewerkt met commit-hash; HERVAT-BLOK en `WERKLIJST.md` bijgewerkt.
