# Beslissingenlog: Valqeron platform

Eén plek voor alle besluiten van Dennis. Elke beslissing staat hier één keer, met datum. Wijzigen kan; dan wordt de oude regel doorgehaald en de nieuwe toegevoegd. Bij twijfel geldt de nieuwste regel.

Laatste update: 25 nov 2026.

## A. Documenten en scope (23 en 24 nov 2026)

- **Scope-code** staat in de bestandsnaam (`[scope=...]`) én op de eerste regel van de inhoud (`scope: ...`). Beide moeten gelijk zijn. (23 nov)
- **Geen code = geen gebruik**: zonder code wordt een document door geen workflow gelezen, en upload wordt geweigerd. (23 nov)
- **Codes zijn vast** na upload. (23 nov)
- **Koppeling automatisch op documenttype** als voorstel; de uploader bevestigt. Zonder bevestiging: geweigerd. (24 nov)
- **Een document kan meerdere codes hebben**, minimaal één. (23 nov)
- **`gedeeld`** is een aparte code. (23 nov)
- **`hr` is exclusief**: nooit combineren met een andere code. Bij een botsing in het voorstel wint `hr`. (23 nov, 24 nov)
- **Uploaden**: admin en operator. (23 nov)
- **Verwijderen**: admin en operator. (24 nov)
- **Snippets** worden niet getoond; elke uitvoer toont `sources`. (23 nov)
- **Limiet**: 5 documenten en 6000 tekens per run. (23 nov)
- **Auditlog**: per run welke documenten zijn gelezen. (23 nov)
- **Archiveren**: alle bestaande documenten worden `archived`. Niets wordt verwijderd. Vanaf dan lezen workflows alleen nieuwe, gecodeerde documenten. Geen overgangsregel voor demo-organisaties. (23 nov)
- **Geen lijst** van documenten vooraf voor klanten 1 en 2. (24 nov)
- **Terugzetten** van archief: alleen Valqeron-beheerders, per document, met MFA. (23 nov, 24 nov)
- **PDF zonder tekstlaag**: wordt geweigerd bij upload. Acceptabel voor nu. (24 nov)
- **Nieuwe versie** met dezelfde naam: de vorige gecodeerde versie wordt gearchiveerd. (acht keuzes, 24 nov)
- **Terugzetten naast een actieve versie**: geblokkeerd (409). (24 nov)
- **Terugzetten met andere codes** dan de bestaande: 409. Een document zonder codes krijgt de codes uit de aanvraag. (24 nov)
- **Super-admin met MFA** mag ook uploaden. (24 nov)

## B. Codes (23 en 24 nov 2026)

- **Codelijst** wordt alleen door Valqeron beheerd. (24 nov)
- **Workflow-codes** bevestigd: `kennis`, `support`, `sales`, `contract`, `meeting`, `marketing`, `factuur`, `compliance`, `hr`, `bi`.
- **Documentcodes**: `gedeeld`, `kennis`, `support`, `sales`, `contract`, `meeting`, `marketing`, `factuur`, `compliance`, `hr`, `bi`. (zie `docs/scope-codes.md`)

## C. Rechten en downloads (23 tot 25 nov 2026)

- **Valqeron-beheerder**: Dennis, Rayvanno, of een door Valqeron aangewezen persoon. Rechten komen van Valqeron. (24 nov)
- **Niet-gecodeerde documenten (`uncoded`) downloaden**: altijd alleen Valqeron. De vlag `archive_download_enabled` heeft hier geen invloed. (25 nov)
- **Gearchiveerde documenten (`archived`) downloaden**: alleen Valqeron, tenzij de vlag `archive_download_enabled` per klant aan staat. (24 nov, 25 nov)
- **Vlag `archive_download_enabled`**: standaard uit. Alleen Valqeron zet de vlag. (24 nov)
- **Klant-admin** mag bij aangezette vlag zijn eigen archief downloaden; auditor niet. (24 nov)
- **Elke download of preview** van archief of niet-gecodeerd document door Valqeron wordt gelogd bij HQ en bij de klant. (25 nov, voorstel geaccepteerd)
- **Valqeron ziet via die route alleen oude documenten**, geen actieve. Nieuw besluit nodig als support dat later nodig heeft. (25 nov)

## D. Workflows en bedrijven (23 en 24 nov 2026)

- **Workflow voor een bedrijf** is een eigen instantie, met eigen naam en eigen instellingen. (23 nov)
- **Alles instelbaar** per bedrijf: toon, taal, documentset, velden, drempels, prompts, model en integraties. (24 nov)
- **Model** per bedrijf kiesbaar. (23 nov)
- **Uitzetten** van een instantie: runs blijven bewaard. (23 nov)
- **Tiers** blijven zoals ze zijn. (23 nov)
- **Inrichting** van nieuwe bedrijven: nu oppakken, volledig automatisch. (24 nov)
- **Runs zonder AI-systeem** blijven historisch. Nieuwe runs zijn verplicht gekoppeld aan een AI-systeem. (24 nov)
- **Een workflow-instantie** is een AI-systeem. (23 nov)

## E. Integraties (23 en 24 nov 2026)

- **Providers**: Microsoft 365 en Google tegelijk. (24 nov)
- **Mailbox**: eigen mailbox van de klant én een adres van Valqeron per bedrijf, per bedrijf instelbaar. (24 nov)
- **Uitgaande mail en afspraken** gaan alleen na goedkeuring, tenzij de instelling anders zegt. (23 nov)
- **Job-mechanisme**: nog te beslissen (voorstel systemd-timer, geen Celery). Open.
- **OAuth-apps** bij Microsoft en Google: aan te maken door Dennis. Open.
- **`CONNECTION_ENCRYPTION_KEY`** op de server: door Dennis te zetten, apart van MFA. Open.

## F. Werkwijze (25 nov 2026)

- **Merge naar `main` en productie-uitrol** doet Dennis zelf. Claude Code merget niet en deployt niet.
- **Push** naar de feature-branch mag Claude Code, met akkoord van Dennis per keer.
- **Productie-migratie** van het archiveren wacht op een werkende off-site back-up.
- **Volgorde van commits**: de archiefmigratie blijft de laatste commit, zodat de downloadregel zonder archiveren uitgerold kan worden (zie `docs/archief-uitrol-aparte-batch.md`).
- **Opdrachten** voor Claude Code worden in de repo gezet (`docs/bouwopdracht-*.md`) en verwijzen naar deze log.

## G. Open punten

1. Job-mechanisme (E).
2. OAuth-apps aanmaken (E).
3. `CONNECTION_ENCRYPTION_KEY` zetten (E).
4. Off-site back-up oplossen (blokkeert productie-migratie).
5. Akkoord op de merge van `feat/scope-documenten` (CI groen, PR nog niet gemaakt).
6. Volgorde van de commits herstellen zodat de archiefmigratie weer de laatste is (zie F). Dennis beslist.
