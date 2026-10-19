"""
Hostel Hunt load test (Locust). STAGING ONLY: it refuses any other host, see guard.py and LOADTEST.md.

  StudentUser      the normal mix (browse, detail, search, logged-in reads, a few writes). Run this one.
  LoginStormUser   everyone logging in at once (password hashing is the heaviest CPU work we do).
  PaymentCreateUser  creates online bookings and Razorpay TEST orders. Needs Razorpay TEST keys on staging. Few users only.

Run only the class you mean: `locust -f locustfile.py StudentUser ...` (commands are in LOADTEST.md).
Needs LOADTEST_PASSWORD (the password seed_loadtest used) in the environment. It is never printed.
"""
import itertools
import json
import os
import random
import sys
from pathlib import Path

import requests
from locust import HttpUser, between, events, task

sys.path.insert(0, str(Path(__file__).parent))
import guard  # noqa: E402
import rules  # noqa: E402

API = '/api/v1'
STUDENTS = int(os.environ.get('HH_STUDENTS', '300'))
PAYMENT_STUDENTS = int(os.environ.get('HH_PAYMENT_STUDENTS', '50'))
THINK = (float(os.environ.get('HH_THINK_MIN', '2')), float(os.environ.get('HH_THINK_MAX', '8')))
THRESHOLDS_FILE = Path(os.environ.get('HH_THRESHOLDS', Path(__file__).parent / 'thresholds.json'))
SEARCH_WORDS = ['seed', 'load', 'gachibowli', 'kothrud', 'pune', 'stay']
CITIES = ['Hyderabad', 'Pune', 'Bengaluru']
_numbers = itertools.count()


@events.init.add_listener
def _refuse_wrong_target(environment, **_kwargs):
    """Runs before any user starts. Exits the whole process when the target is not staging."""
    host = environment.host or ''
    reported = None
    if rules_host_needs_health(host):
        try:
            reported = requests.get(host.rstrip('/') + '/healthz', timeout=90).json().get('env')
        except Exception:  # an old build, a sleeping server that never woke, bad JSON: all "cannot tell"
            reported = None
    allowed, message = guard.check_target(host, os.environ, reported)
    if message:
        print(message, file=sys.stderr, flush=True)
    if not allowed:
        sys.exit(2)
    if not os.environ.get('LOADTEST_PASSWORD'):
        print('Set LOADTEST_PASSWORD (the password seed_loadtest used for the test students).', file=sys.stderr, flush=True)
        sys.exit(2)


def rules_host_needs_health(host):
    name = guard.host_of(host)
    return bool(name) and name not in guard.LOCAL_HOSTS and name not in guard.PRODUCTION_HOSTS and not guard.production_allowed(os.environ)


class _Student(HttpUser):
    abstract = True
    access = None
    refresh = None

    def on_start(self):
        self.number = next(_numbers) % STUDENTS + 1
        self.login()

    # ── plumbing ────────────────────────────────────────────────────────────

    def call(self, method, path, name, expect=(200,), auth=False, retry=True, **kwargs):
        """One request, counted under `name`. 429 is its own failure text so reports can set it apart."""
        headers = {'Authorization': f'Bearer {self.access}'} if auth and self.access else {}
        with self.client.request(method, API + path, name=name, headers=headers, catch_response=True, **kwargs) as response:
            if response.status_code in expect:
                response.success()
            elif response.status_code == 429:
                response.failure(rules.THROTTLED)
            else:
                response.failure(f'HTTP {response.status_code}')
            status = response.status_code
        if status == 401 and auth and retry and self.refresh_tokens():
            return self.call(method, path, name, expect, auth, False, **kwargs)
        return response

    def login(self):
        response = self.call(
            'POST', '/auth/login/', 'login: password',
            json={'identifier': rules.student_email(self.number), 'identifier_type': 'email', 'password': os.environ['LOADTEST_PASSWORD']},
        )
        self._store_tokens(response)

    def _store_tokens(self, response):
        try:
            body = response.json()
        except ValueError:
            return
        tokens = (body.get('data') or {}).get('tokens') or body.get('tokens') or body
        if isinstance(tokens, dict):
            self.access = tokens.get('access', self.access)
            self.refresh = tokens.get('refresh', self.refresh)

    def refresh_tokens(self):
        if not self.refresh:
            return False
        response = self.call('POST', '/auth/token/refresh/', 'auth: refresh', json={'refresh': self.refresh}, retry=False)
        if response.status_code == 200:
            self._store_tokens(response)
            return True
        return False


