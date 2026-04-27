import random


GRID_SIZE = 4
WIN_TILE = 2048
VALID_DIRECTIONS = {"up", "down", "left", "right"}


class InvalidDirection(ValueError):
    pass


def empty_grid():
    return [[0 for _column in range(GRID_SIZE)] for _row in range(GRID_SIZE)]


def normalize_grid(raw_grid):
    grid = []
    rows = list(raw_grid or [])
    for row_index in range(GRID_SIZE):
        raw_row = list(rows[row_index] if row_index < len(rows) else [])
        row = []
        for column_index in range(GRID_SIZE):
            try:
                value = int(raw_row[column_index]) if column_index < len(raw_row) else 0
            except (TypeError, ValueError):
                value = 0
            row.append(value if value > 0 else 0)
        grid.append(row)
    return grid


def empty_cells(grid):
    return [
        {"row": row_index, "col": column_index}
        for row_index, row in enumerate(grid)
        for column_index, value in enumerate(row)
        if value == 0
    ]


def spawn_tile(grid, rng=None):
    cells = empty_cells(grid)
    if not cells:
        return None
    random_source = rng or random.Random()
    cell = random_source.choice(cells)
    value = 4 if random_source.random() < 0.1 else 2
    grid[cell["row"]][cell["col"]] = value
    return {**cell, "value": value}


def slide_row_left(row):
    values = [value for value in row if value]
    merged = []
    gained = 0
    index = 0
    while index < len(values):
        value = values[index]
        if index + 1 < len(values) and values[index + 1] == value:
            value *= 2
            gained += value
            index += 2
        else:
            index += 1
        merged.append(value)
    merged.extend([0] * (GRID_SIZE - len(merged)))
    return merged, gained


def transpose(grid):
    return [list(row) for row in zip(*grid)]


def move_grid(raw_grid, direction):
    if direction not in VALID_DIRECTIONS:
        raise InvalidDirection("방향 확인")

    grid = normalize_grid(raw_grid)
    gained = 0

    if direction == "left":
        moved_grid = []
        for row in grid:
            next_row, row_gained = slide_row_left(row)
            moved_grid.append(next_row)
            gained += row_gained
    elif direction == "right":
        moved_grid = []
        for row in grid:
            next_row, row_gained = slide_row_left(list(reversed(row)))
            moved_grid.append(list(reversed(next_row)))
            gained += row_gained
    elif direction == "up":
        columns = transpose(grid)
        moved_columns = []
        for column in columns:
            next_column, column_gained = slide_row_left(column)
            moved_columns.append(next_column)
            gained += column_gained
        moved_grid = transpose(moved_columns)
    else:
        columns = transpose(grid)
        moved_columns = []
        for column in columns:
            next_column, column_gained = slide_row_left(list(reversed(column)))
            moved_columns.append(list(reversed(next_column)))
            gained += column_gained
        moved_grid = transpose(moved_columns)

    return {
        "grid": moved_grid,
        "gained": gained,
        "moved": moved_grid != grid,
    }


def has_winning_tile(grid):
    return any(value >= WIN_TILE for row in grid for value in row)


def available_moves(grid):
    normalized = normalize_grid(grid)
    return [
        direction
        for direction in ["up", "down", "left", "right"]
        if move_grid(normalized, direction)["moved"]
    ]


def is_game_over(grid):
    return not available_moves(grid)


def public_state(state):
    grid = normalize_grid((state or {}).get("grid"))
    moves = available_moves(grid)
    score = int((state or {}).get("score") or 0)
    move_count = int((state or {}).get("moves") or 0)
    won = bool((state or {}).get("won")) or has_winning_tile(grid)
    game_over = bool((state or {}).get("game_over")) or not moves
    return {
        "grid": grid,
        "score": score,
        "moves": move_count,
        "won": won,
        "game_over": game_over,
        "spawned": list((state or {}).get("spawned") or []),
        "gained": int((state or {}).get("gained") or 0),
        "moved": bool((state or {}).get("moved")),
        "available_moves": moves,
    }


def initial_state_json(rng=None):
    grid = empty_grid()
    random_source = rng or random.Random()
    spawned = []
    first = spawn_tile(grid, random_source)
    if first:
        spawned.append(first)
    second = spawn_tile(grid, random_source)
    if second:
        spawned.append(second)
    return {
        "grid": grid,
        "score": 0,
        "moves": 0,
        "won": False,
        "game_over": False,
        "spawned": spawned,
        "gained": 0,
        "moved": False,
        "available_moves": available_moves(grid),
    }


def apply_move(state, direction, rng=None):
    normalized_direction = str(direction or "").strip().lower()
    if normalized_direction not in VALID_DIRECTIONS:
        raise InvalidDirection("방향 확인")

    current = public_state(state or {})
    move = move_grid(current["grid"], normalized_direction)
    next_grid = move["grid"]
    spawned = []
    score = current["score"]
    move_count = current["moves"]

    if move["moved"]:
        score += move["gained"]
        move_count += 1
        tile = spawn_tile(next_grid, rng or random.Random())
        if tile:
            spawned.append(tile)

    won = current["won"] or has_winning_tile(next_grid)
    moves = available_moves(next_grid)
    game_over = not moves

    return {
        "grid": next_grid,
        "score": score,
        "moves": move_count,
        "won": won,
        "game_over": game_over,
        "spawned": spawned,
        "gained": move["gained"] if move["moved"] else 0,
        "moved": move["moved"],
        "available_moves": moves,
    }
