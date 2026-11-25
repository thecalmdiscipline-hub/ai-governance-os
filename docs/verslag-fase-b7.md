# Verslag Fase B7: bestaande documenten archiveren, terugzetroute, codevoorstellen, verwijderrechten

Branch: `feat/scope-documenten`. Datum: 2026-11-24.
Stand: **T1 t/m T4 klaar en getest, plus de correcties van Dennis van 24 nov (§9). Niets gepusht, niets gemerged, niets op productie.**

## 1. Commits op de branch

| Commit | Taak | Inhoud |
|---|---|---|
| `fddd56b` | T1 | Migratie `96a4f064fbef`: elk document dat nog niet `archived` is, wordt `archived`. De oude status gaat naar de nieuwe kolom `documents.scope_status_before_archive`. Bevat ook `docs/bouwopdracht-fase-b7.md`. |
| `faabb11` | T2–T4 | Terugzetroute, `POST /documents/scope-suggestion` met `config/document_scope_rules.yaml`, en verwijderen alleen door admin en operator. |
| `333ba13` | — | Eerste versie van dit verslag. |
| `69621e4` | Correcties | Archief downloaden (B5b, migratie `fb88a0a24a73`), 409 bij terugzetten naast een actieve versie, regelbestand aangepast, PyYAML vastgezet, PostgreSQL-service in CI. Zie §9. |
| `f7ce439` | — | Verslag bijgewerkt met de correcties. |
| `7aa0180` | Vervolg | `PUT /ops/tenants/{id}/archive-download`, plus een test voor de auditregel bij een preview. Zie §10. |
| `47d5b74` | — | Verslag, derde ronde. |
| `8f7381a` | Losmaken | Archief-migratie uit de keten gehaald; de app gebruikt `scope_status_before_archive` niet meer. Zie §11. |
| **`3defa42`** | **T1 (archief-migratie)** | **De archief-migratie `96a4f064fbef` als eigen, laatste commit. Alleen dit migratiebestand en de bijbehorende test. Zie §11.** |

Alembic-keten na §11: `bab4f26df0b0` → `fb88a0a24a73` (archief-vlag) → **`96a4f064fbef`** (archief-migratie, head). Zonder de archief-commit is de head `fb88a0a24a73`.

## 2. Testaantallen

| Moment | Resultaat |
|---|---|
| Vóór (stand na B6) | 585 geslaagd, 1 uitgesloten |
| Na T1 | 591 geslaagd, 1 uitgesloten |
| Na T2–T4 | 629 geslaagd, 1 uitgesloten, 0 overgeslagen |
| Na de correcties | 647 geslaagd, 1 uitgesloten, 0 overgeslagen |
| Na de ops-route (§10) | 650 geslaagd, 1 uitgesloten, 0 overgeslagen |
| Zonder archief-commit (`8f7381a`, §11) | **646 geslaagd, 1 uitgesloten, 0 overgeslagen** |
| Mét archief-commit (`3defa42`, §11) | **653 geslaagd, 1 uitgesloten, 0 overgeslagen** |

Commando: `pytest -m "not codex"`.

**Op PostgreSQL gedraaid** (`tests/test_migration_b7_archive.py`, elke test draait zowel op SQLite als op PostgreSQL):
- upgrade: alle rijen `archived`, evenveel rijen als vooraf, paden en bestandsinhoud ongewijzigd, bestaande codes blijven staan;
- downgrade: de bewaarde status komt terug; een document dat intussen is teruggezet, blijft `coded`; de kolom verdwijnt;
- upgrade op een lege tabel;
- `organizations.archive_download_enabled`: upgrade (standaard uit) en downgrade.

De keten B1 → B5 → B7 → archief-vlag draait in deze test, dus de migraties van B1 en B5 zijn nu ook op PostgreSQL getest.

PostgreSQL in de test: als `TEST_POSTGRES_URL` gezet is, gebruikt de test die database. Anders start de test zelf een tijdelijke PostgreSQL-cluster (`initdb` + `pg_ctl`, lokaal PostgreSQL 14.21) in een tijdelijke map op een vrije poort op `127.0.0.1`. Na afloop wordt die cluster gestopt en verwijderd. Er is nooit verbinding met productie gemaakt.

