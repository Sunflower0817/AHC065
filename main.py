import sys


def make_ring_belt(d: int, n: int) -> list[tuple[int, int]]:
    cells: list[tuple[int, int]] = []
    if n - 2 * d < 2:
        return cells

    # top edge
    for j in range(d, n - d):
        cells.append((d, j))
    # right edge
    for i in range(d + 1, n - d):
        cells.append((i, n - 1 - d))
    # bottom edge
    for j in range(n - 2 - d, d - 1, -1):
        cells.append((n - 1 - d, j))
    # left edge
    for i in range(n - 2 - d, d, -1):
        cells.append((i, d))
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


def main() -> None:
    data = sys.stdin.read().strip().split()
    if not data:
        return
    it = iter(data)
    n = int(next(it))
    grid = [[int(next(it)) for _ in range(n)] for _ in range(n)]

    belts: list[list[tuple[int, int]]] = []
    for d in range(n // 2):
        belt = make_ring_belt(d, n)
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
                exit_idx = belt_index[central_id][exit_pos]
                steps, direction = cycle_distance(current_idx, exit_idx, len(central_belt))
                for _ in range(steps):
                    rotate_belt(grid, central_belt, direction, pos)
                    operations.append((central_id, direction))
                    next_target = maybe_extract(grid, exit_pos, pos, next_target)
                continue

            ring_id = belts_at_cell[0]
            ring = belts[ring_id]
            current_idx = belt_index[ring_id][cell]
            best_plan = None
            c = n // 2
            d = ring_id
            candidates = [
                (d, c),
                (n - 1 - d, c),
                (d, c + 1),
                (n - 1 - d, c + 1),
            ]
            for candidate in candidates:
                if candidate not in belt_index[ring_id]:
                    continue
                ring_target_idx = belt_index[ring_id][candidate]
                ring_steps, ring_dir = cycle_distance(current_idx, ring_target_idx, len(ring))
                central_target_idx = belt_index[central_id][candidate]
                exit_idx = belt_index[central_id][exit_pos]
                central_steps, central_dir = cycle_distance(central_target_idx, exit_idx, len(central_belt))
                cost = ring_steps + central_steps
                plan = (cost, ring_steps, candidate, ring_dir, central_dir)
                if best_plan is None or plan < best_plan:
                    best_plan = plan

            if best_plan is None:
                break
            _, ring_steps, candidate_cell, ring_dir, _ = best_plan
            if ring_steps > 0:
                for _ in range(ring_steps):
                    rotate_belt(grid, ring, ring_dir, pos)
                    operations.append((ring_id, ring_dir))
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
    main()
