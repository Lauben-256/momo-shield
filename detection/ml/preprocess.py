"""
MoMo Shield — Preprocessing & Feature Engineering
===================================================
Two modes:

  INFERENCE MODE (preprocess_inference_data):
      Produces the exact 13-feature set that the shipped model.pkl / scaler.pkl
      were trained on:
          amount_ugx, is_weekend, hour, sender_account_age_days,
          receiver_account_age_days, is_new_receiver, sender_txn_count_1h,
          sender_txn_count_24h, amount_deviation, receiver_previously_flagged,
          round_amount, txn_type_encoded, channel_encoded

  TRAINING MODE (preprocess_training_data):
      Produces the full 26-feature set (one-hot encoded) used by train.py when
      retraining all three candidate models from scratch. A new scaler is saved
      at that point, so the two feature sets stay consistent with their
      respective model/scaler pair.
"""
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

# ── Feature set used by the SHIPPED model / scaler (inference) ───────────────
INFERENCE_FEATURE_COLS = [
    'amount_ugx', 'is_weekend', 'hour', 'sender_account_age_days',
    'receiver_account_age_days', 'is_new_receiver', 'sender_txn_count_1h',
    'sender_txn_count_24h', 'amount_deviation', 'receiver_previously_flagged',
    'round_amount', 'txn_type_encoded', 'channel_encoded',
]

# ── Label-encoding maps matching the original training ───────────────────────
TXN_TYPE_MAP = {
    'Send Money':     0,
    'Withdraw':       1,
    'Deposit':        2,
    'Pay Bill':       3,
    'Airtime':        4,
    'Buy Goods':      5,
    'Bank Transfer':  6,
}
CHANNEL_MAP = {
    'App':   0,
    'USSD':  1,
    'Agent': 2,
}

# ── Full feature set used when retraining (train.py) ─────────────────────────
TRAINING_FEATURE_COLS = [
    'amount_ugx', 'is_weekend', 'hour', 'sender_account_age_days',
    'receiver_account_age_days', 'is_new_receiver', 'sender_txn_count_1h',
    'sender_txn_count_24h', 'amount_deviation', 'receiver_previously_flagged',
    'round_amount',
    'amount_log', 'high_value_flag', 'night_txn', 'sender_age_bucket',
    'velocity_ratio',
    'txn_type_Airtime', 'txn_type_Bank Transfer', 'txn_type_Buy Goods',
    'txn_type_Deposit', 'txn_type_Pay Bill', 'txn_type_Send Money',
    'txn_type_Withdraw',
    'channel_Agent', 'channel_App', 'channel_USSD',
]

TRAINING_CSV_COLUMNS = [
    'txn_id', 'sender', 'receiver', 'amount_ugx', 'txn_type', 'time',
    'day_of_week', 'is_weekend', 'hour', 'channel', 'sender_account_age_days',
    'receiver_account_age_days', 'is_new_receiver', 'sender_txn_count_1h',
    'sender_txn_count_24h', 'amount_deviation', 'receiver_previously_flagged',
    'round_amount', 'label',
]

INFERENCE_REQUIRED_COLS = [
    'amount_ugx', 'txn_type', 'hour', 'channel',
    'sender_account_age_days', 'receiver_account_age_days',
]


# ── Validation ───────────────────────────────────────────────────────────────

def validate_training_csv(df: pd.DataFrame) -> dict:
    report = {'valid': True, 'errors': [], 'warnings': [], 'rows': len(df)}
    for col in TRAINING_CSV_COLUMNS:
        if col not in df.columns:
            report['errors'].append(f"Missing required column: {col}")
            report['valid'] = False
    if report['valid']:
        if df['label'].nunique() < 2:
            report['warnings'].append("Only one class found in label column")
        null_counts = df.isnull().sum()
        for col, cnt in null_counts.items():
            if cnt > 0:
                report['warnings'].append(f"Column '{col}' has {cnt} null values")
        fraud_pct = df['label'].mean() * 100
        report['fraud_pct'] = round(fraud_pct, 2)
        report['class_distribution'] = df['label'].value_counts().to_dict()
    return report


def validate_inference_csv(df: pd.DataFrame) -> dict:
    report = {'valid': True, 'errors': [], 'warnings': [], 'rows': len(df)}
    for col in INFERENCE_REQUIRED_COLS:
        if col not in df.columns:
            report['errors'].append(f"Missing required column: {col}")
            report['valid'] = False
    return report


