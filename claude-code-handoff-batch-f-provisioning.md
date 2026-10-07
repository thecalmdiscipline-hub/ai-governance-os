# Hand-off Batch F — Provisioning (nieuwe klant in één aanroep)

Auteur: Cowork (architect). Uitvoerder: Claude Code. Datum: 21 sep 2026.
Repo: `ai-governance-os` (alleen backend; er komt in deze batch **geen** portaalscherm, de Ops-tab hoort bij een latere fase).

## Doel

Een nieuwe klant aanmaken is nu handwerk (organisatie, gebruiker en modules apart, en er bestaat geen endpoint om modules toe te kennen). Na deze batch is het **één aanroep** die een werkende klant oplevert, veilig, herhaalbaar en met bewijs in de audit-trail. Alles loopt via de control plane uit Batch E (`/ops`, super-admin + MFA, dubbele audit-logging).

Taak-ID's uit het plan: 1.2 (module-API met tierregels), 1.3 (`POST /ops/tenants/provision`), 1.5 (testmatrix en smoke).

## Vooraf besloten door Dennis/Cowork (niet opnieuw voorleggen)

- **Tierregels (bevestigd door Dennis op 21 sep):** Starter = minstens 2 workflows; Business = minstens 5, waarvan Compliance Monitoring (`compliance_monitor`) er één is; Enterprise = minstens 7, waarvan Compliance Monitoring er één is. `core` is altijd aan en telt **niet** als workflow. Controleer in de code hoe "workflow" nu is gedefinieerd (de HQ-organisatie heeft 11 modules: `core` plus 10 workflows) en meld een afwijking; ga uit van "aantal modules exclusief `core`".
- **Bestaande organisaties blijven zoals ze zijn (grandfathering):** org 1 (HQ, 11 modules) en org 2 (demo, `core` + `customer_support_ai`) krijgen **geen** automatische backfill en worden niet opnieuw beoordeeld. Org 2 zou als Starter zelfs niet voldoen. Tierregels gelden voor nieuwe provisioning en voor wijzigingen via de nieuwe module-API. Meld in je rapport welke bestaande organisaties de regels overtreden.
- **Eerste beheerder:** krijgt een eenmalig wachtwoord dat **nooit per e-mail** wordt verstuurd. Het staat één keer in het antwoord van de provisioning-aanroep, `must_change_password=true` (bestaat sinds Batch E), en komt nergens in logs, auditdetails, Sentry of git.
- Geen portaalwijzigingen. Geen wijzigingen aan auth, MFA of het loginformulier.
- Demo-run met OpenAI is **optioneel** en mislukt nooit de hele provisioning (zie Deel 3).

## Werkwijze (vaste afspraken)

1. Begin met `git status` en `git diff` (drift-check). Verwacht HEAD `7f89e4d` of nieuwer. Meld afwijkingen; los ze niet stilzwijgend op.
2. **Fase 0 (alleen lezen), zet het resultaat in de eerste alinea van je rapport:** hoe `Organization`, `User`, `TenantModule` en de module-catalogus zijn gemodelleerd; of er al een `tier`-veld bestaat; wat `scripts/seed_modules.py` precies doet en of `deploy.sh` (dat hem bij elke deploy draait) daarmee bestaande organisaties wijzigt; hoe de modellen `AIPolicy` en `AIRisk` eruitzien en of er voorbeelden in org 1/2 zijn; hoe workflows aan modules gekoppeld zijn; hoe `log_ops_action` (Batch E) en `create_audit_log` werken. Wijkt iets af van dit document, dan **stoppen en melden** voordat je bouwt.
3. Kleine losse commits (zie de delen). Na elke push: CI én Deploy controleren via de GitHub Actions-API, plus een echte functionele check op productie.
4. Alleen additieve, nullable migraties. Geen nieuwe zware dependencies.

## Deel 1 — Tiers en module-API (commit 1 en 2)

