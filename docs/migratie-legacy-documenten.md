# Migratievoorstel: bestaande documenten zonder scope-code

Status: **voorstel, 23 nov 2026.** Niet uitgevoerd. Geldt voor productie (organisaties 1 t/m 5 en later).

## 1. Probleem

Na fase B mag een workflow alleen documenten lezen met een scope-code die bij die workflow hoort (V3). Bestaande documenten hebben nog geen code. Zonder overgang leest `document_knowledge` daarna niets meer, ook niet de demodocumenten van organisaties 3, 4 en 5.

Besluit V27 zegt: bestaande documenten krijgen **handmatig** een code. Dat klopt voor echte klantdocumenten. Voor demo- en testdocumenten is het overbodig werk.

## 2. Besluit (23 nov 2026, Dennis)

**Alle bestaande documenten worden gearchiveerd. Daarna start alles vers.**

**Stap 1 — kolom.** Nieuwe kolom `documents.scope_status`: `uncoded` (nieuwe default), `coded`, `archived`.

**Stap 2 — archiveren.** Een migratie zet alle bestaande rijen op `archived` (V29, V30). Geen rij wordt verwijderd. Geen bestand wordt verplaatst. Oude documenten blijven zichtbaar in het archief.

**Stap 3 — geen overgangsregel.** Er is geen `LEGACY_UNCODED_ORGS` en geen einddatum. Demo-organisaties 3, 4 en 5 lezen geen documenten tot er nieuwe, gecodeerde documenten zijn geüpload.

**Stap 4 — terughalen van archief (alleen op verzoek).** Een Valqeron-beheerder kan een archiefdocument terugzetten: codeer het via `PATCH /documents/{id}/scope` en zet het op `coded`. Dat gebeurt per document, handmatig. Er is geen bulkscript.

**Beheer.** Alleen Valqeron-beheerders (Dennis, Rayvanno, of door Valqeron aangewezen personen) mogen codes toewijzen en de codelijst beheren. Organisatie-admins van klanten niet. Het recht komt van Valqeron (zie bouwopdracht B5a).

## 3. Volgorde in productie

1. Migratie `add scope_status` en archiveren van alle bestaande rijen, in één migratie.
2. Code uitrollen met de scope-filter. Vanaf dan lezen workflows alleen gecodeerde documenten.
3. Controle: demo-organisaties geven een nette "geen documenten gevonden"-uitvoer, niet een fout.
4. Klanten (organisatie 1 en 2) uploaden opnieuw met codes, of Valqeron zet oude documenten terug via de terugzetroute.

Stap 1 en 2 gebeuren in dezelfde deploy; de migratie is onomkeerbaar voor de lees-route, maar niet voor de data (rijen en bestanden blijven staan).

## 4. Open vragen

1. Is er een lijst van documenten die echte klanten (organisatie 1 en 2) nu gebruiken? Die moet met de klant worden doorgenomen voordat het archief wordt gemaakt.
2. Moet een archiefdocument downloadbaar blijven voor de klant, of alleen voor Valqeron?

## 5. Wat dit niet doet

- Geen automatische codetoewijzing op basis van inhoud. Dat is een AI-taak en wordt niet door de migratie gedaan.
- Geen verwijdering van bestanden of rijen.
- Geen wijziging van bestaande run-geschiedenis.
