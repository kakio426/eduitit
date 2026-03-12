from django.http import HttpResponse

from .seo import SITE_CANONICAL_BASE_URL


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /secret-admin-kakio/",
        "Disallow: /accounts/",
        "Disallow: /api/",
        "Disallow: */review/",
        "Disallow: */create/",
        "Disallow: */edit/",
        "Disallow: */delete/",
        "Disallow: /news/review/",
        "Disallow: /insights/review/",
        "Disallow: /insights/create/",
        "Disallow: /insights/paste/",
        f"Sitemap: {SITE_CANONICAL_BASE_URL}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")
