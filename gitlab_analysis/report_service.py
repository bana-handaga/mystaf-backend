"""
Report service: extract meaningful insights from commit messages and activities.
Uses simple NLP (word frequency, keyword matching) — no heavy ML library needed.
"""
import re
from collections import Counter
from datetime import timedelta
from django.utils import timezone
from .models import ProjectCommit, GitLabActivity, GitLabProject
from accounts.models import StafUser

# ── Stopwords (Indonesian + English + git noise) ────────────────────────────
STOPWORDS = {
    # Indonesian
    'dan', 'yang', 'di', 'ke', 'dari', 'ini', 'itu', 'untuk', 'dengan',
    'pada', 'ada', 'tidak', 'dalam', 'atau', 'juga', 'sudah', 'belum',
    'akan', 'bisa', 'agar', 'apa', 'saat', 'lagi', 'jika', 'maka',
    'oleh', 'serta', 'karena', 'seperti', 'lebih', 'hanya', 'masih',
    'setelah', 'tetapi', 'namun', 'ketika', 'semua', 'dapat', 'baru',
    # English
    'the', 'and', 'for', 'with', 'from', 'into', 'this', 'that', 'some',
    'not', 'are', 'was', 'were', 'has', 'have', 'had', 'use', 'used',
    'add', 'update', 'fix', 'remove', 'change', 'changes', 'initial',
    'added', 'updated', 'fixed', 'removed', 'changed', 'create', 'created',
    'set', 'get', 'run', 'make', 'made', 'new', 'old', 'now', 'also',
    'all', 'only', 'can', 'will', 'when', 'then', 'more', 'via', 'to',
    'in', 'on', 'at', 'by', 'of', 'is', 'it', 'be', 'as', 'an', 'a',
    # Git/commit noise
    'merge', 'branch', 'commit', 'rebase', 'pull', 'push', 'request',
    'wip', 'todo', 'fixme', 'misc', 'minor', 'major', 'temp', 'test',
    'tests', 'testing', 'refactor', 'cleanup', 'clean',
}

# ── Tech topic keyword groups ────────────────────────────────────────────────
TOPIC_KEYWORDS = {
    'API / Backend':    ['api', 'endpoint', 'rest', 'graphql', 'service', 'controller',
                         'view', 'model', 'serializer', 'middleware', 'backend', 'server',
                         'django', 'flask', 'laravel', 'express', 'fastapi', 'spring'],
    'Frontend / UI':    ['frontend', 'ui', 'ux', 'component', 'template', 'style', 'css',
                         'scss', 'html', 'angular', 'react', 'vue', 'layout', 'design',
                         'responsive', 'mobile', 'page', 'form', 'button', 'modal', 'icon'],
    'Database':         ['database', 'db', 'query', 'migration', 'schema', 'table', 'index',
                         'sql', 'mysql', 'postgres', 'mongodb', 'redis', 'orm', 'seed',
                         'fixture', 'backup', 'data'],
    'Auth / Keamanan':  ['auth', 'login', 'logout', 'token', 'jwt', 'oauth', 'password',
                         'permission', 'role', 'guard', 'security', 'csrf', 'cors',
                         'encrypt', 'hash', 'user', 'session'],
    'Testing / QA':     ['test', 'unit', 'integration', 'e2e', 'spec', 'assert', 'mock',
                         'coverage', 'selenium', 'cypress', 'jest', 'pytest', 'qa'],
    'DevOps / CI/CD':   ['docker', 'ci', 'cd', 'pipeline', 'deploy', 'deployment',
                         'kubernetes', 'nginx', 'apache', 'github', 'gitlab', 'action',
                         'workflow', 'env', 'config', 'setup', 'build', 'release'],
    'Performa':         ['performance', 'optimize', 'cache', 'speed', 'load', 'memory',
                         'async', 'concurrency', 'queue', 'lazy', 'paginate', 'index'],
    'Fitur Bisnis':     ['report', 'laporan', 'dashboard', 'chart', 'graph', 'export',
                         'import', 'pdf', 'excel', 'email', 'notif', 'notification',
                         'payment', 'invoice', 'schedule', 'cron', 'webhook'],
}

