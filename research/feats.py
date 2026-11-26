"""Shared indicator code (TradingView-matching definitions) + zone-test helpers."""
import sys; import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from zones import *; from structure import *
def ema(s,n): return s.ewm(span=n,adjust=False).mean()
def rsi(s,n=14):
    d=s.diff(); g=d.clip(lower=0).ewm(alpha=1/n,adjust=False).mean(); l=(-d.clip(upper=0)).ewm(alpha=1/n,adjust=False).mean()
    return 100-100/(1+g/l)
def stochrsi(s,k=3,dd=3,rl=14,sl=14):
    r=rsi(s,rl); lo=r.rolling(sl).min(); hi=r.rolling(sl).max()
    st=100*(r-lo)/(hi-lo); K=st.rolling(k).mean(); D=K.rolling(dd).mean(); return K,D
def add(d):
    d=d.copy(); d["e50"]=ema(d.close,50); d["e200"]=ema(d.close,200); d["rsi"]=rsi(d.close)
    d["K"],d["D"]=stochrsi(d.close); d["atr"]=atr(d); return d
def held_rate(r):
    x=r[r.outcome.isin(["held","failed"])]; return ((x.outcome=="held").mean() if len(x) else np.nan), len(x)
def tag_struct(d,tfW,W):
    ws,_,_=trend_state(W,2)
    return ws if tfW else map_state(d,W,ws,pd.Timedelta(days=7))
