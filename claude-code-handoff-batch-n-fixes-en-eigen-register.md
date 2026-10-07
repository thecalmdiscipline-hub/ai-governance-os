# Hand-off Batch N — kleine correcties op Batch L en het eigen AI-register laden (org 1)

Auteur: Cowork (architect). Uitvoerder: Claude Code, **één sessie**. Datum: 7 okt 2026. Kan **zonder toezicht** worden uitgevoerd: lees de stopregels. Repo: `ai-governance-os` (backend) en `ai-governance-frontend` (portaal, alleen als genoemd). Dennis heeft de inhoud hieronder op 7 okt goedgekeurd.

## Vooraf besloten (niet opnieuw voorleggen)

- Geen migraties. Geen wijziging aan auth, MFA, provisioning of de ops-code. Geen serverwijzigingen (geen apt, geen herstart, geen SSH- of nginx-config).
- Bestaande rijen worden nooit overschreven, behalve de ene, exact omschreven tekstcorrectie in N3 (alleen organisatie 3).
- Organisatie 4 (ISO Cert-demo) blijft **ongewijzigd**. Organisaties 1 en 2 blijven ongewijzigd, behalve de toevoegingen van N4 aan org 1.

## Werkwijze

1. `git pull` in beide repo's, dan `git status` en `git diff` (drift-check; verwacht `be91737` / `4793a82` of nieuwer). Meld afwijkingen.
2. Kleine losse commits; na elke push CI en Deploy controleren (GitHub Actions-API, `DEPLOY CHECK OK`), plus een echte functionele check op productie waar genoemd.
3. Lees je Fase 0 vooraf (alleen lezen) kort in je rapport: hoe de klantroutes de taaktitels nu teruggeven, waar `POST /ai-policy` de overclaim bevat, en de echte velden van `AIPolicy`, `AISystem` en `AIRisk` (namen, lengtes, toegestane waarden voor `level`).

## N1 — Engelse taaktitels in de klantkaart

De fasetitels in de klantkaart zijn Engels, de taaktitels Nederlands. Los dit op **zonder migratie en zonder bestaande data te herschrijven**:
- Voeg in `app/services/onboarding.py` een vaste vertaaltabel toe, `CUSTOMER_TASK_TITLES_EN`, met sleutel `(fase, positie)` en de Engelse titel voor de 14 klantzichtbare taken van `standard-v1`. Voorgestelde teksten:
  - (2,2) `Proposal approved` (2,3) `DPA signed` (2,4) `Company details received: company name, country, sector, first administrator, roles of other users`
  - (3,1) `Kickoff call scheduled` (3,2) `Goals and scope confirmed per workflow` (3,3) `Technical contact and roles assigned: admin, auditor, operator` (3,4) `Go-live date agreed`
  - (5,1) `First documents uploaded` (6,1) `Training session scheduled` (6,2) `Training delivered with the Client Portal Guide` (6,3) `Roles and reviewing results explained`
  - (7,2) `Result reviewed together with you` (8,1) `First-week check-in` (8,2) `First monthly usage report sent`
- `GET /onboarding/progress` geeft de Engelse titel terug als de sleutel in de tabel staat, anders de opgeslagen titel (terugval). De ops-tab en de opgeslagen taken blijven Nederlands.
- Test: elke klantzichtbare taak van `standard-v1` heeft een Engelse titel (de test faalt als een nieuwe klantzichtbare taak er geen heeft); het antwoord bevat geen Nederlandse titel; ops-routes ongewijzigd.
- Taak (8,2) blijft staan: Dennis gaat het maandrapport leveren (de rapportagefunctie zelf is een aparte, geplande batch).

## N2 — `POST /ai-policy` overclaim

`governance.py` heeft een eigen vaste tekst met dezelfde overclaim als het provisioningsjabloon ("monitored continuously"). Vervang door dezelfde tekst als het sjabloon uit commit `be91737` (zorg dat beide plekken uit **één** constante komen als dat zonder grote ingreep kan; anders alleen de tekst gelijk trekken en melden). Pas de tests aan. Bestaande rijen blijven ongemoeid.