**CI:** `.github/workflows/ci.yml` heeft nu een PostgreSQL 16-service (dummy-wachtwoord, leeft alleen tijdens die ene CI-job) en zet `TEST_POSTGRES_URL`. Alleen de migratietest gebruikt die database; de rest van de suite blijft op SQLite in het geheugen. Is `TEST_POSTGRES_URL` gezet maar de database onbereikbaar, dan faalt de test (niet overgeslagen). Het `TEST_POSTGRES_URL`-pad is lokaal nagebootst tegen een losse tijdelijke database `migration_test` (8 geslaagd). Een echte CI-run is er nog niet: daarvoor moet de branch gepusht worden, en dat wacht op jouw akkoord.

Verplichte tests (§3):

| # | Test | Waar |
|---|---|---|
| 1 | Migratie op PostgreSQL | `tests/test_migration_b7_archive.py` (`[postgresql]`) |
| 2 | Migratie op SQLite | idem (`[sqlite]`) |
| 3 | Geen workflow leest een archiefdocument, ook niet met de juiste code of bij expliciete selectie (alle 10 workflows) | `tests/test_document_b7.py` |
| 4 | Valqeron-beheerder zet `archived` → `coded`: 200, daarna leest `sales_lead_qualification` het document (en `document_knowledge` niet) | idem |
| 5 | Klantadmin: 403 | idem |
| 6 | Onbekende code: 422 `scope_unknown`, status blijft `archived` | idem |
| 7 | Zonder MFA-token: 403 | idem |
| 8 | Auditregel in de HQ-keten en in de organisatie | idem |
| 9 | PDF zonder tekstlaag: geen voorstel (`readable: false`) en de upload wordt geweigerd (422) | idem |
| 10 | Trefwoord geeft voorstel, geen match geeft een lege lijst | idem |
| 11 | Upload zonder bevestigde code, ook met een voorstel: 422 `scope_missing` | idem |
| 12 | Yaml met onbekende code: `ScopeRulesError` met regelnaam en code in de melding | idem (plus 7 andere ongeldige bestanden en een ontbrekend bestand) |
| 13 | `DELETE` door auditor/member: 403 (document blijft); door admin/operator: 200 | idem |
| 14 | `sales_lead_qualification` en `compliance_monitoring` zonder documenten werken nog | idem, plus de bestaande tests in `tests/test_document_access.py` |
| extra | Klantgebruiker krijgt 403 op download en preview van een archiefdocument zonder vlag; met vlag 200 | `tests/test_document_b7.py` |

## 3. Downgrade en de oorspronkelijke status

- De upgrade bewaart per document de status van vóór de migratie in `scope_status_before_archive`. Documenten die al `archived` waren, raakt de migratie niet aan; daar blijft de kolom leeg.
- De downgrade zet die bewaarde status terug, maar **alleen** bij rijen die nog `archived` zijn en een bewaarde status hebben. Daarna wordt de kolom verwijderd.
- Zet een Valqeron-beheerder een document terug via `PATCH`, dan maakt de route `scope_status_before_archive` leeg. Een downgrade laat zo'n document dus `coded`.
- Grens: een document dat na de migratie opnieuw is gearchiveerd (via V29 of V30) zonder eerst te zijn teruggezet, heeft nog de bewaarde status van de migratie. Een downgrade zet het dan terug naar die status.
- Geen enkele `DELETE`, geen bestandsverplaatsing. Codes in `document_scope_codes` blijven staan.

## 4. Nieuwe dependencies

Geen nieuwe pakketten. **PyYAML** wordt nu gebruikt (`yaml.safe_load`). Het werd al geïnstalleerd omdat `presidio-analyzer` het nodig heeft; op jouw verzoek staat het nu ook expliciet in `requirements.txt`, als `PyYAML==6.0.3`, de versie die al in de venv stond.

## 5. Keuzes die ik zelf heb gemaakt (graag bevestigen)

