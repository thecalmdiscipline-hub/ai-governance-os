# Hand-off Batch E2 — Microsoft-sync-bug en klein opruimwerk

Auteur: Cowork (architect). Uitvoerder: Claude Code. Datum: 21 sep 2026.
Repo's: `ai-governance-os` (backend) en `ai-governance-frontend` (portaal).

**Start pas als Dennis meldt dat Batch E volledig klaar is** (backend én portaal). Doe daarom eerst een nieuwe drift-check: zowel de MFA-code als het portaal zijn dan veranderd, en dit document is geschreven vóór dat rapport. Wijkt iets af van wat hieronder staat, meld dat in plaats van te gokken.

## Doel

1. De bug repareren waardoor "Sync documents" in het portaal altijd faalt.
2. Een paar kleine opruimpunten uit de parkeerlijst afronden.

Geen nieuwe functies. Geen wijzigingen aan auth of MFA.

## Werkwijze (vaste afspraken)

1. Begin in beide repo's met `git status` en `git diff`. Meld afwijkingen.
2. Kleine losse commits per onderdeel. Na elke push: CI én Deploy controleren via de GitHub Actions-API, en bij het portaal `DEPLOY CHECK OK`.
3. Geen tokens, wachtwoorden of DSN's in output, logs of git. Geen nieuwe zware dependencies; meld elke nieuwe.

## Deel 1 — Microsoft "Sync documents" (backend en portaal)

**Wat we weten uit het D2-rapport:**
- `src/components/MicrosoftConnect.tsx:51` stuurt bij elke klik op "Sync documents" `POST /microsoft/sync` met `access_token: 'TEMP_TOKEN_REPLACE'`.
- De backend (`app/api/microsoft.py`, rond regel 122-132) gebruikt een aangeleverd token in plaats van het opgeslagen `MicrosoftToken`. Graph krijgt daardoor de placeholder en de sync faalt.
- "Connect Microsoft 365" gebruikt de placeholder niet.

**Gewenst:**
- Backend: `POST /microsoft/sync` gebruikt **alleen** het opgeslagen `MicrosoftToken` van de organisatie van de ingelogde gebruiker. Een `access_token` in de request body wordt genegeerd (het veld mag optioneel blijven staan voor compatibiliteit, maar wordt nooit meer gebruikt). Verloopt het opgeslagen token en is er een refresh-token en bestaande refresh-logica, gebruik die; bestaat die logica niet, bouw hem **niet** in deze batch, maar geef dan een duidelijke fout terug (bijv. `409` met `{"error":"microsoft_token_expired"}`). Is er helemaal geen verbinding: `409` met `{"error":"microsoft_not_connected"}`. Bevestig eerst in de code hoe tokens worden opgeslagen, en of `MicrosoftToken` per organisatie of per gebruiker is; houd de tenant-isolatie intact (een organisatie mag nooit het token van een andere gebruiken).
- Portaal: verwijder de placeholder en stuur geen token meer mee. Toon bij de twee foutcodes een duidelijke, korte melding ("Microsoft 365 is niet verbonden" en "Verbinding met Microsoft 365 is verlopen, verbind opnieuw") in plaats van een stille of cryptische fout.
- Tokens komen nooit in logs, Sentry of foutmeldingen. Controleer dat de Microsoft-endpoints geen token in een auditregel of logregel zetten.

**Tests:** backend-tests met een gemockte Graph-client (geen netwerk): sync met opgeslagen token slaagt, sync zonder verbinding geeft `409 microsoft_not_connected`, een meegestuurd `access_token` in de body verandert niets aan welk token gebruikt wordt, en een andere organisatie kan het token niet gebruiken. Portaal: Testing Library-test dat de request-body geen `access_token` bevat en dat beide foutmeldingen getoond worden.

**Belangrijk in je rapport:** zeg expliciet dat de sync **niet live** getest is tegen echt Microsoft 365 (daar is een testaccount van Dennis voor nodig) en wat er precies wél is gedekt. Beweer niet dat de sync "werkt".

