# Hand-off Batch G — Supportverzoek-slice (portaal → tenant 0 → e-mailmelding)

Auteur: Cowork (architect). Uitvoerder: Claude Code. Datum: 21 sep 2026.
Repo's: `ai-governance-os` (backend, eerst) en `ai-governance-frontend` (portaal, daarna).

## Doel

Bevinding B1 sluiten: het aanvraagformulier op de Account-tab ("Getting help") verstuurt nu niets. Na deze batch komt een supportverzoek van een klant als record binnen bij Valqeron (HQ, tenant 0), wordt Dennis per e-mail gewaarschuwd, en ziet de klant een referentienummer.

Taak-ID: 1.1 uit het plan. Alleen wat hieronder staat; geen ticketsysteem, geen chat, geen klantzichtbare voortgang (dat is Fase 2).

## Vooraf besloten door Dennis/Cowork (niet opnieuw voorleggen)

- **E-mail via Resend** (EU-regio waar mogelijk). Sleutel en adressen komen **later** van Dennis. Bouw daarom alles zo dat het **zonder sleutel werkt**: het verzoek wordt dan wel opgeslagen (`201` naar de klant), de mail wordt overgeslagen en `notify_status="skipped_no_config"` gezet. Een mislukte of ontbrekende mail laat het verzoek **nooit** falen.
- Omgevingsvariabelen (allemaal leeg in `.env.example`): `RESEND_API_KEY`, `SUPPORT_FROM_EMAIL`, `SUPPORT_NOTIFY_EMAIL`. `deploy.sh` mag ze **niet** verplicht stellen.
- De e-mail bevat organisatienaam, gebruikersnaam van de indiener, categorie, onderwerp, referentie en de **tekst van het verzoek** (de klant schrijft die zelf voor Valqeron). Geen wachtwoorden, tokens of andere data. In het formulier komt een korte waarschuwing dat de klant geen persoonsgegevens van derden hoeft in te vullen.
- Geen wijzigingen aan auth, MFA of het provisioning-gedrag. Er komt geen ops-scherm.

## Werkwijze (vaste afspraken)

1. Begin in beide repo's met `git status` en `git diff` (drift-check). Verwacht backend `2932463` of nieuwer en portaal `28ea9e4` of nieuwer. Meld afwijkingen.
2. **Fase 0 (alleen lezen), resultaat in de eerste alinea van je rapport:** hoe het huidige formulier op de Account-tab werkt en wat het aanroept; of er al een `ContactSubmission`- of vergelijkbaar model is (dat hoort bij een andere flow, Sales Qualification, en **niet** aangepast wordt); hoe tenant-scoped endpoints de organisatie van de gebruiker bepalen (`get_current_user`, `get_org_scoped_org`); waar de bestaande limieten staan (`/login` heeft een IP-limiet) en wat er beschikbaar is voor een per-gebruiker-limiet; hoe `create_audit_log` en `log_ops_action` werken. Wijkt iets af van dit document, dan **stoppen en melden**.
3. Kleine losse commits; na elke push CI én Deploy controleren via de GitHub Actions-API, plus een echte functionele check op productie.
4. Alleen additieve migraties. Geen nieuwe zware dependencies: gebruik `httpx` (of wat er al is) voor de Resend-API in plaats van een SDK, tenzij de SDK klein en exact te pinnen is; meld je keuze.

## Deel 1 — Backend (commits 1 t/m 3)

**Tabel `support_requests`** (additief; tabel is globaal, want HQ leest hem, maar elke rij hoort bij de bron-organisatie): `id`, `reference` (leesbaar en uniek, bijv. `SR-000123`), `organization_id`, `user_id`, `category` (bijv. `question`, `problem`, `access`, `other`), `subject`, `message`, `status` (`new` | `in_progress` | `done`, standaard `new`), `created_at`, `updated_at`, `notified_at` (nullable), `notify_status` (`pending` | `sent` | `failed` | `skipped_no_config`), `notify_error` (korte tekst zonder geheimen, nullable).

**Endpoints:**
- `POST /support-requests` (ingelogde gebruiker van elke organisatie): valideert lengte (onderwerp ≤ 200, bericht ≤ 5000 tekens, categorie uit de lijst), slaat het verzoek op voor de **eigen** organisatie en gebruiker (nooit een `organization_id` uit de body accepteren), schrijft een auditregel in de keten van de eigen organisatie (`support_request_created`, **zonder** berichttekst), stuurt daarna de mail en geeft `201 {reference, status, created_at}`. Per gebruiker maximaal 5 verzoeken per uur en 20 per dag (`429` met duidelijke tekst).
- `GET /support-requests` (tenant-scoped): alleen de eigen organisatie, nieuwste eerst, zonder interne velden (`notify_*`).
- `GET /ops/support-requests` en `PATCH /ops/support-requests/{id}` (alleen `require_ops_access`, statuswijziging via `log_ops_action` in de HQ-keten én in die van de bron-organisatie): alle verzoeken met filter op status, en de status wijzigen. Geen andere velden aanpasbaar.

**E-mail via Resend:** één functie, verzendt met een korte time-out (bijv. 10 s), nooit in de transactie van het verzoek (na de commit), vangt alle fouten af, zet `notify_status`/`notified_at` en logt alleen een generieke regel (geen sleutel, geen berichttekst, geen ontvangeradres). Onderwerp van de mail: `[Valqeron support] <reference> <organisatienaam>`. `Reply-To` is **niet** het adres van een klant (er is geen e-mailkolom op `users`). Zet tekst en HTML-versie op, met escape van alle klantinvoer (geen HTML-injectie).

