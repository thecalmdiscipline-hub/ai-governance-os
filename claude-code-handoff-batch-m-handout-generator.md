# Hand-off Batch M — handout-generator per tenant (NL en EN, licht en printvriendelijk)

Auteur: Cowork (architect). Uitvoerder: Claude Code, **één sessie, meerdere fasen**. Datum: 8 okt 2026. Kan **zonder toezicht**: lees de stopregels. Repo: `ai-governance-os` (map `tools/handout/`, script `scripts/generate_handout.py`). Vervolg op Batch H (demotenant "Atlas Demo B.V." = organisatie 5) en Batch O (Governance-tab kan nu aanmaken en bijwerken).

## Waarom

Een klant krijgt bij de overdracht een PDF-handout die precies bij zijn omgeving past: alleen de actieve modules, in NL of EN, met schermafbeeldingen uit een fictieve demotenant, in minuten gemaakt in plaats van met de hand. Nu bestaat er één algemene Client Portal Guide die alle tien workflows beschrijft, ook voor klanten die er twee hebben. Dit batch bouwt de generator en maakt voorbeeld-handouts; **verzenden doet Claude Code nooit**.

## Bronnen (Cowork heeft ze in de repo gezet)

- `docs/handout/handout-inhoud-concept.md`: de NL/EN-teksten (gedeelde delen, 10 modules), het claimregister (C1 t/m C16), de verboden-woordenlijst en de stijlgids. **Dit is de inhoudsbron.** Zet de teksten om in `handout/shared.yaml`, `handout/modules.yaml` en `handout/claims.yaml`, NL en EN onder dezelfde sleutel. Verander de betekenis niet. Klopt een feit niet met de code of `CLAUDE.md`: niet afzwakken of verzinnen, maar melden (zie stopvoorwaarden).
- `CLAUDE.md` (§2, §3, §5, §6) voor feiten en bewijs; `app/services/tenant_modules.py` voor de tierregels (nooit een kopie in de handout).
- Hergebruik de bestaande bouwscripts van de Client Portal Guide en de ISO CERT-PDF (`build_pdf_prospect.py` of vergelijkbaar) en merkassets; zoek ze in Fase 0.

## Vooraf besloten (niet opnieuw voorleggen)

- **NL en EN allebei vanaf het begin**, als twee losse PDF's (nooit door elkaar). Stijl licht en printvriendelijk volgens de stijlgids; kleuren en lettertype uit de portaal-tokens lezen, geen eigen schatting.
- **De generator praat niet met productie en heeft nooit een token nodig.** Invoer is één config-bestand per handout (JSON, geen persoonsgegevens): `tenant_name`, `tier`, `modules` (lijst `module_key`, plus `core`), `language`, `generated_for` (optioneel), `confirmed_blocks` (lijst; zie hieronder). Config met de hand of uit een bestaand ops-pad gemaakt; de tenant-ophaalstap staat niet in de generator.
- **Contactgegevens:** komen uit een apart `contact.json` (velden `urgent_phone`, `urgent_hours`, `security_contact`) dat Dennis later aanlevert. **Ontbreekt dat bestand of een veld, dan maakt de generator uitsluitend een concept** met op elke pagina de markering "CONCEPT, contactgegevens ontbreken" (NL) of "DRAFT, contact details missing" (EN), en **weigert** het een definitieve uitvoer. De voorbeeld-handouts van dit batch zijn daarom altijd concepten.
- **HR-module vergrendeld:** het blok `hr_recruitment_ai` wordt alleen opgenomen als `confirmed_blocks` die sleutel bevat. Staat de module wel in `modules` maar niet in `confirmed_blocks`: de generator stopt met een duidelijke melding en maakt geen PDF. In de voorbeeldconfig van dit batch staat HR niet in `modules`.
- **Screenshots alleen uit de demotenant** "Atlas Demo B.V." (organisatie 5): nooit klantdata, niet organisatie 4. Playwright/Chromium, vaste afmetingen 1440×900, server-side gemunt token **alleen in geheugen** (zoals bij de eerdere productiechecks en `run_demo_scenarios.py`), geen credentials in bestanden, niets printen.
- **Versheid:** elke screenshotset krijgt het portaal-commit (`build_sha` uit `/health` of de laatste frontend-deploy) als stempel in de bestandsnaam of een manifest. De generator waarschuwt (breekt niet stilzwijgend door) bij een set die ouder is dan de laatste frontend-deploy van een relevant scherm.
- **Waar het draait:** lokaal op de Mac of in een Claude Code-sessie, **niet** op de productieserver (geheugen). Geen serverwijzigingen.
- **Uitvoer:** `Valqeron-Handout_<tenant-slug>_<nl|en>_<JJJJ-MM-DD>_<sha>.pdf` in een **gitignored** map `handouts/`; de PDF's komen niet in git en niet in het portaal. Versie op de laatste pagina: sjabloonversie plus de commit-hash van `CLAUDE.md`.
- **Verzenden:** nooit. Dennis leest de eerste vijf handouts volledig en verstuurt zelf.
- **Geen migraties.** Geen wijziging aan auth, MFA, provisioning, ops-code of bestaande endpoints. Geen portaalwijziging in dit batch (de config-knop in de Ops-tab is een latere optie).
- **Nieuwe afhankelijkheden:** alleen wat al in de bestaande bouwscripts zit (bijvoorbeeld Jinja2, PyYAML, Playwright). Zet ze in `tools/handout/requirements.txt`, niet in de productie-`requirements.txt`. De lokale dev-venv staat op Python 3.9: kan een afhankelijkheid daar niet draaien, stop en meld (niet de venv ombouwen).

