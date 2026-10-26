const $=id=>document.getElementById(id);let jobs=[],feedback={};try{feedback=JSON.parse(localStorage.getItem("jobRadarFeedback")||"{}")}catch{}const sample={schemaVersion:1,isSampleData:true,jobs:[]};function esc(v=""){return String(v).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}function dateLabel(v){if(!v||v==="Not stated"||v==="Rolling")return v||"Not stated";const d=new Date(v+"T12:00:00");return Number.isNaN(+d)?v:d.toLocaleDateString(undefined,{year:"numeric",month:"short",day:"numeric"})}function initFilters(){const clusters=[...new Set(jobs.map(j=>j.cluster).filter(Boolean))].sort();$("cluster").innerHTML='<option value="">All clusters</option>'+clusters.map(c=>'<option>'+esc(c)+'</option>').join("")}function filtered(){let list=jobs.filter(j=>feedback[j.id]?.status!=="not-fit"&&(!$("cluster").value||j.cluster===$("cluster").value)&&(!$("tier").value||j.tier===$("tier").value)&&(!$("level").value||j.level===$("level").value)&&(!$("location").value||String(j.location||"").toLowerCase().includes($("location").value.toLowerCase())||String(j.work||"").toLowerCase().includes($("location").value.toLowerCase()))&&(!$("stageFilter").value||($("stageFilter").value==="not-applied"?!feedback[j.id]?.applicationStage||feedback[j.id]?.applicationStage==="Not applied":feedback[j.id]?.applicationStage===$("stageFilter").value))&&(!$("search").value||[j.title,j.company,j.cluster,j.summary,j.fit].join(" ").toLowerCase().includes($("search").value.toLowerCase())));const mode=$("sort").value;return list.sort((a,b)=>mode==="newest"?String(b.posted).localeCompare(String(a.posted)):mode==="deadline"?String(a.deadline||"9999").localeCompare(String(b.deadline||"9999")):(a.rank||999)-(b.rank||999)||String(b.posted).localeCompare(String(a.posted)))}function render(){const active=jobs.filter(j=>feedback[j.id]?.status!=="not-fit").length,fit=Object.values(feedback).filter(f=>f.status==="fit").length,applied=Object.values(feedback).filter(f=>["Applied","Screening","Interview","Offer","Not moving ahead"].includes(f.applicationStage)).length;$("stats").innerHTML=[[active,"Opportunities in feed"],[fit,"Marked fit"],[applied,"Applications tracked"],[new Set(jobs.map(j=>j.cluster)).size,"Role clusters"]].map(s=>'<div class="stat"><strong>'+s[0]+'</strong><span>'+s[1]+'</span></div>').join("");const list=filtered();$("count").textContent="("+list.length+")";if(!list.length){$("jobs").innerHTML='<div class="empty">'+(jobs.length?'No roles match these filters. Clear a filter or adjust your search.':'No verified vacancies are loaded yet. The feed is connected, but its starter file contains no job listings. Check back after the daily search publishes verified results.')+'</div>';return}$("jobs").innerHTML=list.map(j=>{const status=feedback[j.id]?.status||"",stage=feedback[j.id]?.applicationStage||"Not applied",tier=j.tier==="Strongest fit"?"strong":j.tier==="Good fit with stretch"?"stretch":"domain";return '<article class="job-card"><div class="job-top"><div><p class="company">'+esc(j.company)+'</p><h3>'+esc(j.title)+'</h3><div class="job-meta">'+esc(j.location)+' · '+esc(j.work)+' · Posted '+esc(dateLabel(j.posted))+'</div></div><div><span class="tag '+tier+'">'+esc(j.tier)+'</span><span class="tag level">'+esc(j.level)+'</span></div></div><div>'+esc(j.cluster)+'</div><p class="job-desc">'+esc(j.summary)+'</p><p class="job-reason"><b>Why it fits:</b> '+esc(j.fit)+'</p><p class="job-reason"><b>Potential gap:</b> '+esc(j.gap)+'</p><div class="job-meta">Deadline: '+esc(dateLabel(j.deadline))+' · Salary: '+esc(j.salary)+'</div><div class="application-tracker"><label>Application progress<select data-stage-id="'+esc(j.id)+'"><option'+(stage==="Not applied"?" selected":"")+'>Not applied</option><option'+(stage==="Applied"?" selected":"")+'>Applied</option><option'+(stage==="Screening"?" selected":"")+'>Screening</option><option'+(stage==="Interview"?" selected":"")+'>Interview</option><option'+(stage==="Offer"?" selected":"")+'>Offer</option><option'+(stage==="Not moving ahead"?" selected":"")+'>Not moving ahead</option></select></label><span class="stage-note">'+(stage==="Not applied"?"Not yet applied":"Current stage: "+esc(stage))+'</span></div><div class="job-footer"><a href="'+esc(j.url)+'" target="_blank" rel="noopener">View posting ↗</a><div class="actions"><button data-id="'+esc(j.id)+'" data-status="fit" class="'+(status==="fit"?"selected-fit":"")+'">✓ Fit</button><button data-id="'+esc(j.id)+'" data-status="not-fit" class="'+(status==="not-fit"?"selected-no":"")+'">× Not a fit</button><button data-id="'+esc(j.id)+'" data-status="applied" class="'+(status==="applied"?"selected-applied":"")+'">'+(status==="applied"?"✓ Applied":"Mark applied")+'</button></div></div></article>'}).join("");document.querySelectorAll("[data-status]").forEach(b=>b.onclick=()=>{const id=b.dataset.id,s=b.dataset.status;feedback[id]=feedback[id]||{};if(feedback[id].status===s)delete feedback[id].status;else feedback[id].status=s;if(!Object.keys(feedback[id]).length)delete feedback[id];if(feedback[id])feedback[id].updatedAt=new Date().toISOString();localStorage.setItem("jobRadarFeedback",JSON.stringify(feedback));render()});document.querySelectorAll("[data-stage-id]").forEach(sel=>sel.onchange=()=>{const id=sel.dataset.stageId;feedback[id]=feedback[id]||{};feedback[id].applicationStage=sel.value;feedback[id].updatedAt=new Date().toISOString();if(sel.value!=="Not applied")feedback[id].status="applied";localStorage.setItem("jobRadarFeedback",JSON.stringify(feedback));render()})}async function loadFeed(){try{const r=await fetch("./feed.json?updated="+Date.now(),{cache:"no-store"});if(!r.ok)throw Error("Feed unavailable");const data=await r.json();jobs=Array.isArray(data.jobs)?data.jobs:[];$("status").textContent=data.isSampleData?"Sample feed · no verified vacancies loaded":"Feed updated "+dateLabel((data.generatedAt||"").slice(0,10));if(data.isSampleData&&jobs.length)$("status").textContent="Illustrative sample data · not live vacancies";}catch(e){jobs=[];$("status").textContent="Feed unavailable · open via web host to load feed.json"}initFilters();render()}["cluster","tier","level","location","sort","stageFilter"].forEach(id=>$(id).addEventListener("change",render));$("search").addEventListener("input",render);$("clear").onclick=()=>{["cluster","tier","level","location","stageFilter","search"].forEach(id=>$(id).value="");$("sort").value="rank";render()};$("reset").onclick=()=>{if(confirm("Clear feedback saved for this project?")){feedback={};localStorage.removeItem("jobRadarFeedback");render()}};$("export").onclick=()=>{const blob=new Blob([JSON.stringify({feedback,exportedAt:new Date().toISOString()},null,2)],{type:"application/json"}),a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download="job-radar-feedback.json";a.click();URL.revokeObjectURL(a.href)};loadFeed();
/* Supabase email-link authentication */
(function setupEmailSignIn(){
  const authMessage=document.getElementById("authMessage");
  const emailInput=document.getElementById("authEmail");
  const signInButton=document.getElementById("signIn");
  const signOutButton=document.getElementById("signOut");
  const identity=document.getElementById("authIdentity");
  const syncState=document.getElementById("syncState");
  if(!authMessage||!emailInput||!signInButton||!signOutButton)return;
  const say=(text,kind="")=>{authMessage.textContent=text;authMessage.className="auth-message "+kind;};
  if(!window.supabase?.createClient){
    say("Sign-in could not load. Check your internet connection and refresh this page.","error");
    return;
  }
  const client=window.supabase.createClient(
    "https://axypeonrgxsjojxnttaf.supabase.co",
    "sb_publishable_OhbGKJuGLnwp2jwLnon_NA_qjNhEnIa"
  );
  async function paintSession(){
    const {data,error}=await client.auth.getSession();
    if(error){say("Unable to check sign-in status: "+error.message,"error");return;}
    const session=data.session;
    const signedIn=!!session;
    emailInput.disabled=signedIn;
    emailInput.value=signedIn?(session.user.email||""):emailInput.value;
    signInButton.hidden=signedIn;
    signOutButton.hidden=!signedIn;
    identity.textContent=signedIn?"Signed in as "+(session.user.email||"your account"):"Sign in to your Job Radar account";
    syncState.textContent=signedIn?"Signed in":"Not signed in";
    if(signedIn)say("You're signed in. Cloud-saving your application tracker will be enabled once the tracker sync step is connected.","success");
  }
  signInButton.addEventListener("click",async()=>{
    const email=emailInput.value.trim();
    if(!email){say("Enter your email address first.","error");emailInput.focus();return;}
    signInButton.disabled=true;
    say("Sending a secure sign-in link…");
    try{
      const {error}=await client.auth.signInWithOtp({
        email,
        options:{emailRedirectTo:window.location.origin+window.location.pathname}
      });
      if(error)throw error;
      say("Sign-in link sent. Check your inbox and spam folder, then open the link on this device. If no email arrives, the Supabase email provider/settings may need attention.","success");
    }catch(error){say("Could not send sign-in link: "+(error.message||"Please try again."),"error");}
    finally{signInButton.disabled=false;}
  });
  signOutButton.addEventListener("click",async()=>{
    signOutButton.disabled=true;
    const {error}=await client.auth.signOut();
    signOutButton.disabled=false;
    if(error){say("Sign-out failed: "+error.message,"error");return;}
    say("You have signed out. Your current tracker entries remain in this browser.");
    await paintSession();
  });
  client.auth.onAuthStateChange((_event)=>{paintSession();});
  paintSession();
})();
