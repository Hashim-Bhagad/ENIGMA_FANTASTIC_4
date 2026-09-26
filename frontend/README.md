# SafeBitez frontend

Shared mobile and web UI built with Expo, React Native, TypeScript, and Expo Router. It follows the SafeBitez design references and the frontend stack described in the planning notes.

## Run

```sh
npm install
npm run start
```

Use `npm run web` for the browser build. Expo Camera provides barcode scanning on supported devices. Mobile label photos use the camera; the web flow selects an image file.

## Pages

- **Guide** — recorded profile summary and entry points into the check flows.
- **Scan** — barcode scan, manual barcode entry, and product search.
- **Review** — editable label observations before an assessment.
- **Assessment** — separate declared matches, advisory statements, considerations, and unknown information.
- **Replacements** — same-category comparison examples with incomplete-data limits shown.
- **Dish check** — questions for a restaurant or buffet preparer.
- **History** — recent and saved assessment examples.
- **Profile** — allergies, explicit limits, and preferences.

The tab bar keeps the four frequent destinations (Guide, Scan, History, Profile). Review, Assessment, Replacements, and Dish check appear only in their relevant task flows.

## Frontend-only boundary

There is no backend, authentication service, catalog, OCR, or assessment engine in this repository. Product records and assessment findings in `src/data/demo.ts` are invented UI fixtures. They are labeled as illustrative; attached label photos are previewed locally and are not uploaded or read. Edited label text is saved only in app memory and does not produce a suitability result. Replacements are category examples, not approved recommendations. Profile and saved-state controls are local preview interactions and do not persist across reloads.
