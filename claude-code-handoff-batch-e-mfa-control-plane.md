# Hand-off Batch E — Control plane beveiligen (MFA, super-admin, /ops, wachtwoord-wijzigen)

Auteur: Cowork (architect). Uitvoerder: Claude Code. Datum: 21 sep 2026.
Repo's: `ai-governance-os` (backend, eerst) en `ai-governance-frontend` (portaal, daarna).

## Doel

De basis leggen waarop het beheer van alle klanten (de "control plane" onder `/ops/*`) veilig kan draaien: tweede factor (TOTP), een super-admin-vlag die alleen met MFA werkt, een `/ops`-router die alleen door een super-admin met MFA te gebruiken is, dubbele audit-logging voor ops-acties, een wachtwoord-wijzigscherm en een noodprocedure tegen buitensluiting.

Ontwerpprincipes: (1) **niets breekt voor gebruikers zonder MFA** (login, tokens, bestaande tests blijven zoals ze zijn); (2) alleen additieve, nullable migraties; (3) geheimen (TOTP-geheimen, back-upcodes, codes, tokens) komen nooit in logs, in Sentry, in git of in je rapport; (4) nog **geen** super-admin aanwijzen: dat doet Dennis pas nadat hij zelf MFA heeft ingesteld (zie "Stop na de backend" en "Na de frontend").

## Vooraf besloten door Dennis/Cowork (niet opnieuw voorleggen)

- Tweede factor = TOTP-app (RFC 6238: 6 cijfers, 30 s, SHA-1, tolerantie ±1 stap). Geen SMS, geen e-mail-code.
- HQ = org 1 (`HQ_ORGANIZATION_ID=1`). Alleen gebruikers van HQ kunnen super-admin worden.
- MFA is **optioneel** voor gewone gebruikers (klanten) en **verplicht** voor super-admins en voor `/ops`.
- Voor de frontend zijn `jsdom` en Testing Library (`@testing-library/react`, `@testing-library/user-event`) toegestaan, alleen voor de nieuwe schermen in dit hand-off. Exacte versies, en meld ze. Het verplaatsen van de `ResultsPage`-helpers naar `src/lib/` is **niet** onderdeel van deze batch.
- Een QR-code in het portaal mag met één kleine, exacte-versie dependency (bijv. `qrcode.react`); toon daarnaast altijd het geheim als tekst voor handmatige invoer.

## Werkwijze (vaste afspraken)

1. Begin in beide repo's met `git status` en `git diff` (drift-check). Meld afwijkingen; los ze niet stilzwijgend op.
2. **Fase 0 (alleen lezen):** inventariseer de bestaande auth: hoe `POST /login` werkt en wat het teruggeeft, hoe tokens (JWT) worden gemaakt en gecontroleerd, welke dependency de huidige gebruiker levert, waar `is_super_admin` en `must_change_password`-achtige velden nu voorkomen, waar de cross-tenant-uitzonderingen voor super-admins zitten (`get_org_scoped_org`, `POST /organizations`, `POST /users` met `organization_id`), welke code of clients `/login` aanroepen (portaal, scripts, tests, CI), en hoe de audit-log-helper werkt (ketting per tenant, `performed_by`). Zet het resultaat in de eerste alinea van je rapport. Wijkt iets af van dit document, dan **stoppen en melden** vóór je bouwt.
3. Kleine losse commits (zie de onderdelen). Na elke push: CI én Deploy controleren via de GitHub Actions-API, plus een echte functionele check op productie.
4. Nieuwe backend-dependencies: alleen `pyotp` en (voor versleuteling van het geheim) `cryptography` als die er nog niet is, met exacte versies die op Python 3.9 én 3.12 installeren (`pip install --dry-run`). Meld ze.

## Deel 1 — Database (additief), backend-commit 1

Nieuwe kolommen op `users`, alle nullable of met veilige default, migratie draait vóór de restart via `deploy.sh`:

