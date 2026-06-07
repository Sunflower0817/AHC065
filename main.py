import sys
import time
from dataclasses import dataclass


BEAM_WIDTH = 16
LOOKAHEAD_BOXES = 6
MAX_OPERATIONS = 100000
SELECT_OVERALL = 8
SELECT_ORDER = 4
SELECT_READY = 2
SELECT_ROW = 2
SELECT_SHORT = 0


@dataclass
class BeamState:
    grid: list[list[int]]
    pos: dict[int, tuple[int, int]]
    operations: list[tuple[int, int]]
    next_target: int
    parent: "BeamState | None" = None
    op_count: int = 0
    sort_key: tuple[int, int, int, int, int, bool] | None = None

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


def steps_with_fixed_direction(src: int, dst: int, length: int, direction: int) -> int:
    if direction == 1:
        return (dst - src) % length
    return (src - dst) % length


def rotate_belt(grid: list[list[int]], belt: list[tuple[int, int]], d: int, pos: dict[int, tuple[int, int]]) -> None:
    length = len(belt)
    if d == 1:
        last_i, last_j = belt[-1]
        carried = grid[last_i][last_j]
        for idx in range(length - 1, 0, -1):
            src_i, src_j = belt[idx - 1]
            dst_i, dst_j = belt[idx]
            value = grid[src_i][src_j]
            grid[dst_i][dst_j] = value
            if value >= 0:
                pos[value] = (dst_i, dst_j)
        first_i, first_j = belt[0]
        grid[first_i][first_j] = carried
        if carried >= 0:
            pos[carried] = (first_i, first_j)
        return

    first_i, first_j = belt[0]
    carried = grid[first_i][first_j]
    for idx in range(length - 1):
        src_i, src_j = belt[idx + 1]
        dst_i, dst_j = belt[idx]
        value = grid[src_i][src_j]
        grid[dst_i][dst_j] = value
        if value >= 0:
            pos[value] = (dst_i, dst_j)
    last_i, last_j = belt[-1]
    grid[last_i][last_j] = carried
    if carried >= 0:
        pos[carried] = (last_i, last_j)


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


def find_best_rotation_to_column(
    current_idx: int,
    target_col: int,
    belt: list[tuple[int, int]],
    direction: int,
    preserve_idx: int | None = None,
    preserve_col: int | None = None,
) -> tuple[int, int] | None:
    best: tuple[int, int] | None = None
    length = len(belt)
    for steps in range(length):
        next_idx = (current_idx + direction * steps) % length
        if belt[next_idx][1] != target_col:
            continue
        if preserve_idx is not None and preserve_col is not None:
            preserved_next_idx = (preserve_idx + direction * steps) % length
            if belt[preserved_next_idx][1] != preserve_col:
                continue
        plan = (steps, direction)
        if best is None or plan[0] < best[0]:
            best = plan
    return best


def find_horizontal_belt_id(cell: tuple[int, int], cell_belts: dict[tuple[int, int], list[int]], central_id: int) -> int | None:
    for belt_id in cell_belts.get(cell, []):
        if belt_id != central_id:
            return belt_id
    return None


def should_gather_next_to_center(target_cell: tuple[int, int], next_cell: tuple[int, int]) -> bool:
    target_row = target_cell[0]
    next_row = next_cell[0]
    if target_row % 2 == 0:
        return next_row >= target_row + 2
    return next_row > target_row


def gather_value_to_column(value: int, target_col: int, grid: list[list[int]], belts: list[list[tuple[int, int]]], belt_index: list[dict[tuple[int, int], int]], cell_belts: dict[tuple[int, int], list[int]], pos: dict[int, tuple[int, int]], operations: list[tuple[int, int]], central_id: int, central_direction: int, exit_pos: tuple[int, int], next_target: int, preserve_center_cell: tuple[int, int] | None = None) -> tuple[bool, int]:
    cell = pos[value]
    if cell[1] == target_col:
        return False, next_target

    horiz_id = find_horizontal_belt_id(cell, cell_belts, central_id)
    if horiz_id is not None:
        preserve_horiz_id = None
        if preserve_center_cell is not None:
            preserve_horiz_id = find_horizontal_belt_id(preserve_center_cell, cell_belts, central_id)
        if preserve_horiz_id != horiz_id:
            horiz_belt = belts[horiz_id]
            current_idx = belt_index[horiz_id][cell]
            top_row = horiz_id * 2
            bottom_row = horiz_id * 2 + 1
            target_cells: list[tuple[int, int]] = []
            if top_row < len(grid):
                target_cells.append((top_row, target_col))
            if bottom_row < len(grid):
                target_cells.append((bottom_row, target_col))
            plan = find_best_rotation_to_targets(current_idx, horiz_belt, target_cells, belt_index[horiz_id])
            if plan is not None:
                steps, direction, _ = plan
                for _ in range(steps):
                    rotate_belt(grid, horiz_belt, direction, pos)
                    operations.append((horiz_id, direction))
                    next_target = maybe_extract(grid, exit_pos, pos, next_target)
                return True, next_target

    if central_id in cell_belts[cell]:
        central_belt = belts[central_id]
        current_idx = belt_index[central_id][cell]
        preserve_idx = None
        preserve_col = None
        if preserve_center_cell is not None and preserve_center_cell != cell:
            preserve_idx = belt_index[central_id][preserve_center_cell]
            preserve_col = preserve_center_cell[1]
        plan = find_best_rotation_to_column(current_idx, target_col, central_belt, central_direction, preserve_idx, preserve_col)
        if plan is None:
            return False, next_target
        steps, direction = plan
        for _ in range(steps):
            rotate_belt(grid, central_belt, direction, pos)
            operations.append((central_id, direction))
            next_target = maybe_extract(grid, exit_pos, pos, next_target)
        return True, next_target

    return False, next_target