# ── Shared feature engineering helpers ───────────────────────────────────────

def _fill_defaults(df: pd.DataFrame) -> pd.DataFrame:
    defaults = {
        'is_weekend': 0, 'sender_account_age_days': 365,
        'receiver_account_age_days': 365, 'is_new_receiver': 0,
        'sender_txn_count_1h': 1, 'sender_txn_count_24h': 1,
        'amount_deviation': 0.0, 'receiver_previously_flagged': 0,
        'round_amount': 0,
    }
    for col, val in defaults.items():
        if col not in df.columns:
            df[col] = val
    return df


def _coerce_numerics(df: pd.DataFrame) -> pd.DataFrame:
    df['amount_ugx'] = pd.to_numeric(df['amount_ugx'], errors='coerce').fillna(0)
    df['hour']       = pd.to_numeric(df.get('hour', 12), errors='coerce').fillna(12).astype(int)
    return df


def _label_encode(df: pd.DataFrame) -> pd.DataFrame:
    """Label-encode txn_type and channel — matches the shipped scaler."""
    df = df.copy()
    df['txn_type_encoded'] = df['txn_type'].map(TXN_TYPE_MAP).fillna(0).astype(int)
    df['channel_encoded']  = df['channel'].map(CHANNEL_MAP).fillna(1).astype(int)
    return df


def _one_hot_encode(df: pd.DataFrame) -> pd.DataFrame:
    """One-hot encode txn_type and channel — used when retraining."""
    df = df.copy()
    txn_dummies = pd.get_dummies(df['txn_type'], prefix='txn_type')
    ch_dummies  = pd.get_dummies(df['channel'],   prefix='channel')
    return pd.concat([df, txn_dummies, ch_dummies], axis=1)


def _engineer_extended_features(df: pd.DataFrame) -> pd.DataFrame:
    """Additional engineered features used only during retraining."""
    df = df.copy()
    df['amount_log']        = np.log1p(df['amount_ugx'].clip(lower=0))
    df['high_value_flag']   = (df['amount_ugx'] > 1_000_000).astype(int)
    df['night_txn']         = df['hour'].apply(lambda h: 1 if h >= 22 or h <= 5 else 0)
    df['sender_age_bucket'] = df['sender_account_age_days'].apply(
        lambda d: 0 if d < 30 else (1 if d < 180 else 2)
    )
    df['velocity_ratio']    = df['sender_txn_count_1h'] / (df['sender_txn_count_24h'] + 1)
    return df


def _align(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    for col in cols:
        if col not in df.columns:
            df[col] = 0
    return df[cols]


# ── Public API ────────────────────────────────────────────────────────────────

def preprocess_inference_data(df: pd.DataFrame):
    """
    Preprocess an uploaded CSV for inference against the SHIPPED model.
    Returns (X_features [13 cols], df_enriched).
    """
    df = df.copy()
    df = _fill_defaults(df)
    df = _coerce_numerics(df)
    df = _label_encode(df)
    X  = _align(df.copy(), INFERENCE_FEATURE_COLS)
    return X, df


def preprocess_training_data(df: pd.DataFrame):
    """
    Full pipeline for retraining. Returns (X [26 cols], y, log_lines).
    train.py saves a new scaler that matches this feature set.
    """
    log = []
    before = len(df)
    df = df.drop_duplicates(subset='txn_id')
    dropped = before - len(df)
    if dropped:
        log.append(f"Dropped {dropped} duplicate rows")

    df = df.fillna({'amount_deviation': 0.0, 'sender_txn_count_1h': 1, 'sender_txn_count_24h': 1})
    df = df.dropna(subset=['amount_ugx', 'txn_type', 'channel', 'label'])
    log.append(f"Rows after null handling: {len(df)}")

    df['amount_ugx'] = pd.to_numeric(df['amount_ugx'], errors='coerce').fillna(0)
    df['label']      = df['label'].astype(int)

    df = _engineer_extended_features(df)
    df = _one_hot_encode(df)

    y = df['label'].values
    X = _align(df, TRAINING_FEATURE_COLS)

    log.append(f"Training set: {len(X)} rows, {round(y.mean()*100, 2)}% fraud")
    return X, y, log
