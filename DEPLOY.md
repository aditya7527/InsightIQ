# Deployment Guide

This guide helps you push your InsightIQ code to GitHub and deploy it to the cloud.

## 1. Push to GitHub

I have already initialized the local git repository and committed all files for you.
Now, run these commands in your terminal to push to your GitHub account:

1.  **Create a new repository** on GitHub (e.g., named `insightiq`).
2.  **Run these commands** (replace `YOUR_USERNAME`):

```bash
# Link your local repo to GitHub
git remote add origin https://github.com/YOUR_USERNAME/insightiq.git

# Rename branch to main
git branch -M main

# Push your code
git push -u origin main
```

## 2. Deploy to Render (Free Tier Recommended)

[Render](https://render.com/) is the easiest way to deploy python apps for free.

1.  **Sign up** at [render.com](https://render.com/).
2.  Click **New +** and select **Web Service**.
3.  Connect your GitHub repository.
4.  Use these settings:
    *   **Name**: `insightiq`
    *   **Region**: (Choose closest to you)
    *   **Branch**: `main`
    *   **Runtime**: `Python 3`
    *   **Build Command**: `pip install -r requirements.txt`
    *   **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5.  **Environment Variables** (Scroll down to "Advanced"):
    *   `PYTHON_VERSION`: `3.9.13` (Recommended)
    *   `DATABASE_URL`: `sqlite:///./insightiq.db`
        > *Note: On the free tier, SQLite data resets if the app restarts. For permanent data, use Render's PostgreSQL database.*
    *   `GEMINI_API_KEY`: `your_gemini_key`
    *   `JWT_SECRET`: `strong_secret_at_least_24_chars`
    *   `APP_ENV`: `production`
    *   `CORS_ORIGINS`: `https://your-frontend-domain.com`

## 3. Deploy to Railway

[Railway](https://railway.app/) is another excellent option.

1.  Log in to Railway.
2.  Click **New Project** → **Deploy from GitHub repo**.
3.  Select your `insightiq` repo.
4.  Railway will auto-detect Python.
5.  Go to **Variables** tab and add the same variables as above (`DATABASE_URL`, `GEMINI_API_KEY`, etc.).
6.  (Optional) Add a **PostgreSQL** plugin in Railway for a production-grade database.

## Troubleshooting

*   **PDF Export**: Requires `reportlab`. It's included in requirements.txt.
*   **Database**: If using SQLite on free tiers, remember data isn't persistent across deploys.
