from django.core.management.base import BaseCommand, CommandError

from textbook_ai.models import TextbookDocument
from textbook_ai.services import rebuild_document_from_saved_artifact


class Command(BaseCommand):
    help = "Rebuild textbook_ai chunks from saved parser artifacts."

    def add_arguments(self, parser):
        parser.add_argument("--document-id", dest="document_id")

    def handle(self, *args, **options):
        document_id = options.get("document_id")
        queryset = TextbookDocument.objects.select_related("artifact").order_by("updated_at")
        if document_id:
            queryset = queryset.filter(id=document_id)
        documents = list(queryset)
        if not documents:
            raise CommandError("재구성할 문서를 찾지 못했습니다.")

        rebuilt = 0
        for document in documents:
            rebuild_document_from_saved_artifact(document)
            rebuilt += 1
            self.stdout.write(self.style.SUCCESS(f"[textbook_ai_reindex] rebuilt: {document.id}"))

        self.stdout.write(self.style.SUCCESS(f"[textbook_ai_reindex] total rebuilt: {rebuilt}"))
