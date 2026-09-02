"""The versions of the documents an account agreed to.

One definition, on the backend, because a version string that lives in two
places will eventually say two things. The frontend reads these from the API
rather than repeating them, and signup is validated against them rather than
recording whatever the client claimed.

Bump a version only for a *material* change — one a reasonable person would
want to be told about. Fixing a typo is not that, and bumping for it trains
people to click through the notice that matters.
"""

#: ISO dates, so ordering and meaning are both obvious at a glance.
CURRENT_TERMS_VERSION = "2026-09-02"
CURRENT_PRIVACY_VERSION = "2026-09-02"


def is_current_terms(version: str | None) -> bool:
    return version == CURRENT_TERMS_VERSION


def is_current_privacy(version: str | None) -> bool:
    return version == CURRENT_PRIVACY_VERSION
