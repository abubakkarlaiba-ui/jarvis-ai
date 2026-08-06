"""
Workflow Engine — dependency resolver.
======================================
Resolves step dependencies, detects cycles, and builds execution order.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from jarvis.core.workflow.base import Step


class DependencyResolver:
    """Resolve step dependencies, detect cycles, and build execution order."""

    def resolve(self, steps: list[Step]) -> list[list[str]]:
        """Return execution groups via topological sort with parallelism.

        Each inner list is a group of step IDs that can run in parallel.
        Raises ValueError if a cycle is detected.
        """
        graph = self.build_dependency_graph(steps)
        in_degree: dict[str, int] = {s.id: 0 for s in steps}
        step_map = {s.id: s for s in steps}

        for step_id, deps in graph.items():
            in_degree.setdefault(step_id, len(deps))
            for dep in deps:
                if dep in in_degree:
                    in_degree[dep] = in_degree.get(dep, 0)

        # Recompute in_degree properly from graph edges
        in_degree = {s.id: 0 for s in steps}
        for step_id, deps in graph.items():
            in_degree[step_id] = len(deps)

        queue: deque[str] = deque()
        for step_id, deg in in_degree.items():
            if deg == 0:
                queue.append(step_id)

        groups: list[list[str]] = []
        processed = 0

        while queue:
            group = list(queue)
            queue.clear()
            groups.append(group)
            processed += len(group)

            for step_id in group:
                for dependent_id, deps in graph.items():
                    if step_id in deps:
                        in_degree[dependent_id] -= 1
                        if in_degree[dependent_id] == 0:
                            queue.append(dependent_id)

        if processed != len(steps):
            cycle = self.detect_cycle(steps)
            cycle_info = f" Cycle: {' -> '.join(cycle)}" if cycle else ""
            raise ValueError(
                f"Dependency cycle detected ({processed}/{len(steps)} steps processed).{cycle_info}"
            )

        return groups

    def detect_cycle(self, steps: list[Step]) -> list[str] | None:
        """Return cycle path if detected, else None."""
        graph = self.build_dependency_graph(steps)
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {s.id: WHITE for s in steps}
        parent: dict[str, str | None] = {s.id: None for s in steps}

        def dfs(node: str) -> list[str] | None:
            color[node] = GRAY
            for neighbor in graph.get(node, []):
                if neighbor not in color:
                    continue
                if color[neighbor] == GRAY:
                    cycle = [neighbor, node]
                    cur = node
                    while cur != neighbor:
                        cur = parent[cur]
                        if cur is None:
                            break
                        cycle.append(cur)
                    cycle.reverse()
                    return cycle
                if color[neighbor] == WHITE:
                    parent[neighbor] = node
                    result = dfs(neighbor)
                    if result:
                        return result
            color[node] = BLACK
            return None

        for step_id in steps:
            if color[step_id] == WHITE:
                result = dfs(step_id)
                if result:
                    return result
        return None

    def get_ready_steps(
        self, steps: list[Step], completed: set[str]
    ) -> list[Step]:
        """Return steps whose dependencies are all completed."""
        ready = []
        for step in steps:
            if step.id in completed:
                continue
            deps_met = all(dep in completed for dep in step.depends_on)
            if deps_met:
                ready.append(step)
        return ready

    def get_blocked_steps(
        self, steps: list[Step], completed: set[str]
    ) -> list[Step]:
        """Return steps still blocked by dependencies."""
        blocked = []
        for step in steps:
            if step.id in completed:
                continue
            deps_met = all(dep in completed for dep in step.depends_on)
            if not deps_met:
                blocked.append(step)
        return blocked

    def build_dependency_graph(self, steps: list[Step]) -> dict[str, list[str]]:
        """Return adjacency list: step_id -> list of dependency step_ids."""
        graph: dict[str, list[str]] = {}
        for step in steps:
            graph[step.id] = list(step.depends_on)
        return graph

    def estimate_parallelism(self, steps: list[Step]) -> dict[str, Any]:
        """Return max parallelism, critical path length, and total work."""
        groups = self.resolve(steps)
        step_map = {s.id: s for s in steps}

        max_parallelism = max(len(g) for g in groups) if groups else 0

        # Critical path: longest chain of dependencies
        critical_path = 0
        if groups:
            critical_path = len(groups)

        total_work = sum(
            step.timeout for step in steps
        )

        return {
            "max_parallelism": max_parallelism,
            "critical_path_length": critical_path,
            "total_work": total_work,
            "execution_groups": groups,
        }

    def validate(self, steps: list[Step]) -> list[str]:
        """Return list of validation errors (missing deps, cycles, etc.)."""
        errors: list[str] = []
        step_ids = {s.id for s in steps}

        for step in steps:
            for dep in step.depends_on:
                if dep not in step_ids:
                    errors.append(
                        f"Step '{step.id}' depends on non-existent step '{dep}'"
                    )

        cycle = self.detect_cycle(steps)
        if cycle:
            errors.append(
                f"Dependency cycle detected: {' -> '.join(cycle)}"
            )

        seen_ids = set()
        for step in steps:
            if step.id in seen_ids:
                errors.append(f"Duplicate step ID: '{step.id}'")
            seen_ids.add(step.id)

        return errors
