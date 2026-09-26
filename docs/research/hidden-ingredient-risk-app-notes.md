# Personalized Hidden-Ingredient & Dietary-Risk Alert System — Project Notes (PS 3)

> Status: historical notes. Banner added 2026-09-26; the original problem-statement notes, retained for context.

## Problem Statement

Millions of people managing chronic conditions — diabetes, CKD, food allergies, PCOS, hypertension — are silently harmed by what they eat, not because they're careless, but because the danger is invisible. A "sugar-free" biscuit can be loaded with maida and hidden syrups; a "healthy" salad can carry a sodium load that spikes blood pressure; a common spice mix can contain an allergen never clearly listed. Doctors give a generic "avoid oily and sugary food" instruction in a five-minute appointment, but nobody translates that into the dozens of real food decisions a patient makes every day at a store, a tiffin service, or a wedding buffet. Existing ingredient-scanning apps solve a lifestyle problem (vegan or not) — none solve a clinical one, where the wrong bite can trigger a hospital visit.

**Objective:** Develop a personalized decision-support solution that helps people better understand food-related risks in their everyday situations.
- Help individuals make better-informed decisions about food in relation to their personal circumstances.
- Account for the complexity, variability, and limitations of information available in real-world situations.
- Present relevant information in a clear, understandable and responsible manner.

## Core Features Requested

