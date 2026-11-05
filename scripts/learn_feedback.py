"""Apply portal feedback (Fit / Not a fit / Applied) to feed.json.

Usage (from the repo root): python3 -I scripts/learn_feedback.py ~/Downloads/job-radar-feedback.json

Reads a feedback export (never commit it: notes are private and this repo is public),
recovers job details for old ids from feed.json git history, excludes Not-a-fit roles and
reposts, scores patterns (level, title seniority, cluster, contract, employer), re-ranks each
tier, and writes a public-safe feedbackLearning summary with no note text or employer names.
Note-derived rules are applied separately by the daily task.
"""
import json,subprocess,re,collections,unicodedata,sys
exp=json.load(open(sys.argv[1]));fb=exp['feedback']
hist={}
for h in reversed(subprocess.run(['git','log','--format=%H','--','feed.json'],capture_output=True,text=True).stdout.split()):
  try: d=json.loads(subprocess.run(['git','show',h+':feed.json'],capture_output=True,text=True).stdout)
  except Exception: continue
  for j in d.get('jobs',[]): hist[j['id']]=j
hist.update(exp.get('jobs',{}))
def norm(s): return re.sub(r'[^a-z0-9]+',' ',unicodedata.normalize('NFKD',s or '').lower()).strip()
KW=['coordinator','specialist','advisor','manager','director','lead']
CL={'content marketing':'content marketing roles','email':'email-marketing roles','agency pr':'agency PR roles','media relations':'media-relations roles','executive communications':'executive communications roles','internal':'internal communications roles','corporate':'corporate communications roles','digital':'digital communications roles','sport':'sport-sector roles','fundraising':'fundraising communications roles','philanthropic':'philanthropic communications roles','public':'public/Crown-sector roles'}
def pats(j):
  t=norm(j.get('title'));c=norm(j.get('cluster'))
  p={'level:'+j.get('level',''),'employer:'+norm(j.get('company'))}
  if j.get('contract') or re.search(r'contract|\bterm\b|temporary|\[c\]',j.get('title',''),re.I): p.add('contract')
  for k in KW:
    if re.search(r'\b'+k,t): p.add('title:'+k)
  for k in CL:
    if k in c or k in t: p.add('cluster:'+k)
  return p
W={'not-fit':-1,'fit':1,'applied':1.5}
score=collections.Counter();pos=collections.Counter();notfit=set()
for k,v in fb.items():
  w=W.get(v.get('status'),0)
  if v.get('applicationStage') not in (None,'Not applied') and w>=0: w=1.5
  j=hist.get(k)
  if not j or not w: continue
  if w<0: notfit.add((norm(j['company']),norm(j['title'])))
  junior=j.get('level')=='Below target level'
  for p in pats(j):
    # a junior role marked Not a fit says "too junior", not "wrong field": don't charge it to cluster patterns
    if w<0 and junior and p.startswith('cluster:'): continue
    score[p]+=w
    if w>0: pos[p]+=1
active={p:s for p,s in score.items() if s<=-2 or s>=2}
label={'title:coordinator':'coordinator-level roles','title:specialist':'specialist-level roles','title:manager':'manager-titled roles','title:director':'director-level roles','title:advisor':'advisor roles','title:lead':'lead roles','level:Below target level':'below-target-level roles','level:Target level':'target-level (manager+) roles','contract':'contract roles'}
def lab(p):
  if p.startswith('employer:'): return 'same employer'
  if p.startswith('cluster:'): return CL[p.split(':',1)[1]]
  return label.get(p,p)
d=json.load(open('feed.json'))
nf_ids={k for k,v in fb.items() if v.get('status')=='not-fit'}
removed=[j for j in d['jobs'] if j['id'] in nf_ids or (norm(j['company']),norm(j['title'])) in notfit]
d['jobs']=[j for j in d['jobs'] if j not in removed]
for j in d['jobs']:
  j.pop('feedbackAdjustment',None)
  if 'tierBeforeFeedbackDowngrade' in j: j['tier']=j.pop('tierBeforeFeedbackDowngrade')
down=[]
for j in d['jobs']:
  ps=pats(j); s=sum(active.get(p,0) for p in ps); j['_fs']=s
  neg=[p for p in ps if active.get(p,0)<=-2]; posp=[p for p in ps if active.get(p,0)>=2 and not p.startswith('employer:')]
  if s<=-2 and neg: j['feedbackAdjustment']='Ranked lower: similar to roles you marked Not a fit ('+', '.join(sorted({lab(p) for p in neg}))+')'
  elif s>=2 and posp: j['feedbackAdjustment']='Ranked higher: similar to roles you marked Fit or applied to ('+', '.join(sorted({lab(p) for p in posp}))+')'
  for p in ps:
    if (p.startswith('title:') or p.startswith('cluster:')) and active.get(p,0)<=-3 and pos[p]==0 and j['tier']=='Strongest fit':
      j['tierBeforeFeedbackDowngrade']=j['tier'];j['tier']='Good fit with stretch';down.append(j['id'])
      j['feedbackAdjustment']=j.get('feedbackAdjustment','Ranked lower')+'; tier lowered after repeated Not a fit on '+lab(p)
      break
tierO={'Strongest fit':0,'Good fit with stretch':1,'Domain expertise required':2}
d['jobs'].sort(key=lambda j:(tierO[j['tier']],1 if j.get('contract') else 0,-j['_fs'],j['rank']))
for i,j in enumerate(d['jobs'],1): j['rank']=i; j.pop('_fs')
adj=[{'effect':'Roles you marked Not a fit, and reposts of them, are excluded','basis':'%d removed this run'%len(removed)}]
for p,s in sorted(active.items(),key=lambda x:x[1]):
  if p.startswith('employer:'):
    if s<0: adj.append({'effect':'Roles at an employer you passed on repeatedly ranked lower','basis':'net feedback score %+g'%s})
    continue
  eff=lab(p)[0].upper()+lab(p)[1:]+(' ranked lower' if s<0 else ' ranked higher')
  if s<0 and (p.startswith('title:') or p.startswith('cluster:')) and s<=-3 and pos[p]==0: eff+=' and lowered one fit tier'
  adj.append({'effect':eff,'basis':'net feedback score %+g'%s})
d['feedbackLearning']={'available':True,'exportedAt':exp.get('exportedAt'),'signals':{'fit':sum(1 for v in fb.values() if v.get('status')=='fit'),'notFit':len(nf_ids),'withNotes':sum(1 for v in fb.values() if v.get('notes'))},'adjustments':adj}
d['notes']=re.sub(r"Feedback history.*?applied\. ","Feedback learning used the portal's feedback export (see feedbackLearning). ",d.get('notes',''))
with open('feed.json','w') as f: json.dump(d,f,indent=2,ensure_ascii=False); f.write('\n')
print('excluded:',[j['id'] for j in removed]);print('tier-lowered:',down)
for a in adj: print(' -',a['effect'],'|',a['basis'])
print(collections.Counter(j.get('feedbackAdjustment','none').split(':')[0] for j in d['jobs']), len(d['jobs']))
