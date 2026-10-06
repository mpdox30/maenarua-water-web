# -*- coding: utf-8 -*-
"""Flag 6h windows whose level jump RETRACES within the next 6-12h (transient spike/dip, not sustained inflow)."""
import os, sys
import numpy as np, pandas as pd
from datetime import timedelta
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import hourly_series as hs

def flag_windows(df, hl):
    L = lambda t: hl.get(t)
    flags = []
    for t in df.Datetime:
        a, b = L(t - timedelta(hours=6)), L(t)
        c = L(t + timedelta(hours=6)); c2 = L(t + timedelta(hours=12))
        if a is None or b is None: flags.append(np.nan); continue
        jump = b - a
        # also catch a spike INSIDE the window that retraces before the mark (max excursion vs endpoints)
        inner = [L(t - timedelta(hours=k)) for k in range(0, 6)]
        inner = [v for v in inner if v is not None]
        exc = max(inner) - max(a, b) if inner else 0.0
        ret = np.nan
        later = [v for v in (c, c2) if v is not None]
        if later and abs(jump) > 0.15:
            ret = float(np.min([abs(v - a) for v in later]) < 0.5 * abs(jump))   # returns toward pre-window level
        flags.append(1.0 if (ret == 1.0) or exc > 0.15 else 0.0)
    return np.array(flags)

if __name__ == "__main__":
    hl, hr, _ = hs.load_hourly(False)
    df = pd.read_csv(os.path.join(HERE, "Training_v2_6h.csv"), parse_dates=["Datetime"])
    df["artifact"] = flag_windows(df, hl)
    df[["Datetime", "artifact"]].to_csv(os.path.join(HERE, "artifact_flags.csv"), index=False)
    big = df[df["Qend"] > 50000]
    print("windows:", len(df), " flagged artifact:", int(df.artifact.sum()))
    print("Qend>50k windows:", len(big), " of which flagged:", int(big.artifact.sum()))
    # rain presence among big windows
    big = big.assign(rain_any=(big["rain_6h_end"] > 2) | (big["rain6_lag1"] > 2))
    print(pd.crosstab(big.artifact, big.rain_any, rownames=["artifact"], colnames=["rain>2mm (this/prev window)"]))
    print("share of total Qend volume in flagged windows: %.1f%%" % (100 * df.loc[df.artifact == 1, "Qend"].sum() / df.Qend.sum()))
    print(df[(df.artifact == 1) & (df.Qend > 50000)][["Datetime", "Qend", "L_end", "rain_6h_end"]].round(1).to_string(index=False))
