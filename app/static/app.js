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

const CHUNK_SIZE = 4 * 1024 * 1024; // 4MB slices for fast, reliable Railway uploading

async function uploadFileInChunks(file, onProgress) {
  const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
  const uploadId = Date.now().toString(36) + Math.random().toString(36).substring(2, 9);
  let completedFilePath = null;

  for (let i = 0; i < totalChunks; i++) {
    const start = i * CHUNK_SIZE;
    const end = Math.min(file.size, start + CHUNK_SIZE);
    const chunkBlob = file.slice(start, end);

    const chunkFormData = new FormData();
    chunkFormData.append("upload_id", uploadId);
    chunkFormData.append("chunk_index", i);
    chunkFormData.append("total_chunks", totalChunks);
    chunkFormData.append("filename", file.name);
    chunkFormData.append("chunk", chunkBlob, file.name);

    let attempts = 0;
    let success = false;
    let responseData = null;

    while (attempts < 3 && !success) {
      try {
        attempts++;
        const res = await fetch("/api/upload_chunk", { method: "POST", body: chunkFormData });
        responseData = await res.json();
        if (res.ok) {
          success = true;
        } else {
          if (attempts >= 3) throw new Error(responseData.error || "Chunk upload failed");
          await new Promise(r => setTimeout(r, 1000));
        }
      } catch (err) {
        if (attempts >= 3) throw err;
        await new Promise(r => setTimeout(r, 1000));
      }
    }

    const progressPct = Math.round(((i + 1) / totalChunks) * 100);
    onProgress(progressPct);

    if (responseData && responseData.status === "complete") {
      completedFilePath = responseData.file_path;
    }
  }

  return completedFilePath;
}

async function startJob() {
  clearError();
  const file = fileInput.files[0];

  if (!file) {
    showError("Choose a video file to upload.");
    return;
  }

  startBtn.disabled = true;
  startBtn.textContent = "Uploading 0%…";

  const speedSelect = document.getElementById("speed-select");
  const lineModeSelect = document.getElementById("line-mode-select");
  const invertCheck = document.getElementById("invert-check");

  const speed = speedSelect ? speedSelect.value : "2";
  const lineMode = lineModeSelect ? lineModeSelect.value : "box";
  const invert = invertCheck ? invertCheck.checked : false;

  try {
    const uploadedFilePath = await uploadFileInChunks(file, (pct) => {
      startBtn.textContent = `Uploading ${pct}%…`;
    });

    startBtn.textContent = "Starting Analysis…";

    const startFormData = new FormData();
    if (uploadedFilePath) {
      startFormData.append("file_path", uploadedFilePath);
    }
    startFormData.append("filename", file.name);
    startFormData.append("speed", speed);
    startFormData.append("line_mode", lineMode);
    startFormData.append("invert", invert);

    const res = await fetch("/api/start", { method: "POST", body: startFormData });
    const data = await res.json();
    if (res.ok && data.job_id) {
      currentJobId = data.job_id;
      beginRunView();
    } else {
      showError(data.error || "Failed to start job.");
      resetStartBtn();
    }
  } catch (err) {
    showError("Upload error: " + err.message);
    resetStartBtn();
  }
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