- Migratie (additief): `organizations.tier` (`starter` | `business` | `enterprise`, nullable; bestaande rijen blijven `NULL`). Bestaat het veld al, hergebruik het.
- Eén servicefunctie (bijv. `app/services/tenant_modules.py`) met de tierregels en `validate_tier_modules(tier, modules)`, gebruikt door alles hieronder. **Geen dubbele regels** in meerdere plekken.
- Endpoints, allemaal onder `require_ops_access`, elke schrijfactie via `log_ops_action` (regel in HQ-keten én in de keten van de doel-tenant):
  - `GET /ops/tenants` (id, naam, tier, aantal modules, aantal actieve gebruikers),
  - `GET /ops/tenants/{id}` (dezelfde velden plus de modulelijst),
  - `GET /ops/tenants/{id}/modules`,
  - `PUT /ops/tenants/{id}/modules` met body `{ "tier": ..., "modules": [...] }`: vervangt de set, valideert tegen de tierregels, weigert onbekende module-keys en het weglaten van `core`, en is idempotent. Heeft de organisatie nog geen tier, dan is `tier` in de body verplicht. Bij overtreding `422` met een duidelijke lijst van wat er ontbreekt, zonder wijziging.
- `seed_modules.py` wordt een dunne wrapper om dezelfde servicefunctie. **Kritiek:** het draaien van `deploy.sh` moet voor bestaande organisaties functioneel identiek blijven. Bewijs dat met een `tenant_modules`-snapshot van org 1 en org 2 vóór en na de deploy (alleen aantallen en module-keys).

## Deel 2 — Provisioning-endpoint (commit 3)

`POST /ops/tenants/provision`, alleen `require_ops_access`, body (namen mogen afwijken van de bestaande conventie; meld het):

```json
{
  "idempotency_key": "rayvanno-2026-09",
  "organization_name": "...",
  "country": "NL",
  "sector": "...",
  "tier": "starter|business|enterprise",
  "modules": ["..."],
  "admin_username": "...",
  "admin_email": "...",
  "include_demo_document": true,
  "include_demo_run": false
}
```

- **Eén databasetransactie** met rollback bij elke fout: organisatie, eerste beheerder, tenant-modules, standaard-AIPolicy, starter-AIRisks en het optionele demodocument. Bij een fout blijft er niets van over (bewijs met een test die halverwege een fout forceert en daarna elke tabel telt).
- **Idempotent:** dezelfde `idempotency_key` met dezelfde parameters geeft `200` met de bestaande id's en `created: false`, maakt geen dubbele rijen en toont het wachtwoord **niet** opnieuw. Dezelfde sleutel met andere parameters geeft `409` zonder wijzigingen. Bestaat de organisatienaam al onder een andere sleutel (ook HQ), dan `409`.
- **Validatie:** tierregels via de gedeelde servicefunctie; `admin_username` uniek; sterk eenmalig wachtwoord (minstens 20 tekens, met `secrets`), opgeslagen als hash, `must_change_password=true`, nooit MFA of super-admin. De response heeft `Cache-Control: no-store`.
- **Standaard-AIPolicy en starter-AIRisk:** maak per nieuwe organisatie één algemene AIPolicy en per ingeschakelde workflow één starter-AIRisk, met de bestaande modelvelden en het formaat van de voorbeelden in de bestaande organisaties. Zet de tekstsjablonen in één apart bestand (bijv. `app/core/provisioning_defaults.py`) zodat Cowork ze kan nalezen en aanpassen. Teksten neutraal, in dezelfde taal als de bestaande voorbeelden, en duidelijk gemarkeerd als "standaardsjabloon, laten beoordelen door de klant". Neem je teksten op in je rapport.
- **Demodocument** (optioneel, standaard `true`): één kort fictief document zonder persoonsgegevens.
- **Demo-run** (optioneel, standaard `false`, kost OpenAI-geld): draait **na** de commit, buiten de transactie. Een falende run geeft `demo_run: "failed"` in de response, maar de tenant blijft bestaan.
- **Audit:** `log_ops_action` (HQ-keten én keten van de nieuwe tenant) bij succes; het wachtwoord of iets wat erop lijkt komt nergens in de details.
- **Schema:** de response bevat organisatie-id, tier, modules, admin-gebruikersnaam, het eenmalige wachtwoord (alleen bij `created: true`), aantallen aangemaakte policy's en risico's, en `demo_run`-status.

## Deel 3 — CLI en smoke (commit 4)

- `scripts/provision_tenant.py --config <json> [--dry-run] [--password-file PAD]`: draait dezelfde servicefunctie voor gebruik op de server (auditregel `performed_by="system:provision_cli"`), met `--dry-run` en het wachtwoord standaard naar stdout, of met `--password-file` naar een bestand met modus 600. Dit is het gereedschap voor de latere demotenant en de ISO Cert-organisatie.
- `scripts/smoke_provision.sh`: doorloopt provisioning tegen een draaiende API met een `OPS_TOKEN` uit de omgeving. **Geen tokens minten in scripts in de repo.** Documenteer in CLAUDE.md hoe Dennis zo'n token later verkrijgt (login met wachtwoord en code) en dat voor deze batch een server-side gemunt token is gebruikt (niet gecommit, niet geprint).

