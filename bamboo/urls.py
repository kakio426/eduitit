from django.urls import path

from . import views

app_name = "bamboo"

urlpatterns = [
    path("", views.feed, name="feed"),
    path("write/", views.write, name="write"),
    path("result/<uuid:story_uuid>/", views.result, name="result"),
    path("post/<uuid:story_uuid>/", views.post, name="post"),
    path("post/<uuid:story_uuid>/comments/", views.create_comment, name="comment_create"),
    path(
        "post/<uuid:story_uuid>/comments/<int:comment_id>/delete/",
        views.delete_comment,
        name="comment_delete",
    ),
    path(
        "post/<uuid:story_uuid>/comments/<int:comment_id>/report/",
        views.report_comment,
        name="comment_report",
    ),
    path("<uuid:story_uuid>/like/", views.like_story, name="like"),
    path("<uuid:story_uuid>/report/", views.report_story, name="report"),
    path("<uuid:story_uuid>/delete/", views.delete_story, name="delete"),
    path("<uuid:story_uuid>/visibility/", views.update_visibility, name="visibility"),
]