1. **Searchable menu/database of packaged food items** with their ingredient lists.
2. **Barcode / label scanning** — user scans a product and sees how it's specifically bad for *them* (personalized to their condition).
3. **Dish warning labels** — for restaurant/tiffin/buffet dishes (no barcode exists), give the user a list of ingredients to ask about.
4. **Recommendations** — suggest foodstuffs or recipes that would benefit the user's specific condition.
5. **FSSAI Rating display** — show FSSAI-related trust/safety info for a product (see clarification below — this needed scoping, since FSSAI doesn't rate packaged products the way the team initially assumed).

## Data Sources & APIs

### Packaged food / barcode lookup
- **Open Food Facts API** — free, open, no API key required (ODbL license). ~1.3M+ products globally; India-specific instance at `in.openfoodfacts.org` with a growing dataset (crossed 10k Indian products, still growing). Provides ingredient lists, allergen tags, additive/E-number tags, Nutri-Score, and NOVA processing classification.
  - Barcode lookup: `GET https://world.openfoodfacts.org/api/v2/product/{barcode}.json`
  - Text search: `GET https://world.openfoodfacts.org/cgi/search.pl?search_terms=...`
  - Being used in the project **via an Apify actor** for the "ready-to-eat" / packaged product slice (though the direct free REST API above may be cheaper/fresher than going through Apify, since Open Food Facts is already open and keyless).
- **USDA FoodData Central** — free (DEMO_KEY works for prototyping, 30 req/hr; registered key gives 1,000 req/hr, api.data.gov). Good secondary source for generic nutrient-level detail; includes a Branded Foods dataset (~400k UPC-coded products), but is US-centric so less useful for Indian-specific products.
- **GS1 India — Smart Consumer app + DataKart**: India's *official* infrastructure for this exact use case. FSSAI mandates brands to publish product info (ingredients, FSSAI license number, etc.) to GS1 India's DataKart, which powers the consumer-facing Smart Consumer app (scans barcodes starting with "890"). **Not usable directly** — DataKart is a brand-facing B2B upload platform, not a public developer API. Worth citing in documentation as the "official" system this could integrate with in a real-world deployment.
- **barcode-list.com** — community barcode-to-product-name lookup, being used as a **fallback only** when a barcode isn't found in Open Food Facts. Not an official database — coverage/accuracy for Indian brands is inconsistent, and scraping carries the usual ToS risk of scraping any consumer site. Should be used to get a product *name* only, with the user asked to confirm/fill in ingredient details rather than trusting it blindly.

### Indian nutrition / dish-level data
- **IFCT 2017 (Indian Food Composition Tables)** — published by the National Institute of Nutrition (ICMR), Hyderabad. Provides detailed nutrient composition (151 discrete food components) for Indian foods, measured across six regions of India. This is the right dataset for *raw ingredients and homemade/restaurant dishes* (not packaged goods), since it's Indian-specific rather than US-centric like USDA.
  - GitHub org (all data packages): https://github.com/ifct2017
  - Core dataset repo (nutrient composition): https://github.com/ifct2017/compositions
  - Combined npm package (queryable JS API, `npm install ifct2017`): https://github.com/ifct2017/ifct2017
  - Alternate/actively maintained fork being used in this project: https://github.com/nodef/ifct2017 (542 key foods — a later iteration of the dataset; food-code numbering differs slightly from the 528-food 2017 original, so pick one version and stay consistent)
  - Online searchable database: https://ifct2017.github.io
  - Original source PDF: https://nin.res.in/ebooks/IFCT2017.pdf
  - Useful sub-packages: `codes` (food name → food code, handles regional-language names, e.g. "atta" → A019), `intakes` (recommended daily intake values — useful for the daily-budget tracking feature idea below).

### Recipes / recommendations
- **Food.com recipe dataset** — being pulled via an Apify actor (`https://console.apify.com/actors/L9lMlZe30ghx2Zdv3/input`). Note: Food.com scrapers on Apify are often built on top of a static Kaggle-hosted dump of the same dataset — worth checking if the Kaggle version can be used directly instead, to save Apify credits.
- **Spoonacular API** — free tier available. ~365k recipes filterable by diet tags (vegan, gluten free, low sodium, low carb, etc.), automatic nutrition-per-recipe calculation, allergen detection via food ontology (knows "nut free" excludes pecans even if not explicitly stated).
- **Edamam APIs** (three separate products): Food Database API (nutrient/allergen/diet lookup, incl. UPC/barcode search), Nutrition Analysis API (NLP-based ingredient-line parsing — useful for OCR post-processing), Recipe Search API (5M+ recipes, diet/allergen/nutrient filtering).

### FSSAI-related data (clarified)
There is **no FSSAI "rating" for packaged products** in the way a health/quality score would work. What actually exists:
- **FoSCoS (Food Safety Compliance System) license verification** — lets you check whether a 14-digit FSSAI license number is valid/active and see the registered business name, address, license type (State/Central/Basic), status (Active/Expired/Suspended), and product category. This is a *license validity check*, not a quality rating. No official public API exists for this — third-party scrapers exist (e.g. Apify actors that replicate FoSCoS's encrypted request flow) but this is unofficial and fragile.
- **FSSAI Hygiene Rating Scheme** — a genuine 1–5 star rating (displayed as smileys), but it applies **only to food service establishments** (restaurants, cafes, dhabas, sweet shops, bakeries, meat shops) based on a physical audit of hygiene practices — **not to packaged products**. This is actually a good fit for the "dish/restaurant" side of the product (warning labels for buffets/tiffin services), where you could show a venue's Hygiene Rating alongside the ingredient-ask warnings, but it does nothing for packaged-good scanning.
- **Practical implication for the product:** for packaged products, show "FSSAI License: Verified/Not Found" (a trust signal) rather than a "rating." For the restaurant/dish side, FSSAI's real Hygiene Rating (where available) can be shown as an actual star rating.

### OCR fallback (for products not in any database)
- When a barcode scan misses across all sources, fall back to OCR on the ingredient panel: Google ML Kit Text Recognition (on-device, free) or Tesseract OCR, then run extracted text through Edamam's Food Text Analysis (NLP-based ingredient/allergen extraction from unstructured text) or a custom ingredient-matching layer.
- Longer-term pattern to consider: let the user's own camera photograph the label on the spot (like the Indian app "OpenLabel" does), run OCR + NLP locally, and optionally contribute the result back into a shared open database — avoids legal/reliability issues of scraping retailer sites for images, and improves coverage over time.

## How Blinkit-style Grocery Apps Actually Source Catalog Data (background research)
Blinkit runs a vendor purchase-order model, not an open marketplace: brands submit structured catalog data (name, images, ingredients, nutrition, manufacturer, shelf life, FSSAI license) during a "New Product Introduction" process before Blinkit issues a purchase order; a physical inward-check team verifies stock matches the submitted data at the dark store gate. **Ingredients are never derived from photos** — they're submitted as structured text directly by brands. There's no public Blinkit API; third-party scrapers exist but carry ToS risk and aren't a good foundation for the core data pipeline.

## Feature Ideas Discussed (beyond the core four)

### Making "hidden" ingredients actually explainable
- **Ingredient alias/synonym detection** — sugar hides under 20+ names (maltose, dextrose, corn syrup, invert syrup...); maida under "refined flour," "all-purpose flour." A synonym-mapping engine that flags these even when the label doesn't use the exact term the user is watching for — arguably the single most differentiating feature for the "hidden ingredient" framing.
- **Plain-language "why" explanations** — not just "flagged: sodium nitrite" but "a preservative linked to blood pressure spikes — relevant because you marked hypertension."

### Personalization
- **Multi-condition, multi-person profiles** — one account holds several household members (e.g. mom with CKD, dad with diabetes), each flagged independently per product.
- **Severity tiers, not binary flags** — "avoid entirely" vs "occasional/small portion okay" vs "fine," rather than a flat red/green list.
- **Cumulative daily tracking** — track scanned/logged items against a daily sodium/sugar budget (using IFCT's `intakes` package for reference values) and warn as the user approaches the limit across a day, not just per-item.

### Handling real-world data messiness (ties directly to the PS's stated objective)
- **Confidence/data-quality indicator** — show "verified" (structured data from Open Food Facts) vs "OCR-extracted, may contain errors" (scanned fallback) so users know how much to trust a given flag.
- **Restaurant/buffet mode** — user picks a dish name (no barcode exists) and gets "ask the caterer if this has X, Y, Z" based on a dish → typical-ingredients mapping, built from Spoonacular/Edamam recipe data cross-referenced against the user's condition-specific risk list.
- **Crowdsourced gap-filling** — when a scan fails, let the user submit the label photo/OCR result back into a shared pool (same model as Open Food Facts), improving coverage with use.

### Making the safe choice easy, not just visible
- **Swap suggestions at the point of failure** — when a product is flagged, immediately suggest 2–3 alternatives in the same category that pass the user's filters.
- **Shareable allergy/condition card** — a generated QR code or card summarizing what to avoid, useful to hand to a waiter or wedding caterer, outside the app entirely.

### Stretch / differentiator
- **Tie-in with lab report data (linking to the HealthBridge project)** — if a user's uploaded lab report shows elevated creatinine or HbA1c, use that to auto-tighten thresholds (e.g. stricter potassium flagging for CKD once labs cross a range) instead of relying only on a static self-declared condition. Even describing this as a documented "Phase 2 vision" (without building it for the hackathon) demonstrates systems thinking beyond a basic scanner.

## Known Gaps / Open Work
- **Additive/E-number risk mapping** is not solved by any existing API — Open Food Facts tags which additives are present, but doesn't say "sodium benzoate is risky for condition X." This condition-to-ingredient risk table has to be built in-house and is on the critical path for the actual risk-flagging logic (not just data plumbing).
- Indian packaged-product coverage across all open databases (Open Food Facts, GS1 DataKart, barcode-list.com) is still thin relative to what's actually sold in India — the OCR/user-submission fallback path is not optional, it's core to making the product usable.
