"""
Read-only check of a deployed backend. Plain GET requests only: nothing is written, no login, no secret.

  python backend/ops/post_deploy_check.py https://<host> [--expect-env production|staging] [--timeout 90]

Prints one line per check (status codes only, never a response body) and ends with RESULT: PASS or RESULT: FAIL
(exit code 0 or 1). Paste the printout into RELEASE.md after a deploy.

  /healthz   answers 200 {"status": "ok"} and names the environment (so a wrong service is noticed)
  /readyz    answers 200 {"status": "ok"}: the database is reachable
  /api/v1/debug-logs/ answers 404: the old debug route is gone

The first request may take up to a minute on a sleeping free instance, hence the long default timeout.
"""
import argparse
import json
import sys
import urllib.error
import urllib.request


def get(url, timeout):
    """(status, parsed json or None). A network failure is status None."""
    request = urllib.request.Request(url, method='GET', headers={'User-Agent': 'hh-post-deploy-check'})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status, raw = response.status, response.read(4096)
    except urllib.error.HTTPError as exc:
        status, raw = exc.code, b''
        try:
            raw = exc.read(4096)
        except Exception:  # noqa: BLE001
            pass
    except Exception:  # noqa: BLE001  (DNS failure, refused, timeout)
        return None, None
    try:
        return status, json.loads(raw.decode('utf-8'))
    except ValueError:
        return status, None


def run_checks(base_url, expect_env='production', timeout=90):
    base = base_url.rstrip('/')
    results = []

    status, body = get(base + '/healthz', timeout)
    body = body if isinstance(body, dict) else {}
    results.append(('/healthz answers ok', status == 200 and body.get('status') == 'ok', f'HTTP {status}'))
    results.append((f'/healthz says env={expect_env}', status == 200 and body.get('env') == expect_env,
                    f"env={body.get('env')!r}" if status == 200 else f'HTTP {status}'))

    status, body = get(base + '/readyz', timeout)
    body = body if isinstance(body, dict) else {}
    results.append(('/readyz answers ok', status == 200 and body.get('status') == 'ok', f'HTTP {status}'))

    status, _ = get(base + '/api/v1/debug-logs/', timeout)
    results.append(('debug route is gone (404)', status == 404, f'HTTP {status}'))
    return results


def main(argv):
    parser = argparse.ArgumentParser(prog=argv[0], description='Read-only post-deploy check.')
    parser.add_argument('base_url', help='https://<host> of the deployed backend')
    parser.add_argument('--expect-env', default='production', choices=['production', 'staging'])
    parser.add_argument('--timeout', type=float, default=90)
    args = parser.parse_args(argv[1:])
    if not args.base_url.startswith(('http://', 'https://')):
        print('The address must start with http:// or https://')
        return 2

    results = run_checks(args.base_url, args.expect_env, args.timeout)
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}  ({detail})")
    passed = all(ok for _, ok, _ in results)
    print('RESULT: PASS' if passed else 'RESULT: FAIL')
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
