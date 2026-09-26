# SafeBitez

SafeBitez is an Expo/React Native app and a FastAPI/PostgreSQL backend that turns recorded
allergies and conditions into explicit checks on food labels, with evidence and unknowns.

## Team Name & Members

**Team Name:** Fantastic 4

1. Hashim Bhagad
2. Harsh Chikane
3. Ratnesh Gandhi
4. Saurabh Kokane

## Problem Statement

PS 3
Personalized Hidden-Ingredient & Dietary-Risk Alert
System
Problem Statement:
Millions of people managing chronic conditions — diabetes, CKD, food allergies, PCOS, hypertension — are
silently harmed by what they eat, not because they're careless, but because the danger is invisible. A 'sugar-
free' biscuit can be loaded with maida and hidden syrups; a 'healthy' salad can carry a sodium load that
spikes blood pressure; a common spice mix can contain an allergen never clearly listed. Doctors give a
generic 'avoid oily and sugary food' instruction in a five-minute appointment, but nobody translates that into
the dozens of real food decisions a patient makes every day at a store, a tiffin service, or a wedding buffet.
Existing ingredient-scanning apps solve a lifestyle problem (vegan or not) — none solve a clinical one,
where the wrong bite can trigger a hospital visit.
Objective:
Develop a personalized decision-support solution that helps people better understand food-related risks in
their everyday situations.
• Help individuals make better-informed decisions about food in relation to their personal circumstances.
• Account for the complexity, variability, and limitations of information available in real-world situations.
• Present relevant information in a clear

## Tech Stack Used

- **Frontend:** React Native, Expo, Expo Router, TypeScript, and React Native Web
- **Backend:** Python, FastAPI, SQLAlchemy, Alembic, and Uvicorn
- **Database:** PostgreSQL
- **Containerisation:** Docker and Docker Compose
- **Integrations:** Open Food Facts for product data, with optional Fireworks and TypeSafe
  services for label extraction and preference ranking

## Setup Instructions

### Prerequisites

- Node.js and npm
- Docker Desktop (or Docker Engine with Docker Compose)

### 1. Configure and start the backend

From the repository root, create a local backend configuration file:

```sh
cp backend/.env.example backend/.env
```

In `backend/.env`, set a strong `JWT_SECRET` (at least 32 characters) and choose a
`POSTGRES_PASSWORD`. Then start PostgreSQL and the FastAPI service:

```sh
docker compose --env-file backend/.env up --build -d
```

The API is available at `http://localhost:8000`, and the interactive API documentation is at
`http://localhost:8000/docs`.

### 2. Configure and start the frontend

```sh
cd frontend
npm ci
cp .env.example .env
npm run web
```

Open the Expo web app at `http://localhost:8081`. To run on a mobile device or emulator instead,
use `npm run start`; Android and iOS launch commands are also available through Expo.

For a physical device, update `EXPO_PUBLIC_API_URL` in `frontend/.env` to your computer's
reachable LAN address.

## Documentation

- [Documentation index](docs/README.md) — design history, research, and verification evidence.
- [Backend README](backend/README.md) — API surface, behaviours, and checks.
- [Frontend README](frontend/README.md) — Expo setup and the public API URL.

## Safety stance

Inference stays advisory: deterministic code runs the restriction checks and arithmetic,
replacements split into a verified tier and an unverified `needs_review` tier that are never
merged, and unknown data stays explicitly unknown rather than guessed.
