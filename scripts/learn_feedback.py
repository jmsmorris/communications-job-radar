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
    if j.get('sector'):
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
    w = work_of(j)
    if w: out.append(('work:' + w, w))
    p = pay_band_of(j)
    if p: out.append(('pay:' + p, 'roles with ' + p))
    return out


# Which traits a Not-a-fit reason points at.
REASON_PREFIXES = {'junior': ('level:', 'seniority:'), 'pay': ('pay:',), 'work': ('work:',), 'role': ('family:', 'seniority:')}


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
    for j in d['jobs']:
        j['sector'] = sector_of(j)
        hist[j['id']] = j

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
        key = (norm(j['company']), norm(j['title']))
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
        key = (norm(j['company']), norm(j['title']))
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
        tr = [(t, label) for t, label in traits(j) if t in active]
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
    tier_order = {'Strongest fit': 0, 'Good fit with stretch': 1, 'Domain expertise required': 2}
    d['jobs'].sort(key=lambda j: (tier_order[j['tier']], 1 if j.get('contract') else 0, -j['_score'], j['rank']))
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
    d['excludedSectors'] = sorted(blocked_sectors)
    d['feedbackLearning'] = {'available': bool(export_path), 'exportedAt': exp.get('exportedAt'),
                             'signals': {'fit': sum(1 for f in fb.values() if f.get('status') == 'fit'),
                                         'notFit': sum(1 for k, f in fb.items() if f.get('status') == 'not-fit' and not k.startswith('block:')),
                                         'withNotes': sum(1 for f in fb.values() if f.get('notes'))},
                             'adjustments': adj}
    if not export_path:
        d['feedbackLearning']['note'] = 'No feedback export found — click Export feedback in the portal.'
    with open('feed.json', 'w') as f:
        json.dump(d, f, indent=2, ensure_ascii=False); f.write('\n')

    # Public archive of every posting the feed has listed, so old feedback ids keep their details.
    fields = ['company', 'title', 'cluster', 'tier', 'level', 'location', 'work', 'salary', 'contract', 'url', 'posted']
    archive = {k: dict({f: j.get(f) for f in fields if j.get(f) is not None}, sector=sector_of(j))
               for k, j in sorted(hist.items()) if j.get('company') and j.get('title')}
    with open('archive.json', 'w') as f:
        json.dump({'about': 'Every posting the feed has listed (public posting details only).', 'jobs': archive}, f, indent=1, ensure_ascii=False); f.write('\n')

    print('excluded:', {k: len(v) for k, v in removed.items()}, '| tier lowered:', lowered)
    for a in adj: print(' -', a['effect'], '|', a['basis'])
    print('tags:', collections.Counter(j.get('feedbackAdjustment', 'none').split(':')[0] for j in d['jobs']), 'of', len(d['jobs']))
    for j in d['jobs']: print('  ', j['rank'], j['title'][:45], '|', j.get('feedbackAdjustment', ''))


main()