1. **Terugzetten met bestaande codes (V7):** een archiefdocument dat al codes heeft (bijvoorbeeld door V29/V30 gearchiveerd) kan alleen met exact die codes terug. Andere codes geven 409 `scope_fixed`. Een document zonder codes krijgt de codes uit de aanvraag. Eerst worden de codes gevalideerd (onbekend → 422), daarna pas wordt V7 gecontroleerd.
2. **Terugzetten en V30:** zie §9, punt 3 (nu 409).
3. **Codevoorstellen:** zie §9, punt 4 (hele woorden, `match: all`, nooit `hr` met een andere code).
4. **Inhoud van het regelbestand:** de trefwoorden in `config/document_scope_rules.yaml` zijn een voorstel van mij (10 regels, één per code), aangepast volgens §9.
5. **Validatie bij het laden:** naast onbekende codes faalt het laden ook bij `hr` gecombineerd met een andere code, een regel zonder voorwaarde of zonder codes, een dubbele naam, onbekende velden, ongeldige YAML of een ontbrekend bestand.
6. **Wie mag een voorstel vragen:** dezelfde rollen als voor uploaden (admin en operator, plus een super-admin met MFA). Auditor en member krijgen 403.
7. **Verwijderen door een super-admin met MFA:** mag, net als bij uploaden (`require_any_role`).

## 6. Niet gebouwd

- (Opgelost in §10: de ops-route voor de vlag `archive_download_enabled` is er nu.)
- **Microsoft-sync en het demodocument bij provisioning** maken nog steeds documenten zonder code (status `uncoded`). Ongewijzigd, zie het verslag van B1–B6.

## 7. Frontend-gevolgen (nieuw)

- **Na de migratie is de documentenlijst van elke klant volledig `archived`.** De lijst toont ze nog (er is geen filter op status), maar geen workflow leest ze. Het portaal laat dat nog niet zien.
- **Nieuw endpoint `POST /documents/scope-suggestion`** (multipart, veld `file`). Antwoord: `readable`, `suggested_codes`, `matched_rules`. Het portaal kan dit tonen vóór de upload. Bevestigen betekent dat de gekozen code in de bestandsnaam en op de eerste regel van het bestand moet staan; de upload-API zelf is niet veranderd.
- **Verwijderen:** auditor en member krijgen nu 403. Een verwijderknop voor die rollen moet verborgen worden.
- **`PATCH /documents/{id}/scope`** accepteert nu ook archiefdocumenten (alleen Valqeron-beheerders, dus een ops-scherm, niet het klantportaal). Nieuwe fout 409 `active_version_exists`.
- **Download en preview van een archiefdocument:** een klantgebruiker krijgt 403 `archive_download_disabled`, tenzij de vlag voor zijn organisatie aan staat. Download- en voorbeeldknoppen bij archiefdocumenten moeten dan verborgen worden.

## 8. Bevestiging (bijgewerkt na de correcties)

- Niets gepusht: niet naar `main` en ook niet naar de branch. Niets gemerged.
- Geen productie-acties: geen SSH, geen deploy, geen migratie op productie. De PostgreSQL-test draaide op een tijdelijke lokale cluster die na afloop is verwijderd.
- Geen geheimen gelezen of geprint.
- Voor de productie-uitrol geldt §5 van de bouwopdracht: pas na jouw akkoord en een werkende off-site back-up.

## 9. Correcties van Dennis (24 nov 2026)

Alle correcties zitten in commit `69621e4`.

