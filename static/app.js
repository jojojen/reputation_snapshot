const form = document.getElementById("capture-form");
const resultMessage = document.getElementById("result-message");
const resultJson = document.getElementById("result-json");
const resultActions = document.getElementById("result-actions");
const statusBadge = document.getElementById("status-badge");

function setStatus(state, label) {
  statusBadge.textContent = label;
  statusBadge.className = `status-badge ${state}`;
}

function renderActions(data) {
  resultActions.innerHTML = "";
  if (!data || !data.proof_url) {
    return;
  }

  const link = document.createElement("a");
  link.href = data.proof_url;
  link.textContent = "開啟 Proof Page";
  link.className = "action-link";
  resultActions.appendChild(link);
}

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  setStatus("loading", "執行中");
  resultMessage.textContent = "正在擷取頁面並建立 proof，這可能需要數秒。";
  resultJson.textContent = "";
  resultActions.innerHTML = "";

  const formData = new FormData(form);
  const payload = {
    profile_url: String(formData.get("profile_url") || ""),
    expires_in_days: Number(formData.get("expires_in_days") || 30),
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

    setStatus("success", "完成");
    resultMessage.textContent = `已建立 capture ${data.capture_id} 與 proof ${data.proof_id}。`;
    resultJson.textContent = JSON.stringify(data, null, 2);
    renderActions(data);
  } catch (error) {
    setStatus("error", "失敗");
    resultMessage.textContent = error.message || "發生未預期錯誤。";
    resultJson.textContent = "";
  }
});
