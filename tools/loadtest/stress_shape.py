"""
Optional ramp for finding the limit. Add it to the command: -f locustfile.py,stress_shape.py
Locust then ignores -u/-r and follows these steps (seconds from the start, users, users started per second).
"""
from locust import LoadTestShape

STAGES = [
    (120, 5, 1),      # warm-up: wakes the server, fills caches; ignore these two minutes
    (420, 50, 5),
    (720, 100, 5),
    (1320, 200, 2),   # the launch target, held for 10 minutes
    (1620, 300, 5),
    (1920, 400, 5),
]


class StepShape(LoadTestShape):
    def tick(self):
        run_time = self.get_run_time()
        for end, users, spawn_rate in STAGES:
            if run_time < end:
                return users, spawn_rate
        return None
