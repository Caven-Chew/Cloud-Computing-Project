"""Build agent contact graphs. Uses networkx for scale-free; hand-rolled for star/mesh."""
from __future__ import annotations
import networkx as nx


def star(n: int) -> dict[int, list[int]]:
    # node 0 is the hub
    return {0: list(range(1, n)), **{i: [0] for i in range(1, n)}}


def mesh(n: int) -> dict[int, list[int]]:
    return {i: [j for j in range(n) if j != i] for i in range(n)}


def scale_free(n: int, seed: int = 0) -> dict[int, list[int]]:
    g = nx.barabasi_albert_graph(n, m=2, seed=seed)
    return {i: list(g.neighbors(i)) for i in range(n)}


def ring(n: int) -> dict[int, list[int]]:
    return {i: [(i - 1) % n, (i + 1) % n] for i in range(n)}


BUILDERS = {"star": star, "mesh": mesh, "scale_free": scale_free, "ring": ring}
