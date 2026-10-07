# Hand-off voor Claude Code: testorganisatie "ISO Cert International" aanmaken op productie

## Context

Dennis wil een fictieve testorganisatie in het echte Valqeron-systeem, om de workflows die aan de prospect ISO CERT INTERNATIONAL zijn beloofd (zie `Valqeron-for-Certification-Bodies-ISO-CERT-INTERNATIONAL.pdf`, door een Cowork-sessie geleverd) daadwerkelijk te draaien, te screenshotten, en tot een demo te verwerken. Deze sessie (Cowork) heeft geen SSH-/serverd-toegang en kan deze stap dus niet zelf uitvoeren — vandaar deze hand-off. Zodra dit gedaan is, pakt de Cowork-sessie het testen + screenshots + demo-opbouw zelf op via de browser.

Volledig plan (achtergrond, testscenario's, motivatie): `claude/iso-cert-international-demo-plan.md` in het gekoppelde claude.ai-project "AI business" — niet nodig om te lezen voor deze specifieke stap, maar goed om te weten dat het bestaat.

## Wat nodig is

**1. Nieuwe organisatie aanmaken:**
- Naam: `ISO Cert International`
- Land: `GB`
- Sector: `Certification body / conformity assessment`
- Gebruik het volgende vrije `organization_id` (org 1 = Valqeron/tenant 1, org 2 = "Valqeron Demo Org 2" — dus waarschijnlijk 3, maar controleer eerst wat er al bestaat in plaats van dit aan te nemen).

**2. 8 modules toewijzen via `TenantModule` (`is_active=True`):**
```
core
sales_qualification_ai
document_intelligence
compliance_monitor
business_intelligence
quote_contract_generator
meeting_agenda_assistant
customer_support_ai
```
Bewust **niet** toewijzen: `invoice_processing_ai`, `hr_recruitment_ai`, `marketing_automation_ai` (staan niet in de aan de prospect beloofde scope).

**3. Eén admin-gebruiker aanmaken voor deze organisatie:**
- Voorgestelde username: `isocert_demo_admin` (of iets vergelijkbaars, maakt niet uit)
- Rol: admin
- Wachtwoord: zelf genereren, **rechtstreeks met Dennis delen (chat/anders), niet opnemen in CLAUDE.md, deze hand-off, of enig ander git-getrackt bestand** — zelfde aanpak als bij `dennis_admin`/`customer2_admin` op 18 sep 2026.

**4. Verifiëren:**
Een echte `POST /login`-aanroep tegen `https://api.valqeron.com` doen met de nieuwe credentials (zelfde patroon als eerder gebruikt) om te bevestigen dat de hash/login-flow werkt — niet alleen aannemen dat de DB-write is gelukt.

**5. Uitvoeringswijze — aan jou:**
Kies zelf of dit een eenmalig, niet-gecommit script is (zoals bij de `dennis_admin`/`customer2_admin`-aanmaak op 18 sep — org is een prospect, geen betalende klant, dus permanent in `scripts/seed_modules.py`'s `SEED_DATA` opnemen is niet per se gewenst) of dat je het toch structureel wilt maken. Als er een bestaand, herbruikbaar patroon is (zoals `scripts/create_local_customer_2.sh`, maar dan voor productie) gebruik dat gerust als basis.

## Rapportage nodig (aan Dennis, die het weer aan de Cowork-sessie doorgeeft — of direct als je een kanaal hebt)

- Het gebruikte `organization_id`.
- Bevestiging dat alle 8 modules actief staan.
- De gebruikersnaam (het wachtwoord los, rechtstreeks aan Dennis).
- Resultaat van de login-verificatie.
- CLAUDE.md-regel toevoegen zoals gebruikelijk (sectie 6).

Zodra dit bevestigd is, logt de Cowork-sessie zelf in via de browser en doorloopt de 7 testscenario's uit het plan-document om er een demo van te bouwen.
