# Verslag Fase B: scope-codes en documenttoegang

Branch: `feat/scope-documenten`. Datum: 2026-11-23.
Stand: **B1 t/m B6 klaar. B7 (archiveren van bestaande documenten + terugzetroute) is niet gestart: wacht op akkoord van Dennis.**

## 1. Commits op de branch

| Commit | Stap | Inhoud |
|---|---|---|
| `5d349f9` | B1 | Tabel `document_scope_codes`, kolom `documents.scope_status` (default `uncoded`). Migratie `507b3c60b20b`. |
| `efeb6f6` | B2 | Codelijst op één plek, parsen uit bestandsnaam en eerste regel, validatie, upload weigert vóór het wegschrijven. |
| `4907c77` | B3 | Eén gedeelde documentfilter (`app/services/document_access.py`); `document_knowledge`, `sales_lead_qualification` en `compliance_monitoring` gebruiken hem. |
| `c030da7` | B4 | Snippets weg uit `document_knowledge`; `sources` in elke uitvoer van de drie workflows. |
| `33bc6d4` | B5 | Uploadrechten, archiveren in plaats van verwijderen, nieuwe versie vervangt oude, scope toewijzen alleen door Valqeron-beheerders, `PUT /ops/staff/{user_id}`. Migratie `bab4f26df0b0`. |
| `99a3b44` | B6 | `document_usage` per run en auditregel `workflow_run_documents`. |

Alembic-head is nu `bab4f26df0b0` (was `3352c2c44255`). Beide nieuwe migraties zijn op SQLite omhoog en omlaag getest.

## 2. Testaantallen

| Moment | Resultaat |
|---|---|
| Vóór (baseline) | 528 geslaagd, 1 uitgesloten |
| Na B1 | 530 |
| Na B2 | 549 |
| Na B3 | 564 |
| Na B4 | 567 |
| Na B5 | 580 |
| Na B6 | **585 geslaagd, 1 uitgesloten** |

Commando: `pytest -m "not codex"`. Nergens een rode test overgeslagen.

Verplichte tests uit de bouwopdracht (§4):

| # | Test | Waar |
|---|---|---|
| 1 | Upload zonder code: 422, geen bestand op schijf | `tests/test_document_scope.py` |
| 2 | Code in naam, niet in inhoud: 422 | idem |
| 3 | Onbekende code: 422 | idem |
| 4 | `hr`-document nooit gelezen door een niet-HR-workflow (ook niet bij expliciete selectie) | `tests/test_document_access.py` |
| 5 | `hr_recruitment` leest geen `sales`-document | idem |
| 6 | `gedeeld` wordt door alle tien workflows gelezen | idem |
| 7 | `uncoded` wordt door geen workflow gelezen | idem |
| 8 | `archived` wordt niet gelezen | idem |
| 9 | Gebruikt document wordt bij DELETE gearchiveerd, bestand blijft | `tests/test_document_rights.py` |
| 10 | Elke run schrijft `document_usage` en een auditregel | `tests/test_document_usage.py` |
| 11 | `sales_lead_qualification` zonder documenten werkt nog | `tests/test_document_access.py` |
| 12 | `compliance_monitoring` zonder documenten werkt nog | idem |
| 13 | Geen snippets in de response | idem |
| 14 | Auditor en member mogen niet uploaden (403) | `tests/test_document_rights.py` |
| 15 | Script `assign_document_scopes.py` dry-run | **niet gebouwd**, zie §4 |

Bestaande tests die ik heb aangepast (geen verzwakking, alleen aan het nieuwe gedrag): zes upload-tests uploaden nu een bestand met `[scope=kennis]` in de naam en `scope: kennis` als eerste regel; vijf tests die `document_knowledge` laten lezen maken hun document nu gecodeerd aan (`ensure_document(..., scope_codes=["kennis"])`); één test controleerde de snippets en controleert nu dat ze ontbreken en dat `sources` klopt.

## 3. Nieuwe dependencies

Geen. (PyYAML staat wel in de venv, maar is niet gebruikt; zie §4, V2.)

## 4. Wat niet is gedaan en waarom

- **B7 (archiveren van alle bestaande documenten, terugzetroute):** bewust niet gestart, zoals gevraagd. Wacht op akkoord.
- **V2 (automatische koppeling op documenttype, `config/document_scope_rules.yaml`):** niet gebouwd. Het staat in §1 maar in geen van de stappen B1–B6, en het botst met V1/V5: een upload zonder code wordt geweigerd, dus er valt niets automatisch te koppelen. Er is ook nergens een documenttype-veld. Graag besluiten wat V2 precies moet doen (bijvoorbeeld: een voorstel voor codes tonen in het portaal, of een regel per workflow welke codes hij mag lezen) voordat het gebouwd wordt.
- **Test 15 en het script `assign_document_scopes.py`:** niet gebouwd. B7 stap 4 zegt dat het script niet meer nodig is; test 15 is daardoor vervallen.
- **Test 7, deel "behalve via `LEGACY_UNCODED_ORGS`":** niet van toepassing, `LEGACY_UNCODED_ORGS` wordt niet gebouwd (B3d).
- **Beheer van de codelijst via een route:** niet gebouwd. De lijst staat in code (`app/services/document_scope_codes.py`) en wordt alleen via een codewijziging met review uitgebreid (scope-codes.md §4). Er is dus geen route om op te weigeren; de test "403 op codelijst-beheer" is daarom niet geschreven. De 403-test op `PATCH /documents/{id}/scope` is er wel (klantadmin, klantadmin met vlag en MFA, HQ zonder vlag, HQ met vlag zonder MFA).
- **Wie mag DELETE doen:** ongewijzigd (elke gebruiker van de eigen organisatie). De opdracht noemt geen rol; alleen het archiveren is toegevoegd.
- **Microsoft-sync en het demodocument bij provisioning:** die maken documenten zonder code. Ze blijven `uncoded` en worden dus door geen workflow gelezen. Niet aangepast (Microsoft staat uit, en voor het demodocument moet een code gekozen worden: voorstel `gedeeld`).
- **Frontend:** niet aangeraakt (B8).

