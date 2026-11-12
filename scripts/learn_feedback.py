"""Apply portal feedback (Fit / Not a fit / Applied, reasons, rule-outs, notes) to feed.json.

Usage (from the repo root): python3 -I scripts/learn_feedback.py ~/Downloads/job-radar-feedback.json
Without an export it still assigns sectors, applies taxonomy.json's excluded sectors and
refreshes archive.json.

The export is private (notes, applications) and this repo is public: never commit it.
Traits come from taxonomy.json and match app.js, so portal tags and the daily feed agree:
  - each trait (level, title seniority, role family, sector, work setup, pay band) is compared
    with the overall share of Fit/Applied picks; it moves ranking only with >= minPicks picks and
    a pick rate <= lowerRatio or >= higherRatio times the overall rate, so traits common to
    everything shown stay neutral; a weak trait (negativeWeight) outweighs a liked one, and a
    card shows one tag: its clearest weak trait, else a strongly liked one (>= tagHigherRatio);
  - a Not a fit with reasons counts only against the matching traits; one without reasons on a
    junior role counts as "too junior", not against its family or sector;
  - employers count only when ruled out (a "block:employer:" entry); sectors are hidden only
    when ruled out ("block:sector:") or listed in taxonomy.json excludedSectors.
"""
import json, subprocess, re, collections, unicodedata, sys, os, math

TAX = json.load(open('taxonomy.json'))
LEARN = TAX['learning']


def norm(s):
    return re.sub(r'[^a-z0-9]+', ' ', unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()).strip()


def has_kw(text, kw):
    kw = norm(kw)
    return re.search(r'\b' + re.escape(kw) + (r'\b' if len(kw) <= 3 else ''), text) is not None


def sector_of(j):
    if j.get('sector') and j['sector'] not in TAX.get('legacySectors', {}):
        return j['sector']
    company = norm(j.get('company'))
    for key, sector in TAX['employerSectors'].items():
        if company == key or company.startswith(key + ' '):
            return sector
    text = norm(' '.join([j.get('company', ''), j.get('title', ''), j.get('cluster', '')]))
    for s in TAX['sectors']:
        if any(has_kw(text, k) for k in s['keywords']):
            return s['name']
    return 'Other'


def family_of(j):
    text = norm(j.get('cluster', '') + ' ' + j.get('title', ''))
    for f in TAX['clusterFamilies']:
        if any(has_kw(text, k) for k in f['keywords']):
            return f['name']
    return None


def seniority_of(j):
    text = norm(j.get('title'))
    for s in TAX['seniority']:
        if any(has_kw(text, k) for k in s['keywords']):
            return s['name']
    return None


AGG = re.compile(r'sportswork|sirc\.ca|linkedin|indeed|glassdoor|charityvillage|jobbank|workopolis|eluta|goodwork|gcjobs|jobs\.gc\.ca|ziprecruiter|talent\.com', re.I)


def ckey(j):
    """Employer + title identity used to spot the same posting listed twice (e.g. employer page and job board)."""
    co = re.sub(r'\([^)]*\)', ' ', j.get('company') or '')
    co = norm(co)
    co = re.sub(r'\b(the|inc|ltd|limited|corp|corporation|canada|canadian)\b', ' ', co)
    co = re.sub(r'\s+', ' ', co).strip()
    ti = re.sub(r'\([^)]*\)', ' ', j.get('title') or '')
    ti = re.sub(r'\s+', ' ', norm(ti)).strip()
    return co, ti


def same_place(a, b):
    ta, tb = set(norm(a.get('location')).split()) - {'gta', 'canada', 'ontario', 'on', 'or', 'and'}, set(norm(b.get('location')).split()) - {'gta', 'canada', 'ontario', 'on', 'or', 'and'}
    return not ta or not tb or bool(ta & tb)


def pay_band_of(j):
    sal = j.get('salary') or ''
    nums = [int(n.replace(',', '')) for n in re.findall(r'\d{2,3}(?:,\d{3})+', sal)]
    nums += [int(float(n) * 1000) for n in re.findall(r'(\d{2,3}(?:\.\d)?)\s*[kK]\b', sal)]
    nums = [n for n in nums if n >= 20000]
    if not nums:
        return None
    top = max(nums)
    for b in TAX['payBands']:
        if top < b['max']:
            return b['name']
    return TAX['payBands'][-1]['name']


