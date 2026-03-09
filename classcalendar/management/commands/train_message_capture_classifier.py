import json
import pickle
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from classcalendar.message_capture_classifier import build_classifier_text_sample, get_default_model_path


class Command(BaseCommand):
    help = "메시지 캡처 분류기(Logistic Regression)를 학습합니다."

    def add_arguments(self, parser):
        parser.add_argument("--dataset", required=True, help="학습용 JSONL 파일 경로")
        parser.add_argument("--output", default="", help="모델 저장 경로")
        parser.add_argument("--min-rows", type=int, default=20, help="최소 학습 건수")

    def handle(self, *args, **options):
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.linear_model import LogisticRegression
            from sklearn.pipeline import Pipeline
        except ImportError as exc:
            raise CommandError("scikit-learn이 설치되어 있지 않습니다.") from exc

        dataset_path = Path(options["dataset"])
        if not dataset_path.exists():
            raise CommandError(f"데이터셋을 찾을 수 없습니다: {dataset_path}")

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

        min_rows = int(options.get("min_rows") or 20)
        if len(samples) < min_rows:
            raise CommandError(f"학습 데이터가 부족합니다. 현재 {len(samples)}건, 최소 {min_rows}건 필요합니다.")

        pipeline = Pipeline(
            [
                ("vectorizer", TfidfVectorizer(analyzer="char", ngram_range=(2, 5), lowercase=False)),
                ("classifier", LogisticRegression(max_iter=2000)),
            ]
        )
        pipeline.fit(samples, labels)

        output_path = Path(options.get("output") or get_default_model_path())
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("wb") as fp:
            pickle.dump({"pipeline": pipeline, "labels": list(pipeline.classes_)}, fp)

        self.stdout.write(self.style.SUCCESS(f"trained model saved to {output_path}"))