## Werkwijze

0. **Hervatten:** lees eerst het HERVAT-BLOK in `CLAUDE.md` en `WERKLIJST.md`; ga door bij de eerste onvoltooide fase. Elke fase is veilig opnieuw te draaien (vaste uitvoernamen, geen dubbele schermafbeeldingen).
1. `git pull`, `git status`, `git diff` (drift-check; verwacht backend `3a4a5d9` of nieuwer). Meld afwijkingen.
2. **Fase 0 (alleen lezen), eerste alinea van je rapport:** modulecatalogus (`BASE_MODULES`) en tierregels uit de code; welke workflows een startformulier hebben (vlag `has_start_form` per module, uit de portaalcode); de exacte invoer- en uitvoervelden van `quote_contract_generator`; wat een klant in de Governance-tab echt kan (aanmaken, bijwerken, status wijzigen, per onderdeel); portaal-tokens (kleuren, lettertypen); bestaande PDF-bouwscripts en merkassets; of Playwright/Chromium en de overige afhankelijkheden lokaal draaien; huidige `build_sha` van het portaal. Wijkt iets af van dit document of van het concept: stoppen en melden.
3. Kleine losse commits per fase; na elke push CI en Deploy controleren (`DEPLOY CHECK OK`) waar van toepassing.

## Bouw

**M1 — Bronnen en controles.** `tools/handout/handout/shared.yaml`, `modules.yaml` (NL en EN, 10 modules plus `core`), `claims.yaml` (C1 t/m C16 met het exacte bewijs: testbestand of plek in de code). Automatische, blokkerende controles in `tools/handout/checks.py`: (1) verboden woorden NL en EN met de ontkenningsregel uit het concept; (2) claimregister: elke claim-ID in de tekst heeft bewijs, en elke zin met "altijd", "nooit", "elke" of een getal heeft een claim-ID of een expliciete uitzondering; (3) volledigheid: de handout bevat precies de modules uit de config, en een test faalt als een sleutel uit de catalogus geen sjabloon heeft of andersom; (4) de HR-vergrendeling en de contact-poort. Tests voor alle vier, ook met opzettelijk foute invoer.

