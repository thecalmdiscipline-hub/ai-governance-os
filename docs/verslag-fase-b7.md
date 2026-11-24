# Verslag Fase B7: bestaande documenten archiveren, terugzetroute, codevoorstellen, verwijderrechten

Branch: `feat/scope-documenten`. Datum: 2026-11-24.
Stand: **T1 t/m T4 klaar en getest. Niets gepusht, niets gemerged, niets op productie.**

## 1. Commits op de branch

| Commit | Taak | Inhoud |
|---|---|---|
| `fddd56b` | T1 | Migratie `96a4f064fbef`: elk document dat nog niet `archived` is, wordt `archived`. De oude status gaat naar de nieuwe kolom `documents.scope_status_before_archive`. Bevat ook `docs/bouwopdracht-fase-b7.md`. |
| `faabb11` | T2–T4 | Terugzetroute, `POST /documents/scope-suggestion` met `config/document_scope_rules.yaml`, en verwijderen alleen door admin en operator. |

Alembic-head is nu **`96a4f064fbef`** (was `bab4f26df0b0`).

## 2. Testaantallen

| Moment | Resultaat |
|---|---|
| Vóór (stand na B6) | 585 geslaagd, 1 uitgesloten |
| Na T1 | 591 geslaagd, 1 uitgesloten |
| Na T2–T4 | **629 geslaagd, 1 uitgesloten, 0 overgeslagen** |

Commando: `pytest -m "not codex"`.

**Op PostgreSQL gedraaid** (`tests/test_migration_b7_archive.py`, elke test draait zowel op SQLite als op PostgreSQL):
- upgrade: alle rijen `archived`, evenveel rijen als vooraf, paden en bestandsinhoud ongewijzigd, bestaande codes blijven staan;
- downgrade: de bewaarde status komt terug; een document dat intussen is teruggezet, blijft `coded`; de kolom verdwijnt;
- upgrade op een lege tabel.

De keten B1 → B5 → B7 draait in deze test, dus de migraties van B1 en B5 zijn nu ook op PostgreSQL getest.

PostgreSQL in de test: als `TEST_POSTGRES_URL` gezet is, gebruikt de test die database. Anders start de test zelf een tijdelijke PostgreSQL-cluster (`initdb` + `pg_ctl`, lokaal PostgreSQL 14.21) in een tijdelijke map op een vrije poort op `127.0.0.1`. Na afloop wordt die cluster gestopt en verwijderd. Er is nooit verbinding met productie gemaakt.

**Let op voor CI:** op de GitHub-runner staan `initdb` en `pg_ctl` niet in het PATH. Daar worden de PostgreSQL-gevallen dus overgeslagen, met de reden in de pytest-uitvoer. Wil je dat CI ze ook draait, dan moet er een PostgreSQL-service met `TEST_POSTGRES_URL` in `ci.yml` komen. Dat heb ik niet gedaan, want het stond niet in de opdracht.

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

## 3. Downgrade en de oorspronkelijke status

- De upgrade bewaart per document de status van vóór de migratie in `scope_status_before_archive`. Documenten die al `archived` waren, raakt de migratie niet aan; daar blijft de kolom leeg.
- De downgrade zet die bewaarde status terug, maar **alleen** bij rijen die nog `archived` zijn en een bewaarde status hebben. Daarna wordt de kolom verwijderd.
- Zet een Valqeron-beheerder een document terug via `PATCH`, dan maakt de route `scope_status_before_archive` leeg. Een downgrade laat zo'n document dus `coded`.
- Grens: een document dat na de migratie opnieuw is gearchiveerd (via V29 of V30) zonder eerst te zijn teruggezet, heeft nog de bewaarde status van de migratie. Een downgrade zet het dan terug naar die status.
- Geen enkele `DELETE`, geen bestandsverplaatsing. Codes in `document_scope_codes` blijven staan.

## 4. Nieuwe dependencies

Geen. **PyYAML** (6.0.3) wordt nu gebruikt (`yaml.safe_load`), maar staat **niet** in `requirements.txt`. Het wordt geïnstalleerd omdat `presidio-analyzer` het nodig heeft (bevestigd met `pip show`). Voorstel: PyYAML expliciet vastzetten in `requirements.txt`, zodat het niet verdwijnt als presidio ooit wijzigt. Dat heb ik niet gedaan, omdat het een wijziging aan de dependencies is.

