"""
Sized versions of Cloudinary images.

Photos are uploaded to Cloudinary at full size and the public API used to hand those originals to phones. A
Cloudinary delivery URL can carry a transformation (`f_auto` picks WebP or AVIF when the phone supports it,
`q_auto` picks the quality, `c_limit,w_N` shrinks to at most N pixels wide and never enlarges), so the same
stored picture is served at the size the screen needs. Nothing is re-uploaded and the stored URL is unchanged.

Only plain Cloudinary image upload URLs are rewritten. Anything else (another host, a video, a `fetch` URL,
a URL that already carries a transformation, an empty value) is returned exactly as it was.

Cloudinary counts each distinct transformed URL once per month against the plan's credits, so the widths are
few and fixed: LIST_WIDTH for cards, DETAIL_WIDTH for the detail gallery.
"""
import re

LIST_WIDTH = 640
DETAIL_WIDTH = 1600

_UPLOAD = re.compile(r'^(https://res\.cloudinary\.com/[^/]+/image/upload/)(.*)$')
# A path segment such as "w_300,c_fill" or "f_auto,q_auto": one or more known transformation keys.
_TRANSFORMATION = re.compile(
    r'^(?:w|h|c|f|q|g|ar|dpr|e|a|b|r|o|x|y|z|t|l|u|fl|bo|co)_[^/,]+(?:,(?:w|h|c|f|q|g|ar|dpr|e|a|b|r|o|x|y|z|t|l|u|fl|bo|co)_[^/,]+)*$'
)


def sized_image_url(url, width):
    """`url` with automatic format and quality and a maximum width, or `url` unchanged when it is not a plain
    Cloudinary image upload URL (or already carries a transformation)."""
    if not isinstance(url, str):
        return url
    match = _UPLOAD.match(url)
    if match is None:
        return url
    base, rest = match.groups()
    if _TRANSFORMATION.match(rest.split('/', 1)[0]):
        return url
    return f'{base}f_auto,q_auto,c_limit,w_{int(width)}/{rest}'
