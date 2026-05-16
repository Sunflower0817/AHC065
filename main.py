import sys
import time

def make_horizontal_belt(row_pair: int, n: int) -> list[tuple[int, int]]:
    """Create a 2-row belt at the given row_pair level (0-indexed pair).
    
    row_pair = 0 -> rows 0-1
    row_pair = 1 -> rows 2-3
    """
    cells: list[tuple[int, int]] = []
    top_row = row_pair * 2
    bottom_row = row_pair * 2 + 1
    
    if bottom_row >= n:
        return cells
    
    # Top row: left to right
    for j in range(n):
        cells.append((top_row, j))
    # Bottom row: right to left
    for j in range(n - 1, -1, -1):
        cells.append((bottom_row, j))
    
    return cells


def make_central_belt(n: int) -> list[tuple[int, int]]:
    c = n // 2
    cells: list[tuple[int, int]] = []

    cells.append((0, c))
    for i in range(1, n):
        cells.append((i, c))
    cells.append((n - 1, c + 1))
    for i in range(n - 2, -1, -1):
        cells.append((i, c + 1))
    return cells


def cycle_distance(src: int, dst: int, length: int) -> tuple[int, int]:
    forward = (dst - src) % length
    backward = (src - dst) % length
    if forward <= backward:
        return forward, 1
    return backward, -1


def rotate_belt(grid: list[list[int]], belt: list[tuple[int, int]], d: int, pos: dict[int, tuple[int, int]]) -> None:
    length = len(belt)
    old_values = [grid[i][j] for i, j in belt]
    for idx, (i, j) in enumerate(belt):
        new_val = old_values[(idx - d) % length]
        grid[i][j] = new_val
        if new_val >= 0:
            pos[new_val] = (i, j)


def maybe_extract(grid: list[list[int]], exit_pos: tuple[int, int], pos: dict[int, tuple[int, int]], next_target: int) -> int:
    i, j = exit_pos
    while next_target in pos and grid[i][j] == next_target:
        pos.pop(next_target, None)
        grid[i][j] = -1
        next_target += 1
    return next_target


def find_best_rotation_to_targets(current_idx: int, belt: list[tuple[int, int]], target_cells: list[tuple[int, int]], belt_index: dict[tuple[int, int], int]) -> tuple[int, int, tuple[int, int]] | None:
    best: tuple[int, int, tuple[int, int]] | None = None
    for cell in target_cells:
        if cell not in belt_index:
            continue
        idx = belt_index[cell]
        steps, direction = cycle_distance(current_idx, idx, len(belt))
        if best is None or steps < best[0] or (steps == best[0] and direction == 1 and best[1] == -1):
            best = (steps, direction, cell)
    return best


def should_gather_next_to_center(target_cell: tuple[int, int], next_cell: tuple[int, int]) -> bool:
    target_row = target_cell[0]
    next_row = next_cell[0]
    if target_row % 2 == 0:
        return next_row >= target_row + 2
    return next_row > target_row


