import math
import statistics
import time
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from sheetbook.models import SheetColumn, SheetTab, Sheetbook
from sheetbook.views import _build_grid_data_payload, _paste_matrix_into_grid_tab


def _parse_int_list(raw, option_name):
    values = []
    for item in str(raw or "").split(","):
        token = item.strip()
        if not token:
            continue
        try:
            values.append(int(token))
        except (TypeError, ValueError):
            raise CommandError(f"{option_name} 값은 정수 목록이어야 합니다: {raw}")
    if not values:
        raise CommandError(f"{option_name} 값이 비어 있습니다.")
    return values


def _build_matrix(row_count, col_count):
    base_day = date(2026, 3, 1)
    matrix = []
    for row_idx in range(row_count):
        row_values = []
        for col_idx in range(col_count):
            mod = col_idx % 3
            if mod == 0:
                row_values.append(f"행{row_idx + 1}-열{col_idx + 1}")
            elif mod == 1:
                row_values.append(str((row_idx + 1) * (col_idx + 2)))
            else:
                row_values.append((base_day + timedelta(days=((row_idx + col_idx) % 27))).isoformat())
        matrix.append(row_values)
    return matrix


def _create_benchmark_tab(owner, col_count, case_label):
    sheetbook = Sheetbook.objects.create(
        owner=owner,
        title=f"[bench] {case_label}",
        academic_year=2026,
    )
    tab = SheetTab.objects.create(
        sheetbook=sheetbook,
        name="벤치마크",
        tab_type=SheetTab.TYPE_GRID,
        sort_order=1,
    )
    column_types = [
        SheetColumn.TYPE_TEXT,
        SheetColumn.TYPE_NUMBER,
        SheetColumn.TYPE_DATE,
    ]
    for idx in range(col_count):
        col_type = column_types[idx % len(column_types)]
        SheetColumn.objects.create(
            tab=tab,
            key=f"c_{idx + 1}",
            label=f"열{idx + 1}",
            column_type=col_type,
            sort_order=idx + 1,
        )
    return sheetbook, tab