1. **Archief downloaden (B5b).** Let op: in `docs/bouwopdracht-scope-en-integraties.md` staat geen B5b en ook nergens `archive_download_enabled`. De enige beschrijving is de regel in `docs/bouwopdracht-fase-b7.md` §1 en jouw opdracht. Daarop gebouwd:
   - Nieuwe kolom `organizations.archive_download_enabled` (standaard uit), migratie `fb88a0a24a73`, getest op SQLite en PostgreSQL.
   - `GET /documents/{id}/download` **en** `GET /documents/{id}/preview` (het voorbeeld toont ook de inhoud, dus dezelfde regel) volgen één functie, `get_readable_document`:
     - document niet gearchiveerd: zoals voorheen, alleen de eigen organisatie;
     - gearchiveerd, Valqeron-beheerder (HQ, vlag, MFA): mag, bij elke organisatie;
     - gearchiveerd, gebruiker van de eigen organisatie: alleen als de vlag aan staat, anders **403** `archive_download_disabled` (getest);
     - document van een andere organisatie: altijd 404 voor een klantgebruiker, ook als zijn eigen vlag aan staat.
   - Eigen keuzes: (a) met de vlag aan mag elke rol van die organisatie downloaden, net als bij een gewoon document; (b) een Valqeron-beheerder kan via deze route alleen *gearchiveerde* documenten van een klant openen, geen actieve (404); (c) elke download of preview door een Valqeron-beheerder van een archiefdocument krijgt een auditregel in de HQ-keten en in die van de klant (`archived_document_downloaded` / `archived_document_previewed`). Toegang over organisaties heen hoort in het auditlog; graag bevestigen.
2. **PyYAML** staat vast als `PyYAML==6.0.3` in `requirements.txt`.
3. **Terugzetten, codes:** andere codes dan de bestaande geven 409 `scope_fixed`; een document zonder codes krijgt de codes uit de aanvraag als eerste codes. Dit werkte al zo sinds `faabb11`; er is een extra test bij gekomen.
4. **Terugzetten naast een actieve versie:** is er in dezelfde organisatie een ander document met dezelfde bestandsnaam dat `coded` is, dan geeft terugzetten **409** `active_version_exists`, en beide documenten blijven zoals ze waren. Ik controleer op *elke* andere actieve versie, niet alleen een nieuwere: anders zouden er alsnog twee actieve versies zijn (V30). Normaal is die andere versie de nieuwere die de oude heeft vervangen.
5. **Regelbestand:**
   - `procedure` en `avg` zijn verwijderd uit de compliance-regel.
   - Trefwoorden passen alleen op hele woorden: vlak vóór of na het trefwoord mag geen letter of cijfer staan. `invoice` past dus niet op `invoicing`; een liggend streepje telt als scheiding, dus `invoice_jan.txt` past wel. Woorden uit meerdere delen (`ai act`, `iso 27001`) werken ook.
   - Nieuw veld `match` per regel: `any` (standaard) of `all`. De csv-regel heeft `match: all`: hij past alleen als het bestand een `.csv` is **én** een trefwoord bevat (`kpi`, `kwartaalrapport`, `dashboard`). Een losse csv krijgt dus geen voorstel meer, en een tekstbestand met `kpi` ook niet.
   - Het voorstel-endpoint geeft **nooit** `hr` samen met een andere code. Past een `hr`-regel, dan is het voorstel alleen `[hr]`, ook als andere regels ook passen (die staan nog wel in `matched_rules`). Eigen keuze: `hr` gaat vóór, omdat een te ruim gedeeld personeelsdocument erger is dan een te nauw gedeeld gewoon document. Graag bevestigen.
   - Bij het laden wordt ook `match` gecontroleerd (alleen `any`/`all`; `all` vraagt zowel `document_types` als `keywords`). Een fout stopt de app bij het opstarten.
6. **PostgreSQL in CI:** zie §2.

## 10. Vervolg (24 nov 2026, derde ronde)

1. **`PUT /ops/tenants/{id}/archive-download`** (commit `7aa0180`), in `app/api/ops.py` naast de andere tenant-routes.
   - Body: `{"archive_download_enabled": true|false}`; andere velden geven 422.
   - Dezelfde ops-controles als alle `/ops/*`-routes: `require_ops_access` (super-admin van HQ, actief, MFA-token), inclusief de bestaande rate limit. Een klantadmin, een Valqeron-beheerder zonder super-admin en een super-admin zonder MFA krijgen 403; een onbekende organisatie geeft 404 `tenant_not_found`.
   - Idempotent. Alleen bij een echte wijziging komt er een auditregel via `log_ops_action`, in de HQ-keten én in die van de organisatie (`archive_download_enabled` of `archive_download_disabled`).
   - Antwoord: `{organization_id, archive_download_enabled, changed}`.
   - Getest: aan, nog een keer aan (`changed: false`, geen tweede auditregel), een member downloadt een archiefdocument (200), uit, dezelfde member krijgt 403.
