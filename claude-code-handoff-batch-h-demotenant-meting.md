# Hand-off Batch H — fictieve demotenant, alle 10 workflows en doorlooptijdmeting

Auteur: Cowork (architect). Uitvoerder: Claude Code, **één sessie**. Datum: 7 okt 2026. Kan **zonder toezicht**: lees de stopregels. Repo: `ai-governance-os`. Productie: `/opt/valqeron` op `164.92.221.90`.

## Waarom

(1) Er is geen neutrale demo-omgeving: de handout-generator (Batch M) en de ISO-/ISMS-bewijsvoering hebben **fictieve** schermen en runs nodig; organisatie 4 draagt de ISO CERT-context en mag daar niet voor dienen. (2) Definitie van klaar punt 9: alle 10 workflows op één tenant gedraaid en de technische doorlooptijd van provisioning tot "klaar" gemeten. Dit is **geen** meting van een echte klant en geen verkooplead-tijd; het is een technische nulmeting zonder menselijke wachttijden.

## Vooraf besloten (niet opnieuw voorleggen)

- **Fictieve organisatie "Atlas Demo B.V."** (land NL, sector "Professional services", duidelijk fictief; in elke tekst staat dat het demodata betreft). **Alleen fictieve data**: verzonnen bedrijven en personen die niet bestaan, geen echte klant, prospect, collega of Valqeron-gegevens, geen echte e-mailadressen (gebruik het gereserveerde domein `.invalid`).
- **Tier `enterprise`, alle 10 workflows plus `core`.** Dat is ook voor `hr_recruitment_ai`: de demotenant gebruikt uitsluitend verzonnen kandidaten. (De HR-workflow staat voor Valqeron zelf on hold; de demotenant verandert dat niet en mag nergens als "operationeel gebruik" worden gepresenteerd.)
- **Beheerder `atlas_demo_admin`**, e-mail `demo-admin@atlas-demo.invalid`, via `scripts/provision_tenant.py` (eerst `--dry-run`, dan echt) met `--password-file` (eenmalig wachtwoord, nooit geprint, niet in git, niet in het rapport). `include_demo_document` aan, `include_demo_run` uit (je draait de runs zelf). `idempotency_key`: `atlas-demo-2026-10`.
- **Geen migraties, geen wijziging aan auth, MFA, provisioning of de ops-code, geen serverwijzigingen** buiten het draaien van `provision_tenant.py` en de checks hieronder.
- Organisaties 1 t/m 4 blijven **ongewijzigd** (tellingen vóór en na).
- Geen echte e-mail, geen berichten, geen verzending naar derden.

## Werkwijze

0. **Hervatten:** lees eerst het HERVAT-BLOK in `CLAUDE.md` en `WERKLIJST.md`; ga door bij de eerste onvoltooide stap. Elke stap is veilig opnieuw te draaien: de provisioning is idempotent; de scenario's krijgen een vaste sleutel zodat een herhaalde run herkenbaar is.
1. `git pull`, `git status`, `git diff` (drift-check; verwacht de commits van O3 of nieuwer). Meld afwijkingen.
2. **Fase 0 (alleen lezen), eerste alinea van je rapport:** de tierregels, de echte `module_key`'s en `workflow_key`'s (CLAUDE.md §3), de invoerschema's per workflow (lees de `run()`-functies), `provision_tenant.py`-opties, hoe eerdere productiechecks tokens server-side mintten (in geheugen, nooit printen), de pacing-regel (≥13 s tussen logins), de huidige tellingen van de organisaties. Wijkt iets af: stoppen en melden.

## H1 — demotenant aanmaken (en meten)

1. Zet `klant.json` op de server (alleen fictieve gegevens; geen wachtwoord erin). `--dry-run`, daarna echt met `--password-file`. **Noteer met een klok** (`date -u`, of de duur uit het script) het begin en einde van de provisioning.
2. Controleer: organisatie bestaat (nu 5 organisaties), 11 modules actief, tier `enterprise`, het standaard-AI-beleid en per workflow een AI-systeem met risico aanwezig, `/audit/verify` `valid` voor de nieuwe organisatie, org 1 t/m 4 ongewijzigd.
3. **Wachtwoordbestand:** laat het staan op de server (rechten 600, alleen root), noem alleen het pad in het rapport. **Dennis haalt het zelf op en verwijdert het** (zie rapportregel). Maak er geen kopie van.

## H2 — alle 10 workflows draaien met fictieve scenario's

