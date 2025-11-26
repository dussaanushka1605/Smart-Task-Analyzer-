from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Set

TaskInput = Dict[str, Any]

DEFAULT_WEIGHTS = {
    "urgency": 1.0,
    "importance": 1.0,
    "effort": 1.0,
    "dependency": 1.0,
}

# (month, day)
HOLIDAYS = {
    (1, 1),   # New Year's Day
    (7, 4),   # Independence Day
    (12, 25), # Christmas Day
}


def normalize_weights(raw_weights: Any) -> Dict[str, float]:
    normalized = DEFAULT_WEIGHTS.copy()
    if not isinstance(raw_weights, dict):
        return normalized

    alias_map = {
        "urgency_weight": "urgency",
        "importance_weight": "importance",
        "effort_weight": "effort",
        "dependency_weight": "dependency",
        "urgency": "urgency",
        "importance": "importance",
        "effort": "effort",
        "dependency": "dependency",
    }

    for key, target in alias_map.items():
        if key in raw_weights and raw_weights[key] is not None:
            try:
                normalized[target] = max(0.0, float(raw_weights[key]))
            except (TypeError, ValueError):
                continue

    return normalized


def adjust_to_business_day(due: date) -> date:
    """Shift future weekend/holiday dates to the next working day."""
    today = date.today()
    if due < today:
        return due

    adjusted = due
    while adjusted.weekday() >= 5 or (adjusted.month, adjusted.day) in HOLIDAYS:
        adjusted += timedelta(days=1)
    return adjusted


def _normalize_dependencies(raw_dependencies: Any) -> List[str]:
    if raw_dependencies is None:
        return []
    if isinstance(raw_dependencies, str):
        return [dep for dep in (d.strip() for d in raw_dependencies.split(",")) if dep]
    if isinstance(raw_dependencies, list):
        return [str(dep).strip() for dep in raw_dependencies if str(dep).strip()]
    raise ValueError("Dependencies must be a list or comma-separated string.")


def _parse_due_date(value: Any) -> date:
    if isinstance(value, date):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError("due_date must be in YYYY-MM-DD format.") from exc
    else:
        raise ValueError("due_date is required for each task.")

    return adjust_to_business_day(parsed)


def _build_aliases(task: TaskInput) -> Set[str]:
    aliases = {task["_identifier"], task["title"]}
    if task.get("id"):
        aliases.add(str(task["id"]))
    return {alias for alias in aliases if alias}


def normalize_task(task: TaskInput, idx: int) -> TaskInput:
    if not isinstance(task, dict):
        raise ValueError("Each task must be an object.")

    normalized: TaskInput = {**task}
    normalized["title"] = str(normalized.get("title") or f"Task {idx + 1}")
    normalized["due_date"] = _parse_due_date(normalized.get("due_date"))
    normalized["estimated_hours"] = float(normalized.get("estimated_hours", 0))
    normalized["importance"] = int(normalized.get("importance", 0))
    normalized["dependencies"] = _normalize_dependencies(normalized.get("dependencies"))
    normalized["_identifier"] = str(normalized.get("id") or normalized["title"] or f"task_{idx}")
    normalized["_dependency_ids"] = []
    normalized["_aliases"] = _build_aliases(normalized)
    return normalized


def canonicalize_dependencies(tasks: List[TaskInput]) -> None:
    alias_map: Dict[str, str] = {}
    for task in tasks:
        for alias in task["_aliases"]:
            alias_map.setdefault(alias, task["_identifier"])

    for task in tasks:
        canonical = []
        for dep in task.get("dependencies", []):
            if dep in alias_map:
                canonical.append(alias_map[dep])
        task["_dependency_ids"] = canonical


