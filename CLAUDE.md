# MaukaBros: Know Your District

Profiles of who lives in each of Hawaiʻi's 51 House and 25 Senate districts, from the ACS 2024 5-year estimates. The site will be judged: aim for an impressive but professional, civic-data look.

## Run it
- Build data: `python pipeline/build.py` (reads `.env`, writes `data/kyd.duckdb`)
- Serve: `python -m uvicorn api.main:app --reload`, then open http://127.0.0.1:8000
- API: `GET /api/districts`, `GET /api/districts/{geo_id}`; docs at /docs

## Frontend
- `web/index.html` is plain HTML/CSS/JS served by FastAPI's static mount. No build step.
- Keep it that way unless the team decides otherwise. Load libraries from a CDN (cdnjs, jsdelivr).
- Don't change the API shape without updating the frontend and asking first.

## Data rules (never break these)
- Every figure shows its source and year.
- Show the margin of error. Suppressed or not-applicable values are labeled as such, never hidden or shown as zero.
- Render data with textContent, not innerHTML.
- Keep Hawaiian spelling intact: ʻokina and kahakō (Hawaiʻi, kūpuna).

## Design
- Use the frontend-design skill. Propose a design plan (palette, type, layout) and wait for approval before coding.
- One showpiece moment (for example an interactive district map); keep everything else calm and readable.
- Responsive to 390px, keyboard accessible, WCAG AA contrast, respect prefers-reduced-motion.

## Verify
After any UI change, make sure the server is running, then use Playwright to screenshot http://127.0.0.1:8000 at 1440px and 390px wide and fix what looks off.
