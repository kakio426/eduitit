from asgiref.sync import sync_to_async
from django_ratelimit.core import is_ratelimited


def _client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return (request.META.get("REMOTE_ADDR") or "").strip()


def rate_key_for_user_or_ip(group, request):
    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        return f"user:{user.id}"
    return f"ip:{_client_ip(request)}"


def daily_fortune_rate_d(group, request):
    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        return "5/d"
    return "1/d"


def chat_rate_d(group, request):
    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        return "10/d"
    return "1/d"


def chat_turn_limit_for_request(request):
    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        return 10
    return 1


def request_actor_label(request):
    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        username = getattr(user, "username", "") or str(user)
        return username or "authenticated-user"
    return "anonymous"


@sync_to_async
def check_daily_fortune_limit(request):
    return is_ratelimited(
        request,
        group="fortune_daily",
        key=rate_key_for_user_or_ip,
        rate=daily_fortune_rate_d,
        method="POST",
        increment=True,
    )


@sync_to_async
def check_chat_limit(request):
    return is_ratelimited(
        request,
        group="fortune_chat",
        key=rate_key_for_user_or_ip,
        rate=chat_rate_d,
        method="POST",
        increment=True,
    )