# ── Commit category labels (in Indonesian) ──────────────────────────────────
CATEGORY_LABELS = {
    'fix':      'Perbaikan Bug',
    'feature':  'Pengembangan Fitur Baru',
    'refactor': 'Refaktorisasi / Perbaikan Kode',
    'docs':     'Dokumentasi',
    'config':   'Konfigurasi / Setup',
    'test':     'Pengujian',
    'remove':   'Penghapusan Kode',
    'merge':    'Merge / Integrasi',
    'other':    'Aktivitas Lainnya',
}

COMMIT_CATEGORIES = {
    'fix':      ['fix', 'bug', 'error', 'resolve', 'patch', 'hotfix', 'repair', 'revert'],
    'feature':  ['add', 'feat', 'feature', 'implement', 'new', 'create', 'build', 'init'],
    'refactor': ['refactor', 'clean', 'improve', 'optimize', 'restructure', 'enhance', 'update', 'upgrade'],
    'docs':     ['doc', 'readme', 'comment', 'docs', 'documentation', 'changelog'],
    'config':   ['config', 'setup', 'env', 'setting', 'deploy', 'ci', 'cd', 'workflow', 'docker'],
    'test':     ['test', 'spec', 'unit', 'integration', 'testing', 'coverage'],
    'remove':   ['remove', 'delete', 'drop', 'cleanup', 'clean up', 'deprecated'],
    'merge':    ['merge', 'pull request', 'rebase', 'sync'],
}


def classify_commit(message: str) -> str:
    msg = (message or '').lower()
    for cat, keywords in COMMIT_CATEGORIES.items():
        for kw in keywords:
            if kw in msg:
                return cat
    return 'other'


