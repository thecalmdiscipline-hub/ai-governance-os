# Hand-off Batch R — technische schuld: CI op Python 3.12, rate limiting `/ops`, certificaatcheck (alleen lezen)

Auteur: Cowork (architect). Uitvoerder: Claude Code, **één sessie**. Datum: 7 okt 2026. Kan **zonder toezicht**: lees de stopregels. Repo's: `ai-governance-os` (alles hier) en, alleen als de CI het vraagt, `ai-governance-frontend`. Vervolg op Batch O en H (KLAAR).

## Waarom

Drie kleine openstaande punten uit het executieplan en de gereedheidslijst (A8): (1) de CI draait op een andere Python-versie dan productie (productie 3.12; CI volgens CLAUDE.md §5 nog 3.10), zodat een fout die alleen op 3.12 optreedt in CI onzichtbaar blijft; (2) de `/ops/*`-routes (super-admin) hebben geen eigen snelheidsbegrenzing; (3) het TLS-certificaat verloopt op **2026-11-20** en niemand controleert dat automatisch.

## Vooraf besloten (niet opnieuw voorleggen)

- **Geen serverwijzigingen.** Alleen de repo en alleen-lezen controles van buitenaf. Geen SSH-actie, geen wijziging aan nginx, certbot of systemd. Het certificaat zelf vernieuwen is niet van dit batch.
- **Geen migraties.** Geen wijziging aan auth, MFA, provisioning-logica of datamodel. Rate limiting mag geen bestaand gedrag veranderen buiten het begrenzen van `/ops/*`.
- **Gelijk trekken met productie:** CI-runner op Python **3.12** (de exacte patchversie die productie gebruikt; lees die uit CLAUDE.md of de deploy-config; bij twijfel `3.12`). Alle tests moeten onder 3.12 groen zijn. Wijkt een test af door een versieverschil: repareer de **test of de code** zonder gedrag te veranderen, en meld het.
- **Rate limiting `/ops/*`:** hergebruik de bestaande rate-limit-infrastructuur van het project (lees in Fase 0 hoe `rate_limit` nu werkt en welke routes het al gebruiken); geen nieuwe dependency. Kies een ruime grens die normaal beheer niet hindert (bijvoorbeeld 60 aanvragen per minuut per ingelogde super-admin, te onderbouwen in het rapport) met een duidelijke `429`-reactie. Login- en MFA-routes blijven hun bestaande, strengere limieten houden. Meld de gekozen waarden.
- **Certificaatcheck:** een klein script `scripts/check_cert_expiry.py` dat voor `api.valqeron.com`, `app.valqeron.com` en `compliance.valqeron.com` via een gewone TLS-handshake de einddatum van het certificaat leest en het aantal dagen overhoudt toont; exitcode ≠ 0 bij minder dan 21 dagen. Geen schrijfacties, geen geheimen. Een test met een gemockte handshake. Documenteer in CLAUDE.md (§2/§5) hoe en wanneer het draait; Cowork neemt het in de maandelijkse controle op. Geen geplande CI-taak toevoegen zonder dat dit in de Fase 0 als eenvoudig en veilig blijkt; meld het dan als voorstel.

## Werkwijze

0. **Hervatten:** lees eerst het HERVAT-BLOK in `CLAUDE.md` en `WERKLIJST.md`; ga door bij de eerste onvoltooide stap. Elke stap is veilig opnieuw te draaien.
1. `git pull`, `git status`, `git diff` (drift-check; verwacht backend `9ef6634` of nieuwer). Meld afwijkingen.
2. **Fase 0 (alleen lezen), eerste alinea van je rapport:** welke Python-versie CI nu gebruikt en welke productie; waar in de workflow dat staat; welke rate-limit-helper er is en waar hij nu wordt gebruikt; welke `/ops/*`-routes bestaan; wat CLAUDE.md zegt over het certificaat en de domeinen. Wijkt iets af van dit document: stoppen en melden.
3. Kleine losse commits (R1 CI, R2 rate limiting, R3 certificaatcheck); na elke push CI en Deploy controleren (`DEPLOY CHECK OK`).

## Bouw en tests

- **R1 CI 3.12:** workflow aanpassen; alle tests groen (`pytest -q -m "not codex"`, nu 462 + O4-tests). Meld afwijkende tests.
- **R2 rate limiting:** tests voor onder de grens (`200`), over de grens (`429`), isolatie tussen twee super-admins, en dat de bestaande login/MFA-limieten ongewijzigd werken. Geen tekst of token in logs of Sentry.
- **R3 certificaatcheck:** test met gemockte handshake (genoeg dagen, bijna verlopen, handshake mislukt = foutcode). Draai het script **één keer echt** tegen de drie domeinen en noem alleen domeinnaam en resterende dagen in het rapport.
- Lint `--max-warnings=0` waar van toepassing.

## Productiecontrole

Alleen lezen. Na de Deploy: `DEPLOY CHECK OK`; `/health` en een gewone inlog van een testgebruiker werken (server-side token in geheugen, niet printen); een `/ops/*`-route met normaal gebruik geeft `200`; `/audit/verify` `valid` voor alle vijf organisaties. Een bewuste burst tegen een **ongevaarlijke, alleen-lezen** `/ops/*`-route om de `429` te bevestigen mag, met pacing daarna; geen schrijf-routes testen op productie.

## Stopvoorwaarden

Stop en meld als: een serverwijziging nodig lijkt; een migratie nodig lijkt; auth, MFA of provisioning geraakt wordt; de limiet normaal super-admin-gebruik zou blokkeren; tests onder 3.12 rood blijven na een redelijke reparatie van de test; een Deploy twee keer achter elkaar faalt; de classifier iets blokkeert (niet omzeilen); de schijf boven 80%. Bij een **gebruikslimiet**: werk het HERVAT-BLOK bij (welke R-stap, welke commits), commit, push en stop netjes; Dennis typt later "continue".

## Rapport

Fase 0-bevindingen; commits (hash en doel), CI-/Deploy-run-id's; testaantallen vóór en na; gekozen limieten met onderbouwing; resultaat van de certificaatcheck per domein (dagen resterend); productiecontrole per stap; beslissingen die je zelf nam; CLAUDE.md (§2, §5, §6, §7) bijgewerkt met commit-hash; HERVAT-BLOK en `WERKLIJST.md` (status `KLAAR`) bijgewerkt.