## 5. Keuzes die ik zelf heb gemaakt (graag bevestigen)

1. **V30, "nieuwe versie":** een nieuwe upload met exact dezelfde bestandsnaam (inclusief `[scope=...]`) in dezelfde organisatie archiveert de vorige gecodeerde versie. De response noemt `replaced_document_ids`. Een andere code in de naam geldt dus als een ander document.
2. **Expliciete selectie:** ook als de aanvraag zelf documenten noemt, past dezelfde filter toe. Een `hr`-document selecteren in `document_knowledge` levert niets op.
3. **`hr` met `gedeeld`:** wordt bij upload en bij `PATCH` geweigerd (B3a). Bestaat zo'n rij toch, dan leest géén workflow hem, ook `hr_recruitment` niet.
4. **`PATCH /documents/{id}/scope`:** een Valqeron-beheerder werkt over organisaties heen (hij zit in HQ, het document bij de klant). Alleen bij status `uncoded`; anders 409. Auditregel in de HQ-keten en in die van de klant (`log_ops_action`).
5. **Valqeron-beheerder:** HQ-gebruiker + `is_valqeron_admin` + actief + MFA-token. Zelfde vorm als de super-admin-controle, geen tweede rechtensysteem. `PUT /ops/staff/{user_id}` weigert gebruikers buiten HQ (422).
6. **`document_usage`:** de runner registreert welke documenten de filter aan de workflow heeft gegeven (niet wat de workflow zelf terugmeldt). Bij een run met fout worden gelezen documenten ook geregistreerd. De auditregel komt alleen bij workflows die documenten lezen; bij nul documenten staat er "read no documents".
7. **`sources` bij een fout zonder API-sleutel:** leeg, want er is niets gelezen.
8. **Uploadrol "super-admin":** zoals `require_role` telt een super-admin met MFA ook als toegestaan.

## 6. Beslispunten B3a–B3d

| Punt | Gebruikt | Nog bevestigen? |
|---|---|---|
| B3a: `hr` exclusief | Ja: upload en `PATCH` weigeren elke combinatie met `hr`; filter leest `hr` alleen in `hr_recruitment` | Nee, door Dennis beantwoord |
| B3b: `gedeeld` aparte code | Ja: geen impliciete scope, `uncoded` wordt nooit gelezen | Nee |
| B3c: alleen Valqeron-beheerders wijzen codes toe | Ja: `PATCH /documents/{id}/scope` en `PUT /ops/staff` | Nee; wel de keuzes in §5 punt 4 en 5 |
| B3d: geen `LEGACY_UNCODED_ORGS`, alles archiveren | Geen uitzondering gebouwd. Het archiveren zelf is B7 en is **nog niet gedaan** | Ja: akkoord nodig om B7 te starten |

## 7. Frontend-gevolgen (bekend, niet opgelost)

- **Documentenpagina, upload:** een upload zonder `[scope=...]` in de naam en `scope: ...` op de eerste regel geeft nu 422. Auditors krijgen 403. Een PDF zonder tekstlaag kan geen code hebben en kan dus niet meer worden geüpload.
- **Documentenpagina, verwijderen:** een gebruikt document blijft bestaan (status `archived`); de response heeft `archived` in plaats van `deleted`.
- **"Ask your documents" / workflow-resultaat:** `answer.document_snippets` bestaat niet meer. Nieuw veld `sources` (bestandsnaam + codes).
- **Lijst- en detailweergave:** krijgen extra velden `scope_status` en `scope_codes` (geen breuk, wel nog niet getoond).

## 8. Bevestiging

- Niets gepusht: niet naar `main` en ook niet naar de branch (wacht op akkoord).
- Geen productie-acties: geen SSH, geen deploy, geen migratie op productie.
- Geen geheimen gelezen of geprint.
- Lokaal: de oude `test.db` is bewaard als `test-old-fase-b.db` (git-genegeerd), omdat `create_all` geen kolommen toevoegt aan een bestaande SQLite-database.

## 9. Vraag voor B7

B7 zet met een migratie **alle bestaande documenten op `archived`** en bouwt een terugzetroute (archief → `coded` via `PATCH /documents/{id}/scope`). Na uitrol leest geen workflow meer een oud document, ook niet bij organisatie 1 en 2. Open vraag 1 uit `docs/migratie-legacy-documenten.md` (welke documenten gebruiken klanten 1 en 2 nu?) is nog niet beantwoord. Mag ik B7 bouwen (alleen in code en tests, niets op productie)?
