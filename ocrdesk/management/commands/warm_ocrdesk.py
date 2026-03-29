import os

from django.core.management.base import BaseCommand, CommandError

from ocrdesk.services import OCREngineUnavailable, _get_paddlex_cache_dir, get_ocr_engine


def _strict_warmup_enabled():
    raw_value = os.environ.get("OCRDESK_STRICT_WARMUP", "")
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


class Command(BaseCommand):
    help = "Warm the Paddle OCR engine and pre-download OCR models into the shared cache."

    def add_arguments(self, parser):
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Fail the command when the OCR engine cannot be prepared.",
        )

    def handle(self, *args, **options):
        self.stdout.write("[ocrdesk] warming Paddle OCR engine")
        self.stdout.write(f"[ocrdesk] cache dir: {_get_paddlex_cache_dir()}")

        try:
            get_ocr_engine()
        except OCREngineUnavailable as exc:
            message = f"[ocrdesk] warmup failed: {exc}"
            if options["strict"] or _strict_warmup_enabled():
                raise CommandError(message) from exc
            self.stderr.write(self.style.WARNING(message))
            return

        self.stdout.write(self.style.SUCCESS("[ocrdesk] Paddle OCR engine ready"))
