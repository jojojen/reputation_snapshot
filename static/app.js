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

async function pollJob(jobId) {
  const maxWait = 5 * 60 * 1000; // 5 minutes
  const interval = 4000;
  const started = Date.now();

  while (Date.now() - started < maxWait) {
    await new Promise((r) => window.setTimeout(r, interval));
    const resp = await fetch(`/api/jobs/${jobId}`);
    const data = await resp.json();

    if (data.status === "done") return data;
    if (data.status === "failed") throw new Error(data.error || "Capture failed.");
    // still pending/processing — keep polling
  }
  throw new Error("Timed out waiting for capture agent. Is it running?");
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

    // Immediate reuse — no job needed
    if (data.reused) {
      clearProgressTimers();
      renderActions(data);
      setStatus("success", i18n.js_found_label || "Found");
      resultMessage.textContent = i18n.js_reused_message || "Existing snapshot found. Redirecting\u2026";
      redirectToProof(data.proof_url);
      return;
    }

    // Job queued — poll until agent completes it
    resultMessage.textContent = i18n.js_queued_message || "Queued — waiting for capture agent\u2026";
    const result = await pollJob(data.job_id);

    clearProgressTimers();
    renderActions(result);
    setStatus("success", i18n.js_created_label || "Created");
    resultMessage.textContent = i18n.js_created_message || "Snapshot created. Redirecting\u2026";
    redirectToProof(result.proof_url);
  } catch (error) {
    clearProgressTimers();
    setStatus("error", i18n.js_error_label || "Error");
    resultMessage.textContent = error.message || (i18n.js_error_message || "Could not create snapshot. Please try again.");
  }
});
