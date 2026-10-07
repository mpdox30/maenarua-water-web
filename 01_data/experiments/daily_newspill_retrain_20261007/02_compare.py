# -*- coding: utf-8 -*-
"""เทียบ: A = โมเดลเทรนด้วยข้อมูลสูตรเก่า (production-like) ทำนายบนฟีเจอร์/target สูตรใหม่  vs  B = เทรนด้วยข้อมูลสูตรใหม่
Expanding-window walk-forward, CatBoost delta-regression, hyperparam เดียวกับ production (ไม่รวม rain-forecast feature / bias correction)"""
import os, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
from catboost import CatBoostRegressor
HERE=os.path.dirname(os.path.abspath(__file__))
M=os.environ.get("MNT","/sessions/busy-awesome-cerf/mnt")
SRC=f"{M}/maenaruea-water-web/01_data/scripts and code/Reservoir_inflow/active/Training_Values_Nofct_7day_Extended_lagfeat.csv"
new=pd.read_csv(f"{HERE}/Training_Values_newspill_offset0_20261007.csv",parse_dates=["Date"])
old=pd.read_csv(SRC,parse_dates=["Date"])
FEATS=["Q_in_t (m3/day)","Water_Level_t (m)","Storage_S_t (m3)","DeltaS_t (m3/day)","%Full_t","Rain_obs_t (mm)","API_t (mm)","Qin_lag1 (m3/day)","Qin_lag2 (m3/day)","Rain_roll3 (mm)","Rain_roll5 (mm)","Rain_roll7 (mm)"]
P={1:dict(depth=6,learning_rate=0.0109312751880508,l2_leaf_reg=23.808543547006124,min_data_in_leaf=8,subsample=0.8332116765879214,rsm=0.7890628480631008,random_strength=1.07161216899677),
2:dict(depth=5,learning_rate=0.0146991485489077,l2_leaf_reg=1.7430504177815451,min_data_in_leaf=24,subsample=0.914033992242307,rsm=0.6212741213218833,random_strength=1.9674909492695445),
3:dict(depth=5,learning_rate=0.0159859205807381,l2_leaf_reg=4.339666832543908,min_data_in_leaf=37,subsample=0.986523802644266,rsm=0.8127877215251221,random_strength=2.57649494325228),
4:dict(depth=3,learning_rate=0.0109387154307568,l2_leaf_reg=3.810029124004568,min_data_in_leaf=36,subsample=0.4063769521841512,rsm=0.9913749176499462,random_strength=2.699726957831789),
5:dict(depth=2,learning_rate=0.0121759578591452,l2_leaf_reg=31.27438558692472,min_data_in_leaf=25,subsample=0.9868547519916756,rsm=0.6502309452463372,random_strength=1.0),
6:dict(depth=2,learning_rate=0.0136765950369614,l2_leaf_reg=4.382716203014211,min_data_in_leaf=29,subsample=0.7105210344032551,rsm=0.8290243458181864,random_strength=1.9867898992450308),
7:dict(depth=2,learning_rate=0.0119080907879342,l2_leaf_reg=1.426422588105843,min_data_in_leaf=18,subsample=0.4317495679086314,rsm=0.7638703770649338,random_strength=1.0054966332229271)}
def fit(X,y,p):
    n=len(X);cut=int(n*0.85);q=dict(p);q.update(iterations=300,loss_function="MAE",random_seed=42,verbose=False,od_type="Iter",od_wait=30)
    m=CatBoostRegressor(**q);m.fit(X[:cut],y[:cut],eval_set=(X[cut:],y[cut:]),use_best_model=True);return m
def nse(o,p): return 1-((o-p)**2).sum()/((o-o.mean())**2).sum()
folds=[(150,180),(180,210),(210,240),(240,270),(270,300),(300,330),(330,360),(360,393)]  # (train_end_idx exclusive, test_end)
out=[];Q="Q_in_t (m3/day)"
for h in range(1,8):
    yc=f"y{h}=Q_in_t+{h} (m3/day)"
    rec=[]
    for te,tend in folds:
        tr_end=te-h  # กัน target ซ้อนทับ
        tests=new.iloc[te:tend]; tests=tests[tests[yc].notna()]
        if len(tests)==0: continue
        for tag,tr in (("A_old_trained",old),("B_new_trained",new)):
            d=tr.iloc[:tr_end]; d=d[d[yc].notna()&d["Qin_lag2 (m3/day)"].notna()]
            m=fit(d[FEATS].values,(d[yc]-d[Q]).values,P[h])
            pred=np.clip(tests[Q].values+m.predict(tests[FEATS].values),0,None)
            rec.append(pd.DataFrame(dict(h=h,tag=tag,Date=tests.Date.values,obs=tests[yc].values,pred=pred)))
        rec.append(pd.DataFrame(dict(h=h,tag="persistence",Date=tests.Date.values,obs=tests[yc].values,pred=tests[Q].values)))
    r=pd.concat(rec);out.append(r)
R=pd.concat(out);R.to_csv(f"{HERE}/cv_predictions.csv",index=False)
S=R.groupby(["h","tag"]).apply(lambda g:pd.Series(dict(n=len(g),MAE=(g.obs-g.pred).abs().mean(),NSE=nse(g.obs.values,g.pred.values)))).reset_index()
S.to_csv(f"{HERE}/cv_summary.csv",index=False)
print(S.pivot(index="h",columns="tag",values=["MAE","NSE"]).round(3).to_string())
