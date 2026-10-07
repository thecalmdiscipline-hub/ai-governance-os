# Nachtrapport — 2026-10-07 (dagrun, zonder toezicht tot 12:30)

Opdracht: "DAGRUN, geen toezicht tot 12:30. Eén sessie." — lees
`claude-code-handoff-batch-n-fixes-en-eigen-register.md` en voer N1–N4 uit; alleen als N gezond is
(tests groen, Deploy groen), lees `claude-code-handoff-batch-o-governance-schrijfkant.md` en voer
O1, daarna O2, daarna O3 uit. Geen migraties, geen serverwijzigingen, geen nieuwe organisaties, geen
berichten/e-mail. Dit document bevat geen geheimen of persoonsgegevens.

**Resultaat in één zin:** Batch N volledig klaar (N1 t/m N4); Batch O's O1 volledig klaar; O2 en O3
bewust niet gebouwd — geblokkeerd op een echte schema-beperking (geen migratie uitgevoerd, zoals
voorgeschreven).

---

## Batch N — kleine correcties + Valqerons eigen AI-register

Hand-off: `claude-code-handoff-batch-n-fixes-en-eigen-register.md`.

**N1 — Engelse taaktitels.** `app/services/onboarding.py` kreeg `CUSTOMER_TASK_TITLES_EN`, een
`(fase, positie)`-vertaaltabel voor de 14 klantzichtbare `standard-v1`-taken. `GET
/onboarding/progress` geeft nu de Engelse titel terug, met terugval op de opgeslagen Nederlandse
titel. Geen migratie, de opgeslagen taken en de ops-tab blijven Nederlands.
Commit `14ee3a4`. CI `37585542117` (success), Deploy `37585708357` (success).

**N2 — `POST /ai-policy`-overclaim.** Dit endpoint had zijn eigen, losse hardcoded "AI systems are
continuously monitored." — dezelfde overclaim als het provisioningsjabloon had vóór een eerdere
sessie. Beide plekken trekken nu uit één nieuwe, gedeelde constante.
Commit `27d4322`. CI `37585845235` (success), Deploy `37586075176` (success).

**N3 — organisatie 3's tekst gecorrigeerd.** Nieuw, idempotent script
`scripts/fix_monitoring_commitment.py --org <id> [--dry-run]`: corrigeert een `AIPolicy`-rij alleen
als de tekst **exact** de oude overclaim is. Op productie gedraaid voor org 3 (dry-run eerst, toen
echt): gecorrigeerd. **Organisatie 4 bewust ongewijzigd** (nog de oude tekst, zoals voorgeschreven).
`/audit/verify` bevestigd `valid` voor org 3.
Commit `b6411e9`. CI `37586188132` (success), Deploy `37586377937` (success).

**N4 — Valqerons eigen AI-register geladen in organisatie 1.** Nieuw, idempotent en insert-only
script `scripts/seed_own_register.py --config scripts/data/eigen-register-valqeron.json
[--dry-run]`. Op productie gedraaid (dry-run eerst, toen echt): organisatie 1 had 0 rijen zoals
verwacht → 1 `AIPolicy`, 14 `AISystem`, 14 `AIRisk` aangemaakt (12 medium, 1 high, 1 low). Een
herhaalde dry-run bewees idempotentie (alles overgeslagen). Organisaties 2/3/4 bevestigd
ongewijzigd. `/audit/verify` bevestigd `valid` voor org 1.
**Belangrijke bevinding tijdens het bouwen:** `create_audit_log()` committed de lopende transactie
zelf — dit dwong een herontwerp af (eerst alle rijen bouwen en in één commit wegschrijven, pas
daarna auditregels), nu gedocumenteerd in CLAUDE.md zodat een volgende sessie dit niet opnieuw moet
ontdekken.
Commit `aaca3f7`. CI `37586672416` (success), Deploy `37586863483` (success).

**CLAUDE.md bijgewerkt (secties 2, 5, 6, 7) voor Batch N.** Commit `cdbd2e8`. CI `37587670567`
(success), Deploy `37587868441` (success).

**Testaantallen Batch N:** backend 395 → **414** (N1 +2, N2 +1, N3 +6, N4 +10).

---

## Batch O — governance schrijfkant

Hand-off: `claude-code-handoff-batch-o-governance-schrijfkant.md`, gestart direct na Batch N (N was
gezond: alle tests groen, alle acht CI/Deploy-runs groen).

**Fase 0 (alleen lezen) — de bevinding die de rest van dit batch bepaalde:** `CorrectiveAction`
heeft precies vier kolommen: `title`, `description`, `status`, `ai_risk_id`. Er is **geen**
`owner`-kolom, **geen** `deadline`-kolom, en **geen** `ai_incident_id` (alleen een koppeling naar
een risico, niet naar een incident). O2 vroeg letterlijk om een eigenaar, een deadline, en een
koppeling aan "een incident of risico" — van die drie bestaat er dus precies één.

### O1 — incidenten: volledig klaar en op productie geverifieerd

