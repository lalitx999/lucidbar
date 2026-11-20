"""
Session keys that carry a visitor through multi-step flows (verify, reset).

Only an ID or email is stored in the session; nothing secret.
"""

PENDING_MEMBER_KEY = "pending_member_id"
RESET_EMAIL_KEY = "reset_email"


def remember_pending_member(request, member):
    request.session[PENDING_MEMBER_KEY] = member.pk


def pending_member_id(request):
    return request.session.get(PENDING_MEMBER_KEY)


def forget_pending_member(request):
    request.session.pop(PENDING_MEMBER_KEY, None)


def remember_reset_email(request, email):
    request.session[RESET_EMAIL_KEY] = email.strip().lower()


def reset_email(request):
    return request.session.get(RESET_EMAIL_KEY)


def forget_reset_email(request):
    request.session.pop(RESET_EMAIL_KEY, None)
