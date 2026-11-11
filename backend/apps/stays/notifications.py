"""
Unread notices for the badge on the Home screen Notices action and on the Active stay screen: the real count from
apps/notifications (cached 15 seconds per user). Kept as one small function so the stay payloads do not import the
notifications app at module load.
"""


def unread_count(user):
    from apps.notifications import services
    return services.unread_count(user)