- `must_change_password` (bool, default false)
- `password_changed_at` (timestamp, nullable)
- `mfa_enabled` (bool, default false)
- `mfa_secret_enc` (text, nullable; het TOTP-geheim **versleuteld**, zie onder)
- `mfa_last_step` (integer, nullable; laatste geaccepteerde 30 s-stap tegen hergebruik/replay)
- `mfa_backup_codes` (JSON/text, nullable; lijst van **gehashte** eenmalige codes)
- `mfa_failed_attempts` (integer, default 0) en `mfa_locked_until` (timestamp, nullable)

Versleuteling van het geheim: Fernet met een aparte sleutel `MFA_ENCRYPTION_KEY` (niet `SECRET_KEY`). Genereer de sleutel op de server en zet hem in de productie-`.env` via stdin (zoals bij de Sentry-DSN: back-up van `.env`, modus 600 `www-data`, back-up daarna verwijderen, nooit printen). Staat de sleutel niet in de omgeving, dan weigert MFA-inschrijving met een duidelijke fout; de rest van de app blijft werken. `.env.example`: `MFA_ENCRYPTION_KEY=` zonder waarde. Documenteer in CLAUDE.md dat het kwijtraken van deze sleutel alle MFA-geheimen onbruikbaar maakt, en dat de noodprocedure (Deel 5) dan nodig is.

## Deel 2 — MFA-backend, backend-commit 2

Endpoints (namen mogen afwijken als de bestaande conventie dat vraagt; meld het):

- `POST /auth/mfa/setup` (ingelogd): maakt een nieuw geheim, slaat het versleuteld op met `mfa_enabled=false`, geeft `otpauth://`-URI en het geheim in tekst terug. Kan opnieuw worden aangeroepen zolang MFA nog niet bevestigd is.
- `POST /auth/mfa/enable` (ingelogd, met een geldige code): zet `mfa_enabled=true`, maakt **10 back-upcodes** (willekeurig, voldoende lang, elk eenmalig), slaat alleen hashes op (zelfde hasher als wachtwoorden) en geeft de codes **één keer** terug. Audit-regel.
- `POST /auth/mfa/disable` (ingelogd; wachtwoord + huidige code): niet toegestaan voor een super-admin. Audit-regel.
- Loginflow: bestaat er voor de gebruiker `mfa_enabled=true`, dan geeft `POST /login` bij een juist wachtwoord **geen** toegangstoken maar `{"mfa_required": true, "mfa_token": "<kortlevend token, 5 min, alleen geldig voor de MFA-stap>"}`. Daarna `POST /login/mfa` met `mfa_token` en `code` (TOTP of een back-upcode) → het gewone toegangstoken, met een claim `mfa: true`. Voor gebruikers zonder MFA blijft `POST /login` **exact** zoals nu (zelfde velden, zelfde token; bestaande tests blijven ongewijzigd groen).
- Beveiliging: dezelfde TOTP-stap mag maar één keer geaccepteerd worden (`mfa_last_step`); 5 opeenvolgende foute codes → 15 minuten blokkade (`mfa_locked_until`), teller reset na een geslaagde login; een back-upcode werkt één keer; timing-veilige vergelijking; overal generieke foutmeldingen (geen verschil tussen "fout wachtwoord" en "MFA vereist" voor niet-bestaande gebruikers).
- Audit-regels (bestaande ketting, `performed_by` = de gebruiker of `system`): inschrijving gestart/bevestigd, mislukte MFA-poging, blokkade, gebruik van een back-upcode, MFA uitgezet, MFA-reset. **Nooit** een code of geheim in de auditregel.

## Deel 3 — Wachtwoord wijzigen, backend-commit 3

