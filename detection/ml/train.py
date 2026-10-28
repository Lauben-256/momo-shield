"""
MoMo Shield — Multi-Model Training & Comparison Pipeline
=========================================================
Trains three classifiers on the same SMOTE-balanced data:
  1. Logistic Regression  (baseline / linear)
  2. Random Forest        (ensemble / bagging)
  3. XGBoost              (ensemble / boosting) ← selected for production

All three are evaluated with stratified 5-fold CV and on a held-out
20% test split. The best model by CV F1-score is automatically saved
as model.pkl for inference; all comparison metrics are saved to
model_comparison.json and training_metrics.json.

Run standalone:
    cd detection/ml && python train.py

Or via Django:
    python manage.py train_model
"""

import os, sys, json, pickle, logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    classification_report, roc_auc_score, f1_score,
    precision_score, recall_score, confusion_matrix,
    matthews_corrcoef, average_precision_score,
)
from xgboost import XGBClassifier
from imblearn.over_sampling import SMOTE

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format='%(asctime)s  %(levelname)s  %(message)s')
logger = logging.getLogger(__name__)

ML_DIR   = Path(__file__).parent
DATA_CSV = ML_DIR / 'momo_shield_training_data.csv'

# ── Scoring metrics used in cross-validation ─────────────────────────────────
CV_SCORING = {
    'roc_auc':   'roc_auc',
    'f1':        'f1',
    'precision': 'precision',
    'recall':    'recall',
}

CV_FOLDS = 5


def _build_models():
    """Return the three candidate models with tuned hyperparameters."""
    return {
        'Logistic Regression': LogisticRegression(
            C=0.1,
            max_iter=1000,
            solver='lbfgs',
            class_weight='balanced',   # handles residual imbalance after SMOTE
            random_state=42,
            n_jobs=-1,
        ),
        'Random Forest': RandomForestClassifier(
            n_estimators=300,
            max_depth=12,
            min_samples_leaf=4,
            class_weight='balanced',
            random_state=42,
            n_jobs=-1,
        ),
        'XGBoost': XGBClassifier(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            use_label_encoder=False,
            eval_metric='logloss',
            random_state=42,
            n_jobs=-1,
        ),
    }


def _evaluate_on_test(model, X_test_scaled, y_test, model_name):
    """Compute full evaluation metrics on the held-out test set."""
    y_pred = model.predict(X_test_scaled)
    y_prob = model.predict_proba(X_test_scaled)[:, 1]

    cm = confusion_matrix(y_test, y_pred)
    tn, fp, fn, tp = cm.ravel()

    metrics = {
        'roc_auc':          round(roc_auc_score(y_test, y_prob), 4),
        'avg_precision':    round(average_precision_score(y_test, y_prob), 4),
        'f1':               round(f1_score(y_test, y_pred), 4),
        'precision':        round(precision_score(y_test, y_pred), 4),
        'recall':           round(recall_score(y_test, y_pred), 4),
        'mcc':              round(float(matthews_corrcoef(y_test, y_pred)), 4),
        'confusion_matrix': {'tn': int(tn), 'fp': int(fp), 'fn': int(fn), 'tp': int(tp)},
        'classification_report': classification_report(y_test, y_pred,
                                    target_names=['Legit', 'Fraud']),
    }

    logger.info(f"\n{'='*60}")
    logger.info(f"  TEST SET RESULTS — {model_name}")
    logger.info(f"{'='*60}")
    logger.info(f"  ROC-AUC:       {metrics['roc_auc']}")
    logger.info(f"  Avg Precision: {metrics['avg_precision']}")
    logger.info(f"  F1-Score:      {metrics['f1']}")
    logger.info(f"  Precision:     {metrics['precision']}")
    logger.info(f"  Recall:        {metrics['recall']}")
    logger.info(f"  MCC:           {metrics['mcc']}")
    logger.info(f"  Confusion Matrix:  TN={tn}  FP={fp}  FN={fn}  TP={tp}")
    logger.info(f"\n{metrics['classification_report']}")
    return metrics


