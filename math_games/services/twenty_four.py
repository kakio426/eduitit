from __future__ import annotations

import ast
import random
import re
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction


TARGET_VALUE = Fraction(24, 1)
DEFAULT_NUMBER_MIN = 1
DEFAULT_NUMBER_MAX = 9


class ExpressionError(ValueError):
    pass


@dataclass(frozen=True)
class ExpressionResult:
    value: Fraction
    numbers: tuple[int, ...]


def solve_numbers(numbers: list[int] | tuple[int, ...]) -> str | None:
    items = [(Fraction(int(number), 1), str(int(number))) for number in numbers]
    return _search_solution(items, set())


def generate_puzzle(*, rng: random.Random | None = None, attempts: int = 300) -> dict:
    rng = rng or random.Random()
    for _ in range(attempts):
        numbers = [rng.randint(DEFAULT_NUMBER_MIN, DEFAULT_NUMBER_MAX) for _ in range(4)]
        solution = solve_numbers(numbers)
        if solution:
            return {"numbers": numbers, "solution": solution}
    numbers = [3, 3, 8, 8]
    return {"numbers": numbers, "solution": solve_numbers(numbers) or "8/(3-8/3)"}


def validate_answer(expression: str, numbers: list[int] | tuple[int, ...]) -> dict:
    expression = (expression or "").strip()
    if not expression:
        raise ExpressionError("식을 입력하세요.")
    if len(expression) > 120:
        raise ExpressionError("식이 너무 깁니다.")

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ExpressionError("식을 다시 볼까요?") from exc

    result = _eval_node(tree.body)
    expected = Counter(int(number) for number in numbers)
    used = Counter(result.numbers)
    if used != expected:
        raise ExpressionError("숫자 4개만 한 번씩!")

    return {
        "value": result.value,
        "is_correct": result.value == TARGET_VALUE,
        "used_numbers": list(result.numbers),
    }


def hint_for_solution(solution: str, hint_index: int) -> str:
    steps = _solution_steps(solution)
    if hint_index <= 1:
        if steps:
            return f"먼저 {steps[0]} 보기"
        return "두 수를 먼저 묶기"
    if hint_index == 2:
        if len(steps) > 1:
            return f"다음은 {steps[1]} 보기"
        return "6, 8, 12 만들기"
    return f"예: {solution}"


def _solution_steps(solution: str) -> list[str]:
    return re.findall(r"\d+\s*[+\-*/]\s*\d+", solution or "")


def _search_solution(items: list[tuple[Fraction, str]], seen: set[tuple[Fraction, ...]]) -> str | None:
    values_key = tuple(sorted(value for value, _expr in items))
    if values_key in seen:
        return None
    seen.add(values_key)

    if len(items) == 1:
        value, expr = items[0]
        return expr if value == TARGET_VALUE else None

    for first_index in range(len(items)):
        for second_index in range(first_index + 1, len(items)):
            first_value, first_expr = items[first_index]
            second_value, second_expr = items[second_index]
            rest = [item for idx, item in enumerate(items) if idx not in {first_index, second_index}]

            candidates = [
                (first_value + second_value, f"({first_expr}+{second_expr})"),
                (first_value - second_value, f"({first_expr}-{second_expr})"),
                (second_value - first_value, f"({second_expr}-{first_expr})"),
                (first_value * second_value, f"({first_expr}*{second_expr})"),
            ]
            if second_value != 0:
                candidates.append((first_value / second_value, f"({first_expr}/{second_expr})"))
            if first_value != 0:
                candidates.append((second_value / first_value, f"({second_expr}/{first_expr})"))

            for value, expr in candidates:
                solution = _search_solution([*rest, (value, expr)], seen)
                if solution:
                    return solution
    return None


def _eval_node(node) -> ExpressionResult:
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
        if not (DEFAULT_NUMBER_MIN <= node.value <= DEFAULT_NUMBER_MAX):
            raise ExpressionError("카드 숫자만 써요!")
        return ExpressionResult(Fraction(node.value, 1), (int(node.value),))

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        operand = _eval_node(node.operand)
        if isinstance(node.op, ast.USub):
            return ExpressionResult(-operand.value, operand.numbers)
        return operand

    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        numbers = (*left.numbers, *right.numbers)
        if isinstance(node.op, ast.Add):
            return ExpressionResult(left.value + right.value, numbers)
        if isinstance(node.op, ast.Sub):
            return ExpressionResult(left.value - right.value, numbers)
        if isinstance(node.op, ast.Mult):
            return ExpressionResult(left.value * right.value, numbers)
        if right.value == 0:
            raise ExpressionError("0으로 나눌 수 없습니다.")
        return ExpressionResult(left.value / right.value, numbers)

    raise ExpressionError("사칙연산만 써요!")
