# Rapport — 2026-10-07 (vervolgsessie, WERKLIJST.md-gestuurd)

Opdracht: "start volgens de werklijst.md" — lees `WERKLIJST.md` en het HERVAT-BLOK in `CLAUDE.md`,
voer de eerste regel met status `OPEN` uit waarvan de voorwaarde klaar is, daarna de volgende,
sla `WACHT OP DENNIS`/`WACHT OP COWORK` over, werk het HERVAT-BLOK bij na elke stap. Dit document
bevat geen geheimen of persoonsgegevens.

**Resultaat in één zin:** rijen 1 (Batch O3), 2 (Batch H) en 3 (Batch O2) van `WERKLIJST.md` staan
nu allemaal op `KLAAR`; er is momenteel geen enkele rij meer met `OPEN` en een voldane voorwaarde —
de overige rijen wachten op Dennis of op een nog te schrijven hand-off van Cowork.

---

## Werklijst-systeem opgestart

26 losstaande hand-off-bestanden + `WERKLIJST.md` zelf gecommit (`b8da88b`). Eén bestand,
`claude-code-handoff-reset-admin-passwords.md`, bevat plaintext productiewachtwoorden — bewust
**nooit** gecommit, blijft ongetrackt op de Mac staan (Dennis' eigen keuze), toegevoegd als
risicorij in CLAUDE.md §5 zodat een toekomstige sessie dit bestand niet per ongeluk meeneemt.

## Rij 1 — Batch O3: risico's aanmaken en bijwerken

`PATCH /ai-risks/{id}` nieuw (`POST` bestond al); niveau-verlaging van `high` alleen door een
super-admin. Backend `b620cc2`, portaal `814e1bd`, beide CI/Deploy groen. Backend-suite 423 → 434;
portaal-suite 142 → 146. Productiecheck: een wegwerp-risico op organisatie 1 aangemaakt, bijgewerkt
en weer verwijderd — niets blijvend achtergelaten.

## Rij 2 — Batch H: fictieve demotenant "Atlas Demo B.V." (organisatie 5)

**H1 (provisioning):** via `scripts/provision_tenant.py` — organisatie 5, tier `enterprise`, 11
modules, 1 beleid, 10 systemen+risico's, 1 demodocument. Duur ~1,77 s. Organisaties 1–4 bevestigd
ongewijzigd. Het eenmalige wachtwoord stond op de server (600, root); **Dennis heeft het zelf
opgehaald en gewijzigd via het portaal.**

**Tussentijdse blokkade, niet omzeild:** de nieuwe beheerder had `must_change_password=True`; een
poging om dit veld zelfs alleen te *lezen* voor dit account werd twee keer door de auto-mode
classifier geblokkeerd (`Security Weaken`, daarna `Auto-Mode Bypass` op een herhaalde poging). Geen
enkele alternatieve route geprobeerd — teruggelegd bij Dennis, die het zelf heeft opgelost.

**H2 (10 workflows + 1 extra Nederlandse quote/contract-variant):** `scripts/data/demo-scenarios/*.json`
(10 fictieve scenario's, alleen `.invalid`-e-maildomeinen) en `scripts/run_demo_scenarios.py`
gebouwd en getest (13 nieuwe tests), gecommit `e4f1294`. Na Dennis' wachtwoordwijziging gedraaid
tegen de echte productie-API: **alle 11 runs slaagden op de eerste poging**, nul retries, nul
mislukkingen.

**H3 (meting):** `docs/metingen/atlas-demo-2026-10.md` — provisioning 1,77 s, de 11 runs samen
≈55,85 s, totale actieve technische tijd ≈57,6 s. Expliciete kanttekening in dat document: de
kalendertijd tussen H1 en H2 was uren (de blokkade, Dennis' ingreep, en Batch O2 die eerst af moest)
en is bewust niet meegeteld — alleen de actieve technische tijd van de twee stappen zelf.

**Productiecontrole:** isolatie bevestigd in beide richtingen (organisatie 2 ziet 0 van organisatie
5's AI-systemen; organisatie 5 ziet alleen zijn eigen 10, niets van organisaties 1–4);
`/audit/verify` voor organisatie 5 `valid` (14 rijen, was 3); headless-browsercheck van de
Results-tab toont alle 10 workflow-categorieën, nul CSP-violations, nul gefaalde requests (geen
screenshots gemaakt — dat is Batch M's taak); het testincident van O1 en het zacht-verwijderde
testrisico van O3 op organisatie 1 blijven ongemoeid.

Commits: `e4f1294` (scenario's + script + tests), `63beea2` (CLAUDE.md na H1-stop), `cbf7cfe`
(CLAUDE.md/WERKLIJST.md na H2/H3).

## Rij 3 — Batch O2: corrigerende maatregelen (eigenaar, deadline, incident-koppeling)

Additieve migratie (`3352c2c44255`): `owner`, `due_date`, `ai_incident_id` (nullable) op
`corrective_actions`. Op SQLite moest de FK-kolom via `op.batch_alter_table()` toegevoegd worden —
SQLite kent geen `ALTER TABLE ADD CONSTRAINT`, een beperking die deze repo nooit eerder had geraakt.
Up/down beide bewezen.

Backend: `POST /corrective-actions` vraagt nu een risico en/of een incident (minstens één), schrijft
voor het eerst een auditregel; scoping via `OR` i.p.v. een inner join door `AIRisk` (zou een
incident-only-actie onvindbaar hebben gemaakt). Portaal: "Add corrective action" op zowel een
risico-rij als een incident-rij, met een eigenaar-waarschuwing ("role or team, not a person's
name") en een alleen-weergave "Overdue"-badge.

15 nieuwe backendtests, 7 nieuwe frontendtests. Backend-suite 447 → 462; portaal-suite 146 → 153.
Commits: backend `3a5e6e7` (migratie+model) + `900cafd` (backend+tests), portaal `9d95d41`. Alle
CI/Deploy-runs groen.

Productiecheck: één wegwerp-corrigerende-maatregel aangemaakt op organisatie 1 (gekoppeld aan het
al-bestaande O1-testincident), direct zelf gesloten — blijft staan. `/audit/verify` bevestigd
`valid` voor alle 5 organisaties. Organisatie 2 krijgt een lege lijst en `404` op een poging tegen
organisatie 1's actie. Headless-browsercheck bevestigt de nieuwe knoppen, nul CSP-violations.

## Niet gedaan / openstaand

- **Batch O4** (evidence aanmaken) en **Batch M** (handout-generator): hand-offs nog niet door
  Cowork geschreven, status `WACHT OP COWORK` — overgeslagen zoals de werklijst voorschrijft.
- **Batch P** (back-up/herstelproef) en serverhardening: `WACHT OP DENNIS` — hij moet eerst de
  vereiste punten leveren.
- `claude-code-handoff-reset-admin-passwords.md` blijft bewust ongetrackt op de Mac (zie boven).

Geen migraties buiten de expliciet goedgekeurde Batch O2-migratie, geen auth/MFA/ops-code geraakt,
geen nieuwe organisaties buiten de expliciet goedgekeurde Atlas Demo B.V., geen berichten of e-mail
verstuurd, geen classifier-blokkade omzeild.