def gather_value_to_center_cell(value: int, target_cell: tuple[int, int], grid: list[list[int]], belts: list[list[tuple[int, int]]], belt_index: list[dict[tuple[int, int], int]], cell_belts: dict[tuple[int, int], list[int]], pos: dict[int, tuple[int, int]], operations: list[tuple[int, int]], central_id: int, exit_pos: tuple[int, int], next_target: int, protected_cells: tuple[tuple[int, int], ...] = ()) -> tuple[bool, int]:
    cell = pos[value]
    if cell == target_cell:
        return False, next_target
    horiz_id = find_horizontal_belt_id(cell, cell_belts, central_id)
    if horiz_id is None or target_cell not in belt_index[horiz_id]:
        return False, next_target
    for protected_cell in protected_cells:
        if find_horizontal_belt_id(protected_cell, cell_belts, central_id) == horiz_id:
            return False, next_target
    current_idx = belt_index[horiz_id][cell]
    target_idx = belt_index[horiz_id][target_cell]
    steps, direction = cycle_distance(current_idx, target_idx, len(belts[horiz_id]))
    for _ in range(steps):
        rotate_belt(grid, belts[horiz_id], direction, pos)
        operations.append((horiz_id, direction))
        next_target = maybe_extract(grid, exit_pos, pos, next_target)
    return True, next_target


def gather_following_values_to_center(start_value: int, target_col: int, anchor_cell: tuple[int, int], grid: list[list[int]], belts: list[list[tuple[int, int]]], belt_index: list[dict[tuple[int, int], int]], cell_belts: dict[tuple[int, int], list[int]], pos: dict[int, tuple[int, int]], operations: list[tuple[int, int]], central_id: int, central_direction: int, exit_pos: tuple[int, int], next_target: int) -> tuple[bool, int]:
    if anchor_cell[1] != target_col:
        return False, next_target
    gathered_any = False
    value = start_value
    last_center_cell = anchor_cell
    while value in pos and should_gather_next_to_center(last_center_cell, pos[value]):
        if pos[value][1] == target_col:
            last_center_cell = pos[value]
            value += 1
            continue
        gathered, next_target = gather_value_to_column(value, target_col, grid, belts, belt_index, cell_belts, pos, operations, central_id, central_direction, exit_pos, next_target, preserve_center_cell=last_center_cell)
        if not gathered or value not in pos or pos[value][1] != target_col:
            break
        gathered_any = True
        last_center_cell = pos[value]
        value += 1
    return gathered_any, next_target


def clone_state(state: BeamState) -> BeamState:
    return BeamState(
        [row[:] for row in state.grid],
        dict(state.pos),
        [],
        state.next_target,
        state,
        total_operations(state),
    )


def total_operations(state: BeamState) -> int:
    return state.op_count + len(state.operations)


def restore_operations(state: BeamState) -> list[tuple[int, int]]:
    chunks: list[list[tuple[int, int]]] = []
    current: BeamState | None = state
    while current is not None:
        chunks.append(current.operations)
        current = current.parent
    result: list[tuple[int, int]] = []
    for chunk in reversed(chunks):
        result.extend(chunk)
    return result


def ready_count(next_target: int, pos: dict[int, tuple[int, int]], center_col: int, total: int, limit: int = LOOKAHEAD_BOXES) -> int:
    count = 0
    for value in range(next_target, min(total, next_target + limit)):
        if value not in pos or pos[value][1] != center_col:
            break
        count += 1
    return count


