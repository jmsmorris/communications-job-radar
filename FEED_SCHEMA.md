# feed.json schema

The site fetches `./feed.json` on page load.

```json
{
  "schemaVersion": 1,
  "generatedAt": "2026-10-27T12:00:00Z",
  "isSampleData": false,
  "source": "Daily Communications Job Feed",
  "jobs": [{
    "id": "employer-title-unique-id",
    "company": "Employer name",
    "title": "Communications Manager",
    "cluster": "Digital Communications / Digital Content",
    "tier": "Strongest fit",
    "level": "Target level",
    "location": "Toronto",
    "work": "Hybrid",
    "posted": "2026-10-27",
    "deadline": "Not stated",
    "salary": "Not stated",
    "url": "https://employer.example/careers/job-id",
    "summary": "Factual summary of the role.",
    "fit": "Evidence-based match to the candidate profile.",
    "gap": "Material gap, or 'No obvious gap stated'.",
    "rank": 1
  }]
}
```

Valid tiers: `Strongest fit`, `Good fit with stretch`, `Domain expertise required`.

Contract roles: set `"contract": true` for contract, term, fixed-term, temporary, interim or leave-coverage roles (optionally `"contractTerm": "12 months"`). Full-time is preferred, so a contract role drops one tier — `Strongest fit` becomes `Good fit with stretch`, with the original kept in `"tierBeforeContractDowngrade"` — and ranks after full-time roles in its tier. The gap line should name the contract term.
Valid levels: `Target level`, `Below target level`.
Locations: `Toronto`, `Hamilton`, `Remote Canada`. Use `work` for Remote, Hybrid or On-site.

Only mark `isSampleData` false after replacing the starter feed with verified current postings. Do not use example.com links in a live feed. Prefer employer career pages. A published feed may be public; do not include private notes or sensitive personal data.
Optional per-job fields written by `scripts/learn_feedback.py`: `sector` (from `taxonomy.json`), `feedbackAdjustment` (one public reason line), `tierBeforeFeedbackDowngrade`. Top-level: `excludedSectors`, `feedbackLearning`. `archive.json` maps every job id ever listed to its public posting details.

`url` must be the employer's own application page (careers site or ATS such as Workday, Lever, Greenhouse, iCIMS, Dayforce, UltiPro, Oracle, SuccessFactors) whenever one exists — not LinkedIn or a job board. Set `urlSource` to `"employer"` or `"aggregator"`; an aggregator link is kept only when no employer page can be found, and the portal labels it "job board".

Seniority ranking: Jacob's highest title so far is Manager. Director / Associate Director / Senior Director / Account Director / Head roles are never "Strongest fit"; use `Good fit with stretch` (optional `tierBeforeSeniorityDowngrade`) and rank them after manager-level roles. Senior Manager roles rank after Manager roles within a tier. `learn_feedback.py` applies this tier rule and order itself (title seniority sorts before feedback score), so it holds after every run.

New postings: `learn_feedback.py` sets `"newSinceLastRun": true` on roles that were not in the previous run's feed (the newest "Refresh daily communications job feed" commit with a different `generatedAt`) and writes top-level `previousRunAt`. The portal's "New Postings" filter and "New" tag read these.

Role targets and preferences (2026-11-11). Optional per-job fields the routine fills from the posting: `roleTarget` ("A" editorial & publications leadership, "B" sport communications leadership, "C" health content / plain language — shown with a "New category" tag), `mission` ("Sport", "Jewish community", "Health & wellness"), `peopleLeadership` ("yes", "no", "not stated"), `orgSize` ("large", "small"), `labels` (any of "social-heavy", "sales duties", "small or early-stage", "sole communicator"), `benefits` (any of "pension", "RRSP match", "extended health"). `learn_feedback.py` infers missing roleTarget / mission / peopleLeadership ("likely" when only the title suggests it) and always computes `payStatus` ("below floor" under $75K top of range, "above floor", "meets target" at $100K+, "pay not stated"), `arrangement` (Hybrid / Remote / On-site / Not stated) and `priority` (weights in taxonomy.json `priority`; orders roles inside a tier after the title-seniority step). Hard-excluded sectors: Religious organization (non-Jewish), Tobacco, Gambling. `feedbackLearning.notices` lists categories moved down because they were repeatedly passed on; the portal shows them in a banner above the feed.
