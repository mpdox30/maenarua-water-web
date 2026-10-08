# -*- coding: utf-8 -*-
"""ดึง IMERG V07 รายครึ่งชั่วโมง "Late (GPM_3IMERGHHL) ก่อน ไม่มีค่อย Early (GPM_3IMERGHHE)" ผ่าน NASA Earthdata (earthaccess)
เฉลี่ยเชิงพื้นที่ของลุ่มน้ำ 1.MaenaruaMain1 (ถ่วงน้ำหนักตามพื้นที่ทับซ้อนของพิกเซล 0.1 องศากับโพลิกอน) -> imerg_early_halfhourly_main1.csv
คอลัมน์: end_utc, rain_mm_30min (= mm/hr x 0.5), source (E/L)
ตั้งค่าครั้งเดียว (Windows, ใน .venv): pip install earthaccess h5py geopandas shapely pandas numpy
  setx EARTHDATA_USERNAME "<ชื่อผู้ใช้>"   &   setx EARTHDATA_PASSWORD "<รหัสผ่าน>"   (หรือใช้ไฟล์ %USERPROFILE%\\_netrc ตามคู่มือ Earthdata)
รัน: python fetch_imerg_early_earthaccess.py   (ตัวแปรเสริม LOOKBACK_DAYS=4, WMB_ROOT=D:\\WMB_Phayao)
หมายเหตุ: ดึงเฉพาะที่ยังไม่มีในไฟล์ (ต่อจากช่อง 30 นาทีล่าสุด) ; ไฟล์ HDF5 ดาวน์โหลดไป cache ชั่วคราวแล้วลบหลังอ่าน"""
import os, re, json, glob, shutil, tempfile
from datetime import datetime, timedelta, timezone
import numpy as np, pandas as pd
HERE=os.path.dirname(os.path.abspath(__file__));ROOT=os.environ.get("WMB_ROOT",r"D:\WMB_Phayao");NAME=os.environ.get("CATCHMENT","1.MaenaruaMain1")
OUT=os.path.join(HERE,"imerg_early_halfhourly_main1.csv");LOOK=int(os.environ.get("LOOKBACK_DAYS","4"))
import earthaccess, h5py, geopandas as gpd
from shapely.geometry import box
GPKG=os.environ.get("CATCHMENT_GPKG") or (os.path.join(HERE,"sub_catchments.gpkg") if os.path.exists(os.path.join(HERE,"sub_catchments.gpkg")) else os.path.join(ROOT,"02_processed","sub_catchment","sub_catchments.gpkg"))
g=gpd.read_file(GPKG,layer="watersheds").to_crs("EPSG:4326");poly=g[g["name"]==NAME].iloc[0].geometry
lon0,lat0,lon1,lat1=poly.bounds;BBOX=(lon0-0.1,lat0-0.1,lon1+0.1,lat1+0.1)
def pixel_weights(lons,lats):
    ws={}
    for i,lo in enumerate(lons):
        for j,la in enumerate(lats):
            a=box(lo-0.05,la-0.05,lo+0.05,la+0.05).intersection(poly).area
            if a>0: ws[(i,j)]=a
    tot=sum(ws.values());return {k:v/tot for k,v in ws.items()}
earthaccess.login(strategy="environment") if os.environ.get("EARTHDATA_USERNAME") else earthaccess.login()
have=pd.read_csv(OUT,parse_dates=["end_utc"]) if os.path.exists(OUT) else pd.DataFrame(columns=["end_utc","rain_mm_30min","source"])
t_end=datetime.now(timezone.utc).replace(tzinfo=None);t_start=(have.end_utc.max().to_pydatetime()-timedelta(hours=1)) if len(have) else t_end-timedelta(days=LOOK)
t_start=max(t_start,t_end-timedelta(days=LOOK+10))
fmt=lambda d:d.strftime("%Y-%m-%dT%H:%M:%SZ");rows=[];tmp=tempfile.mkdtemp(prefix="imerg_")
def parse_start(fn):
    m=re.search(r"\.(\d{8})-S(\d{6})-E",os.path.basename(fn));return datetime.strptime(m.group(1)+m.group(2),"%Y%m%d%H%M%S")
try:
    for short,src in (("GPM_3IMERGHHL","L"),("GPM_3IMERGHHE","E")):
        res=earthaccess.search_data(short_name=short,version="07",temporal=(fmt(t_start),fmt(t_end)),bounding_box=BBOX)
        print(short,"พบ",len(res),"ไฟล์")
        if not res: continue
        files=earthaccess.download(res,tmp)
        W=None
        for f in files:
            with h5py.File(f,"r") as h:
                lon=h["Grid/lon"][:];lat=h["Grid/lat"][:];p=h["Grid/precipitation"]
                ii=np.where((lon>=BBOX[0]-0.05)&(lon<=BBOX[2]+0.05))[0];jj=np.where((lat>=BBOX[1]-0.05)&(lat<=BBOX[3]+0.05))[0]
                if W is None: W={(a,b):w for (a,b),w in pixel_weights(lon[ii],lat[jj]).items()}
                sub=p[0][np.ix_(ii,jj)].astype(float);sub[sub<0]=np.nan
            num=sum(sub[a,b]*w for (a,b),w in W.items() if not np.isnan(sub[a,b]));den=sum(w for (a,b),w in W.items() if not np.isnan(sub[a,b]))
            if den>0: rows.append({"end_utc":parse_start(f)+timedelta(minutes=30),"rain_mm_30min":float(num/den)*0.5,"source":src})
        for f in files:
            try: os.remove(f)
            except OSError: pass
finally:
    shutil.rmtree(tmp,ignore_errors=True)
new=pd.DataFrame(rows)
allv=pd.concat([have,new]);allv["pri"]=(allv.source=="L").astype(int)   # ถ้ามีทั้ง L และ E ของช่องเดียวกัน ใช้ L
allv=allv.sort_values(["end_utc","pri"]).drop_duplicates("end_utc",keep="last").drop(columns="pri").sort_values("end_utc")
allv.to_csv(OUT,index=False);print("บันทึก",OUT,len(allv),"ช่อง ล่าสุด",allv.end_utc.max(),"| ใหม่",len(new))
