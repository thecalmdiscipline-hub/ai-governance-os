# Hand-off Batch J — herstelbare PII-anonimisering op de overige 9 workflows

Auteur: Cowork (architect). Uitvoerder: Claude Code, **één sessie**. Datum: 6 okt 2026.
Repo: `ai-governance-os` (backend).

## Doel

Op 5 okt is voor Quote & Contract Generator een terugzet-mechanisme gebouwd (`anonymize_text_with_mapping()` en `restore_placeholders()` in `app/core/pii_anonymizer.py`, commits `7a2e251`, `4770448`). Alle andere workflows hebben hetzelfde structurele risico: ze sturen geanonimiseerde invoer naar het taalmodel en geven vrije tekst terug waarin een ruwe placeholder (`<LOCATIE>`, `<PERSOON_2>`) kan staan. Dennis heeft besloten (6 okt) dat dit ook voor de overige 9 workflows wordt aangesloten. Hierna kan Batch H alle 10 workflows meten zonder lekken.

## Vooraf besloten (niet opnieuw voorleggen)

- Gebruik **dezelfde gedeelde functies** als bij Quote & Contract Generator. Geen aparte logica per workflow. Wijkt een workflow structureel af (bijvoorbeeld uitvoer die geen vrije tekst is), meld dat dan en pas alleen de relevante velden aan.
- Het terugzetten gebruikt alleen de mapping van dit ene verzoek, gaat alleen terug naar dezelfde gebruiker, en herstelde tekst en mapping komen **niet** in logs, auditregels of Sentry.
- Het vangnet blijft: een placeholder-vormig token dat niet in de mapping staat, wordt nooit ruw getoond (`"[omitted]"`), alleen aantal en placeholdernaam worden gelogd.
- `anonymize_text()` zelf blijft ongewijzigd.
- Gedrag **zonder** placeholders blijft identiek aan nu (zelfde uitvoer, zelfde velden).
- Geen wijzigingen aan auth, MFA, provisioning of andere organisaties. Geen portaalwijziging.

## Werkwijze

1. `git status` en `git diff` (drift-check, verwacht `8e423be` of nieuwer). Meld afwijkingen.
2. **Fase 0 (alleen lezen), eerste alinea van je rapport:** een tabel van alle workflows (behalve Quote & Contract Generator) met per workflow: welke invoervelden worden geanonimiseerd, welke uitvoervelden zijn vrije tekst (die het taalmodel schrijft) en dus herstel nodig hebben, en welke zijn gestructureerd (getallen, enums, ids) en dus niet. Wijkt iets af van dit document: stoppen en melden.
3. Kleine losse commits; na elke push CI en Deploy controleren (GitHub Actions-API), plus een echte functionele check op productie.

## Uitvoering

- Per workflow: vervang `anonymize_text()` door `anonymize_text_with_mapping()` waar de uitvoer terugkomt bij de gebruiker, en laat elk vrij-tekst-uitvoerveld door `restore_placeholders()` lopen vóór het wordt teruggegeven. Houd `tests/workflows/test_pii_anonymizer_wiring.py` actueel (nu spiedt die op `anonymize_text()` voor alle workflows; pas aan voor de nieuwe aanroep, zonder het doel van de test te verzwakken).
- Genummerde placeholders per distincte waarde blijven zoals nu. Een waarde die in de invoer vaker voorkomt krijgt één placeholder.
- Documenten: let op workflows die documentinhoud gebruiken (Document Intelligence, Compliance Monitor). Meld hoe die documentinhoud wordt geanonimiseerd en of terugzetten daar zinvol en veilig is (het terugzetten gaat alleen naar dezelfde gebruiker die het document zelf aanleverde). Twijfel je, stop en meld in plaats van te kiezen.

## Tests

Per workflow (of gedeeld via parametrisatie): placeholder in invoer wordt in de uitvoer teruggezet; een door het model verzonnen of ongemapte placeholder komt niet ruw terug (`[omitted]`); uitvoer zonder placeholders is identiek aan vóór de wijziging; geen mapping of herstelde tekst in logs of een Sentry-event (met `caplog` en de bestaande Sentry-testopzet); fail-closed gedrag van de anonimisering blijft overeind. Alle bestaande tests blijven groen; `pytest -q -m "not codex"` volledig groen.

## Productiecheck (server-side gemunt token voor `isocert_demo_admin` in geheugen, niet printen, **wachtwoord niet resetten of aanraken**)

Eén echte run op org 4 voor **één** workflow met een invoer die zeker een placeholder oplevert (bijvoorbeeld de Northbridge-casus met "Sheffield" in een vrij-tekstveld), met een regex-scan `<[A-Z][A-Z_-]*(_\d+)?>` over de volledige uitvoer: nul treffers, en de echte waarde staat in de tekst. Rapporteer run-id en uitkomst, geen persoonsgegevens. Meer OpenAI-runs zijn niet nodig; de tests dekken de rest.

Is er geen token mogelijk zonder het wachtwoord te resetten: stop, meld het en sla de productierun over; de tests blijven dan de dekking.

## Stopvoorwaarden

Stop en meld als: een wijziging auth, MFA of andere organisaties zou raken; uitvoer verandert zonder placeholders; documentinhoud niet veilig kan worden teruggezet; een mapping of herstelde tekst in een log of Sentry-event zou komen; tests rood worden; een Deploy faalt (de pijplijn draait zelf terug, meld het); de classifier iets blokkeert (niet omzeilen, melden).

## Rapport

Fase 0-tabel; commits (hash en doel), CI- en Deploy-run-id's; per workflow wat is aangesloten en wat niet (met reden); testaantallen vóór en na; productiecheck (run-id, uitkomst); CLAUDE.md (§2, §5, §6, §7) bijgewerkt met commit-hash, inclusief het sluiten van de open beslissing over de overige 9 workflows.
