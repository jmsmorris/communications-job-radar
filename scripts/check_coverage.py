#!/usr/bin/env python3
"""Search-coverage log and gate for the daily job-feed routine.

The routine records every search action while it works, then runs `check` as the first part of
its publish command; `check` exits non-zero until the minimums in the routine prompt are met.

  python3 scripts/check_coverage.py add board  <employer>  <ok|empty|blocked|search>
  python3 scripts/check_coverage.py add jobboard <name>    <ok|search|blocked>
  python3 scripts/check_coverage.py add search <query>     <ok> [--ats]
  python3 scripts/check_coverage.py add lead   <name>      <pending|opened|screened>
  python3 scripts/check_coverage.py check                  # prints totals, exit 1 if short
  python3 scripts/check_coverage.py check --waive "specific reason a minimum is impossible"

Log: /tmp/cov.log (one JSON object per line). A board counts when its listing was read
(ok/empty) or its postings were found by a site search instead (search); a bare "blocked"
does not count. A job board counts when its listing was read or searched. A lead counts once
its last entry is opened or screened.
"""
import json, os, sys

LOG = os.environ.get('COV_LOG', '/tmp/cov.log')
MIN_BOARDS, MIN_SEARCHES, MIN_ATS = 20, 15, 6
JOBBOARDS = ['sportswork', 'sirc', 'charityvillage', 'jobbank', 'ops', 'toronto', 'hamilton', 'gcjobs']


def read():
    rows = []
    if os.path.exists(LOG):
        for line in open(LOG):
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    pass
    return rows


def add(argv):
    if len(argv) < 3:
        sys.exit(__doc__)
    typ, name, result = argv[0], argv[1], argv[2]
    row = {'type': typ, 'name': name, 'result': result, 'ats': '--ats' in argv}
    with open(LOG, 'a') as f:
        f.write(json.dumps(row) + '\n')


def check(argv):
    rows = read()
    boards = {r['name'] for r in rows if r['type'] == 'board' and r['result'] in ('ok', 'empty', 'search')}
    blocked = {r['name'] for r in rows if r['type'] == 'board' and r['result'] == 'blocked'} - boards
    jb = {r['name'].lower() for r in rows if r['type'] == 'jobboard' and r['result'] in ('ok', 'search')}
    searches = [r for r in rows if r['type'] == 'search']
    ats = [r for r in searches if r.get('ats')]
    leads = {}
    for r in rows:
        if r['type'] == 'lead':
            leads[r['name']] = r['result']
    open_leads = sorted(n for n, s in leads.items() if s not in ('opened', 'screened'))
    missing_jb = [b for b in JOBBOARDS if b not in jb]

    problems = []
    if len(boards) < MIN_BOARDS:
        problems.append('employer boards read: %d of %d' % (len(boards), MIN_BOARDS))
    if missing_jb:
        problems.append('job boards not yet read or searched: ' + ', '.join(missing_jb))
    if len(searches) < MIN_SEARCHES:
        problems.append('web searches: %d of %d' % (len(searches), MIN_SEARCHES))
    if len(ats) < MIN_ATS:
        problems.append('ATS-restricted searches: %d of %d' % (len(ats), MIN_ATS))
    if open_leads:
        problems.append('leads not yet opened or screened: ' + ', '.join(open_leads))

    print('COVERAGE employer boards read %d (+%d blocked) | job boards %d of %d | searches %d (ATS %d) | leads opened/screened %d of %d'
          % (len(boards), len(blocked), len(jb & set(JOBBOARDS)), len(JOBBOARDS), len(searches), len(ats),
             len(leads) - len(open_leads), len(leads)))
    if '--waive' in argv:
        i = argv.index('--waive')
        reason = ' '.join(argv[i + 1:]).strip()
        if not reason:
            sys.exit('--waive needs the specific reason a minimum is impossible')
        print('WAIVED (quote this in the run summary):', reason)
        for p in problems:
            print(' short:', p)
        return 0
    if problems:
        print('NOT MET - keep searching, do not publish:')
        for p in problems:
            print(' -', p)
        return 1
    print('MET')
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if sys.argv[1] == 'add':
        add(sys.argv[2:])
    elif sys.argv[1] == 'check':
        sys.exit(check(sys.argv[2:]))
    else:
        sys.exit(__doc__)
