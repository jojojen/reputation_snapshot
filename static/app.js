const i18n = window._i18n || {};

const form = document.getElementById("capture-form");
const resultMessage = document.getElementById("result-message");
const resultJson = document.getElementById("result-json");
const resultActions = document.getElementById("result-actions");
const statusBadge = document.getElementById("status-badge");

const progressMessages = [
  i18n.js_progress_1 || "Parsing the URL and identifying the seller\u2026",
  i18n.js_progress_2 || "Checking for an existing snapshot\u2026",
  i18n.js_progress_3 || "No existing snapshot \u2014 creating a new one, this may take a few seconds\u2026",
];

let progressTimers = [];

function setStatus(state, label) {
  statusBadge.textContent = label;
  statusBadge.className = `status-badge ${state}`;
}

function clearProgressTimers() {
  progressTimers.forEach((timer) => window.clearTimeout(timer));
  progressTimers = [];
}

function scheduleProgressMessages() {
  clearProgressTimers();
  progressMessages.forEach((message, index) => {
    const timer = window.setTimeout(() => {
      resultMessage.textContent = message;
    }, index * 1400);
    progressTimers.push(timer);
  });
}

function renderActions(data) {
  resultActions.innerHTML = "";
  if (!data || !data.proof_url) {
    return;
  }

  const link = document.createElement("a");
  link.href = data.proof_url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = i18n.js_proof_link || "If not redirected automatically, click here";
  link.className = "action-link";
  resultActions.appendChild(link);
}

function redirectToProof(proofUrl) {
  window.setTimeout(() => {
    window.open(proofUrl, "_blank", "noopener,noreferrer");
  }, 700);
}

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  setStatus("loading", i18n.js_loading || "Loading\u2026");
  resultActions.innerHTML = "";
  resultJson.hidden = true;
  resultJson.textContent = "";
  scheduleProgressMessages();

  const formData = new FormData(form);
  const payload = {
    query_url: String(formData.get("query_url") || "").trim(),
  };

  try {
    const response = await fetch("/api/captures", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || "Capture failed.");
    }

    clearProgressTimers();
    renderActions(data);

    const name = data.display_name || "?";
    if (data.reused) {
      setStatus("success", i18n.js_found_label || "Found");
      resultMessage.textContent = (i18n.js_reused_message || "Existing snapshot found for {name}. Redirecting\u2026").replace("{name}", name);
    } else {
      setStatus("success", i18n.js_created_label || "Created");
      resultMessage.textContent = (i18n.js_created_message || "Snapshot created for {name}. Redirecting\u2026").replace("{name}", name);
    }

    redirectToProof(data.proof_url);
  } catch (error) {
    clearProgressTimers();
    setStatus("error", i18n.js_error_label || "Error");
    resultMessage.textContent = error.message || (i18n.js_error_message || "Could not create snapshot. Please try again.");
  }
});
