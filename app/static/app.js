const fileInput = document.getElementById("file-input");
const dropZone = document.getElementById("drop-zone");
const dropZoneText = document.getElementById("drop-zone-text");
const startBtn = document.getElementById("start-btn");
const cancelBtn = document.getElementById("cancel-btn");
const refreshBtn = document.getElementById("refresh-btn");
const errorMsg = document.getElementById("error-msg");

const setupCard = document.getElementById("setup-card");
const runCard = document.getElementById("run-card");
const runTitle = document.getElementById("run-title");
const streamImg = document.getElementById("stream-img");

const statCount = document.getElementById("stat-count");
const statProgress = document.getElementById("stat-progress");
const statStatus = document.getElementById("stat-status");
const progressFill = document.getElementById("progress-fill");

const historyBody = document.getElementById("history-body");

let currentJobId = null;
let pollTimer = null;

function showError(msg) {
  errorMsg.textContent = msg;
  errorMsg.hidden = false;
}

function clearError() {
  errorMsg.hidden = true;
  errorMsg.textContent = "";
}

async function startJob() {
  clearError();
  const file = fileInput.files[0];

  if (!file) {
    showError("Choose a video file to upload.");
    return;
  }

  startBtn.disabled = true;
  startBtn.textContent = "Starting…";

  const formData = new FormData();
  formData.append("file", file);
  formData.append("line_pos", document.getElementById("line-pos").value);
  formData.append("min_width", document.getElementById("min-width").value);
  formData.append("min_height", document.getElementById("min-height").value);

  try {
    const res = await fetch("/api/start", { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) {
      showError(data.error || "Failed to start job.");
      resetStartBtn();
      return;
    }
    currentJobId = data.job_id;
    beginRunView();
  } catch (err) {
    showError("Network error: " + err.message);
    resetStartBtn();
  }
}

function resetStartBtn() {
  startBtn.disabled = false;
  startBtn.textContent = "Start Counting";
}

function beginRunView() {
  runCard.hidden = false;
  runTitle.textContent = "Processing…";
  streamImg.src = `/api/stream/${currentJobId}?t=${Date.now()}`;
  statCount.textContent = "0";
  statProgress.textContent = "0%";
  statStatus.textContent = "starting";
  progressFill.style.width = "0%";
  runCard.scrollIntoView({ behavior: "smooth", block: "start" });
  pollTimer = setInterval(pollStatus, 500);
}

async function pollStatus() {
  if (!currentJobId) return;
  try {
    const res = await fetch(`/api/status/${currentJobId}`);
    const data = await res.json();
    if (!res.ok) return;

    statCount.textContent = data.count;
    statProgress.textContent = data.progress + "%";
    statStatus.textContent = data.status;
    progressFill.style.width = data.progress + "%";

    if (data.done) {
      clearInterval(pollTimer);
      pollTimer = null;
      runTitle.textContent = data.status === "finished" ? "Done" : "Stopped";
      resetStartBtn();
      currentJobId = null;
      loadHistory();
    }
  } catch (err) {
    // transient network hiccup, keep polling
  }
}

async function cancelJob() {
  if (!currentJobId) return;
  await fetch(`/api/cancel/${currentJobId}`, { method: "POST" });
}

function fmtWhen(ts) {
  if (!ts) return "–";
  const d = new Date(ts * 1000);
  return d.toLocaleString();
}

function fmtDuration(sec) {
  if (sec == null) return "–";
  if (sec < 60) return `${sec.toFixed(1)}s`;
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}m ${s}s`;
}

async function loadHistory() {
  try {
    const res = await fetch("/api/history");
    const items = await res.json();
    if (!items.length) {
      historyBody.innerHTML = `<tr><td colspan="6" class="empty">No runs yet</td></tr>`;
      return;
    }
    historyBody.innerHTML = items.map(item => `
      <tr>
        <td>${fmtWhen(item.started_at)}</td>
        <td>${escapeHtml(item.video || "")}</td>
        <td>${item.count}</td>
        <td>${item.total_frames}</td>
        <td>${fmtDuration(item.duration_sec)}</td>
        <td class="status-${item.status}">${item.status}</td>
      </tr>
    `).join("");
  } catch (err) {
    // ignore
  }
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function updateDropZoneLabel() {
  const file = fileInput.files[0];
  if (file) {
    dropZoneText.innerHTML = `Selected: <span class="file-name">${escapeHtml(file.name)}</span>`;
  } else {
    dropZoneText.textContent = "Drag & drop a video here, or click to choose a file";
  }
}

startBtn.addEventListener("click", startJob);
cancelBtn.addEventListener("click", cancelJob);
refreshBtn.addEventListener("click", loadHistory);

dropZone.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", () => {
  clearError();
  updateDropZoneLabel();
});

["dragenter", "dragover"].forEach(evt => {
  dropZone.addEventListener(evt, (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropZone.classList.add("dragover");
  });
});

["dragleave", "dragend"].forEach(evt => {
  dropZone.addEventListener(evt, (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropZone.classList.remove("dragover");
  });
});

dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  e.stopPropagation();
  dropZone.classList.remove("dragover");
  const dropped = e.dataTransfer.files;
  if (dropped.length) {
    fileInput.files = dropped;
    clearError();
    updateDropZoneLabel();
  }
});

loadHistory();
