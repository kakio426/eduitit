import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from classcalendar.message_capture_classifier import build_classifier_text_sample, load_classifier_artifact


class Command(BaseCommand):
    help = "저장된 메시지 캡처 분류기를 평가합니다."

    def add_arguments(self, parser):
        parser.add_argument("--dataset", required=True, help="평가용 JSONL 파일 경로")
        parser.add_argument("--model", default="", help="모델 파일 경로")

    def handle(self, *args, **options):
        try:
            from sklearn.metrics import classification_report
        except ImportError as exc:
            raise CommandError("scikit-learn이 설치되어 있지 않습니다.") from exc

        dataset_path = Path(options["dataset"])
        if not dataset_path.exists():
            raise CommandError(f"데이터셋을 찾을 수 없습니다: {dataset_path}")

        artifact = load_classifier_artifact(model_path=options.get("model") or None)
        if not artifact:
            raise CommandError("평가할 모델을 찾을 수 없습니다.")
        pipeline = artifact.get("pipeline")
        if pipeline is None:
            raise CommandError("모델 아티팩트 형식이 올바르지 않습니다.")

        samples = []
        labels = []
        with dataset_path.open("r", encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                label = row.get("label") or row.get("confirmed_item_type") or row.get("predicted_item_type")
                if label not in {"event", "task", "ignore"}:
                    continue
                sample = build_classifier_text_sample(
                    raw_text=row.get("raw_text") or "",
                    normalized_text=row.get("normalized_text") or "",
                    source_hint=row.get("source_hint") or "unknown",
                    attachment_extensions=row.get("attachment_extensions") or [],
                    parser_result=row.get("initial_extract_payload") or {},
                )
                if not sample.strip():
                    continue
                samples.append(sample)
                labels.append(label)

        if len(samples) < 3:
            raise CommandError("평가 데이터가 부족합니다.")

        predictions = list(pipeline.predict(samples))
        report = classification_report(labels, predictions, digits=4)
        self.stdout.write(report)
