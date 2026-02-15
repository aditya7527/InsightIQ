# InsightIQ — AI-Powered Business Intelligence Engine

InsightIQ is an enterprise-grade AI analytics platform designed to transform raw datasets into actionable executive insights. It leverages GPT-4 for narrative generation, statistical modeling for forecasting, and advanced pattern recognition for root cause analysis.

## 🚀 Key Features

*   **📈 Intelligent Ingestion**: Auto-detects schema, industry context, and data quality issues.
*   **🤖 AI Executive Summary**: Generates C-suite level narratives identifying key trends and risks.
*   **🔍 Root Cause Analysis**: Automatically identifies drivers behind metric changes (e.g., "Why did revenue drop?").
*   **🔮 Automated Forecasting**: Predicts future trends using Prophet (with linear regression fallback).
*   **💬 Ask Your Data**: Natural language query interface (NLP-to-SQL) for instant answers.
*   **📄 PDF Reports**: Exports professional, ready-to-present executive PDF reports.
*   **📊 Interactive Dashboard**: Modern, responsive UI with dynamic charting and drill-down capabilities.

## 🛠️ Tech Stack

*   **Backend**: FastAPI, SQLAlchemy, Pydantic, Pandas
*   **AI & ML**: OpenAI GPT-4, Prophet, Statsmodels, Scikit-learn
*   **Frontend**: HTML5, Vanilla JS, Chart.js, Tailwind-inspired CSS
*   **Database**: PostgreSQL 15
*   **Infrastructure**: Docker, Docker Compose

## ⚡ Quick Start

### Prerequisites
*   Python 3.9+
*   OpenAI API Key

### Local Installation

1.  **Clone the repository**
    ```bash
    git clone https://github.com/yourusername/insightiq.git
    cd insightiq
    ```

2.  **Configure Environment**
    Create a `.env` file in the root directory:
    ```env
    DATABASE_URL=sqlite:///./insightiq.db
    OPENAI_API_KEY=your_openai_api_key_here
    JWT_SECRET=your_super_secret_key
    ```

3.  **Run Locally**
    Windows:
    ```bash
    run_local.bat
    ```
    
    Linux/Mac:
    ```bash
    pip install -r requirements.txt
    python init_local_db.py
    uvicorn app.main:app --reload --port 8001
    ```
    
    The application will be available at `http://localhost:8001`.

## 🚀 Deployment (Railway)

1.  **Push to GitHub**
2.  **Connect in Railway**
3.  **Set Environment Variables**:
    *   `DATABASE_URL`: (Add your PostgreSQL URL)
    *   `OPENAI_API_KEY`: (Add your key)
    *   `JWT_SECRET`: (Add a secret)
    *   `PORT`: (Railway sets this automatically)
4.  **Start Command**:
    ```bash
    uvicorn app.main:app --host 0.0.0.0 --port $PORT
    ```

## 📖 Usage Guide

1.  **Upload Data**: Drag and drop your CSV/Excel file (e.g., sales data, financial reports).
2.  **View Dashboard**: Instantly see key metrics, quality scores, and AI-generated summaries.
3.  **Analyze**:
    *   Check **Root Cause** tab to understand drivers.
    *   View **Forecasts** to see future trends.
    *   Use **Ask Your Data** to query specific details (e.g., "What was the total profit in Q4?").
4.  **Export**: Click "Export Report" to download a comprehensive PDF for your stakeholders.

## 📚 API Documentation

Once running, access the interactive API docs at:
*   Swagger UI: `/docs`
*   ReDoc: `/redoc`

## 🛡️ License

MIT values

