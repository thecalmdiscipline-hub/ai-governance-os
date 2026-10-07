# Hand-off — ISO Cert prospectversie: nacontrole, 3 correcties, wachtwoord roteren

Auteur: Cowork (architect). Uitvoerder: Claude Code, **sessie 1** (degene die Deel A deed). Datum: 5 okt 2026, deadline vandaag 19:00 NL.
Repo: `ai-governance-os`. Materiaal: `demo-assets/iso-cert-international/prospect/` (niet in git).

## Antwoord op je vraag

Deel B hoeft **niet** meer: de parallelle sessie heeft het gedaan en ik heb het gecontroleerd tegen CLAUDE.md (commits `7a2e251`, `4770448`, `de29e2c`, run `70a4fdf5-f0c2-407c-8536-2c0f909a3fd3`). Doe er niets aan en draai die run niet opnieuw. De gelijktijdige sessie was bedoeld.

## Wat ik na controle van je PDF wil aanpassen

Ik heb alle 17 pagina's tekstueel nagelopen. Goed: voettekst, p.3-zin, p.17-slot, geen interne woorden. Drie punten kloppen niet met wat we kunnen waarmaken:

1. **p.14**: "generated in the client's own language" is te breed. Het product ondersteunt alleen `nl` en `en`, en de getoonde Results-run is bovendien de eerdere (Nederlandse) run. Vervang door: "...alongside a full narrative quote and a set of contract terms, which can be generated in English or Dutch."
2. **p.15** (Meeting Agenda): "ready to send as-is" → "ready for review". Dit is AI-uitvoer van een product dat aan een certificatie-instelling wordt getoond; "zonder menselijke controle versturen" mag nergens suggereren.
3. **p.17**: "ready-to-use artefacts" → "ready-for-review artefacts".

Zoek in de hele PDF-tekst ook op "as-is", "ready to send", "ready-to-use", "automatically", "fully", "guarantee" en meld wat je vindt. Pas alleen aan wat een belofte of een overclaim is; verander niets aan feiten.

## Deel 1 — PDF opnieuw bouwen

Zelfde bouwscript, alleen de drie tekstwijzigingen (plus eventuele treffers uit de zoekactie, eerst melden). Bouw naar hetzelfde pad (overschrijven mag; de interne PDF blijft onaangeroerd). Render alle pagina's opnieuw, controleer dat p.14, p.15 en p.17 de nieuwe tekst hebben en dat er nog steeds geen lege pagina's of losse onderschriften zijn. Rapporteer de wijzigingstabel (pagina, oud, nieuw).

## Deel 2 — Video-script laten zien

Ik kan het geluid niet beluisteren. Geef mij **de volledige voice-over-tekst van alle 11 segmenten van de prospectvideo, letterlijk** (zoals naar TTS gestuurd), in je rapport. Markeer bij elke zin of die iets zegt over: fouten of interne opmerkingen, taal, "ready to send", goedkeuring of menselijke beslissing, functies die er niet zijn. Wijzig de video **niet** zonder mijn akkoord; zijn er zinnen die niet kloppen, stel dan alleen de vervangende tekst voor.

## Deel 3 — Wachtwoord `isocert_demo_admin` roteren (Dennis geeft hierbij akkoord)

Uitvoeren zoals in het eerdere hand-off Deel C:
1. Zet een nieuw eenmalig wachtwoord via het bestaande resetpad (`must_change_password=true`), schrijf het naar een nieuw bestand met modus 600 (`--password-file`-stijl) buiten git. Print het wachtwoord nergens en zet het niet in het rapport; geef alleen de bestandslocatie.
2. Verifieer met één echte `POST /login` (zonder het wachtwoord te tonen), zorg dat het nieuwe wachtwoord daarna **niet** is verbruikt door een wachtwoordwijziging.
3. Verwijder `demo-assets/iso-cert-international/.new_password_DO_NOT_COMMIT`. Is verwijderen geblokkeerd, verplaats het dan naar `_to_delete/` en meld dat.
4. Zoek de oorzaak van de eerste 401 bij browser-login terwijl `curl` met dezelfde string slaagde (IP-limiet gedeeld met `/login/mfa`? slot na 5 fouten? URL-encoding?). Alleen onderzoeken en melden, niets aan auth wijzigen.
5. Elke blokkade van de classifier: stoppen en melden, niet omzeilen.

## Vaste afspraken

- `git status`/`git diff` eerst; verwacht `de29e2c` of nieuwer. Niets versturen, niets uploaden.
- Geen wachtwoorden of tokens in output, logs, PDF, video, git of rapport.
- Auth, MFA, provisioning, andere organisaties: niet aanraken.
- CLAUDE.md **aan het eind** bijwerken (§5, §6, §7): Deel A (prospectversie, video, wijzigingen), correcties uit dit document, wachtwoordrotatie, 401-oorzaak. Verwijs voor Deel B naar de andere sessie; schrijf het niet dubbel.
- Stop en meld als een claim in de prospectversie niet waar te maken is.

## Rapport

1. Wijzigingstabel PDF + zoekresultaat. 2. De 11 voice-over-teksten met markeringen. 3. Wachtwoord: bestandslocatie, resultaat van de loginverificatie, wat er met het oude bestand is gebeurd, oorzaak 401 (of "onbekend"). 4. Commit-hash van de CLAUDE.md-update.
