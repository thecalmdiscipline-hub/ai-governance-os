# Hand-off Batch L — Fase 3.1 onboarding-voortgang voor de klant, 3.2 governance-tab voor de klant

Auteur: Cowork (architect). Uitvoerder: Claude Code, **één sessie**. Datum: 6 okt 2026 (avond). Kan **zonder toezicht** worden uitgevoerd: lees de stopregels.
Repo's: `ai-governance-os` (backend) en `ai-governance-frontend` (portaal). Taak-ID's 3.1 en 3.2 uit `claude/dogfood-portal-onboarding-plan.md`.

## Doel

1. **3.1** Een klant ziet op Home een kaart "Onboarding-voortgang" met de voortgang per fase en de taken die voor de klant bedoeld zijn, en kan zijn **eigen** taken afvinken.
2. **3.2** Een klant ziet een tab "Governance" met zijn eigen beleid, AI-systemen, risico's, incidenten, corrigerende maatregelen en evidence (lezen), en kan de **status van een corrigerende maatregel** bijwerken. Dit maakt de belofte "corrective-action tracking" waar.

## Vooraf besloten (niet opnieuw voorleggen)

- **Eigen organisatie, altijd.** Elk nieuw klantendpoint leest alleen rijen van de organisatie van de ingelogde gebruiker (`organization_id` uit het token, nooit uit de aanroep). Een andere organisatie geeft `404` (niet `403`), zodat het bestaan niet lekt. Klantcode importeert nooit uit de ops-code of leest `/ops/*`.
- **D4/D5 uit het ontwerp:** de klant krijgt uit tenant 0 alleen wat hieronder staat, via een server-side servicefunctie. Nooit: accountgegevens (contactnaam, e-mail, notities, bron, voorgestelde tier, status), interne taaknotities, metrics, andere taken dan de klantzichtbare, of id's van andere organisaties.
- **Geen migraties.** Dit batch gebruikt alleen bestaande tabellen en kolommen. Lijkt een migratie nodig: stop en meld.
- Alleen **additieve** backendwijzigingen; bestaand gedrag, auth, MFA, provisioning en de ops-code blijven ongewijzigd. Geen nieuwe zware dependencies; hergebruik het bestaande ontwerp en de tabstructuur (geen router).
- Klantcode komt in de gewone bundel; de ops-code blijft lazy en onaangeroerd.
- Alle klantgegevens blijven uit `localStorage`, `console` en Sentry.

## Werkwijze

1. In beide repo's `git status` en `git diff` (drift-check; verwacht `72135ea` backend of nieuwer, en het laatste frontendcommit van Batch I2). Meld afwijkingen.
2. **Fase 0 (alleen lezen), eerste alinea van je rapport:**
   - Onboarding: de echte velden van `onboarding_tasks` (eigenaar, klantzichtbaar, status, tekstvelden), hoe een project aan een organisatie hangt (via `ops_accounts.organization_id`), en een **lijst van de taken met `customer_visible = true` in `standard-v1`** (titel en eigenaar).
   - Governance: de bestaande endpoints in `app/api/governance.py` en elders voor policy, AI-systemen, risico's, incidenten, corrigerende maatregelen en evidence; welke `GET`-lijsten bestaan en welke niet (het plan zegt: incident-endpoints bestaan niet), met welke rol, en hoe de tenant-scoping werkt (`AIRisk` hangt aan een `AISystem`); de statuswaarden van `CorrectiveAction` en de bestaande `PUT /corrective-actions/{id}/status` (en de CORS-`PUT` uit commit `64bf1ac`).
   - Portaal: hoe tabs en rollen werken, welke tabs een gewone klantadmin ziet, hoe een nieuwe tab zich verhoudt tot de modulepoort (`core`).
   - Wijkt iets af van dit document: stoppen en melden.
3. Kleine losse commits; na elke push CI en Deploy controleren (GitHub Actions-API, `DEPLOY CHECK OK`), plus een echte functionele check op productie (hieronder).

## Deel A — 3.1 Onboarding-voortgang

**Backend (nieuw, buiten `/ops`):**
- `GET /onboarding/progress`: vindt via de organisatie van de gebruiker het gekoppelde account en het actieve of gepauzeerde project. Geen koppeling of geen project: `200` met `{"project": null}`. Anders: per fase (nummer, titel) het aantal klantzichtbare taken en hoeveel `done` of `skipped`, plus de lijst klantzichtbare taken: `id`, `phase`, `title`, `status`, `owner` (alleen een label). Geen notities.
- `PATCH /onboarding/tasks/{id}`: alleen als de taak in het project van de eigen organisatie zit, klantzichtbaar is en eigenaar `klant` of `beide` heeft. Body: alleen `status` met `todo`, `doing` of `done` (geen `skipped`/`blocked`, geen notitie, `extra="forbid"`). Alles anders: `404`. Volg het bestaande rollenmodel (schrijven alleen met de rol die ook elders governance-gegevens mag wijzigen, meld wat je koos). Auditregel voor de organisatie van de klant via de bestaande auditfunctie, zonder tekstvelden; de keten blijft `valid`.

