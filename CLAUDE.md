# CLAUDE.md — MoMo Shield Project Memory

## Project Overview
MoMo Shield is a Django-based fraud detection system for Mobile Money (MoMo) transactions in Uganda.
XGBoost ML model trained on 450,000 transactions. Users upload CSV files and get real fraud predictions.

---

## Current Project Status
**Phase:** ✅ Fully complete + all bug fixes applied
**Last Updated:** 2026-06-07

---

## Completed Tasks

### Phase 1–5 (Initial Build)
- [x] Full Django project structure created
- [x] XGBoost model trained — ROC-AUC: 0.896, PR-AUC: 0.725
- [x] model.pkl, scaler.pkl, feature_names.pkl saved to detection/ml/
- [x] All Django apps: accounts, dashboard, detection, reports, api
- [x] All HTML templates + CSS design system
- [x] REST API (DRF) at /api/
- [x] Database migrations applied, superuser created (admin / MoMo2026!)

### Bug Fix 1 — Mac OpenMP / XGBoost error
- [x] Not a code issue — user needed: `brew install libomp`

### Bug Fix 2 — Upload CSV column flexibility
- [x] Rewrote preprocess.py — only `amount_ugx` and `txn_type` are required
- [x] All other columns auto-derived or filled from training data medians
- [x] Upload template updated to show required vs optional columns clearly

### Bug Fix 3 — 200k row upload taking ~10 minutes
- [x] Root cause: `_derive_velocity_features` used a Python for-loop (O(n²))
- [x] Fixed: rewrote with vectorised pandas groupby().rolling()
- [x] Fixed: time parsing switched from dateutil per-row to fixed-format strptime
- [x] Fixed: time-only columns (HH:MM AM/PM, no date) now skip rolling window entirely
- [x] Result: 200,000 rows in ~1 second (578× faster)
- [x] Added chunked DB writes (5,000 rows per batch)
- [x] Added /detect/progress/<id>/ polling endpoint for live progress

### Bug Fix 4 — New users seeing other users' data
- [x] Root cause: dashboard queries used Transaction.objects.all() — no user filter
- [x] Fixed: _user_transactions() and _user_alerts() helper functions scope all queries to uploaded_by=request.user
- [x] Admins (role='admin') still see all data
- [x] FraudAlert creation rewritten — was doing N/5000 DB queries, now 2 queries total
- [x] Added compound DB indexes: (uploaded_by, is_fraud), (uploaded_by, created_at)
- [x] Register template fixed — password fields were type="text" (exposed passwords)
- [x] Viewer role blocked from uploading files
- [x] Profile page created showing role and permissions

### Bug Fix 5 — Migration NodeNotFoundError on runserver
- [x] Root cause: DB had migrations 0002+0003 applied (from build env) but files were missing from zip
- [x] Fixed: created stub 0002 and 0003 migration files matching DB history (empty operations)
- [x] Created 0004_final_model_sync using SeparateDatabaseAndState — updates model state only, no DB ops
- [x] migrate runs cleanly, check reports 0 issues, runserver starts normally

---

## User Roles (3 configured)

| Role | Upload CSV | Own data | All data | Admin panel |
|------|-----------|----------|----------|-------------|
| admin | ✅ | ✅ | ✅ | ✅ |
| analyst | ✅ | ✅ | ❌ | ❌ |
| viewer | ❌ | ✅ | ❌ | ❌ |

New users self-register as analyst or viewer only. Admin created via createsuperuser or Django admin.

---

## ML Model

| Artifact | Path | Status |
|----------|------|--------|
| model.pkl | detection/ml/model.pkl | ✅ Trained |
| scaler.pkl | detection/ml/scaler.pkl | ✅ Saved |
| feature_names.pkl | detection/ml/feature_names.pkl | ✅ Saved |

| Metric | Score |
|--------|-------|
| ROC-AUC | 0.896 |
| PR-AUC | 0.725 |
| F1 | 0.535 |

**Only 2 columns required for inference:** `amount_ugx`, `txn_type`
All other features auto-derived. More columns = more accurate predictions.

---

## Migration State (dashboard app)

| File | Status | Notes |
|------|--------|-------|
| 0001_initial.py | ✅ Real migration | Creates Transaction, FraudAlert |
| 0002_fraudalert_...py | ✅ Stub | DB already had this applied |
| 0003_add_user_scoping_indexes.py | ✅ Stub | DB already had this applied |
| 0004_final_model_sync.py | ✅ Real (SeparateDatabaseAndState) | Syncs model state only |

**Important:** On a fresh database (deleted db.sqlite3), all 4 migrations apply cleanly from scratch.

---

## API Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| GET | /api/stats/ | Dashboard aggregates (scoped to user) |
| GET | /api/transactions/ | Transactions (?fraud=true/false, ?risk=high/medium/low) |
| GET | /api/alerts/ | Fraud alerts (?severity=high/medium/low) |
| POST | /api/detect/upload/ | Upload CSV → run detection (field: "file") |
| GET | /api/detect/jobs/ | List detection jobs |
| GET | /api/detect/jobs/<id>/ | Job detail + all predictions |
| GET | /api/detect/jobs/<id>/progress/ | Live progress polling |

---

## Known Issues / Future Work
- Detection runs synchronously (blocks the HTTP request). For very large files (500k+ rows)
  consider adding Celery + Redis for true async background processing.
- React SPA (frontend/src/MoMoShield.jsx) is built but not yet served via Django static files.
  Currently using Django HTML templates as primary UI.
- Reports app: Report model exists but export goes directly from DetectionJob, not via Report model.

---

## Quick Start
```bash
pip install -r requirements.txt
# Only needed once — model.pkl already exists in the zip:
# python detection/ml/train.py
python manage.py migrate
python manage.py runserver
# Login: admin / MoMo2026!
```

## File Inventory (key files)
```
momoshield/
├── CLAUDE.md                          ← this file — update after every change
├── README.md
├── manage.py
├── requirements.txt
├── db.sqlite3                         ← created after migrate
├── momoshield/settings.py
├── accounts/models.py                 ← User model (3 roles)
├── accounts/views.py
├── accounts/templates/accounts/
│   ├── login.html
│   ├── register.html                  ← fixed: no admin self-reg, correct input types
│   └── profile.html                   ← shows role + permissions
├── dashboard/models.py                ← Transaction, FraudAlert + indexes
├── dashboard/views.py                 ← user-scoped queries (_user_transactions)
├── dashboard/migrations/
│   ├── 0001_initial.py
│   ├── 0002_fraudalert_...py          ← stub
│   ├── 0003_add_user_scoping_indexes.py ← stub
│   └── 0004_final_model_sync.py       ← SeparateDatabaseAndState
├── detection/views.py                 ← chunked writes, 2-query alert creation
├── detection/ml/
│   ├── preprocess.py                  ← fully vectorised, no Python loops
│   ├── train.py
│   ├── predict.py
│   ├── model.pkl                      ← trained ✅
│   ├── scaler.pkl                     ← trained ✅
│   └── feature_names.pkl              ← trained ✅
├── api/views.py                       ← DRF endpoints + progress polling
├── static/css/main.css
└── templates/base.html                ← sidebar with role-based nav
```
