"""
Train Application Classifier

Pipeline:
  1. Load synthetic (+ real) application data
  2. Extract features using lib/feature_extraction.py
  3. Compare 5 regression models with cross-validation
  4. Train best model, compute feature importance
  5. Run bias audit
  6. Save model to models/application-scorer-v1.joblib

Run: python scripts/train_scorer.py
Requires: python scripts/generate_synthetic_apps.py (run first)
"""

import json
import os
import sys
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"

import joblib
import mlflow
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge, Lasso
from sklearn.model_selection import cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR

root = Path(__file__).resolve().parent.parent

mlflow.set_tracking_uri(f"sqlite:///{root}/mlruns.db")
mlflow.set_experiment("application-scorer")
env_file = root / ".env.local"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(root))

from lib.feature_extraction import extract_features, FEATURE_NAMES

SYNTHETIC_FILE = str(root / "models" / "synthetic_applications.json")
MODEL_OUTPUT = str(root / "models" / "application-scorer-v1.joblib")
REPORT_DIR = str(root / "reports")

MODELS = {
    "Ridge Regression": Pipeline([
        ("scaler", StandardScaler()),
        ("model", Ridge(alpha=1.0)),
    ]),
    "Lasso (feature selection)": Pipeline([
        ("scaler", StandardScaler()),
        ("model", Lasso(alpha=0.5)),
    ]),
    "Random Forest": RandomForestRegressor(
        n_estimators=100, max_depth=6, random_state=42,
    ),
    "Gradient Boosting": GradientBoostingRegressor(
        n_estimators=100, max_depth=4, learning_rate=0.1, random_state=42,
    ),
    "SVR (RBF)": Pipeline([
        ("scaler", StandardScaler()),
        ("model", SVR(kernel="rbf", C=10)),
    ]),
}


# ---------------------------------------------------------------------------
# Load and featurise data
# ---------------------------------------------------------------------------

def load_data() -> tuple[np.ndarray, np.ndarray]:
    if not os.path.exists(SYNTHETIC_FILE):
        print(f"Error: {SYNTHETIC_FILE} not found.")
        print("Run: python scripts/generate_synthetic_apps.py first")
        sys.exit(1)

    with open(SYNTHETIC_FILE) as f:
        applications = json.load(f)

    print(f"Loaded {len(applications)} applications")

    # Also load real scored applications from Supabase if available
    try:
        from supabase import create_client
        supabase = create_client(
            os.environ.get("SUPABASE_URL") or os.environ["VITE_SUPABASE_URL"],
            os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        )
        res = (
            supabase.table("applications")
            .select("business_name, business_idea, stage, ai_score, video_pitch_url")
            .not_.is_("ai_score", "null")
            .execute()
        )
        real_apps = res.data or []
        if real_apps:
            print(f"Also loaded {len(real_apps)} real scored applications from Supabase")
            applications.extend(real_apps)
    except Exception as e:
        print(f"  (Could not load real applications: {e})")

    print("Extracting features...")
    X_rows = []
    y_values = []

    for i, app in enumerate(applications):
        score = app.get("ai_score")
        if score is None:
            continue

        features = extract_features(app)
        row = [features.get(name, 0) for name in FEATURE_NAMES]
        X_rows.append(row)
        y_values.append(score)

        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(applications)} featurised")

    X = np.array(X_rows, dtype=np.float64)
    y = np.array(y_values, dtype=np.float64)
    print(f"Feature matrix: {X.shape[0]} samples x {X.shape[1]} features")
    return X, y


# ---------------------------------------------------------------------------
# Model comparison
# ---------------------------------------------------------------------------

def compare_models(X: np.ndarray, y: np.ndarray) -> str:
    print(f"\nModel Comparison \u2014 5-Fold Cross-Validation")
    print("\u2550" * 65)
    print(f"{'Model':30s} {'MAE':>12s} {'R\u00b2':>16s}")
    print("\u2500" * 65)

    best_name = ""
    best_mae = float("inf")

    for name, model in MODELS.items():
        mae_scores = cross_val_score(model, X, y, cv=5, scoring="neg_mean_absolute_error")
        r2_scores = cross_val_score(model, X, y, cv=5, scoring="r2")

        mae = -mae_scores.mean()
        mae_std = mae_scores.std()
        r2 = r2_scores.mean()
        r2_std = r2_scores.std()

        # Log each model as a child run
        with mlflow.start_run(run_name=name, nested=True):
            mlflow.log_params({"model_name": name})
            mlflow.log_metrics({"mae": mae, "mae_std": mae_std, "r2": r2, "r2_std": r2_std})

        marker = ""
        if mae < best_mae:
            best_mae = mae
            best_name = name
            marker = " \u2605"

        print(f"{name:30s} {mae:>5.1f} \u00b1 {mae_std:<5.1f} {r2:>7.3f} \u00b1 {r2_std:<5.3f}{marker}")

    print("\u2550" * 65)
    print(f"\nWinner: {best_name} (lowest MAE: {best_mae:.1f})")
    return best_name