**Portaal:** kaart op Home met voortgangsbalken per fase en de takenlijst, afvinken met terugdraaien bij een fout, geen kaart als `project` null is, nette melding bij `404`/netwerkfout. Geen weergave van iets wat de backend niet teruggeeft.

**Tests:** isolatie (organisatie A ziet nooit project of taken van B, `PATCH` op andermans taak geeft `404`); alleen klantzichtbare taken in het antwoord; geen interne notitie, contactgegevens of accountstatus in het antwoord (assert op de volledige JSON); `PATCH` weigert `skipped`, `blocked`, extra velden, taken met eigenaar Valqeron en niet-klantzichtbare taken; auditregel zonder tekst; `/audit/verify` `valid`; frontend: kaart wel/niet, afvinken, terugdraaien, geen klantgegevens in `localStorage`/console/Sentry.

## Deel B — 3.2 Governance-tab

**Backend (alleen als de Fase 0-tabel gaten toont):** voeg ontbrekende **tenant-gescopede `GET`-lijsten** toe (verwacht: incidenten, evidence; controleer de rest). Alleen lezen. Geen endpoints om risico's, incidenten of evidence aan te maken of te wijzigen in dit batch. Voor corrigerende maatregelen gebruik je het bestaande `PUT /corrective-actions/{id}/status`; controleer dat het tenant-scoped is en alleen geldige statussen accepteert, en corrigeer alleen als dat aantoonbaar ontbreekt (meld het).

**Portaal:** nieuwe tab "Governance" met secties Beleid, AI-systemen, Risico's (niveau als label), Incidenten, Corrigerende maatregelen (statuswissel met terugdraaien bij fout), Evidence (lijst). Lege toestanden netjes ("Nog niets geregistreerd"). Toon beleidstekst letterlijk zoals opgeslagen (de sjablooncursieven beginnen met "Standard template, to be reviewed by the client."). **Schrijf op deze tab geen beloften die het product niet waarmaakt**: geen "continu bewaakt", geen "automatisch".

**Tekstcorrectie sjabloon:** in `app/core/provisioning_defaults.py` staat bij `monitoring_commitment` "AI systems are monitored continuously; incidents are recorded and followed up." Dat is een overclaim. Vervang door: "AI systems are reviewed on a regular basis by the organisation; incidents are recorded and followed up." Pas alleen het sjabloon aan (geldt voor nieuwe tenants); wijzig **geen bestaande rijen**. Pas de tests aan. Meld in het rapport welke bestaande organisaties de oude tekst nog hebben (alleen organisatie-id's).

**Tests:** isolatie per lijst (organisatie B ziet niets van A); statuswissel alleen binnen de eigen organisatie, ongeldige status geeft `422`; frontend: tab, lege toestanden, statuswissel met terugdraaien; geen klantgegevens in `localStorage`/console/Sentry; bestaande tests blijven groen (`pytest -q -m "not codex"` en `npm test`, lint met `--max-warnings=0`).

## Productiecheck (alleen lezen, server-side gemunt token voor `isocert_demo_admin` in geheugen, niet printen, wachtwoord niet resetten of aanraken; als dat niet kan zonder reset: sla over, meld het, tests blijven de dekking)

- `GET /onboarding/progress` voor org 4: project aanwezig, alleen klantzichtbare taken, geen notities.
- Governance-lijsten voor org 4: 200, alleen eigen rijen.
- `customer2_admin` (org 2) krijgt voor `/onboarding/progress` `{"project": null}` en kan org 4 niet zien; `PATCH` op een taak van org 4 geeft `404`.
- **Schrijf niets op productie** in deze check (geen taak afvinken, geen status wijzigen).
- Headless browser: de kaart op Home en de Governance-tab renderen zonder CSP-fouten; geen screenshot met klantgegevens bewaren.

## Stopvoorwaarden

Stop en meld als: een migratie nodig lijkt; een wijziging auth, MFA, provisioning of de ops-code zou raken; er een aanroep is waarbij `organization_id` uit de aanroep zou komen; klantgegevens of interne notities in een antwoord, `localStorage`, log of Sentry-event zouden komen; de bundel van klanten ops-code zou bevatten; tests rood worden; een Deploy twee keer achter elkaar faalt (de pijplijn draait zelf terug, meld het); de classifier iets blokkeert (niet omzeilen); de schijf boven 80% komt. Is Deel A klaar maar Deel B blokkeert: lever Deel A volledig af en meld Deel B.

## Rapport

Fase 0-bevindingen en afwijkingen (incl. de lijst klantzichtbare taken met titels); commits per repo (hash en doel), CI- en Deploy-run-id's; nieuwe endpoints en schermen; testaantallen vóór en na; productiecheck per stap (verwacht, gezien, geen geheimen of persoonsgegevens); beslissingen die je zelf hebt genomen; welke organisaties de oude `monitoring_commitment` nog hebben; CLAUDE.md (§2, §5, §6, §7) en README bijgewerkt met commit-hash.
