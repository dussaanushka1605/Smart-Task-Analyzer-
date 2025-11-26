const API_URL = "http://127.0.0.1:8000/api/tasks/analyze/";

const state = {
  tasks: [],
  results: [],
  weights: {
    urgency: 1,
    importance: 1,
    effort: 1,
    dependency: 1,
  },
  view: "list",
  loading: false,
};

const weightMeta = [
  { key: "urgency", label: "Urgency", description: "Boosts upcoming and overdue tasks." },
  { key: "importance", label: "Importance", description: "Rewards high-impact tasks." },
  { key: "effort", label: "Effort", description: "Highlights quick wins." },
  { key: "dependency", label: "Dependency", description: "Prioritizes blockers." },
];

const selectors = {
  form: document.getElementById("task-form"),
  clearTasks: document.getElementById("clear-tasks"),
  taskList: document.getElementById("task-list"),
  taskCount: document.getElementById("task-count"),
  weightControls: document.getElementById("weight-controls"),
  resetWeights: document.getElementById("reset-weights"),
  analyzeBtn: document.getElementById("analyze-btn"),
  status: document.getElementById("status"),
  results: document.getElementById("results"),
  segmentedButtons: document.querySelectorAll(".segmented-btn"),
};

function init() {
  selectors.form.addEventListener("submit", handleAddTask);
  selectors.clearTasks.addEventListener("click", handleClearTasks);
  selectors.resetWeights.addEventListener("click", handleResetWeights);
  selectors.analyzeBtn.addEventListener("click", handleAnalyze);
  selectors.segmentedButtons.forEach((btn) =>
    btn.addEventListener("click", () => {
      selectors.segmentedButtons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.view = btn.dataset.view;
      renderResults();
    })
  );
  renderWeightControls();
  renderTasks();
  renderResults();
}

function handleAddTask(event) {
  event.preventDefault();

  const title = document.getElementById("title").value.trim();
  const dueDate = document.getElementById("due_date").value;
  const estimatedHours = Number(document.getElementById("hours").value);
  const importance = Number(document.getElementById("importance").value);
  const dependenciesRaw = document.getElementById("dependencies").value;

  if (!title || !dueDate) {
    return;
  }

  const dependencies = dependenciesRaw
    ? dependenciesRaw.split(",").map((dep) => dep.trim()).filter(Boolean)
    : [];

  state.tasks.push({
    id: crypto.randomUUID(),
    title,
    due_date: dueDate,
    estimated_hours: estimatedHours,
    importance,
    dependencies,
  });

  selectors.form.reset();
  document.getElementById("importance").value = "5";
  document.getElementById("hours").value = "1";
  renderTasks();
}

function handleClearTasks() {
  if (state.tasks.length === 0) return;
  state.tasks = [];
  state.results = [];
  renderTasks();
  renderResults();
}

function renderTasks() {
  selectors.taskCount.textContent = `${state.tasks.length} item${state.tasks.length === 1 ? "" : "s"}`;
  selectors.taskList.innerHTML = "";

  if (state.tasks.length === 0) {
    const empty = document.createElement("p");
    empty.className = "matrix-empty";
    empty.textContent = "No tasks yet. Add one using the form above.";
    selectors.taskList.appendChild(empty);
    return;
  }

  state.tasks.forEach((task, index) => {
    const item = document.createElement("li");
    item.className = "task-card";
    item.innerHTML = `
      <div>
        <strong>${task.title}</strong>
        <p class="weight-description">
          Due ${task.due_date} • ${task.estimated_hours}h • Importance ${task.importance}/10
        </p>
        ${task.dependencies.length ? `<p class="weight-description">Dependencies: ${task.dependencies.join(", ")}</p>` : ""}
      </div>
      <button type="button" class="secondary small" data-index="${index}">Remove</button>
    `;
    item.querySelector("button").addEventListener("click", () => {
      state.tasks.splice(index, 1);
      renderTasks();
    });
    selectors.taskList.appendChild(item);
  });
}

function renderWeightControls() {
  selectors.weightControls.innerHTML = "";
  weightMeta.forEach(({ key, label, description }) => {
    const wrapper = document.createElement("div");
    wrapper.className = "weight-control";

    wrapper.innerHTML = `
      <div class="weight-meta">
        <span>${label}</span>
        <strong><span data-weight-value="${key}">${state.weights[key].toFixed(1)}</span>x</strong>
      </div>
      <input type="range" min="0" max="3" step="0.1" value="${state.weights[key]}" data-weight="${key}" />
      <p class="weight-description">${description}</p>
    `;

    const range = wrapper.querySelector("input");
    range.addEventListener("input", (event) => {
      const value = Number(event.target.value);
      state.weights[key] = Number(value.toFixed(1));
      wrapper.querySelector(`[data-weight-value="${key}"]`).textContent = state.weights[key].toFixed(1);
    });

    selectors.weightControls.appendChild(wrapper);
  });
}

