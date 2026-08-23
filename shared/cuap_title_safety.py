from shared.title_quality import normalize_title

def normalize_cuap_title(title):
    value = normalize_title(title or '', language='ko')
    for token in ('laptop-hugo', 'bike-hugo', 'cleaner-hugo', 'site:', 'blog:', 'project:'):
        value = value.replace(token, ' ')
    return value.strip(' -:,.?')

def cuap_title_issues(title, keyword, products, recent_titles=()):
    value = normalize_cuap_title(title)
    issues = []
    if not value: issues.append('empty_title')
    if len(value) < 12: issues.append('too_short')
    if len(value) > 60: issues.append('too_long')
    low = (title or '').lower()
    if any(token in low for token in ('-hugo', 'site:', 'blog:', 'project:')): issues.append('internal_identifier')
    if any(ord(ch) > 127 and not (0xAC00 <= ord(ch) <= 0xD7A3) for ch in (title or '') if ch.isalpha()): issues.append('foreign_script')
    if keyword and not any(token in value for token in keyword.split() if token != '\ucd94\ucc9c'): issues.append('missing_topic')
    if any(value == normalize_cuap_title(old) for old in recent_titles if old): issues.append('repeated_title')
    return issues
