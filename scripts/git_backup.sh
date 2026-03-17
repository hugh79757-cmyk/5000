#!/bin/bash
cd /Users/twinssn/Projects/5000
.venv/bin/python3 -c "
import yaml, subprocess, os
from datetime import datetime

with open('config/blogs.yaml') as f:
    config = yaml.safe_load(f)

blogs = config.get('blogs', [])
TIMESTAMP = datetime.now().strftime('%Y-%m-%d %H:%M')
SUCCESS = 0
FAIL = 0

print('===== Git Backup: ' + TIMESTAMP + ' =====')

for blog in blogs:
    if blog.get('status') != 'active':
        continue
    site_path = blog.get('site_path', '')
    name = blog['id']

    if not site_path or not os.path.isdir(site_path):
        continue

    os.chdir(site_path)
    try:
        subprocess.run(['git', 'add', '-A'], capture_output=True, timeout=30)
        r = subprocess.run(['git', 'commit', '-m', 'backup: ' + TIMESTAMP, '--quiet'], capture_output=True, text=True, timeout=30)
        if 'nothing to commit' in r.stdout:
            continue
        r = subprocess.run(['git', 'push', 'origin', 'main', '--quiet'], capture_output=True, text=True, timeout=60)
        if r.returncode == 0:
            print('  [OK] ' + name)
            SUCCESS += 1
        else:
            subprocess.run(['git', 'pull', '--rebase', 'origin', 'main', '--quiet'], capture_output=True, timeout=60)
            subprocess.run(['git', 'push', 'origin', 'main', '--quiet'], capture_output=True, timeout=60)
            print('  [OK] ' + name + ' (after pull)')
            SUCCESS += 1
    except Exception as e:
        print('  [FAIL] ' + name + ': ' + str(e))
        FAIL += 1

print('===== 완료: 성공 ' + str(SUCCESS) + ' / 실패 ' + str(FAIL) + ' =====')
"
