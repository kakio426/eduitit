from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

from doccollab.models import DocRoom


User = get_user_model()


class DoccollabMigrationTests(TransactionTestCase):
    migrate_from = ("doccollab", "0002_alter_docrevision_file_alter_docroom_source_file")
    migrate_to = ("doccollab", "0003_docroom_source_format_and_more")

    def setUp(self):
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_from])
        old_apps = self.executor.loader.project_state([self.migrate_from]).apps

        user = User.objects.create_user(
            username="legacy-doccollab",
            email="legacy-doccollab@example.com",
            password="pw123456",
        )
        workspace_model = old_apps.get_model("doccollab", "DocWorkspace")
        membership_model = old_apps.get_model("doccollab", "DocMembership")
        room_model = old_apps.get_model("doccollab", "DocRoom")

        workspace = workspace_model.objects.create(
            name="기존 문서실",
            created_by_id=user.id,
            status="active",
        )
        membership_model.objects.create(
            workspace_id=workspace.id,
            user_id=user.id,
            role="owner",
            status="active",
            invited_by_id=user.id,
        )
        room = room_model(
            workspace_id=workspace.id,
            title="기존 문서",
            created_by_id=user.id,
            source_name="legacy.hwpx",
            source_sha256="0" * 64,
            last_activity_at=timezone.now(),
            status="active",
        )
        room.source_file.save("legacy.hwpx", ContentFile(b"legacy hwpx bytes"), save=False)
        room.save()
        self.legacy_room_id = room.id

    def tearDown(self):
        self.executor.migrate(self.executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_source_format_backfills_to_hwpx_for_existing_rooms(self):
        self.executor.loader.build_graph()
        self.executor.migrate([self.migrate_to])

        room = DocRoom.objects.get(pk=self.legacy_room_id)

        self.assertEqual(room.source_format, DocRoom.SourceFormat.HWPX)
