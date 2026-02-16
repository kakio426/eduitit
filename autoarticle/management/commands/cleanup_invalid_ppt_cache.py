import os
import zipfile

from django.core.management.base import BaseCommand

from autoarticle.models import GeneratedArticle


class Command(BaseCommand):
    help = "Remove invalid cached PPT files from GeneratedArticle.ppt_file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report invalid files without deleting them.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        scanned = 0
        invalid = 0
        fixed = 0

        qs = GeneratedArticle.objects.exclude(ppt_file="")
        for article in qs.iterator():
            if not article.ppt_file:
                continue

            scanned += 1
            file_name = article.ppt_file.name

            try:
                file_path = article.ppt_file.path
            except Exception:
                file_path = None

            is_valid = bool(file_path and os.path.exists(file_path) and zipfile.is_zipfile(file_path))
            if is_valid:
                continue

            invalid += 1
            self.stdout.write(
                self.style.WARNING(f"[INVALID] article_id={article.id}, file={file_name}")
            )

            if dry_run:
                continue

            try:
                article.ppt_file.delete(save=False)
            except Exception:
                pass
            article.ppt_file = None
            article.save(update_fields=["ppt_file"])
            fixed += 1

        summary = f"scanned={scanned}, invalid={invalid}, fixed={fixed}, dry_run={dry_run}"
        self.stdout.write(self.style.SUCCESS(summary))
