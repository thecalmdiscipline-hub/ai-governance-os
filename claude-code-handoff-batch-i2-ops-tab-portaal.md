# Hand-off Batch I2 — Fase 2.3: ops-tab in het portaal (accounts, onboarding, provisioning-wizard)

Auteur: Cowork (architect). Uitvoerder: Claude Code, **één sessie**. Datum: 6 okt 2026.
Repo: `ai-governance-frontend` (portaal). De backend uit Batch I (`/ops/accounts`, `/ops/onboarding/*`, migratie `410fa8b741b8`) staat op productie; backend-wijzigingen zijn **niet** de bedoeling (zie stopvoorwaarden).

## Doel

Een super-admin met MFA (alleen `dennis_admin`) krijgt in het bestaande portaal een tab **Ops** waarmee Valqeron zelf in tenant 0 werkt: accounts bekijken en aanmaken, de status van een account verzetten, een bestaande organisatie koppelen, een onboardingproject starten en de taken per fase bijwerken, de doorlooptijd zien, en (Deel 2) een nieuwe klant provisionen vanuit een wizard. Taak-ID 2.3 uit `claude/executieplan-fase-0-1.md`.

## Vooraf besloten (niet opnieuw voorleggen)

- **De server is de grens, niet de UI.** De Ops-tab is alleen zichtbaar als `GET /ops/whoami` slaagt (super-admin, HQ-organisatie, MFA-claim). Een gewone admin of klant ziet niets en kan niets zonder `403` van de backend. Verberg de tab bij elke andere uitkomst, ook bij netwerkfouten.
- **Ops-code in een apart, lazy geladen deel** (`src/ops/`, dynamische `import()`), zodat klanten deze code nooit downloaden. Dit is geen beveiliging, wel minder oppervlak en een bundel die klanten niet vertraagt.
- Hergebruik het bestaande ontwerp (donker paneel, gouden accent, serif-koppen) en de bestaande tabstructuur; er komt geen router.
- Geen nieuwe zware dependencies.
- **Alle klantgegevens blijven uit `localStorage`, logs, `console` en Sentry-events.** Dat geldt voor contactnaam, contact-e-mail, notities, en het eenmalige wachtwoord uit de wizard. Controleer `sentryScrub` en voeg waar nodig scrub-regels en tests toe.
- Geen backend-wijzigingen. Ontbreekt er iets in de API (bijvoorbeeld een veld dat het scherm nodig heeft), stop dan en meld het in plaats van de backend aan te passen.
- Er komt **geen** gezondheidsweergave per tenant (health-checks); toon alleen wat de bestaande `/ops/tenants*`-endpoints teruggeven.

## Werkwijze

1. In `ai-governance-frontend`: `git status` en `git diff` (drift-check). Meld afwijkingen.
2. **Fase 0 (alleen lezen), resultaat in de eerste alinea van je rapport:** hoe tabs, auth en de API-client nu werken (hoe het token wordt meegestuurd, hoe `mfa_required` en `must_change_password` in het portaal zijn opgelost, wat `GET /auth/me` teruggeeft); de exacte vorm van de responses van `/ops/whoami`, `/ops/tenants`, `/ops/accounts`, `/ops/onboarding/*` en `POST /ops/tenants/provision` (lees de backendrouters in `ai-governance-os`, alleen lezen); hoe `sentryScrub` werkt. Wijkt iets af van dit document: stoppen en melden.
3. Kleine losse commits; na elke push CI en Deploy controleren (GitHub Actions-API, `DEPLOY CHECK OK`), plus een echte functionele check op productie. Lint blijft `--max-warnings=0`, `npm test` groen.

## Deel 1 — Accounts en onboarding (commits 1 t/m 3)

**Tab "Ops"** met drie weergaven (eenvoudige tabs of een zijpaneel, geen router):

1. **Accounts:** lijst (naam, land, status, voorgestelde tier, gekoppelde organisatie ja/nee), filter op status, zoeken op naam, formulier "Nieuw account" (naam verplicht ≤200, land ≤2, sector ≤120, bron, voorgestelde tier, optioneel contactnaam en contact-e-mail met e-mailvalidatie, notitie ≤1000 met de waarschuwing "geen klantinhoud, geen wachtwoorden"). Bij het opslaan tonen: laadstatus, bij `400/422` de veldfouten, bij `409` een duidelijke tekst, bij netwerkfout blijft het ingevulde formulier staan.
2. **Account-detail:** de velden, de statusknoppen (alleen de toegestane vervolgstatus(sen) tonen volgens de backendregels; `lost` en `churned` achter een bevestiging), "Organisatie koppelen" (keuzelijst uit `GET /ops/tenants`, toont alleen organisaties zonder koppeling), en "Start onboarding" (alleen als er geen actief project is).
3. **Onboardingproject:** taken per fase (1 t/m 8), per taak status (`todo`/`doing`/`done`/`skipped`/`blocked`) en een notitie ≤500; wie de eigenaar is (Valqeron/klant/beide) en of de taak klantzichtbaar is, alleen lezen; voortgangsbalk per fase; paneel **Doorlooptijd** uit `/metrics` (per fase, kickoff-naar-go-live, totaal; "nog niet bekend" waar de backend `null` geeft). Optimistische updates mogen alleen als ze bij een fout netjes terugdraaien.

