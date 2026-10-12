"""Compare a video2midi output for a CLIP with the matching stretch of a full reference MIDI.

Usage: python tools/compare_clip.py ours.mid reference.mid CLIP_START_SECONDS_IN_REFERENCE
"""
import sys, numpy as np, collections
OFF=float(sys.argv[3]) if len(sys.argv)>3 else 87.75
sys.argv=[sys.argv[0],sys.argv[1],sys.argv[2]]
src=open("tools/compare_midi.py").read()
exec(src.split("_,ours")[0])
exec("def match"+src.split("def match")[1].split("for hi,hn")[0])
_,ours,_=load(sys.argv[1]); _,ref,_=load(sys.argv[2])
T=max(e for tr in ours for _,_,e in tr[1])
refw=[[(p,s-OFF,e-OFF) for p,s,e in tr[1] if OFF-0.3<=s<=OFF+T+0.3] for tr in ref]
for hi,hn in ((0,"Right"),(1,"Left")):
    o=ours[hi][1]; r=refw[hi]
    print(f"== {hn}: ours {len(o)} ref(window) {len(r)}")
    for tol in (0.06,0.1,0.2):
        pr,uo,ur=match(o,r,tol); print(f"  tol {int(tol*1000)}ms: matched {len(pr)} precision {len(pr)/max(1,len(o)):.1%} recall {len(pr)/max(1,len(r)):.1%}")
    pr,uo,ur=match(o,r,0.2)
    d=np.array([x[2] for x in pr]); print(f"  onset err ms (ref-ours): median {np.median(d)*1000:.0f}  p10 {np.percentile(d,10)*1000:.0f} p90 {np.percentile(d,90)*1000:.0f}")
    dd=np.array([(r[j][2]-r[j][1])-(o[i][2]-o[i][1]) for i,j,_ in pr]); print(f"  duration err ms (ref-ours): median {np.median(dd)*1000:.0f} mean {dd.mean()*1000:.0f}")
    print("  extra:",[(o[i][0],round(o[i][1],2)) for i in uo][:12],len(uo))
    print("  missing:",[(r[j][0],round(r[j][1],2),round(r[j][2]-r[j][1],2)) for j in ur][:15],len(ur))
# hand mismatch: ours R notes matching ref L notes
allref=[(p,s,e,h) for h in (0,1) for p,s,e in refw[h]]
bad=0;tot=0
for h in (0,1):
    for p,s,e in ours[h][1]:
        c=[x for x in allref if x[0]==p and abs(x[1]-s)<0.2]
        if c: tot+=1; bad+= c[0][3]!=h
print("hand assignment mismatches:",bad,"of",tot)
