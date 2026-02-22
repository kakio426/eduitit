import json

from django.test import TestCase
from django.urls import reverse

from .manual_pipeline import ManualPipelineError, parse_manual_pipeline_result


class ManualPipelineParserTest(TestCase):
    def test_parse_json_with_time_materials_and_tip(self):
        payload = {
            "video_title": "테스트 수업",
            "steps": [
                {
                    "start": "00:35",
                    "end": "01:20",
                    "summary": "도화지 중앙에 큰 원을 그린다.",
                    "materials": ["도화지", "연필"],
                    "teacher_tip": "선을 약하게 시작하세요.",
                },
                {
                    "summary": "배경 색을 칠하고 명암을 넣는다.",
                },
            ],
        }

        result = parse_manual_pipeline_result(json.dumps(payload, ensure_ascii=False))

        self.assertEqual(result["meta"]["mode"], "json")
        self.assertEqual(result["meta"]["step_count"], 2)
        self.assertIn("[00:35-01:20]", result["steps"][0]["text"])
        self.assertIn("준비물:", result["steps"][0]["text"])
        self.assertIn("교사 팁:", result["steps"][0]["text"])

    def test_parse_fenced_json(self):
        raw_text = """```json
{
  "steps": [
    {"summary": "재료를 준비한다."},
    {"summary": "색을 섞어 바탕을 칠한다."}
  ]
}
```"""
        result = parse_manual_pipeline_result(raw_text)
        self.assertEqual(result["meta"]["mode"], "json")
        self.assertEqual(len(result["steps"]), 2)

    def test_parse_plain_text_list(self):
        raw_text = """
1. [00:10] 연필로 스케치를 시작한다.
2. [00:45] 스케치 선을 정리한다.
3. 색연필로 주요 부분에 색을 넣는다.
"""
        result = parse_manual_pipeline_result(raw_text)
        self.assertEqual(result["meta"]["mode"], "plain_text")
        self.assertEqual(len(result["steps"]), 3)
        self.assertIn("[00:10]", result["steps"][0]["text"])

    def test_rejects_heavily_duplicated_steps(self):
        payload = {"steps": [{"summary": "같은 문장이 반복됩니다"} for _ in range(5)]}
        with self.assertRaises(ManualPipelineError) as exc:
            parse_manual_pipeline_result(json.dumps(payload, ensure_ascii=False))
        self.assertEqual(exc.exception.code, "DUPLICATED_STEPS")


class ManualPipelineApiTest(TestCase):
    def test_parse_gemini_steps_api_success(self):
        url = reverse("artclass:parse_gemini_steps_api")
        raw = json.dumps(
            {
                "steps": [
                    {"start": "00:12", "summary": "주요 도형을 크게 잡는다."},
                    {"summary": "윤곽선을 정리하고 색을 넣는다."},
                ]
            },
            ensure_ascii=False,
        )

        response = self.client.post(
            url,
            data=json.dumps(
                {
                    "videoUrl": "https://www.youtube.com/watch?v=2bBhnfh4StU",
                    "rawText": raw,
                },
                ensure_ascii=False,
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["meta"]["step_count"], 2)
        self.assertIn("https://www.youtube.com/watch?v=2bBhnfh4StU", data["promptTemplate"])

    def test_parse_gemini_steps_api_rejects_empty_input(self):
        url = reverse("artclass:parse_gemini_steps_api")
        response = self.client.post(
            url,
            data=json.dumps({"rawText": ""}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "EMPTY_INPUT")

    def test_parse_gemini_steps_api_method_not_allowed(self):
        url = reverse("artclass:parse_gemini_steps_api")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)
