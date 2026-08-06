"""
Train XGBoost models for:
  (1) flood_severity classification (multi-class)
  (2) resource_demand_units regression

Evaluate each against a simple baseline model:
  - Classification baseline: Logistic Regression (multinomial, scaled features)
  - Regression baseline:     Linear Regression

CHANGELOG vs v1 (schema-compliance pass, Phase 2):
  - Replaced sklearn.LabelEncoder with CanonicalSeverityEncoder from
    src/q_rescue/ai/label_mapper.py. LabelEncoder.fit() sorts classes
    alphabetically ("High"=0,"Low"=1,"Moderate"=2,"Severe"=3), which
    silently disagreed with the canonical map in schema §1
    ("Low"=0,"Moderate"=1,"High"=2,"Severe"=3). Aggregate metrics
    (accuracy/F1) were unaffected by this (label-permutation invariant),
    but the per-class report, confusion matrix, and any consumer trusting
    flood_severity_int (M1's QUBO builder!) would have been silently wrong.
  - Feature order is asserted against EXPECTED_FEATURES (schema §2.1)
    before training, instead of being inferred implicitly from CSV
    column order.
  - Saves outputs/normalization.json with the training-set min/max of
    resource_demand_units, used by predictor.py to compute
    resource_demand_normalised = (value - min) / (max - min), per §2.2
    and M5's Week 2 task list.
  - Output paths now follow the schema's file contract (§3.1) exactly:
    flood_xgboost_project/data/flood_dataset.csv,
    flood_xgboost_project/outputs/{xgb_severity_classifier,
    xgb_resource_regressor,label_encoder}.joblib
"""

import json
import sys
import warnings
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import joblib
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier, XGBRegressor

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]  # flood_xgboost_project/
REPO_ROOT = ROOT.parent  # repo root (contains src/)
sys.path.insert(0, str(REPO_ROOT / "src"))

from q_rescue.ai.label_mapper import SEVERITY_ORDER, CanonicalSeverityEncoder  # noqa: E402
from q_rescue.ai.validation import EXPECTED_FEATURES  # noqa: E402

DATA_PATH = ROOT / "data" / "flood_dataset.csv"
CHART_DIR = ROOT / "charts"
OUT_DIR = ROOT / "outputs"
CHART_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(parents=True, exist_ok=True)

sns.set_theme(style="whitegrid", font_scale=1.0)
PALETTE = {"XGBoost": "#1f6feb", "Baseline": "#94a3b8"}

# ----------------------------------------------------------------------
# 1. Load data, validate schema compliance, split
# ----------------------------------------------------------------------
df = pd.read_csv(DATA_PATH)

feature_cols = [c for c in df.columns if c not in ("flood_severity", "resource_demand_units")]
assert feature_cols == EXPECTED_FEATURES, (
    "flood_dataset.csv feature columns do not match the schema §2.1 FloodObservation "
    f"order.\nExpected: {EXPECTED_FEATURES}\nGot:      {feature_cols}"
)
FEATURES = EXPECTED_FEATURES

X = df[FEATURES]
y_clf_raw = df["flood_severity"]
y_reg = df["resource_demand_units"]

assert set(y_clf_raw.unique()) == set(SEVERITY_ORDER), (
    f"flood_severity values {sorted(y_clf_raw.unique())} do not match canonical "
    f"severity labels {SEVERITY_ORDER}"
)

# Canonical encoder: Low=0, Moderate=1, High=2, Severe=3 (schema §1) —
# NOT sklearn.LabelEncoder, which would sort alphabetically instead.
le = CanonicalSeverityEncoder()
y_clf = le.transform(y_clf_raw)

X_train, X_test, yclf_train, yclf_test, yreg_train, yreg_test = train_test_split(
    X, y_clf, y_reg, test_size=0.2, random_state=42, stratify=y_clf
)

# ----------------------------------------------------------------------
# 2. CLASSIFICATION: flood severity
# ----------------------------------------------------------------------
xgb_clf = XGBClassifier(
    n_estimators=300,
    max_depth=5,
    learning_rate=0.08,
    subsample=0.85,
    colsample_bytree=0.85,
    reg_lambda=1.0,
    objective="multi:softprob",
    num_class=4,
    eval_metric="mlogloss",
    random_state=42,
    n_jobs=-1,
)
xgb_clf.fit(X_train, yclf_train)
pred_xgb_clf = xgb_clf.predict(X_test)

scaler = StandardScaler()
Xtr_s = scaler.fit_transform(X_train)
Xte_s = scaler.transform(X_test)
baseline_clf = LogisticRegression(max_iter=2000)
baseline_clf.fit(Xtr_s, yclf_train)
pred_base_clf = baseline_clf.predict(Xte_s)


def clf_metrics(y_true, y_pred):
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "macro_f1": f1_score(y_true, y_pred, average="macro"),
        "weighted_f1": f1_score(y_true, y_pred, average="weighted"),
        "macro_precision": precision_score(y_true, y_pred, average="macro"),
        "macro_recall": recall_score(y_true, y_pred, average="macro"),
    }


