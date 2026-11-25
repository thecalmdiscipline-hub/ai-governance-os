# Scope-codes: documenten en workflows

Status: **voorstel, 23 nov 2026.** Codes met (?) moeten Dennis nog bevestigen.

## 1. Regels voor codes

- Kleine letters, cijfers en koppelteken. Geen spaties, geen accenten. Lengte 2 tot 24 tekens.
- Een code is een vaste sleutel: wijzigen kan niet (V7). Nieuwe codes toevoegen mag.
- Een document heeft één of meer codes (V4). Minimaal één.
- Een workflow leest een document alleen als één van de codes van het document bij zijn eigen workflow-code hoort, of bij de code `gedeeld`.

## 2. Formaat in bestandsnaam en inhoud (V1)

De code staat in de bestandsnaam én bovenaan de inhoud. Beide moeten gelijk zijn.

- Bestandsnaam: `[scope=hr,sales] Functieprofiel.pdf`
- Inhoud, eerste regel (tekst, markdown, csv): `scope: hr,sales`
- Word en PDF: dezelfde regel als eerste tekstregel van het document.

Upload wordt geweigerd als: de code ontbreekt, de bestandsnaam en de inhoud verschillen, of een code is onbekend (V5). Dit is de enige controle; de database krijgt de codes uit de bestandsnaam en wordt bij verschil geweigerd.

## 3. Workflow-codes

Eén code per workflow. De code is de sleutel die in `workflows` en in de documentscope wordt gebruikt.

| Workflow-sleutel (code) | Workflow-code (voorstel) | Module in catalogus |
|---|---|---|
| `document_knowledge` | `kennis` | document_intelligence |
| `customer_support` | `support` | customer_support_ai |
| `sales_lead_qualification` | `sales` | sales_qualification_ai |
| `quote_contract_generator` | `contract` | quote_contract_generator |
| `meeting_agenda_assistant` | `meeting` | meeting_agenda_assistant |
| `marketing_automation` | `marketing` | marketing_automation_ai |
| `invoice_processing` | `factuur` | invoice_processing_ai |
| `compliance_monitoring` | `compliance` | compliance_monitor |
| `hr_recruitment` | `hr` | hr_recruitment_ai |
| `business_intelligence` | `bi` | business_intelligence |

Dit zijn tien workflow-codes. De codes staan nu alleen in het ontwerp; de code moet ze uit één bron lezen (de workflow-registry).

## 4. Documentcodes

| Code | Betekenis | Workflows die lezen |
|---|---|---|
| `gedeeld` | Bedrijfsbreed: beleid, handboek, algemene voorwaarden (?) | alle workflows |
| `kennis` | Algemene kennisdocumenten | kennis |
| `support` | Klantenservice-kennis, FAQ, productdocs | support |
| `sales` | Prijslijsten, productfiches, ICP | sales |
| `contract` | Sjablonen voor offertes en contracten | contract |
| `meeting` | Agenda's, notulen, vergaderstukken | meeting |
| `marketing` | Campagnemateriaal, merkrichtlijnen | marketing |
| `factuur` | Facturen en inkoopdocumenten | factuur |
| `compliance` | Beleid, procedures, audit-bewijs | compliance |
| `hr` | Personeels- en wervingsdocumenten | hr (alleen) |
| `bi` | Rapportages en KPI's | bi |

Regels:
- `hr` is **exclusief** (V18, bevestigd door Dennis): een document met `hr` mag nooit een andere code hebben, ook niet `gedeeld`. Een combinatie met `hr` wordt bij upload geweigerd, en alleen de workflow `hr` leest het document.
- `gedeeld` is een aparte code (bevestigd). Een document met `gedeeld` én een workflow-code wordt door de workflow-code gelezen plus door alle workflows.
- Nieuwe documentcodes komen alleen via een migratie en een entry in de code-lijst; niet via de upload.

## 5. Beslissingen van Dennis (23 nov 2026)

1. De workflow-codes uit §3 zijn bevestigd.
2. `gedeeld` is een aparte code.
3. `hr` is exclusief: nooit combineren met `gedeeld` of een andere code. Upload met `hr` plus een andere code wordt geweigerd.
4. Alleen Valqeron beheert de codelijst. Klanten voegen geen codes toe aan de lijst.

Let op punt 4: dit gaat over de **lijst** van codes. Of een organisatie-admin een **document** een bestaande code mag geven (beslispunt B3c in de bouwopdracht) is een ander besluit en staat nog open.
