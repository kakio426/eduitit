from time import perf_counter

from django.conf import settings
from django.core.management import call_command, get_commands
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
            ("createcachetable_if_needed", self._create_cache_table_if_needed),
            ("ensure_ssambti", lambda: call_command("ensure_ssambti")),
            ("ensure_studentmbti", lambda: call_command("ensure_studentmbti")),
            ("ensure_notebooklm", lambda: call_command("ensure_notebooklm")),
            ("ensure_collect", lambda: call_command("ensure_collect")),
            ("ensure_handoff", lambda: call_command("ensure_handoff")),
            ("ensure_qrgen", lambda: call_command("ensure_qrgen")),
            ("ensure_hwpxchat", lambda: call_command("ensure_hwpxchat")),
            ("ensure_doccollab", lambda: call_command("ensure_doccollab")),
            ("ensure_consent", lambda: call_command("ensure_consent")),
            ("ensure_docsign", lambda: call_command("ensure_docsign")),
            ("ensure_reservations", lambda: call_command("ensure_reservations")),
            ("ensure_version_manager", lambda: call_command("ensure_version_manager")),
            ("ensure_janggi", lambda: call_command("ensure_janggi")),
            ("ensure_fairy_games", lambda: call_command("ensure_fairy_games")),
            ("ensure_reflex_game", lambda: call_command("ensure_reflex_game")),
            ("ensure_math_games", lambda: call_command("ensure_math_games")),
            ("ensure_mancala", lambda: call_command("ensure_mancala")),
            ("ensure_ppobgi", lambda: call_command("ensure_ppobgi")),
            ("ensure_happy_seed", lambda: call_command("ensure_happy_seed")),
            ("ensure_seed_quiz", lambda: call_command("ensure_seed_quiz")),
            ("seed_quiz_bank", lambda: call_command("seed_quiz_bank")),
            ("ensure_noticegen", lambda: call_command("ensure_noticegen")),
            ("ensure_timetable", lambda: call_command("ensure_timetable")),
            ("ensure_classcalendar", lambda: call_command("ensure_classcalendar")),
            ("ensure_schoolcomm", lambda: call_command("ensure_schoolcomm")),
            ("ensure_schoolprograms", lambda: call_command("ensure_schoolprograms")),
            ("ensure_quickdrop", lambda: call_command("ensure_quickdrop")),
            ("ensure_ocrdesk", lambda: call_command("ensure_ocrdesk")),
            ("warm_ocrdesk", lambda: self._run_optional_command("warm_ocrdesk")),
            ("ensure_parentcomm", lambda: call_command("ensure_parentcomm")),
            ("ensure_insights", lambda: call_command("ensure_insights")),
            ("ensure_docviewer", lambda: call_command("ensure_docviewer")),
            ("ensure_pdfhub", lambda: call_command("ensure_pdfhub")),
            ("ensure_slidesmith", lambda: call_command("ensure_slidesmith")),
            ("ensure_blockclass", lambda: call_command("ensure_blockclass")),
            ("ensure_textbooks", lambda: call_command("ensure_textbooks")),
            ("ensure_textbook_ai", lambda: call_command("ensure_textbook_ai")),
            ("ensure_edu_materials", lambda: call_command("ensure_edu_materials")),
            ("ensure_edu_materials_next", lambda: call_command("ensure_edu_materials_next")),
            ("ensure_tts_announce", lambda: call_command("ensure_tts_announce")),
            ("ensure_infoboard", lambda: call_command("ensure_infoboard")),
            ("ensure_teacher_law", lambda: call_command("ensure_teacher_law")),
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

    def _run_optional_command(self, command_name, *args):
        if not self._command_exists(command_name):
            self.stdout.write(f"[bootstrap] skip {command_name}: command not available")
            return
        call_command(command_name, *args)

    @staticmethod
    def _command_exists(command_name):
        return command_name in get_commands()
