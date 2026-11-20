"""
Small fixed-window rate limiter backed by the Django cache (Redis in dev/prod).

Kept deliberately simple: a counter per key that expires after the window.
"""

from django.core.cache import cache


def _key(scope, identifier):
    return f"rl:{scope}:{identifier}"


def hit(scope, identifier, window_seconds):
    """Record one event and return the number of events in the current window."""
    key = _key(scope, identifier)
    # add() only sets the key if it does not exist, which starts the window.
    if cache.add(key, 1, timeout=window_seconds):
        return 1
    try:
        return cache.incr(key)
    except ValueError:
        # Key expired between add() and incr(); start a new window.
        cache.set(key, 1, timeout=window_seconds)
        return 1


def count(scope, identifier):
    return cache.get(_key(scope, identifier), 0)


def is_limited(scope, identifier, limit):
    return count(scope, identifier) >= limit


def reset(scope, identifier):
    cache.delete(_key(scope, identifier))
