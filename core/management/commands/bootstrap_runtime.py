from time import perf_counter

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Run runtime bootstrap tasks once before app server starts."

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("[bootstrap] start"))

        steps = [
            ("migrate", lambda: call_command("migrate", "--noinput")),
            ("check_consent_schema", lambda: call_command("check_consent_schema")),
            ("check_collect_schema", lambda: call_command("check_collect_schema")),
            ("check_sheetbook_rollout", self._check_sheetbook_rollout),
            ("createcachetable_if_needed", self._create_cache_table_if_needed),
            ("ensure_ssambti", lambda: call_command("ensure_ssambti")),
            ("ensure_studentmbti", lambda: call_command("ensure_studentmbti")),
            ("ensure_notebooklm", lambda: call_command("ensure_notebooklm")),
            ("ensure_collect", lambda: call_command("ensure_collect")),
            ("ensure_handoff", lambda: call_command("ensure_handoff")),
            ("ensure_qrgen", lambda: call_command("ensure_qrgen")),
            ("ensure_hwpxchat", lambda: call_command("ensure_hwpxchat")),
            ("ensure_consent", lambda: call_command("ensure_consent")),
            ("ensure_reservations", lambda: call_command("ensure_reservations")),
            ("ensure_version_manager", lambda: call_command("ensure_version_manager")),
            ("ensure_janggi", lambda: call_command("ensure_janggi")),
            ("ensure_fairy_games", lambda: call_command("ensure_fairy_games")),
            ("ensure_ppobgi", lambda: call_command("ensure_ppobgi")),
            ("ensure_happy_seed", lambda: call_command("ensure_happy_seed")),
            ("ensure_seed_quiz", lambda: call_command("ensure_seed_quiz")),
            ("seed_quiz_bank", lambda: call_command("seed_quiz_bank")),
            ("ensure_noticegen", lambda: call_command("ensure_noticegen")),
            ("ensure_timetable", lambda: call_command("ensure_timetable")),
            ("ensure_classcalendar", lambda: call_command("ensure_classcalendar")),
            ("ensure_sheetbook", lambda: call_command("ensure_sheetbook")),
            ("ensure_parentcomm", lambda: call_command("ensure_parentcomm")),
            ("ensure_insights", lambda: call_command("ensure_insights")),
        ]

        for name, fn in steps:
            started = perf_counter()
            self.stdout.write(f"[bootstrap] running: {name}")
            fn()
            elapsed_ms = int((perf_counter() - started) * 1000)
            self.stdout.write(self.style.SUCCESS(f"[bootstrap] done: {name} ({elapsed_ms} ms)"))

        self.stdout.write(self.style.SUCCESS("[bootstrap] complete"))

    def _create_cache_table_if_needed(self):
        cache_table = "django_cache_table"
        table_names = connection.introspection.table_names()
        if cache_table in table_names:
            self.stdout.write(f"[bootstrap] skip createcachetable: '{cache_table}' exists")
            return
        call_command("createcachetable")

    def _check_sheetbook_rollout(self):
        if getattr(settings, "SHEETBOOK_ROLLOUT_STRICT_STARTUP", False):
            call_command("check_sheetbook_rollout", "--strict")
        else:
            call_command("check_sheetbook_rollout")

        if getattr(settings, "SHEETBOOK_ROLLOUT_RECOMMEND_STARTUP", False):
            raw_days = getattr(settings, "SHEETBOOK_ROLLOUT_RECOMMEND_DAYS", 14)
            try:
                recommend_days = int(raw_days)
            except (TypeError, ValueError):
                recommend_days = 14
            if recommend_days < 1:
                recommend_days = 14
            call_command("recommend_sheetbook_thresholds", "--days", str(recommend_days))
