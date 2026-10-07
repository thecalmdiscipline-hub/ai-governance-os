# Handoff voor Claude Code — brand-visuals verwerkt in de loginpagina, build + deploy nodig

Dennis had gelijk in zijn eerdere feedback: de eerdere "restyling" van `ai-governance-frontend` had alleen de kleurtokens (donker/goud-thema) uit de website overgenomen, maar geen van de aangeleverde beeldmerken/foto's daadwerkelijk verwerkt. Dat is nu wel gebeurd, specifiek voor de loginpagina — op zijn expliciete instructie: *"de fotos gebruik je als leidraad om de login meer de look te laten hebben zoals de website. afbeeldingen mogen wel gebruikt worden zonder dat ze de overhand krijgen."*

Puur uitvoerend vanaf hier — geen ontwerpkeuzes meer te maken, alleen bouwen en deployen. **Geen git-repo** in `ai-governance-frontend` (bekend, zie eerdere hand-off `claude-code-handoff-portal-deploy.md`), dus dit is weer een handmatige build + kopie, geen CI/CD.

## Wat er is gewijzigd (al rechtstreeks op de Mac geschreven vanuit de Cowork-sessie)

1. **Nieuw bestand:** `ai-governance-frontend/public/valqeron-brand-bg.jpg` (1080×750, ~93KB, geoptimaliseerd JPEG). Dit is een bijgesneden versie van één van Dennis' Valqeron-merkvisuals (de "Less talking. More building." poster) — de kop-tekst is eraf gesneden, alleen het abstracte gouden-kubus/pilaren-beeld is overgebleven, zodat er geen dubbele/botsende tekst in het beeld zelf zit.
2. **Gewijzigd:** `ai-governance-frontend/src/pages/LoginPage.tsx` — het linker merkpaneel (met het "Premium AI control..."-blok en de drie feature-cards) heeft nu:
   - Dit beeld als laag achtergrond, onder een donkere gradient-overlay (dus subtiel zichtbaar, niet dominant — precies zoals gevraagd).
   - Een dun goud lijntje onder het logo/wordmark, als kleine decoratieve accent die de posterstijl echoot.
   - De drie feature-cards zijn nu licht transparant met een `backdrop-filter: blur(...)`, zodat het gouden licht van de achtergrondafbeelding er zacht doorheen schemert.
   - Geen enkele bestaande functionaliteit aangeraakt (login-logica, form-handling, etc. zijn ongewijzigd).

Ik heb dit lokaal (in een sandbox, los van de Mac) gerenderd met een headless browser om het resultaat visueel te verifiëren vóórdat het naar de Mac is geschreven — ziet er goed uit: de kop blijft scherp leesbaar, het gouden beeld is duidelijk zichtbaar als sfeer/textuur maar neemt de aandacht niet over. Screenshot is niet meegestuurd in deze hand-off, maar het is triviaal te controleren zodra het gebouwd en gedeployed is (zie verificatie hieronder).

## Uit te voeren

1. Bevestig dat beide bestanden er staan zoals hierboven beschreven (`public/valqeron-brand-bg.jpg` bestaat, `src/pages/LoginPage.tsx` bevat de `background:` regel met `url('/valqeron-brand-bg.jpg')` in het linkerpaneel).
2. `cd ai-governance-frontend && npm install` (indien nodig) `&& npm run build` — levert een nieuwe `dist/`-map op.
3. Kopieer `dist/` naar de server zoals eerder gedaan (`/opt/valqeron-frontend/dist` op `valqeron-prod-v2`, 164.92.221.90): bijv. `rsync -av --delete dist/ root@164.92.221.90:/opt/valqeron-frontend/dist/` (of `scp -r`, consistent met hoe de vorige portaal-deploy is gedaan).
4. `nginx -t && systemctl reload nginx` is voor deze wijziging niet per se nodig (de nginx-config zelf is niet aangeraakt), maar kost niets om voor de zekerheid te draaien.

## Verificatie

- Open `https://app.valqeron.com` in een echte browser (niet alleen `curl`) en bevestig visueel: het gouden kubus/pilaren-beeld is zichtbaar als achtergrondtextuur in het linkerpaneel van het loginscherm, de kop "Premium AI control for client environments" blijft volledig leesbaar, en de drie feature-cards ogen licht doorschijnend.
- Controleer de browserconsole op eventuele CSP-violations voor het laden van `/valqeron-brand-bg.jpg` — dit is een same-origin afbeelding (geen CDN), dus zou geen probleem moeten geven met de bestaande CSP op dit domein, maar gezien de eerdere CSP-geschiedenis op `app.valqeron.com` (zie CLAUDE.md sectie 4/6) is een expliciete check de moeite waard.
- Test dat inloggen zelf nog steeds werkt (functionaliteit is niet aangeraakt, maar bevestig voor de zekerheid met een bestaande demo-user).

## Na afloop

Laat hier weten of de build/deploy gelukt is (en of de CSP-check schoon was). Dan kan ik CLAUDE.md/het projectdocument bijwerken en teruggeven aan Dennis dat dit rond is. Dit is puur een front-end visuele wijziging — geen wijziging aan `ai-governance-os` nodig, dus geen commit/push in die repo voor dit stuk.
