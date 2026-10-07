# Hand-off — ISO Cert International: prospectversie van de demo (deadline vandaag 19:00 NL) + twee productfixes

Auteur: Cowork (architect). Uitvoerder: Claude Code. Datum: 5 okt 2026.
Repo: `ai-governance-os` (backend). Demo-materiaal staat in `demo-assets/iso-cert-international/` (niet in git; blijft zo).

## Waarom en wat de deadline vraagt

De interne demo (PDF 17 p. + video 2:37) staat klaar. Voor de prospect is die **nog niet geschikt**:
- De PDF is een intern document: voettekst "Confidential — internal walkthrough", een stuk met eigen bevindingen bij stap 7 (p. 14: Nederlandstalige tekst, `<LOCATIE>`-placeholder) en slotpagina 17 met drie interne observaties ("Three things worth a closer look…", o.a. het ontbreken van een goedkeuringsstap en van startformulieren).
- De screenshot van stap 7 laat de placeholder en de Nederlandse tekst **niet** zien (Results toont daar alleen "processed successfully", detaildata staat verborgen). De fout zit dus alleen in de ruwe uitvoer en in onze eigen tekst. De video hoeft daarom waarschijnlijk niet opnieuw (zie A2).

**Volgorde, dit is de enige juiste volgorde:** Deel A (prospectversie) heeft prioriteit en moet vóór 19:00 klaar zijn. Deel B (twee productfixes) daarna, alleen als er tijd is, en mag de deadline nooit in gevaar brengen. Deel C (wachtwoord) op Dennis' melding. **Niets versturen naar wie dan ook: verzenden is Dennis' beslissing.**

## Vaste afspraken

1. Begin met `git status` en `git diff` (drift-check, verwacht HEAD `72c4b3f` of nieuwer). Meld afwijkingen.
2. Geen wachtwoorden, tokens of geheimen in output, logs, PDF, video, git of je rapport. Gebruik voor productieacties alleen een server-side gemunt token in geheugen (zoals eerder), reset het wachtwoord van `isocert_demo_admin` **niet**.
3. Raak auth, MFA, provisioning en andere organisaties niet aan. Alleen org 4 voor de ene echte testrun in Deel B.
4. Alles wat in de prospectversie staat moet **waar** zijn. Verberg niets wat de prospect zou misleiden (zie A1-regels); haal alleen interne commentaar weg.
5. CLAUDE.md bijwerken aan het eind (§5, §6, §7), met `git status`/`git diff` vooraf en verificatie na de commit.

## Deel A — Prospectversie (deadline-kritiek)

**A1. Nieuwe PDF** `demo-assets/iso-cert-international/prospect/ISO-Cert-International-Live-Environment-Walkthrough-PROSPECT.pdf`. De interne PDF blijft ongewijzigd staan. Zelfde stijl en screenshots, met deze wijzigingen:
- Voettekst: "Prepared for ISO Cert International — fictitious client scenario (Northbridge Precision Engineering Ltd)". Geen "internal".
- Stap 7 (p. 14): haal de alinea "Two things worth flagging honestly…" weg. Houd de feiten (itemised pricing, subtotal £3,300, VAT £660, total £3,960) en zeg niets over de taal of de inhoud van de narratieve tekst. **Is Deel B klaar en geverifieerd voordat je de PDF afrondt** (nieuwe run met `output_language="en"` zonder placeholders), dan mag je schrijven dat de narratieve tekst en de contractvoorwaarden in het Engels worden gegenereerd. Is Deel B er niet, schrijf dat dan niet.
- Slotpagina (p. 17): vervang "Observations…/Three things worth a closer look" door een korte, neutrale afsluiting: wat de negen stappen lieten zien (specifieke uitvoer, gebruik van het geüploade document), dat alle schermen uit de live productieomgeving komen, en dat de organisatie volledig is gescheiden van andere klanten. **Geen** beloftes over toekomstige functies of data, geen interne roadmap, geen kritiek op het product.
- **Moet blijven (eerlijkheid):** de introductie zegt nu dat zes workflows zijn gestart via een geauthenticeerde API-aanroep en dat alleen Document Knowledge een startformulier in het portaal heeft. Herschrijf dat naar één neutrale, feitelijke zin zonder zelfkritiek, bijvoorbeeld: "Document Knowledge is run through the portal; the other six workflows were started through the Valqeron API and their results are shown in the portal's Results view." Laat het niet weg.
- Noem nergens "AI proposes, human decides", goedkeuringsflows, of dat een klant zelf runs kan starten. Geen claim die het product vandaag niet waarmaakt (bevinding B1-klasse).
- Controleer de hele tekst op: wachtwoorden, tokens, interne URL's, de gebruikersnaam is toegestaan, bestandspaden, de woorden "internal", "finding", "bug", "LOCATIE". Render alle pagina's naar PNG en bekijk ze (zoals bij de eerste versie), controleer dat er geen losse onderschriften of lege pagina's zijn.

