# Archief-uitrol als aparte batch

Doel: het archiveren van alle bestaande documenten (migratie T1 uit `docs/bouwopdracht-fase-b7.md`) los houden van de rest van de branch `feat/scope-documenten`, zodat de rest gemerged kan worden zonder dat de archivering meegaat.

Besluit Dennis, 25 nov 2026: archivering komt pas op productie nadat de off-site back-up werkt.

## Stand (25 nov 2026)

- `e30bf9b`: zonder archiefmigratie, mét de downloadregel voor `uncoded`. Alembic-head `fb88a0a24a73`. 682 geslaagd, 1 uitgesloten.
- `fb60d21`: mét archiefmigratie als laatste code-commit. Alembic-head `96a4f064fbef`. 689 geslaagd, 1 uitgesloten.
- (Oude hashes vóór de herordening: `725576a` en `3defa42`.)

## Uitrol

1. Uitrol zonder archiveren: deploy `e30bf9b`.
2. Uitrol van het archiveren: pas als de back-up werkt, in een eigen deploy, vanaf `fb60d21` of een latere commit.

## Wat niet doen

- Geen archiefmigratie mergen naar `main` zonder dat de back-up werkt.
- Geen productie-acties vanuit Claude Code.
