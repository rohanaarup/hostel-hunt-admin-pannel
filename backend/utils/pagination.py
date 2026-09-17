from rest_framework.pagination import PageNumberPagination

class CustomPageNumberPagination(PageNumberPagination):
    """
    Standard flat DRF envelope: {count, next, previous, results}.

    NOTE: this class previously overrode get_paginated_response() to wrap
    the page in {success, message, data: {...}}. That shape was never
    actually wired up anywhere (dead code), but both the Flutter app
    (hostel_provider.dart, search_provider.dart — checks body['results']
    at the top level) and the admin panel (hooks/queries.ts `unwrap()` —
    res?.data ?? res?.results ?? res, then requires an array) already
    assume the flat shape. Keeping the default get_paginated_response()
    here so turning pagination on doesn't require client changes.
    """
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100