## Deel 4 — Testmatrix (bij elke commit meelopen)

Bestaande 198 tests blijven groen. Nieuw, zonder netwerk: tierregels (Starter met 1 workflow, Business zonder `compliance_monitor`, Enterprise met 6 workflows, elk `422`; geldig `200`); `core` verplicht; onbekende module-key; idempotentie (twee keer dezelfde aanroep: één organisatie, één gebruiker, dezelfde aantallen modules/policy's/risico's; wachtwoord alleen de eerste keer); sleutelconflict (`409`); naamconflict met HQ (`409`); **rollback** met geforceerde fout na de organisatie en na de gebruiker (alle tabellen leeg); `must_change_password` op de nieuwe beheerder en dat de poort uit Batch E werkt; **cross-tenant-isolatie voor `/ops`** (wijziging aan tenant X raakt geen rij van tenant Y; een gewone admin krijgt `403`; een super-admin zonder MFA-claim `403`); dubbele auditregels en `/audit/verify` `valid` voor HQ en de nieuwe tenant; het wachtwoord komt niet voor in een geserialiseerd Sentry-event, logregel of auditdetail (gebruik de bestaande in-memory-Sentry-testopzet); de `deploy.sh`-seed verandert bestaande organisaties niet.

## Deel 5 — Productiecheck (na deploy)

Met een tijdelijk server-side gemunt token voor `dennis_admin` (niet gecommit, niet geprint, na afloop niets laten liggen):
1. `GET /ops/whoami`, `GET /ops/tenants` (org 1 en 2 zichtbaar, tier `NULL`).
2. Provisioneer één wegwerp-tenant **"ZZ Provisioning Test"** (tier Business, een geldige modulelijst, demodocument aan, demo-run uit) en controleer: één aanroep gaf een werkende klant; organisatie, gebruiker, modules, policy en risico's kloppen met de aantallen; inloggen als de nieuwe beheerder met het eenmalige wachtwoord (server-side, niet printen) geeft de `password_change_required`-poort; wachtwoord wijzigen werkt en daarna werkt `/modules`.
3. Tweede identieke aanroep: `created: false`, geen dubbele rijen. Aanroep met een tierovertreding: `422`. Aanroep met dezelfde sleutel maar andere modules: `409`.
4. Isolatie: aantallen rijen van org 1 en org 2 zijn vóór en na gelijk, behalve de auditregels.
5. `/audit/verify` is `valid` voor org 1, org 2 en de nieuwe organisatie; er staat een regel in de HQ-keten en in die van de nieuwe organisatie.
6. Zet de gebruikers van de wegwerp-tenant op `is_active=False`. **Niets verwijderen.** Meld dat org 3 als testtenant blijft staan en welk id hij kreeg.

## Afronden

- CLAUDE.md bijwerken: sectie 2 (nieuwe endpoints en scripts), sectie 5 (risico's: grandfathering, wachtwoord in response, token-uitgifte), sectie 6 (logregel, nieuwste bovenaan), sectie 7 (volgende stap: Batch G, supportverzoek-slice, Resend). Doe vooraf `git status`/`git diff` en verifieer na de commit dat de wijziging blijft staan.
- Voeg in CLAUDE.md een korte handleiding "een klant aanmaken" toe in gewoon Nederlands, met het CLI-commando en een voorbeeldconfig.

## Stopvoorwaarden

Stop en meld als: het datamodel of `seed_modules.py`/`deploy.sh` afwijkt van dit document; een wijziging bestaande organisaties zou aanraken; tests rood worden; een migratie niet additief kan; een Deploy faalt (de pijplijn draait dan zelf terug, meld dat); je wachtwoorden, tokens of geheimen in output, logs, Sentry of git zou moeten zetten; de productietest iets anders zou raken dan de wegwerp-tenant.

## Rapport

Geef: Fase 0-bevindingen en afwijkingen; commits (hash + doel), CI/Deploy-run-id's; migratie (alleen namen en aantallen); nieuwe endpoints en scripts; testaantallen vóór en na; de resultaten van de productiecheck per stap (verwacht, gezien, echte uitvoer zonder geheimen); welke bestaande organisaties de tierregels overtreden; de standaardteksten van de AIPolicy en de starter-AIRisk; en beslissingen die je zelf hebt genomen.