- Backend: `POST /ai-incidents`, `PATCH /ai-incidents/{id}` (bewust op het bestaande
  `/ai-incidents`-pad, niet het letterlijke `/incidents` uit de hand-off, voor consistentie met de
  al bestaande `GET`). `ai_system_id` blijft verplicht bij aanmaken (niet "optioneel" zoals de
  hand-off's tekst suggereerde) — zonder gekoppeld systeem heeft een incident geen enkele manier om
  aan een organisatie te hangen. Geen extra rolcontrole (spiegelt het bestaande
  `PUT /corrective-actions/{id}/status`). Auditregels bevatten nooit titel-/beschrijvingstekst.
  9 nieuwe tests. Commit `bc8aa33`. CI `37588788575` (success), Deploy `37588990853` (success).
- Portaal: een "Register incident"-formulier + een statusselect per incident op de Governance-tab,
  optimistisch met terugrollen bij een mislukte save. 6 nieuwe tests. Commit `4f86403`.
  CI `37589117624` (success), Deploy `37589246970` (success).
- **Productiecheck:** één echt, toegestaan wegwerp-incident aangemaakt op organisatie 1
  ("TEST (7 okt), mag worden gesloten", gekoppeld aan een echt org-1-systeem) en meteen gesloten via
  de nieuwe statuswissel — blijft bewust op productie staan met status "closed", zoals de hand-off
  toestond. Organisatie 2 kreeg `404` op een poging het te wijzigen en zag een lege lijst.
  `/audit/verify` bevestigd `valid` voor organisatie 1. Een headless-browsercheck bevestigde dat de
  Governance-tab het testincident als "Closed" toont en dat het registratieformulier met alle
  velden opent, zonder CSP-fouten.

**Testaantallen O1:** backend 414 → **423** (+9); portaal 136 → **142** (+6).

### O2/O3 — niet gebouwd, batch gestopt

Reden: `CorrectiveAction` mist de kolommen die O2 nodig heeft (`owner`, `deadline`,
`ai_incident_id`). Dit is precies de stopvoorwaarde die de hand-off zelf benoemt ("een migratie of
nieuw veld nodig lijkt: stop en meld"). Geen migratie uitgevoerd (verboden door zowel de hand-off
als de dagrun-opdracht) en geen workaround geprobeerd (bijvoorbeeld eigenaar/deadline in de vrije
tekst proppen — dat zou het "verzin geen kolom"-principe in de geest schenden).

O3 (risico's aanmaken/bijwerken) was zelf **niet** geblokkeerd — `AIRisk` heeft alle benodigde
kolommen al. Toch bewust niet gebouwd, omdat de dagrun-opdracht de volgorde "O1, daarna O2, daarna
O3" voorschrijft en de hand-off's stopvoorwaarde batch-breed is geformuleerd, niet per onderdeel.

**Wat nodig is om verder te gaan:** een kleine, losse hand-off met een migratie die `owner`,
`deadline` en `ai_incident_id` aan `CorrectiveAction` toevoegt (of een bewust besluit om zonder die
velden verder te gaan), waarna O2 en O3 in een vervolgsessie gebouwd kunnen worden.

**CLAUDE.md bijgewerkt (secties 2, 5, 6, 7) voor Batch O.** Commit `c8ee957`. CI `37608921767`
(success), Deploy `37609091043` (success). Frontend README bijgewerkt: commit `6cc419a`.

---

## Samenvatting commits/runs

| Commit | Repo | Omschrijving | CI | Deploy |
|---|---|---|---|---|
| `14ee3a4` | ai-governance-os | N1: Engelse taaktitels | `37585542117` success | `37585708357` success |
| `27d4322` | ai-governance-os | N2: gedeelde monitoring-tekst-constante | `37585845235` success | `37586075176` success |
| `b6411e9` | ai-governance-os | N3: fix-script voor org 3 | `37586188132` success | `37586377937` success |
| `aaca3f7` | ai-governance-os | N4: eigen AI-register seed-script | `37586672416` success | `37586863483` success |
| `cdbd2e8` | ai-governance-os | CLAUDE.md: Batch N | `37587670567` success | `37587868441` success |
| `bc8aa33` | ai-governance-os | O1 backend: incidenten | `37588788575` success | `37588990853` success |
| `4f86403` | ai-governance-frontend | O1 portaal: incidentenformulier | `37589117624` success | `37589246970` success |
| `c8ee957` | ai-governance-os | CLAUDE.md: Batch O | `37608921767` success | `37609091043` success |
| `6cc419a` | ai-governance-frontend | README: Batch O1 | `37609211431` success | `37609377960` success |

**Testaantallen:** backend 395 → 414 (Batch N) → 423 (Batch O1). Portaal 136 → 142 (Batch O1).

Geen migraties uitgevoerd. Geen nieuwe organisaties geprovisioned. Geen berichten of e-mail
verstuurd. Geen serverwijzigingen (geen apt, geen herstart, geen SSH-/nginx-config). De enige
schrijfacties op productie waren: (1) het daadwerkelijk gevraagde werk van N3 (org 3's tekst
gecorrigeerd) en N4 (org 1's eigen register geladen), en (2) de door de hand-off O1 expliciet
toegestane wegwerp-aanroep (één testincident op org 1, aangemaakt en meteen gesloten, blijft bewust
staan). Alle overige productiechecks waren alleen-lezen, met server-side gemunte tokens die nooit
zijn geprint en na gebruik verwijderd.