def gather_value_to_column(value: int, target_col: int, grid: list[list[int]], belts: list[list[tuple[int, int]]], belt_index: list[dict[tuple[int, int], int]], cell_belts: dict[tuple[int, int], list[int]], pos: dict[int, tuple[int, int]], operations: list[tuple[int, int]], central_id: int, exit_pos: tuple[int, int], next_target: int, preserve_center_cell: tuple[int, int] | None = None) -> tuple[bool, int]:
    cell = pos[value]
    if central_id in cell_belts[cell]:
        if cell[1] == target_col:
            return False, next_target
        if preserve_center_cell is not None and preserve_center_cell != cell:
            return False, next_target
        central_belt = belts[central_id]
        current_idx = belt_index[central_id][cell]
        target_cells = [c for c in central_belt if c[1] == target_col]
        plan = find_best_rotation_to_targets(current_idx, central_belt, target_cells, belt_index[central_id])
        if plan is None:
            return False, next_target
        steps, direction, _ = plan
        for _ in range(steps):
            rotate_belt(grid, central_belt, direction, pos)
            operations.append((central_id, direction))
            next_target = maybe_extract(grid, exit_pos, pos, next_target)
        return True, next_target

    belt_id = cell_belts[cell][0]
    if belt_id == central_id:
        return False, next_target

    horiz_belt = belts[belt_id]
    current_idx = belt_index[belt_id][cell]
    top_row = belt_id * 2
    bottom_row = belt_id * 2 + 1
    target_cells: list[tuple[int, int]] = []
    if top_row < len(grid):
        target_cells.append((top_row, target_col))
    if bottom_row < len(grid):
        target_cells.append((bottom_row, target_col))
    plan = find_best_rotation_to_targets(current_idx, horiz_belt, target_cells, belt_index[belt_id])
    if plan is None:
        return False, next_target
    steps, direction, _ = plan
    for _ in range(steps):
        rotate_belt(grid, horiz_belt, direction, pos)
        operations.append((belt_id, direction))
        next_target = maybe_extract(grid, exit_pos, pos, next_target)
    return True, next_target


def gather_following_values_to_center(start_value: int, target_col: int, anchor_cell: tuple[int, int], grid: list[list[int]], belts: list[list[tuple[int, int]]], belt_index: list[dict[tuple[int, int], int]], cell_belts: dict[tuple[int, int], list[int]], pos: dict[int, tuple[int, int]], operations: list[tuple[int, int]], central_id: int, exit_pos: tuple[int, int], next_target: int) -> tuple[bool, int]:
    gathered_any = False
    value = start_value
    last_center_cell = anchor_cell
    while value in pos and should_gather_next_to_center(last_center_cell, pos[value]):
        if pos[value][1] == target_col:
            last_center_cell = pos[value]
            value += 1
            continue
        gathered, next_target = gather_value_to_column(value, target_col, grid, belts, belt_index, cell_belts, pos, operations, central_id, exit_pos, next_target, preserve_center_cell=last_center_cell)
        if not gathered or value not in pos or pos[value][1] != target_col:
            break
        gathered_any = True
        last_center_cell = pos[value]
        value += 1
    return gathered_any, next_target


