# Hand-off Batch D2 — Frontend opruimen (lint blokkerend, basistests)

Auteur: Cowork (architect). Uitvoerder: Claude Code. Datum: 21 sep 2026.
Repo: `ai-governance-frontend` (portaal). Backend-repo alleen voor de CLAUDE.md-update.

## Doel

Vóór Batch E (die in het portaal gaat bouwen: MFA-inschrijving, wachtwoord-wijzigscherm) moet het portaal een schone basis hebben: lint zonder fouten en **blokkerend** in CI, en een paar eenvoudige tests. Geen functionele wijzigingen aan het gedrag van het portaal.

## Stand waarvan we uitgaan (controleer, neem niet blind over)

- Frontend-HEAD zou `2c49622` moeten zijn (na Batch D). Backend-HEAD `df18d8e` of later.
- `npm run lint` = 5 errors (`no-explicit-any`: `WorkflowDashboard.tsx:10`, `HomePage.tsx:20`, `RunsPage.tsx:37` en `:41`, `services/results.ts:3`) en 11 `react-hooks/exhaustive-deps`-warnings.
- `ci.yml` draait lint met `continue-on-error: true`. Vitest staat er sinds Batch D (5 tests voor `src/lib/sentryScrub.ts`), `npm test` draait in CI.
- `src/components/MicrosoftConnect.tsx:51` bevat een placeholder-token (`'TEMP_TOKEN_REPLACE'`).

## Werkwijze (vaste afspraken)

1. Begin met `git status` en `git diff` in beide repo's (drift-check). Meld afwijkingen; los ze niet stilzwijgend op.
2. Kleine, losse commits per onderdeel (zie hieronder). Na elke push: CI én Deploy controleren via de GitHub Actions-API, en de headless deploy-check moet `DEPLOY CHECK OK` geven.
3. Geen nieuwe zware dependencies. Nieuwe devDependencies alleen als het echt nodig is, met exacte versie, en meld ze.

## Deel 1 — De 5 lint-errors (commit 1)

- Vervang elke `any` door een echt type. Kijk naar wat de backend teruggeeft (Pydantic-schema's in `ai-governance-os/app/` of de werkelijke response) en definieer interfaces (bijv. in `src/types/`), niet `unknown` met een cast om de lint stil te krijgen.
- **Geen gedragswijziging.** `npm run build` (`tsc -b`) moet blijven slagen, en de app moet er hetzelfde uitzien en werken.
- Twijfel je over de vorm van een response, kijk dan in de backendcode of, als dat niet volstaat, in een echte response met een testtoken van de demo-tenant (org 2). Geen wachtwoorden of tokens in de output of in git.

## Deel 2 — De 11 exhaustive-deps-warnings (commit 2)

- Analyseer elke warning apart. Waar een fix veilig is (bijv. `useCallback`, ontbrekende dependency toevoegen zonder oneindige lus of dubbele fetch), doe dat.
- Waar de fix het gedrag zou veranderen (extra fetches, lussen), laat de code zoals hij is en zet `// eslint-disable-next-line react-hooks/exhaustive-deps -- <korte reden>` erboven.
- Maak in je rapport een tabel: bestand:regel, wat je deed, waarom.

## Deel 3 — Lint blokkerend maken (commit 3)

- Verwijder `continue-on-error: true` van de lintstap in `.github/workflows/ci.yml` en werk de bijbehorende comment bij.
- Draai `npm run lint` met `--max-warnings=0`, alleen als er na deel 2 echt 0 warnings over zijn (ook de bewust uitgezette tellen dan niet mee). Anders: alleen errors blokkerend, en meld waarom.
- **Bewijs dat het blokkeert:** voeg lokaal tijdelijk een `any` toe, draai `npm run lint`, controleer dat het faalt, en draai die wijziging terug. Niet committen of pushen.

## Deel 4 — Basistests (commit 4)

- Zoek de pure logica in `src/` (bijv. hulpfuncties voor tokenafhandeling, API-basis-URL, formatters, `services/results.ts`) en schrijf maximaal ~10 kleine vitest-tests. Geen netwerk, geen echte tokens.
- Render-tests (React Testing Library) alleen als die al als dependency aanwezig is. Voeg geen jsdom/RTL toe zonder dat te melden en te motiveren.
- Vind je bijna niets pure-testbaars, meld dat dan eerlijk in plaats van nutteloze tests te schrijven.

## Deel 5 — Alleen kijken, niet aanpassen

- `MicrosoftConnect.tsx`: **niet wijzigen.** Meld alleen of het component vanuit een route of menu bereikbaar is in de gebouwde app, en of het placeholder-token ooit daadwerkelijk naar de backend gaat.
- Meld het verschil in release-naam tussen backend (`e71a77f`, 7 tekens) en portaal (volledige sha, 40 tekens) in Sentry. Niet aanpassen, alleen melden.

## Afronden

- README ("Known gaps") van het portaal bijwerken.
- CLAUDE.md in `ai-governance-os` bijwerken: sectie 5 (lint- en testrisico verkleind), sectie 6 (logregel, nieuwste bovenaan), sectie 7 (volgende stap: Batch E). Doe vooraf `git status`/`git diff` en verifieer na de commit dat de wijziging blijft staan.

## Stopvoorwaarden

Stop en meld als: een fix het gedrag van het portaal zou veranderen; een Deploy faalt (de pijplijn draait dan zelf terug, meld dat); je iets ontdekt dat niet klopt met dit document; je tokens, wachtwoorden of DSN's in de output of in git zou moeten zetten.

## Rapport

Geef: commits (hash + doel), CI/Deploy-run-id's met status, aantal lint-errors/warnings vóór en na, de tabel uit deel 2, het bewijs uit deel 3, de tests uit deel 4 (aantal en wat ze dekken), en de bevindingen uit deel 5.
