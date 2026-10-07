import joblib, json, pandas as pd, numpy as np
from pathlib import Path

ACTIVE = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/scripts and code/Reservoir_inflow/active")

regressors = joblib.load(ACTIVE / "deployment_regressors_no_stage1.pkl")
print("Horizons in pkl:", sorted(regressors.keys()))
for h, m in sorted(regressors.items()):
    print(f"\n=== h{h} ===")
    print("type:", type(m))
    try:
        print("n_features_in_:", m.n_features_in_)
    except Exception as e:
        print("n_features_in_ err:", e)
    try:
        print("feature_names_:", m.feature_names_)
    except Exception as e:
        pass
    try:
        params = m.get_params()
        # print only a few key params
        for k in ["iterations", "depth", "learning_rate", "loss_function", "n_estimators"]:
            if k in params:
                print(f"  {k}: {params[k]}")
    except Exception as e:
        print("get_params err:", e)
    try:
        print("tree_count_:", m.tree_count_)
    except Exception:
        pass