def main() -> None:
    data = sys.stdin.read().strip().split()
    if not data:
        return
    it = iter(data)
    n = int(next(it))
    grid = [[int(next(it)) for _ in range(n)] for _ in range(n)]

    belts: list[list[tuple[int, int]]] = []
    for row_pair in range(n // 2):
        belt = make_horizontal_belt(row_pair, n)
        if len(belt) >= 2:
            belts.append(belt)
    central_belt = make_central_belt(n)
    belts.append(central_belt)
    central_id = len(belts) - 1

    cell_belts: dict[tuple[int, int], list[int]] = {}
    belt_index: list[dict[tuple[int, int], int]] = []
    for bid, belt in enumerate(belts):
        index_map: dict[tuple[int, int], int] = {}
        for idx, cell in enumerate(belt):
            cell_belts.setdefault(cell, []).append(bid)
            index_map[cell] = idx
        belt_index.append(index_map)

    for cell, ids in cell_belts.items():
        if len(ids) > 2:
            raise AssertionError(f"Cell {cell} belongs to more than 2 belts: {ids}")

    pos: dict[int, tuple[int, int]] = {}
    for i in range(n):
        for j in range(n):
            pos[grid[i][j]] = (i, j)

    exit_pos = (0, n // 2)
    operations: list[tuple[int, int]] = []
    next_target = 0
    next_target = maybe_extract(grid, exit_pos, pos, next_target)

    for target in range(n * n):
        if target < next_target:
            continue
        while next_target == target:
            if target not in pos:
                break
            cell = pos[target]
            if cell == exit_pos:
                next_target = maybe_extract(grid, exit_pos, pos, next_target)
                break

            belts_at_cell = cell_belts.get(cell, [])
            if central_id in belts_at_cell:
                current_idx = belt_index[central_id][cell]
                a_col = cell[1]
                gathered, next_target = gather_following_values_to_center(target + 1, a_col, cell, grid, belts, belt_index, cell_belts, pos, operations, central_id, exit_pos, next_target)
                if gathered and target + 1 in pos and pos[target + 1][1] != a_col:
                    continue
                exit_idx = belt_index[central_id][exit_pos]
                steps, direction = cycle_distance(current_idx, exit_idx, len(central_belt))
                for _ in range(steps):
                    rotate_belt(grid, central_belt, direction, pos)
                    operations.append((central_id, direction))
                    next_target = maybe_extract(grid, exit_pos, pos, next_target)
                    if next_target != target:
                        break
                    cell = pos[target]
                    gathered, next_target = gather_following_values_to_center(target + 1, cell[1], cell, grid, belts, belt_index, cell_belts, pos, operations, central_id, exit_pos, next_target)
                    if gathered:
                        break
                continue

            # Target is on a horizontal belt
            horiz_id = belts_at_cell[0]
            horiz = belts[horiz_id]
            current_idx = belt_index[horiz_id][cell]
            
            # Find best intersection point to central belt
            best_plan = None
            c = n // 2
            
            # Candidates: the two columns (c and c+1) in both rows of this horizontal belt
            row_pair = horiz_id
            top_row = row_pair * 2
            bottom_row = row_pair * 2 + 1
            
            candidates = [
                (top_row, c),
                (top_row, c + 1),
                (bottom_row, c),
                (bottom_row, c + 1),
            ]
            
            for candidate in candidates:
                if candidate not in belt_index[horiz_id]:
                    continue
                horiz_target_idx = belt_index[horiz_id][candidate]
                horiz_steps, horiz_dir = cycle_distance(current_idx, horiz_target_idx, len(horiz))
                
                if candidate not in belt_index[central_id]:
                    continue
                central_target_idx = belt_index[central_id][candidate]
                exit_idx = belt_index[central_id][exit_pos]
                central_steps, central_dir = cycle_distance(central_target_idx, exit_idx, len(central_belt))
                cost = horiz_steps + central_steps
                plan = (cost, horiz_steps, candidate, horiz_dir, central_dir)
                if best_plan is None or plan < best_plan:
                    best_plan = plan

            if best_plan is None:
                break
            _, horiz_steps, candidate_cell, horiz_dir, _ = best_plan
            if horiz_steps > 0:
                for _ in range(horiz_steps):
                    rotate_belt(grid, horiz, horiz_dir, pos)
                    operations.append((horiz_id, horiz_dir))
                    next_target = maybe_extract(grid, exit_pos, pos, next_target)
                if target < next_target:
                    break

            if candidate_cell == exit_pos:
                next_target = maybe_extract(grid, exit_pos, pos, next_target)
                break

            current_cell = pos.get(target)
            if current_cell is None:
                break
            if current_cell not in belt_index[central_id]:
                break
            gathered, next_target = gather_following_values_to_center(target + 1, current_cell[1], current_cell, grid, belts, belt_index, cell_belts, pos, operations, central_id, exit_pos, next_target)
            if gathered:
                current_cell = pos.get(target)
                if current_cell is None or current_cell not in belt_index[central_id]:
                    break
            current_idx = belt_index[central_id][current_cell]
            exit_idx = belt_index[central_id][exit_pos]
            central_steps, central_dir = cycle_distance(current_idx, exit_idx, len(central_belt))
            for _ in range(central_steps):
                rotate_belt(grid, central_belt, central_dir, pos)
                operations.append((central_id, central_dir))
                next_target = maybe_extract(grid, exit_pos, pos, next_target)

    print(len(belts))
    for belt in belts:
        line = [str(len(belt))]
        for i, j in belt:
            line.append(str(i))
            line.append(str(j))
        print(" ".join(line))
    print(len(operations))
    for belt_id, direction in operations:
        print(belt_id, direction)


if __name__ == "__main__":
    st = time.time()
    main()
    en = time.time()
    print(f"Execution time: {en - st:.2f} seconds", file=sys.stderr)
