from django.core.cache import cache
from django.test import TestCase

from core.ai_usage_limits import consume_ai_usage_limit, consume_ai_usage_limits


class AIUsageLimitTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_consume_ai_usage_limit_blocks_after_max_count(self):
        self.assertFalse(consume_ai_usage_limit("unit:test", "teacher:1", ((86400, 1),)))
        self.assertTrue(consume_ai_usage_limit("unit:test", "teacher:1", ((86400, 1),)))

    def test_consume_ai_usage_limits_checks_all_scopes_before_incrementing(self):
        self.assertTrue(
            consume_ai_usage_limits(
                (
                    ("unit:test:teacher", "teacher:1", ((86400, 1),)),
                    ("unit:test:room", "room:1", ((86400, 0),)),
                )
            )
        )
        self.assertFalse(consume_ai_usage_limit("unit:test:teacher", "teacher:1", ((86400, 1),)))