def salary_top(j):
    sal = j.get('salary') or ''
    if re.search(r'hour|/hr|per hr', sal, re.I):
        return None
    nums = [int(n.replace(',', '')) for n in re.findall(r'\d{2,3}(?:,\d{3})+', sal)]
    nums += [int(float(n) * 1000) for n in re.findall(r'(\d{2,3}(?:\.\d)?)\s*[kK]\b', sal)]
    nums = [n for n in nums if n >= 20000]
    return max(nums) if nums else None


def pay_status_of(j):
    """Jacob's floor ($75K) and target ($100K) are judged on the top of the posted range."""
    top = salary_top(j)
    if top is None: return 'pay not stated'
    if top < TAX['pay']['floor']: return 'below floor'
    if top >= TAX['pay']['target']: return 'meets target'
    return 'above floor'


def arrangement_of(j):
    w = (j.get('work') or '').lower()
    if 'hybrid' in w: return 'Hybrid'
    if 'remote' in w: return 'Remote'
    if re.search(r'on-?site|office|in-person', w): return 'On-site'
    return 'Not stated'


def hamilton_area(j):
    loc = (j.get('location') or '').lower()
    return any(k in loc for k in TAX['hamiltonArea'])


def onsite_days(j):
    """Days a week in the office: the routine's onsiteDays, else 5 for fully on-site roles, else unknown."""
    v = j.get('onsiteDays')
    if isinstance(v, (int, float)) and 0 <= v <= 5: return int(v)
    return 5 if arrangement_of(j) == 'On-site' else None


def flags_of(j):
    """Computed labels (not routine-supplied): pension/benefits gaps and on-site load.
    Benefit flags need a posting that was actually read (benefitsChecked is not false)."""
    out = []
    if j.get('benefitsChecked') is not False:
        ben = j.get('benefits') or []
        if 'pension' not in ben and 'RRSP match' not in ben: out.append('no pension')  # an employer RRSP match counts as retirement cover
        if not ben: out.append('no benefits mentioned')
    days = onsite_days(j)
    if days is not None and days >= 4: out.append('heavy on-site')
    if arrangement_of(j) == 'On-site' and not hamilton_area(j): out.append('on-site outside Hamilton')
    return out


def sideways_ok(j):
    """A sideways title is fine when the pay is higher: no title-seniority markdown for non-step-up titles."""
    if j.get('payStatus') not in TAX['titleRule']['sidewaysOkPay']: return False
    return not re.search(r'\b(director|head|senior manager|sr\.? manager|vice president|vp)\b', (j.get('title') or '').lower())


def target_of(j):
    """Role target A/B/C: the routine's own value wins; otherwise inferred from the title and cluster."""
    if j.get('roleTarget') in ('A', 'B', 'C'): return j['roleTarget']
    title = norm(j.get('title')); head = norm((j.get('title') or '') + ' ' + (j.get('cluster') or ''))
    if re.search(r'managing editor|editorial director|editor in chief|(head|director) of (content|publications?|editorial)|publications? (manager|director|lead)|editorial (manager|lead|strategy)', title): return 'A'
    if re.search(r'(director|head) of (corporate |external |strategic |marketing and )?communications|communications director|director communications', title) \
            and (sector_of(j) == 'Sport & recreation' or has_kw(norm(j.get('company')), 'sport') or has_kw(norm(j.get('company')), 'athletics')):
        return 'B'
    if re.search(r'health content|content designer|patient education|plain language|health communications|knowledge translation|health information|health literacy', head): return 'C'
    return None


def mission_of(j):
    if j.get('mission') in TAX['missions']: return j['mission']
    co = norm(' '.join([j.get('company') or '', j.get('title') or '']))
    if sector_of(j) == 'Sport & recreation' or any(has_kw(co, k) for k in ('sport', 'olympic', 'paralympic', 'athletics')): return 'Sport'
    if re.search(r'\bjewish\b|\buja\b|\bhillel\b|\bjcc\b', co): return 'Jewish community'
    if sector_of(j) == 'Health & hospital' or any(has_kw(co, k) for k in ('health', 'wellness', 'hospital')): return 'Health & wellness'
    return None


def leadership_of(j):
    v = j.get('peopleLeadership')
    if v in ('yes', 'no', 'not stated'): return v
    # Not read from the posting: a Manager/Director/Head title only suggests it.
    return 'likely' if re.search(r'\b(manager|director|head|managing|lead)\b', (j.get('title') or '').lower()) else 'not stated'


