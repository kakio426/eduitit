from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView


OPENCLO_LOGIN_PATH = "_bridge/teacher-access-9f84c1d6/"
OPENCLO_LOGIN_URL = f"/{OPENCLO_LOGIN_PATH}"


class OpenCloLoginView(LoginView):
    authentication_form = AuthenticationForm
    template_name = "core/openclo_login.html"
    redirect_authenticated_user = True

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        response["X-Robots-Tag"] = "noindex, nofollow, noarchive, nosnippet"
        response["Cache-Control"] = "no-store, max-age=0"
        response["Pragma"] = "no-cache"
        response["Referrer-Policy"] = "same-origin"
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Secure Workspace Access",
                "robots": "noindex,nofollow,noarchive,nosnippet",
            }
        )
        return context


openclo_login_view = OpenCloLoginView.as_view()
