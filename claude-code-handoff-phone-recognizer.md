# Handoff voor Claude Code — NL-telefoonnummer-recognizer testen, committen, pushen

Kort en puur uitvoerend: dit is de laatste stap van de PII-telefoonnummerdetectie-beslissing (zie CLAUDE.md sectie 4 actie 2, sectie 5, sectie 6, sectie 7, en `readiness-plan.md` sectie 11 in het projectdocument voor het volledige verhaal). Geen ontwerpkeuzes meer nodig — Dennis heeft al gekozen ("Regex-recognizer toevoegen") en de code staat al klaar in de working tree.

## Context in het kort

Bij de productieverificatie van de AVG-anonimiseringslaag (eerder vandaag, commits `b4c4b22`/`cbe6b06`) bleek het Nederlandse telefoonnummerformaat "06-12345678" niet betrouwbaar gedetecteerd te worden door Presidio's ingebouwde `PHONE_NUMBER`-recognizer, met de (door Python 3.9 afgedwongen) oudere spaCy-modellen. Dennis koos voor een aanvullende, patroonbased `NL_PHONE_recognizer` — exact hetzelfde ontwerp als de bestaande `NL_BSN`-recognizer in dezelfde file.

## Wat er al klaarstaat in de working tree

- `app/core/pii_anonymizer.py`: nieuwe `_is_valid_nl_phone()` + `_build_nl_phone_recognizer()`, geregistreerd in `_init_analyzer()` naast de bestaande `_build_nl_bsn_recognizer()`. Plus een nieuwe bullet in de moduledocstring ("Ontwerpkeuzes") die dit toelicht.
- `tests/test_pii_anonymizer.py`: 7 nieuwe pure-logic tests voor de validator, 1 nieuwe presidio-vereisende test tegen false positives (IBAN-cijferstaart), 2 nieuwe e2e-tests (incl. 4 notatievarianten), en de bestaande `test_anonymize_text_redacts_dutch_name_and_email` uitgebreid met een `<TELEFOONNUMMER>`-assertie op de al aanwezige "06-12345678"-reproductiezin.

Geen wijzigingen aan `requirements.txt` nodig — geen nieuwe dependency, alleen `re`/`presidio_analyzer` die de file al gebruikte.

## Stappen

1. `git status`/`git diff` op beide bestanden — bevestig dat dit exact is wat hierboven beschreven staat, geen onverwachte bestanden.
2. `pytest -q` in de échte repo-omgeving (Python 3.9-venv, de échte `presidio-analyzer==2.2.360` + `spacy==3.7.5` + `nl_core_news_lg`/`en_core_web_lg` 3.7.0-modellen). **Dit is de eerste keer dat deze recognizer tegen het daadwerkelijke Nederlandse productiemodel loopt** — de Cowork-sessie die dit bouwde had geen Nederlands spaCy-model beschikbaar en heeft het mechanisme alleen met een Engels testmodel + presidio 2.2.360 geverifieerd (taal-onafhankelijke regex/validator-logica, dus het mechanisme zelf is bewezen, maar niet de exacte `nl_core_news_lg`-taalregistratie). Controleer specifiek:
   - `test_anonymize_text_redacts_dutch_name_and_email` (nu met de `<TELEFOONNUMMER>`-assertie)
   - `test_anonymize_text_redacts_nl_mobile_number_format_variants` (vier notatievarianten)
   - `test_nl_phone_pattern_does_not_match_inside_an_iban` (regressie tegen de false positive die tijdens het bouwen werd gevonden en gefixt)
3. Als er onverhoopt een test faalt: dit raakt kern-detectielogica, dus graag eerst terugkoppelen (in CLAUDE.md sectie 4/6 zoals gebruikelijk) voordat je zelf de regex/validator aanpast — niet omdat het verboden is, maar omdat een wijziging aan de detectielogica zelf weer instructies van Dennis vraagt volgens de bestaande afspraak in dit project.
4. Als groen: committen (bijv. `"Add NL_PHONE regex recognizer to fix 06-XXXXXXXX detection gap"`) en pushen naar `origin/main` — dit deployt zichzelf via de nu bewezen werkende CD-pijplijn.
5. Na deploy: bevestig met een echte productie-aanroep (zelfde aanpak als bij de PII-laag zelf — rechtstreekse functie-aanroep via SSH, of een workflow-run met een demo-tenant) dat de exacte reproductiezin "Contactpersoon: Jan de Vries, e-mail jan.devries@acme.nl, telefoon 06-12345678." nu ook het telefoonnummer redigeert, niet alleen naam/e-mail — zodat dit ook op productie zelf bevestigd is, niet alleen in CI.
6. CLAUDE.md bijwerken zoals gebruikelijk (sectie 6 nieuwe regel, sectie 7 herschrijven) — met dit afgerond is er geen puur-technisch engineeringpunt meer over zonder externe afhankelijkheid; het volgende punt (DPA/verwerkersovereenkomst) hangt van een jurist af, niet van code.
