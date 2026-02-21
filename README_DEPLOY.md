# Deployment Guide

See the project root README for quick start. This file contains detailed deployment instructions for Local, Render, Railway and AWS EC2.

1) Local (docker-compose):

```bash
cp .env.example .env
export GEMINI_API_KEY=your_key
docker-compose up --build
```

2) Render / Railway: build Docker image and deploy with env vars from `.env`.

3) AWS EC2: create instance, install Docker, copy repo, run `docker-compose up --build`.
