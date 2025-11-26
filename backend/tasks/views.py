import json
from typing import Any, Dict, List

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import serializers

from .serializers import TaskSerializer
from .scoring import (
    DEFAULT_WEIGHTS,
    cleanup_internal_fields,
    ensure_task_list,
    extract_weights_from_payload,
    normalize_weights,
    score_tasks,
)

TaskData = Dict[str, Any]


def _extract_tasks_from_request(request) -> List[TaskData]:
    if request.query_params.get("tasks"):
        try:
            return json.loads(request.query_params["tasks"])
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON supplied in 'tasks' query parameter.") from exc

    if request.data:
        return ensure_task_list(request.data)

    return []


def _weights_from_request(request) -> Dict[str, float]:
    if request.query_params.get("weights"):
        try:
            payload = json.loads(request.query_params["weights"])
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON supplied in 'weights' query parameter.") from exc
        return normalize_weights(payload)

    if request.data:
        return extract_weights_from_payload(request.data)

    return DEFAULT_WEIGHTS.copy()


def _validate_tasks(raw_tasks: List[TaskData]) -> List[TaskData]:
    serializer = TaskSerializer(data=raw_tasks, many=True)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


@api_view(["POST"])
def analyze_tasks(request):
    payload = request.data
    try:
        raw_tasks = ensure_task_list(payload)
        validated = _validate_tasks(raw_tasks)
        weights = extract_weights_from_payload(payload)
        scored_tasks = score_tasks(validated, weights)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except serializers.ValidationError as exc:
        return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)

    cleanup_internal_fields(scored_tasks)
    return Response(scored_tasks)


@api_view(["GET"])
def suggest_tasks(request):
    try:
        raw_tasks = _extract_tasks_from_request(request)
        if not raw_tasks:
            raise ValueError("No tasks provided. Include tasks via ?tasks=[...] or request body.")
        validated = _validate_tasks(raw_tasks)
        weights = _weights_from_request(request)
        scored_tasks = score_tasks(validated, weights)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except serializers.ValidationError as exc:
        return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)

    cleanup_internal_fields(scored_tasks)

    return Response(
        {
            "message": "Top 3 recommended tasks based on priority score",
            "suggested_tasks": scored_tasks[:3],
        }
    )

