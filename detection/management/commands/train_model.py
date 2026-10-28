"""
Django management command: python manage.py train_model

Trains all three candidate models (Logistic Regression, Random Forest,
XGBoost), evaluates and compares them, and saves the best-performing
model as the production inference artefact.
"""
import sys
from pathlib import Path
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        'Train and compare Logistic Regression, Random Forest, and XGBoost '
        'fraud detection models. The best model by CV F1-score is saved for '
        'production inference.'
    )

    def handle(self, *args, **options):
        ml_dir = Path(__file__).resolve().parents[3] / 'ml'
        sys.path.insert(0, str(ml_dir))

        self.stdout.write(self.style.NOTICE(
            '\n══════════════════════════════════════════════════\n'
            '  MoMo Shield — Multi-Model Training Pipeline\n'
            '══════════════════════════════════════════════════\n'
            'Candidate models:\n'
            '  1. Logistic Regression  (baseline)\n'
            '  2. Random Forest        (ensemble / bagging)\n'
            '  3. XGBoost              (ensemble / boosting)\n'
        ))

        try:
            import os
            os.chdir(ml_dir)
            from train import train_and_save
            metrics = train_and_save()

            # ── Comparison table ──────────────────────────────────────────────
            self.stdout.write(self.style.SUCCESS(
                '\n┌──────────────────────────────────────────────────────────────┐\n'
                '│              MODEL COMPARISON — TEST SET RESULTS             │\n'
                '└──────────────────────────────────────────────────────────────┘'
            ))

            summary = metrics.get('all_models_summary', {})
            header = f"  {'Model':<24} {'AUC':>7} {'F1':>7} {'Prec':>7} {'Recall':>7} {'MCC':>7}"
            self.stdout.write(header)
            self.stdout.write('  ' + '─' * 62)

            for model_name, m in summary.items():
                marker = '  ★ ' if model_name == metrics.get('model_name') else '    '
                line = (
                    f"{marker}{model_name:<22} "
                    f"{m['test_auc']:>7.4f} "
                    f"{m['test_f1']:>7.4f} "
                    f"{m['test_precision']:>7.4f} "
                    f"{m['test_recall']:>7.4f} "
                    f"{m['test_mcc']:>7.4f}"
                )
                if model_name == metrics.get('model_name'):
                    self.stdout.write(self.style.SUCCESS(line))
                else:
                    self.stdout.write(line)

            # ── Selected model summary ────────────────────────────────────────
            self.stdout.write(self.style.SUCCESS(
                f'\n  ★  Selected for production: {metrics["model_name"]}\n'
                f'     Selection criterion: CV F1-Score (5-fold mean)\n'
                f'\n  Production model metrics:\n'
                f'     CV AUC   : {metrics["cv_auc_mean"]:.4f} ± {metrics["cv_auc_std"]:.4f}\n'
                f'     CV F1    : {metrics["cv_f1_mean"]:.4f} ± {metrics["cv_f1_std"]:.4f}\n'
                f'     Test AUC : {metrics["full_roc_auc"]:.4f}\n'
                f'     Test F1  : {metrics["full_f1"]:.4f}\n'
                f'     Precision: {metrics["precision"]:.4f}\n'
                f'     Recall   : {metrics["recall"]:.4f}\n'
                f'     MCC      : {metrics["mcc"]:.4f}\n'
                f'\n  Artifacts saved:\n'
                f'     detection/ml/model.pkl          ← production model\n'
                f'     detection/ml/scaler.pkl\n'
                f'     detection/ml/training_metrics.json\n'
                f'     detection/ml/model_comparison.json\n'
                f'     detection/ml/logistic_regression.pkl\n'
                f'     detection/ml/random_forest.pkl\n'
                f'     detection/ml/xgboost.pkl\n'
            ))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Training failed: {e}'))
            raise
