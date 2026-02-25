from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.utils import timezone

from core.models import Post
from core.news_ingest import compute_news_score, pick_core_news


class Command(BaseCommand):
    help = "뉴스 링크 게시글의 랭킹 점수를 갱신하고 핵심 5개 후보를 계산합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=3,
            help="점수 계산 대상 기간(일) (기본값: 3)",
        )
        parser.add_argument(
            "--print-top",
            action="store_true",
            help="핵심 5개 후보를 콘솔에 출력합니다.",
        )

    def handle(self, *args, **options):
        since = timezone.now() - timedelta(days=options["days"])
        news_posts = list(
            Post.objects.filter(
                post_type="news_link",
                approval_status="approved",
                created_at__gte=since,
            )
            .annotate(
                likes_count_annotated=Count("likes", distinct=True),
                comments_count_annotated=Count(
                    "comments",
                    filter=Q(comments__is_hidden=False),
                    distinct=True,
                ),
            )
            .order_by("-created_at")
        )

        if not news_posts:
            self.stdout.write(self.style.WARNING("점수 갱신 대상 뉴스가 없습니다."))
            return

        for post in news_posts:
            post.ranking_score = compute_news_score(post)
        Post.objects.bulk_update(news_posts, ["ranking_score"])

        self.stdout.write(self.style.SUCCESS(f"랭킹 점수 갱신 완료: {len(news_posts)}개"))

        if options["print_top"]:
            core_five = pick_core_news(news_posts, pick_count=5)
            self.stdout.write("핵심 5개 후보:")
            for idx, post in enumerate(core_five, start=1):
                title = post.og_title or post.content
                self.stdout.write(f"{idx}. [{post.primary_tag}] {title} ({post.ranking_score:.2f})")