- Maak per workflow een kort, realistisch **fictief scenario** in `scripts/data/demo-scenarios/<workflow_key>.json` (veilig om te committen omdat alles verzonnen is; zet bovenaan een veld `"fictional": true`). Voorbeelden: een verzonnen lead voor sales qualification; een verzonnen factuurtekst voor invoice processing; een verzonnen beleidstekst en kader voor compliance monitoring; een verzonnen kandidaat voor HR; een verzonnen vergadering; een verzonnen offerteaanvraag; een verzonnen klantvraag; een verzonnen bedrijfsvraag voor business intelligence; een marketingcampagne voor een verzonnen product; een vraag over het meegeleverde demodocument voor document intelligence. Invoer in het Engels (portaal en demo zijn Engelstalig); één scenario (quote/contract) mag extra in het Nederlands om de taalkeuze te tonen.
- **Draai ze server-side** met een server-side gemunt token voor `atlas_demo_admin` (alleen in geheugen, niet printen, niets achterlaten), met pacing, via de gewone `POST /workflows/{key}/run`. Eén run per workflow. Een mislukte run één keer opnieuw proberen; blijft het fout: noteren, niet omzeilen.
- **Per run noteren:** `workflow_key`, status, duur in seconden, run-id. **Controleer de uitvoer** op: niet leeg, geen onvervangen placeholders (`<…>`), geen verwijzing naar een echte persoon of organisatie, geen foutmelding. Noteer **niet** de uitvoertekst in het rapport.
- Zet de hele serie in een klein, herbruikbaar script `scripts/run_demo_scenarios.py --org-name "Atlas Demo B.V."` (alleen leesbare invoer, tokenmunting zoals de bestaande productiecheck-aanpak, geen geheimen in het bestand), zodat de handout-generator en de videoproductie dezelfde set later opnieuw kunnen draaien.

## H3 — meting en rapportage van de doorlooptijd

Maak een tabel in het rapport met: duur provisioning; tijd van de eerste tot de laatste workflowrun; duur per workflow; totale technische doorlooptijd van het begin van H1 tot de tiende geslaagde run; aantal mislukte of herhaalde runs. Zet bovenaan: "technische nulmeting, zonder menselijke wachttijden, fictieve data". Schrijf dezelfde tabel naar `docs/metingen/atlas-demo-2026-10.md` (geen persoonsgegevens, geen uitvoertekst).

## Tests

Backend: een test voor `run_demo_scenarios.py` met gemockte workflows (invoer geldig volgens het schema, `fictional: true` aanwezig, geen `.invalid`-adres ontbreekt, geen echt domein in de scenario's) en een test dat elk scenarioschema bij een bestaande `workflow_key` hoort. `pytest -q -m "not codex"` volledig groen (nu 423, daarna meer). Geen portaalwijziging verwacht.

## Productiecontrole (alleen lezen, behalve de eigen runs)

- Isolatie: een gebruiker van organisatie 2 ziet niets van de demotenant (`404` of lege lijsten); `atlas_demo_admin` ziet niets van de organisaties 1 t/m 4.
- `/audit/verify` `valid` voor alle vijf organisaties.
- De Results-tab van de demotenant toont de 10 runs (headless browsercheck met het server-side token, geen CSP-fouten); maak **geen** screenshots voor de handout in dit batch (dat doet Batch M).
- Het testincident van O1 en het O3-wegwerprisico op organisatie 1 blijven ongemoeid.

## Stopvoorwaarden

Stop en meld als: een migratie nodig lijkt; auth, MFA, provisioning of ops-code geraakt wordt; er een echte persoon of organisatie in een scenario of uitvoer opduikt; een wachtwoord of token in een bestand, log of chat zou moeten (classifier-blokkade niet omzeilen); organisatie 1 t/m 4 veranderen; een isolatietest faalt; tests rood worden; een Deploy twee keer achter elkaar faalt; meer dan twee workflows twee keer na elkaar falen; de schijf boven 80% komt. Bij een **gebruikslimiet**: werk het HERVAT-BLOK bij (welke stap, welke runs al gedaan), commit, push en stop netjes; Dennis typt later "continue".

## Rapport

Fase 0-bevindingen; het pad van het wachtwoordbestand (niet de inhoud); tellingen van organisaties vóór en na; per workflow status, duur en run-id; de meettabel; wat de controles per run lieten zien; isolatie en audit-uitkomsten; commits (hash en doel), CI-/Deploy-run-id's; testaantallen vóór en na; beslissingen die je zelf nam; CLAUDE.md (§2, §5, §6, §7) bijgewerkt met commit-hash; HERVAT-BLOK en `WERKLIJST.md` bijgewerkt. **Dennis moet nog:** het wachtwoordbestand ophalen en verwijderen, en de demo-logingegevens veilig bewaren.