def priority_of(j):
    """Preference score used to order roles inside a tier (weights in taxonomy.json priority)."""
    P = TAX['priority']; score = 0.0
    score += P['target'].get(j.get('roleTarget'), 0)
    score += P['mission'].get(j.get('mission'), 0)
    score += P['leadership'].get(j.get('peopleLeadership'), 0)
    heavy = 'heavy on-site' in (j.get('flags') or [])
    if j.get('arrangement') == 'On-site':
        score += 0 if hamilton_area(j) else P['arrangement']['On-site']  # five days is acceptable in the Hamilton area only
    elif not heavy:
        score += P['arrangement'].get(j.get('arrangement'), 0)
    score += sum(P['flags'].get(f, 0) for f in (j.get('flags') or []))
    score += P['pay'].get(j.get('payStatus'), 0)
    score += min(2, sum(P['benefits'].get(b, 0) for b in (j.get('benefits') or [])))
    score += sum(P['labels'].get(l, 0) for l in (j.get('labels') or []))
    score += P['orgSize'].get(j.get('orgSize'), 0)
    return round(score, 2)


def work_of(j):
    w = (j.get('work') or '').lower()
    if 'hybrid' in w: return 'hybrid roles'
    if 'remote' in w: return 'fully remote roles'
    if re.search(r'on-?site|office', w): return 'on-site roles'
    return None


LEVEL_LABEL = {'Below target level': 'below-target-level roles', 'Target level': 'target-level (manager+) roles'}


def traits(j):
    """[(key, label)] — the same keys app.js builds."""
    out = []
    if j.get('level'): out.append(('level:' + j['level'], LEVEL_LABEL.get(j['level'], j['level'])))
    s = seniority_of(j)
    if s: out.append(('seniority:' + s, s))
    f = family_of(j)
    if f: out.append(('family:' + f, f + ' roles'))
    sec = sector_of(j)
    out.append(('sector:' + sec, sec + ' employers'))
    t = target_of(j)
    if t: out.append(('target:' + t, next(x['name'] for x in TAX['roleTargets'] if x['id'] == t) + ' roles'))
    m = mission_of(j)
    if m: out.append(('mission:' + m, m + ' employers'))
    w = work_of(j)
    if w: out.append(('work:' + w, w))
    p = pay_band_of(j)
    if p: out.append(('pay:' + p, 'roles with ' + p))
    return out


# Which traits a Not-a-fit reason points at.
REASON_PREFIXES = {'junior': ('level:', 'seniority:'), 'pay': ('pay:',), 'work': ('work:',), 'role': ('family:', 'seniority:', 'target:')}


def signal_weight(f):
    if f.get('status') == 'not-fit':
        return -1
    if f.get('applicationStage') not in (None, 'Not applied') or f.get('status') == 'applied':
        return 1.5
    return 1 if f.get('status') == 'fit' else 0


