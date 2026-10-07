# Handoff voor Claude Code — merkvisuals doorgetrokken naar de rest van het portaal (dashboard + sidebar)

Vervolg op de eerdere hand-off `claude-code-handoff-login-portal-visuals.md` (login-pagina). Dennis heeft nu expliciet akkoord gegeven om dezelfde beeldtaal door te trekken naar de rest van het klantportaal — specifiek dashboard en sidebar. Weer puur uitvoerend: build + deploy, geen ontwerpkeuzes.

## Wat er is gewijzigd (al rechtstreeks op de Mac geschreven vanuit de Cowork-sessie)

**Gewijzigd:** `ai-governance-frontend/src/pages/WorkflowDashboardPage.tsx` — dit is het gedeelde shell-component (sidebar + header) waar alle tabs (Home, Core, Products, Results, Documents, Account) doorheen renderen, dus één wijziging hier dekt het hele portaal:

1. **Sidebar (`<aside>`):** dezelfde gelaagde achtergrond (donkere gradient-overlay + `/valqeron-brand-bg.jpg`, hetzelfde bestand als op de loginpagina — dat bestaat al in `public/` sinds de vorige hand-off) als het merkpaneel op de loginpagina. Subtiel zichtbaar achter de navigatie, niet dominant.
2. **De twee kaarten in de sidebar** ("Environment"-kaart en de onderste "Need more?"-kaart): van een dekkende achtergrond naar licht transparant met `backdrop-filter: blur(...)`, zodat het gouden licht er zachtjes doorheen schemert — zelfde behandeling als de feature-cards op de loginpagina.
3. **Header-banner in de hoofdcontent** (de rij met paginatitel + status-badge, boven elke tab-inhoud): omgezet van een platte balk met een onderrand naar een afgeronde kaart met dezelfde gelaagde achtergrondafbeelding, rechts uitgelijnd zodat het beeld niet achter de titel-tekst zelf zit.
4. De eigenlijke pagina-inhoud onder de header (HomePage, CorePage, DocumentsPage, etc.) is **niet aangeraakt** — die blijft leesbaar or data-dicht zoals die was, geen visuele ruis daar.

Lokaal gerenderd met een headless browser vóór het wegschrijven om te bevestigen dat het resultaat consistent oogt met de loginpagina en dat alle tekst (navigatielabels, titel, badges) volledig leesbaar blijft. Geen functionaliteit aangeraakt (tab-navigatie, API-health-check, logout — allemaal ongewijzigd).

## Uit te voeren

Zelfde route als de vorige hand-off (geen git-repo in `ai-governance-frontend`, dus geen CI/CD):

1. Bevestig dat `src/pages/WorkflowDashboardPage.tsx` de nieuwe `background:`-regels bevat (sidebar, de twee kaarten, en de header-banner) en dat `public/valqeron-brand-bg.jpg` er nog staat (zou er al moeten zijn van de vorige hand-off).
2. `cd ai-governance-frontend && npm install` (indien nodig) `&& npm run build`.
3. Kopieer `dist/` naar de server zoals eerder: `rsync -av --delete dist/ root@164.92.221.90:/opt/valqeron-frontend/dist/` (of `scp -r`).
4. `nginx -t && systemctl reload nginx` is ook hier niet strikt nodig (geen nginx-wijziging), maar geen kwaad om te draaien.

## Verificatie

- Log in op `https://app.valqeron.com` met een bestaande demo-user en loop alle zes tabs langs (Home, Core, Products, Results, Documents, Account): bevestig dat de sidebar en de header-banner overal consistent het gouden achtergrondmotief tonen, dat de twee sidebar-kaarten licht doorschijnend ogen, en dat geen enkele tab-inhoud eronder lijdt aan leesbaarheidsproblemen.
- Browserconsole controleren op CSP-violations voor het laden van `/valqeron-brand-bg.jpg` (zelfde same-origin asset als bij de login, zou geen probleem moeten geven).
- Bevestig dat tab-navigatie, de "Logout"-knop en de live API-statusindicator (online/offline-badge) nog normaal werken — puur visuele wijziging, geen logica aangeraakt.

## Na afloop

Laat hier weten of build/deploy gelukt is. Dan werk ik het projectdocument bij en geef ik het terug aan Dennis.
