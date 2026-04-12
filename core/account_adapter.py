from allauth.account.adapter import DefaultAccountAdapter

from .policy_consent import get_pending_policy_consent_redirect


class EduititAccountAdapter(DefaultAccountAdapter):
    def _get_policy_redirect(self, request, *, default_next_url):
        return get_pending_policy_consent_redirect(request, next_url=default_next_url)

    def get_signup_redirect_url(self, request):
        default_url = super().get_signup_redirect_url(request)
        return self._get_policy_redirect(request, default_next_url=default_url) or default_url

    def get_login_redirect_url(self, request):
        default_url = super().get_login_redirect_url(request)
        return self._get_policy_redirect(request, default_next_url=default_url) or default_url