def tokenize(text: str) -> list[str]:
    """Lowercase, remove special chars, split into words >= 3 chars."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    return [w for w in text.split() if len(w) >= 3 and w not in STOPWORDS]


def extract_keywords(messages: list[str], top_n: int = 10) -> list[dict]:
    """Return top-N keywords with frequency from a list of strings."""
    all_tokens = []
    for msg in messages:
        all_tokens.extend(tokenize(msg))
    counter = Counter(all_tokens)
    return [{'word': w, 'count': c} for w, c in counter.most_common(top_n)]


def detect_topics(messages: list[str]) -> list[dict]:
    """Detect which tech topics appear in the messages, sorted by hit count."""
    combined = ' '.join(messages).lower()
    results = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        hits = sum(1 for kw in keywords if re.search(r'\b' + re.escape(kw) + r'\b', combined))
        if hits > 0:
            results.append({'topic': topic, 'hits': hits})
    return sorted(results, key=lambda x: x['hits'], reverse=True)


def generate_narrative(staf_name: str, days: int, total_commits: int,
                       dominant_cat: str, topics: list[dict],
                       keywords: list[dict], projects: list[str],
                       total_push: int, total_mr: int, total_issues: int) -> str:
    """Generate a human-readable Indonesian narrative paragraph for one staff member."""
    if total_commits == 0 and total_push == 0:
        return f"{staf_name} tidak memiliki aktivitas yang tercatat dalam {days} hari terakhir."

    # Opening
    parts = []
    parts.append(
        f"Dalam {days} hari terakhir, {staf_name} mencatat {total_commits} commit"
        + (f" di {len(projects)} proyek" if projects else "") + "."
    )

    # Dominant activity
    cat_label = CATEGORY_LABELS.get(dominant_cat, 'Aktivitas Lainnya')
    parts.append(f"Aktivitas yang paling dominan adalah {cat_label.lower()}.")

    # Topics
    if topics:
        top_topics = [t['topic'] for t in topics[:3]]
        if len(top_topics) == 1:
            parts.append(f"Bidang teknis yang dikerjakan mencakup {top_topics[0]}.")
        else:
            parts.append(
                f"Bidang teknis yang dikerjakan mencakup {', '.join(top_topics[:-1])} dan {top_topics[-1]}."
            )

    # Keywords
    if keywords:
        kw_words = [k['word'] for k in keywords[:5]]
        parts.append(
            f"Kata kunci yang sering muncul pada pesan commit antara lain: {', '.join(kw_words)}."
        )

    # Push events, MRs, issues
    extras = []
    if total_push:
        extras.append(f"{total_push} push event")
    if total_mr:
        extras.append(f"{total_mr} merge request")
    if total_issues:
        extras.append(f"{total_issues} issue")
    if extras:
        parts.append(f"Selain commit, terdapat {', '.join(extras)} pada periode ini.")

    return ' '.join(parts)


def build_staff_report(staf: StafUser, days: int) -> dict:
    """Build a single staff report dict."""
    since = timezone.now() - timedelta(days=days)

    commits = list(ProjectCommit.objects.filter(
        staf=staf, committed_at__gte=since
    ).select_related('project').order_by('-committed_at'))

    messages = [c.message for c in commits if c.message]

    # Category breakdown
    all_cats = list(COMMIT_CATEGORIES.keys()) + ['other']
    cat_counts = {c: 0 for c in all_cats}
    for c in commits:
        cat_counts[classify_commit(c.message)] += 1
    dominant_cat = max(cat_counts, key=lambda c: cat_counts[c]) if commits else 'other'

    # Projects involved
    projects_set = list(dict.fromkeys(
        c.project.name for c in commits if c.project
    ))

    # Keywords & topics
    keywords = extract_keywords(messages, top_n=10)
    topics = detect_topics(messages)

    # Activity stats (from GitLabActivity)
    activities = GitLabActivity.objects.filter(staf=staf, activity_date__gte=since)
    total_push = activities.filter(activity_type='push').count()
    total_mr = activities.filter(activity_type='merge_request').count()
    total_issues = activities.filter(activity_type='issue').count()

    narrative = generate_narrative(
        staf_name=staf.get_full_name() or staf.username,
        days=days,
        total_commits=len(commits),
        dominant_cat=dominant_cat,
        topics=topics,
        keywords=keywords,
        projects=projects_set,
        total_push=total_push,
        total_mr=total_mr,
        total_issues=total_issues,
    )

    return {
        'staf_id': staf.id,
        'staf_name': staf.get_full_name() or staf.username,
        'staf_username': staf.username,
        'gitlab_username': staf.gitlab_username or '',
        'total_commits': len(commits),
        'total_push': total_push,
        'total_mr': total_mr,
        'total_issues': total_issues,
        'total_activity': len(commits) + total_push + total_mr + total_issues,
        'category_breakdown': [
            {'category': k, 'label': CATEGORY_LABELS.get(k, k), 'count': v}
            for k, v in cat_counts.items() if v > 0
        ],
        'dominant_category': dominant_cat,
        'dominant_category_label': CATEGORY_LABELS.get(dominant_cat, dominant_cat),
        'keywords': keywords,
        'topics': topics,
        'projects': projects_set,
        'narrative': narrative,
    }


def build_team_report(days: int) -> dict:
    """Build full team management report."""
    since = timezone.now() - timedelta(days=days)
    staff_list = StafUser.objects.filter(role='programmer', is_active=True).order_by('first_name')

    staff_reports = []
    for staf in staff_list:
        report = build_staff_report(staf, days)
        staff_reports.append(report)

    # Sort: most active first
    staff_reports.sort(key=lambda r: r['total_activity'], reverse=True)

    total_commits = sum(r['total_commits'] for r in staff_reports)
    active_staff = [r for r in staff_reports if r['total_activity'] > 0]

    # Team-level topic aggregation
    all_topics: dict[str, int] = {}
    for r in staff_reports:
        for t in r['topics']:
            all_topics[t['topic']] = all_topics.get(t['topic'], 0) + t['hits']
    team_topics = sorted(
        [{'topic': k, 'hits': v} for k, v in all_topics.items()],
        key=lambda x: x['hits'], reverse=True
    )

    # Team-level keyword aggregation
    all_messages = list(
        ProjectCommit.objects.filter(committed_at__gte=since).values_list('message', flat=True)
    )
    team_keywords = extract_keywords(all_messages, top_n=15)

    return {
        'days': days,
        'total_staff': len(staff_list),
        'active_staff': len(active_staff),
        'total_commits': total_commits,
        'team_topics': team_topics,
        'team_keywords': team_keywords,
        'staff_reports': staff_reports,
    }