def train_and_save():
    from preprocess import preprocess_training_data, validate_training_csv

    logger.info("=" * 60)
    logger.info("  MoMo Shield — Multi-Model Training Pipeline")
    logger.info("=" * 60)

    # ── 1. Load & validate ───────────────────────────────────────────────────
    logger.info(f"Loading data from: {DATA_CSV}")
    df = pd.read_csv(DATA_CSV)
    logger.info(f"Loaded {len(df):,} rows")

    report = validate_training_csv(df)
    if not report['valid']:
        for err in report['errors']:
            logger.error(err)
        raise ValueError("Training data validation failed")
    for w in report.get('warnings', []):
        logger.warning(w)
    logger.info(f"Class distribution: {report['class_distribution']}")
    logger.info(f"Fraud rate: {report['fraud_pct']}%")

    # ── 2. Preprocess ────────────────────────────────────────────────────────
    X_full, y_full, prep_log = preprocess_training_data(df)
    for line in prep_log:
        logger.info(line)
    logger.info(f"Feature matrix shape: {X_full.shape}")

    # ── 3. Train/test split (stratified) ────────────────────────────────────
    X_train_raw, X_test_raw, y_train, y_test = train_test_split(
        X_full, y_full, test_size=0.20, stratify=y_full, random_state=42
    )
    logger.info(f"Train: {len(X_train_raw):,} rows  |  Test: {len(X_test_raw):,} rows")

    # ── 4. Scale ─────────────────────────────────────────────────────────────
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train_raw)
    X_test_scaled  = scaler.transform(X_test_raw)

    # ── 5. SMOTE on training set only ────────────────────────────────────────
    logger.info("Applying SMOTE to training set...")
    sm = SMOTE(random_state=42, k_neighbors=min(5, y_train.sum() - 1))
    X_train_res, y_train_res = sm.fit_resample(X_train_scaled, y_train)
    logger.info(
        f"After SMOTE: {X_train_res.shape[0]:,} rows  "
        f"(fraud={y_train_res.sum():,}, legit={len(y_train_res)-y_train_res.sum():,})"
    )

    # ── 6. Initialise models ─────────────────────────────────────────────────
    models = _build_models()
    cv     = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=42)

    comparison   = {}   # full comparison table
    cv_results   = {}   # cross-val scores per model
    test_results = {}   # held-out test metrics per model

    # ── 7. Train & evaluate each model ──────────────────────────────────────
    for name, model in models.items():
        logger.info(f"\n{'─'*60}")
        logger.info(f"  Training: {name}")
        logger.info(f"{'─'*60}")

        # Fit on SMOTE-balanced training set
        model.fit(X_train_res, y_train_res)

        # Cross-validate on original (unbalanced) scaled training set
        logger.info(f"  Running {CV_FOLDS}-fold CV on original training data...")
        cv_scores = cross_validate(
            model, X_train_scaled, y_train,
            cv=cv, scoring=CV_SCORING, n_jobs=-1
        )
        cv_results[name] = {
            metric: {
                'mean': round(float(cv_scores[f'test_{metric}'].mean()), 4),
                'std':  round(float(cv_scores[f'test_{metric}'].std()),  4),
            }
            for metric in CV_SCORING
        }
        logger.info(
            f"  CV AUC  : {cv_results[name]['roc_auc']['mean']:.4f} "
            f"± {cv_results[name]['roc_auc']['std']:.4f}"
        )
        logger.info(
            f"  CV F1   : {cv_results[name]['f1']['mean']:.4f} "
            f"± {cv_results[name]['f1']['std']:.4f}"
        )
        logger.info(
            f"  CV Prec : {cv_results[name]['precision']['mean']:.4f}  "
            f"CV Recall: {cv_results[name]['recall']['mean']:.4f}"
        )

        # Evaluate on held-out test set
        test_results[name] = _evaluate_on_test(model, X_test_scaled, y_test, name)

        comparison[name] = {
            'cv':   cv_results[name],
            'test': {k: v for k, v in test_results[name].items()
                     if k != 'classification_report'},
        }

    # ── 8. Summary comparison table ──────────────────────────────────────────
    logger.info(f"\n{'='*60}")
    logger.info("  MODEL COMPARISON SUMMARY (test set)")
    logger.info(f"{'='*60}")
    header = f"{'Model':<22} {'AUC':>7} {'F1':>7} {'Prec':>7} {'Recall':>7} {'MCC':>7}"
    logger.info(header)
    logger.info('-' * len(header))
    for name, res in test_results.items():
        logger.info(
            f"{name:<22} {res['roc_auc']:>7.4f} {res['f1']:>7.4f} "
            f"{res['precision']:>7.4f} {res['recall']:>7.4f} {res['mcc']:>7.4f}"
        )

    # ── 9. Select best model by CV F1 ────────────────────────────────────────
    best_name = max(cv_results, key=lambda n: cv_results[n]['f1']['mean'])
    best_model = models[best_name]
    logger.info(f"\n  SELECTED FOR PRODUCTION: {best_name} "
                f"(CV F1 = {cv_results[best_name]['f1']['mean']:.4f})")

    # ── 10. Feature importances (tree models only) ───────────────────────────
    feat_names   = list(X_full.columns)
    importances  = {}
    if hasattr(best_model, 'feature_importances_'):
        importances = dict(zip(feat_names, best_model.feature_importances_.tolist()))
        top10 = sorted(importances.items(), key=lambda x: x[1], reverse=True)[:10]
        logger.info("\n  Top 10 features:")
        for feat, imp in top10:
            logger.info(f"    {feat:<40} {imp:.4f}")

    # ── 11. Save artifacts ────────────────────────────────────────────────────
    with open(ML_DIR / 'model.pkl', 'wb') as f:
        pickle.dump(best_model, f)
    with open(ML_DIR / 'scaler.pkl', 'wb') as f:
        pickle.dump(scaler, f)

    # Save all individual model objects for optional later use
    for name, model in models.items():
        safe_name = name.lower().replace(' ', '_')
        with open(ML_DIR / f'{safe_name}.pkl', 'wb') as f:
            pickle.dump(model, f)
    logger.info("  Saved: model.pkl, scaler.pkl, logistic_regression.pkl, "
                "random_forest.pkl, xgboost.pkl")

    # ── 12. Save metrics JSONs ────────────────────────────────────────────────
    model_comparison = {
        'models': comparison,
        'best_model': best_name,
        'selection_criterion': 'CV F1-Score (mean across 5 folds)',
        'training_rows': int(len(df)),
        'test_rows':     int(len(y_test)),
        'fraud_rate_pct': float(report['fraud_pct']),
        'cv_folds': CV_FOLDS,
        'feature_cols': feat_names,
    }
    with open(ML_DIR / 'model_comparison.json', 'w') as f:
        json.dump(model_comparison, f, indent=2)

    # Backward-compatible training_metrics.json (best model's stats)
    training_metrics = {
        'model_name':       best_name,
        'cv_auc_mean':      cv_results[best_name]['roc_auc']['mean'],
        'cv_auc_std':       cv_results[best_name]['roc_auc']['std'],
        'cv_f1_mean':       cv_results[best_name]['f1']['mean'],
        'cv_f1_std':        cv_results[best_name]['f1']['std'],
        'full_roc_auc':     test_results[best_name]['roc_auc'],
        'full_f1':          test_results[best_name]['f1'],
        'precision':        test_results[best_name]['precision'],
        'recall':           test_results[best_name]['recall'],
        'mcc':              test_results[best_name]['mcc'],
        'avg_precision':    test_results[best_name]['avg_precision'],
        'confusion_matrix': test_results[best_name]['confusion_matrix'],
        'training_rows':    int(len(df)),
        'fraud_rate_pct':   float(report['fraud_pct']),
        'feature_importances': importances,
        'feature_cols':     feat_names,
        'all_models_summary': {
            name: {
                'cv_f1_mean':  cv_results[name]['f1']['mean'],
                'cv_auc_mean': cv_results[name]['roc_auc']['mean'],
                'test_f1':     test_results[name]['f1'],
                'test_auc':    test_results[name]['roc_auc'],
                'test_precision': test_results[name]['precision'],
                'test_recall':    test_results[name]['recall'],
                'test_mcc':       test_results[name]['mcc'],
            }
            for name in models
        },
    }
    with open(ML_DIR / 'training_metrics.json', 'w') as f:
        json.dump(training_metrics, f, indent=2)

    logger.info("  Saved: model_comparison.json, training_metrics.json")
    logger.info("=" * 60)
    logger.info("  Training pipeline complete.")
    logger.info("=" * 60)

    return training_metrics


if __name__ == '__main__':
    os.chdir(ML_DIR)
    train_and_save()
