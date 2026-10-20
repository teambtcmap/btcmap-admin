"""Readable text for JSON-RPC errors returned by the BTC Map API.

The API answers a failed RPC with HTTP 200 and a JSON-RPC error object. Two
shapes reach us:

- handler failures — ``handle_rpc_error`` in the API wraps the error in
  ``{"code": -32000, "message": "Server error", "data": "<the real message>"}``,
  so ``message`` is boilerplate and ``data`` is what the user needs to see;
- permission refusals — ``{"code": 1, "message": "You don't have permissions
  to call this method"}`` with no ``data``.

Both are flattened to one line here so every route and template shows the same
text instead of "Server error" or "[object Object]".
"""

# Filler the API uses when the informative text is somewhere else.
GENERIC_MESSAGES = frozenset({
    'Server error',
    'Internal Server Error',
    'Unknown error',
})

# What the API says when an id/alias lookup matched nothing.
NOT_FOUND_MESSAGES = frozenset({
    'Query returned no rows',
})

# rpc_call() reports its own failures with these prefixes when the API never
# answered; they are not refusals by the API.
TRANSPORT_ERROR_PREFIXES = (
    'Timeout error in RPC call',
    'Network error in RPC call',
    'Unexpected error in RPC call',
)

DEFAULT_MESSAGE = 'The BTC Map API rejected this request'


def _text(value):
    """Return a trimmed string, or None when ``value`` carries no message."""
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        return _text(value.get('message')) or _text(value.get('error'))
    return None


def rpc_error_message(error, fallback=DEFAULT_MESSAGE):
    """Flatten a JSON-RPC ``error`` member into one line worth showing a user."""
    if isinstance(error, str):
        return error.strip() or fallback
    if not isinstance(error, dict):
        return fallback

    data = _text(error.get('data'))
    message = _text(error.get('message'))

    if data:
        return data
    if message and message not in GENERIC_MESSAGES:
        return message
    return message or fallback


def is_not_found(message):
    """True when the API could not resolve the requested id or alias."""
    return (message or '').strip() in NOT_FOUND_MESSAGES


def is_transport_error(message):
    """True when the message came from ``rpc_call`` rather than the API."""
    return (message or '').startswith(TRANSPORT_ERROR_PREFIXES)
