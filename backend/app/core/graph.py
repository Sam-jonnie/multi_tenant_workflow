from collections import defaultdict, deque
from collections.abc import Iterable


def would_create_cycle(
    edges: Iterable[tuple[int, int]], task_id: int, depends_on_id: int
) -> bool:
    """Would adding "task_id depends on depends_on_id" create a cycle?

    `edges` are existing (dependent, prerequisite) pairs.
    A cycle appears if the new prerequisite already depends, directly or
    through a chain, on the task we are adding it to.
    """
    if task_id == depends_on_id:
        return True

    prerequisites: defaultdict[int, list[int]] = defaultdict(list)
    for dependent, prerequisite in edges:
        prerequisites[dependent].append(prerequisite)

    seen = {depends_on_id}
    queue = deque([depends_on_id])
    while queue:  # breadth-first walk along "depends on" arrows
        current = queue.popleft()
        for nxt in prerequisites[current]:
            if nxt == task_id:
                return True
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return False