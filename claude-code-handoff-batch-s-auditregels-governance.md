# Hand-off Batch S — auditregels voor vier governance-schrijfacties (klein, geen migratie)

Auteur: Cowork. Uitvoerder: Claude Code, **één sessie**. Datum: 12 okt 2026. Repo: `ai-governance-os`. Kan zonder toezicht; lees de stopregels. Grootte: S.

## Waarom

Bij A6 (12 okt) vond Claude Code bij een code-audit van `app/api/governance.py` dat vier schrijf-endpoints **geen auditregel** schrijven: `POST /ai-systems`, `POST /ai-risks`, `DELETE /ai-risks/{id}` en `POST /production-approvals/{system_id}`. Dat betekent dat "elke governance-actie staat in het auditlog" onjuist is. Het raakt ISMS-bewijs (SoA, procedure P2/P3), de DPA-bijlage en marketingclaims. Dit batch laat de software doen wat we beweren, in plaats van de claim te blijven afzwakken.

## Vooraf besloten (niet opnieuw voorleggen)

- **Geen migratie, geen schemawijziging, geen wijziging aan de hash-keten-logica zelf** (`create_audit_log()` blijft zoals hij is; je roept hem alleen aan zoals de andere governance-endpoints).
- **Geen berichtinhoud of persoonsgegevens in de auditregel**: alleen actienaam, entiteitstype, id en organisatie, zoals de bestaande governance-auditregels. Volg het bestaande patroon (actienamen en detailvelden) van de andere endpoints in hetzelfde bestand; verzin geen nieuw formaat.
- **Alleen deze vier endpoints**, tenzij Fase 0 meer vindt: noem andere gevonden schrijf-endpoints zonder auditregel in het rapport en **repareer ze niet** zonder dat Cowork ze heeft beoordeeld (uitzondering: dezelfde zuivere ontbrekende aanroep in hetzelfde bestand mag mee als je het apart meldt).
- Geen backfill van oude acties: de bestaande keten wordt niet herschreven. Er komen alleen nieuwe regels vanaf de uitrol.
- Geen portaalwijziging.

## Werkwijze

0. Lees het HERVAT-BLOK in `CLAUDE.md` en `WERKLIJST.md`; hervat bij de eerste onvoltooide fase.
1. `git pull`, `git status`, `git diff`; meld afwijkingen.
2. **Fase 0 (alleen lezen), eerste alinea van je rapport:** loop **alle** schrijf-endpoints (POST/PUT/PATCH/DELETE) in `app/api/` langs en maak een tabel: endpoint, schrijft auditregel ja/nee, actienaam. Bevestig de vier bekende, noem eventuele andere. Meld ook of `/audit/verify` per organisatie nu `valid` geeft (alle vijf).
3. **Fase 1:** voeg de `create_audit_log()`-aanroep toe aan de vier endpoints, in dezelfde transactie als de schrijfactie (faalt de log, dan faalt de actie, zoals de bestaande endpoints doen; controleer dat patroon in Fase 0 en volg het).
4. **Fase 2 tests:** per endpoint een test dat na de actie precies één nieuwe auditregel bestaat met de juiste actie, organisatie en entiteit; dat de regel geen vrije tekst of persoonsgegevens bevat; dat `/audit/verify` `valid` blijft; dat een mislukte actie (validatiefout of 4xx) **geen** auditregel schrijft; dat de isolatie tussen organisaties blijft kloppen. `pytest -q -m "not codex"` volledig groen; lint volgens het project.
5. Kleine commits, push, CI en Deploy controleren (`DEPLOY CHECK OK`).
6. **Productiecheck (alleen org 1 en org 5, wegwerpgegevens):** maak één wegwerp-AI-systeem en -risico aan (met herkenbare testnaam), voer één productiegoedkeuring uit op het wegwerpsysteem **alleen als dat zonder bijwerkingen kan** (anders overslaan en melden), verwijder het wegwerprisico; controleer dat per actie één auditregel verschijnt en dat `/audit/verify` `valid` blijft voor alle vijf organisaties. Laat geen wegwerpgegevens achter die niet netjes weg kunnen; meld wat blijft staan (zoals bij het testbewijsstuk id 1). Organisatie 2, 3 en 4 niet aanraken.

## Stopvoorwaarden

Stop en meld als: een migratie of schemawijziging nodig lijkt; `create_audit_log()` aangepast zou moeten worden; een test rood blijft; Deploy twee keer achter elkaar faalt; de schijf boven 80% komt; de classifier iets blokkeert (niet omzeilen); een geheim of wachtwoord in een bestand, log of chat zou moeten; er een aanwijzing is dat de bestaande keten ongeldig is (`/audit/verify` niet `valid`): dan **niets wijzigen** en melden. Bij een gebruikslimiet: HERVAT-BLOK bijwerken, commit, push, stop netjes.

## Rapport

Tabel uit Fase 0; commits (hash en doel), CI-/Deploy-run-id's; testaantallen vóór en na; productiecheck (welke acties, welke regels, wat blijft staan); eventuele andere endpoints zonder auditregel; CLAUDE.md (§2, §5, §6, §7) bijgewerkt; HERVAT-BLOK en `WERKLIJST.md` (status `KLAAR`). Cowork past daarna de claimtekst in briefing, handout en SoA aan (C2 kan dan weer "elke governance-schrijfactie" worden, **alleen** als Fase 0 alle schrijf-endpoints heeft gedekt).
