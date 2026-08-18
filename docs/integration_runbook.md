# Phase 2 Integration Runbook

This runbook covers the Member 4 integration path. It reuses the contracts in
[interface_spec.md](interface_spec.md), the AI flow in
[phase2_ai_integration.md](phase2_ai_integration.md), and the Member 1 QUBO
contract in [phase2_member1_ai_qubo.md](phase2_member1_ai_qubo.md).

## Data flow

1. The Streamlit Disaster Input page saves the user's simulation values.
2. `frontend/backend_integration.py` creates the existing Member 2 flood
   scenario and hydrological features.
3. Member 5's XGBoost predictor produces per-incident severity, confidence,
   and resource-demand values.
4. `run_validated_ai_prediction_pipeline()` validates predictions,
   incident coverage, the dashboard payload, and the QUBO patch.
5. The existing Member 1 `apply_ai_patch()` applies severity and demand
   overrides to the QUBO builder.
6. Member 2's distance matrix and severity mapping feed the shared allocation
   service.
7. The exact QUBO solver returns ambulance assignments, energy, incident
   coverage, and critical-incident coverage.
8. Streamlit stores the outputs in session state and displays them in the AI
   Prediction and Comparison pages.

Session keys:

- `ai_predictions`: validated incident predictions.
- `ai_dashboard_payload`: dashboard-ready AI data.
- `ai_qubo_patch`: severity and demand overrides.
- `ai_quantum_allocation`: patched QUBO allocation result.
- `ai_integration_error`: fallback reason when integration is unavailable.

The trained model is flood-specific. Non-flood scenarios clear these values
and continue through the existing heuristic flow. Flood integration failures
also fall back safely instead of blocking the simulation page.

## Local setup

Run these commands from the repository root.

### macOS prerequisite

XGBoost requires the OpenMP runtime:

```bash
brew install libomp
```

### Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[ai]"
python -m pip install -r frontend/requirements.txt
```

On Windows, activate with:

```powershell
.venv\Scripts\Activate.ps1
```

## Start Streamlit

```bash
cd frontend
python -m streamlit run Home.py
```

Open the local URL printed by Streamlit, sign in with a configured demo
account, and use **Disaster Input** to run a scenario.

## Automated checks

From the repository root:

```bash
python -m ruff check src tests frontend
python -m ruff format --check src tests frontend
python -m pytest
```

## Manual verification

1. Run a **Flood** scenario.
2. Confirm the simulation succeeds and reports validated XGBoost output.
3. Open **AI Prediction View** and confirm per-incident risk and demand values.
4. Open **Comparison View** and confirm the AI-patched QUBO banner appears.
5. Confirm QUBO energy, incident coverage, and critical coverage are present.
6. Confirm the quantum ambulance count comes from exact-QUBO assignments.
7. Run a non-flood scenario and confirm the application returns to heuristic
   mode without showing stale flood predictions or allocations.

The frontend limits the integrated demo to four ambulances and five incidents
so the existing exact solver remains below its 24-binary-variable safety
limit. QAOA remains controlled by the existing allocation settings.
