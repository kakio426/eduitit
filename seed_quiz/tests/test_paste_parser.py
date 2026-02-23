from django.test import SimpleTestCase

from seed_quiz.services.paste_parser import parse_pasted_text_to_csv_bytes


class PasteParserTest(SimpleTestCase):
    def test_parse_tsv_text(self):
        raw = (
            "주제\t학년\t문제\t보기1\t보기2\t보기3\t보기4\t정답번호\t해설\t난이도\n"
            "맞춤법\t3\t다음 중 맞는 것은?\t가\t나\t다\t라\t1\t해설\t쉬움\n"
        )
        csv_bytes, source_format, errors = parse_pasted_text_to_csv_bytes(raw)
        self.assertEqual(source_format, "tsv")
        self.assertFalse(errors)
        self.assertIsNotNone(csv_bytes)
        body = csv_bytes.decode("utf-8")
        self.assertIn("preset_type,grade,question_text", body)
        self.assertIn("맞춤법,3,다음 중 맞는 것은?", body)

    def test_parse_stacked_lines_text(self):
        raw = (
            "주제\n학년\n문제\n보기1\n보기2\n보기3\n보기4\n정답번호\n해설\n난이도\n"
            "맞춤법\n3\n다음 중 맞는 것은?\n가\n나\n다\n라\n1\n해설\n보통\n"
        )
        csv_bytes, source_format, errors = parse_pasted_text_to_csv_bytes(raw)
        self.assertEqual(source_format, "stacked_lines")
        self.assertFalse(errors)
        self.assertIsNotNone(csv_bytes)
        body = csv_bytes.decode("utf-8")
        self.assertIn("맞춤법,3,다음 중 맞는 것은?", body)

    def test_parse_json_items(self):
        raw = (
            '{"preset_type":"orthography","grade":3,"items":['
            '{"question_text":"문제","choices":["가","나","다","라"],"correct_index":0,"explanation":"해설","difficulty":"easy"}'
            "]}"
        )
        csv_bytes, source_format, errors = parse_pasted_text_to_csv_bytes(raw)
        self.assertEqual(source_format, "json")
        self.assertFalse(errors)
        self.assertIsNotNone(csv_bytes)
        body = csv_bytes.decode("utf-8")
        self.assertIn("orthography,3,문제,가,나,다,라,1,해설,easy", body)

    def test_parse_empty_text_returns_error(self):
        csv_bytes, source_format, errors = parse_pasted_text_to_csv_bytes(" \n ")
        self.assertIsNone(csv_bytes)
        self.assertEqual(source_format, "empty")
        self.assertTrue(errors)

