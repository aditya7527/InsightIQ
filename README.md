# InsightIQ

InsightIQ is a FastAPI-based business intelligence application that turns CSV/Excel uploads into analytics, forecasting, root-cause analysis, and executive summaries.

## Stack

- Backend: FastAPI, SQLAlchemy, Pandas
- AI Provider: Google Gemini (`google-generativeai`)
- Forecasting: Prophet, Statsmodels, scikit-learn
- Frontend: Server-rendered HTML + vanilla JavaScript
- Database: SQLite by default, PostgreSQL supported via `DATABASE_URL`

## Runtime Frontend

The active UI is served from:
- `app/templates/index.html`
- `app/static/app.js`
- `app/static/style.css`

## Quick Start

1. Create and activate a virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Configure environment variables in `.env`:
   - `DATABASE_URL=sqlite:///./insightiq.db`
   - `JWT_SECRET=replace_with_a_strong_secret`
   - `GEMINI_API_KEY=your_api_key`
   - `APP_ENV=development`
   - `CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000`
4. Run:
   - `uvicorn app.main:app --reload --port 8001`

Open `http://localhost:8001`.

## Production Notes

- Set `APP_ENV=production` or `staging`.
- Use a strong `JWT_SECRET` (24+ chars).
- `GEMINI_API_KEY` is required in production/staging.
- Configure `CORS_ORIGINS` explicitly for trusted domains only.

## Tests

- Run tests with:
  - `pytest -q -p no:cacheprovider`