class Command(BaseCommand):
    help = "Benchmark sheetbook grid paste performance for target cell counts and batch sizes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--cells",
            default="500,1000",
            help="쉼표 구분 셀 개수. 예: 500,1000",
        )
        parser.add_argument(
            "--cols",
            type=int,
            default=10,
            help="테스트 열 개수(행 수는 cells/cols로 계산).",
        )
        parser.add_argument(
            "--runs",
            type=int,
            default=3,
            help="각 케이스 반복 횟수.",
        )
        parser.add_argument(
            "--batch-sizes",
            default="200,400,800",
            help="쉼표 구분 batch_size 후보. 예: 200,400,800",
        )
        parser.add_argument(
            "--keep-data",
            action="store_true",
            help="벤치마크용 생성 데이터를 삭제하지 않습니다.",
        )
        parser.add_argument(
            "--read-rows",
            type=int,
            default=1000,
            help="조회 벤치마크용 행 개수(limit). 기본 1000",
        )
        parser.add_argument(
            "--skip-read",
            action="store_true",
            help="1,000행 조회 벤치마크를 건너뜁니다.",
        )

    def handle(self, *args, **options):
        target_cells = _parse_int_list(options.get("cells"), "--cells")
        batch_sizes = _parse_int_list(options.get("batch_sizes"), "--batch-sizes")
        cols = int(options.get("cols") or 0)
        runs = int(options.get("runs") or 0)
        keep_data = bool(options.get("keep_data"))
        read_rows = int(options.get("read_rows") or 0)
        skip_read = bool(options.get("skip_read"))

        if cols < 1:
            raise CommandError("--cols 값은 1 이상이어야 합니다.")
        if runs < 1:
            raise CommandError("--runs 값은 1 이상이어야 합니다.")
        if any(size < 1 for size in batch_sizes):
            raise CommandError("--batch-sizes 값은 1 이상의 정수여야 합니다.")
        if read_rows < 1:
            raise CommandError("--read-rows 값은 1 이상이어야 합니다.")

        user_model = get_user_model()
        username = f"sheetbook_bench_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
        bench_user = user_model.objects.create_user(
            username=username,
            password="unused",
            email=f"{username}@example.com",
        )
        try:
            self.stdout.write(self.style.SUCCESS("[sheetbook] grid paste benchmark start"))
            self.stdout.write(f"- target cells: {target_cells}")
            self.stdout.write(f"- columns: {cols}")
            self.stdout.write(f"- runs: {runs}")
            self.stdout.write(f"- batch sizes: {batch_sizes}")
            self.stdout.write(f"- read rows: {read_rows}")

            summary_rows = []
            for target in target_cells:
                if target < 1:
                    raise CommandError("--cells 값은 1 이상의 정수여야 합니다.")

                row_count = max(1, math.ceil(target / cols))
                matrix = _build_matrix(row_count, cols)
                actual_cells = row_count * cols
                self.stdout.write("")
                self.stdout.write(f"[case] target={target} cells -> rows={row_count}, cols={cols}, actual={actual_cells}")

                for batch_size in batch_sizes:
                    create_times = []
                    update_times = []
                    for run_idx in range(1, runs + 1):
                        case_label = f"{target}_cells_b{batch_size}_r{run_idx}"
                        sheetbook, tab = _create_benchmark_tab(bench_user, cols, case_label)
                        try:
                            start = time.perf_counter()
                            create_result = _paste_matrix_into_grid_tab(
                                tab=tab,
                                matrix=matrix,
                                start_row_index=0,
                                start_col_index=0,
                                actor=bench_user,
                                batch_size=batch_size,
                            )
                            create_elapsed = (time.perf_counter() - start) * 1000.0

                            start = time.perf_counter()
                            update_result = _paste_matrix_into_grid_tab(
                                tab=tab,
                                matrix=matrix,
                                start_row_index=0,
                                start_col_index=0,
                                actor=bench_user,
                                batch_size=batch_size,
                            )
                            update_elapsed = (time.perf_counter() - start) * 1000.0
                        finally:
                            if not keep_data:
                                sheetbook.delete()

                        create_times.append(create_elapsed)
                        update_times.append(update_elapsed)

                        if run_idx == 1:
                            self.stdout.write(
                                "  "
                                f"batch={batch_size} sample(create rows_added={create_result['rows_added']}, "
                                f"updated={create_result['updated']}; update rows_added={update_result['rows_added']}, "
                                f"updated={update_result['updated']})"
                            )

                    create_avg = statistics.mean(create_times)
                    update_avg = statistics.mean(update_times)
                    total_avg = create_avg + update_avg
                    summary_rows.append((target, batch_size, create_avg, update_avg, total_avg))
                    self.stdout.write(
                        "  "
                        f"batch={batch_size} avg: create={create_avg:.1f}ms, "
                        f"update={update_avg:.1f}ms, total={total_avg:.1f}ms"
                    )

            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("[sheetbook] benchmark summary"))
            for target in target_cells:
                case_rows = [row for row in summary_rows if row[0] == target]
                if not case_rows:
                    continue
                best = min(case_rows, key=lambda item: item[4])
                self.stdout.write(
                    f"- target={target}: best batch={best[1]} "
                    f"(create={best[2]:.1f}ms, update={best[3]:.1f}ms, total={best[4]:.1f}ms)"
                )

            if skip_read:
                return

            self.stdout.write("")
            self.stdout.write("[read] grid_data payload benchmark")
            read_batch_size = min(batch_sizes)
            read_matrix = _build_matrix(read_rows, cols)
            read_times = []
            for run_idx in range(1, runs + 1):
                case_label = f"read_rows_{read_rows}_r{run_idx}"
                sheetbook, tab = _create_benchmark_tab(bench_user, cols, case_label)
                try:
                    _paste_matrix_into_grid_tab(
                        tab=tab,
                        matrix=read_matrix,
                        start_row_index=0,
                        start_col_index=0,
                        actor=bench_user,
                        batch_size=read_batch_size,
                    )
                    start = time.perf_counter()
                    payload = _build_grid_data_payload(tab=tab, offset=0, limit=read_rows)
                    read_elapsed = (time.perf_counter() - start) * 1000.0
                finally:
                    if not keep_data:
                        sheetbook.delete()
                read_times.append(read_elapsed)
                if run_idx == 1:
                    self.stdout.write(
                        "  "
                        f"sample rows={payload['count']}, columns={len(payload['columns'])}, total_rows={payload['total_rows']}"
                    )

            read_avg = statistics.mean(read_times)
            self.stdout.write(f"  avg read(limit={read_rows}): {read_avg:.1f}ms")
        finally:
            if not keep_data:
                bench_user.delete()
