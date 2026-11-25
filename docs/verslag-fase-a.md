# Verslag Fase A: onderzoek en ontwerp

Opdracht: `docs/bouwopdracht-scope-en-integraties.md`, alleen Fase A. Datum: 2026-11-23.

## Wat is gedaan

- Branch `feat/scope-documenten` aangemaakt vanaf `main` (`71c9a2d`).
- Gelezen: `app/models/*` (document, workflow_run, ai_system, tenant_module, organization, user, microsoft_token,
  microsoft_document), `app/api/documents.py`, `app/services/document_storage.py`, `app/services/document_reader.py`,
  `app/services/module_access.py`, `app/services/tenant_modules.py`, `app/workflows/services/runner.py`, `app/workflows/registry.py`,
  de workflow-routers, `app/workflows/implementations/*` (volledig: document_knowledge; op documenttoegang, model, drempels en
  signatuur: de overige negen), `app/api/governance.py` (endpointoverzicht), `app/api/dependencies.py` (rollen, scoping),
  `app/api/microsoft.py`, `app/services/microsoft/*`, `app/integrations/microsoft/graph_client.py`, `app/core/microsoft_config.py`,
  `app/core/mfa.py` (Fernet-patroon), `app/services/provisioning.py`, de lijst met tests en de documentgerelateerde tests.
  `support_mail.py` niet opnieuw regel voor regel gelezen; het gedrag staat uitgebreid in CLAUDE.md en verandert niet (E7).
- Geschreven: `docs/ontwerp-scope-en-integraties.md` (datamodel, migratieplan, API-wijzigingen, documentfilter, integratielaag,
  besluiten → code, risico's, vragen, teststand).
- Dit verslag.
- **Geen codewijziging.** Eén commit op de branch met alleen deze twee documenten plus de bouwopdracht zelf
  (`docs/bouwopdracht-scope-en-integraties.md` stond ongetrackt in de repo).

## Testresultaten

- Vóór (baseline, `pytest -q -m "not codex"`, lokaal op de branch): **528 passed, 1 deselected, exit 0**.
- Na: niet opnieuw gedraaid, want er is geen code gewijzigd (alleen Markdown in `docs/`).
- Niet meegeteld: de losse suites `tools/handout/tests/` en `tools/report/tests/` (staan buiten `testpaths`, raken dit werk niet).

## Belangrijkste bevindingen

1. **De bronspecificatie ontbreekt.** `claude/scope-documenten-specificatie.md` staat nergens op deze Mac. Het ontwerp gebruikt
   alleen de besluiten die in de bouwopdracht samengevat staan; ontbrekende V-nummers kan ik niet plaatsen.
2. Alleen `document_knowledge` leest vandaag documenten. Zonder selectie pakt het de 5 nieuwste documenten van de hele
   organisatie, en het geeft 500 tekens ruwe tekst terug als snippet. `compliance_monitoring` en `sales_lead_qualification`
   lezen geen documenten; V21 is voor hen dus nieuw gedrag.
3. Documenten worden hard verwijderd, ook als ze in een run zijn gebruikt. Er wordt nergens vastgelegd welke documenten een run
   gebruikte; de auditregel per run bevat alleen workflow en status.
4. Elke rol (ook `auditor`) mag nu uploaden.
5. `ai_systems` en `workflow_runs` hebben geen koppeling met een workflow; die bestaat alleen via de modulenaam.
6. Microsoft-tokens staan onversleuteld in een `String`-kolom, de callback slaat niets op en eist een Bearer-token, er is geen
   Google-code (bevestigt §4 van de bouwopdracht).
7. Na Fase B zijn alle bestaande documenten ongeclassificeerd (V27), ook de demodocumenten op productie (org 3, 4, 5); na Fase C
   is een backfill van workflow-instanties nodig, anders kan niemand meer een run starten (V31).
8. Ongeveer 15 testbestanden raken documentgedrag; ze moeten in Fase B worden aangepast (zie ontwerp §10).

## Nieuwe dependencies

Geen. Het ontwerp gaat voor Fase E uit van `httpx` en `cryptography`, die al aanwezig zijn (geen Google- of Microsoft-SDK).

## Wat niet is gedaan en waarom

- Geen code, migraties of tests geschreven: Fase A is alleen ontwerp.
- De frontend (`ai-governance-frontend`) niet onderzocht: valt buiten deze opdracht (bouwopdracht §4).
- Niet gepusht. Pushen naar de branch mag (regel 2), maar was niet nodig voor een documentatiecommit; zeg het als je de branch
  op GitHub wilt hebben.

## Vragen voor Dennis

Zie `docs/ontwerp-scope-en-integraties.md`, §9 (13 vragen). De belangrijkste vóór Fase B:
- vraag 1 (bronspecificatie in de repo zetten),
- vraag 2 en 3 (welke codes, en het exacte formaat in bestandsnaam en inhoud),
- vraag 5 (wint HR altijd bij meerdere codes),
- vraag 13 (mag de frontend tijdelijk breken op snippets en upload zonder code).

## Bevestiging

- Niets gepusht naar `main`, geen commit op `main`.
- Geen productie-acties: geen SSH, geen `deploy.sh`, geen migraties, niets op de server.
- Geen `.env`, sleutels, tokens of `backup.env` gelezen of geprint.
- `CLAUDE.md` niet gewijzigd.
