# Smart Task Analyzer

GitHub Repository: https://github.com/dussaanushka1605/Smart-Task-Analyzer-

A full-stack mini-application that helps teams reason about their backlog by blending a configurable scoring algorithm, clean Django APIs, and a lightweight vanilla-JS interface.

```
task-analyzer/
├── backend/
│   ├── manage.py
│   ├── requirements.txt
│   ├── task_analyzer/
│   └── tasks/
│       ├── scoring.py      # scoring + normalization helpers
│       ├── serializers.py  # DRF serializers + validation rules
│       ├── urls.py / views.py
│       └── tests.py
├── frontend/
│   ├── index.html
│   ├── styles.css
│   └── script.js
└── README.md
```

---

## Setup Instructions

### Backend
```bash
cd backend
python -m venv .venv
. .venv/Scripts/activate      # or source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Run tests anytime:
```bash
cd backend
python manage.py test tasks
```

### Frontend
The UI is a static bundle. The quickest way to preview it is:
```bash
cd frontend
python -m http.server 5173
```
Then open http://localhost:5173 (ensure the Django server is running on 127.0.0.1:8000).

---

## API Cheatsheet (Optional)

### Analyze Tasks
```
POST http://127.0.0.1:8000/api/tasks/analyze/
Content-Type: application/json

{
  "tasks": [
    {
      "title": "Fix login bug",
      "due_date": "2025-11-30",
      "estimated_hours": 3,
      "importance": 8,
      "dependencies": []
    }
  ],
  "weights": {
    "urgency": 1,
    "importance": 1,
    "effort": 1,
    "dependency": 1
  }
}
```

### Suggest Top Tasks
```
GET http://127.0.0.1:8000/api/tasks/suggest/?tasks=[{"title":"Fix login bug","due_date":"2025-11-30","estimated_hours":3,"importance":8,"dependencies":[]}]
```

Both endpoints also accept JSON bodies for `tasks` (and optional `weights`) if you prefer POST/GET with payloads.

---

## Algorithm Explanation

Every incoming task is normalized first. Dates are parsed and, when they fall on a weekend or holiday, shifted to the next business day to avoid artificially inflating urgency for items due on non-working days. Past-due dates remain untouched so the algorithm can recognise true overruns. Importance is clamped to the 1–10 scale, estimated hours are coerced to floats, and dependencies are canonicalized. When tasks reference each other by ID, title, or alias, those references are resolved into a dependency graph that powers both scoring and circular-detection logic.

The core score is a weighted sum of four components. Urgency derives from the number of days until (or since) the due date: overdue tasks receive the maximum urgency, upcoming tasks taper linearly, and far-off items eventually hit zero. Importance is taken verbatim from the user. Effort rewards “quick wins” by flipping estimated hours into a 1–10 contribution, favouring small values. Dependencies boost tasks that unblock others; every downstream dependency adds a fixed multiplier. Default weights keep the mix balanced, but the frontend exposes sliders so users can dial urgency, importance, effort, or dependency emphasis per request. The backend simply applies those multipliers, so future weight schemes remain extensible.

Edge cases surface early. Missing fields are caught by DRF serializers, malformed dates raise user-friendly errors, and circular dependencies are detected with a DFS over the canonicalized graph. Rather than rejecting the entire payload, tasks participating in a cycle are flagged with `circular=true` plus a descriptive message (e.g., “Task A -> Task B -> Task A”), letting users resolve the issue in context.

After scoring, tasks are sorted by descending score and enriched with human-readable explanations. The explanation builder weaves together urgency notes (“Due soon in 2 days”), importance cues (“High importance”), quick-win hints, and dependency callouts so product leads understand why a task ranks where it does. The same scored list powers both `/api/tasks/analyze/` (return all tasks) and `/api/tasks/suggest/` (top three recommendations). Suggest also honours optional query/body weight overrides, making experimentation effortless.

Finally, every response is scrubbed of helper fields before returning to the client, ensuring API consumers only see meaningful data: title, due date, estimated hours, importance, dependencies, score, explanation, and any circular warnings. The result is a transparent, configurable prioritization pipeline that stays resilient to bad data while providing actionable insights.

---

## Design Decisions
- **Single scoring module (`tasks/scoring.py`)** isolates normalization, business-day logic, dependency graphing, and weighting, keeping views slim.
- **Serializer-backed validation** catches missing or malformed fields before scoring.
- **Circular detection as warnings** avoids blocking analysis while still surfacing risks directly in the UI.
- **Vanilla JS frontend** keeps the footprint small and mirrors the suggested structure while still offering modern UX (modals, tabs, matrix view).
- **Weight sliders** let stakeholders experiment with prioritization philosophies without code changes.

---

## Time Breakdown
| Task | Approx. Time |
| --- | --- |
| Algorithm + normalization design | 2.0 h |
| API endpoints & serializers | 1.0 h |
| Frontend UI (forms, results, matrix) | 1.5 h |
| Bonus features (weights, circular flags, holidays) | 1.0 h |
| Testing + polishing + docs | 0.5 h |

---

## Bonus Challenges Attempted
- Circular dependency detection with inline warnings.
- Date intelligence (weekend/holiday adjustment).
- Eisenhower matrix visualization.
- Weighting customization UI + backend support.
- Unit tests covering scoring edge cases.

---

## Future Improvements
- Allow users to save weight presets or personas (“Ops mode”, “Delivery mode”).
- Visual dependency graph (e.g., force-directed diagram) to complement warnings.
- Add persistence so tasks survive page reloads (localStorage or backend DB).
- Introduce a simple “feedback” loop where users can mark suggestions as helpful to inform future weighting defaults.
- Internationalization (custom work weeks, regional holidays).

---