## Deel 2 — Kleine opruimpunten

Elk als aparte commit; sla een punt over en meld het als het groter blijkt dan hier staat.

a. **`ResultsPage`-helpers naar `src/lib/`:** de samenvatting- en metric-functies uit `ResultsPage.tsx` verplaatsen naar `src/lib/` (geëxporteerd), zonder gedragswijziging, met unit-tests. Zo raakt `react-refresh/only-export-components` niet meer in de knoop. De `--max-warnings=0`-lint blijft groen. Toon voor en na dat de gebouwde weergave gelijk blijft (zelfde tabs laden op productie met een server-side gemunt token, zoals bij D2, zonder tokens te printen).

b. **Sentry-release-naam gelijktrekken:** het portaal gebruikt de volledige 40-tekens-sha, de backend 7 tekens (`e71a77f`). Laat het portaal de eerste 7 tekens gebruiken (in de build-configuratie of in `src/main.tsx`; kies de plek die het minste raakt) en controleer met de bestaande `scripts/sentry-smoke.mjs` dat het event de korte release draagt. Stuur maximaal één testevent.

c. **`import openai` in de warm-up:** de eerste `import openai` kost ~1,9 s bij het eerste verzoek. Neem hem op in `pii_anonymizer.warm_up()` (of de logisch dichtstbijzijnde startup-plek), zonder het opstartgedrag bij falen te veranderen (warm-up mag nooit crashen). Meet de opstarttijd tot `/health` ok vóór en na (dat mag maximaal een paar seconden langer zijn) en meld de geheugendelta. De systemd-unit verandert niet.

d. **`DEPLOY_RECOVERY.md` bijwerken:** het document is achterhaald. Herschrijf het naar de huidige situatie in gewoon Nederlands: hoe de backend deployt (CI → Deploy, `deploy.sh`, rollback bij falen), hoe de frontend deployt en terugrolt (`scripts/rollback.sh`, release-symlink), de handmatige unit-sync-procedure, de SSH-noodprocedure voor MFA uit Batch E, waar Sentry staat, en wat te doen bij een 502. Alleen dingen opnemen die je op de server of in de repo hebt kunnen controleren.

## Bewust niet in deze batch

- Python 3.12 (productie) versus 3.9 (CI/lokaal) gelijktrekken: raakt CI, dependencies en tests, eigen batch.
- De `root`-deploysleutels vervangen door een beperkte deploy-gebruiker: heeft handelingen van Dennis nodig, eigen batch.
- `include_source_context` uitzetten in Sentry, tag `organization_id`, source maps: Dennis beslist later.
- Alles rond MFA/`/ops` (Batch E) en provisioning (Batch F).

## Afronden

- CLAUDE.md in `ai-governance-os`: sectie 5 (risico's bijwerken), sectie 6 (logregel, nieuwste bovenaan), sectie 7 (volgende stap: Dennis rondt MFA-inschrijving en super-admin af, daarna Batch F). Vooraf `git status`/`git diff`, en na de commit verifiëren dat de wijziging blijft staan.
- README van het portaal ("Known gaps") bijwerken.

## Stopvoorwaarden

Stop en meld als: de Microsoft-code niet overeenkomt met wat hierboven staat; een fix de tenant-isolatie zou raken; tests rood worden; een Deploy faalt (de pijplijn draait dan zelf terug, meld dat); je tokens of geheimen in output, logs of git zou moeten zetten.

## Rapport

Geef: drift-check en afwijkingen; commits (hash + doel) met CI/Deploy-run-id's; wat Deel 1 precies dekt en wat niet (niet live getest tegen Microsoft); per punt in Deel 2 wat je deed en gemeten hebt (opstarttijd en geheugen bij punt c); testaantallen vóór en na; de nieuwe `DEPLOY_RECOVERY.md` in één alinea samengevat.
