from django.test import SimpleTestCase

class BasicTest(SimpleTestCase):
    def test_basic_logic(self):
        self.assertEqual(1 + 1, 2)
