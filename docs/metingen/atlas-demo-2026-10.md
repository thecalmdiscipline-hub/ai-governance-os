# Atlas Demo B.V. — technische doorlooptijdmeting (Batch H, oktober 2026)

**Technische nulmeting, zonder menselijke wachttijden, fictieve data.** Dit is geen meting van een
echte klant en geen verkooplead-tijd — het meet alleen hoe snel het systeem zelf een nieuwe tenant
kan opzetten en alle 10 workflows kan draaien, als alle stappen direct na elkaar worden uitgevoerd.

## Methodologische kanttekening

Deze run liep in de praktijk niet aan één stuk door: tussen H1 (provisioning) en H2 (de
workflow-runs) zat een pauze van enkele uren — eerst een classifier-blokkade op het wijzigen van
het eenmalige wachtwoord, die vroeg om Dennis' eigen ingreep (hij heeft het wachtwoord zelf via het
portaal gewijzigd), en vervolgens is op zijn expliciete verzoek eerst Batch O2 afgerond vóórdat H2
werd hervat. Die pauze bevat uren onafhankelijk werk (Batch O2: een migratie, backend-endpoints,
portaalwerk) en is dus geen eerlijke "wachttijd" voor dit specifieke traject. De tabel hieronder
telt daarom alleen de **actieve technische tijd** van H1 en H2 bij elkaar op — niet de werkelijke
kalendertijd tussen de twee stappen.

## Meettabel

| Stap | Duur |
|---|---|
| H1 — provisioning (organisatie aanmaken, 11 modules, 1 beleid, 10 systemen+risico's, 1 demodocument) | **1,77 s** |
| H2 — eerste tot laatste workflowrun (11 runs: alle 10 workflows + de extra Nederlandse quote/contract-variant, geen pacing nodig — één token wordt hergebruikt, geen herhaalde logins) | **≈55,85 s** (som van de 11 individuele runduren, zie onder) |
| **Totale actieve technische tijd (H1 + H2)** | **≈57,6 s** |
| Aantal mislukte of herhaalde runs | **0** van de 11 |

## Duur per workflow (seconden, zoals teruggegeven door `scripts/run_demo_scenarios.py`)

| Workflow | Duur (s) | Run-id |
|---|---|---|
| business_intelligence | 7.62 | `c05ae009-5ca5-44bd-9674-f6b0fc088dfd` |
| compliance_monitoring | 4.39 | `eb2d9302-c63e-4912-a5f5-4536483ba070` |
| customer_support | 2.48 | `9780cf75-12b2-4843-aacf-e086e5d9a869` |
| document_knowledge | 2.04 | `fdd06d5f-560f-4205-b903-4933c66fc145` |
| hr_recruitment | 2.62 | `4f1b4e48-c070-4aaa-8ae2-380e78fe9a8e` |
| invoice_processing | 4.42 | `08be890b-9c52-4de0-8bb5-784737e41852` |
| marketing_automation | 5.20 | `deb36363-b1ac-4e62-b841-c14c650e2cee` |
| meeting_agenda_assistant | 6.11 | `3b106fe5-5b15-4a31-b132-800273a9c3be` |
| quote_contract_generator (en) | 9.53 | `58a696da-ead0-43ff-ace1-e1b69a0bd85e` |
| quote_contract_generator (nl, extra variant) | 7.97 | `be873819-f747-45cd-bdc2-2a988fd38d76` |
| sales_lead_qualification | 3.47 | `6f322312-d052-4d46-b45a-d629cee32ad7` |

All 11 runs succeeded on the first attempt (`attempt: 1`), `http_status: 200`, no content problems
(no empty output, no unresolved placeholder tokens). No output text is recorded here or anywhere
else, per the hand-off's instructions — only the structural metrics above.
