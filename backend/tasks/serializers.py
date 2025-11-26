from typing import Any, List

from rest_framework import serializers


class DependenciesField(serializers.Field):
    def to_internal_value(self, data: Any) -> List[str]:
        if data is None:
            return []
        if isinstance(data, list):
            return [str(item).strip() for item in data if str(item).strip()]
        if isinstance(data, str):
            return [segment.strip() for segment in data.split(",") if segment.strip()]
        raise serializers.ValidationError(
            "Dependencies must be a list or a comma-separated string."
        )

    def to_representation(self, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [segment.strip() for segment in value.split(",") if segment.strip()]
        return []


class TaskSerializer(serializers.Serializer):
    id = serializers.CharField(required=False, allow_blank=True)
    title = serializers.CharField()
    due_date = serializers.DateField()
    estimated_hours = serializers.FloatField(min_value=0)
    importance = serializers.IntegerField(min_value=0, max_value=10)
    dependencies = DependenciesField(required=False)