**Herstelscript:** `scripts/resend_support_notifications.py` (`--dry-run`) verstuurt de mail opnieuw voor rijen met `notify_status` `failed` of `skipped_no_config`, zodat verzoeken die binnenkwamen vóór de sleutel er was, achteraf alsnog een melding krijgen.

**Sentry en logs:** berichttekst, onderwerp en de Resend-sleutel komen niet in logregels, auditdetails of een geserialiseerd Sentry-event (test met de bestaande in-memory-testopzet).

**Tests** (zonder netwerk; Resend gemockt): opslaan met juiste organisatie en gebruiker, `organization_id` in de body wordt genegeerd, validatiegrenzen, limieten, isolatie (tenant A ziet nooit verzoeken van tenant B), ops-endpoints `403` voor gewone admin en voor super-admin zonder MFA-claim, `200` met beide, statuswijziging met dubbele auditregels en `/audit/verify` `valid`, mail overgeslagen zonder configuratie (`201` en `skipped_no_config`), mailfout en time-out maken het verzoek niet mislukt, HTML-escape, en dat berichttekst niet in auditregel, logregel of Sentry-event staat. Bestaande 259 tests blijven groen.

## STOP na de backend

Als Deel 1 op productie staat met groene CI en Deploy en de productiecheck (Deel 2) gedaan is: **stop, rapporteer en wacht** op mijn melding voor Deel 3. Ik stuur dan ook de Resend-gegevens.

## Deel 2 — Productiecheck backend

Met een tijdelijk server-side gemunt token (niet geprint, niet gecommit, niets laten liggen) voor de bestaande testtenant "ZZ Provisioning Test" of voor `customer2_admin` in org 2:
1. `POST /support-requests` → `201` met referentie; het record staat er met de juiste organisatie; `notify_status=skipped_no_config`.
2. `GET /support-requests` toont alleen het eigen verzoek; een token van een andere organisatie ziet het niet.
3. Als `dennis_admin` (gemunt token, met MFA-claim): `GET /ops/support-requests` toont het verzoek; `PATCH` naar `in_progress` werkt; er staat een auditregel in de HQ-keten én in die van de bron-organisatie; `/audit/verify` is `valid` voor HQ en die organisatie.
4. Zet het testverzoek na afloop op `done`. **Niets verwijderen.**

## Deel 3 — Portaal (na mijn akkoord)

- Sluit het formulier op de Account-tab aan op `POST /support-requests`: categorie, onderwerp, bericht, de korte privacywaarschuwing, laadstatus, en na succes een bevestiging met het referentienummer. Duidelijke meldingen bij `400`/`422`, `429` (te veel verzoeken) en netwerkfouten; het bericht blijft in het formulier staan als het versturen mislukt.
- Een simpele lijst "Mijn verzoeken" op dezelfde tab uit `GET /support-requests` (referentie, onderwerp, status, datum). Geen chat, geen antwoorden.
- Zorg dat de tekst van een verzoek nergens in `localStorage` of in een Sentry-event terechtkomt (controleer `sentryScrub`).
- Tests met Testing Library (gemockte `fetch`): succes toont het referentienummer, validatie, `429`, netwerkfout behoudt de tekst, lijst rendert. Lint blijft `--max-warnings=0`, `npm test` groen, `DEPLOY CHECK OK`, alle tabs laden op productie met een server-side gemunt token (niet geprint).
- Werk README (Known gaps) en CLAUDE.md (§2, §5, §6, §7) bij; noteer dat B1 gesloten is en dat de e-mailmelding pas werkt na activering (Deel 4).

## Deel 4 — Activering van Resend (alleen op mijn melding, niet eerder)

Dennis levert de sleutel en de adressen. Dan: zet `RESEND_API_KEY`, `SUPPORT_FROM_EMAIL` en `SUPPORT_NOTIFY_EMAIL` in de productie-`.env` via stdin (back-up van `.env`, modus 600 `www-data`, back-up daarna verwijderen, nooit printen, niet in git), herstart met de handmatige procedure als dat nodig is, draai `scripts/resend_support_notifications.py --dry-run` en daarna echt, en stuur **één** testmelding. Dennis bevestigt dat de mail is aangekomen. Geen extra testmails.

## Stopvoorwaarden

Stop en meld als: het bestaande formulier of datamodel afwijkt van dit document; een wijziging auth, MFA of bestaande organisaties raakt; tests rood worden; een migratie niet additief kan; een Deploy faalt (de pijplijn draait dan zelf terug, meld dat); je sleutels, tokens of berichttekst in output, logs, Sentry of git zou moeten zetten; je iets zou moeten versturen naar een echt extern adres voordat Dennis akkoord gaf.

## Rapport

Geef: Fase 0-bevindingen en afwijkingen; commits (hash + doel), CI/Deploy-run-id's; migratie (alleen namen en aantallen); nieuwe endpoints en scripts; testaantallen vóór en na; de productiechecks per stap (verwacht, gezien, echte uitvoer zonder geheimen); en beslissingen die je zelf hebt genomen. Na Deel 3 en Deel 4 elk een korte aanvulling.
