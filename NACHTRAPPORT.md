# Rapport — 2026-10-12 (Claude Code, A6: ISO Cert International-prospectvideo opnieuw)

Opdracht van Dennis: "Lees WERKLIJST.md en het HERVAT-BLOK in CLAUDE.md. Op last van Dennis
(8 okt): voer rij 8 (A6, ISO CERT-video opnieuw) nu uit, vóór rij 5 (Batch M). Zet in
WERKLIJST.md rij 5 daarvoor op wachten en zet de volgorde terug als rij 8 KLAAR is. Volg de
stopregels uit de hand-off, commit en push niets dat geheimen bevat, verzend niets en schrijf
aan het eind NACHTRAPPORT.md." Dit document bevat geen geheimen of persoonsgegevens.

**Resultaat in één zin:** A6 (rij 8) is volledig af — een nieuwe prospectvideo (4:37,9 min) en
PDF (17 pagina's) voor ISO Cert International, die alle negen eerder gemiste prospectpunten
direct beantwoordt met alleen bestaande productcapaciteiten, staan lokaal klaar maar zijn
**niet verzonden**; WERKLIJST.md rij 8 staat op `KLAAR`, rij 5 (Batch M) is teruggezet op
`OPEN` en is nu de volgende uitvoerbare rij.

---

## Wat is er gebeurd

Dennis had de vorige (2026-10-05) prospectvideo beoordeeld met 7,5/10 voor beeld maar 5/10 voor
relevantie: negen specifieke punten die een certificatie-instelling (het fictieve ISO Cert
International-scenario) had opgeworpen, misten een directe, concrete beantwoording. De hand-off
`claude-code-handoff-a6-iso-cert-video-opnieuw.md` koppelt elk van de negen punten aan wat het
product daadwerkelijk doet, de aanpak voor de video, en een vooraf goedgekeurde zin — met de
harde regel: nooit overclaimen, twee ontbrekende capaciteiten (een los audit-rapport, een
ingebouwde goedkeuringsstap) eerlijk als "on the roadmap" tonen in plaats van verzinnen.

**Fase 0:** de meeste workflows hebben geen portaalformulier om een run te starten — alleen
Document Knowledge heeft dat. Hergebruikt: hetzelfde hybride patroon uit de 2026-10-05-productie
— runs starten via directe, echte API-calls tegen organisatie 4, en daarna een echte
portaalscreenshot van dat resultaat via de Results-tab. Elke screenshot in de video/PDF is dus
óf een echt, live portaalscherm, óf een duidelijk gelabeld, uit echte data opgebouwd technisch
overzicht — nooit een verzonnen productscherm. Nieuwe bevinding: `AuditPage.tsx` bestaat wel in
de frontendcode maar heeft geen navigatie-ingang — een klant ziet dit scherm nooit. Punt 9's
audit-logbewijs is daarom getoond als een directe, expliciet gelabelde `/audit/verify`-API-
respons (als technische terminal-output), niet als een niet-bestaand portaalscherm.

**Runs en screenshots:** 13 echte workflow-runs via API + 1 echte run via de portaal-UI (Ask
your documents) op organisatie 4, allemaal geslaagd. 5 fictieve Northbridge-documenten
geüpload. 30+ echte screenshots/assets verzameld (portaalschermen + 4 zelfgebouwde, uit echte
data opgebouwde technische overzichtspagina's: controlegebied-tabel, roadmap-kaarten,
"naast-uw-eigen-systeem"-diagram, audit-verify-bewijs).

**Belangrijkste bevinding — een onbewezen claim gecorrigeerd vóór publicatie:** het eerste
concept van scène 13 beweerde "Every governance action is recorded in a hash-chained audit
log." Een directe code-audit van `app/api/governance.py` (elke write-endpoint gecontroleerd op
een `create_audit_log()`-aanroep) toonde dit als feitelijk onjuist: vier endpoints
(`POST /ai-systems`, `POST /ai-risks`, `DELETE /ai-risks/{id}`, `POST /production-approvals/
{system_id}`) schrijven geen auditregel. Conform de hand-off se eigen regel ("klopt een regel
niet, pas de aanpak aan — nooit de claim — en meld het") is de zin aangescherpt naar wat
daadwerkelijk klopt, en die correctie is doorgevoerd in de narratie, de audio, het on-screen
asset, het videoframe én de PDF — alle vier opnieuw gegenereerd en visueel herbevestigd.

**Techniek onderweg:** de geïnstalleerde Homebrew-ffmpeg bleek zonder `drawtext`-filter gebouwd
(geen `libfreetype`) — opgelost zonder herinstallatie door titel-overlays met Pillow direct op
de screenshots te componeren, in dezelfde goud-op-donker stijl als eerdere producties. Zeer
lange full-page-screenshots zijn gecapt op een leesbare hoogte in plaats van onleesbaar
uitgerekt te worden.

**Kwaliteitscontrole:** een verboden-woorden-scan (as-is, ready to send, automatically, fully,
guarantee(d), continuous(ly), certified, compliant, "AI approves/decides") en een "elke absolute
claim of elk getal heeft bewijs nodig"-scan zijn uitgevoerd over alle 15 scène-narraties en de
4 asset-teksten — na de scène-13-correctie: 0 violaties. Alle 17 PDF-pagina's zijn naar PNG
gerenderd en bekeken (geen lege pagina's, geen afgekapte afbeeldingen, geen losse
onderschriften). 7 videoframes op verspreide tijdstippen zijn geëxtraheerd en bekeken
(leesbaar, niets afgekapt, de correctie zichtbaar correct). `QUALITY-REPORT-v2.md` staat in de
outputmap met de volledige puntsgewijze index (video-tijdstip + PDF-pagina + gebruikte zin per
punt).

## Resultaat

- Video: `demo-assets/iso-cert-international/prospect/v2/video/ISO-Cert-International-Live-Environment-Walkthrough-PROSPECT-v2.mp4`
  — 1280×720, 4:37,9 min, 5,0 MB, volledige decodeer-pass zonder fouten.
- PDF: `demo-assets/iso-cert-international/prospect/v2/pdf/ISO-Cert-International-Live-Environment-Walkthrough-PROSPECT-v2.pdf`
  — 17 pagina's, 5,6 MB.
- Kwaliteitsrapport: `demo-assets/iso-cert-international/prospect/v2/QUALITY-REPORT-v2.md`.
- **Alles staat uitsluitend lokaal.** `demo-assets/` is volledig gitignored (bevestigd vóór en
  na dit werk met `git check-ignore`); niets van A6 is of wordt gecommit. **Niets is verzonden**
  aan ISO Cert International of wie dan ook.

## Productiecontrole (organisatie 4)

14 nieuwe runs (13 via API + 1 via de echte portaal-UI), 5 nieuwe fictieve documenten
geüpload. Geen nieuwe gebruikers of wachtwoorden aangemaakt of gereset. Organisaties 1, 2, 3,
5: niet aangeraakt.

## WERKLIJST.md en CLAUDE.md

- Rij 8 (A6) op `KLAAR` gezet.
- Rij 5 (Batch M) teruggezet op `OPEN` — was tijdelijk op `WACHT` gezet op Dennis' verzoek zodat
  A6 eerst kon lopen.
- CLAUDE.md: nieuwe sectie-6-logregel voor deze sessie, HERVAT-BLOK bijgewerkt (volgende stap =
  rij 5, Batch M), en twee verouderde alinea's rechtgezet die Batch O2 nog als "geblokkeerd"
  en rij 2 (Batch H) nog als "volgende" beschreven — die batches waren al in een eerdere sessie
  afgerond, alleen deze twee samenvattende alinea's waren niet meer bijgewerkt.
- Beide bestanden gecommit (`9798f87`) en gepusht naar `origin/main`. Geen andere bestanden
  gewijzigd of gestaged — `git status` vóór de commit bevestigde alleen `CLAUDE.md` en
  `WERKLIJST.md` als gewijzigd, en de twee bekende, bewust nooit te committen untracked items
  (`claude-code-handoff-reset-admin-passwords.md`, `Claude outputs/`) ongewijzigd daarbuiten.

## Niet gedaan / openstaand

- **Niets verzonden** — dat was expliciet niet gevraagd en is bewust niet gedaan. Dennis moet
  zelf de video en de PDF volledig bekijken/lezen, ISO Cert International's eigen
  accreditatieclaims apart verifiëren, en beslissen of en wanneer iets verstuurd wordt.
- Een oud, los `.otp`-bestand in een eerdere-sessie-scratchpad (alleen-lezen-referentiemateriaal
  voor deze taak) is aangetroffen maar niet geopend, aangeraakt of verwijderd — gemeld in
  `QUALITY-REPORT-v2.md` als een mogelijk achtergebleven plaintext-wachtwoordrisico uit een
  eerdere sessie, niet iets dat deze taak zelf veroorzaakte of oploste.
- `claude-code-handoff-reset-admin-passwords.md` blijft bewust ongetrackt op de Mac (eerdere
  Dennis-beslissing, ongewijzigd).
- Batch M (rij 5), Batch Q (rij 6), Batch P (rij 7) en serverhardening (rij 10): niet
  uitgevoerd deze sessie — M is nu de volgende `OPEN`-rij, de andere drie wachten op Cowork of
  Dennis zoals de werklijst voorschrijft.

Geen migraties, geen auth/MFA/ops-codewijzigingen, geen productcodewijzigingen van welke aard
dan ook — A6 is uitsluitend contentproductie in een gitignored map.
