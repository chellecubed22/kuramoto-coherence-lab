"""Network topology generators for CMT layer."""

from __future__ import annotations

import numpy as np


def meanfield(n: int) -> np.ndarray:
    """All-to-all excluding self."""
    a = np.ones((n, n)) - np.eye(n)
    return a


def regular_lattice(n: int) -> np.ndarray:
    """1D ring lattice."""
    a = np.zeros((n, n))
    for i in range(n):
        a[i, (i - 1) % n] = 1
        a[i, (i + 1) % n] = 1
    return a


def smallworld(n: int, k: int = 4, p_rewire: float = 0.15, seed: int | None = None) -> np.ndarray:
    """Watts-Strogatz small-world on ring."""
    rng = np.random.default_rng(seed)
    a = regular_lattice(n)
    # Ensure k nearest neighbors each side
    for i in range(n):
        for j in range(2, k // 2 + 1):
            a[i, (i + j) % n] = 1
            a[i, (i - j) % n] = 1
    # Rewire edges with probability p
    for i in range(n):
        for j in range(n):
            if i != j and a[i, j] == 1 and rng.random() < p_rewire:
                a[i, j] = 0
                new_j = rng.integers(0, n)
                while new_j == i or a[i, new_j] == 1:
                    new_j = rng.integers(0, n)
                a[i, new_j] = 1
    return a


def scale_free(n: int, m: int = 2, seed: int | None = None) -> np.ndarray:
    """Barabási–Albert preferential attachment."""
    rng = np.random.default_rng(seed)
    a = np.zeros((n, n))
    # Start with m+1 fully connected nodes
    init = m + 1
    for i in range(init):
        for j in range(i + 1, init):
            a[i, j] = a[j, i] = 1
    degrees = a[:init, :init].sum(axis=1)

    for new_node in range(init, n):
        probs = degrees / degrees.sum()
        targets = rng.choice(new_node, size=m, replace=False, p=probs)
        for t in targets:
            a[new_node, t] = a[t, new_node] = 1
        degrees = np.append(degrees, m)
        degrees[targets] += 1

    return a


def symmetric_modules(
    n_modules: int = 4,
    nodes_per_module: int = 25,
    p_in: float = 0.05,
    c_inter: float = 0.10,
    seed: int | None = None,
) -> tuple[np.ndarray, list[list[int]]]:
    """4×25 modular network with intra rewiring and inter-module bridges."""
    rng = np.random.default_rng(seed)
    n = n_modules * nodes_per_module
    a = np.zeros((n, n))
    modules: list[list[int]] = []

    for m in range(n_modules):
        start = m * nodes_per_module
        mod_nodes = list(range(start, start + nodes_per_module))
        modules.append(mod_nodes)
        # Ring within module
        for i, node in enumerate(mod_nodes):
            a[node, mod_nodes[(i - 1) % nodes_per_module]] = 1
            a[node, mod_nodes[(i + 1) % nodes_per_module]] = 1
        # Random intra rewiring
        for _ in range(int(p_in * nodes_per_module * nodes_per_module)):
            i, j = rng.choice(mod_nodes, size=2, replace=False)
            a[i, j] = a[j, i] = 1

    # Inter-module bridges
    for m in range(n_modules):
        for m2 in range(m + 1, n_modules):
            n_bridges = max(1, int(c_inter * nodes_per_module))
            for _ in range(n_bridges):
                i = rng.choice(modules[m])
                j = rng.choice(modules[m2])
                a[i, j] = a[j, i] = c_inter

    return a, modules