## N3 — organisatie 3: tekst corrigeren

Alleen organisatie 3 ("ZZ Provisioning Test"; test-tenant) draagt nog de oude `monitoring_commitment`. Schrijf een klein, idempotent script `scripts/fix_monitoring_commitment.py --org 3 [--dry-run]` dat **alleen** de AIPolicy-rij van die organisatie aanpast, en **alleen als** de huidige waarde exact de oude overclaimtekst is; anders overslaan en melden. Auditregel `performed_by=system:fix_monitoring_commitment`, zonder de tekst zelf. Dry-run eerst; daarna echt draaien op de server. Controleer `/audit/verify` `valid` voor org 3. **Organisatie 4 niet aanraken.**

## N4 — het eigen AI-register laden voor organisatie 1

Bron: `eigen-register-valqeron.json` in de repo-root (door Cowork neergezet, door Dennis goedgekeurd; verplaats het naar `scripts/data/` en commit het daar). Structuur: `policy` (vier velden) en `ai_systems` (14 items), elk met `key`, `name`, `description`, `purpose`, `use_status` en `risks` (title, description, mitigation, level).
- Script `scripts/seed_own_register.py --config scripts/data/eigen-register-valqeron.json [--dry-run]`, op de server, auditregel `performed_by=system:seed_own_register`.
- **Idempotent en insert-only.** Org 1 heeft naar verwachting 0 rijen. Bestaat er al een AIPolicy voor org 1 of een AISystem/AIRisk met dezelfde naam of titel: overslaan en melden (nooit overschrijven). Is er iets onverwachts aanwezig, stop dan na de dry-run en meld.
- Eerst AIPolicy, dan per systeem een AISystem, dan het AIRisk (`level` uit het bestand). **Alles in één transactie**; faalt iets, dan alles terug.
- `use_status` is geen databaseveld: voeg **geen kolom** toe. De tekst in `purpose` en `description` draagt de status al (bijvoorbeeld `On hold: ...` bij de HR-workflow). Controleer dat teksten binnen de kolomlengtes passen; past iets niet, stop en meld (kort niet stilzwijgend in).
- Het niveau `high` (HR-workflow) kan alleen een super-admin verwijderen; dat is bedoeld.
- Dry-run eerst, rapporteer aantallen en namen; daarna echt draaien. Controleer daarna: `/audit/verify` `valid` voor org 1; org 2, 3 en 4 ongewijzigd (tellingen vóór en na); `GET` van de nieuwe governance-lijsten voor een org-1-gebruiker (server-side gemunt token, in geheugen, niet printen) toont de 14 systemen, de risico's en het beleid; de Governance-tab van Batch L rendert het register zonder fouten.

## Tests

Backend: tests voor N1 (titeltabel en terugval), N2 (tekst), N3 (script: dry-run, alleen exacte oude tekst, andere org ongemoeid), N4 (script: idempotent, overslaan bij bestaande rij, rollback bij fout, geen kolomwijziging). `pytest -q -m "not codex"` volledig groen. Portaal: alleen aanpassen als N1 dat nodig maakt (verwacht van niet); `npm test` en lint blijven groen.

## Stopvoorwaarden

Stop en meld als: een migratie nodig lijkt; auth, MFA of de ops-code geraakt wordt; een bestaande rij overschreven zou worden; org 4 geraakt wordt; een tekst niet in een kolom past; tests rood worden; een Deploy twee keer achter elkaar faalt (de pijplijn draait zelf terug, meld het); de classifier iets blokkeert (niet omzeilen); de schijf boven 80% komt. Is een onderdeel klaar en blokkeert het volgende: lever het klare onderdeel af en meld de rest.

## Rapport

Fase 0-bevindingen; commits (hash en doel), CI- en Deploy-run-id's; per onderdeel (N1 t/m N4) wat is gedaan; dry-run-uitkomsten (aantallen en namen); productiecontroles per stap (verwacht, gezien, geen geheimen of persoonsgegevens); testaantallen vóór en na; CLAUDE.md (§2, §5, §6, §7) en READMEs bijgewerkt met commit-hash.
