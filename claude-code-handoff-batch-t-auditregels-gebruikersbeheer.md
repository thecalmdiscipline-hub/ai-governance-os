# Hand-off Batch T — auditregels voor gebruikersbeheer (klein, geen migratie)

Auteur: Cowork. Uitvoerder: Claude Code, **één sessie**. Datum: 13 okt 2026. Repo: `ai-governance-os`. Kan zonder toezicht; lees de stopregels. Grootte: S. Opvolger van Batch S: bij Fase 0 van Batch S bleek dat `app/api/users.py` geen auditregel schrijft voor gebruikersbeheer (bewust niet gefixt, buiten die scope).

## Waarom

Toegangsbeheer is een kernonderdeel van ISMS (procedure P1) en van wat Valqeron aan klanten belooft. Als het aanmaken, wijzigen of uitschakelen van gebruikers niet in de hash-geketende auditlog staat, ontbreekt het bewijs van wie wanneer toegang kreeg of verloor. Daarnaast klopt dan de claim "acties worden vastgelegd" voor precies de acties waar een auditor het eerst naar kijkt niet.

## Vooraf besloten (niet opnieuw voorleggen)

- **Geen migratie, geen schemawijziging, geen wijziging aan `create_audit_log()`, auth, MFA, wachtwoordregels of provisioning-logica.** Je voegt alleen auditaanroepen toe aan bestaande schrijf-acties, volgens het patroon van Batch S en de andere governance-endpoints.
- **Nooit geheimen of persoonsgegevens in een auditregel:** geen wachtwoord, geen wachtwoordhash, geen eenmalig wachtwoord, geen MFA-geheim of back-upcode, geen token. Wel toegestaan: actienaam, entiteit (`user`), gebruiker-id, organisatie-id en welke rol of status is gezet. Geen e-mailadres of naam in de log tenzij het bestaande patroon in dit project dat al doet; volg het patroon en meld het.
- **Alleen `app/api/users.py`** en eventueel dezelfde zuivere ontbrekende aanroep in een direct aangrenzend bestand als Fase 0 die vindt; noem andere gevonden endpoints zonder auditregel in je rapport en **repareer ze niet** zonder Cowork.
- Geen backfill. Geen portaalwijziging.
- Geen echte gebruikers aanmaken of wijzigen op productie voor de productiecheck, behalve wegwerpgebruikers op organisatie 1 (zie hieronder), en nooit het account of de rol van een bestaande echte gebruiker (zoals `atlas_demo_admin` of de super-admin) wijzigen.

## Werkwijze

0. Lees het HERVAT-BLOK in `CLAUDE.md` en `WERKLIJST.md`; hervat bij de eerste onvoltooide fase.
1. `git pull`, `git status`, `git diff`; meld afwijkingen.
2. **Fase 0 (alleen lezen), eerste alinea van je rapport:** tabel van alle schrijf-endpoints in `app/api/users.py` (aanmaken, wijzigen, rol, uitschakelen/activeren, wachtwoord wijzigen/resetten, MFA aan/uit, enz.): schrijft hij een auditregel ja/nee, welke actienaam past bij het bestaande patroon, en of de actie `organization_id` en actor-id beschikbaar heeft. Bevestig dat `/audit/verify` nu `valid` is voor alle vijf organisaties.
3. **Fase 1:** voeg de `create_audit_log()`-aanroep toe aan elk endpoint dat gebruikers- of toegangsstatus wijzigt (aanmaken, rolwijziging, uitschakelen/activeren, verwijderen/soft-delete, wachtwoordreset door een beheerder). Voor een **wachtwoordwijziging door de gebruiker zelf** en **MFA aan/uit**: een auditregel zonder enige geheime waarde is gewenst; als het bestaande patroon dit al elders loggen (bijv. in `auth.py`), loop dan niet dubbel. Houd de transactiegedrag-conventie aan uit Batch N/S (`create_audit_log()` commit zelf; volg het gedocumenteerde patroon).
4. **Fase 2 tests:** per endpoint precies één nieuwe auditregel met juiste actie, organisatie, actor en entiteit; de regel bevat nergens een wachtwoord, hash, token of MFA-geheim (test met herkenbare nepwaarden en zoek ze in de opgeslagen auditregel); een mislukte actie (4xx) schrijft geen regel; isolatie tussen organisaties blijft kloppen; `/audit/verify` blijft `valid`. `pytest -q -m "not codex"` volledig groen; lint volgens het project.
5. Kleine commits, push, CI en Deploy controleren (`DEPLOY CHECK OK`).
6. **Productiecheck (alleen organisatie 1, wegwerpgebruiker):** maak één wegwerpgebruiker aan (herkenbare testnaam, laagste rol), wijzig de rol, schakel hem uit; controleer per actie één auditregel zonder geheime waarden; verwijder/soft-delete de wegwerpgebruiker als het bestaande endpoint dat toestaat en meld wat blijft staan. `/audit/verify` `valid` voor alle vijf organisaties; organisaties 2, 3, 4, 5 ongewijzigd; geen wachtwoord of eenmalig wachtwoord in je rapport, log of chat.

## Stopvoorwaarden

Stop en meld als: een migratie of schemawijziging nodig lijkt; `create_audit_log()` of auth-/MFA-logica aangepast zou moeten worden; een geheim, wachtwoord of token in een auditregel, bestand, log of chat terecht zou komen; de classifier iets blokkeert (niet omzeilen); een test rood blijft; Deploy twee keer achter elkaar faalt; de schijf boven 80% komt; `/audit/verify` niet `valid` is (dan niets wijzigen). Bij een gebruikslimiet: HERVAT-BLOK bijwerken, commit, push, stop netjes.

## Rapport

Tabel uit Fase 0; commits (hash, doel), CI/Deploy-run-id's; testaantallen vóór en na; productiecheck (welke acties, welke regels, wat blijft staan); eventuele andere endpoints zonder auditregel; CLAUDE.md (§2, §5, §6, §7) bijgewerkt; HERVAT-BLOK en `WERKLIJST.md` (rij 12 `KLAAR`). Cowork past daarna de claim in briefing, handout en ISMS-stukken aan.
