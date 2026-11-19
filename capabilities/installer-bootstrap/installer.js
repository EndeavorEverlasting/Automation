"use strict";

const get = (id) => document.getElementById(id);
const title = get("title");
const summary = get("summary");
const feedback = get("feedback");
const options = get("options");
const install = get("install");
let previous;
let busy = false;
let closed = false;
let actionVersion = 0;

const stepStatus = {
  pending: ["·", "Waiting"], running: ["›", "In progress"],
  done: ["✓", "Complete"], skipped: ["–", "Skipped"], failed: ["!", "Needs attention"]
};

function announce(node, text) {
  if (node.textContent !== text) node.textContent = text;
}

function buildOptions(state) {
  get("destination").textContent = state.destination;
  for (const option of state.options) {
    const label = document.createElement("label");
    label.className = "option";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.name = option.id;
    input.checked = state.choices[option.id];
    const text = document.createElement("span");
    text.textContent = option.label;
    const details = document.createElement("small");
    details.textContent = option.description;
    text.append(details);
    label.append(input, text);
    options.append(label);
  }
  options.hidden = !state.options.length;
}

function render(state) {
  if (!previous) buildOptions(state);
  const transition = state.status !== previous?.status;
  const running = ["running", "stopping"].includes(state.status);
  const retry = ["failed", "cancelled"].includes(state.status);
  const review = state.status === "review" || retry;
  document.title = state.title + " setup";
  announce(title, ({
    review: "Set up " + state.title,
    running: "Installing " + state.title,
    stopping: "Stopping setup",
    cancelled: "Setup stopped",
    failed: "Setup needs attention",
    done: state.title + " is installed"
  })[state.status]);
  const active = state.steps.find((step) => step.state === "running");
  announce(summary, ({
    review: state.description,
    running: state.progress + "% complete" + (active ? " · " + active.label : ""),
    stopping: "Waiting for the current step to finish.",
    cancelled: "Review your choices and try again when you're ready.",
    failed: "Review the step below. You can adjust your choices before retrying.",
    done: state.destination
  })[state.status]);
  get("review").hidden = !review;
  get("work").hidden = state.status === "review";
  get("actions").hidden = false;
  install.hidden = !review;
  announce(install, retry ? "Retry setup" : "Install");
  get("close").hidden = running;
  get("cancel").hidden = !running;
  get("cancel").disabled = busy || state.status === "stopping";
  const rail = get("rail");
  rail.style.setProperty("--progress", state.progress + "%");
  rail.setAttribute("aria-valuenow", state.progress);
  if (!previous || JSON.stringify(previous.steps) !== JSON.stringify(state.steps)) {
    get("steps").replaceChildren(...state.steps.map((step) => {
      const row = document.createElement("li");
      row.className = step.state;
      const indicator = document.createElement("span");
      indicator.className = "indicator";
      indicator.setAttribute("aria-hidden", "true");
      indicator.textContent = stepStatus[step.state][0];
      const text = document.createElement("span");
      text.textContent = step.label;
      const detail = document.createElement("small");
      detail.textContent = stepStatus[step.state][1] + (step.detail ? " · " + step.detail : "");
      text.append(detail);
      row.append(indicator, text);
      return row;
    }));
  }
  if (previous && transition) title.focus();
  previous = state;
}

async function call(endpoint, payload) {
  const response = await fetch(endpoint, payload === undefined ? {} : {
    method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Setup is unavailable.");
  return data;
}

function showError(error) {
  feedback.hidden = false;
  announce(feedback, error.message);
}

async function action(endpoint, payload = {}) {
  if (busy || closed) return;
  busy = true;
  actionVersion++;
  const buttons = document.querySelectorAll("button");
  buttons.forEach((button) => { button.disabled = true; });
  feedback.hidden = true;
  try {
    const state = await call(endpoint, payload);
    if (endpoint === "close") {
      closed = true;
      get("review").hidden = get("work").hidden = get("actions").hidden = true;
      announce(title, "Setup closed");
      announce(summary, "You can close this tab.");
      title.focus();
      return;
    }
    render(state);
  } catch (error) {
    showError(error);
  } finally {
    busy = false;
    buttons.forEach((button) => { button.disabled = false; });
    get("cancel").disabled = previous?.status === "stopping";
  }
}

install.addEventListener("click", () => action("start", Object.fromEntries(
  [...options.querySelectorAll("input")].map((input) => [input.name, input.checked])
)));
get("cancel").addEventListener("click", () => action("cancel"));
get("close").addEventListener("click", () => action("close"));
get("motion").addEventListener("change", (event) => {
  document.documentElement.classList.toggle("reduce-motion", event.target.checked);
});

async function refresh() {
  if (closed) return;
  if (!busy) {
    const version = actionVersion;
    try {
      const state = await call("state");
      if (!busy && !closed && version === actionVersion) render(state);
    } catch (error) {
      if (!busy && !closed && version === actionVersion) showError(error);
    }
  }
  if (!closed) setTimeout(refresh, 450);
}
refresh();