function handleResetWeights() {
  state.weights = { urgency: 1, importance: 1, effort: 1, dependency: 1 };
  renderWeightControls();
}

async function handleAnalyze() {
  if (state.tasks.length === 0 || state.loading) {
    setStatus("Add at least one task before analyzing.");
    return;
  }

  try {
    state.loading = true;
    selectors.analyzeBtn.disabled = true;
    setStatus("Analyzing tasks...");

    const response = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tasks: state.tasks,
        weights: state.weights,
      }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `Request failed with status ${response.status}`);
    }

    const data = await response.json();
    state.results = Array.isArray(data) ? data : [];
    setStatus("Tasks analyzed successfully.");
    renderResults();
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    state.loading = false;
    selectors.analyzeBtn.disabled = false;
  }
}

function setStatus(message, isError = false) {
  if (!message) {
    selectors.status.textContent = "";
    selectors.status.classList.remove("error");
    return;
  }
  selectors.status.textContent = message;
  selectors.status.classList.toggle("error", Boolean(isError));
}

function renderResults() {
  selectors.results.innerHTML = "";

  if (state.results.length === 0) {
    const empty = document.createElement("p");
    empty.className = "matrix-empty";
    empty.textContent = "No results yet. Run an analysis to populate this area.";
    selectors.results.appendChild(empty);
    return;
  }

  if (state.view === "matrix") {
    selectors.results.appendChild(renderMatrix());
  } else {
    selectors.results.appendChild(renderResultList());
  }
}

function renderResultList() {
  const container = document.createElement("div");
  container.className = "results-list";

  state.results.forEach((task, index) => {
    const card = document.createElement("div");
    card.className = `result-card ${task.circular ? "circular" : ""}`;
    card.innerHTML = `
      <div class="panel-header">
        <strong>#${index + 1} &middot; ${task.title}</strong>
        <span class="badge ${task.priority || "unknown"}">${(task.priority || "unknown").toUpperCase()}</span>
      </div>
      <p class="weight-description">
        Due ${task.due_date} • ${task.estimated_hours}h • Importance ${task.importance}/10 • Score ${Number(
          task.score || 0
        ).toFixed(2)}
      </p>
      ${task.explanation ? `<p class="weight-description">${task.explanation}</p>` : ""}
      ${
        task.dependencies?.length
          ? `<p class="weight-description">Dependencies: ${task.dependencies.join(", ")}</p>`
          : ""
      }
      ${
        task.circular
          ? `<p class="badge circular">⚠ ${task.circular_message || "Circular dependency detected"}</p>`
          : ""
      }
    `;
    container.appendChild(card);
  });

  return container;
}

function renderMatrix() {
  const container = document.createElement("div");
  container.className = "matrix";

  const quadrants = {
    urgentImportant: [],
    urgentNotImportant: [],
    notUrgentImportant: [],
    notUrgentNotImportant: [],
  };

  state.results.forEach((task) => {
    const urgent = isUrgent(task.due_date);
    const important = Number(task.importance) >= 6;

    if (urgent && important) quadrants.urgentImportant.push(task);
    else if (urgent && !important) quadrants.urgentNotImportant.push(task);
    else if (!urgent && important) quadrants.notUrgentImportant.push(task);
    else quadrants.notUrgentNotImportant.push(task);
  });

  const meta = [
    { key: "urgentImportant", title: "Do First", description: "Urgent & important" },
    { key: "urgentNotImportant", title: "Delegate", description: "Urgent & less important" },
    { key: "notUrgentImportant", title: "Schedule", description: "Important but not urgent" },
    { key: "notUrgentNotImportant", title: "Eliminate", description: "Neither urgent nor important" },
  ];

  meta.forEach(({ key, title, description }) => {
    const card = document.createElement("div");
    card.className = "matrix-card";
    card.innerHTML = `<div><h3>${title}</h3><p class="weight-description">${description}</p></div>`;

    if (quadrants[key].length === 0) {
      const empty = document.createElement("p");
      empty.className = "matrix-empty";
      empty.textContent = "No tasks yet.";
      card.appendChild(empty);
    } else {
      quadrants[key].forEach((task) => {
        const entry = document.createElement("div");
        entry.className = "result-card";
        entry.innerHTML = `
          <strong>${task.title}</strong>
          <p class="weight-description">Due ${task.due_date} • Score ${Number(task.score || 0).toFixed(2)}</p>
          ${task.circular ? `<p class="badge circular">⚠ ${task.circular_message || "Circular"}</p>` : ""}
        `;
        card.appendChild(entry);
      });
    }

    container.appendChild(card);
  });

  return container;
}

function isUrgent(dueDate) {
  const today = new Date();
  const due = new Date(dueDate);
  const diffDays = Math.ceil((due - today) / (1000 * 60 * 60 * 24));
  return diffDays <= 3;
}

init();

