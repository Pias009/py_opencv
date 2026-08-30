const fileInput = document.getElementById("file-input");
const dropZone = document.getElementById("drop-zone");
const dropZoneText = document.getElementById("drop-zone-text");
const startBtn = document.getElementById("start-btn");
const cancelBtn = document.getElementById("cancel-btn");
const refreshBtn = document.getElementById("refresh-btn");
const errorMsg = document.getElementById("error-msg");

const setupCard = document.getElementById("setup-card");
const runCard = document.getElementById("run-card");
const reportCard = document.getElementById("report-card");
const runTitle = document.getElementById("run-title");
const streamImg = document.getElementById("stream-img");

const statProgress = document.getElementById("stat-progress");
const statFrames = document.getElementById("stat-frames");
const progressFill = document.getElementById("progress-fill");

const sideTotal = document.getElementById("side-total");
const sideStatus = document.getElementById("side-status");
const sideLinesBlock = document.getElementById("side-lines-block");
const lineRows = document.getElementById("line-rows");
const sideCategoriesBlock = document.getElementById("side-categories-block");
const categoryRows = document.getElementById("category-rows");
const sideMetaBlock = document.getElementById("side-meta-block");
const metaSpeed = document.getElementById("meta-speed");
const metaReanalyzed = document.getElementById("meta-reanalyzed");
const metaModel = document.getElementById("meta-model");

const reportCountLabel = document.getElementById("report-count-label");
const downloadPdf = document.getElementById("download-pdf");
const downloadXlsx = document.getElementById("download-xlsx");
const newVideoBtn = document.getElementById("new-video-btn");

const historyBody = document.getElementById("history-body");

const LINE_COLORS = ["#4f8cff", "#ff7a45", "#3ddc84", "#ff5c5c", "#c084fc", "#facc15"];

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

let activeSourceMode = "local"; // "local", "upload", "camera"

const tabLocalBtn = document.getElementById("tab-local-btn");
const tabUploadBtn = document.getElementById("tab-upload-btn");
const tabCameraBtn = document.getElementById("tab-camera-btn");

const sourceLocalBlock = document.getElementById("source-local-block");
const sourceUploadBlock = document.getElementById("source-upload-block");
const sourceCameraBlock = document.getElementById("source-camera-block");

const localPathInput = document.getElementById("local-path-input");
const localQuickSelect = document.getElementById("local-quick-select");
const cameraUrlInput = document.getElementById("camera-url-input");

function setSourceMode(mode) {
  activeSourceMode = mode;
  [tabLocalBtn, tabUploadBtn, tabCameraBtn].forEach(btn => btn && btn.classList.remove("active"));
  [sourceLocalBlock, sourceUploadBlock, sourceCameraBlock].forEach(block => block && (block.hidden = true));

  if (mode === "local") {
    tabLocalBtn && tabLocalBtn.classList.add("active");
    sourceLocalBlock && (sourceLocalBlock.hidden = false);
  } else if (mode === "upload") {
    tabUploadBtn && tabUploadBtn.classList.add("active");
    sourceUploadBlock && (sourceUploadBlock.hidden = false);
  } else if (mode === "camera") {
    tabCameraBtn && tabCameraBtn.classList.add("active");
    sourceCameraBlock && (sourceCameraBlock.hidden = false);
  }
}

tabLocalBtn && tabLocalBtn.addEventListener("click", () => setSourceMode("local"));
tabUploadBtn && tabUploadBtn.addEventListener("click", () => setSourceMode("upload"));
tabCameraBtn && tabCameraBtn.addEventListener("click", () => setSourceMode("camera"));

async function loadLocalQuickSelect() {
  try {
    const res = await fetch("/api/list_local_videos");
    const files = await res.json();
    if (res.ok && files.length) {
      localQuickSelect.innerHTML = `<option value="">Quick Select...</option>` +
        files.map(f => `<option value="${escapeHtml(f.path)}">${escapeHtml(f.name)}</option>`).join("");
    }
  } catch (e) {}
}
loadLocalQuickSelect();

if (localQuickSelect) {
  localQuickSelect.addEventListener("change", () => {
    if (localQuickSelect.value) {
      localPathInput.value = localQuickSelect.value;
    }
  });
}

async function startJob() {
  clearError();

  const speedSelect = document.getElementById("speed-select");
  const lineModeSelect = document.getElementById("line-mode-select");
  const invertCheck = document.getElementById("invert-check");

  const speed = speedSelect ? speedSelect.value : "2";
  const lineMode = lineModeSelect ? lineModeSelect.value : "box";
  const invert = invertCheck ? invertCheck.checked : false;

  const formData = new FormData();
  formData.append("speed", speed);
  formData.append("line_mode", lineMode);
  formData.append("invert", invert);

  if (activeSourceMode === "local") {
    const localPath = localPathInput ? localPathInput.value.trim() : "";
    if (!localPath) {
      showError("Enter a local video file path.");
      return;
    }
    formData.append("source_type", "local");
    formData.append("local_path", localPath);
    startBtn.disabled = true;
    startBtn.textContent = "Starting Local Video…";
  } else if (activeSourceMode === "camera") {
    const cameraUrl = cameraUrlInput ? cameraUrlInput.value.trim() : "0";
    formData.append("source_type", "camera");
    formData.append("local_path", cameraUrl);
    startBtn.disabled = true;
    startBtn.textContent = "Connecting Camera…";
  } else {
    const file = fileInput.files[0];
    if (!file) {
      showError("Choose a video file to upload.");
      return;
    }
    formData.append("source_type", "upload");
    formData.append("file", file);
    startBtn.disabled = true;
    startBtn.textContent = "Uploading 0%…";
  }

  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/start", true);

  if (activeSourceMode === "upload") {
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        const pct = Math.round((e.loaded / e.total) * 100);
        startBtn.textContent = `Uploading ${pct}%…`;
      }
    };
  }

  xhr.onload = () => {
    try {
      const data = JSON.parse(xhr.responseText);
      if (xhr.status >= 200 && xhr.status < 300 && data.job_id) {
        currentJobId = data.job_id;
        beginRunView();
      } else {
        showError(data.error || "Failed to start job.");
        resetStartBtn();
      }
    } catch (err) {
      showError("Server response error: " + err.message);
      resetStartBtn();
    }
  };

  xhr.onerror = () => {
    showError("Network error. Please check connection and try again.");
    resetStartBtn();
  };

  xhr.send(formData);
}

