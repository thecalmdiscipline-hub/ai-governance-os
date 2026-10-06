# Nachtrapport — 2026-10-06 (nacht, zonder toezicht)

Opdracht: "NACHTRUN, geen toezicht. Dennis slaapt. SNAPSHOT=ja" — Batch K (serverhygiëne) uitvoeren,
en alleen als K gezond is doorgaan naar Batch L (klantzicht op onboardingvoortgang + governance-tab),
Deel A dan Deel B. Geen migraties, geen nieuwe organisaties provisionen, geen berichten/e-mail, geen
echte klantacties. Dit document bevat geen geheimen of persoonsgegevens.

**Resultaat in één zin:** Batch K volledig klaar; Batch L Deel A volledig klaar en op productie
geverifieerd; Batch L Deel B niet gestart (geen stopvoorwaarde geraakt — bewuste batchgrens bij het
aflopen van het contextbudget, een uitkomst die de hand-off zelf toestaat).

---

## Batch K — serverhygiëne

Hand-off: `claude-code-handoff-batch-k-serverhygiene.md`.

**K1 — pip-cache structureel gefixt.** `--no-cache-dir` toegevoegd aan alle `pip install`-aanroepen
die daadwerkelijk op de productieserver draaien (`scripts/deploy.sh`, `scripts/setup_server.sh`).
Bewust niet aangeraakt: `.github/workflows/ci.yml` (draait op een ophemere GitHub-runner) en
`scripts/bootstrap_workflows.sh` (dode heredoc-tekst, nooit uitgevoerd). Vóór de fix: pip's eigen
downloadcache op de server was 4,4 GB en groeide bij elke deploy verder. Ná een deploy met de fix:
cache bleef exact gelijk — bewezen dat de groei stopt. Eenmalig de resterende, van-vóór-de-fix cache
opgeruimd (`pip cache purge`): schijf van 20% naar 14% vol.
Commit `6e5a49d`. CI `37517040475` (success), Deploy `37517281973` (success).

**K2 — testaccount afgesloten.** Account id 2 ("ZZ Provisioning Wizard Test", een wegwerp-testaccount
uit een eerdere sessie) via de bestaande API op status `lost` gezet en een duidelijke notitie
toegevoegd ("TESTACCOUNT, niet gebruiken"). Account id 1 (ISO CERT, een echt gebruikt testaccount)
en alle 4 organisaties bleven ongewijzigd. Geen SQL, geen classifier-blokkade.

**K3 — OS-updates + één herstart (uitgevoerd omdat `SNAPSHOT=ja` was bevestigd).** Alle vooraf-checks
groen (schijf 14% vol, alle 4 diensten actief, certificaten geldig, `/health` ok). 33 reguliere
Ubuntu-updates (`apt-get upgrade`, expliciet geen `dist-upgrade`) eerst gesimuleerd (0 te verwijderen,
4 kernel-metapakketten "kept back" — verwacht gedrag van een gewone `upgrade`, geen stopreden), dan
echt geïnstalleerd: geen prompts, geen verwijderingen. Eén herstart om 19:19:12 UTC, SSH terug na 35
seconden. Kernel ging van `6.8.0-139` naar de al-klaarstaande `6.8.0-142`. Na de herstart: alle 4
diensten actief, `/health` 200 met hetzelfde `build_sha`, site extern bereikbaar, de laatste
Deploy-workflow opnieuw gedraaid en geslaagd (bewijst dat de pijplijn na de herstart nog werkt).
Eén benigne, zelf-opgeloste bijzaak: `needrestart` herstartte automatisch Postgres tijdens de
upgrade, wat `/health` heel even "degraded" liet zien — herstelde zichzelf binnen ~10 seconden zonder
enige actie.

**Batch K: volledig klaar, geen openstaande problemen.**

---

## Batch L, Deel A — klantzicht op onboardingvoortgang

Hand-off: `claude-code-handoff-batch-l-klantzicht-voortgang-governance.md`.

Een klant met een lopend onboardingtraject ziet nu op de Home-tab van het portaal een "Onboarding
progress"-kaart: een voortgangsbalk per fase en een checklist van zijn eigen taken, met een checkbox
voor de taken die hij zelf mag afvinken.

**Backend** (`app/api/onboarding.py`, nieuw, los van de bestaande ops-only `/ops/onboarding/*`):
- `GET /onboarding/progress` — alleen de eigen organisatie (uit het token, nooit uit de aanvraag),
  geeft `{"project": null}` zonder gekoppeld account/actief project, anders fasen met voortgang en
  alleen de taken die `customer_visible=True` zijn — nooit een veld uit de interne `ops_accounts`-tabel
  (contactnaam, e-mail, notities, voorgestelde tier, accountstatus).
- `PATCH /onboarding/tasks/{id}` — alleen `status` (ongeldige waarde of extra veld → automatisch 422),
  alleen voor taken die zichtbaar én van de klant (`owner` = customer/both) zijn, **404** (nooit 403)
  voor alles daarbuiten. Elke echte wijziging krijgt een auditregel zonder notitietekst.
