from django.contrib.staticfiles import finders
from django.http import FileResponse, Http404, HttpResponse

from .seo import SITE_CANONICAL_BASE_URL


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        f"Sitemap: {SITE_CANONICAL_BASE_URL}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")


def favicon_ico(request):
    favicon_path = finders.find("favicon.ico")
    if not favicon_path:
        raise Http404("favicon.ico not found")

    response = FileResponse(open(favicon_path, "rb"), content_type="image/x-icon")
    response["Cache-Control"] = "public, max-age=604800, immutable"
    return response
