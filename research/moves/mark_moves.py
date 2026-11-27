import pandas as pd, numpy as np, json
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from btcdata import load
d=load()
d['t']=d.time
# drop the still-forming candle if any (last candle open < 1 day ago is fine since file is daily closes)
H,L,C,O=d.high.values,d.low.values,d.close.values,d.open.values
pc=np.r_[C[0],C[:-1]]
tr=np.maximum(H-L,np.maximum(abs(H-pc),abs(L-pc)))
atr=pd.Series(tr).ewm(alpha=1/14,adjust=False).mean().values
atrp=atr/C*100

def zig(hi,lo,th):
    """High/low zigzag. Each bar: extend the current extreme first; only a bar that does NOT extend it can
    confirm a reversal. Returns pivots [idx, price, type, confirm_idx] and the open final extreme."""
    n=len(hi); hi0,lo0=0,0; mode=0
    for i in range(1,n):                       # find the first 10%+ swing to set the starting direction
        if hi[i]>hi[hi0]: hi0=i
        if lo[i]<lo[lo0]: lo0=i
        if hi[hi0]>=lo[lo0]*(1+th) and lo0<hi0: mode=1; piv=[[lo0,lo[lo0],'L',hi0]]; ei,ehi=hi0,hi[hi0]; break
        if lo[lo0]<=hi[hi0]*(1-th) and hi0<lo0: mode=-1; piv=[[hi0,hi[hi0],'H',lo0]]; eli,elo=lo0,lo[lo0]; break
    for i in range(i+1,n):
        if mode==1:
            if hi[i]>ehi: ei,ehi=i,hi[i]
            elif lo[i]<=ehi*(1-th): piv.append([ei,ehi,'H',i]); mode=-1; eli,elo=i,lo[i]
        else:
            if lo[i]<elo: eli,elo=i,lo[i]
            elif hi[i]>=elo*(1+th): piv.append([eli,elo,'L',i]); mode=1; ei,ehi=i,hi[i]
    last=[ei,ehi,'H',None] if mode==1 else [eli,elo,'L',None]
    return piv,last

def era(t):
    y=t.year+(t.month-1)/12
    return '2011-16' if t<pd.Timestamp('2016-07-01') else ('2016-21' if t<pd.Timestamp('2021-07-01') else '2021-26')

out=[]
for basis in ('wick','close'):
    hi,lo=(H,L) if basis=='wick' else (C,C)
    levels={}
    for th in (0.10,0.20,0.30,0.50):
        piv,last=zig(hi,lo,th)
        mv=[]
        seq=piv+[last]
        for a,b in zip(seq[:-1],seq[1:]):
            s,e=a[0],b[0]; ps,pe=a[1],b[1]
            mv.append(dict(basis=basis,level=int(th*100),start=s,end=e,ps=float(ps),pe=float(pe),
                 dir='up' if pe>ps else 'down',pct=round((pe/ps-1)*100,1),days=int(e-s),
                 confirmed=None if b[3] is None else int(b[3]),
                 atr_start=round(float(atrp[s]),2)))
        levels[th]=mv
    # parent tagging. "same as": identical start and end at a bigger size. "inside": the smallest bigger move
    # that is NOT identical and whose span contains this move's midpoint.
    fd=lambda i: f"{d.t[i]:%b %d, %Y}"
    for th in (0.10,0.20,0.30,0.50):
        for m in levels[th]:
            same=[];m['parent']=None
            for th2 in [x for x in (0.20,0.30,0.50) if x>th]:
                for p in levels[th2]:
                    if p['start']==m['start'] and p['end']==m['end']: same.append(f"{int(th2*100)}%")
            m['same_as']=', '.join(same) or None
            mid=(m['start']+m['end'])/2
            for th2 in [x for x in (0.20,0.30,0.50) if x>th]:
                for p in levels[th2]:
                    if p['start']<=mid<=p['end'] and not (p['start']==m['start'] and p['end']==m['end']):
                        m['parent']=f"{int(th2*100)}% {p['dir']} {fd(p['start'])} → {fd(p['end'])} ({p['pct']:+.0f}%)"
                        break
                if m['parent']: break
    for th in levels:
        for m in levels[th]:
            m.setdefault('parent',None)
            m['size_atr']=round(abs(m['pct'])/m['atr_start'],1) if m['start']>=14 else None
            m['era']=era(d.t[m['start']]); m['open']=m['confirmed'] is None
            hi,lo=(H,L) if basis=='wick' else (C,C)
            a,b=m['start'],m['end']
            if b>a+1:
                inner=lo[a+1:b].min() if m['dir']=='up' else hi[a+1:b].max()
                u=(inner/m['ps']-1)*100 if m['dir']=='up' else (inner/m['ps']-1)*100
                m['undercut_pct']=round(min(u,0),2) if m['dir']=='up' else round(max(u,0),2)
            else: m['undercut_pct']=0.0
            m['same_day']=bool(basis=='wick' and ((m['dir']=='up' and (L[b]<m['ps'] or H[a]>m['pe'])) or (m['dir']=='down' and (H[b]>m['ps'] or L[a]<m['pe']))))
            out.append(m)
df=pd.DataFrame(out)
for c in ('start','end'): df[c+'_date']=d.t.values[df[c]]
df['confirmed_date']=[None if pd.isna(x) else d.t[int(x)] for x in df.confirmed]
df['confirm_lag_days']=[None if pd.isna(x) else int(x)-e for x,e in zip(df.confirmed,df.end)]
df.to_csv('moves.csv',index=False)
print(df.groupby(['basis','level','era','dir']).size().unstack(['dir']).to_string())
print(df[df.open][['basis','level','dir','start_date','ps','pe','pct']].to_string())