## 5. Keuzes die ik zelf heb gemaakt (graag bevestigen)

1. **Terugzetten met bestaande codes (V7):** een archiefdocument dat al codes heeft (bijvoorbeeld door V29/V30 gearchiveerd) kan alleen met exact die codes terug. Andere codes geven 409 `scope_fixed`. Een document zonder codes krijgt de codes uit de aanvraag. Eerst worden de codes gevalideerd (onbekend → 422), daarna pas wordt V7 gecontroleerd.
2. **Terugzetten en V30:** wordt een oude versie teruggezet, terwijl er een nieuwere gecodeerde versie met dezelfde bestandsnaam bestaat, dan zijn beide `coded`. De route archiveert de nieuwere versie niet; dat stond niet in de opdracht.
3. **Codevoorstellen:** een regel heeft `document_types` (extensies) en/of `keywords`. Een regel past als de extensie in de lijst staat óf als een trefwoord voorkomt (hoofdletterongevoelig, in de bestandsnaam en de eerste 20.000 tekens van de tekst). Het voorstel is de vereniging van de codes van alle passende regels. Kan het voorstel `hr` samen met een andere code bevatten? Ja, als twee regels passen. De upload weigert die combinatie dan (B3a). De uploader moet dus kiezen.
4. **Inhoud van het regelbestand:** de trefwoorden in `config/document_scope_rules.yaml` zijn een voorstel van mij (10 regels, één per code; `csv` → `bi` als voorbeeld van een regel op documenttype). Graag nakijken.
5. **Validatie bij het laden:** naast onbekende codes faalt het laden ook bij `hr` gecombineerd met een andere code, een regel zonder voorwaarde of zonder codes, een dubbele naam, onbekende velden, ongeldige YAML of een ontbrekend bestand.
6. **Wie mag een voorstel vragen:** dezelfde rollen als voor uploaden (admin en operator, plus een super-admin met MFA). Auditor en member krijgen 403.
7. **Verwijderen door een super-admin met MFA:** mag, net als bij uploaden (`require_any_role`).

## 6. Niet gebouwd

- **Archief downloaden (B5b, vlag `archive_download_enabled`):** staat in de besluiten (§1), maar niet in de taken T1–T4. Volgens regel 6 heb ik het niet gebouwd. `GET /documents/{id}/download` werkt dus nog voor elke gebruiker van de eigen organisatie, ook bij archiefdocumenten. Graag een taak als dit erbij moet.
- **PostgreSQL in CI:** zie §2.
- **Microsoft-sync en het demodocument bij provisioning** maken nog steeds documenten zonder code (status `uncoded`). Ongewijzigd, zie het verslag van B1–B6.

## 7. Frontend-gevolgen (nieuw)

- **Na de migratie is de documentenlijst van elke klant volledig `archived`.** De lijst toont ze nog (er is geen filter op status), maar geen workflow leest ze. Het portaal laat dat nog niet zien.
- **Nieuw endpoint `POST /documents/scope-suggestion`** (multipart, veld `file`). Antwoord: `readable`, `suggested_codes`, `matched_rules`. Het portaal kan dit tonen vóór de upload. Bevestigen betekent dat de gekozen code in de bestandsnaam en op de eerste regel van het bestand moet staan; de upload-API zelf is niet veranderd.
- **Verwijderen:** auditor en member krijgen nu 403. Een verwijderknop voor die rollen moet verborgen worden.
- **`PATCH /documents/{id}/scope`** accepteert nu ook archiefdocumenten (alleen Valqeron-beheerders, dus een ops-scherm, niet het klantportaal).

## 8. Bevestiging

- Niets gepusht: niet naar `main` en ook niet naar de branch. Niets gemerged.
- Geen productie-acties: geen SSH, geen deploy, geen migratie op productie. De PostgreSQL-test draaide op een tijdelijke lokale cluster die na afloop is verwijderd.
- Geen geheimen gelezen of geprint.
- Voor de productie-uitrol geldt §5 van de bouwopdracht: pas na jouw akkoord en een werkende off-site back-up.
