import copy
import json
from datetime import date, timedelta

from django.test import TestCase
from rest_framework.test import APIClient

from .scoring import DEFAULT_WEIGHTS, HOLIDAYS, calculate_score


class ScoringTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_high_importance_gives_higher_score(self):
        """Tasks with higher importance should get higher score"""
        today = date.today()

        task_low = {
            "due_date": today,
            "estimated_hours": 3,
            "importance": 3,
            "dependencies": []
        }

        task_high = {
            "due_date": today,
            "estimated_hours": 3,
            "importance": 9,
            "dependencies": []
        }

        score_low = calculate_score(task_low, DEFAULT_WEIGHTS)
        score_high = calculate_score(task_high, DEFAULT_WEIGHTS)

        self.assertTrue(score_high > score_low)

    def test_overdue_task_has_higher_urgency(self):
        """Past-due tasks should get urgency boost"""
        yesterday = date.today() - timedelta(days=1)
        tomorrow = date.today() + timedelta(days=1)

        overdue_task = {
            "due_date": yesterday,
            "estimated_hours": 2,
            "importance": 5,
            "dependencies": []
        }

        future_task = {
            "due_date": tomorrow,
            "estimated_hours": 2,
            "importance": 5,
            "dependencies": []
        }

        score_overdue = calculate_score(overdue_task, DEFAULT_WEIGHTS)
        score_future = calculate_score(future_task, DEFAULT_WEIGHTS)

        self.assertTrue(score_overdue > score_future)

    def test_dependencies_increase_score(self):
        """Tasks with more dependencies should get a boost"""
        today = date.today()

        task_no_deps = {
            "due_date": today,
            "estimated_hours": 2,
            "importance": 5,
            "dependencies": []
        }

        task_with_deps = {
            "due_date": today,
            "estimated_hours": 2,
            "importance": 5,
            "dependencies": ["T1", "T2"]
        }

        score_no = calculate_score(task_no_deps, DEFAULT_WEIGHTS)
        score_yes = calculate_score(task_with_deps, DEFAULT_WEIGHTS)

        self.assertTrue(score_yes > score_no)

    def test_analyze_flags_circular_dependencies(self):
        today = date.today().isoformat()

        circular_payload = [
            {
                "id": "A",
                "title": "Task A",
                "due_date": today,
                "estimated_hours": 2,
                "importance": 5,
                "dependencies": ["B"],
            },
            {
                "id": "B",
                "title": "Task B",
                "due_date": today,
                "estimated_hours": 2,
                "importance": 6,
                "dependencies": ["A"],
            },
        ]

        response = self.client.post("/api/tasks/analyze/", circular_payload, format="json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        flagged = [task for task in data if task["title"] in {"Task A", "Task B"}]
        self.assertTrue(all(task.get("circular") for task in flagged))
        self.assertTrue(all("Circular dependency" in task.get("circular_message", "") for task in flagged))

    def test_weekend_due_dates_shift_forward(self):
        today = date.today()

        def next_saturday(start: date) -> date:
            days_ahead = (5 - start.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            candidate = start + timedelta(days=days_ahead)
            # ensure following Monday is not a holiday
            monday = candidate + timedelta(days=2)
            while (monday.month, monday.day) in HOLIDAYS:
                candidate += timedelta(days=7)
                monday = candidate + timedelta(days=2)
            return candidate

        saturday = next_saturday(today)
        expected_monday = saturday + timedelta(days=(7 - saturday.weekday()))

        payload = [
            {
                "title": "Weekend task",
                "due_date": saturday.isoformat(),
                "estimated_hours": 3,
                "importance": 5,
                "dependencies": [],
            }
        ]

        response = self.client.post("/api/tasks/analyze/", payload, format="json")
        self.assertEqual(response.status_code, 200)
        returned_due_date = response.json()[0]["due_date"]
        self.assertEqual(returned_due_date, expected_monday.isoformat())

    def test_custom_weights_influence_scores(self):
        today = date.today().isoformat()
        base_tasks = [
            {
                "title": "Dependency heavy",
                "due_date": today,
                "estimated_hours": 6,
                "importance": 5,
                "dependencies": ["Quick win"],
            },
            {
                "title": "Quick win",
                "due_date": today,
                "estimated_hours": 1,
                "importance": 8,
                "dependencies": [],
            },
        ]

        default_response = self.client.post("/api/tasks/analyze/", copy.deepcopy(base_tasks), format="json")
        self.assertEqual(default_response.status_code, 200)
        default_top = default_response.json()[0]["title"]

        weighted_payload = {
            "tasks": copy.deepcopy(base_tasks),
            "weights": {
                "urgency_weight": 0.5,
                "importance_weight": 0.5,
                "effort_weight": 0.5,
                "dependency_weight": 3,
            },
        }
        weighted_response = self.client.post("/api/tasks/analyze/", weighted_payload, format="json")
        self.assertEqual(weighted_response.status_code, 200)
        weighted_top = weighted_response.json()[0]["title"]

        self.assertNotEqual(default_top, weighted_top)


class SuggestionEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        base_date = date.today()
        self.sample_tasks = [
            {
                "title": "Fix login bug",
                "due_date": (base_date).isoformat(),
                "estimated_hours": 3,
                "importance": 9,
                "dependencies": [],
            },
            {
                "title": "Write documentation",
                "due_date": (base_date + timedelta(days=5)).isoformat(),
                "estimated_hours": 6,
                "importance": 5,
                "dependencies": [],
            },
            {
                "title": "Prep release",
                "due_date": (base_date + timedelta(days=2)).isoformat(),
                "estimated_hours": 4,
                "importance": 7,
                "dependencies": ["Fix login bug"],
            },
            {
                "title": "Refactor dashboard",
                "due_date": (base_date + timedelta(days=10)).isoformat(),
                "estimated_hours": 2,
                "importance": 6,
                "dependencies": [],
            },
        ]

    def test_suggest_requires_tasks(self):
        response = self.client.get("/api/tasks/suggest/")
        self.assertEqual(response.status_code, 400)
        self.assertIn("No tasks provided", response.json().get("detail", ""))

    def test_suggest_returns_top_three_sorted(self):
        response = self.client.get(
            "/api/tasks/suggest/",
            {"tasks": json.dumps(self.sample_tasks)},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        suggested = payload.get("suggested_tasks", [])
        self.assertEqual(len(suggested), 3)

        scores = [task["score"] for task in suggested]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertTrue(all("explanation" in task for task in suggested))
