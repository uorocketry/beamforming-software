const events = new EventSource("/events");
const calibratedPhaseDegrees = [];

fetch("/static/phase_lookup_2_4ghz.csv")
  .then((response) => {
    if (!response.ok) throw new Error("Phase calibration table unavailable");
    return response.text();
  })
  .then((csv) => {
    for (const row of csv.trim().split(/\r?\n/).slice(1)) {
      const columns = row.split(",");
      calibratedPhaseDegrees[Number(columns[0])] = Number(columns[6]);
    }
    for (const input of document.querySelectorAll('.node-controls input[name="phase_state"]')) {
      updateSliderValue(input);
    }
  })
  .catch(() => {
    // The target angle remains available from the uniformly spaced state index.
  });

function phaseDescription(state) {
  const calibrated = calibratedPhaseDegrees[state];
  const degrees = Number.isFinite(calibrated) ? calibrated : state * 360 / 256;
  return `${degrees.toFixed(2)}° (state ${state})`;
}

function updateSliderValue(input) {
  const output = input.closest(".node-controls")?.querySelector(
    `[data-value-for="${input.name}"]`,
  );
  if (!output) return;
  output.textContent = input.name === "attenuation_db"
    ? `${input.value} dB`
    : phaseDescription(Number(input.value));
}

events.addEventListener("update", (event) => {
  const update = JSON.parse(event.data);
  const element = document.getElementById(update.id);
  if (!element) return;

  if ("text" in update && element.textContent !== update.text) {
    element.textContent = update.text;
  }
  if ("className" in update && element.className !== update.className) {
    element.className = update.className;
  }
  if ("hidden" in update && element.hidden !== update.hidden) {
    element.hidden = update.hidden;
  }
  if ("html" in update && element.innerHTML.trim() !== update.html.trim()) {
    element.innerHTML = update.html;
  }
});

const applyTimers = new WeakMap();

async function sendCommand(form, action) {
  const output = form.querySelector(".command-result");
  const payload = { action };
  if (action === "combined") {
    payload.phase_state = Number(form.elements.phase_state.value);
    payload.attenuation_db = Number(form.elements.attenuation_db.value);
  }

  if (form.dataset.sending === "true") {
    form.dataset.queued = "true";
    return;
  }
  form.dataset.sending = "true";
  for (const button of form.querySelectorAll("button")) button.disabled = true;
  output.className = "command-result pending";
  output.textContent = action === "safe" ? "Applying safe state…" : "Applying…";
  try {
    const response = await fetch(`/api/nodes/${form.dataset.nodeId}/commands`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) {
      const error = new Error(result.error || "Command failed");
      error.detail = result.detail;
      throw error;
    }
    output.className = "command-result success";
    if (action === "safe") {
      form.elements.phase_state.value = 0;
      form.elements.attenuation_db.value = 23;
      updateSliderValue(form.elements.phase_state);
      updateSliderValue(form.elements.attenuation_db);
      output.textContent = `Safe state acknowledged · ${phaseDescription(0)} · 23 dB`;
    } else {
      output.textContent = `Acknowledged · ${phaseDescription(payload.phase_state)} · ${payload.attenuation_db} dB`;
    }
  } catch (error) {
    output.className = "command-result error";
    output.textContent = error.detail ? `${error.message} ${error.detail}` : error.message;
  } finally {
    form.dataset.sending = "false";
    for (const button of form.querySelectorAll("button")) button.disabled = false;
    if (form.dataset.queued === "true") {
      form.dataset.queued = "false";
      void sendCommand(form, "combined");
    }
  }
}

document.addEventListener("input", (event) => {
  if (!event.target.matches('.node-controls input[type="range"]')) return;
  updateSliderValue(event.target);
  const form = event.target.closest(".node-controls");
  const output = form.querySelector(".command-result");
  output.className = "command-result pending";
  output.textContent = "Waiting to apply…";
  clearTimeout(applyTimers.get(form));
  applyTimers.set(form, setTimeout(() => void sendCommand(form, "combined"), 150));
});

document.addEventListener("change", (event) => {
  if (!event.target.matches('.node-controls input[type="range"]')) return;
  const form = event.target.closest(".node-controls");
  clearTimeout(applyTimers.get(form));
  void sendCommand(form, "combined");
});

document.addEventListener("click", (event) => {
  const button = event.target.closest('.node-controls button[data-action="safe"]');
  if (!button) return;
  const form = button.closest(".node-controls");
  clearTimeout(applyTimers.get(form));
  void sendCommand(form, "safe");
});
