from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import numpy as np
import pandas as pd
try:
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.metrics import accuracy_score, log_loss
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder
except ImportError:
    ColumnTransformer=HistGradientBoostingClassifier=SimpleImputer=Pipeline=OneHotEncoder=None

NUM=["ball_count","strike_count","outs","inning","pitch_number","runner_on_first","runner_on_second","runner_on_third","score_diff","plate_x","plate_z","release_velocity","release_spin_rate","release_extension"]
CAT=["pitch_type","batter_side","previous_pitch_type"]

@dataclass
class OutcomeModelResult:
    available: bool; sample_size:int; accuracy:float|None; log_loss:float|None; classes:list[str]; note:str; model:Any=None

def _outcome(desc:str, event:str, ev:float|None)->str:
    text=f"{desc} {event}".lower()
    if "swinging_strike" in text or "swinging strike" in text or "foul_tip" in text:return "whiff"
    if "called_strike" in text or "called strike" in text:return "called_strike"
    if "ball" in text and "in play" not in text:return "ball"
    if "home_run" in text or "home run" in text:return "damage"
    if ev is not None and not pd.isna(ev) and ev>=95:return "hard_contact"
    if "hit_into_play" in text or "in play" in text:return "weak_contact"
    return "other"

def prepare(frame:pd.DataFrame)->pd.DataFrame:
    if frame.empty:return pd.DataFrame()
    d=frame.copy().sort_values([c for c in ["game_date","game_pk","at_bat_number","pitch_number"] if c in frame])
    keys=[c for c in ["game_pk","at_bat_number"] if c in d]
    d["previous_pitch_type"]=d.groupby(keys)["pitch_type"].shift(1) if len(keys)==2 else "START"
    d["previous_pitch_type"]=d["previous_pitch_type"].fillna("START")
    d["batter_side"]=d.get("batter_side",pd.Series("U",index=d.index)).fillna("U")
    home=pd.to_numeric(d.get("home_score",0),errors="coerce").fillna(0); away=pd.to_numeric(d.get("away_score",0),errors="coerce").fillna(0)
    half=d.get("inning_half",pd.Series("top",index=d.index)).fillna("top").astype(str).str.lower()
    d["score_diff"]=np.where(half.eq("top"),away-home,home-away)
    for c in NUM:
        if c.startswith("runner_"):d[c]=d.get(c,False).fillna(False).astype(int)
        else:d[c]=pd.to_numeric(d.get(c,0),errors="coerce")
    ev=pd.to_numeric(d.get("exit_velocity",np.nan),errors="coerce")
    d["outcome"]=[_outcome(a,b,c) for a,b,c in zip(d.get("pitch_description",""),d.get("events",""),ev)]
    return d[d["outcome"].ne("other") & d["pitch_type"].notna()].copy()

def train_outcome_model(frame:pd.DataFrame,minimum_rows:int=500)->OutcomeModelResult:
    if Pipeline is None:return OutcomeModelResult(False,0,None,None,[],"Install scikit-learn to enable pitch-outcome modeling.")
    d=prepare(frame)
    if len(d)<minimum_rows or d.outcome.nunique()<3:return OutcomeModelResult(False,len(d),None,None,sorted(d.outcome.unique().tolist()),f"Need at least {minimum_rows} classified pitches and three outcomes.")
    split=max(int(len(d)*.8),1); train,test=d.iloc[:split],d.iloc[split:]
    pre=ColumnTransformer([("num",Pipeline([("impute",SimpleImputer(strategy="median"))]),NUM),("cat",Pipeline([("impute",SimpleImputer(strategy="most_frequent")),("onehot",OneHotEncoder(handle_unknown="ignore",sparse_output=False))]),CAT)])
    model=Pipeline([("features",pre),("classifier",HistGradientBoostingClassifier(max_iter=180,learning_rate=.06,max_leaf_nodes=28,l2_regularization=1.2,random_state=42))])
    model.fit(train[NUM+CAT],train.outcome); pred=model.predict(test[NUM+CAT]); prob=model.predict_proba(test[NUM+CAT]); classes=list(model.named_steps["classifier"].classes_)
    return OutcomeModelResult(True,len(d),round(float(accuracy_score(test.outcome,pred)),3),round(float(log_loss(test.outcome,prob,labels=classes)),3),classes,"Time-ordered gradient-boosted pitch-outcome classifier.",model)

def scenario_scores(result:OutcomeModelResult,pitch_types:list[str],batter_side:str="R")->list[dict[str,Any]]:
    if not result.available:return []
    zones=[("Up",0,3.1),("Down",0,1.7),("Arm-side",.7,2.4),("Glove-side",-.7,2.4)]
    rows=[]
    run_values={"whiff":-.08,"called_strike":-.06,"ball":.05,"weak_contact":.01,"hard_contact":.18,"damage":.42}
    for p in pitch_types[:6]:
        for zone,x,z in zones:
            row=pd.DataFrame([{**{c:0 for c in NUM},"ball_count":1,"strike_count":1,"inning":5,"pitch_number":3,"plate_x":x,"plate_z":z,"release_velocity":92,"release_spin_rate":2200,"release_extension":6.5,"pitch_type":p,"batter_side":batter_side,"previous_pitch_type":"START"}])
            probs=result.model.predict_proba(row[NUM+CAT])[0]; pdict={str(c):float(v) for c,v in zip(result.classes,probs)}
            erv=sum(pdict.get(k,0)*v for k,v in run_values.items())
            rows.append({"pitch_type":p,"zone":zone,"expected_run_value":round(erv,3),"whiff":round(pdict.get("whiff",0)*100,1),"called_strike":round(pdict.get("called_strike",0)*100,1),"hard_contact":round((pdict.get("hard_contact",0)+pdict.get("damage",0))*100,1)})
    return sorted(rows,key=lambda r:r["expected_run_value"])[:10]
