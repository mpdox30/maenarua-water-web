# -*- coding: utf-8 -*-
"""สร้างชุด Training รายวันที่ใช้ Q_in ตามสูตร spill ใหม่ (ledger offset 0) -- experiment เท่านั้น ไม่แตะ production"""
import glob, os, datetime as dt
import numpy as np, pandas as pd, openpyxl
HERE=os.path.dirname(os.path.abspath(__file__))
M=os.environ.get("MNT","/sessions/busy-awesome-cerf/mnt")
LEDGER_DIR=os.environ.get("LEDGER_DIR",f"{M}/outputs/ledger_new")
SRC=f"{M}/maenaruea-water-web/01_data/scripts and code/Reservoir_inflow/active/Training_Values_Nofct_7day_Extended_lagfeat.csv"
MONTHS=dict(January=1,February=2,March=3,April=4,May=5,June=6,July=7,August=8,September=9,October=10,November=11,December=12)
rows=[]
for f in glob.glob(f"{LEDGER_DIR}/*_MNR.xlsx"):
    y,mn,_=os.path.basename(f).split("_");ws=openpyxl.load_workbook(f,data_only=True).active
    for r in ws.iter_rows(min_row=6):
        if isinstance(r[0].value,int):
            rows.append(dict(Date=pd.Timestamp(int(y),MONTHS[mn],r[0].value),Q_new=r[3].value,Spill_new=r[5].value,note=r[11].value))
led=pd.DataFrame(rows).set_index("Date").sort_index()
df=pd.read_csv(SRC,parse_dates=["Date"])
q="Q_in_t (m3/day)"
df=df.merge(led.reset_index(),on="Date",how="left")
df["Q_old"]=df[q]
df[q]=df["Q_new"].fillna(df["Q_old"])
df["fallback_old_formula"]=df["Q_new"].isna()|df["note"].fillna("").str.startswith("ใช้ค่าเดิม")
# สร้าง lag/target ใหม่จาก Q ใหม่ (ลำดับวันต่อเนื่อง)
s=df.set_index("Date")[q]
df["Qin_lag1 (m3/day)"]=s.shift(1).values
df["Qin_lag2 (m3/day)"]=s.shift(2).values
for h in range(1,8):
    df[f"y{h}=Q_in_t+{h} (m3/day)"]=s.shift(-h).values
assert (df["Date"].diff().dropna()==pd.Timedelta(days=1)).all(),"วันไม่ต่อเนื่อง"
df=df.drop(columns=["Q_new","Spill_new","note"])
out=os.path.join(HERE,"Training_Values_newspill_offset0_20261007.csv");df.to_csv(out,index=False)
d=(df[q]-df["Q_old"])
print("rows",len(df),"changed",(d.abs()>1).sum(),"fallback",df.fallback_old_formula.sum())
print("sum old",round(df.Q_old.sum()),"sum new",round(df[q].sum()))
print(df.loc[d.abs()>1,["Date","Q_old",q]].sort_values("Date").head(12).to_string())
