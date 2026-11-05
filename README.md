# Communications Job Radar

A responsive, personalized front-end for a communications job-search portal.

## Current status
This repository contains the portal UI and a starter feed file. The starter feed has **zero vacancies** and is explicitly marked as sample data. No live vacancies are represented as verified jobs yet.

## Deploy
The site is static and requires no build step:
1. In GitHub, open **Settings → Pages**.
2. Under **Build and deployment**, choose **Deploy from a branch**.
3. Choose branch `main` and folder `/(root)`, then save.
4. Wait for GitHub Pages to publish the site. If the repository is private, confirm your GitHub plan and repository settings allow Pages publishing.

## Features
- Cluster, fit tier, level, location and keyword filters
- Strongest-fit-first, newest-first and deadline sorting
- Fit, Not a fit and Applied feedback controls
- Feedback stored in browser localStorage and exportable as JSON
- Loads `feed.json` from the same site origin
- Contract badge and employment-type filter (full-time preferred; contract roles downgraded one fit tier)
- Responsive layout

## Feed contract
Replace `feed.json` with a JSON object containing `schemaVersion`, `generatedAt` (ISO timestamp), `isSampleData: false`, `source`, and a `jobs` array. Each job should include `id`, `company`, `title`, `cluster`, `tier`, `level`, `location`, `work`, `posted`, `deadline`, `salary`, `url`, `summary`, `fit`, `gap`, and `rank`. Unknown dates, deadlines and salary should be stated rather than invented.

Valid fit tiers: `Strongest fit`, `Good fit with stretch`, `Domain expertise required`.
Valid level flags: `Target level`, `Below target level`.
Locations should be `Toronto`, `Hamilton`, or `Remote Canada`; use `work` for `Remote`, `Hybrid`, or `On-site`.

Only set `isSampleData` to false after adding source-verified, current postings. Prefer employer career pages; exclude expired, redirected and stale roles unless a recent repost is verified.

## Search profile
Target communications leadership and manager+ roles in Toronto/GTA, Hamilton and Remote Canada, including digital communications/content, content strategy/editorial, fundraising and philanthropic communications, sport-sector communications/partnerships, internal communications, public/Crown-sector advisory, executive communications, agency PR, research/knowledge translation, brand storytelling and contract consulting. Specialist/coordinator roles may be included but should be flagged below target level. Full-time permanent roles are preferred over contract work: contract, term, fixed-term, temporary, interim and leave-coverage roles are kept but set `contract: true`, show a **Contract** badge in the UI, and drop one fit tier (Strongest fit → Good fit with stretch; record the original in `tierBeforeContractDowngrade`). Contract roles rank after full-time roles in the same tier. The UI also applies this downgrade as a backstop when a feed marks a role `contract: true` or its title names a contract/term arrangement. Salary is not a hard gate. Flag French only when required. Rank down roles that require deep specialist expertise in an unrelated domain.

Candidate context: Content Manager at UJA Federation of Greater Toronto, including content strategy for a $78M+ annual campaign, flagship publications, content calendars and senior leadership advisory; former Manager, Digital Media & Communications at AthletesCAN with digital growth, web/SEO and media relations; Co-Founder & CEO of Mile 27 PR; Canadian Olympic Committee communications; MA in Applied Health Sciences with research on gender representation in sport media. Not bilingual in French.

## Production work still required
The front end does not crawl job boards or independently verify listings. A scheduled ingestion/verification service must search employer pages and relevant aggregators, extract and verify deadlines, locations, salary, French requirements and direct application URLs, deduplicate postings, and publish the feed. Feedback is local to this browser until a backend is added.

## Feedback learning

Fit, Not a fit, Applied and private notes shape both the portal and the daily search:

- **In the portal (immediate, private):** Not a fit hides a role. Within each fit tier, roles similar to your Fit/Applied picks (same cluster, employer, level or contract status) rise and get a *Like your picks* tag; roles similar to Not a fit picks sink and get a *Like roles you passed on* tag. Each feedback entry keeps a snapshot of the job so the signal survives after the posting closes.
- **In the daily search:** click **Export feedback** now and then. The scheduled task reads the newest `job-radar-feedback*.json` in your Downloads folder (or `~/.config/communications-job-radar/feedback.json`) and runs `scripts/learn_feedback.py`, which:
  - excludes roles marked Not a fit and any repost of them;
  - excludes reposts of roles where your application stage is *Not moving ahead*;
  - scores patterns (level, title seniority, cluster, contract, employer) by comparing each pattern's share of Fit/Applied picks with your overall share, so traits common to everything you see stay neutral; with at least 3 picks, a pattern 12+ points below ranks lower within its tier and 12+ points above ranks higher; a title keyword or cluster with no Fit/Applied picks at 15+ points below also drops one fit tier (`tierBeforeFeedbackDowngrade`); a junior role marked Not a fit counts against seniority, not against its field;
  - ranks roles requiring French fluency lower when a Not-a-fit note cites French;
  - never lifts a role above its cluster tier and never hides a role on a pattern alone.
  The task also reads notes for reasons ("too junior", "no agency roles") and applies them as rules.
- **Privacy:** this repository is public. The export and notes are never committed (`.gitignore` blocks them); `feed.json` carries only a generic `feedbackLearning` summary and per-job `feedbackAdjustment` lines with no note text or employer names. The portal shows that summary under *What the daily search learned*.

## Duplicate prevention

The tracker deduplicates loaded vacancies by canonical application URL and by normalized employer + role title + location. Normalize case, punctuation, accents, trailing slashes and common tracking parameters. Prefer active, source-verified employer postings over aggregator duplicates; preserve genuinely distinct requisitions and locations. Before publishing a feed, run the same checks across all sources and manually review near-duplicates and reposts. Keep stable job IDs so existing application stages, notes and Fit/Not a fit feedback remain attached; never reset feedback during feed refreshes. Runtime deduplication is a backstop, not a substitute for checking that a role is still open.
