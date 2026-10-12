"""Compare a video2midi output with a known-good MIDI: python tools/compare_midi.py ours.mid reference.mid

Matches notes per hand (track 1 = right, track 2 = left) by pitch and onset, reports precision/recall at several
tolerances, timing error, and why reference notes are missing (merged repeats, other hand, undetected).
"""
import sys, mido, numpy as np, collections
def load(path):
    mid=mido.MidiFile(path)
    # absolute time in seconds per track using merged tempo map
    tempos=[]
    for tr in mid.tracks:
        t=0
        for m in tr:
            t+=m.time
            if m.type=="set_tempo": tempos.append((t,m.tempo))
    tempos=sorted(set(tempos))
    if not tempos or tempos[0][0] > 0: tempos.insert(0,(0,500000))  # MIDI default
    tempos=list({t: m for t, m in tempos}.items())  # last tempo at a tick wins
    def sec(tick):
        s=0;last=0;tp=500000
        for tt,tm in tempos:
            if tt>=tick: break
            s+=(tt-last)*tp/1e6/mid.ticks_per_beat; last=tt; tp=tm
        return s+(tick-last)*tp/1e6/mid.ticks_per_beat
    tracks=[]
    for tr in mid.tracks:
        t=0; on={}; notes=[]; name=""
        for m in tr:
            t+=m.time
            if m.type=="track_name": name=m.name
            if m.type=="note_on" and m.velocity>0: on.setdefault(m.note,[]).append(t)
            elif m.type in("note_off","note_on") and m.note in on and on[m.note]:
                s=on[m.note].pop(0); notes.append((m.note,sec(s),sec(t)))
        if notes: tracks.append((name,sorted(notes,key=lambda n:(n[1],n[0]))))
    bpms=[round(mido.tempo2bpm(tm),1) for _,tm in tempos]
    return mid,tracks,bpms
_,ours,_=load(sys.argv[1])
_,ref,_=load(sys.argv[2])
# track order differs between files: put the higher-pitched track first (right hand)
ours.sort(key=lambda t: -np.mean([n[0] for n in t[1]])); ref.sort(key=lambda t: -np.mean([n[0] for n in t[1]]))
def match(a,b,tol):
    """greedy one-to-one match by pitch, nearest onset within tol. returns pairs, unmatched a, unmatched b"""
    byp=collections.defaultdict(list)
    for i,n in enumerate(b): byp[n[0]].append(i)
    used=set(); pairs=[]; ua=[]
    for i,n in enumerate(a):
        best=None
        for j in byp[n[0]]:
            if j in used: continue
            d=abs(b[j][1]-n[1])
            if d<=tol and (best is None or d<best[0]): best=(d,j)
        if best: used.add(best[1]); pairs.append((i,best[1],b[best[1]][1]-n[1]))
        else: ua.append(i)
    ub=[j for j in range(len(b)) if j not in used]
    return pairs,ua,ub
for hi,hn in ((0,"Right"),(1,"Left")):
    o=ours[hi][1]; r=ref[hi][1]
    print(f"== {hn} hand: ours {len(o)} vs reference {len(r)}")
    for tol in (0.05,0.1,0.2,0.4):
        pr,uo,ur=match(o,r,tol)
        print(f"  tol {int(tol*1000):3d}ms: matched {len(pr)}  precision {len(pr)/len(o):.1%}  recall {len(pr)/len(r):.1%}")
    pr,uo,ur=match(o,r,0.4)
    d=np.array([x[2] for x in pr])
    print(f"  onset error (ref-ours) ms: mean {d.mean()*1000:.0f} median {np.median(d)*1000:.0f} p10 {np.percentile(d,10)*1000:.0f} p90 {np.percentile(d,90)*1000:.0f}")
    dd=np.array([(r[j][2]-r[j][1])-(o[i][2]-o[i][1]) for i,j,_ in pr])
    print(f"  duration diff (ref-ours) ms: mean {dd.mean()*1000:.0f} median {np.median(dd)*1000:.0f}")
    print("  extra in ours (pitch hist):",collections.Counter(o[i][0] for i in uo).most_common(6), "n",len(uo))
    print("  missing from ours (pitch hist):",collections.Counter(r[j][0] for j in ur).most_common(6),"n",len(ur))
    # when are the misses
    if ur:
        ts=np.array([r[j][1] for j in ur]); print("  missing by time (30s bins):",np.histogram(ts,bins=np.arange(0,361,30))[0].tolist())
    if uo:
        ts=np.array([o[i][1] for i in uo]); print("  extra by time (30s bins):  ",np.histogram(ts,bins=np.arange(0,361,30))[0].tolist())
# drift over time
pr,_,_=match(ours[0][1],ref[0][1],0.4)
ts=np.array([ours[0][1][i][1] for i,_,_ in pr]); d=np.array([x[2] for x in pr])
for a in range(0,331,60):
    m=(ts>=a)&(ts<a+60)
    if m.any(): print(f"  R drift t={a:3d}-{a+60}: median {np.median(d[m])*1000:.0f}ms n={m.sum()}")

print("\n=== why are notes missing? ===")
allours=[(n[0],n[1],n[2],h) for h,(nm,ns) in enumerate(ours) for n in ns]
for hi,hn in ((0,"R"),(1,"L")):
    o=ours[hi][1]; r=ref[hi][1]
    _,uo,ur=match(o,r,0.4)
    cats=collections.Counter(); samples=collections.defaultdict(list)
    for j in ur:
        p,s,e=r[j]
        cont=[x for x in allours if x[0]==p and x[1]-0.05<=s<=x[2]+0.05]
        other=[x for x in allours if x[0]==p and abs(x[1]-s)<0.4 and x[3]!=hi]
        if other: c="in other hand track"
        elif cont: c="merged into neighbouring same-pitch note"
        else: c="not detected at all"
        cats[c]+=1; samples[c].append((p,round(s,2),round(e-s,2)))
    print(hn,dict(cats))
    for c,sm in samples.items():
        durs=np.array([x[2] for x in sm]); print("   ",c,"median ref dur",round(float(np.median(durs)),2),"s; e.g.",sm[:5])

