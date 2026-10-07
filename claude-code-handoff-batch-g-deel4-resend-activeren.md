# Hand-off Batch G, Deel 4 — Resend activeren (supportmail aanzetten)

Auteur: Cowork (architect). Uitvoerder: Claude Code, **één sessie** (de andere sessie laat je dicht of leeg). Datum: 6 okt 2026.
Repo: `ai-governance-os` (backend). Productie: `/opt/valqeron` op `164.92.221.90`.

## Doel

Supportverzoeken van klanten leveren nu wel een record op, maar nog geen e-mailmelding (`notify_status=skipped_no_config`). Na deze batch krijgt Dennis een melding op `support@valqeron.com` bij elk nieuw supportverzoek. Dit is Deel 4 uit `claude-code-handoff-batch-g-supportverzoek.md`; lees dat deel opnieuw voor de achtergrond (mail via `httpx`, nooit blokkerend, geen berichttekst in logs).

## Wat al klaar is (door Dennis en Cowork, 6 okt)

- Resend-account (EU-regio **Ireland, eu-west-1**) met verzenddomein **`mail.valqeron.com`**, status **Verified** (DKIM en beide CNAME's). Cowork controleerde de DNS-records ook in de openbare DNS: kloppen.
- "Enable Receiving" in Resend staat **uit** en blijft uit; er is geen MX-record voor Resend aangemaakt en het MX-record van `valqeron.com` is niet aangeraakt.
- Het postvak `support@valqeron.com` bestaat bij Strato (ontvangstadres).
- Dennis maakt in Resend een API-sleutel met alleen **"Sending access"**, beperkt tot het domein `mail.valqeron.com`. Hij geeft die sleutel **alleen aan jou in deze sessie** als jij erom vraagt. De sleutel komt nergens anders: niet in chat met Cowork, niet in git, niet in logs.

## Waarden

| Variabele | Waarde |
|---|---|
| `SUPPORT_FROM_EMAIL` | `support@mail.valqeron.com` (kijk eerst hoe de code het van-adres opbouwt; zet geen weergavenaam als de code die zelf toevoegt) |
| `SUPPORT_NOTIFY_EMAIL` | `support@valqeron.com` |
| `RESEND_API_KEY` | door Dennis in deze sessie te geven, nooit herhalen of tonen |

## Werkwijze

1. `git status` en `git diff` (drift-check; verwacht `ea889f0` of nieuwer). Meld afwijkingen.
2. **Read-only vooraf:** controleer in de code en in `.env.example` de exacte variabelenamen en hoe het van-adres wordt gebruikt. Controleer op productie (zonder waarden te printen, bijvoorbeeld met `grep -c`) of de drie variabelen al in `/opt/valqeron/.env` staan.
3. **Sleutel vragen aan Dennis** (in de sessie, één keer). Zet hem niet in een bash-commando, niet in een bestand in de repo, en niet in een logregel.
4. **Zet de drie variabelen in de productie-`.env`** via stdin (back-up van `.env` eerst, modus 600, eigenaar `www-data`, back-up daarna verwijderen, nooit printen, niet in git). Herstart de service met de gewone procedure. Controleer `/health` en dat de service draait.
5. **Herstelscript:** draai `scripts/resend_support_notifications.py --dry-run` en rapporteer hoeveel rijen er zijn (verwacht: alleen SR-000001, het eerdere testverzoek). Zijn het er meer dan één, meld dat dan **voordat** je echt draait. Draai daarna echt: dit is de **ene** testmelding aan `support@valqeron.com`. Geen extra testmails.
6. **Dennis bevestigt** dat de mail is aangekomen (hij kijkt in de Strato-webmail van `support@valqeron.com`). Pas daarna werk je CLAUDE.md bij.
7. **CLAUDE.md** (§2, §5, §6, §7): e-mailmelding actief; Resend als sub-verwerker (EU/Ireland) toevoegen aan de lijst voor de DPA; de rij "e-mail nog niet geactiveerd" aanpassen; §7 volgende stap bijwerken. `git status` en `git diff` vooraf en verificatie na de commit.

## Als de classifier het blokkeert

Gisteren blokkeerde de classifier het wegschrijven van een wachtwoord (`Secret-Store Writes`, `Credential Materialization`). Dat kan hier ook gebeuren bij het zetten van de sleutel. **Omzeil het niet.** Stop in dat geval en geef Dennis (in gewoon Nederlands, genummerd, kort) precies de handmatige stappen: inloggen op de server, de drie regels in `/opt/valqeron/.env` zetten zonder de sleutel in de shell-geschiedenis te laten staan (bijvoorbeeld met `read -s`), rechten controleren, de service herstarten, en daarna door jou uit te voeren: de rest van deze hand-off. Test die stappen read-only vooraf voor zover mogelijk (paden, servicenaam, rechten).

## Stopvoorwaarden

Stop en meld als: Resend `403` of een "domain not verified"-fout geeft (dan staat het domein niet goed; niet in een lus herhalen); de sleutel ergens anders dan in `/opt/valqeron/.env` zou moeten komen; het herstelscript meer dan één rij wil versturen; de service na herstart niet gezond is (rol de `.env` terug vanuit de back-up en meld); een extern adres anders dan `support@valqeron.com` zou worden aangeschreven.

## Rapport

1. Drift-check en bevindingen uit stap 2 (variabelenamen, van-adres). 2. Wat er op productie is gewijzigd (alleen namen, geen waarden). 3. Resultaat van `--dry-run` en van de echte run (aantal rijen, `notify_status`, geen berichttekst). 4. Bevestiging van Dennis dat de mail is aangekomen. 5. Commit-hash van de CLAUDE.md-update.
