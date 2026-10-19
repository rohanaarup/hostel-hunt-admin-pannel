"""
Pure helpers for the load test: the test data's names and ids, and the pass/fail rules.
No Locust import, so backend/apps/core/test_f7.py can test them (and check them against seed_loadtest).
"""
import uuid

# Same value as apps/core/sample_data.SEED_NAMESPACE; a test keeps the two equal.
SEED_NAMESPACE = uuid.UUID('6f1c0f6e-6f55-4b53-9a3e-1b0a5c3d7e11')
EMAIL_DOMAIN = 'example.test'

THROTTLED = '429 throttled'


def student_email(n):
    return f'load{n:04d}@{EMAIL_DOMAIN}'


def payment_id_for(n):
    """The id seed_loadtest gives student n's settled payment (the student can poll its status)."""
    return str(uuid.uuid5(SEED_NAMESPACE, f'payment:load{student_email(n)}'))


def group_of(name):
    """'public: list' -> 'public'."""
    return name.split(':', 1)[0].strip()


def classify(error_text):
    if error_text == THROTTLED:
        return 'throttled'
    if error_text.startswith('HTTP 5'):
        return 'server'
    return 'other'


def evaluate(rows, thresholds):
    """
    rows: [{name, requests, p95, failures: {error_text: count}}]. Returns (passed, lines).
    The lines say what was checked, so the run's result can be pasted as it is.
    """
    lines, passed = [], True
    total = sum(r['requests'] for r in rows)
    if total < thresholds.get('min_requests', 0):
        return False, [f'FAIL  only {total} requests were made (need at least {thresholds["min_requests"]}); the run proves nothing']

    counts = {'throttled': 0, 'server': 0, 'other': 0}
    for row in rows:
        for text, n in row['failures'].items():
            counts[classify(text)] += n

    for key, label in (('other', 'errors'), ('server', '5xx'), ('throttled', 'throttled (429)')):
        limit = thresholds[{'other': 'max_error_ratio', 'server': 'max_5xx_ratio', 'throttled': 'max_throttled_ratio'}[key]]
        ratio = counts[key] / total if total else 0
        ok = ratio <= limit
        passed &= ok
        lines.append(f'{"PASS" if ok else "FAIL"}  {label}: {counts[key]} of {total} ({ratio:.2%}), limit {limit:.2%}')

    limits = thresholds['p95_ms']
    for row in sorted(rows, key=lambda r: r['name']):
        limit = limits.get(group_of(row['name']))
        if limit is None or row['requests'] == 0:
            continue
        ok = row['p95'] <= limit
        passed &= ok
        lines.append(f'{"PASS" if ok else "FAIL"}  p95 {row["name"]}: {row["p95"]:.0f} ms, limit {limit} ms ({row["requests"]} requests)')
    return passed, lines