**M2 — Renderer.** Jinja-sjabloon (licht, printvriendelijk, stijlgids), `scripts/generate_handout.py --config <klant>.json [--contact contact.json] --out <map> [--screenshots <map>]`, PDF via headless Chromium. Voorpagina, kop- en voettekst, achterpagina met contactblok, gedeelde delen, per actieve module de vijf kopjes (vlag `has_start_form` bepaalt de terugvalzin), tierinformatie uit `tenant_modules.py`. **Rendercheck** als vierde kwaliteitscontrole: pagina's naar PNG; geen lege pagina's, geen losse onderschriften, geen afgekapte schermafbeeldingen, geen kop als laatste regel. Test dat de PDF's NL en EN bestaan en dat een concept zonder contact de markering draagt.

**M3 — Schermafbeeldingen.** `tools/handout/capture_screenshots.py` tegen `https://app.valqeron.com` met een server-side gemunt token voor `atlas_demo_admin` (alleen in geheugen), voor de tabs Home, Core, Products, Results, Documents, Governance, Account en per module één of twee vaste schermen (waar het portaal een startformulier heeft). Manifest met `build_sha`, afmetingen en tijdstip; geen klantdata of tokens in het manifest. Controleer elke afbeelding op wachtwoorden, tokens en echte namen (er hoort alleen fictieve demodata op te staan). Geen CSP-fouten of gefaalde requests tijdens het vastleggen.

**M4 — Voorbeelden.** Twee configs onder `tools/handout/examples/`: (a) `atlas-demo-enterprise.json` met `core` plus alle modules **behalve** `hr_recruitment_ai`; (b) `starter-example.json` met `core` plus twee modules. Genereer NL en EN voor beide (vier PDF's, alle als concept zonder `contact.json`) naar `handouts/` (gitignored). Zet daarnaast `handouts/LEES-MIJ-DENNIS.md` met twee lijsten: "dit is gecontroleerd" en "dit moet jij lezen vóór verzending", plus de punten die Dennis nog moet aanleveren (contact.json, HR-bevestiging, stijlgoedkeuring op de proefpagina's). Dit bestand bevat geen geheimen.

## Tests

Backend/tools: `pytest -q -m "not codex"` volledig groen (nu 462 + O4 + R), plus de nieuwe tests voor M1 en M2; geen testmarker voor de schermafbeeldingen die netwerk nodig hebben. Lint volgens het project. Geen portaaltests nodig (geen portaalwijziging).

## Productiecontrole (alleen lezen, behalve het inloggen van de demobeheerder)

Alleen M3 raakt productie: lezen van het portaal als `atlas_demo_admin`. Daarna: `/audit/verify` `valid` voor alle vijf organisaties, organisaties 1 t/m 4 ongewijzigd, het wachtwoord van de demobeheerder niet aangeraakt of gelezen. Geen schrijfacties in het portaal tijdens het vastleggen (alleen kijken en openen van tabs).

## Stopvoorwaarden

Stop en meld als: een token of wachtwoord in een bestand, log of chat zou moeten komen; er klantdata op een schermafbeelding zichtbaar is; een claim in de tekst geen bewijs heeft (eerst melden, niet afzwakken); een feit in het concept niet met de code klopt; een afhankelijkheid niet draait op de lokale Python; de classifier iets blokkeert (niet omzeilen); een migratie of serverwijziging nodig lijkt; tests rood; een Deploy twee keer achter elkaar faalt; de schijf boven 80%. Bij een **gebruikslimiet**: werk het HERVAT-BLOK bij (welke fase M1 t/m M4, welke bestanden al bestaan), commit, push en stop netjes; Dennis typt later "continue".

## Rapport

Fase 0-bevindingen en afwijkingen van het concept; commits (hash en doel), CI-/Deploy-run-id's; testaantallen vóór en na; per kwaliteitscontrole wat hij bij de voorbeelden vond; paginaaantal per voorbeeld-PDF; welke modules `has_start_form` hebben; waar teksten zijn aangepast aan de code en waarom; Dennis' openstaande punten (contact.json, HR-bevestiging, stijlgoedkeuring); CLAUDE.md (§2, §5, §6, §7) bijgewerkt met commit-hash; HERVAT-BLOK en `WERKLIJST.md` (status `KLAAR`) bijgewerkt. Geen PDF's in git, niets verzonden.