def main():
    export_path = sys.argv[1] if len(sys.argv) > 1 and os.path.exists(sys.argv[1]) else None
    exp = json.load(open(export_path)) if export_path else {'feedback': {}}
    fb = exp['feedback']

    hist = {}
    for h in reversed(subprocess.run(['git', 'log', '--format=%H', '--', 'feed.json'], capture_output=True, text=True).stdout.split()):
        try:
            d = json.loads(subprocess.run(['git', 'show', h + ':feed.json'], capture_output=True, text=True).stdout)
        except Exception:
            continue
        for j in d.get('jobs', []):
            hist[j['id']] = j
    if os.path.exists('archive.json'):
        for k, j in json.load(open('archive.json')).get('jobs', {}).items():
            hist.setdefault(k, j)
    for k, j in exp.get('jobs', {}).items():
        hist.setdefault(k, j)

    d = json.load(open('feed.json'))

    # Duplicates: the same employer + title listed twice (employer page and a job board, or a new id for a role
    # that was already listed/tracked). Keep one record under the oldest known id (so feedback and applications stay
    # attached), preferring the employer's own application page.
    by_key = collections.defaultdict(list)
    for k, h in hist.items():
        if h.get('company') and h.get('title'): by_key[ckey(h)].append(k)
    merged, drop_ids = [], set()
    for j in d['jobs']:
        known = [k for k in by_key.get(ckey(j), []) if k != j['id'] and same_place(hist[k], j) and (k in fb or hist[k].get('url'))]
        known = sorted(known, key=lambda k: (k not in fb,))  # an id with your feedback wins, else oldest first
        if known and j['id'] not in fb:
            old = known[0]; old_url = hist[old].get('url') or ''
            drop_ids.add(j['id']); merged.append((j['id'], old))
            if old_url and AGG.search(j.get('url') or '') and not AGG.search(old_url):
                j['url'], j['urlSource'] = old_url, 'employer'
            j['id'] = old
    seen = {}
    for j in d['jobs']:
        key = ckey(j)
        prior = seen.get(key)
        if prior is not None and same_place(prior, j):
            keep, lose = (j, prior) if (AGG.search(prior.get('url') or '') and not AGG.search(j.get('url') or '')) else (prior, j)
            if keep is j: seen[key] = j
            merged.append((lose['id'], keep['id'])); lose['_dup'] = True
        else:
            seen[key] = j
    d['jobs'] = [j for j in d['jobs'] if not j.get('_dup')]
    for k in drop_ids: hist.pop(k, None)
    for a, b in merged: print('merged duplicate:', a, '->', b)
    for j in d['jobs']:
        j['sector'] = sector_of(j)
        # Role target, mission, people leadership, pay and work arrangement (the daily routine supplies
        # roleTarget / mission / peopleLeadership / labels / benefits / orgSize from the posting; gaps are inferred).
        for key, val in (('roleTarget', target_of(j)), ('mission', mission_of(j))):
            if val: j[key] = val
            else: j.pop(key, None)
        j['peopleLeadership'] = leadership_of(j)
        j['payStatus'] = pay_status_of(j)
        j['arrangement'] = arrangement_of(j)
        j['flags'] = flags_of(j)
        j['priority'] = priority_of(j)
        hist[j['id']] = j

    # "New Postings": roles that were not in the previous run's feed. The previous run is the newest
    # "Refresh daily communications job feed" commit with a different generatedAt than this feed
    # (so re-running the script on an already-committed run still compares against the run before).
    prev_ids, prev_at = None, None
    runs = subprocess.run(['git', 'log', '--format=%H', '--grep=^Refresh daily communications job feed', '--', 'feed.json'],
                          capture_output=True, text=True).stdout.split()
    for h in runs:
        try:
            pd = json.loads(subprocess.run(['git', 'show', h + ':feed.json'], capture_output=True, text=True).stdout)
        except Exception:
            continue
        if pd.get('generatedAt') == d.get('generatedAt'):
            continue
        prev_ids, prev_at = {j['id'] for j in pd.get('jobs', [])}, pd.get('generatedAt')
        break
    for j in d['jobs']:
        j.pop('newSinceLastRun', None)
        if prev_ids is not None and j['id'] not in prev_ids:
            j['newSinceLastRun'] = True
    d['previousRunAt'] = prev_at

    # Rule-outs: the portal stores each one as a block entry (Undo deletes it).
    sector_slugs = {norm(s['name']).replace(' ', '-'): s['name'] for s in TAX['sectors']}
    blocked_employers, blocked_sectors = set(), set(TAX['excludedSectors'])
    for k, f in fb.items():
        if k.startswith('block:') and f.get('status') == 'not-fit':
            _, kind, value = k.split(':', 2)
            if kind == 'employer': blocked_employers.add(value.replace('-', ' '))
            elif kind == 'sector': blocked_sectors.add(sector_slugs.get(value, value))
            continue

    # Trait statistics.
    n, pos = collections.Counter(), collections.Counter()
    nf_keys, closed_out, keep = set(), set(), set()
    signals = total_pos = 0
    for k, f in fb.items():
        j = hist.get(k)
        w = signal_weight(f)
        if k.startswith('block:') or not j or not w:
            continue
        signals += 1
        key = ckey(j)
        if f.get('applicationStage') == 'Not moving ahead': closed_out.add(key)
        if w < 0:
            nf_keys.add(key)
            reasons = [r for r in (f.get('reasons') or []) if r in REASON_PREFIXES]
            junior = j.get('level') == 'Below target level'
            for t, _ in traits(j):
                if reasons:
                    if not any(t.startswith(p) for r in reasons for p in REASON_PREFIXES[r]): continue
                elif junior and t.startswith(('family:', 'sector:')):
                    continue
                n[t] += 1
        else:
            keep.add(k); total_pos += 1
            for t, _ in traits(j):
                n[t] += 1; pos[t] += 1
    base = total_pos / max(1, signals)

    def ratio(t):
        return (pos[t] + LEARN['smoothing'] * base) / (n[t] + LEARN['smoothing']) / base if base else 1

    # active[t] = log pick-rate ratio; negative = picked less often than usual.
    active = {t: round(math.log(ratio(t)), 3) for t in n
              if n[t] >= LEARN['minPicks'] and (ratio(t) <= LEARN['lowerRatio'] or ratio(t) >= LEARN['higherRatio'])}
    french = any(f.get('status') == 'not-fit' and re.search(r'french|bilingual', f.get('notes', ''), re.I) for f in fb.values())
    french_req = re.compile(r'french[^.;]{0,40}(required|mandatory|essential)|bilingual(ism)?[^.;]{0,40}(required|mandatory|essential)|(required|must)[^.;]{0,40}(french|bilingual)', re.I)

    # Exclusions. A role with its own Fit/Applied feedback always stays.
    removed = {'notfit': [], 'reposts': [], 'employer': [], 'sector': []}
    kept_jobs = []
    for j in d['jobs']:
        key = ckey(j)
        if j['id'] in keep: kept_jobs.append(j); continue
        if fb.get(j['id'], {}).get('status') == 'not-fit' or key in nf_keys: removed['notfit'].append(j['id']); continue
        if key in closed_out: removed['reposts'].append(j['id']); continue
        if norm(j['company']) in blocked_employers: removed['employer'].append(j['id']); continue
        if j['sector'] in blocked_sectors: removed['sector'].append(j['id']); continue
        kept_jobs.append(j)
    d['jobs'] = kept_jobs

    # Scores, ranking notes and tier changes.
    for j in d['jobs']:
        j.pop('feedbackAdjustment', None)
        if 'tierBeforeFeedbackDowngrade' in j:
            j['tier'] = j.pop('tierBeforeFeedbackDowngrade')
    lowered = []
    for j in d['jobs']:
        if j['id'] in fb:  # your own pick: no similarity note, keep the normal order
            j['_score'] = 0; continue
        tr = [(t, label) for t, label in traits(j) if t in active and not (t.startswith('seniority:') and sideways_ok(j))]
        weights = dict((t, active[t]) for t, _ in tr)
        if french and french_req.search(' '.join([j.get('gap', ''), j.get('summary', ''), j.get('title', '')])):
            tr.append(('french', 'roles requiring French fluency')); weights['french'] = math.log(LEARN['lowerRatio'])
        j['_score'] = sum(w * (LEARN['negativeWeight'] if w < 0 else 1) for w in weights.values())
        weak = [x for x in tr if weights[x[0]] < 0]
        strong = [x for x in tr if weights[x[0]] >= math.log(LEARN['tagHigherRatio'])]
        if weak:
            t, label = min(weak, key=lambda x: weights[x[0]])
            j['feedbackAdjustment'] = 'Often passed on: ' + label + (' (%d of %d picked)' % (pos[t], n[t]) if t in n else '')
        elif strong:
            t, label = max(strong, key=lambda x: weights[x[0]])
            j['feedbackAdjustment'] = 'Like your picks: ' + label + ' (%d of %d picked)' % (pos[t], n[t])
        for t, label in tr:
            if t.startswith('seniority:') and pos[t] == 0 and n[t] >= 5 and j['tier'] == 'Strongest fit':
                j['tierBeforeFeedbackDowngrade'] = j['tier']; j['tier'] = 'Good fit with stretch'; lowered.append(j['id'])
                j['feedbackAdjustment'] = j.get('feedbackAdjustment', 'Ranked lower') + '; fit tier lowered: you have not picked any ' + label
                break
    # Title seniority vs Jacob's highest title held (Manager): director-level titles are never
    # Strongest fit and rank after manager-level roles; Senior Manager ranks after Manager.
    def title_step(j):
        t = (j.get('title') or '').lower()
        # Role targets A and B are Director/Head titles by design (2026-11-11): treated as manager-level.
        if j.get('roleTarget') in ('A', 'B'): return 0
        if re.search(r'\b(director|head)\b', t): return 2
        if re.search(r'\bsenior manager\b|\bsr\.? manager\b', t): return 1
        return 0
    for j in d['jobs']:
        if title_step(j) == 2 and j['tier'] == 'Strongest fit':
            j['tierBeforeSeniorityDowngrade'] = j['tier']; j['tier'] = 'Good fit with stretch'
    tier_order = {'Strongest fit': 0, 'Good fit with stretch': 1, 'Domain expertise required': 2}
    d['jobs'].sort(key=lambda j: (tier_order[j['tier']], 1 if j.get('contract') else 0, 1 if 'on-site outside Hamilton' in j.get('flags', []) else 0, title_step(j), -j['priority'], -j['_score'], j['rank']))
    for i, j in enumerate(d['jobs'], 1):
        j['rank'] = i; j.pop('_score')

    # Public-safe summary: trait wording only, no employer names or note text.
    labels = {t: label for j in hist.values() if j.get('company') for t, label in traits(j)}
    adj = []
    if removed['notfit']: adj.append({'effect': 'Roles you marked Not a fit, and reposts of them, are excluded', 'basis': '%d removed this run' % len(removed['notfit'])})
    if removed['reposts']: adj.append({'effect': 'Reposts of roles where you were not moved ahead are excluded', 'basis': '%d removed this run' % len(removed['reposts'])})
    if blocked_employers: adj.append({'effect': 'Employers you ruled out are excluded', 'basis': '%d employers' % len(blocked_employers)})
    adj.append({'effect': 'Sectors excluded: ' + ', '.join(sorted(blocked_sectors)), 'basis': 'ruled out or never considered'})
    if french: adj.append({'effect': 'Roles requiring French fluency ranked lower', 'basis': 'from your notes'})
    for t, v in sorted(active.items(), key=lambda x: x[1]):
        label = labels.get(t, t)
        adj.append({'effect': label[0].upper() + label[1:] + (' ranked lower' if v < 0 else ' ranked higher'),
                    'basis': '%d of %d picks were Fit or Applied, vs %d%% overall' % (pos[t], n[t], round(base * 100))})
    # Categories Jacob keeps passing on move down (the traits above); say so in the feed and the portal.
    notices = []
    for t, v in sorted(active.items(), key=lambda x: x[1]):
        if v < 0 and t.startswith(('target:', 'mission:', 'family:')):
            notices.append('Moved down: %s. You passed on %d of the %d you rated.' % (labels.get(t, t), n[t] - pos[t], n[t]))
    d['excludedSectors'] = sorted(blocked_sectors)
    d['feedbackLearning'] = {'available': bool(export_path), 'exportedAt': exp.get('exportedAt'),
                             'signals': {'fit': sum(1 for f in fb.values() if f.get('status') == 'fit'),
                                         'notFit': sum(1 for k, f in fb.items() if f.get('status') == 'not-fit' and not k.startswith('block:')),
                                         'withNotes': sum(1 for f in fb.values() if f.get('notes'))},
                             'adjustments': adj}
    d['feedbackLearning']['notices'] = notices
    if not export_path:
        d['feedbackLearning']['note'] = 'No feedback export found — click Export feedback in the portal.'
    with open('feed.json', 'w') as f:
        json.dump(d, f, indent=2, ensure_ascii=False); f.write('\n')

    # Public archive of every posting the feed has listed, so old feedback ids keep their details.
    fields = ['company', 'title', 'cluster', 'tier', 'level', 'location', 'work', 'salary', 'contract', 'url', 'posted', 'roleTarget', 'mission']
    archive = {k: dict({f: j.get(f) for f in fields if j.get(f) is not None}, sector=sector_of(j))
               for k, j in sorted(hist.items()) if j.get('company') and j.get('title')}
    with open('archive.json', 'w') as f:
        json.dump({'about': 'Every posting the feed has listed (public posting details only).', 'jobs': archive}, f, indent=1, ensure_ascii=False); f.write('\n')

    print('excluded:', {k: len(v) for k, v in removed.items()}, '| tier lowered:', lowered)
    for a in adj: print(' -', a['effect'], '|', a['basis'])
    print('tags:', collections.Counter(j.get('feedbackAdjustment', 'none').split(':')[0] for j in d['jobs']), 'of', len(d['jobs']))
    for n_ in notices: print(' !', n_)
    for j in d['jobs']: print('  ', j['rank'], j['title'][:45], '|', j.get('feedbackAdjustment', ''))


main()
