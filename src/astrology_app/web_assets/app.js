const form = document.querySelector("#reading-form");
const generateButton = document.querySelector("#generate-btn");
const resetButton = document.querySelector("#reset-btn");
const errorBox = document.querySelector("#form-error");
const emptySummary = document.querySelector("#empty-summary");
const summaryContent = document.querySelector("#summary-content");
const categoryValue = document.querySelector("#category-value");
const timezoneValue = document.querySelector("#timezone-value");
const engineValue = document.querySelector("#engine-value");
const exportsValue = document.querySelector("#exports-value");
const enginePill = document.querySelector("#engine-pill");
const interpretationAnswer = document.querySelector("#interpretation-answer");
const promptOutput = document.querySelector("#prompt-output");
const readingInput = document.querySelector("#reading-input");
const evidenceKeys = document.querySelector("#evidence-keys");
const copyPrompt = document.querySelector("#copy-prompt");

document.querySelectorAll(".tab").forEach((button) => {
  button.addEventListener("click", () => activateTab(button.dataset.tab));
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorBox.textContent = "";
  setBusy(true);

  try {
    const response = await fetch("/api/readings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(formPayload(new FormData(form))),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Unable to generate reading.");
    }
    renderReading(payload);
    activateTab("summary");
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    setBusy(false);
  }
});

resetButton.addEventListener("click", () => {
  form.reset();
  errorBox.textContent = "";
});

copyPrompt.addEventListener("click", async () => {
  if (!promptOutput.value.trim()) {
    return;
  }
  await navigator.clipboard.writeText(promptOutput.value);
  copyPrompt.textContent = "Copied";
  window.setTimeout(() => {
    copyPrompt.textContent = "Copy Prompt";
  }, 1200);
});

function formPayload(data) {
  return {
    date_of_birth: data.get("date_of_birth"),
    time_of_birth: data.get("time_of_birth"),
    birth_place: data.get("birth_place"),
    timezone: data.get("timezone"),
    question: data.get("question"),
    client_context: data.get("client_context"),
    answer_style: data.get("answer_style"),
    comprehensive_reading: data.get("comprehensive_reading") === "on",
    requested_chart_keys: commaList(data.get("requested_chart_keys")),
    prediction_start: data.get("prediction_start"),
    prediction_end: data.get("prediction_end"),
    prediction_step: data.get("prediction_step"),
  };
}

function commaList(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function renderReading(payload) {
  emptySummary.classList.add("hidden");
  summaryContent.classList.remove("hidden");

  categoryValue.textContent = payload.category || "general";
  timezoneValue.textContent = `${payload.birth_input.timezone || ""} (${payload.birth_input.timezone_source || "unknown"})`;
  engineValue.textContent = payload.chart_source || "unknown";
  enginePill.textContent = payload.chart_status === "mock-data-for-development" ? "Mock" : "Ready";
  exportsValue.textContent = payload.export_paths?.prompt ? "Saved locally" : "Not saved";
  interpretationAnswer.textContent = payload.interpretation_answer || "";
  promptOutput.value = payload.llm_prompt || "";
  readingInput.textContent = JSON.stringify(payload.reading_input || {}, null, 2);

  evidenceKeys.replaceChildren();
  (payload.evidence_keys || []).forEach((key) => {
    const item = document.createElement("li");
    item.textContent = key;
    evidenceKeys.appendChild(item);
  });
}

function activateTab(name) {
  document.querySelectorAll(".tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === name);
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === `${name}-tab`);
  });
}

function setBusy(isBusy) {
  generateButton.disabled = isBusy;
  generateButton.textContent = isBusy ? "Generating..." : "Generate Chart Desk";
}
