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

Seniority ranking: Jacob's highest title so far is Manager. Director / Associate Director / Senior Director / Account Director / Head roles are never "Strongest fit"; use `Good fit with stretch` (optional `tierBeforeSeniorityDowngrade`) and rank them after manager-level roles. Senior Manager roles rank after Manager roles within a tier. `learn_feedback.py` reorders ranks, so re-apply this order after running it.
