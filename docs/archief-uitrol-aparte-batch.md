# Archief-uitrol als aparte batch

Doel: het archiveren van alle bestaande documenten (migratie T1 uit `docs/bouwopdracht-fase-b7.md`) los houden van de rest van de branch `feat/scope-documenten`, zodat de rest gemerged kan worden zonder dat de archivering meegaat.

Besluit Dennis, 25 nov 2026: archivering komt pas op productie nadat de off-site back-up werkt.

## Stand (25 nov 2026)

- `8f7381a`: zonder archiefmigratie. Alembic-head `fb88a0a24a73`. 646 geslaagd, 1 uitgesloten.
- `3defa42`: mét archiefmigratie als laatste in de keten. Alembic-head `96a4f064fbef`. 653 geslaagd, 1 uitgesloten.

## Uitrol

1. Uitrol zonder archiveren: deploy `8f7381a`, of een latere commit vóór `3defa42`.
2. Uitrol van het archiveren: pas als de back-up werkt, in een eigen deploy, vanaf `3defa42` of een latere commit.

## Wat niet doen

- Geen archiefmigratie mergen naar `main` zonder dat de back-up werkt.
- Geen productie-acties vanuit Claude Code.