- `POST /auth/change-password` (ingelogd): huidig wachtwoord + nieuw wachtwoord (minimaal 12 tekens, niet gelijk aan het huidige). Zet `must_change_password=false` en `password_changed_at`. Audit-regel.
- Is `must_change_password=true`, dan geeft `POST /login` (en `/login/mfa`) dat door in de response (`must_change_password: true`), en weigert de gedeelde auth-dependency alle endpoints behalve `change-password`, `me`/profiel en de MFA-endpoints met `403 {"error":"password_change_required"}`. Bouw dit in de bestaande dependency, niet per route; test dat het geen andere endpoints raakt voor gebruikers met de vlag uit.

## Deel 4 — Super-admin en /ops, backend-commit 4

- `is_super_admin` wordt **alleen** gezet door een eenmalig, idempotent script `scripts/grant_super_admin.py --username X` (met `--dry-run` en `--revoke`): weigert tenzij de gebruiker in de HQ-organisatie zit, `mfa_enabled=true` heeft en actief is; schrijft een auditregel (`performed_by="system"`). Er komt **geen** API-endpoint om `is_super_admin` te zetten of de vlag via een bestaand endpoint (bijv. `POST /users`) mee te geven; controleer dat dat nu ook echt niet kan en meld het.
- Nieuwe dependency `require_ops_access`: eist `is_super_admin`, gebruiker in HQ (`get_hq_organization_id()`), én token-claim `mfa: true`. Gewone admin of super-admin zonder MFA-claim → `403`. Pas dezelfde MFA-eis toe op de **bestaande** cross-tenant-uitzonderingen voor super-admins (`get_org_scoped_org`, `POST /organizations`, `POST /users` met `organization_id`), zodat een super-admin zonder MFA-claim daar ook niet bij kan.
- Nieuwe router `app/api/ops.py` met prefix `/ops` (bewust minimaal in deze batch): `GET /ops/whoami` (alleen wie ben ik, org, `is_super_admin`, `mfa`), verder niets. De echte ops-endpoints komen in Batch F.
- Dubbele audit-logging: een helper `log_ops_action(actor, action, target_org_id=None, details=...)` schrijft één regel in de ketting van tenant 0 (HQ) en, als er een doel-tenant is, één regel in de ketting van die tenant. Gebruik hem in `/ops/whoami` (target leeg) en test hem met een doel-tenant (org 2). `GET /audit/verify` moet `valid` blijven voor beide ketens.
- Tests (in de bestaande stijl, geen netwerk): TOTP-tolerantie en replay, blokkade na 5 fouten en reset, back-upcode eenmalig, tweestaps-login, ongewijzigd gedrag zonder MFA, `must_change_password`-poort, `/ops/whoami` 403 voor gewone admin en voor super-admin zonder `mfa`-claim, 200 met beide, dubbele auditregels en `valid` na afloop, script weigert zonder MFA/buiten HQ, en dat een MFA-code of geheim **niet** in een geserialiseerd Sentry-event of logregel terechtkomt (gebruik de bestaande in-memory-Sentry-testopzet). Verwacht: de bestaande 157 tests blijven groen plus nieuwe.

## Deel 5 — Noodprocedure tegen buitensluiting, backend-commit 5

- `scripts/mfa_reset.py --username X` (met `--dry-run`, draait op de server via SSH): wist alle MFA-velden van die gebruiker, zet `mfa_enabled=false`, reset de blokkade, schrijft een auditregel (`performed_by="system:mfa_reset"`). Als de gebruiker super-admin was, wordt de vlag **niet** gewist, maar hij kan pas weer in `/ops` na een nieuwe MFA-inschrijving (de claim ontbreekt zolang hij geen MFA heeft).
- Documenteer in CLAUDE.md, sectie 6, de exacte SSH-procedure voor Dennis (in gewoon Nederlands, met het commando) inclusief wat te doen als `MFA_ENCRYPTION_KEY` kwijt is.
- **Test de procedure op productie met wegwerpaccounts**, zonder Dennis' account aan te raken: maak in org 2 een gebruiker `mfa_test_user` (script, geen wachtwoord in de output), schrijf MFA in met de API en `pyotp` op de server, controleer de tweestaps-login, blokkeer hem met 5 foute codes, reset hem met het script en controleer dat een gewone login weer werkt. Zet hem daarna op `is_active=False` (niet verwijderen). Voor `/ops`: maak een wegwerp-gebruiker in HQ, schrijf MFA in, geef hem tijdelijk super-admin met het script, controleer `/ops/whoami` (200, met dubbele auditregel) en dat een gewone admin `403` krijgt, en trek de vlag daarna in (`--revoke`) en deactiveer de gebruiker. Alle wachtwoorden en tokens blijven buiten de output.

