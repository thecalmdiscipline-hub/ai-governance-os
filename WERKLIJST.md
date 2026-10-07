# WERKLIJST — geordende opdrachten voor Claude Code

Bijgehouden door Cowork (architect). Claude Code **leest** dit bestand en werkt alleen de kolom *Status* en het HERVAT-BLOK in `CLAUDE.md` bij. Laatste wijziging: 7 okt 2026.

## De vaste opdracht (Dennis plakt dit; na een stop typt hij alleen "continue")

> Lees `WERKLIJST.md` en het HERVAT-BLOK in `CLAUDE.md`. Commit eerst alle nieuwe hand-offs en `WERKLIJST.md` zelf als ze er nog niet in zitten. Voer de eerste regel met status `OPEN` uit waarvan de voorwaarde klaar is, daarna de volgende, volgens de stopregels in elke hand-off. Werk na elke stap het HERVAT-BLOK bij. Bij een gebruikslimiet of onverwachte stop: werk het HERVAT-BLOK bij, commit, push en stop netjes. Sla `WACHT OP DENNIS` en `WACHT OP COWORK` over. Schrijf aan het eind `NACHTRAPPORT.md`.

## Regels

1. **Eén sessie tegelijk.** Pak altijd de eerste regel met `OPEN` waarvan de voorwaarde op `KLAAR` staat.
2. Een regel met `WACHT OP DENNIS` of `WACHT OP COWORK` sla je over en noem je in het rapport. Zet zelf nooit een regel op `OPEN`.
3. Harde stopregels staan in elke hand-off. Daarboven altijd: geen migraties tenzij de hand-off ze expliciet toestaat, geen geheimen in bestanden of chat, classifier-blokkades niet omzeilen, niets versturen naar derden, bij twee mislukte Deploys stoppen, schijf boven 80% stoppen.
4. Elke stap moet veilig opnieuw te draaien zijn. Na een stop begin je bij de eerste onvoltooide stap uit het HERVAT-BLOK, niet opnieuw bij het begin.
5. Een stop door een gebruikslimiet is geen fout: werk het HERVAT-BLOK bij en stop. Cowork controleert elke 3 uur en meldt het aan Dennis.

## Opdrachten (volgorde = uitvoeringsvolgorde)

| # | Opdracht | Hand-off | Status | Voorwaarde |
|---|---|---|---|---|
| 1 | Batch O3: risico's aanmaken en bijwerken (geen migratie) | `claude-code-handoff-batch-o3-risicos.md` | KLAAR | O1 klaar (is KLAAR) |
| 2 | Batch H (A3): fictieve demotenant "Atlas Demo B.V.", alle 10 workflows, doorlooptijdmeting | `claude-code-handoff-batch-h-demotenant-meting.md` | KLAAR | H1 klaar. Dennis heeft het wachtwoord van `atlas_demo_admin` gewijzigd (7 okt 2026); hervat bij H2 volgens het HERVAT-BLOK, na afronding van een lopende O2-stap |
| 3 | Batch O2: corrigerende maatregelen aanmaken, **met migratie** (owner, due_date, ai_incident_id) | `claude-code-handoff-batch-o2-corrigerende-maatregelen.md` | KLAAR | Regel 1 KLAAR. Dennis' akkoord op de migratie is gegeven (7 okt 2026) |
| 4 | Batch O4 (A2): evidence aanmaken in de Governance-tab (metadata, geen bestandsupload) | `claude-code-handoff-batch-o4-evidence.md` | OPEN | Regel 3 KLAAR (is KLAAR) |
| 5 | Batch M (A4): handout-generator NL/EN | nog te schrijven door Cowork | WACHT OP COWORK | Regel 2 KLAAR; Dennis' invulpunten (contact, HR-module, goudtint) |
| 6 | Batch Q (A5): maandrapportage | nog te schrijven door Cowork | WACHT OP COWORK | Regel 5 KLAAR |
| 7 | Batch P: back-up, herstelproef, schijf- en uptimebewaking | `claude-code-handoff-batch-p-backup-herstelproef-bewaking.md` | WACHT OP DENNIS | Dennis levert de vier punten bovenaan de hand-off |
| 8 | A6: ISO CERT-video en handout opnieuw (alleen bestaande workflows plus roadmapscène) | nog te schrijven door Cowork | WACHT OP COWORK | Capaciteitscheck door Cowork |
| 9 | Batch R (A8): CI naar Python 3.12, rate limiting `/ops`, certificaatcheck (alleen lezen) | nog te schrijven door Cowork | WACHT OP COWORK | Regel 2 KLAAR |
| 10 | Serverhardening (SSH, fail2ban, kernel-update en één herstart) | nog te schrijven door Cowork | WACHT OP DENNIS | Snapshot en `SNAPSHOT=ja` van Dennis, overdag |

## HERVAT-BLOK (sjabloon; Claude Code voegt dit toe aan `CLAUDE.md`, bovenaan sectie 7, en houdt het actueel)

```
## HERVAT-BLOK (laatst bijgewerkt: JJJJ-MM-DD UU:MM UTC)
- Huidige opdracht: <regel uit WERKLIJST.md, bijv. "2 — Batch H">
- Laatst afgeronde stap: <bijv. "H1 provisioning klaar, org 5 bestaat">
- Volgende stap: <bijv. "H2 scenario 4 van 10, run-id's 1-3 staan in de notitie">
- Laatste commit (beide repo's): <hash> / <hash>
- Niet aanraken / let op: <bijv. "wachtwoordbestand niet verplaatsen; testincident org 1 laten staan">
- Reden stop: <gebruikslimiet / stopregel / klaar>
```
