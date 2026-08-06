"""
Distribution shift analysis — M5 Week 3 task.

Once M2 delivers real `flood_observations.csv` files from
`generate_flood_scenario()`, run this against them to check whether their
feature distributions have drifted from the synthetic training data the
models were fit on. A meaningful shift on any high-importance feature
(rainfall_72h_mm, river_level_m, drainage_capacity_index, etc. — see
feature_importance_*.png) is a signal the model may need retraining on
M2's actual generator output rather than the original synthetic set.

Usage:
    python3 04_distribution_shift_check.py path/to/flood_observations.csv
    python3 04_distribution_shift_check.py           # smoke-tests against
                                                       # the held-out test split

Method: two-sample Kolmogorov-Smirnov test per feature (non-parametric,
no distributional assumptions). A small p-value (< 0.05) means the two
samples likely come from different distributions for that feature.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
from q_rescue.ai.validation import (  # noqa: E402
    EXPECTED_FEATURES,
    validate_flood_observation_columns,
)

TRAIN_DATA_PATH = REPO_ROOT / "flood_xgboost_project" / "data" / "flood_dataset.csv"


def run_shift_check(new_observations: pd.DataFrame, alpha: float = 0.05) -> pd.DataFrame:
    validate_flood_observation_columns(
        [c for c in new_observations.columns if c in EXPECTED_FEATURES] or new_observations.columns
    )
    reference = pd.read_csv(TRAIN_DATA_PATH)[EXPECTED_FEATURES]

    rows = []
    for feat in EXPECTED_FEATURES:
        if feat not in new_observations.columns:
            rows.append(
                {
                    "feature": feat,
                    "ks_stat": None,
                    "p_value": None,
                    "shift_detected": None,
                    "note": "column missing from new observations",
                }
            )
            continue
        ref_vals = reference[feat].dropna().values
        new_vals = new_observations[feat].dropna().values
        if len(new_vals) < 5:
            rows.append(
                {
                    "feature": feat,
                    "ks_stat": None,
                    "p_value": None,
                    "shift_detected": None,
                    "note": "too few samples (<5)",
                }
            )
            continue
        ks_stat, p_value = stats.ks_2samp(ref_vals, new_vals)
        rows.append(
            {
                "feature": feat,
                "train_mean": float(np.mean(ref_vals)),
                "new_mean": float(np.mean(new_vals)),
                "train_std": float(np.std(ref_vals)),
                "new_std": float(np.std(new_vals)),
                "ks_stat": float(ks_stat),
                "p_value": float(p_value),
                "shift_detected": bool(p_value < alpha),
                "note": "",
            }
        )
    return pd.DataFrame(rows)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        print(f"Checking distribution shift for: {path}")
        new_df = pd.read_csv(path)
    else:
        print(
            "No file given — smoke-testing against the model's own held-out test split "
            "(20% random sample of flood_dataset.csv). This should show NO shift, since "
            "it's drawn from the same distribution as training."
        )
        full_df = pd.read_csv(TRAIN_DATA_PATH)
        new_df = full_df.sample(frac=0.2, random_state=123)

    result = run_shift_check(new_df)
    pd.set_option("display.width", 140)
    pd.set_option("display.max_columns", 10)
    print(result.to_string(index=False))

    n_shifted = int(result["shift_detected"].fillna(False).sum())
    n_checked = int(result["shift_detected"].notna().sum())
    print(
        f"\n{n_shifted}/{n_checked} features show a statistically significant shift (alpha=0.05)."
    )
    if n_shifted > 0:
        print(
            "=> Recommend re-evaluating model accuracy on this data before trusting predictions "
            "operationally, and consider retraining if the shift is large or affects "
            "high-importance features."
        )
    else:
        print("=> No significant distribution shift detected; existing models should generalise.")
