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

Only set `isSampleData` to false after adding source-verified, current postings. Link every posting to the employer's own application page (careers site or ATS), not LinkedIn or a job board, whenever one exists, and set `urlSource` (`employer` / `aggregator`); exclude expired, redirected and stale roles unless a recent repost is verified.

## Search profile
Target communications leadership and manager+ roles in Toronto/GTA, Hamilton and Remote Canada, including digital communications/content, content strategy/editorial, fundraising and philanthropic communications, sport-sector communications/partnerships, internal communications, public/Crown-sector advisory, executive communications, agency PR, research/knowledge translation, brand storytelling and contract consulting. Specialist/coordinator roles may be included but should be flagged below target level. Full-time permanent roles are preferred over contract work: contract, term, fixed-term, temporary, interim and leave-coverage roles are kept but set `contract: true`, show a **Contract** badge in the UI, and drop one fit tier (Strongest fit → Good fit with stretch; record the original in `tierBeforeContractDowngrade`). Contract roles rank after full-time roles in the same tier. The UI also applies this downgrade as a backstop when a feed marks a role `contract: true` or its title names a contract/term arrangement. Salary is not a hard gate. Flag French only when required. Rank down roles that require deep specialist expertise in an unrelated domain.

Candidate context: Content Manager at UJA Federation of Greater Toronto, including content strategy for a $78M+ annual campaign, flagship publications, content calendars and senior leadership advisory; former Manager, Digital Media & Communications at AthletesCAN with digital growth, web/SEO and media relations; Co-Founder & CEO of Mile 27 PR; Canadian Olympic Committee communications; MA in Applied Health Sciences with research on gender representation in sport media. Not bilingual in French.

## Production work still required
The front end does not crawl job boards or independently verify listings. A scheduled ingestion/verification service must search employer pages and relevant aggregators, extract and verify deadlines, locations, salary, French requirements and direct application URLs, deduplicate postings, and publish the feed. Feedback is local to this browser until a backend is added.

## Feedback learning

Fit, Not a fit, Applied, reasons, rule-outs and private notes shape both the portal and the daily search. Both use the same traits from `taxonomy.json` — **level, title seniority, role family, sector, work setup and pay band** — so the portal's tags and the daily feed agree.

- **How a trait is judged:** its share of Fit/Applied picks is compared with your overall share. It needs at least 3 picks; at 0.6× your usual rate or lower the trait ranks roles lower, at 1.6× or higher it ranks them higher. Traits common to everything you see (e.g. "manager" titles) stay neutral, and a weak trait weighs double against a liked one.
- **Tags:** each card shows at most one tag naming its reason — *Often passed on: below-target-level roles (4 of 46 picked)* first if any trait is weak, otherwise *Like your picks: …* when a trait is at least twice your usual rate. Most cards have no tag. Your own picks are never tagged.
- **Not a fit reasons:** after clicking × Not a fit, pick why — *Too junior*, *Pay too low*, *Work setup*, *Not my kind of role* — and that pick counts only against those traits. Without a reason, a junior role counts as "too junior", not against its field or sector.
- **Rule out employer / industry:** also in the reason picker. Employers are otherwise judged role by role; a ruled-out employer or industry is hidden and excluded from future feeds. Undo is in the side panel under *Ruled out*. Religious organizations and tobacco are excluded by default (`excludedSectors`).
- **Daily search:** click **Export feedback** now and then. The scheduled task reads the newest `job-radar-feedback*.json` in Downloads and runs `scripts/learn_feedback.py`, which also excludes reposts of roles marked *Not moving ahead* and applies note-based rules (e.g. French required). `archive.json` keeps public details of every posting ever listed, so older picks keep counting after a posting closes.
- **Privacy:** this repository is public. Exports and notes are never committed (`.gitignore` blocks them); `feed.json` carries only trait-level summaries and per-job reason lines.

## Duplicate prevention

The tracker deduplicates loaded vacancies by canonical application URL and by normalized employer + role title + location. Normalize case, punctuation, accents, trailing slashes and common tracking parameters. Prefer active, source-verified employer postings over aggregator duplicates; preserve genuinely distinct requisitions and locations. Before publishing a feed, run the same checks across all sources and manually review near-duplicates and reposts. Keep stable job IDs so existing application stages, notes and Fit/Not a fit feedback remain attached; never reset feedback during feed refreshes. Runtime deduplication is a backstop, not a substitute for checking that a role is still open.
