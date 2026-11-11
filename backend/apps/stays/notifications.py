"""
Unread notices for the badge on the Home screen's Notices action and on the Active stay screen.

Phase 8 adds notifications; until then there is nothing to count, so this returns 0. It is the one place that changes when
Phase 8 lands (the Home and stay payloads already carry the number).
"""


def unread_count(user):
    return 0