def central_order_score(next_target: int, pos: dict[int, tuple[int, int]], belt_index: dict[tuple[int, int], int], center_col: int, total: int, central_direction: int, limit: int = LOOKAHEAD_BOXES) -> int:
    score = 0
    previous_steps = -1
    exit_idx = belt_index[(0, center_col)]
    for value in range(next_target, min(total, next_target + limit)):
        cell = pos.get(value)
        if cell is None or cell[1] != center_col:
            break
        steps = steps_with_fixed_direction(belt_index[cell], exit_idx, len(belt_index), central_direction)
        if previous_steps <= steps:
            score += limit - (value - next_target)
            previous_steps = steps
        else:
            break
    return score


def state_sort_key(state: BeamState, n: int, belts: list[list[tuple[int, int]]], belt_index: list[dict[tuple[int, int], int]], cell_belts: dict[tuple[int, int], list[int]], central_id: int, center_col: int, central_direction: int) -> tuple[int, int, int, int, int, bool]:
    if state.sort_key is not None:
        return state.sort_key
    total = n * n
    operation_count = total_operations(state)
    state.sort_key = (
        state.next_target,
        -operation_count,
        central_order_score(state.next_target, state.pos, belt_index[central_id], center_col, total, central_direction),
        ready_count(state.next_target, state.pos, center_col, total),
        -operation_count,
        state.next_target >= total,
    )
    return state.sort_key


def prepare_values_to_center(state: BeamState, chain_limit: int, n: int, belts: list[list[tuple[int, int]]], belt_index: list[dict[tuple[int, int], int]], cell_belts: dict[tuple[int, int], list[int]], central_id: int, central_direction: int, center_col: int, exit_pos: tuple[int, int]) -> bool:
    total = n * n
    first_value = state.next_target
    last_center_cell: tuple[int, int] | None = None
    prepared = 0
    value = first_value
    while value < total and prepared < chain_limit:
        if value < state.next_target:
            value = state.next_target
            continue
        if value not in state.pos:
            value += 1
            continue
        cell = state.pos[value]
        if prepared > 0 and last_center_cell is not None and not should_gather_next_to_center(last_center_cell, cell):
            break
        if cell[1] != center_col:
            gathered, next_target = gather_value_to_column(
                value,
                center_col,
                state.grid,
                belts,
                belt_index,
                cell_belts,
                state.pos,
                state.operations,
                central_id,
                central_direction,
                exit_pos,
                state.next_target,
                preserve_center_cell=last_center_cell,
            )
            state.next_target = next_target
            if value < state.next_target:
                value = state.next_target
                last_center_cell = None
                prepared = 0
                continue
            if not gathered or value not in state.pos or state.pos[value][1] != center_col:
                break
        last_center_cell = state.pos[value]
        prepared += 1
        value += 1
    return first_value < state.next_target or (first_value in state.pos and state.pos[first_value][1] == center_col)


