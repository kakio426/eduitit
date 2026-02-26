from django.contrib.auth import get_user_model
from django.test import TestCase

from collect.forms import CollectionRequestForm
from handoff.models import HandoffRosterGroup


User = get_user_model()


class CollectionRequestFormTest(TestCase):
    def test_shared_roster_group_choice_uses_group_name_only(self):
        owner = User.objects.create_user(
            username="user694",
            email="owner@example.com",
            password="pw12345",
        )
        group = HandoffRosterGroup.objects.create(owner=owner, name="2026 현암초등학교 담임")

        form = CollectionRequestForm(owner=owner)
        selected_label = None
        for value, label in form.fields["shared_roster_group"].choices:
            if str(value) == str(group.id):
                selected_label = label
                break

        self.assertEqual(selected_label, group.name)
        self.assertNotIn(owner.username, selected_label)
