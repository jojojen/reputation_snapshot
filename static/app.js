const form = document.getElementById("capture-form");
const resultMessage = document.getElementById("result-message");
const resultJson = document.getElementById("result-json");
const resultActions = document.getElementById("result-actions");
const statusBadge = document.getElementById("status-badge");

const progressMessages = [
  "正在解析商品連結，找出賣家資訊…",
  "正在檢查這位賣家是否已有可用快照…",
  "若沒有既有快照，系統會自動建立新的快照，通常需要幾秒鐘…",
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
  link.textContent = "若未自動跳轉，點此開啟 proof 頁面";
  link.className = "action-link";
  resultActions.appendChild(link);
}

function redirectToProof(proofUrl) {
  window.setTimeout(() => {
    window.location.assign(proofUrl);
  }, 700);
}

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  setStatus("loading", "查詢中");
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

    if (data.reused) {
      setStatus("success", "已找到");
      resultMessage.textContent = `已找到 ${data.display_name || "這位賣家"} 的既有快照，正在前往 proof 頁面…`;
    } else {
      setStatus("success", "已建立");
      resultMessage.textContent = `${data.display_name || "賣家"} 的快照已建立完成，正在前往 proof 頁面…`;
    }

    redirectToProof(data.proof_url);
  } catch (error) {
    clearProgressTimers();
    setStatus("error", "查詢失敗");
    resultMessage.textContent = error.message || "目前無法建立快照，請稍後再試。";
  }
});