# ---------------------------------------------------------------------------
# Train final model + feature importance
# ---------------------------------------------------------------------------

def train_final(X: np.ndarray, y: np.ndarray, model_name: str):
    print(f"\nTraining final model: {model_name}...")

    model = MODELS[model_name]
    model.fit(X, y)

    # Feature importance
    if hasattr(model, "feature_importances_"):
        importances = model.feature_importances_
    elif hasattr(model, "named_steps") and hasattr(model.named_steps.get("model", None), "coef_"):
        importances = np.abs(model.named_steps["model"].coef_)
    else:
        importances = None

    if importances is not None:
        print(f"\nFeature Importance:")
        ranked = sorted(zip(FEATURE_NAMES, importances), key=lambda x: -x[1])
        for name, imp in ranked:
            bar = "\u2588" * int(imp * 100)
            print(f"  {imp:.3f}  {name:30s} {bar}")

    # Save model
    os.makedirs(os.path.dirname(MODEL_OUTPUT), exist_ok=True)
    joblib.dump(model, MODEL_OUTPUT)
    print(f"\nModel saved to {MODEL_OUTPUT}")

    return model


# ---------------------------------------------------------------------------
# Bias audit
# ---------------------------------------------------------------------------

def bias_audit(model, X: np.ndarray):
    print(f"\nBias Audit")
    print("\u2550" * 60)

    if hasattr(model, "feature_importances_"):
        importances = dict(zip(FEATURE_NAMES, model.feature_importances_))
    elif hasattr(model, "named_steps") and hasattr(model.named_steps.get("model", None), "coef_"):
        importances = dict(zip(FEATURE_NAMES, np.abs(model.named_steps["model"].coef_)))
    else:
        print("  Cannot extract feature importances for bias audit.")
        return

    style_features = ["word_count", "avg_sentence_length", "vocabulary_richness"]
    substance_features = [
        "has_validation_mention", "has_problem_mention", "has_customer_mention",
        "has_traction_mention", "rubric_spread",
    ]

    style_imp = sum(importances.get(f, 0) for f in style_features)
    substance_imp = sum(importances.get(f, 0) for f in substance_features)

    print(f"  Style features importance:     {style_imp:.1%}")
    print(f"  Substance features importance: {substance_imp:.1%}")

    if style_imp > substance_imp:
        print("  \u26a0  WARNING: Style outweighs substance. May penalise non-native speakers.")
    else:
        print("  \u2713 Substance outweighs style. Good.")

    # Test pairs: same idea, different writing styles
    BIAS_PAIRS = [
        (
            {"business_idea": "We solve payment friction for small merchants in Lagos.", "stage": "mvp"},
            {"business_idea": "Our company, leveraging cutting-edge fintech infrastructure, addresses the multifaceted challenges of payment processing for SMEs in emerging markets.", "stage": "mvp"},
        ),
        (
            {"business_idea": "App that connects local farmers to restaurants. Tested with 5 restaurants, they want it.", "stage": "mvp"},
            {"business_idea": "A sophisticated farm-to-table marketplace platform facilitating seamless B2B procurement between agricultural producers and hospitality establishments, with initial validation.", "stage": "mvp"},
        ),
    ]

    print(f"\n  Writing Style Bias Check:")
    for simple_app, verbose_app in BIAS_PAIRS:
        simple_feat = [extract_features(simple_app).get(n, 0) for n in FEATURE_NAMES]
        verbose_feat = [extract_features(verbose_app).get(n, 0) for n in FEATURE_NAMES]

        simple_score = model.predict([simple_feat])[0]
        verbose_score = model.predict([verbose_feat])[0]
        diff = abs(simple_score - verbose_score)

        print(f"    Simple: {simple_score:.0f}, Verbose: {verbose_score:.0f}, Gap: {diff:.0f}", end="")
        if diff > 10:
            print(" \u26a0 >10 point gap")
        else:
            print(" \u2713")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Application Classifier Training Pipeline")
    print("=" * 60)

    X, y = load_data()

    with mlflow.start_run():
        mlflow.log_params({
            "num_samples": X.shape[0],
            "num_features": X.shape[1],
        })

        winner = compare_models(X, y)
        model = train_final(X, y, winner)
        bias_audit(model, X)

        mlflow.log_param("winning_model", winner)
        mlflow.sklearn.log_model(model, "application-scorer")

        # Quick prediction test
        print(f"\nSample Predictions:")
        test_apps = [
            {"business_idea": "I want to make an app.", "stage": "idea"},
            {"business_idea": "We help small restaurants reduce food waste by connecting them with local food banks. Talked to 20 restaurants, 15 said they'd pay $50/month.", "stage": "mvp"},
        ]
        for app in test_apps:
            feat = [extract_features(app).get(n, 0) for n in FEATURE_NAMES]
            score = model.predict([feat])[0]
            print(f"  Score {score:.0f}: {app['business_idea'][:60]}...")

    print("\nDone.")


if __name__ == "__main__":
    main()
