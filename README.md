# MoMo Shield 🛡️
### AI-Powered Fraud Detection for Mobile Money Transactions

MoMo Shield is a production-grade Django application that detects fraud in Mobile Money (MoMo) transactions using a trained XGBoost machine learning model. Built for the Ugandan market.

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Train the model (only needed once)
python detection/ml/train.py

# 3. Apply database migrations
python manage.py migrate

# 4. Create a superuser
python manage.py createsuperuser

# 5. Start the server
python manage.py runserver
```

Visit: http://127.0.0.1:8000

**Default credentials (dev):** `admin` / `MoMo2026!`

---

## Features

- **Real ML Fraud Detection** — XGBoost model trained on 450,000 Uganda MoMo transactions
- **CSV Upload** — Upload any transaction CSV and get instant fraud scores
- **Fraud Scoring** — Each transaction gets a probability score (0–100%) and risk level (Low / Medium / High)
- **Fraud Alerts** — Auto-generated alerts with human-readable reasons
- **Dashboard** — Overview stats, fraud rate, transaction breakdown by type
- **Reports** — Export results as PDF or Excel
- **REST API** — Full DRF API at `/api/` for frontend/integration use

---

## ML Model

| Metric   | Score  |
|----------|--------|
| ROC-AUC  | 0.896  |
| PR-AUC   | 0.725  |
| F1 Score | 0.535  |

**Algorithm:** XGBoost with `scale_pos_weight` class balancing  
**Training data:** 450,000 transactions, 7.1% fraud rate  
**Top features:** `hour`, `amount_ugx`, `amount_deviation`, `receiver_previously_flagged`

---

## API Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| GET  | `/api/stats/` | Dashboard aggregate stats |
| GET  | `/api/transactions/` | Paginated transaction list |
| GET  | `/api/alerts/` | Fraud alerts |
| POST | `/api/detect/upload/` | Upload CSV → run detection |
| GET  | `/api/detect/jobs/` | List detection jobs |
| GET  | `/api/detect/jobs/<id>/` | Job detail + all predictions |

---

## Project Structure

```
momoshield/
├── accounts/         User authentication
├── dashboard/        Transaction + alert models, views
├── detection/        ML engine (train, predict, preprocess) + upload
├── reports/          PDF & Excel export
├── api/              Django REST Framework endpoints
├── frontend/         React SPA source (MoMoShield.jsx)
├── static/           CSS, JS, images
├── templates/        Base HTML templates
└── CLAUDE.md         Project memory — read this to resume development
```

---

## Environment Variables (`.env`)

```
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgresql://user:pass@localhost/momoshield   # optional
```

---

## Production Deployment

```bash
# Collect static files
python manage.py collectstatic

# Run with gunicorn
gunicorn momoshield.wsgi:application --bind 0.0.0.0:8000 --workers 4
```
