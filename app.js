const $=id=>document.getElementById(id);let jobs=[],feedback={},supabaseClient=null,currentUser=null,syncBusy=false;try{feedback=JSON.parse(localStorage.getItem("jobRadarFeedback")||"{}")}catch{}const sample={schemaVersion:1,isSampleData:true,jobs:[]};function esc(v=""){return String(v).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}function dateLabel(v){if(!v||v==="Not stated"||v==="Rolling")return v||"Not stated";const d=new Date(v+"T12:00:00");return Number.isNaN(+d)?v:d.toLocaleDateString(undefined,{year:"numeric",month:"short",day:"numeric"})}function normalizeKey(v=""){return String(v).normalize("NFKD").replace(/[\u0300-\u036f]/g,"").toLowerCase().replace(/&/g," and ").replace(/[^a-z0-9]+/g," ").trim()}function canonicalJobUrl(raw=""){try{const u=new URL(raw);u.hash="";for(const k of [...u.searchParams.keys()])if(/^utm_/i.test(k)||["source","sourceid","sourceTypeId","trk","trackingId","ref","refId","lipi","midToken"].includes(k))u.searchParams.delete(k);return (u.hostname||"").toLowerCase().replace(/^www\./,"")+u.pathname.replace(/\/+$/,"").toLowerCase()+(u.searchParams.toString()?"?"+u.searchParams.toString():"")}catch{return String(raw).trim().toLowerCase().replace(/[?#].*$/,"").replace(/\/+$/,"")}}function dedupeJobs(input){const seenUrl=new Map(),seenRole=new Map(),out=[];for(const job of input){const urlKey=canonicalJobUrl(job.url||""),roleKey=[normalizeKey(job.company),normalizeKey(job.title),normalizeKey(job.location)].join("|");let priorIndex=(urlKey&&seenUrl.has(urlKey))?seenUrl.get(urlKey):seenRole.get(roleKey);if(priorIndex===undefined){const idx=out.length;out.push(job);if(urlKey)seenUrl.set(urlKey,idx);seenRole.set(roleKey,idx);continue}const prior=out[priorIndex];const score=j=>[j.url&&!/linkedin\.com\/jobs\/search|indeed\.com\/jobs/i.test(j.url)?2:0,j.summary&&j.fit&&j.gap?2:0,j.salary&&j.salary!=="Not stated"?1:0,j.posted&&j.posted!=="Not stated"?1:0,j.deadline&&j.deadline!=="Not stated"?1:0].reduce((a,b)=>a+b,0);if(score(job)>score(prior))out[priorIndex]=job;const chosen=out[priorIndex];const chosenUrl=canonicalJobUrl(chosen.url||"");if(chosenUrl)seenUrl.set(chosenUrl,priorIndex);seenRole.set(roleKey,priorIndex)}return out}const CONTRACT_RE=/\b(contract|temporary|fixed[- ]term|maternity|parental|leave coverage|interim|secondment|fractional)\b|(?<!(long|short)-)\bterm\b|\[c\]/i;function isContract(j){return j.contract===true||CONTRACT_RE.test(j.title||"")}function applyContractPolicy(j){if(!isContract(j))return j;j.contract=true;if(j.tier==="Strongest fit"){j.tierBeforeContractDowngrade=j.tierBeforeContractDowngrade||j.tier;j.tier="Good fit with stretch"}return j}function initFilters(){const nn=jobs.filter(j=>j.newSinceLastRun&&!isHidden(j)).length,no=$("newOnly").options[1];no.textContent="New since last run ("+nn+")";$("newOnly").title=feedData.previousRunAt?"Roles not in the feed from the run on "+dateLabel(String(feedData.previousRunAt).slice(0,10)):"";const clusters=[...new Set(jobs.map(j=>j.cluster).filter(Boolean))].sort();$("cluster").innerHTML='<option value="">All clusters</option>'+clusters.map(c=>'<option>'+esc(c)+'</option>').join("")}function filtered(){let list=jobs.concat(trackedExtras()).filter(j=>(j.id===pendingReason||!isHidden(j))&&(!$("newOnly").value||j.newSinceLastRun===true)&&(!$("cluster").value||j.cluster===$("cluster").value)&&(!$("target").value||j.roleTarget===$("target").value)&&(!$("mission").value||j.mission===$("mission").value)&&(!$("leadership").value||leadershipKey(j)===$("leadership").value)&&(!$("pay").value||j.payStatus===$("pay").value)&&(!$("arrangement").value||j.arrangement===$("arrangement").value)&&(!$("labelFilter").value||jobLabels(j).includes($("labelFilter").value))&&(!$("tier").value||j.tier===$("tier").value)&&(!$("level").value||j.level===$("level").value)&&(!$("location").value||String(j.location||"").toLowerCase().includes($("location").value.toLowerCase())||String(j.work||"").toLowerCase().includes($("location").value.toLowerCase()))&&(!$("employment").value||($("employment").value==="contract")===!!j.contract)&&(!$("stageFilter").value||($("stageFilter").value==="not-applied"?!feedback[j.id]?.applicationStage||feedback[j.id]?.applicationStage==="Not applied":feedback[j.id]?.applicationStage===$("stageFilter").value))&&(!$("search").value||[j.title,j.company,j.cluster,j.summary,j.fit].join(" ").toLowerCase().includes($("search").value.toLowerCase())));const mode=$("sort").value;return list.sort((a,b)=>(a.tracked?1:0)-(b.tracked?1:0)||(mode==="newest"?String(b.posted).localeCompare(String(a.posted)):mode==="deadline"?String(a.deadline||"9999").localeCompare(String(b.deadline||"9999")):(TIER_ORDER[a.tier]??9)-(TIER_ORDER[b.tier]??9)||learnedScore(b)-learnedScore(a)||(a.rank||999)-(b.rank||999)||(a.contract?1:0)-(b.contract?1:0)||String(b.posted).localeCompare(String(a.posted))))}function render(){signalCache=null;renderRuledOut();const active=jobs.filter(j=>!isHidden(j)).length,fit=Object.values(feedback).filter(f=>f.status==="fit").length,applied=Object.values(feedback).filter(f=>["Applied","Screening","Interview","Offer","Not moving ahead"].includes(f.applicationStage)).length;$("stats").innerHTML=[[active,"Opportunities in feed"],[fit,"Marked fit"],[applied,"Applications tracked"],[new Set(jobs.map(j=>j.cluster)).size,"Role clusters"]].map(s=>'<div class="stat"><strong>'+s[0]+'</strong><span>'+s[1]+'</span></div>').join("");const list=filtered();$("count").textContent="("+list.length+")";if(!list.length){$("jobs").innerHTML='<div class="empty">'+(jobs.length?'No roles match these filters. Clear a filter or adjust your search.':'No verified vacancies are loaded yet. The feed is connected, but its starter file contains no job listings. Check back after the daily search publishes verified results.')+'</div>';return}$("jobs").innerHTML=list.map(j=>{const status=feedback[j.id]?.status||"",stage=feedback[j.id]?.applicationStage||"Not applied",tier=j.tier==="Strongest fit"?"strong":j.tier==="Good fit with stretch"?"stretch":"domain";return '<article class="job-card"><div class="job-top"><div><p class="company">'+esc(j.company)+'</p><h3>'+esc(j.title)+'</h3><div class="job-meta">'+esc(j.location)+' · '+esc(j.work)+' · Posted '+esc(dateLabel(j.posted))+'</div></div><div><span class="tag '+tier+'">'+esc(j.tier)+'</span>'+(j.contract?'<span class="tag contract" title="'+esc(j.tierBeforeContractDowngrade?'Contract role: downgraded from '+j.tierBeforeContractDowngrade+'. Full-time preferred.':'Contract role: full-time preferred.')+'">Contract</span>':'')+(j.tracked?'<span class="tag closed" title="No longer in the daily feed: the posting closed or was screened out. Shown only to you because you are tracking an application.">No longer listed</span>':'')+(j.newSinceLastRun?'<span class="tag new">New</span>':'')+'<span class="tag level">'+esc(j.level)+'</span>'+affinityTag(j)+'</div></div>'+extraTags(j)+reasonPicker(j)+'<div>'+esc(j.cluster)+'</div><p class="job-desc">'+esc(j.summary)+'</p><p class="job-reason"><b>Why it fits:</b> '+esc(j.fit)+'</p><p class="job-reason"><b>Potential gap:</b> '+esc(j.gap)+'</p><div class="job-meta">Deadline: '+esc(dateLabel(j.deadline))+' · Salary: '+esc(j.salary)+'</div><label class="notes-label">Private notes<textarea data-notes-id="'+esc(j.id)+'" rows="2" placeholder="Follow-up dates, contacts, interview notes…">'+esc(feedback[j.id]?.notes||"")+'</textarea></label><div class="application-tracker"><label>Application progress<select data-stage-id="'+esc(j.id)+'"><option'+(stage==="Not applied"?" selected":"")+'>Not applied</option><option'+(stage==="Applied"?" selected":"")+'>Applied</option><option'+(stage==="Screening"?" selected":"")+'>Screening</option><option'+(stage==="Interview"?" selected":"")+'>Interview</option><option'+(stage==="Offer"?" selected":"")+'>Offer</option><option'+(stage==="Not moving ahead"?" selected":"")+'>Not moving ahead</option></select></label><span class="stage-note">'+(stage==="Not applied"?"Not yet applied":"Current stage: "+esc(stage))+'</span></div><div class="job-footer"><a href="'+esc(j.url)+'" target="_blank" rel="noopener"'+(j.urlSource==="aggregator"?' title="No employer application page found yet; this links to a job board">View posting (job board) ↗':'>Apply on employer site ↗')+'</a><div class="actions"><button data-id="'+esc(j.id)+'" data-status="fit" class="'+(status==="fit"?"selected-fit":"")+'">✓ Fit</button><button data-id="'+esc(j.id)+'" data-status="not-fit" class="'+(status==="not-fit"?"selected-no":"")+'">× Not a fit</button></div></div></article>'}).join("");document.querySelectorAll("[data-status]").forEach(b=>b.onclick=()=>{const id=b.dataset.id,s=b.dataset.status;feedback[id]=feedback[id]||{};if(feedback[id].status===s){delete feedback[id].status;delete feedback[id].reasons}else feedback[id].status=s;pendingReason=s==="not-fit"&&feedback[id].status==="not-fit"?id:null;if(!Object.keys(feedback[id]).length)delete feedback[id];if(feedback[id])feedback[id].updatedAt=new Date().toISOString();rememberJob(id);saveFeedback();render()});document.querySelectorAll("[data-stage-id]").forEach(sel=>sel.onchange=()=>{const id=sel.dataset.stageId;feedback[id]=feedback[id]||{};feedback[id].applicationStage=sel.value;if(sel.value==="Applied")feedback[id].status="fit";feedback[id].updatedAt=new Date().toISOString();rememberJob(id);saveFeedback();render()});document.querySelectorAll("[data-notes-id]").forEach(area=>area.onchange=()=>{const id=area.dataset.notesId;feedback[id]=feedback[id]||{};feedback[id].notes=area.value.trim();feedback[id].updatedAt=new Date().toISOString();if(!Object.keys(feedback[id]).some(k=>k!=="notes"&&k!=="updatedAt")&&!feedback[id].notes)delete feedback[id];rememberJob(id);saveFeedback();render()});wireReasonPicker()}async function loadFeed(){try{const r=await fetch("./feed.json?updated="+Date.now(),{cache:"no-store"});if(!r.ok)throw Error("Feed unavailable");const data=await r.json();feedData=data;const [tx,ar]=await Promise.all(["./taxonomy.json","./archive.json"].map(u=>fetch(u+"?updated="+Date.now(),{cache:"no-store"}).then(x=>x.ok?x.json():null).catch(()=>null)));taxonomy=tx;archive=ar?.jobs||{};jobs=dedupeJobs(Array.isArray(data.jobs)?data.jobs:[]).map(applyContractPolicy);renderLearning(data.feedbackLearning);$("status").textContent=data.isSampleData?"Sample feed · no verified vacancies loaded":"Feed updated "+dateLabel((data.generatedAt||"").slice(0,10));if(data.isSampleData&&jobs.length)$("status").textContent="Illustrative sample data · not live vacancies";}catch(e){jobs=[];$("status").textContent="Feed unavailable · open via web host to load feed.json"}initFilters();render()}["newOnly","cluster","target","mission","leadership","pay","arrangement","labelFilter","tier","level","location","employment","sort","stageFilter"].forEach(id=>$(id).addEventListener("change",render));$("search").addEventListener("input",render);$("clear").onclick=()=>{["newOnly","cluster","target","mission","leadership","pay","arrangement","labelFilter","tier","level","location","employment","stageFilter","search"].forEach(id=>$(id).value="");$("sort").value="rank";render()};$("reset").onclick=async()=>{if(confirm("Clear feedback saved for this project? This also deletes your synced tracker rows.")){if(currentUser&&supabaseClient){const {error}=await supabaseClient.from("job_applications").delete().eq("user_id",currentUser.id);if(error){alert("Could not clear cloud data: "+error.message);return;}}feedback={};localStorage.removeItem("jobRadarFeedback");render();if($("syncState"))$("syncState").textContent=currentUser?"Synced to your account":"Local-only mode";}};$("export").onclick=()=>{const blob=new Blob([JSON.stringify(feedbackExport(),null,2)],{type:"application/json"}),a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download="job-radar-feedback.json";a.click();URL.revokeObjectURL(a.href)};loadFeed();

function saveFeedback(){
  localStorage.setItem("jobRadarFeedback",JSON.stringify(feedback));
  if(currentUser&&!syncBusy)syncAllToCloud();
}
async function syncAllToCloud(){
  if(!currentUser||!supabaseClient)return;
  const rows=Object.entries(feedback).filter(([,v])=>v&&Object.keys(v).length).map(([job_id,v])=>({user_id:currentUser.id,job_id,application_stage:v.applicationStage||"Not applied",feedback_status:v.status||null,notes:v.notes||"",applied_at:v.appliedAt||null,updated_at:v.updatedAt||new Date().toISOString()}));
  if(!rows.length)return;
  const {error}=await supabaseClient.from("job_applications").upsert(rows,{onConflict:"user_id,job_id"});
  if(error){const el=$("authMessage");if(el){el.textContent="Cloud sync issue: "+error.message;el.className="auth-message error";}}
  else if($("syncState"))$("syncState").textContent="Synced to your account";
}
async function loadCloudForUser(user){
  currentUser=user;syncBusy=true;
  try{
    const {data,error}=await supabaseClient.from("job_applications").select("job_id,application_stage,feedback_status,notes,applied_at,updated_at");
    if(error)throw error;
    const cloud={};
    (data||[]).forEach(row=>{cloud[row.job_id]={applicationStage:row.application_stage||"Not applied",status:row.feedback_status||undefined,notes:row.notes||"",appliedAt:row.applied_at||undefined,updatedAt:row.updated_at};Object.keys(cloud[row.job_id]).forEach(k=>cloud[row.job_id][k]===undefined&&delete cloud[row.job_id][k]);});
    Object.entries(feedback).forEach(([id,local])=>{if(!cloud[id])cloud[id]=local;else if((local.updatedAt||"")>(cloud[id].updatedAt||""))cloud[id]=Object.assign({},cloud[id],local);for(const k of ["job","reasons","label"])if(local[k]&&!cloud[id][k])cloud[id][k]=local[k];});
    feedback=cloud;localStorage.setItem("jobRadarFeedback",JSON.stringify(feedback));
  }catch(error){const el=$("authMessage");if(el){el.textContent="Signed in, but cloud data could not be loaded: "+error.message;el.className="auth-message error";}}
  finally{syncBusy=false;}
  await syncAllToCloud();render();
}
(function setupEmailSignIn(){
  const authMessage=$("authMessage"),emailInput=$("authEmail"),signInButton=$("signIn"),signOutButton=$("signOut"),identity=$("authIdentity"),syncState=$("syncState");
  if(!authMessage||!emailInput||!signInButton||!signOutButton)return;
  const say=(message,kind="")=>{authMessage.textContent=message;authMessage.className="auth-message "+kind;};
  if(!window.supabase?.createClient){
    signInButton.addEventListener("click",()=>say("The sign-in service did not load in this browser. Check your connection or disable script-blocking extensions, then refresh the page.","error"));
    say("Sign-in service is not available yet. If the button does not respond, refresh the page or check whether a browser extension is blocking scripts.","error");
    return;
  }
  try{supabaseClient=window.supabase.createClient("https://axypeonrgxsjojxnttaf.supabase.co","sb_publishable_OhbGKJuGLnwp2jwLnon_NA_qjNhEnIa");}
  catch(error){signInButton.addEventListener("click",()=>say("Could not initialize sign-in: "+(error.message||"Please refresh and try again."),"error"));say("Could not initialize sign-in: "+(error.message||"Please refresh and try again."),"error");return;}
  async function updateSession(){
    const {data,error}=await supabaseClient.auth.getSession();
    if(error){say("Unable to check sign-in status: "+error.message,"error");return;}
    const user=data.session?.user||null;
    emailInput.disabled=!!user;emailInput.value=user?(user.email||""):emailInput.value;
    signInButton.hidden=!!user;signOutButton.hidden=!user;
    identity.textContent=user?"Signed in as "+(user.email||"your account"):"Sign in to your Job Radar account";
    document.body.classList.toggle("signed-out",!user);
    syncState.textContent=user?"Loading your private tracker…":"Local-only mode";
    if(user){await loadCloudForUser(user);say("Signed in. Your application tracker is connected to your account.","success");}
    else{currentUser=null;syncState.textContent="Local-only mode";}
  }
  signInButton.addEventListener("click",async()=>{
    const email=emailInput.value.trim();if(!email){say("Enter your email address first.","error");emailInput.focus();return;}
    signInButton.disabled=true;say("Sending a secure sign-in link…");
    try{const {error}=await supabaseClient.auth.signInWithOtp({email,options:{emailRedirectTo:window.location.origin+window.location.pathname}});if(error)throw error;say("Sign-in link sent. Check your inbox and spam folder, then open it to return here.","success");}
    catch(error){say("Could not send sign-in link: "+(error.message||"Please try again."),"error");}
    finally{signInButton.disabled=false;}
  });
  signOutButton.addEventListener("click",async()=>{
    signOutButton.disabled=true;const {error}=await supabaseClient.auth.signOut();signOutButton.disabled=false;
    if(error){say("Sign-out failed: "+error.message,"error");return;}currentUser=null;say("Signed out. Your local browser copy remains available.");await updateSession();
  });
  supabaseClient.auth.onAuthStateChange((event)=>{if(event==="SIGNED_IN"||event==="INITIAL_SESSION"||event==="TOKEN_REFRESHED")setTimeout(updateSession,0);if(event==="SIGNED_OUT"){currentUser=null;syncState.textContent="Local-only mode";}});
  updateSession();
})();

// Feedback learning: Fit / Applied / Not a fit picks shape ranking here, and the export feeds the daily search.
const TIER_ORDER={"Strongest fit":0,"Good fit with stretch":1,"Domain expertise required":2};
function jobSnapshot(j){return {company:j.company,title:j.title,cluster:j.cluster,tier:j.tierBeforeContractDowngrade||j.tier,level:j.level,location:j.location,work:j.work,contract:!!j.contract,salary:j.salary,sector:sectorOf(j),roleTarget:j.roleTarget,mission:j.mission}}
// Applications you are tracking stay visible after the posting leaves the public feed. They are rebuilt in your
// browser from your own feedback + the public archive, so the public repo never shows which roles you applied to.
const TRACKED_STAGES=["Applied","Screening","Interview","Offer"];
function trackedExtras(){const ids=new Set(jobs.map(j=>j.id));return Object.entries(feedback).filter(([id,f])=>!id.startsWith("block:")&&!ids.has(id)&&TRACKED_STAGES.includes(f.applicationStage)).map(([id,f])=>{const a=(archive&&archive[id])||f.job;if(!a)return null;return Object.assign({location:"Not stated",work:"Not stated",posted:"Not stated",deadline:"Not stated",salary:"Not stated",cluster:"",tier:"Good fit with stretch",level:"Target level",url:"#"},a,{id,tracked:true,rank:9999,summary:"No longer in the daily feed (the posting closed or no longer passes the feed's filters). Kept here because you are tracking an application.",fit:"See your notes.",gap:"—"})}).filter(Boolean)}
function rememberJob(id){const j=jobs.find(x=>x.id===id)||trackedExtras().find(x=>x.id===id);if(feedback[id]&&j)feedback[id].job=jobSnapshot(j)}
function feedbackSignals(){
  const out=[];
  for(const [id,f] of Object.entries(feedback)){
    const job=f.job||(jobs.find(x=>x.id===id)&&jobSnapshot(jobs.find(x=>x.id===id)));
    if(!job)continue;
    const applied=f.applicationStage&&f.applicationStage!=="Not applied";
    const w=f.status==="not-fit"?-1:applied?1.5:f.status==="fit"?1:0;
    if(w)out.push({id,w,job});
  }
  return out;
}
let signalCache=null,pendingReason=null,taxonomy=null,archive={},feedData={};
const normKey=v=>String(v||"").normalize("NFKD").replace(/[\u0300-\u036f]/g,"").toLowerCase().replace(/[^a-z0-9]+/g," ").trim();
const hasKw=(text,kw)=>{kw=normKey(kw);return new RegExp("\\b"+kw.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")+(kw.length<=3?"\\b":"")).test(text)};
// Traits mirror scripts/learn_feedback.py; both read taxonomy.json.
function sectorOf(j){
  if(j.sector&&!(taxonomy&&taxonomy.legacySectors&&j.sector in taxonomy.legacySectors))return j.sector;if(!taxonomy)return "Other";
  const c=normKey(j.company);
  for(const [k,s] of Object.entries(taxonomy.employerSectors))if(c===k||c.startsWith(k+" "))return s;
  const t=normKey([j.company,j.title,j.cluster].join(" "));
  for(const s of taxonomy.sectors)if(s.keywords.some(k=>hasKw(t,k)))return s.name;
  return "Other";
}
function firstMatch(list,text){for(const x of list)if(x.keywords.some(k=>hasKw(text,k)))return x.name;return null}
function payBandOf(j){
  const s=String(j.salary||"");const nums=[...s.matchAll(/\d{2,3}(?:,\d{3})+/g)].map(m=>+m[0].replace(/,/g,"")).concat([...s.matchAll(/(\d{2,3}(?:\.\d)?)\s*[kK]\b/g)].map(m=>Math.round(+m[1]*1000))).filter(n=>n>=20000);
  if(!nums.length)return null;const top=Math.max(...nums);const b=taxonomy.payBands.find(b=>top<b.max)||taxonomy.payBands[taxonomy.payBands.length-1];return b.name;
}
function workOf(j){const w=String(j.work||"").toLowerCase();return w.includes("hybrid")?"hybrid roles":w.includes("remote")?"fully remote roles":/on-?site|office/.test(w)?"on-site roles":null}
function traits(j){
  if(!taxonomy)return [];
  const out=[],lv={"Below target level":"below-target-level roles","Target level":"target-level (manager+) roles"};
  if(j.level)out.push(["level:"+j.level,lv[j.level]||j.level]);
  const s=firstMatch(taxonomy.seniority,normKey(j.title));if(s)out.push(["seniority:"+s,s]);
  const f=firstMatch(taxonomy.clusterFamilies,normKey((j.cluster||"")+" "+(j.title||"")));if(f)out.push(["family:"+f,f+" roles"]);
  const sec=sectorOf(j);out.push(["sector:"+sec,sec+" employers"]);
  const tg=(taxonomy.roleTargets||[]).find(x=>x.id===j.roleTarget);if(tg)out.push(["target:"+tg.id,tg.name+" roles"]);
  if(j.mission)out.push(["mission:"+j.mission,j.mission+" employers"]);
  const w=workOf(j);if(w)out.push(["work:"+w,w]);
  const p=payBandOf(j);if(p)out.push(["pay:"+p,"roles with "+p]);
  return out;
}
const REASONS=[["junior","Too junior",["level:","seniority:"]],["pay","Pay too low",["pay:"]],["work","Work setup",["work:"]],["role","Not my kind of role",["family:","seniority:","target:"]]];
function jobFor(id){return jobs.find(x=>x.id===id)||feedback[id]?.job||archive[id]||null}
function signalWeight(f){return f.status==="not-fit"?-1:(f.applicationStage&&f.applicationStage!=="Not applied")||f.status==="applied"?1.5:f.status==="fit"?1:0}
function learnedStats(){
  if(signalCache)return signalCache;
  const n={},pos={};let total=0,positives=0;
  for(const [id,f] of Object.entries(feedback)){
    if(id.startsWith("block:"))continue;const j=jobFor(id),w=signalWeight(f);if(!j||!w)continue;total++;
    const reasons=(f.reasons||[]).filter(r=>REASONS.some(x=>x[0]===r));
    for(const [t] of traits(j)){
      if(w<0){
        if(reasons.length){if(!REASONS.filter(x=>reasons.includes(x[0])).some(x=>x[2].some(p=>t.startsWith(p))))continue}
        else if(j.level==="Below target level"&&/^(family|sector):/.test(t))continue;
      }
      n[t]=(n[t]||0)+1;if(w>0)pos[t]=(pos[t]||0)+1;
    }
    if(w>0)positives++;
  }
  const L=taxonomy?taxonomy.learning:{},base=positives/Math.max(1,total),active={};
  for(const t in n){const r=((pos[t]||0)+L.smoothing*base)/(n[t]+L.smoothing)/(base||1);if(n[t]>=L.minPicks&&(r<=L.lowerRatio||r>=L.higherRatio))active[t]=Math.log(r)}
  return signalCache={n,pos,active,base};
}
function learned(j){
  if(!taxonomy)return {score:0,tag:null};
  const {n,pos,active}=learnedStats(),L=taxonomy.learning,tr=traits(j).filter(([t])=>t in active);
  const score=tr.reduce((s,[t])=>s+active[t]*(active[t]<0?L.negativeWeight:1),0);
  const weak=tr.filter(([t])=>active[t]<0).sort((a,b)=>active[a[0]]-active[b[0]])[0];
  const strong=tr.filter(([t])=>active[t]>=Math.log(L.tagHigherRatio)).sort((a,b)=>active[b[0]]-active[a[0]])[0];
  const pick=weak||strong;
  return {score,tag:pick&&{up:!weak,label:pick[1],basis:(pos[pick[0]]||0)+" of "+n[pick[0]]+" picked"}};
}
function learnedScore(j){return feedback[j.id]?0:learned(j).score}
function affinityTag(j){
  if(feedback[j.id])return "";const t=learned(j).tag;if(!t)return "";
  return t.up?'<span class="tag affinity-up" title="You picked '+esc(t.basis)+' of these">Like your picks: '+esc(t.label)+'</span>':'<span class="tag affinity-down" title="You picked '+esc(t.basis)+' of these">Often passed on: '+esc(t.label)+'</span>';
}
// Rule-outs are stored as feedback entries ("block:employer:<key>" / "block:sector:<key>") so they sync and export like any pick.
function blockKey(kind,value){return "block:"+kind+":"+normKey(value).replace(/ /g,"-")}
function excludedSectors(){return new Set([...(feedData.excludedSectors||taxonomy?.excludedSectors||[]),...Object.entries(feedback).filter(([k,f])=>k.startsWith("block:sector:")&&f.status==="not-fit").map(([k,f])=>f.label||k.slice(13))])}
function isHidden(j){
  const f=feedback[j.id];if(f&&f.status&&f.status!=="not-fit")return false;
  if(f?.status==="not-fit")return true;
  if(feedback[blockKey("employer",j.company)]?.status==="not-fit")return true;
  return excludedSectors().has(sectorOf(j));
}
function toggleBlock(kind,value){const k=blockKey(kind,value);if(feedback[k])delete feedback[k];else feedback[k]={status:"not-fit",label:value,updatedAt:new Date().toISOString()};}
function reasonPicker(j){
  if(pendingReason!==j.id)return "";
  const f=feedback[j.id]||{},on=r=>(f.reasons||[]).includes(r),sec=sectorOf(j);
  const chip=(r,label)=>'<button class="reason'+(on(r)?" on":"")+'" data-reason="'+r+'" data-id="'+esc(j.id)+'">'+esc(label)+'</button>';
  return '<div class="reason-picker"><span>Why not a fit? (optional — sharpens future tags)</span>'+REASONS.map(([r,l])=>chip(r,l)).join("")+chip("employer","Rule out "+j.company)+(sec!=="Other"?chip("industry","Rule out "+sec+" employers"):"")+'<button class="reason-done" data-reason-done="1">Done</button></div>';
}
function wireReasonPicker(){
  document.querySelectorAll("[data-reason]").forEach(b=>b.onclick=()=>{
    const id=b.dataset.id,r=b.dataset.reason,f=feedback[id];if(!f)return;const j=jobFor(id);
    f.reasons=f.reasons||[];const had=f.reasons.includes(r);f.reasons=had?f.reasons.filter(x=>x!==r):f.reasons.concat(r);
    if(r==="employer"&&j)toggleBlock("employer",j.company);
    if(r==="industry"&&j)toggleBlock("sector",sectorOf(j));
    f.updatedAt=new Date().toISOString();saveFeedback();render();
  });
  document.querySelectorAll("[data-reason-done]").forEach(b=>b.onclick=()=>{pendingReason=null;render()});
}
function renderRuledOut(){
  const el=$("ruledOut");if(!el)return;
  const blocks=Object.entries(feedback).filter(([k,f])=>k.startsWith("block:")&&f.status==="not-fit");
  el.innerHTML=blocks.length?'<hr><p><b>Ruled out</b></p>'+blocks.map(([k,f])=>'<p class="ruled">'+esc(f.label||k.split(":").slice(2).join(":").replace(/-/g," "))+' <button data-unblock="'+esc(k)+'">Undo</button></p>').join(""):"";
  el.querySelectorAll("[data-unblock]").forEach(b=>b.onclick=()=>{delete feedback[b.dataset.unblock];saveFeedback();render()});
}
function feedbackExport(){
  const jobsById={};
  for(const [id,f] of Object.entries(feedback)){if(id.startsWith("block:"))continue;const j=jobs.find(x=>x.id===id);const snap=j?jobSnapshot(j):f.job||archive[id];if(snap)jobsById[id]=snap}
  return {schema:"job-radar-feedback/3",exportedAt:new Date().toISOString(),feedback,jobs:jobsById};
}
function renderLearning(l){
  const el=$("learning");if(!el)return;
  if(!l){el.innerHTML="";return}
  const items=(l.adjustments||[]).map(x=>"<li>"+esc(x.effect)+(x.basis?" <span>("+esc(x.basis)+")</span>":"")+"</li>").join("");
  const nb=$("notices");if(nb)nb.innerHTML=(l.notices||[]).map(x=>"<p>"+esc(x)+"</p>").join("");
  el.innerHTML="<hr><p><b>What the daily search learned</b></p>"+(l.available?"<p>From your export of "+esc(dateLabel(String(l.exportedAt||"").slice(0,10)))+".</p>"+(items?"<ul>"+items+"</ul>":"<p>No patterns strong enough to change ranking yet.</p>"):"<p>"+esc(l.note||"No feedback export found for the last run.")+"</p>");
}

// Role targets, mission, people leadership, pay and arrangement labels (fields written by the daily routine and scripts/learn_feedback.py).
function leadershipKey(j){return j.peopleLeadership==="yes"?"yes":j.peopleLeadership==="likely"?"likely":j.peopleLeadership==="no"?"no":"not stated"}
function jobLabels(j){const l=(j.labels||[]).slice();if(j.peopleLeadership==="no"&&!l.includes("no people leadership"))l.push("no people leadership");return l}
function extraTags(j){
  const t=(x,c,title)=>'<span class="tag '+c+'"'+(title?' title="'+esc(title)+'"':"")+'>'+esc(x)+'</span>',out=[];
  const tg=(taxonomy&&taxonomy.roleTargets||[]).find(x=>x.id===j.roleTarget);
  if(tg)out.push(t(tg.tag,"target"));if(tg&&tg.newCategory)out.push(t("New category","newcat","A role type you have not seen before. Pass on it if it does not fit and it will rank lower."));
  if(j.mission)out.push(t(j.mission,"mission"));
  if(j.arrangement&&j.arrangement!=="Not stated")out.push(t(j.arrangement,j.arrangement==="On-site"?"warn":"good"));
  out.push(t(j.payStatus==="meets target"?"Meets $100K target":j.payStatus==="below floor"?"Below $75K floor":j.payStatus==="above floor"?"Above $75K floor":"Pay not stated",j.payStatus==="meets target"?"good":j.payStatus==="below floor"?"warn":"muted"));
  const lk=leadershipKey(j);out.push(t(lk==="yes"?"People leadership":lk==="likely"?"People leadership likely (title)":lk==="no"?"No people leadership":"Leadership not stated",lk==="no"?"warn":lk==="not stated"?"muted":"good"));
  for(const b of j.benefits||[])out.push(t(b,"good","Mentioned in the posting"));
  for(const l of jobLabels(j))if(l!=="no people leadership")out.push(t(l,"warn"));
  return '<div class="meta-tags">'+out.join("")+'</div>';
}