def _find_circular_dependencies(tasks: List[TaskInput]) -> Dict[str, str]:
    graph = {task["_identifier"]: task["_dependency_ids"] for task in tasks}
    titles = {task["_identifier"]: task["title"] for task in tasks}
    visited: Set[str] = set()
    stack: List[str] = []
    stack_index: Dict[str, int] = {}
    node_messages: Dict[str, str] = {}

    def record_cycle(cycle_nodes: List[str]) -> None:
        unique_cycle = []
        for node in cycle_nodes:
            if not unique_cycle or unique_cycle[-1] != node:
                unique_cycle.append(node)
        readable = " -> ".join(titles.get(node, node) for node in unique_cycle)
        message = f"Circular dependency detected between {readable}"
        for node in set(unique_cycle):
            node_messages.setdefault(node, message)

    def dfs(node: str) -> None:
        visited.add(node)
        stack.append(node)
        stack_index[node] = len(stack) - 1
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                dfs(neighbor)
            elif neighbor in stack_index:
                cycle = stack[stack_index[neighbor] :] + [neighbor]
                record_cycle(cycle)
        stack.pop()
        stack_index.pop(node, None)

    for node in graph:
        if node not in visited:
            dfs(node)

    return node_messages


def calculate_score(task: TaskInput, weights: Dict[str, float]) -> float:
    """Calculate a weighted composite score for the given task."""
    days_left = (task["due_date"] - date.today()).days
    urgency = 10 if days_left < 0 else max(0, 10 - days_left)

    importance = max(0, min(10, int(task.get("importance", 0))))
    estimated_hours = max(0.0, float(task.get("estimated_hours", 0)))
    effort_component = max(1, 10 - estimated_hours)
    dependency_component = len(task.get("dependencies", [])) * 2

    return round(
        weights["urgency"] * urgency
        + weights["importance"] * importance
        + weights["effort"] * effort_component
        + weights["dependency"] * dependency_component,
        2,
    )


def build_explanation(task: TaskInput) -> str:
    reasons: List[str] = []
    days_left = (task["due_date"] - date.today()).days

    if days_left < 0:
        reasons.append("Overdue task needs immediate attention")
    elif days_left <= 3:
        reasons.append(f"Due soon (in {days_left} day{'s' if days_left != 1 else ''})")

    if task["importance"] >= 8:
        reasons.append("High importance")
    elif task["importance"] <= 3:
        reasons.append("Lower importance but balances workload")

    if task["estimated_hours"] <= 2:
        reasons.append("Quick win")

    dependency_count = len(task.get("dependencies") or [])
    if dependency_count:
        reasons.append(f"Unblocks {dependency_count} other task(s)")

    if not reasons:
        reasons.append("Balanced priority based on urgency and importance")

    return "; ".join(reasons)


def ensure_task_list(payload: Any) -> List[TaskInput]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and "tasks" in payload:
        tasks = payload["tasks"]
        if isinstance(tasks, list):
            return tasks
    raise ValueError("Payload must be a list of tasks or include a 'tasks' array.")


def extract_weights_from_payload(payload: Any) -> Dict[str, float]:
    if isinstance(payload, dict):
        return normalize_weights(payload.get("weights"))
    return DEFAULT_WEIGHTS.copy()


def score_tasks(raw_tasks: List[TaskInput], weights: Dict[str, float]) -> List[TaskInput]:
    normalized_tasks = [normalize_task(task, idx) for idx, task in enumerate(raw_tasks)]
    canonicalize_dependencies(normalized_tasks)
    circular_map = _find_circular_dependencies(normalized_tasks)

    for task in normalized_tasks:
        task["score"] = calculate_score(task, weights)
        task["explanation"] = build_explanation(task)
        if task["_identifier"] in circular_map:
            task["circular"] = True
            task["circular_message"] = circular_map[task["_identifier"]]
        else:
            task["circular"] = False
    return sorted(normalized_tasks, key=lambda item: item["score"], reverse=True)


def cleanup_internal_fields(tasks: List[TaskInput]) -> None:
    for task in tasks:
        task.pop("_identifier", None)
        task.pop("_dependency_ids", None)
        task.pop("_aliases", None)