metrics_xgb_clf = clf_metrics(yclf_test, pred_xgb_clf)
metrics_base_clf = clf_metrics(yclf_test, pred_base_clf)

# target_names indexed 0..3 MUST follow the canonical order, which is now
# guaranteed to match the encoded ints because we no longer use LabelEncoder.
report_xgb = classification_report(
    yclf_test,
    pred_xgb_clf,
    labels=[0, 1, 2, 3],
    target_names=SEVERITY_ORDER,
    output_dict=True,
    zero_division=0,
)
report_base = classification_report(
    yclf_test,
    pred_base_clf,
    labels=[0, 1, 2, 3],
    target_names=SEVERITY_ORDER,
    output_dict=True,
    zero_division=0,
)

# ----------------------------------------------------------------------
# 3. REGRESSION: resource demand
# ----------------------------------------------------------------------
xgb_reg = XGBRegressor(
    n_estimators=400,
    max_depth=5,
    learning_rate=0.06,
    subsample=0.85,
    colsample_bytree=0.85,
    reg_lambda=1.0,
    objective="reg:squarederror",
    random_state=42,
    n_jobs=-1,
)
xgb_reg.fit(X_train, yreg_train)
pred_xgb_reg = xgb_reg.predict(X_test)

baseline_reg = LinearRegression()
baseline_reg.fit(Xtr_s, yreg_train)
pred_base_reg = baseline_reg.predict(Xte_s)


def reg_metrics(y_true, y_pred):
    mse = mean_squared_error(y_true, y_pred)
    return {
        "mae": mean_absolute_error(y_true, y_pred),
        "rmse": float(np.sqrt(mse)),
        "r2": r2_score(y_true, y_pred),
    }


metrics_xgb_reg = reg_metrics(yreg_test, pred_xgb_reg)
metrics_base_reg = reg_metrics(yreg_test, pred_base_reg)

# resource_demand_normalised uses TRAINING SET statistics (per M5 Week 2
# task list), not test-set or full-dataset stats, so normalisation is
# well-defined for genuinely unseen live inference data too.
demand_min = float(yreg_train.min())
demand_max = float(yreg_train.max())
normalization = {
    "resource_demand_units": {
        "min": demand_min,
        "max": demand_max,
        "computed_from": "training_set",
        "n_train": len(yreg_train),
    }
}
with open(OUT_DIR / "normalization.json", "w") as f:
    json.dump(normalization, f, indent=2)

# ----------------------------------------------------------------------
# 4. Save consolidated metrics
# ----------------------------------------------------------------------
all_metrics = {
    "schema_version": "1.0",
    "model_version": "xgb_severity_v1",
    "classification": {
        "xgboost": metrics_xgb_clf,
        "baseline_logreg": metrics_base_clf,
        "xgboost_per_class": report_xgb,
        "baseline_per_class": report_base,
        "class_order": SEVERITY_ORDER,
    },
    "regression": {
        "xgboost": metrics_xgb_reg,
        "baseline_linreg": metrics_base_reg,
        "target_mean": float(yreg_test.mean()),
        "target_std": float(yreg_test.std()),
        "normalization": normalization["resource_demand_units"],
    },
    "data": {
        "n_rows": len(df),
        "n_train": len(X_train),
        "n_test": len(X_test),
        "n_features": len(FEATURES),
        "features": FEATURES,
        "class_distribution": df["flood_severity"].value_counts().to_dict(),
    },
}
with open(OUT_DIR / "metrics.json", "w") as f:
    json.dump(all_metrics, f, indent=2)

print(json.dumps(all_metrics["classification"]["xgboost"], indent=2))
print(json.dumps(all_metrics["classification"]["baseline_logreg"], indent=2))
print(json.dumps(all_metrics["regression"]["xgboost"], indent=2))
print(json.dumps(all_metrics["regression"]["baseline_linreg"], indent=2))
print("Normalization stats:", normalization)

# ----------------------------------------------------------------------
# 5. CHARTS
# ----------------------------------------------------------------------

fig, ax = plt.subplots(figsize=(6, 4))
order_counts = df["flood_severity"].value_counts().reindex(SEVERITY_ORDER)
sns.barplot(x=order_counts.index, y=order_counts.values, palette="Blues_d", ax=ax)
ax.set_title("Flood Severity Class Distribution (Full Dataset)")
ax.set_xlabel("Severity Class")
ax.set_ylabel("Number of Observations")
for i, v in enumerate(order_counts.values):
    ax.text(i, v + 30, str(v), ha="center", fontsize=9)
plt.tight_layout()
plt.savefig(CHART_DIR / "class_distribution.png", dpi=150)
plt.close()

fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
for ax, preds, title in [
    (axes[0], pred_xgb_clf, "XGBoost"),
    (axes[1], pred_base_clf, "Baseline (Logistic Regression)"),
]:
    cm = confusion_matrix(yclf_test, preds, labels=[0, 1, 2, 3])
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        cmap="Blues",
        ax=ax,
        xticklabels=SEVERITY_ORDER,
        yticklabels=SEVERITY_ORDER,
        cbar=False,
    )
    ax.set_title(title)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
plt.tight_layout()
plt.savefig(CHART_DIR / "confusion_matrices.png", dpi=150)
plt.close()

clf_metric_names = ["accuracy", "macro_f1", "weighted_f1", "macro_precision", "macro_recall"]
clf_compare_df = pd.DataFrame(
    {
        "metric": clf_metric_names * 2,
        "value": [metrics_xgb_clf[m] for m in clf_metric_names]
        + [metrics_base_clf[m] for m in clf_metric_names],
        "model": ["XGBoost"] * 5 + ["Baseline"] * 5,
    }
)
fig, ax = plt.subplots(figsize=(8, 4.5))
sns.barplot(data=clf_compare_df, x="metric", y="value", hue="model", palette=PALETTE, ax=ax)
ax.set_ylim(0, 1)
ax.set_title("Classification Performance: XGBoost vs Baseline")
ax.set_xlabel("")
ax.set_ylabel("Score")
plt.xticks(rotation=15)
plt.tight_layout()
plt.savefig(CHART_DIR / "classification_comparison.png", dpi=150)
plt.close()

fig, ax = plt.subplots(figsize=(7, 5))
importances = pd.Series(xgb_clf.feature_importances_, index=FEATURES).sort_values(ascending=True)
importances.plot(kind="barh", ax=ax, color="#1f6feb")
ax.set_title("XGBoost Feature Importance \u2013 Flood Severity Classifier")
ax.set_xlabel("Importance (gain-based)")
plt.tight_layout()
plt.savefig(CHART_DIR / "feature_importance_classifier.png", dpi=150)
plt.close()

fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
for ax, preds, title, color in [
    (axes[0], pred_xgb_reg, "XGBoost", "#1f6feb"),
    (axes[1], pred_base_reg, "Baseline (Linear Regression)", "#64748b"),
]:
    ax.scatter(yreg_test, preds, alpha=0.35, s=14, color=color)
    lims = [min(yreg_test.min(), preds.min()), max(yreg_test.max(), preds.max())]
    ax.plot(lims, lims, "r--", linewidth=1.2, label="Perfect prediction")
    ax.set_title(title)
    ax.set_xlabel("Actual Resource Demand (units)")
    ax.set_ylabel("Predicted Resource Demand (units)")
    ax.legend(fontsize=8)
plt.tight_layout()
plt.savefig(CHART_DIR / "regression_actual_vs_predicted.png", dpi=150)
plt.close()

reg_metric_names = ["mae", "rmse", "r2"]
fig, axes = plt.subplots(1, 3, figsize=(11, 4))
for ax, m in zip(axes, reg_metric_names):
    vals = [metrics_xgb_reg[m], metrics_base_reg[m]]
    bars = ax.bar(["XGBoost", "Baseline"], vals, color=[PALETTE["XGBoost"], PALETTE["Baseline"]])
    ax.set_title(m.upper())
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.2f}", ha="center", va="bottom", fontsize=9)
plt.suptitle("Regression Performance: XGBoost vs Baseline", y=1.03)
plt.tight_layout()
plt.savefig(CHART_DIR / "regression_comparison.png", dpi=150)
plt.close()

fig, ax = plt.subplots(figsize=(7, 5))
importances_r = pd.Series(xgb_reg.feature_importances_, index=FEATURES).sort_values(ascending=True)
importances_r.plot(kind="barh", ax=ax, color="#0ea5a3")
ax.set_title("XGBoost Feature Importance \u2013 Resource Demand Regressor")
ax.set_xlabel("Importance (gain-based)")
plt.tight_layout()
plt.savefig(CHART_DIR / "feature_importance_regressor.png", dpi=150)
plt.close()

print("\nAll charts saved to", CHART_DIR)
print("Metrics saved to", OUT_DIR / "metrics.json")

# ----------------------------------------------------------------------
# 6. Save models — filenames per schema §3.1 file contract
# ----------------------------------------------------------------------
joblib.dump(xgb_clf, OUT_DIR / "xgb_severity_classifier.joblib")
joblib.dump(xgb_reg, OUT_DIR / "xgb_resource_regressor.joblib")
joblib.dump(le, OUT_DIR / "label_encoder.joblib")
# Not part of the schema's shared file contract, but kept for our own
# baseline reproducibility / audit trail.
joblib.dump(baseline_clf, OUT_DIR / "baseline_logreg.joblib")
joblib.dump(baseline_reg, OUT_DIR / "baseline_linreg.joblib")
joblib.dump(scaler, OUT_DIR / "scaler.joblib")
print("Models saved to", OUT_DIR)