class StudentUser(_Student):
    """What a student does on the app, in the proportions the plan sets (see LOADTEST.md)."""
    wait_time = between(*THINK)
    hostel_ids = ()
    rooms = ()

    def on_start(self):
        super().on_start()
        self.call('GET', '/cities/', 'public: cities')

    def _remember(self, response):
        try:
            results = response.json().get('results') or []
        except ValueError:
            return
        ids = [item['hostel_id'] for item in results if isinstance(item, dict) and 'hostel_id' in item]
        if ids:
            self.hostel_ids = ids

    @task(45)
    def browse(self):
        city = random.choice(CITIES)
        params = {'city': city, 'page_size': 10}
        roll = random.random()
        if roll < 0.2:
            params['gender_type'] = random.choice(['boys', 'girls'])
        elif roll < 0.3:
            params['amenity'] = 'ac'
        if random.random() < 0.25:
            params['page'] = 2
        # A second page that does not exist (a city with few hostels) is a normal 404, not a failure.
        self._remember(self.call('GET', '/hostels/', 'public: list', expect=(200, 404) if 'page' in params else (200,), params=params))
        if random.random() < 0.3:
            self.call('GET', '/hostels/localities/', 'public: localities', params={'city': city})

    @task(25)
    def detail(self):
        if not self.hostel_ids:
            return self.browse()
        hostel_id = random.choice(self.hostel_ids)
        self.call('GET', f'/hostels/{hostel_id}/', 'detail: hostel')
        rooms = self.call('GET', f'/hostels/{hostel_id}/rooms/', 'detail: rooms')
        try:
            self.rooms = [(hostel_id, r) for r in (rooms.json().get('results') or []) if isinstance(r, dict) and 'room_id' in r]
        except ValueError:
            self.rooms = ()

    @task(10)
    def search(self):
        self.call('GET', '/hostels/', 'search: list', params={'search': random.choice(SEARCH_WORDS), 'page_size': 10})

    @task(10)
    def account_reads(self):
        path, name = random.choice([
            ('/auth/me/', 'auth: me'),
            ('/wishlist/ids/', 'auth: saved ids'),
            ('/bookings/my/', 'auth: my bookings'),
        ])
        self.call('GET', path, name, auth=True)

    @task(3)
    def save_and_unsave(self):
        if not self.hostel_ids:
            return
        hostel_id = random.choice(self.hostel_ids)
        self.call('POST', '/wishlist/', 'write: save hostel', expect=(200, 201), auth=True, json={'hostel_id': hostel_id})
        self.call('DELETE', f'/wishlist/hostel/{hostel_id}/', 'write: unsave hostel', auth=True)

    @task(3)
    def poll_payment(self):
        if self.number > PAYMENT_STUDENTS:
            return
        self.call('GET', f'/payments/status/{rules.payment_id_for(self.number)}/', 'auth: payment status', auth=True)

    @task(2)
    def request_booking(self):
        if not self.rooms:
            return
        hostel_id, room = random.choice(self.rooms)
        self.call(
            'POST', '/bookings/', 'write: create booking', expect=(200, 201), auth=True,
            json={
                'hostel': hostel_id, 'room': room['room_id'], 'room_name': room.get('room_name', ''), 'bed_number': '1',
                'student_name': f'Load Student {self.number}', 'student_phone': '', 'payment_mode': 'offline',
                'check_in_date': '2030-01-01',
            },
        )

    @task(1)
    def renew_token(self):
        self.refresh_tokens()


class LoginStormUser(_Student):
    """Logs in again and again: measures the cost of password hashing under a rush."""
    wait_time = between(1, 3)

    def on_start(self):
        self.number = next(_numbers) % STUDENTS + 1

    @task
    def log_in(self):
        self.login()


class PaymentCreateUser(_Student):
    """Online booking then a Razorpay TEST order. Needs TEST keys on staging; keep it to a handful of users."""
    wait_time = between(5, 15)
    hostel_ids = ()

    @task
    def pay(self):
        listing = self.call('GET', '/hostels/', 'public: list', params={'page_size': 10})
        try:
            hostel_id = random.choice(listing.json()['results'])['hostel_id']
            rooms = self.call('GET', f'/hostels/{hostel_id}/rooms/', 'detail: rooms').json()['results']
            room = random.choice(rooms)
        except (ValueError, KeyError, IndexError):
            return
        booking = self.call(
            'POST', '/bookings/', 'write: create booking', expect=(200, 201), auth=True,
            json={
                'hostel': hostel_id, 'room': room['room_id'], 'room_name': room.get('room_name', ''), 'bed_number': str(random.randint(1, 3)),
                'student_name': f'Load Student {self.number}', 'student_phone': '', 'payment_mode': 'online', 'check_in_date': '2030-01-01',
            },
        )
        try:
            booking_id = booking.json()['id']
        except (ValueError, KeyError):
            return
        self.call('POST', '/payments/create-order/', 'write: create order', expect=(200, 201), auth=True, json={'booking_id': booking_id})


@events.quitting.add_listener
def _judge(environment, **_kwargs):
    """Compares the run with thresholds.json. Exit code 1 when it fails, so a script can tell."""
    try:
        thresholds = json.loads(THRESHOLDS_FILE.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        print(f'Could not read thresholds ({type(exc).__name__}); the run is not judged.', file=sys.stderr)
        return
    errors = {}
    for error in environment.stats.errors.values():
        errors.setdefault(error.name, {})[str(error.error)] = error.occurrences
    rows = [
        {'name': entry.name, 'requests': entry.num_requests, 'p95': entry.get_response_time_percentile(0.95) or 0, 'failures': errors.get(entry.name, {})}
        for entry in environment.stats.entries.values()
    ]
    passed, lines = rules.evaluate(rows, thresholds)
    print('\n=== Thresholds ===\n' + '\n'.join(lines) + f'\nRESULT: {"PASS" if passed else "FAIL"}', flush=True)
    environment.process_exit_code = 0 if passed else 1