def prepare_gap_insert(state: BeamState, n: int, belts: list[list[tuple[int, int]]], belt_index: list[dict[tuple[int, int], int]], cell_belts: dict[tuple[int, int], list[int]], central_id: int, central_direction: int, center_col: int, exit_pos: tuple[int, int]) -> bool:
    total = n * n
    a = state.next_target
    if a + 2 >= total or a not in state.pos or a + 1 not in state.pos or a + 2 not in state.pos:
        return False
    if state.pos[a][1] != center_col:
        gathered, next_target = gather_value_to_column(a, center_col, state.grid, belts, belt_index, cell_belts, state.pos, state.operations, central_id, central_direction, exit_pos, state.next_target)
        state.next_target = next_target
        if a not in state.pos or state.pos[a][1] != center_col:
            return a < state.next_target
    a_cell = state.pos[a]
    if state.pos[a + 2][1] != center_col:
        gathered, next_target = gather_value_to_column(a + 2, center_col, state.grid, belts, belt_index, cell_belts, state.pos, state.operations, central_id, central_direction, exit_pos, state.next_target, preserve_center_cell=a_cell)
        state.next_target = next_target
        if not gathered or a + 2 not in state.pos or state.pos[a + 2][1] != center_col:
            return False
    if a not in state.pos:
        return True
    a_cell = state.pos[a]
    a2_cell = state.pos[a + 2]
    exit_idx = belt_index[central_id][exit_pos]
    a_steps = steps_with_fixed_direction(belt_index[central_id][a_cell], exit_idx, len(belts[central_id]), central_direction)
    a2_steps = steps_with_fixed_direction(belt_index[central_id][a2_cell], exit_idx, len(belts[central_id]), central_direction)
    if a2_steps - a_steps < 2:
        return False
    a1_cell = state.pos[a + 1]
    if a1_cell[1] == center_col:
        a1_steps = steps_with_fixed_direction(belt_index[central_id][a1_cell], exit_idx, len(belts[central_id]), central_direction)
        return a_steps < a1_steps < a2_steps
    horiz_id = find_horizontal_belt_id(a1_cell, cell_belts, central_id)
    if horiz_id is None:
        return False
    target_cells: list[tuple[int, int]] = []
    for target_cell in ((horiz_id * 2, center_col), (horiz_id * 2 + 1, center_col)):
        if target_cell not in belt_index[central_id]:
            continue
        target_steps = steps_with_fixed_direction(belt_index[central_id][target_cell], exit_idx, len(belts[central_id]), central_direction)
        if a_steps < target_steps < a2_steps:
            target_cells.append(target_cell)
    best_plan: tuple[int, tuple[int, int]] | None = None
    for target_cell in target_cells:
        if target_cell not in belt_index[horiz_id]:
            continue
        current_idx = belt_index[horiz_id][a1_cell]
        target_idx = belt_index[horiz_id][target_cell]
        steps, _ = cycle_distance(current_idx, target_idx, len(belts[horiz_id]))
        plan = (steps, target_cell)
        if best_plan is None or plan < best_plan:
            best_plan = plan
    if best_plan is None:
        return False
    _, target_cell = best_plan
    gathered, next_target = gather_value_to_center_cell(a + 1, target_cell, state.grid, belts, belt_index, cell_belts, state.pos, state.operations, central_id, exit_pos, state.next_target, protected_cells=(a_cell, a2_cell))
    state.next_target = next_target
    if a + 1 not in state.pos:
        return True
    a1_cell = state.pos[a + 1]
    if a1_cell[1] != center_col:
        return False
    a1_steps = steps_with_fixed_direction(belt_index[central_id][a1_cell], exit_idx, len(belts[central_id]), central_direction)
    return a_steps < a1_steps < a2_steps


def move_center_until_next_extracts(state: BeamState, n: int, belts: list[list[tuple[int, int]]], belt_index: list[dict[tuple[int, int], int]], cell_belts: dict[tuple[int, int], list[int]], central_id: int, central_direction: int, center_col: int, exit_pos: tuple[int, int]) -> bool:
    if state.next_target not in state.pos:
        return True
    cell = state.pos[state.next_target]
    if cell not in belt_index[central_id] or cell[1] != exit_pos[1]:
        return False
    current_idx = belt_index[central_id][cell]
    exit_idx = belt_index[central_id][exit_pos]
    steps = steps_with_fixed_direction(current_idx, exit_idx, len(belts[central_id]), central_direction)
    before = state.next_target
    tried_mid_gather = False
    for _ in range(steps):
        if total_operations(state) >= MAX_OPERATIONS:
            return False
        rotate_belt(state.grid, belts[central_id], central_direction, state.pos)
        state.operations.append((central_id, central_direction))
        state.next_target = maybe_extract(state.grid, exit_pos, state.pos, state.next_target)
        if state.next_target == before and not tried_mid_gather and before in state.pos:
            current_cell = state.pos[before]
            gathered, next_target = gather_following_values_to_center(
                before + 1,
                center_col,
                current_cell,
                state.grid,
                belts,
                belt_index,
                cell_belts,
                state.pos,
                state.operations,
                central_id,
                central_direction,
                exit_pos,
                state.next_target,
            )
            state.next_target = next_target
            if gathered:
                tried_mid_gather = True
    state.next_target = maybe_extract(state.grid, exit_pos, state.pos, state.next_target)
    return state.next_target > before


def expand_state(state: BeamState, n: int, belts: list[list[tuple[int, int]]], belt_index: list[dict[tuple[int, int], int]], cell_belts: dict[tuple[int, int], list[int]], central_id: int, central_direction: int, center_col: int, exit_pos: tuple[int, int]) -> list[BeamState]:
    total = n * n
    children: list[BeamState] = []
    if state.next_target >= total:
        return children
    for chain_limit in range(1, LOOKAHEAD_BOXES + 1):
        child = clone_state(state)
        if not prepare_values_to_center(child, chain_limit, n, belts, belt_index, cell_belts, central_id, central_direction, center_col, exit_pos):
            continue
        if not move_center_until_next_extracts(child, n, belts, belt_index, cell_belts, central_id, central_direction, center_col, exit_pos):
            continue
        if total_operations(child) <= MAX_OPERATIONS:
            children.append(child)
    child = clone_state(state)
    if prepare_gap_insert(child, n, belts, belt_index, cell_belts, central_id, central_direction, center_col, exit_pos):
        if move_center_until_next_extracts(child, n, belts, belt_index, cell_belts, central_id, central_direction, center_col, exit_pos):
            if total_operations(child) <= MAX_OPERATIONS:
                children.append(child)
    return children