## STOP na de backend

Als Deel 1 t/m 5 op productie staan met groene CI en Deploy: **stop, rapporteer en wacht** op mijn melding voor de frontend. Dan pas Deel 6.

## Deel 6 — Portaal (frontend-repo), na akkoord van Dennis

- **Login in twee stappen:** na wachtwoord bij `mfa_required` een tweede scherm voor de 6-cijfercode (met "back-upcode gebruiken"), foutmeldingen zonder details, en de blokkade duidelijk. Bij `must_change_password` direct naar het wachtwoord-wijzigscherm.
- **Account-pagina:** sectie "Tweestapsverificatie": status, "Inschakelen" (QR + geheim in tekst + code invoeren + eenmalig tonen van de 10 back-upcodes met kopiëren/downloaden en een bevestiging "ik heb ze bewaard" vóór doorgaan), "Uitschakelen" (wachtwoord + code; niet voor een super-admin: dan uitleg).
- **Wachtwoord-wijzigscherm** volgens Deel 3.
- Sla de back-upcodes en het geheim **nooit** op in `localStorage` of elders; alleen in component-state, en niets ervan naar Sentry (controleer dat de bestaande `sentryScrub` er niets van doorlaat).
- Tests met jsdom en Testing Library voor de drie nieuwe schermen (gemockte `fetch`): login met MFA-stap, MFA-inschrijving toont codes één keer, wachtwoord-wijzigen valideert lengte. Lint blijft `--max-warnings=0`, `npm test` groen, deploy-check `DEPLOY CHECK OK`, en laad daarna alle tabs op productie met een server-side gemunt token zoals bij D2 (zonder tokens te printen).
- Werk README (Known gaps) en CLAUDE.md (§2, §5, §6, §7) bij; sectie 7: volgende stap = Dennis schrijft zichzelf in en krijgt super-admin, daarna Batch F.

## Na de frontend (niet doen zonder mijn melding)

Dennis schrijft zichzelf in via het portaal met zijn authenticator-app (bewaart de back-upcodes offline). Daarna, en alleen op zijn uitdrukkelijke melding, draai je `grant_super_admin.py --username dennis_admin` (eerst `--dry-run`), controleer je `/ops/whoami` met zijn account niet zelf (je hebt zijn code niet) maar via de wegwerp-test uit Deel 5, en rapporteer je.

## Stopvoorwaarden

Stop en meld als: de bestaande auth niet overeenkomt met dit document; een wijziging het gedrag voor gebruikers zonder MFA zou veranderen; bestaande tests rood worden; een migratie niet additief kan; een Deploy faalt (de pijplijn draait dan zelf terug, meld dat); je geheimen, codes, tokens of wachtwoorden in output, logs, Sentry of git zou moeten zetten; de wegwerp-tests op productie iets anders zouden raken dan de aangemaakte testaccounts.

## Rapport

Geef: Fase 0-bevindingen en afwijkingen; commits (hash + doel), CI/Deploy-run-id's; migratie-uitvoer (alleen namen en aantallen); nieuwe dependencies met versies; testaantallen vóór en na; resultaten van de productiechecks uit Deel 5 (per stap: verwacht, gezien, met echte uitvoer); de exacte SSH-noodprocedure in Nederlands; en een lijst van beslissingen die je zelf hebt moeten nemen. Na de frontend een tweede rapport met dezelfde structuur.
