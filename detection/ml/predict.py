"""
MoMo Shield — Inference Engine
================================
Loads the production model (whichever was selected as best during training)
and exposes prediction utilities. All comparison metrics are also exposed
so the dashboard can display them.
"""
import pickle, logging, json
from pathlib import Path

import numpy as np
import pandas as pd

ML_DIR = Path(__file__).parent
logger = logging.getLogger(__name__)

FRAUD_THRESHOLD = 0.5

_model  = None
_scaler = None


def _load_artifacts():
    global _model, _scaler
    if _model is None:
        model_path  = ML_DIR / 'model.pkl'
        scaler_path = ML_DIR / 'scaler.pkl'
        if not model_path.exists():
            raise FileNotFoundError(
                "model.pkl not found. Run 'python manage.py train_model' first."
            )
        with open(model_path,  'rb') as f:
            _model  = pickle.load(f)
        with open(scaler_path, 'rb') as f:
            _scaler = pickle.load(f)
        logger.info("ML artifacts loaded from disk")
    return _model, _scaler


def predict_dataframe(X_features: pd.DataFrame) -> dict:
    """
    Run fraud prediction on a preprocessed feature dataframe.

    Returns:
        {
            'probabilities': list[float],
            'predictions':   list[int],
            'fraud_count':   int,
            'total':         int,
        }
    """
    model, scaler = _load_artifacts()
    X_scaled = scaler.transform(X_features)
    probs    = model.predict_proba(X_scaled)[:, 1]
    preds    = (probs >= FRAUD_THRESHOLD).astype(int)
    return {
        'probabilities': probs.tolist(),
        'predictions':   preds.tolist(),
        'fraud_count':   int(preds.sum()),
        'total':         len(preds),
    }


def get_fraud_reason(row: dict, fraud_score: float) -> str:
    """Generate a human-readable explanation for a fraud flag."""
    risk_label = (
        "HIGH RISK"   if fraud_score >= 0.75 else
        "MEDIUM RISK" if fraud_score >= 0.40 else
        "LOW RISK"
    )
    reasons = []
    if row.get('receiver_previously_flagged'):
        reasons.append("Receiver account has been previously flagged for fraud")
    if row.get('is_new_receiver'):
        reasons.append("First transaction to this receiver")
    if row.get('sender_account_age_days', 365) < 30:
        reasons.append("Sender account is less than 30 days old")
    if row.get('amount_ugx', 0) > 1_000_000:
        reasons.append(f"High-value transaction (UGX {row['amount_ugx']:,.0f})")
    if row.get('sender_txn_count_1h', 0) > 3:
        reasons.append(f"High velocity: {row['sender_txn_count_1h']} txns in 1 hour")
    h = row.get('hour', 12)
    if h >= 22 or h <= 5:
        reasons.append(f"Unusual transaction hour ({h}:00)")
    if row.get('amount_deviation', 0) > 2:
        reasons.append("Amount deviates significantly from sender's historical average")
    if not reasons:
        reasons.append(f"Model score: {fraud_score:.2%}")
    return f"[{risk_label}] {'; '.join(reasons)}"


def model_loaded() -> bool:
    try:
        _load_artifacts()
        return True
    except FileNotFoundError:
        return False


def get_training_metrics() -> dict:
    """Return best-model metrics. Falls back to empty dict if not trained."""
    p = ML_DIR / 'training_metrics.json'
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return {}


def get_model_comparison() -> dict:
    """Return full multi-model comparison data."""
    p = ML_DIR / 'model_comparison.json'
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return {}