**Gedrag en veiligheid:** een `401` of `403` uit een ops-aanroep logt de gebruiker niet uit en toont geen details; de Ops-tab verdwijnt als `/ops/whoami` daarna faalt. Geen onderdelen die organisaties of gebruikers verwijderen. Geen weergave van contactgegevens in foutmeldingen.

**Tests** (Testing Library, gemockte `fetch`): tab onzichtbaar voor een gewone admin en bij fout op `/ops/whoami`; zichtbaar voor ops; accountlijst en filter; nieuw account (succes, validatie, `409`, netwerkfout behoudt tekst); statusknoppen volgen de toegestane overgangen; organisatie koppelen (alleen vrije organisaties); onboarding starten (en niet als er al een actief project is); taakstatus wisselen en terugdraaien bij fout; metrics met en zonder `null`; **contactnaam, e-mail en notitie komen niet in `localStorage`, `console` of een Sentry-event** (test met de bestaande scrub-opzet); de ops-bundel wordt niet geladen zonder ops-rechten.

## STOP na Deel 1

Na groene CI en Deploy, `DEPLOY CHECK OK` en de productiecheck hieronder: **stop, rapporteer en wacht** op mijn melding voor Deel 2.

**Productiecheck Deel 1 (alleen lezen, server-side gemunt token voor `dennis_admin` met MFA-claim, alleen in geheugen, niet geprint, niets achtergelaten):** headless browser; laad de Ops-tab; de accountlijst bevat **ISO CERT INTERNATIONAL LTD** met een gekoppelde organisatie; het onboardingproject toont 28 taken waarvan er 2 `done` zijn en fase 1 niet compleet; het paneel Doorlooptijd rendert. Met een klant-token (bijvoorbeeld `customer2_admin`) is de Ops-tab **niet** zichtbaar en geeft de API `403`. **Schrijf niets op productie** in deze check (geen nieuwe accounts, geen taakwijzigingen). Maak geen screenshot die contactgegevens toont; er zijn er nu geen, maar controleer het.

## Deel 2 — Provisioning-wizard (na mijn akkoord)

Wizard vanuit een account (status `contract` of `onboarding`): stappen **Gegevens** (vooringevuld uit het account: naam, land, sector, voorgestelde tier), **Modules** (keuze uit de modules van het tier, met de tierregels uit het backend-antwoord: Starter ≥2 workflows; Business ≥5 incl. `compliance_monitor`; Enterprise ≥7 incl. `compliance_monitor`; `core` altijd), **Beheerder** (gebruikersnaam), **Controle en bevestigen** (samenvatting). Daarna `POST /ops/tenants/provision`.

- Toon eerst een **dry-run** als de backend dat ondersteunt (anders de samenvatting) en vraag een expliciete bevestiging.
- **Het eenmalige wachtwoord** komt alleen in React-state, wordt **eenmaal** getoond met een knop "Kopiëren" en de tekst dat het via een apart, veilig kanaal aan de klant moet worden gegeven, verdwijnt bij sluiten van het scherm, bij navigatie en na 5 minuten, en komt **nooit** in `localStorage`, `sessionStorage`, `console`, URL, een Sentry-event of testsnapshot. Test dit expliciet (inclusief `sentryScrub`).
- Na succes: koppel het account automatisch aan de nieuwe organisatie (`POST /ops/accounts/{id}/link-organization`), zet de accountstatus op `onboarding` als dat de volgende toegestane stap is, en bied aan om de onboardingtaak "Organisatie, beheerder en modules aanmaken via provisioning" op `done` te zetten (alleen na klik, niet stil).
- Idempotentie en fouten: een tweede klik mag geen tweede aanroep doen (knop uitschakelen tijdens het verzoek); `409` van de provisioning (bestaat al) toont een duidelijke tekst en koppelt **niet** automatisch.
- **Productiecheck Deel 2: alleen de wizard tot en met de samenvatting, zonder echt te provisionen.** Geen nieuwe organisatie op productie in deze check. De echte provisioning voor een klant doet Dennis later zelf.

## Stopvoorwaarden

Stop en meld als: de backend iets moet missen of veranderen; een wijziging auth, MFA of de bestaande klantportaal-tabs zou raken; klantgegevens of het wachtwoord in `localStorage`, een log of Sentry-event zouden komen; de bundel van klanten de ops-code zou bevatten; tests rood worden; een Deploy faalt (de pijplijn draait zelf terug, meld het); de classifier iets blokkeert (niet omzeilen, melden).

## Rapport

Fase 0-bevindingen en afwijkingen; commits (hash en doel), CI- en Deploy-run-id's, `DEPLOY CHECK OK`; nieuwe schermen en bestanden; testaantallen vóór en na; productiecheck per stap (verwacht, gezien, geen geheimen of persoonsgegevens); beslissingen die je zelf hebt genomen; README en CLAUDE.md (§2, §5, §6, §7) bijgewerkt met commit-hash.
