#!/usr/bin/env python3
"""직접 표준 검사: fleet 모든 블로그에 대해 R04/R06/R08/R12 실행."""
import sys, yaml
from pathlib import Path
sys.path.insert(0, '/Users/twinssn/Projects/5000')

from ops_dashboard.checks.standard import (
    _check_r04, _check_r06, _check_r08, _check_r12,
    _check_thumbnail_01, _check_r2_01,
)

blogs = []
for yml in sorted((Path('/Users/twinssn/Projects/5000') / 'config' / 'blogs.d').glob('*.yaml')):
    try:
        data = yaml.safe_load(yml.read_text())
    except Exception:
        continue
    for b in data.get('blogs', []):
        if b.get('site_path'):
            blogs.append((b['id'], b['site_path'], b.get('domain', '')))

print(f"Fleet 블로그 {len(blogs)}개에 대한 직접 표준 검사")
print("=" * 60)

fail_summary = {}
pass_count = 0
for bid, sp, domain in blogs:
    site = Path(sp)
    if not site.is_dir():
        continue

    r04 = _check_r04(site)
    r06 = _check_r06(site)
    r08 = _check_r08(site)
    r12 = _check_r12(site)

    fails = []
    if not r04[0]:
        fails.append("R04:" + r04[1][:60])
    if not r06[0]:
        fails.append("R06:" + r06[1][:60])
    if not r08[0]:
        fails.append("R08:" + r08[1][:60])
    if not r12[0]:
        fails.append("R12:" + r12[1][:60])

    if fails:
        fail_summary[bid] = fails
        print("FAIL %s: %s" % (bid, "; ".join(fails)))
    else:
        pass_count += 1

print()
print("통과: %d개, 위반: %d개" % (pass_count, len(fail_summary)))
print()
for bid, fails in fail_summary.items():
    print("  %s: %s" % (bid, fails))
