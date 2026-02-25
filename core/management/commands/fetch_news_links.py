from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from core.models import NewsSource, Post
from core.news_ingest import (
    UnsafeNewsUrlError,
    assert_safe_public_url,
    canonicalize_url,
    classify_tags,
    extract_domain,
    extract_og_metadata,
    fetch_rss_entries,
)


class Command(BaseCommand):
    help = "활성화된 NewsSource를 순회하며 뉴스 링크를 자동 수집합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit-per-source",
            type=int,
            default=10,
            help="소스당 처리할 최대 엔트리 수 (기본값: 10)",
        )
        parser.add_argument(
            "--source-id",
            type=int,
            default=None,
            help="특정 NewsSource ID만 처리",
        )
        parser.add_argument(
            "--bot-username",
            type=str,
            default="newsbot",
            help="자동 업로드 작성자로 사용할 계정명",
        )
        parser.add_argument(
            "--auto-approve",
            action="store_true",
            help="수집 즉시 승인 상태로 게시합니다. (기본: 승인 대기)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="DB에 저장하지 않고 처리 결과만 출력합니다.",
        )
        parser.add_argument(
            "--max-age-hours",
            type=int,
            default=72,
            help="이 시간보다 오래된 기사는 자동 수집에서 제외합니다. (기본값: 72)",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        source_qs = NewsSource.objects.filter(is_active=True).order_by("id")
        source_id = options.get("source_id")
        if source_id:
            source_qs = source_qs.filter(pk=source_id)

        if not source_qs.exists():
            self.stdout.write(self.style.WARNING("활성화된 NewsSource가 없습니다."))
            return

        max_pending = int(getattr(settings, "NEWS_INGEST_MAX_PENDING", 200))
        pending_count = Post.objects.filter(post_type="news_link", approval_status="pending").count()
        if not options["auto_approve"] and pending_count >= max_pending:
            self.stdout.write(
                self.style.WARNING(
                    f"중단: 승인 대기 뉴스가 {pending_count}건으로 상한({max_pending})을 초과했습니다."
                )
            )
            self.stdout.write("먼저 /news/review/에서 일부 승인/반려 후 다시 실행하세요.")
            return

        allowed_hosts = list(getattr(settings, "NEWS_INGEST_ALLOWED_HOSTS", []))
        bot_user = self._get_or_create_bot_user(options["bot_username"])
        created_total = 0
        skipped_total = 0
        failed_total = 0
        og_fallback_total = 0
        stale_skipped_total = 0
        max_age_hours = max(1, int(options["max_age_hours"]))
        now_dt = timezone.now()

        for source in source_qs:
            self.stdout.write(f"[SOURCE] {source.id} {source.name}")
            try:
                entries = fetch_rss_entries(source.url, allowed_host_suffixes=allowed_hosts or None)
            except Exception as exc:
                failed_total += 1
                self.stdout.write(self.style.ERROR(f"  - RSS 조회 실패: {exc}"))
                continue

            for entry in entries[: options["limit_per_source"]]:
                if entry.published_at:
                    age_hours = (now_dt - entry.published_at).total_seconds() / 3600
                    if age_hours > max_age_hours:
                        stale_skipped_total += 1
                        continue

                source_url = canonicalize_url(entry.link)
                if not source_url:
                    skipped_total += 1
                    continue

                try:
                    source_url = assert_safe_public_url(source_url, allowed_host_suffixes=allowed_hosts or None)
                except UnsafeNewsUrlError:
                    skipped_total += 1
                    continue

                if self._already_exists(source_url):
                    skipped_total += 1
                    continue

                try:
                    og_meta = extract_og_metadata(
                        source_url,
                        allowed_host_suffixes=allowed_hosts or None,
                    )
                except Exception:
                    og_fallback_total += 1
                    og_meta = {
                        "title": entry.title,
                        "description": entry.description,
                        "image_url": "",
                        "canonical_url": source_url,
                        "published_at": None,
                        "final_url": source_url,
                        "publisher": extract_domain(source_url),
                    }

                canonical_url = canonicalize_url(
                    str(og_meta.get("canonical_url") or og_meta.get("final_url") or source_url)
                )
                if self._already_exists(canonical_url):
                    skipped_total += 1
                    continue

                title = str(og_meta.get("title") or entry.title or "").strip()
                description = str(og_meta.get("description") or entry.description or "").strip()
                image_url = str(og_meta.get("image_url") or "").strip()
                publisher = str(og_meta.get("publisher") or extract_domain(source_url) or "").strip()
                published_at = og_meta.get("published_at") or entry.published_at
                primary_tag, secondary_tag = classify_tags(
                    title=title,
                    description=description,
                    source_type=source.source_type,
                    publisher=publisher,
                )

                approval_status = "approved" if options["auto_approve"] else "pending"
                reviewed_at = timezone.now() if approval_status == "approved" else None
                reviewed_by = bot_user if approval_status == "approved" else None

                if options["dry_run"]:
                    self.stdout.write(f"  - DRY-RUN 신규: {title[:80] or source_url}")
                    created_total += 1
                    continue

                post_content = title or description or source_url
                Post.objects.create(
                    author=bot_user,
                    content=post_content[:500],
                    post_type="news_link",
                    source_type=source.source_type,
                    source_url=source_url[:1000],
                    canonical_url=canonical_url[:1000],
                    og_title=title[:300],
                    og_description=description,
                    og_image_url=image_url[:1000],
                    publisher=publisher[:120],
                    published_at=published_at,
                    primary_tag=primary_tag[:40],
                    secondary_tag=secondary_tag[:40],
                    approval_status=approval_status,
                    reviewed_at=reviewed_at,
                    reviewed_by=reviewed_by,
                    news_source=source,
                )
                created_total += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"완료: 생성 {created_total} / 중복·스킵 {skipped_total} / 구기사 제외 {stale_skipped_total} / 실패 {failed_total} / OG 폴백 {og_fallback_total}"
            )
        )
        if not options["auto_approve"]:
            self.stdout.write("신규 뉴스는 기본적으로 '승인 대기' 상태로 저장되었습니다.")

    @staticmethod
    def _already_exists(url: str) -> bool:
        if not url:
            return False
        return Post.objects.filter(
            post_type="news_link",
        ).filter(
            Q(source_url=url) | Q(canonical_url=url)
        ).exists()

    def _get_or_create_bot_user(self, username: str):
        UserModel = get_user_model()
        bot_user, created = UserModel.objects.get_or_create(
            username=username,
            defaults={
                "email": f"{username}@eduitit.local",
                "is_active": True,
            },
        )
        if created:
            bot_user.set_unusable_password()
            bot_user.save(update_fields=["password"])
            self.stdout.write(f"[INFO] bot 계정 생성: {username}")
        return bot_user
