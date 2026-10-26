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
Valid levels: `Target level`, `Below target level`.
Locations: `Toronto`, `Hamilton`, `Remote Canada`. Use `work` for Remote, Hybrid or On-site.

Only mark `isSampleData` false after replacing the starter feed with verified current postings. Do not use example.com links in a live feed. Prefer employer career pages. A published feed may be public; do not include private notes or sensitive personal data.