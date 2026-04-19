import yaml, subprocess, os, glob, urllib.request
from datetime import datetime

INDEXNOW_WORKER = "https://indexnow-submit.hugh79757.workers.dev/?site="

def submit_indexnow(domain):
    try:
        urllib.request.urlopen(INDEXNOW_WORKER + domain, timeout=10)
        print("  [IndexNow] " + domain + " 제출완료")
    except Exception as e:
        print("  [IndexNow] " + domain + " 실패: " + str(e))

os.chdir('/Users/twinssn/Projects/5000')

with open('config/blogs.yaml') as f:
    config = yaml.safe_load(f)

deploy_cfg = config.get('deploy', {})
branch = deploy_cfg.get('branch', 'main')
commit_dirty = deploy_cfg.get('commit_dirty', True)

blogs = []
for fpath in sorted(glob.glob('config/blogs.d/*.yaml')):
    with open(fpath) as f:
        data = yaml.safe_load(f)
    if isinstance(data, dict) and 'blogs' in data:
        blogs.extend(data['blogs'])

ALWAYS_DEPLOY_PIPELINES = {'curation'}

TIMESTAMP = datetime.now().strftime('%Y-%m-%d %H:%M')
SUCCESS = 0
SKIP = 0
FAIL = 0

print('===== Wrangler 배치 배포 시작: ' + TIMESTAMP + ' =====')
print('  대상 블로그: ' + str(len(blogs)) + '개')
print('')

for blog in blogs:
    if blog.get('status') != 'active':
        continue
    site_path = blog.get('site_path', '')
    cf_project = blog.get('cf_project', '')
    name = blog['id']
    pipeline = blog.get('pipeline', '')

    if not site_path or not os.path.isdir(site_path):
        print('--- ' + name + ' [SKIP] 디렉토리 없음 ---')
        SKIP += 1
        continue

    os.chdir(site_path)
    always_deploy = pipeline in ALWAYS_DEPLOY_PIPELINES

    if not always_deploy:
        result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
        changes = result.stdout.strip()
        if not changes:
            print('--- ' + name + ' [SKIP] 변경없음 ---')
            SKIP += 1
            continue
        file_count = len(changes.split(chr(10)))
        print('--- ' + name + ' (' + str(file_count) + '건) ---')
        subprocess.run(['git', 'add', '-A'], capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'publish: ' + TIMESTAMP + ' (' + str(file_count) + '건)', '--quiet'], capture_output=True)
    else:
        print('--- ' + name + ' [CUAP] ---')

    print('  Hugo 빌드...')
    r = subprocess.run(['hugo', '--gc', '--minify', '--quiet'], capture_output=True, text=True)
    if r.returncode != 0:
        print('  [FAIL] 빌드 실패: ' + r.stderr[:200])
        FAIL += 1
        continue

    print('  Wrangler 배포...')
    cmd = ['wrangler', 'pages', 'deploy', './public', '--project-name=' + cf_project, '--branch=' + branch]
    if commit_dirty:
        cmd.append('--commit-dirty=true')
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print('  [FAIL] 배포 실패: ' + r.stderr[:200])
        FAIL += 1
    else:
        output_lines = r.stdout.strip().split(chr(10))
        print('  ' + (output_lines[-1] if output_lines else 'OK'))
        print("  [OK]")
        domain = blog.get("domain", "")
        if domain:
            submit_indexnow(domain)
        SUCCESS += 1

    subprocess.run(['rm', '-rf', './public'], capture_output=True)
    print('')

print('===== 결과 =====')
print('  성공: ' + str(SUCCESS))
print('  스킵: ' + str(SKIP))
print('  실패: ' + str(FAIL))