- Commit `400601d`. CI `37520013737` (success), Deploy `37520227420` (success).
- Backendtests: 373 → **384** (11 nieuw, eigen geïsoleerde testfixtures per test).

**Portaal** (`ai-governance-frontend`):
- Nieuwe kaart `src/components/OnboardingProgressCard.tsx` op de Home-tab; rendert niets zonder actief
  project. Optimistische checkbox-update met terugrollen + foutmelding bij een mislukte save.
- `src/services/onboardingProgress.ts` (typed client) + een nieuwe generieke `apiPatch`-helper in
  `src/lib/api.ts`.
- Commit `5edf5ee`. CI `37520453084` (success), Deploy `37520542503` (success, `DEPLOY CHECK OK`).
- README bijgewerkt, commit `5593b3b`. CI `37521528824`/Deploy beide succes.
- Portaaltests: 122 → **128** (6 nieuw).

**Productiecheck** (server-side gemunte tokens voor een testaccount en een bestaande demo-klant, nooit
geprint, bestanden na gebruik direct verwijderd):
- Het echte onboardingproject van het testaccount gaf precies de verwachte 14 klant-zichtbare taken
  terug, met de juiste 4 taken als "niet van jou" gemarkeerd.
- Een organisatie zonder gekoppeld account gaf correct `{"project": null}`.
- Een headless-browsercheck op de echte, live Home-pagina bevestigde: de kaart rendert met de juiste
  fasen/taken, nul CSP-violations, nul gefaalde requests, en een scan over de volledige paginatekst
  vond geen van de interne velden die nooit mogen lekken.

**CLAUDE.md bijgewerkt** (secties 2, 5, 6, 7) met het volledige verhaal van Batch K en Batch L Deel A,
na `git status`/`git diff` in beide repo's. Commit `30194b8`.

---

## Batch L, Deel B — niet gestart

Geen enkele stopvoorwaarde uit de hand-off is geraakt (geen migratie nodig gebleken, geen
classifier-blokkade, geen rode test, geen twee opeenvolgende mislukte Deploys). De keuze om hier te
stoppen is een bewuste batchgrens bij het aflopen van het beschikbare contextbudget voor deze sessie —
de hand-off staat dit zelf expliciet toe: "Is Deel A klaar maar Deel B blokkeert: lever Deel A volledig
af en meld Deel B."

**Wat al wél bekeken is (Fase 0, alleen lezen) en meegegeven wordt aan de volgende sessie:**
- Er bestaat nog geen enkel klant-leesbaar lijst-endpoint voor de governance-objecten (policy,
  AI-systemen, risico's, incidenten, evidence) — alleen ops-only routes en een aggregaat-snapshot die
  niet als lijstbron te gebruiken is.
- `PUT /corrective-actions/{id}/status` bestaat al, is correct op de eigen organisatie geschaald, maar
  geeft bij een ongeldige status een `400` (niet de `422` die een eerste lezing van de hand-off deed
  vermoeden) en roept nog geen audit-log-functie aan — dat moet Deel B zelf toevoegen.
- De tekstcorrectie uit de hand-off (één overclaim in een provisioning-sjabloontekst,
  `app/core/provisioning_defaults.py`'s `monitoring_commitment`) is nog **niet** doorgevoerd — raakt
  alleen toekomstige provisioning, geen bestaande rij.

Deze bevindingen staan ook als nieuwe risicorij in CLAUDE.md sectie 5, zodat ze niet verloren gaan.

---

## Samenvatting commits/runs

| Commit | Repo | Omschrijving | CI | Deploy |
|---|---|---|---|---|
| `6e5a49d` | ai-governance-os | K1: `--no-cache-dir` op elke server-side pip install | `37517040475` success | `37517281973` success |
| `50b10c2` | ai-governance-os | CLAUDE.md: Batch K | `37518908709` success | `37519132969` success |
| `400601d` | ai-governance-os | Batch L Deel A backend: `/onboarding/progress`, `/onboarding/tasks/{id}` | `37520013737` success | `37520227420` success |
| `30194b8` | ai-governance-os | CLAUDE.md: Batch L Deel A + Deel B Fase-0-bevindingen | `37521837829` success | `37522112418` success |
| `5edf5ee` | ai-governance-frontend | Batch L Deel A portaal: onboarding-progress-kaart op Home | `37520453084` success | `37520542503` success |
| `5593b3b` | ai-governance-frontend | README: onboarding-progress-kaart documenteren | `37521528824` success | `37521606481` success |

**Testaantallen:** backend 373 → 384 (+11); portaal 122 → 128 (+6).

Geen migraties uitgevoerd. Geen nieuwe organisaties geprovisioned. Geen berichten of e-mail verstuurd.
Geen echte klantactie uitgevoerd — alleen lezen + schrijven binnen het bestaande, al-aanwezige
testaccount id 2 (status/notitie, via de bestaande API) en read-only productiechecks met server-side
gemunte, nooit-opgeslagen tokens.