def select_beam(candidates: list[BeamState], n: int, belts: list[list[tuple[int, int]]], belt_index: list[dict[tuple[int, int], int]], cell_belts: dict[tuple[int, int], list[int]], central_id: int, center_col: int, central_direction: int) -> list[BeamState]:
    total = n * n
    selected: list[BeamState] = []
    selected_ids: set[int] = set()

    def add_from(states: list[BeamState], limit: int) -> None:
        for state in states:
            if id(state) in selected_ids:
                continue
            selected.append(state)
            selected_ids.add(id(state))
            if len(selected) >= BEAM_WIDTH or limit <= 1:
                return
            limit -= 1

    candidates.sort(key=lambda state: state_sort_key(state, n, belts, belt_index, cell_belts, central_id, center_col, central_direction), reverse=True)
    add_from(candidates, SELECT_OVERALL)

    by_order = sorted(
        candidates,
        key=lambda state: (
            state_sort_key(state, n, belts, belt_index, cell_belts, central_id, center_col, central_direction)[2],
            state.next_target,
            -total_operations(state),
        ),
        reverse=True,
    )
    add_from(by_order, SELECT_ORDER)

    by_ready = sorted(
        candidates,
        key=lambda state: (
            state_sort_key(state, n, belts, belt_index, cell_belts, central_id, center_col, central_direction)[3],
            state.next_target,
            -total_operations(state),
        ),
        reverse=True,
    )
    add_from(by_ready, SELECT_READY)

    by_next_row: dict[int, BeamState] = {}
    for state in candidates:
        cell = state.pos.get(state.next_target)
        row = -1 if cell is None else cell[0]
        current = by_next_row.get(row)
        if current is None or state_sort_key(state, n, belts, belt_index, cell_belts, central_id, center_col, central_direction) > state_sort_key(current, n, belts, belt_index, cell_belts, central_id, center_col, central_direction):
            by_next_row[row] = state
    add_from(
        sorted(by_next_row.values(), key=lambda state: state_sort_key(state, n, belts, belt_index, cell_belts, central_id, center_col, central_direction), reverse=True),
        SELECT_ROW,
    )

    by_short = sorted(candidates, key=lambda state: (-state.next_target, total_operations(state)))
    add_from(by_short, SELECT_SHORT)
    add_from(candidates, BEAM_WIDTH - len(selected))
    return selected[:BEAM_WIDTH]


def beam_search(initial_grid: list[list[int]], belts: list[list[tuple[int, int]]], belt_index: list[dict[tuple[int, int], int]], cell_belts: dict[tuple[int, int], list[int]], central_id: int, central_direction: int, center_col: int, exit_pos: tuple[int, int]) -> BeamState:
    n = len(initial_grid)
    total = n * n
    pos: dict[int, tuple[int, int]] = {}
    for i in range(n):
        for j in range(n):
            pos[initial_grid[i][j]] = (i, j)
    next_target = maybe_extract(initial_grid, exit_pos, pos, 0)
    initial = BeamState(initial_grid, pos, [], next_target)
    beam = [initial]
    best = initial

    while beam:
        if any(state.next_target >= total for state in beam):
            best = max(beam, key=lambda state: state_sort_key(state, n, belts, belt_index, cell_belts, central_id, center_col, central_direction))
            break
        candidates: list[BeamState] = []
        for state in beam:
            candidates.extend(expand_state(state, n, belts, belt_index, cell_belts, central_id, central_direction, center_col, exit_pos))
        if not candidates:
            best = max(beam, key=lambda state: state_sort_key(state, n, belts, belt_index, cell_belts, central_id, center_col, central_direction))
            break
        beam = select_beam(candidates, n, belts, belt_index, cell_belts, central_id, center_col, central_direction)
        if beam and state_sort_key(beam[0], n, belts, belt_index, cell_belts, central_id, center_col, central_direction) > state_sort_key(best, n, belts, belt_index, cell_belts, central_id, center_col, central_direction):
            best = beam[0]
    return best


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
    center_col = n // 2
    central_direction = -1

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

    exit_pos = (0, n // 2)
    best_state = beam_search(grid, belts, belt_index, cell_belts, central_id, central_direction, center_col, exit_pos)
    operations = restore_operations(best_state)

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