**A2. Video.** Lees het script van de 11 segmenten (voice-over) en controleer segmenten 07 (quote) en 10 (outro) op: vermelding van fouten, Nederlands/taal, placeholder, interne opmerkingen, beloftes over functies die niet bestaan. Vind je niets: **laat de video ongemoeid** en meld dat. Vind je iets: genereer alleen die segmenten opnieuw (TTS) en bouw de eindvideo opnieuw, met dezelfde geverifieerde aanpak (statische ffmpeg, alle segmenten opnieuw coderen). Controleer ook dat geen beeld een wachtwoord of token toont (het wachtwoordwijzigscherm toont lege velden; goed). Zet het resultaat in `prospect/ISO-Cert-International-Live-Environment-Walkthrough-PROSPECT.mp4` (kopie als er niets verandert).

**A3. Afleveren en bewijs.** Rapporteer: paden, bestandsgroottes, aantal pagina's en duur; een lijst van elke tekstwijziging ten opzichte van de interne PDF (letterlijk, in een tabel: pagina, oud, nieuw); het resultaat van de grep uit A1. **Doe niets met e-mail of uploads.**

## Deel B — Twee productfixes (na Deel A, alleen met tijd)

Bron: CLAUDE.md §6, regel 2026-10-05, "Twee echte, niet-zelf-opgeloste bevindingen".

1. **`<LOCATIE>` lekt onvervangen** in offerte- en contracttekst van Quote & Contract Generator. Onderzoek of het terugzetten (de-anonimisering) ontbreekt of niet alle velden dekt. Fix het in de gedeelde anonimiseringsservice, niet per workflow. Het terugzetten gebruikt alleen de mapping van dit ene verzoek en gaat alleen naar dezelfde gebruiker; herstelde tekst en mapping komen niet in logs, auditregels of Sentry. Voeg een vangnet toe: blijft er na het terugzetten een placeholder (patroon `<[A-Z_]+>`, ook genummerd) in klanttekst staan, dan wordt die niet ruw getoond; beschrijf je keuze en log zonder inhoud. Controleer alle andere workflows op hetzelfde patroon en rapporteer; los alleen op wat via de gedeelde functie vanzelf meegaat, bouw geen aparte logica per workflow zonder akkoord van Dennis.
2. **Quote & Contract Generator schrijft altijd Nederlands.** Voeg een optionele `output_language` toe (default `"nl"`, bestaand gedrag identiek; `"nl"` en `"en"` ondersteund; andere waarde geeft 422) en gebruik die voor `quote_text` en `contract_terms`. Pas de docstring aan. Geen portaalwijziging.

**Testen vóór CLAUDE.md:** unit tests (placeholder teruggezet; ongemapte placeholder niet ruw getoond; `en` geeft Engelse tekst; `nl` en weglaten gelijk aan nu; onbekende taal 422; geen placeholder of mapping in logs of Sentry-event); `pytest -q` volledig groen; CI en Deploy groen; **één** echte run op productie voor org 4 (ISO Cert International) met Northbridge-input en `output_language="en"`, met een server-side gemunt token voor `isocert_demo_admin` in geheugen (niet printen, wachtwoord niet resetten). Rapporteer run-id en uitvoer (geen persoonsgegevens): geen placeholders, Engelse tekst. Die run verschijnt in de Results van org 4; dat is bedoeld en eerlijk (geen output bewerken).

## Deel C — Wachtwoord van `isocert_demo_admin` (alleen op Dennis' melding)

Het huidige wachtwoord is meerdere keren gereset en met Dennis gedeeld in de chat; daarna staat het ook plat in `demo-assets/iso-cert-international/.new_password_DO_NOT_COMMIT`. Op Dennis' melding: zet een nieuw eenmalig wachtwoord via het bestaande resetpad (`must_change_password=true`), schrijf het met `--password-file`-stijl naar een bestand met modus 600, verwijder het oude wachtwoordbestand (of verplaats het naar `_to_delete/` en meld dat), en geef het nieuwe wachtwoord **niet** in de chat maar alleen als bestandslocatie. Zoek ook uit waarom de eerste browser-login op een 401 liep terwijl `curl` met dezelfde string slaagde (IP-limiet van 5 per 60 s gedeeld met `/login/mfa`? slot na 5 fouten? URL-encoding?) en meld de oorzaak; los het niet zelf op zonder akkoord.

## Stopvoorwaarden

Stop en meld als: een stap tijd kost die Deel A in gevaar brengt (kies dan voor Deel A en meld wat blijft liggen); een wijziging auth, MFA of andere organisaties zou raken; een wachtwoord of token in een bestand of uitvoer zou belanden; een claim in de prospectversie niet waar te maken is; een Deploy faalt (de pijplijn draait zelf terug, meld het).

## Rapport

Geef eerst Deel A (paden, groottes, wijzigingstabel, grep-resultaat, wat er met de video is gebeurd), dan Deel B (commits, CI/Deploy-run-id's, testaantallen, run-id en uitvoer, resultaat van de controle op andere workflows), en wat er blijft liggen voor Deel C.
