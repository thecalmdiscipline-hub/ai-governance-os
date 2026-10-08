# Handout-inhoud (bron voor Batch M, NL en EN)

Status: bronteksten van Cowork, bijgewerkt 8 okt 2026 na Batch O (incidenten, risico's, corrigerende maatregelen en bewijsstukken kunnen nu worden aangemaakt) en Batch H (demotenant "Atlas Demo B.V."). Dit bestand bevat **voorstellen**; Dennis leest de eerste vijf handouts volledig vóór verzending. Claude Code zet deze teksten om in `handout/shared.yaml`, `handout/modules.yaml` en `handout/claims.yaml` (NL en EN onder dezelfde sleutel) en **wijzigt de betekenis niet**. Klopt een feit niet met de code of met `CLAUDE.md`: niet afzwakken of verzinnen, maar melden (stopvoorwaarde).

Aannames: het portaal is Engelstalig en de NL-handout zegt dat. Welke workflows een startformulier hebben, stelt Claude Code in Fase 0 vast uit de code (vlag `has_start_form` per module).

---

## 1. Gedeelde delen (sleutels voor `shared.yaml`)

### 1.1 `welcome`
**NL:** Welkom bij Valqeron. Deze handout hoort bij jullie omgeving en beschrijft alleen de onderdelen die voor jullie zijn ingericht. Valqeron helpt jullie AI gecontroleerd te gebruiken: AI doet een voorstel, een medewerker beoordeelt het resultaat voordat het wordt gebruikt. Het portaal is in het Engels; de schermafbeeldingen in deze handout tonen de Engelstalige interface.
**EN:** Welcome to Valqeron. This handout belongs to your environment and covers only the parts set up for you. Valqeron helps you use AI in a controlled way: the AI produces a proposal, and a team member reviews the result before it is used. The portal is in English, and the screenshots in this handout show the English interface.

### 1.2 `login`
**NL:** Je beheerder maakt je account aan en geeft je een eenmalig wachtwoord via een apart kanaal. Ga naar app.valqeron.com, vul je gebruikersnaam en wachtwoord in en kies bij de eerste keer een nieuw wachtwoord van minstens 12 tekens. Zonder nieuw wachtwoord kun je niets anders openen.
**EN:** Your administrator creates your account and gives you a one-time password through a separate channel. Go to app.valqeron.com, enter your username and password, and on first login choose a new password of at least 12 characters. Until you do, nothing else can be opened.

### 1.3 `change_password`
**NL:** Wachtwoord wijzigen kan altijd via de tab Account, onder "Password". Kies een wachtwoord dat je nergens anders gebruikt.
**EN:** You can change your password at any time on the Account tab, under "Password". Choose a password you do not use anywhere else.

### 1.4 `mfa`
**NL:** Tweestapsverificatie is optioneel en aan te raden. Je zet het aan op de tab Account ("Two-step verification") met een authenticator-app. Bij het aanzetten krijg je 10 eenmalige back-upcodes: bewaar ze offline. Na vijf foute codes is de tweede stap 15 minuten geblokkeerd.
**EN:** Two-step verification is optional and recommended. You turn it on in the Account tab ("Two-step verification") using an authenticator app. When you turn it on you receive 10 one-time backup codes: keep them offline. After five wrong codes, the second step is blocked for 15 minutes.

### 1.5 `tabs`
| Tab | NL | EN |
|---|---|---|
| Home | Overzicht van je omgeving, recente runs en, zolang jullie onboarding loopt, de kaart "Onboarding progress". | Overview of your environment, recent runs and, while your onboarding is in progress, the "Onboarding progress" card. |
| Core | Informatie over Valqeron Core, de besturingslaag onder alle workflows. | Information about Valqeron Core, the control layer under all workflows. |
| Products | De workflows die voor jullie zijn ingericht. | The workflows set up for you. |
| Results | Alle resultaten van gedraaide workflows, met details per run. | All results of workflows that have run, with details per run. |
| Documents | Documenten uploaden en vragen stellen over je eigen documenten (als de module Document Intelligence actief is). | Upload documents and ask questions about your own documents (if the Document Intelligence module is active). |
| Governance | Overzicht van het AI-beleid, AI-systemen, risico's, incidenten, corrigerende maatregelen en bewijsstukken van je organisatie. Je kunt incidenten, risico's, corrigerende maatregelen en bewijsstukken aanmaken en bijwerken, en de status van een corrigerende maatregel wijzigen. Bewijsstukken zijn beschrijvingen van waar iets bewaard wordt, geen bestanden. | Overview of your organisation's AI policy, AI systems, risks, incidents, corrective actions and evidence. You can create and update incidents, risks, corrective actions and evidence items, and change the status of a corrective action. Evidence items describe where something is kept; they are not files. |
| Account | Wachtwoord, tweestapsverificatie en het indienen van een supportverzoek. | Password, two-step verification and submitting a support request. |

*Voor Claude Code:* controleer in Fase 0 per Governance-onderdeel in de code wat een klant echt kan (aanmaken, bijwerken, status wijzigen). Staat er iets in deze tabel dat de code niet kan, pas de zin aan de code aan en meld het in het rapport. Verwijderen kan niet.

### 1.6 `progress_card`
**NL:** Zolang jullie onboarding loopt, toont de Home-tab een kaart met de voortgang per fase. Je ziet alleen de taken die voor jullie relevant zijn en kunt de taken afvinken die jullie zelf uitvoeren. Taken van Valqeron zie je, maar je kunt ze niet aanpassen.
**EN:** While your onboarding is in progress, the Home tab shows a card with progress per phase. You only see the tasks that are relevant to you and can tick off the tasks you perform yourself. Valqeron's tasks are visible, but you cannot change them.

### 1.7 `support`
**NL:** Hulp nodig of een wijziging aanvragen? Gebruik op de tab Account het formulier "Request support or expansion": kies een categorie (Question, Problem, Access request, Other), een onderwerp (maximaal 200 tekens) en je bericht (maximaal 5000 tekens). Je krijgt een referentienummer (SR-nummer) en ziet je verzoeken onder "My requests". Je kunt maximaal 5 verzoeken per uur en 20 per dag indienen. Zet geen persoonsgegevens of wachtwoorden in een verzoek.
**EN:** Need help or want to request a change? On the Account tab, use the "Request support or expansion" form: choose a category (Question, Problem, Access request, Other), a subject (up to 200 characters) and your message (up to 5000 characters). You receive a reference number (SR number) and see your requests under "My requests". You can submit up to 5 requests per hour and 20 per day. Do not put personal data or passwords in a request.

### 1.8 `expect`
**NL:** Wat je van Valqeron mag verwachten: je gegevens zijn gescheiden van die van andere klanten; acties in jouw omgeving worden vastgelegd in een auditlog dat achteraf op wijzigingen is te controleren; persoonsgegevens in de tekst die je invoert worden herkend en vervangen door plaatshouders voordat de tekst naar het taalmodel gaat, en daarna in het resultaat teruggezet. **Wat dit niet is:** de herkenning is niet perfect, dus voer geen gegevens in die je niet aan een taalmodel wilt toevertrouwen; resultaten zijn voorstellen van een taalmodel en kunnen fouten bevatten; jullie beoordelen elk resultaat voordat je het gebruikt.
**EN:** What you can expect from Valqeron: your data is separated from other customers' data; actions in your environment are recorded in an audit log whose integrity can be verified afterwards; personal data in the text you enter is detected and replaced by placeholders before the text goes to the language model, and restored in the result afterwards. **What this is not:** detection is not perfect, so do not enter data you do not want to entrust to a language model; results are proposals from a language model and may contain errors; you review every result before you use it.

### 1.9 `contact`
Waarden komen **uit een apart bestand `contact.json`** dat Dennis aanlevert (niet uit de tekst). Velden: `urgent_phone`, `urgent_hours`, `security_contact`.
**NL:** Wie bel je? Eerste lijn is een supportverzoek via het portaal. Voor spoed: {urgent_phone}, {urgent_hours}. Beveiligings- of privacymelding: {security_contact}.
**EN:** Who do you call? First line is a support request through the portal. For urgent matters: {urgent_phone}, {urgent_hours}. For a security or privacy report: {security_contact}.
Ontbreekt `contact.json` of een veld: de generator maakt alleen een **concept** met een duidelijke markering "CONCEPT, contactgegevens ontbreken" op elke pagina en weigert een definitieve uitvoer.

### 1.10 `limits` (verplicht, eerlijk)
**NL:** Wat nog niet kan: voor een deel van de workflows is in het portaal nog geen startformulier; die worden op aanvraag voor je ingericht (zie het blok per module). Het portaal heeft geen ingebouwde goedkeuringsstap: de beoordeling van een resultaat spreken jullie intern af. Bestanden uploaden als bewijsstuk kan nog niet. Het portaal is Engelstalig.
**EN:** What is not possible yet: for some workflows the portal does not yet have a start form; these are set up for you on request (see the block per module). The portal has no built-in approval step: you agree internally how a result is reviewed. Uploading files as evidence is not possible yet. The portal is in English.

---

## 2. Modules (10 blokken; sleutel = `module_key`)

Per module vijf kopjes: *Wat het doet*, *Wat je ziet*, *Wat je zelf doet*, *Wat een mens controleert*, *Wat nog niet kan*. Het kopje "Wat nog niet kan" bevat bij `has_start_form=false` de zin: **NL** "Voor deze workflow is in het portaal nog geen startformulier; Valqeron richt het gebruik op aanvraag voor je in." **EN** "This workflow does not have a start form in the portal yet; Valqeron sets up its use for you on request." Bij `has_start_form=true` valt die zin weg. Alle modules: "Er is geen ingebouwde goedkeuringsstap." / "There is no built-in approval step." Vul ontbrekende kopjes aan uit `CLAUDE.md` §3 en de uitvoervelden (Batch J-tabel); verzin niets.

1. `sales_qualification_ai` — Sales Lead Qualification. **Doet:** beoordeelt een binnengekomen lead aan de hand van de gegevens die je invoert en geeft een score van 0 tot 100, een kwalificatie, sterke en zwakke punten en voorgestelde vervolgacties. / assesses an incoming lead from the details you enter and returns a score from 0 to 100, a qualification, strengths and weaknesses, and suggested next actions. **Zie:** score, kwalificatie, samenvatting, sterke/zwakke punten, vervolgacties. **Jij:** vul de leadgegevens in; kopieer de vervolgacties naar je eigen CRM. **Mens:** een verkoper beoordeelt de score en de onderbouwing; de score is een hulpmiddel, geen besluit. / a salesperson reviews the score and rationale; the score is an aid, not a decision.
2. `document_intelligence` — Document Knowledge. **Doet:** beantwoordt vragen over documenten die je eigen organisatie heeft geüpload. / answers questions about documents your own organisation has uploaded. **Zie:** antwoord met samenvatting en redenering, een betrouwbaarheidsniveau en de gebruikte bronnen met fragmenten uit je eigen documenten. **Jij:** upload documenten op de tab Documents en stel een vraag. **Mens:** controleer het antwoord altijd tegen de getoonde bronfragmenten. **Let op:** elke medewerker van jullie organisatie kan de geüploade documenten via deze module raadplegen. / every member of your organisation can consult the uploaded documents through this module.
3. `invoice_processing_ai` — Invoice Processing. **Doet:** haalt gegevens uit factuurtekst (leverancier, nummer, datum, regels, bedragen, btw) en meldt afwijkingen. / extracts data from invoice text (vendor, number, date, lines, amounts, VAT) and reports anomalies. **Zie:** gestructureerde factuurvelden, totalen, aantal regels, samenvatting en afwijkingen. **Jij:** plak de factuurtekst in. **Mens:** een medewerker controleert de bedragen en gegevens tegen de originele factuur vóór boeking.
4. `compliance_monitor` — Compliance Monitoring. **Doet:** vergelijkt beleidstekst die je invoert met een gekozen kader en controlegebied en geeft bevindingen, aanbevelingen, een score en een risiconiveau. **Dit is geen continue bewaking en geen certificering**: het is een analyse van de tekst die je op dat moment invoert. / compares policy text you enter against a chosen framework and control area and returns findings, recommendations, a score and a risk level. **This is not continuous monitoring and not certification**: it is an analysis of the text you enter at that moment. **Zie:** score, risiconiveau, bevindingen met verwijzing naar het kader, aanbevelingen. **Jij:** kies kader en controlegebied, plak de beleidstekst, vul bekende bevindingen in. **Mens:** een compliance-verantwoordelijke beoordeelt elke bevinding; het resultaat is geen oordeel van een auditor. **Tier:** verplicht bij Business en Enterprise.
5. `customer_support_ai` — Customer Support. **Doet:** beoordeelt een klantvraag en stelt een prioriteit, een reden voor de urgentie, een voorgestelde actie en een samenvatting voor. / assesses a customer question and proposes a priority, a reason for the urgency, a suggested action and a summary. **Jij:** vul naam, product en de vraag in. **Mens:** een medewerker beslist over de actie en antwoordt zelf aan de klant; het resultaat is geen kant-en-klaar antwoord. / the result is not a ready-to-send reply.
6. `hr_recruitment_ai` — HR Recruitment. **Doet:** vat kandidaatgegevens samen en stelt sterke punten, aandachtspunten, vragen voor het gesprek, een score en een aanbeveling voor. / summarises candidate details and proposes strengths, concerns, interview questions, a score and a recommendation. **Mens:** **elke beslissing over een kandidaat neemt een mens; de score en aanbeveling mogen nooit de beslissing zijn.** Werving valt onder de EU AI Act als hoogrisicogebied en bevat bijzonder gevoelige persoonsgegevens; de klant is zelf verantwoordelijk voor een rechtmatige inzet. / **every decision about a candidate is taken by a person; the score and recommendation must never be the decision.** Recruitment is a high-risk area under the EU AI Act and involves sensitive personal data; the customer is responsible for a lawful use. **Vergrendeling:** dit blok wordt **alleen** opgenomen als de config `confirmed_blocks` de sleutel `hr_recruitment_ai` bevat (Dennis' uitdrukkelijke bevestiging). Staat de module wel actief maar niet bevestigd: de generator stopt met een duidelijke melding en maakt geen handout.
7. `marketing_automation` — Marketing Automation. **Doet:** maakt een campagnevoorstel op basis van doelgroep, product, doelen, budget en huidige kanalen: acties, strategie, boodschappen, timing en een indicatieve rendementsschatting. / produces a campaign proposal from audience, product, goals, budget and current channels: actions, strategy, messaging, timing and an indicative return estimate. **Mens:** de rendementsschatting is een indicatie van een taalmodel en geen voorspelling; marketing beoordeelt alle teksten en aannames. / the return estimate is an indication from a language model and not a forecast.
8. `meeting_agenda_assistant` — Meeting Agenda Assistant. **Doet:** stelt een agenda voor met tijdsduur, gewenste uitkomst per punt, voorbereidingstips per deelnemer, beslispunten en een actielijst-sjabloon. / proposes an agenda with duration, desired outcome per item, preparation tips per participant, decision points and an action-list template. **Let op:** deelnemersnamen in de invoer worden als persoonsgegevens behandeld. / participant names in the input are treated as personal data. **Mens:** de organisator past de agenda aan voordat deze wordt verstuurd.
9. `quote_contract_generator` — Quote & Contract Generator. **Doet:** maakt een concept van een offerte en contracttekst in het Nederlands of het Engels (instelbaar met `output_language`). / produces a draft quote and contract text in Dutch or English (selectable with `output_language`). **Mens:** **de uitkomst is een concept**; een jurist en de verantwoordelijke tekenen na lezing, Valqeron geeft geen juridisch advies. / **the output is a draft**; a lawyer and the responsible person review it before signing; Valqeron does not give legal advice. *Claude Code:* lees de exacte invoer- en uitvoervelden uit de code en vul de kopjes "Zie" en "Jij".
10. `business_intelligence` — Business Intelligence. **Doet:** beantwoordt een zakelijke vraag met een samenvatting, KPI's, aanbevelingen, actiepunten en risico's, op basis van de context die je invoert. / answers a business question with a summary, KPIs, recommendations, action items and risks, based on the context you enter. **Mens:** cijfers in het resultaat zijn afgeleid van de ingevoerde context; een analist controleert ze tegen de bron.

Plus `core` (de besturingslaag): korte uitleg wat Core is, in lijn met de tab Core in het portaal (lees de tekst in de portaalcode; verzin niets).

---

## 3. Claimregister (basis voor `claims.yaml`)

Elke belofte in de tekst staat hier met bewijs. Een claim zonder bewijs breekt de build. Claude Code vult de kolom "Bewijs" in Fase 0 met het exacte testbestand of de exacte plek in de code.

| ID | Claim (kort) | Bewijs (te verfijnen) |
|---|---|---|
| C1 | Eigen organisatie wordt altijd uit het token gehaald; andere organisaties zijn niet bereikbaar | CLAUDE.md §2 Batch L/O + isolatietests |
| C2 | Audit-log is hash-gekoppeld en wijzigen/verwijderen is geblokkeerd | CLAUDE.md §2 "Audit trail" (`app/models/audit_log.py`) |
| C3 | Auditintegriteit is controleerbaar (`/audit/verify`) | CLAUDE.md §2/§6 Batch A |
| C4 | PII wordt vervangen vóór het model en teruggezet in de uitvoer, voor alle 10 workflows | CLAUDE.md §2 "AVG-anonimisering" + `tests/workflows/test_pii_anonymizer_wiring.py` |
| C5 | Als de anonimisering niet beschikbaar is, gaat het verzoek niet naar het model (fail-closed) | CLAUDE.md §2 (`PIIAnonymizerUnavailable`) |
| C6 | Herkenning van persoonsgegevens is niet perfect | CLAUDE.md §5 |
| C7 | Eerste inlog vraagt een nieuw wachtwoord van minstens 12 tekens | CLAUDE.md §6 + test |
| C8 | MFA is optioneel (TOTP), 10 back-upcodes, 5 foute codes = 15 minuten blokkade | CLAUDE.md §2 "Auth" |
| C9 | Supportverzoek: categorieën, limieten 200/5000 tekens, 5 per uur, 20 per dag, SR-referentie, "My requests" | CLAUDE.md §2 Batch G |
| C10 | Onboarding-voortgangskaart toont alleen klantzichtbare taken; klant kan alleen eigen taken afvinken | CLAUDE.md Batch L Deel A |
| C11 | Governance-tab: overzicht plus aanmaken/bijwerken van incidenten, risico's, corrigerende maatregelen en bewijsstukken; status van een maatregel is te wijzigen | CLAUDE.md Batch L Deel B, O1 t/m O4 + tests |
| C12 | Tierregels (Starter ≥2, Business ≥5 incl. Compliance Monitor, Enterprise ≥7 incl. Compliance Monitor) | `app/services/tenant_modules.py` |
| C13 | Foutmeldingen gaan zonder persoonsgegevens naar een foutmeldingsdienst (Sentry, EU) | CLAUDE.md §2 "Foutmelding (Sentry)" |
| C14 | Er is geen goedkeuringsstap in het portaal | CLAUDE.md / executieplan |
| C15 | Quote & Contract Generator ondersteunt `nl` en `en` | CLAUDE.md §6 (`output_language`) |
| C16 | Bewijsstukken zijn beschrijvingen (metadata), geen bestanden | O4-hand-off en code |

**Regel:** elke nieuwe zin met "altijd", "nooit", "elke" of een getal krijgt een claim-ID of wordt geschrapt.

## 4. Verboden-woordenlijst (blokkerend, op de handouttekst)

| EN | NL |
|---|---|
| as-is, ready to send, ready-to-use, ready-made | kant-en-klaar, direct bruikbaar |
| automatically, automated decision | automatisch, geautomatiseerd besluit |
| fully, completely, 100% | volledig, helemaal, 100% |
| guarantee, guaranteed | garantie, gegarandeerd |
| continuous, continuously, real-time monitoring | continu, voortdurend, realtime bewaking |
| certified, certification (als eigenschap van Valqeron), compliant, compliance guaranteed | gecertificeerd, conform (als claim), voldoet aan |
| AI approves, AI decides | AI keurt goed, AI beslist |
| secure, safe (zonder concreet maatregelenzinnetje) | veilig (zonder concrete maatregel) |

Een woord in een **ontkenning** mag als de ontkenning zelf de eerlijke mededeling is ("geen kant-en-klaar antwoord", "not a ready-to-send reply", "geen continue bewaking"). De controle onderscheidt dit of laat de zin toe met een expliciete markering (`allow: negation`). Overige uitzonderingen alleen met reden in het sjabloon (bijvoorbeeld "certificering" als onderdeel van de productnaam).

## 5. Stijlgids: licht en printvriendelijk

| Onderdeel | Waarde |
|---|---|
| Papier | A4, staand; marges 20 mm boven/onder, 18 mm links/rechts; binnenmarge 5 mm extra |
| Achtergrond | wit (#FFFFFF); geen volvlakken, geen achtergrondafbeelding |
| Tekst | #14181F, 10,5 pt, regelafstand 1,45, sans-serif (dezelfde als het portaal, anders systeemfont) |
| Koppen | serif (dezelfde als het portaal, anders Georgia), #14181F; H1 24 pt, H2 15 pt, H3 11,5 pt |
| Accent | goud uit de huisstijl, donker genoeg voor wit papier: #A67C1A voor lijnen en kaders, #7A5A0E voor tekst (contrast ≥ 4,5:1); lichte tint #F7F0DE voor "Let op"-kaders. **Lees de exacte waarden uit de portaal-tokens; bij een afwijking gebruik je de portaalwaarden en meld je het.** |
| Tabellen | dunne grijze lijnen (#D9DCE1), kopregel in lichte goudtint |
| Screenshots | breedte 100% van de tekstkolom, dun kader 0,75 pt (#C9CDD3), onderschrift 8,5 pt in grijs (#59606B), 1440×900, vaste crop |
| Voorpagina | naam van de klant, tier, datum, taal, versie (sjabloonversie + CLAUDE.md-commit), vermelding "De schermafbeeldingen tonen de Engelstalige interface" in NL |
| Kop- en voettekst | links "Valqeron Client Handout", rechts paginanummer; achterpagina met contactblok (§1.9) |
| Afbreking | geen weduwen/wezen; geen kop als laatste regel van een pagina; elk screenshot blijft bij zijn onderschrift |
| Taal | NL en EN als twee losse PDF's, nooit door elkaar |
