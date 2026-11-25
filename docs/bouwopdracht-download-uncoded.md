# Bouwopdracht: downloadregel ook voor niet-gecodeerde documenten

Voor: Claude Code in `ai-governance-os`.
Branch: `feat/scope-documenten`, op commit `8f7381a` (archiefmigratie niet in de keten) of op `3defa42` (archiefmigratie erbij). Werk op de nieuwste commit van de branch.
Lees eerst: `docs/beslissingen-log.md` (sectie C), `docs/verslag-fase-b7.md`.

## 0. Harde regels

1. Alleen code en tests. Niets op productie.
2. Niet pushen en niet mergen zonder akkoord van Dennis.
3. Geen geheimen lezen of printen.
4. Geen nieuwe dependencies.
5. Eerst test, dan commit. Test rood = stoppen.

## 1. Besluit (Dennis, 25 nov 2026)

Oude documenten die nog niet gecodeerd zijn (status `uncoded`) mogen alleen door Valqeron worden gedownload. De vlag `archive_download_enabled` heeft hier **geen** invloed: die geldt alleen voor gearchiveerde documenten (status `archived`). Zo lekt er niets, ook zonder de archiefmigratie.

## 2. Taken

### T1: downloadregel uitbreiden

- Waar de bestaande regel voor `archived` staat (download en preview), geldt die ook voor `uncoded`.
- Voor een klantgebruiker: 403 bij `uncoded` of `archived` als de vlag `archive_download_enabled` uit staat. Met de vlag aan: alleen bij `archived`. Bij `uncoded` blijft het 403 voor klanten, ook met de vlag aan (een niet-gecodeerd document is geen archief).
- Valqeron-beheerders: altijd toegestaan, met de bestaande auditregel.
- Een document van een andere organisatie: altijd 404.
- Preview volgt dezelfde regel als download.

### T2: tests

1. Klantadmin, `uncoded`, vlag uit: 403 op download en preview.
2. Klantadmin, `uncoded`, vlag aan: 403 op download en preview.
3. Klantadmin, `archived`, vlag uit: 403.
4. Klantadmin, `archived`, vlag aan: 200 op download.
5. Valqeron-beheerder, `uncoded`: 200, met auditregel bij HQ en bij de klant.
6. Document van andere organisatie, `uncoded`: 404.
7. `coded` document: het gedrag van de bestaande lees-route blijft gelijk (regressie, geen wijziging).
8. Member en auditor krijgen dezelfde 403-regels als de klantadmin.

### T3: verslag

- Werk `docs/verslag-fase-b7.md` bij met een nieuwe sectie: wat is gewijzigd, de testaantallen vóór en na, en de commit-hash.
- Zet in het verslag dat de archiefmigratie niet nodig is om de download af te schermen.

## 3. Stoppen

- Draai de volledige testset. Meld het aantal.
- Push niet, merge niet.
- Stop na het verslag en wacht op Dennis.