2. **Auditregel bij download of preview door een Valqeron-beheerder:** zat al in `69621e4` (`archived_document_downloaded` / `archived_document_previewed`, HQ en klant). Er was alleen een test voor de download; nu ook voor de preview.
3. **`hr` wint in het voorstel:** zat al in `69621e4`. Passen een `hr`-regel en andere regels tegelijk, dan is het voorstel alleen `["hr"]` (test `test_hr_is_never_suggested_with_another_code`). Niets gewijzigd.

**Push en CI:** de branch `feat/scope-documenten` is gepusht (niet `main`, niet gemerged). `ci.yml` start niet vanzelf bij een push naar deze branch (alleen bij `main`, `feature/workflow-platform` en pull requests). Daarom is CI handmatig gestart op deze branch (`workflow_dispatch`). De deploy-workflow reageert alleen op CI van `main`, dus er is niets gedeployd. Uitkomst van die CI-run: zie het bericht aan Dennis.

## 11. Archief-migratie apart (25 nov 2026)

De opdracht verwees naar `claude/archief-uitrol-aparte-batch.md`. Dat bestand staat niet in de repo; ik heb gewerkt vanuit jouw bericht en `docs/bouwopdracht-fase-b7.md`.

**De archief-migratie staat in commit `3defa42`** (revisie `96a4f064fbef`). Die commit bevat alleen het migratiebestand en de test ervan, verder niets.

Hoe:
- **`8f7381a`** haalt de archief-migratie uit de keten. De migratie voor de vlag `archive_download_enabled` (`fb88a0a24a73`) volgt nu direct op `bab4f26df0b0`. De app gebruikt de kolom `scope_status_before_archive` niet meer: die is uit het model gehaald, en de terugzetroute maakt hem niet meer leeg. De migratietests zijn gesplitst: `tests/test_migration_b7.py` (B1 → B5 → vlag, plus de gedeelde fixtures) en `tests/test_migration_b7_archive.py` (alleen de archief-migratie).
- **`3defa42`** zet de archief-migratie terug als laatste revisie, op `fb88a0a24a73`. Er is geen geschiedenis herschreven: de eerdere commits (`fddd56b` e.d.) staan er nog, dus een gewone push volstaat (geen force-push nodig).

**Zonder de archief-commit** (stand `8f7381a`):
- De kolom `scope_status` blijft. Bestaande documenten houden hun status: `uncoded` sinds B1 (nieuwe test `test_without_archive_migration_existing_rows_keep_their_status`, op SQLite en PostgreSQL).
- Let op: ook `uncoded` wordt door geen enkele workflow gelezen (B3). Wat wél verschilt met archiveren: een `uncoded` document valt niet onder de archiefregel voor downloaden (B5b), dus de eigen organisatie kan het gewoon downloaden en bekijken. Een Valqeron-beheerder kan het coderen via `PATCH` (route voor `uncoded`). En verwijderen werkt zoals altijd (archiveren als het al in een run gebruikt is).
- Testset: **646 geslaagd**, 1 uitgesloten, 0 overgeslagen (PostgreSQL-tests gedraaid).

**Mét de archief-commit** (stand `3defa42`): testset **653 geslaagd**, 1 uitgesloten, 0 overgeslagen.

**Downgrade, gewijzigd:** omdat de app de kolom niet meer leegmaakt bij terugzetten, geldt nu: een teruggezet document is `coded` en blijft bij een downgrade `coded`. Uitzondering: een document dat is teruggezet en daarna opnieuw gearchiveerd (V29/V30), krijgt bij een downgrade zijn status van vóór de migratie terug. Dit staat in het migratiebestand zelf.

**Uitrol zonder archiveren:** de commit vóór `3defa42` deployen, of het migratiebestand `96a4f064fbef_archive_existing_documents.py` weglaten. Komt er later nog een commit bovenop `3defa42`, dan zit de archief-migratie daar ook in; die moet dan bewust weggelaten of teruggedraaid worden.

Niet gepusht, niet gemerged, niets op productie.
