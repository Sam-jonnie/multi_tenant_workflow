from app.core.graph import would_create_cycle


def test_task_cannot_depend_on_itself():
    assert would_create_cycle([], 1, 1)


def test_empty_graph_has_no_cycle():
    assert not would_create_cycle([], 2, 1)


def test_direct_cycle():
    edges = [(2, 1)]  # 2 depends on 1
    assert would_create_cycle(edges, 1, 2)  # adding "1 depends on 2"


def test_indirect_cycle():
    edges = [(2, 1), (3, 2)]  # chain 1 <- 2 <- 3
    assert would_create_cycle(edges, 1, 3)  # adding "1 depends on 3"


def test_diamond_is_not_a_cycle():
    edges = [(2, 1), (3, 1), (4, 2), (4, 3)]
    assert not would_create_cycle(edges, 4, 1)  # redundant, but legal
    assert would_create_cycle(edges, 1, 4)


def test_unrelated_branches_are_fine():
    edges = [(2, 1), (4, 3)]
    assert not would_create_cycle(edges, 3, 2)