function resetStartBtn() {
  startBtn.disabled = false;
  startBtn.textContent = "Start Counting";
}

function resetCancelBtn() {
  cancelBtn.disabled = false;
  cancelBtn.textContent = "🛑 Stop & Get PDF";
}

function beginRunView() {
  reportCard.hidden = true;
  runCard.hidden = false;
  runTitle.textContent = "Processing…";
  streamImg.src = `/api/stream/${currentJobId}?t=${Date.now()}`;
  statProgress.textContent = "0%";
  statFrames.textContent = "";
  progressFill.style.width = "0%";
  resetCancelBtn();

  sideTotal.textContent = "0";
  sideStatus.textContent = "Starting…";
  sideStatus.classList.add("is-live");
  sideLinesBlock.hidden = true;
  sideCategoriesBlock.hidden = true;
  sideMetaBlock.hidden = true;

  runCard.scrollIntoView({ behavior: "smooth", block: "start" });
  pollTimer = setInterval(pollStatus, 500);
}

function renderLines(lines) {
  const entries = Object.entries(lines || {});
  if (!entries.length) {
    sideLinesBlock.hidden = true;
    return;
  }
  sideLinesBlock.hidden = false;
  lineRows.innerHTML = entries.map(([name, v], i) => `
    <div class="line-row">
      <span class="line-row-name">
        <span class="line-dot" style="background:${LINE_COLORS[i % LINE_COLORS.length]}"></span>
        ${escapeHtml(name)}
      </span>
      <span class="line-row-counts">in ${v.in} &middot; out ${v.out}</span>
    </div>
  `).join("");
}

function renderCategories(categories) {
  const entries = Object.entries(categories || {}).sort((a, b) => b[1] - a[1]);
  if (!entries.length) {
    sideCategoriesBlock.hidden = true;
    return;
  }
  sideCategoriesBlock.hidden = false;
  categoryRows.innerHTML = entries.map(([name, count]) => `
    <div class="category-row">
      <span class="category-row-name">${escapeHtml(name)}</span>
      <span class="category-row-count">${count}</span>
    </div>
  `).join("");
}

async function pollStatus() {
  if (!currentJobId) return;
  try {
    const res = await fetch(`/api/status/${currentJobId}`);
    const data = await res.json();
    if (!res.ok) return;

    sideTotal.textContent = data.count;
    statProgress.textContent = data.progress + "%";
    statFrames.textContent = data.total_frames ? `frame ${data.frame_idx}/${data.total_frames}` : "";
    progressFill.style.width = data.progress + "%";

    renderLines(data.lines);
    renderCategories(data.categories);

    if (data.speed_mode || data.reanalyzed) {
      sideMetaBlock.hidden = false;
      metaSpeed.textContent = data.speed_mode || "full";
      metaReanalyzed.textContent = data.reanalyzed || 0;
      metaModel.textContent = data.model_used || "–";
    }

    if (data.done) {
      clearInterval(pollTimer);
      pollTimer = null;
      const ok = data.status === "finished";
      const isStopped = data.status === "cancelled";
      runTitle.textContent = ok ? "Done" : (isStopped ? "Analysis Stopped" : "Error");
      sideStatus.textContent = ok ? "Finished" : (isStopped ? "Stopped by user" : (data.error || "Error"));
      sideStatus.classList.remove("is-live");
      resetStartBtn();
      resetCancelBtn();

      if (data.report_pdf) {
        reportCountLabel.textContent = `${data.count} vehicles counted ${isStopped ? "(Partial Analysis)" : ""}`;
        downloadPdf.href = data.report_pdf;
        downloadXlsx.href = data.report_xlsx;
        reportCard.hidden = false;
        reportCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }

      currentJobId = null;
      loadHistory();
    }
  } catch (err) {
    // transient network hiccup, keep polling
  }
}

async function cancelJob() {
  if (!currentJobId) return;
  cancelBtn.disabled = true;
  cancelBtn.textContent = "Generating PDF…";
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

function startNewVideo() {
  fileInput.value = "";
  updateDropZoneLabel();
  clearError();
  resetStartBtn();
  resetCancelBtn();
  reportCard.hidden = true;
  runCard.hidden = true;
  setupCard.hidden = false;
  setupCard.scrollIntoView({ behavior: "smooth", block: "start" });
}

const invertLiveBtn = document.getElementById("invert-live-btn");

if (invertLiveBtn) {
  invertLiveBtn.addEventListener("click", async () => {
    if (!currentJobId) return;
    try {
      const res = await fetch(`/api/invert/${currentJobId}`, { method: "POST" });
      const data = await res.json();
      if (res.ok) {
        invertLiveBtn.textContent = data.inverted ? "🔄 Direction Swapped (IN ↔ OUT)" : "🔄 Switch IN/OUT Direction";
      }
    } catch (e) {
      // ignore
    }
  });
}

startBtn.addEventListener("click", startJob);
cancelBtn.addEventListener("click", cancelJob);
refreshBtn.addEventListener("click", loadHistory);
newVideoBtn.addEventListener("click", startNewVideo);

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
