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

async function uploadFileInChunks(file, onProgress) {
  // Ultra-fast single-pass XHR upload with real-time hardware progress for files <= 32MB
  if (file.size <= 32 * 1024 * 1024) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const formData = new FormData();
      const uploadId = Date.now().toString(36) + Math.random().toString(36).substring(2, 9);

      formData.append("upload_id", uploadId);
      formData.append("chunk_index", 0);
      formData.append("total_chunks", 1);
      formData.append("filename", file.name);
      formData.append("chunk", file, file.name);

      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          const pct = Math.round((e.loaded / e.total) * 100);
          onProgress(pct);
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const data = JSON.parse(xhr.responseText);
            resolve(data.file_path);
          } catch (err) {
            reject(err);
          }
        } else {
          reject(new Error("Upload failed"));
        }
      };

      xhr.onerror = () => reject(new Error("Network error during upload"));
      xhr.open("POST", "/api/upload_chunk", true);
      xhr.send(formData);
    });
  }

  // 16MB chunking for maximum multi-megabyte throughput on large video streams
  const FAST_CHUNK_SIZE = 16 * 1024 * 1024;
  const totalChunks = Math.ceil(file.size / FAST_CHUNK_SIZE);
  const uploadId = Date.now().toString(36) + Math.random().toString(36).substring(2, 9);
  let completedFilePath = null;

  for (let i = 0; i < totalChunks; i++) {
    const start = i * FAST_CHUNK_SIZE;
    const end = Math.min(file.size, start + FAST_CHUNK_SIZE);
    const chunkBlob = file.slice(start, end);

    const chunkFormData = new FormData();
    chunkFormData.append("upload_id", uploadId);
    chunkFormData.append("chunk_index", i);
    chunkFormData.append("total_chunks", totalChunks);
    chunkFormData.append("filename", file.name);
    chunkFormData.append("chunk", chunkBlob, file.name);

    const res = await fetch("/api/upload_chunk", { method: "POST", body: chunkFormData });
    const responseData = await res.json();

    const progressPct = Math.round(((i + 1) / totalChunks) * 100);
    onProgress(progressPct);

    if (responseData && responseData.status === "complete") {
      completedFilePath = responseData.file_path;
    }
  }

  return completedFilePath;
}

// Dynamic Left Sidebar Shift & Live Rules Updater
function updateSidebarRules() {
  const sideNaming = document.getElementById("side-naming-val");
  const sideIn = document.getElementById("side-in-val");
  const sideOut = document.getElementById("side-out-val");
  const sideLines = document.getElementById("side-lines-val");

  const toggleIn = document.getElementById("toggle-in");
  const toggleOut = document.getElementById("toggle-out");
  const badgeIn = document.getElementById("badge-in");
  const badgeOut = document.getElementById("badge-out");

  const directionModeSelect = document.getElementById("direction-mode-select");
  const directionMode = directionModeSelect ? directionModeSelect.value : "COMING_GOING";

  let namingStr = "COMING / GOING";
  let flow1Title = "🚘 Coming Flow (Front / Facing Camera)";
  let flow1Sub = "Count vehicles moving forward showing front face towards camera";
  let flow2Title = "🚗 Going Flow (Back / Receding Camera)";
  let flow2Sub = "Count vehicles moving backward seeing tail / back away from camera";

  if (directionMode === "FORWARD_BACKWARD") {
    namingStr = "FORWARD / BACKWARD";
    flow1Title = "⬆️ Forward Direction Flow";
    flow1Sub = "Count vehicles moving in forward traffic lanes";
    flow2Title = "⬇️ Backward Direction Flow";
    flow2Sub = "Count vehicles moving in backward / reverse traffic lanes";
  } else if (directionMode === "IN_OUT") {
    namingStr = "IN / OUT";
    flow1Title = "🟢 IN Flow (Incoming Boundary)";
    flow1Sub = "Count vehicles entering boundary zone";
    flow2Title = "🔴 OUT Flow (Outgoing Boundary)";
    flow2Sub = "Count vehicles exiting boundary zone";
  }

  const flow1TitleEl = document.getElementById("flow1-title");
  const flow1SubEl = document.getElementById("flow1-sub");
  const flow2TitleEl = document.getElementById("flow2-title");
  const flow2SubEl = document.getElementById("flow2-sub");

  if (flow1TitleEl) flow1TitleEl.textContent = flow1Title;
  if (flow1SubEl) flow1SubEl.textContent = flow1Sub;
  if (flow2TitleEl) flow2TitleEl.textContent = flow2Title;
  if (flow2SubEl) flow2SubEl.textContent = flow2Sub;

  if (sideNaming) sideNaming.textContent = namingStr;

  const inChecked = document.querySelectorAll(".line-in-check:checked").length;
  const outChecked = document.querySelectorAll(".line-out-check:checked").length;
  const totalActiveRules = (toggleIn && toggleIn.checked ? inChecked : 0) + (toggleOut && toggleOut.checked ? outChecked : 0);

  if (sideIn && toggleIn) {
    sideIn.textContent = toggleIn.checked ? `ENABLED (${inChecked} Sides)` : "OFF";
    sideIn.style.color = toggleIn.checked ? "#3ddc84" : "var(--text-dim)";
    if (badgeIn) badgeIn.textContent = toggleIn.checked ? "ACTIVE" : "OFF";
  }

  if (sideOut && toggleOut) {
    sideOut.textContent = toggleOut.checked ? `ENABLED (${outChecked} Sides)` : "OFF";
    sideOut.style.color = toggleOut.checked ? "#ff4d4d" : "var(--text-dim)";
    if (badgeOut) badgeOut.textContent = toggleOut.checked ? "ACTIVE" : "OFF";
  }

  if (sideLines) {
    sideLines.textContent = `${totalActiveRules} Active Rule${totalActiveRules !== 1 ? 's' : ''}`;
  }

  pushLiveRuleUpdate();
}

async function pushLiveRuleUpdate() {
  if (!currentJobId) return;
  const toggleIn = document.getElementById("toggle-in");
  const toggleOut = document.getElementById("toggle-out");
  const countScopeRadio = document.querySelector('input[name="count_scope_mode"]:checked');
  const directionModeSelect = document.getElementById("direction-mode-select");

  const enableIn = toggleIn ? toggleIn.checked : true;
  const enableOut = toggleOut ? toggleOut.checked : true;
  const countScopeMode = countScopeRadio ? countScopeRadio.value : "active_only";
  const directionMode = directionModeSelect ? directionModeSelect.value : "COMING_GOING";

  const enabledLinesIn = Array.from(document.querySelectorAll(".line-in-check:checked")).map(c => c.value);
  const enabledLinesOut = Array.from(document.querySelectorAll(".line-out-check:checked")).map(c => c.value);
  const allEnabledLines = Array.from(new Set([...enabledLinesIn, ...enabledLinesOut]));

  try {
    await fetch(`/api/update_rules/${currentJobId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        direction_mode: directionMode,
        enable_in: enableIn,
        enable_out: enableOut,
        count_scope_mode: countScopeMode,
        enabled_lines: allEnabledLines,
        enabled_lines_in: enabledLinesIn,
        enabled_lines_out: enabledLinesOut
      })
    });
  } catch (e) {
    console.error("Live rule update error:", e);
  }
}

// Master switch: Toggle all side lines ON / OFF
const masterToggleBtn = document.getElementById("master-toggle-btn");
if (masterToggleBtn) {
  let allLinesOn = true;
  masterToggleBtn.addEventListener("click", () => {
    allLinesOn = !allLinesOn;
    document.querySelectorAll(".line-in-check, .line-out-check").forEach(chk => chk.checked = allLinesOn);
    masterToggleBtn.textContent = allLinesOn ? "⚡ Toggle All Sides (OFF)" : "⚡ Toggle All Sides (ON)";
    updateSidebarRules();
  });
}

// 1-Side Lane Preset Handler
const preset1SideBtn = document.getElementById("preset-1side-btn");
if (preset1SideBtn) {
  preset1SideBtn.addEventListener("click", () => {
    const lineModeSelect = document.getElementById("line-mode-select");
    const toggleIn = document.getElementById("toggle-in");
    const toggleOut = document.getElementById("toggle-out");

    if (lineModeSelect) lineModeSelect.value = "vertical";
    if (toggleIn) toggleIn.checked = true;
    if (toggleOut) toggleOut.checked = false;

    // Check North IN, uncheck others
    document.querySelectorAll(".line-in-check").forEach(chk => chk.checked = (chk.value === "North"));
    document.querySelectorAll(".line-out-check").forEach(chk => chk.checked = false);

    updateSidebarRules();
    alert("🚗 Configured for 1-Side Lane Counting!\n- Flow: IN Only (OUT Disabled)\n- Active Lane: North IN Side\n\nOnly vehicles entering through North IN will be counted in Total Vehicle Count.");
  });
}

// Hover Shift Effect on Left Sidebar
const sideConfigBlock = document.getElementById("side-config-block");
const sideHoverTip = document.getElementById("sidebar-hover-tip");

document.querySelectorAll("[data-tip]").forEach(elem => {
  elem.addEventListener("mouseenter", () => {
    const tip = elem.getAttribute("data-tip");
    if (sideConfigBlock) {
      sideConfigBlock.style.transform = "translateX(8px)";
      sideConfigBlock.style.borderColor = "#3ddc84";
      sideConfigBlock.style.boxShadow = "0 0 15px rgba(61, 220, 132, 0.2)";
    }
    if (sideHoverTip && tip) {
      sideHoverTip.textContent = `💡 ${tip}`;
      sideHoverTip.style.color = "#3ddc84";
    }
  });

  elem.addEventListener("mouseleave", () => {
    if (sideConfigBlock) {
      sideConfigBlock.style.transform = "translateX(0)";
      sideConfigBlock.style.borderColor = "var(--accent)";
      sideConfigBlock.style.boxShadow = "none";
    }
    if (sideHoverTip) {
      sideHoverTip.textContent = "Hover over toggles to preview rule shift.";
      sideHoverTip.style.color = "var(--text-dim)";
    }
  });
});

document.querySelectorAll('#toggle-in, #toggle-out, .line-in-check, .line-out-check, input[name="count_scope_mode"], #direction-mode-select').forEach(input => {
  input.addEventListener("change", updateSidebarRules);
});

// Initialize on page load
updateSidebarRules();

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
  const directionModeSelect = document.getElementById("direction-mode-select");

  const toggleIn = document.getElementById("toggle-in");
  const toggleOut = document.getElementById("toggle-out");

  const countScopeRadio = document.querySelector('input[name="count_scope_mode"]:checked');
  const countScopeMode = countScopeRadio ? countScopeRadio.value : "active_only";

  const speed = speedSelect ? speedSelect.value : "2";
  const lineMode = lineModeSelect ? lineModeSelect.value : "box";
  const directionMode = directionModeSelect ? directionModeSelect.value : "COMING_GOING";
  const enableIn = toggleIn ? toggleIn.checked : true;
  const enableOut = toggleOut ? toggleOut.checked : true;

  const enabledLinesIn = Array.from(document.querySelectorAll(".line-in-check:checked")).map(c => c.value);
  const enabledLinesOut = Array.from(document.querySelectorAll(".line-out-check:checked")).map(c => c.value);
  const allEnabledLines = Array.from(new Set([...enabledLinesIn, ...enabledLinesOut]));

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
    startFormData.append("direction_mode", directionMode);
    startFormData.append("enable_in", enableIn);
    startFormData.append("enable_out", enableOut);
    startFormData.append("count_scope_mode", countScopeMode);
    startFormData.append("enabled_lines", allEnabledLines.join(","));
    startFormData.append("enabled_lines_in", enabledLinesIn.join(","));
    startFormData.append("enabled_lines_out", enabledLinesOut.join(","));

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

function renderLines(lines, directionMode) {
  const entries = Object.entries(lines || {});
  if (!entries.length) {
    sideLinesBlock.hidden = true;
    return;
  }

  const toggleIn = document.getElementById("toggle-in");
  const toggleOut = document.getElementById("toggle-out");
  const isInActive = toggleIn ? toggleIn.checked : true;
  const isOutActive = toggleOut ? toggleOut.checked : true;

  const enabledIn = Array.from(document.querySelectorAll(".line-in-check:checked")).map(c => c.value.toLowerCase());
  const enabledOut = Array.from(document.querySelectorAll(".line-out-check:checked")).map(c => c.value.toLowerCase());

  let totalInCount = 0;
  let totalOutCount = 0;

  entries.forEach(([name, v]) => {
    totalInCount += (v.in || 0);
    totalOutCount += (v.out || 0);
  });

  sideLinesBlock.hidden = false;

  let html = `
    <div class="live-flow-summary-badge" style="display: flex; gap: 8px; margin-bottom: 10px;">
      <div style="flex: 1; background: rgba(16, 185, 129, 0.12); border: 1px solid #10b981; border-radius: 8px; padding: 6px 10px; text-align: center;">
        <span style="font-size: 0.7rem; color: #3ddc84; font-weight: 700; display: block;">🟢 IN FLOW</span>
        <span style="font-size: 1rem; color: #fff; font-weight: 800;">${isInActive ? totalInCount : 'OFF'}</span>
      </div>
      <div style="flex: 1; background: rgba(239, 68, 68, 0.12); border: 1px solid #ef4444; border-radius: 8px; padding: 6px 10px; text-align: center;">
        <span style="font-size: 0.7rem; color: #ff4d4d; font-weight: 700; display: block;">🔴 OUT FLOW</span>
        <span style="font-size: 1rem; color: #fff; font-weight: 800;">${isOutActive ? totalOutCount : 'OFF'}</span>
      </div>
    </div>
  `;

  html += entries.map(([name, v], i) => {
    const sideKey = name.replace(" Line", "").toLowerCase();
    const inActive = isInActive && (enabledIn.length === 0 || enabledIn.includes(sideKey));
    const outActive = isOutActive && (enabledOut.length === 0 || enabledOut.includes(sideKey));

    return `
      <div class="line-row" style="flex-direction: column; align-items: stretch; gap: 4px; padding: 8px 10px; background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 8px; margin-bottom: 6px;">
        <div style="display: flex; align-items: center; justify-content: space-between;">
          <span class="line-row-name" style="font-weight: 700; font-size: 0.82rem; color: #fff;">
            <span class="line-dot" style="background:${LINE_COLORS[i % LINE_COLORS.length]}"></span>
            ${escapeHtml(name)}
          </span>
          <span style="font-size: 0.75rem; color: var(--text-dim); font-weight: 600;">Total: ${(v.in || 0) + (v.out || 0)}</span>
        </div>
        <div style="display: flex; gap: 6px; margin-top: 2px;">
          <span style="flex: 1; font-size: 0.72rem; padding: 3px 6px; border-radius: 5px; background: ${inActive ? 'rgba(16, 185, 129, 0.15)' : 'rgba(255,255,255,0.03)'}; color: ${inActive ? '#3ddc84' : 'var(--text-dim)'}; border: 1px solid ${inActive ? 'rgba(16, 185, 129, 0.3)' : 'transparent'}; font-weight: 600; text-align: center;">
            ⬆️ IN: ${v.in || 0}
          </span>
          <span style="flex: 1; font-size: 0.72rem; padding: 3px 6px; border-radius: 5px; background: ${outActive ? 'rgba(239, 68, 68, 0.15)' : 'rgba(255,255,255,0.03)'}; color: ${outActive ? '#ff4d4d' : 'var(--text-dim)'}; border: 1px solid ${outActive ? 'rgba(239, 68, 68, 0.3)' : 'transparent'}; font-weight: 600; text-align: center;">
            ⬇️ OUT: ${v.out || 0}
          </span>
        </div>
      </div>
    `;
  }).join("");

  lineRows.innerHTML = html;
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

    renderLines(data.lines, data.direction_mode);
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

const confirmModal = document.getElementById("confirm-modal");
const modalCloseBtn = document.getElementById("modal-close-btn");
const modalEditBtn = document.getElementById("modal-edit-btn");
const modalConfirmBtn = document.getElementById("modal-confirm-btn");

function openConfirmModal() {
  clearError();
  const file = fileInput.files[0];

  if (!file) {
    showError("Please select or drop a video file first.");
    return;
  }

  const speedSelect = document.getElementById("speed-select");
  const lineModeSelect = document.getElementById("line-mode-select");
  const toggleIn = document.getElementById("toggle-in");
  const toggleOut = document.getElementById("toggle-out");
  const directionRadio = document.querySelector('input[name="direction_mode"]:checked');
  const activeLines = Array.from(document.querySelectorAll(".line-check:checked")).map(c => c.value);

  const speedMap = { "1": "1x Normal Speed (100%)", "2": "2x Fast-Forward (200%)", "3": "3x Ultra Fast (300%)" };
  const modeMap = { "box": "4-Way Intersection Box", "horizontal": "Single Horizontal Line", "vertical": "Vertical Boundary Line" };
  const termMap = { "IN_OUT": "IN / OUT", "COMING_GOING": "COMING / GOING", "FORWARD_BACKWARD": "FORWARD / BACKWARD" };

  const modeText = modeMap[lineModeSelect ? lineModeSelect.value : "box"] || "4-Way Intersection Box";
  const speedText = speedMap[speedSelect ? speedSelect.value : "2"] || "2x Fast-Forward";
  const namingText = termMap[directionRadio ? directionRadio.value : "IN_OUT"] || "IN / OUT";

  let flowsText = [];
  if (toggleIn && toggleIn.checked) flowsText.push("🟢 IN Flow");
  if (toggleOut && toggleOut.checked) flowsText.push("🔴 OUT Flow");
  const flowStr = flowsText.length ? flowsText.join(" | ") : "⚠️ No Flows Selected";

  const linesStr = activeLines.length ? activeLines.join(", ") : "None (All Disabled)";

  const videoVal = document.getElementById("modal-video-val");
  const modeVal = document.getElementById("modal-mode-val");
  const speedVal = document.getElementById("modal-speed-val");
  const namingVal = document.getElementById("modal-naming-val");
  const flowsVal = document.getElementById("modal-flows-val");
  const linesVal = document.getElementById("modal-lines-val");
  const humanSummary = document.getElementById("modal-human-summary");

  if (videoVal) videoVal.textContent = file.name;
  if (modeVal) modeVal.textContent = modeText;
  if (speedVal) speedVal.textContent = speedText;
  if (namingVal) namingVal.textContent = namingText;
  if (flowsVal) flowsVal.textContent = flowStr;
  if (linesVal) linesVal.textContent = linesStr;

  let summary = `The AI engine will analyze '${file.name}' using ${modeText} at ${speedText}. `;
  if (flowsText.length === 2) {
    summary += `It will count both incoming & outgoing traffic across ${linesStr} lines.`;
  } else if (flowsText.length === 1) {
    summary += `It will count ONLY ${flowsText[0]} vehicles across ${linesStr} lines (1-side lane mode).`;
  } else {
    summary += `Warning: No traffic flows are currently enabled.`;
  }
  if (humanSummary) humanSummary.textContent = summary;

  if (confirmModal) confirmModal.hidden = false;
}

if (modalCloseBtn) modalCloseBtn.addEventListener("click", () => confirmModal.hidden = true);
if (modalEditBtn) modalEditBtn.addEventListener("click", () => confirmModal.hidden = true);
if (modalConfirmBtn) {
  modalConfirmBtn.addEventListener("click", () => {
    confirmModal.hidden = true;
    startJob();
  });
}

startBtn.addEventListener("click", openConfirmModal);
cancelBtn.addEventListener("click", cancelJob);
refreshBtn.addEventListener("click", loadHistory);
newVideoBtn.addEventListener("click", startNewVideo);

// --- Visual Feature Reference Modal (i Icon Handler) ---
const infoModal = document.getElementById("info-modal");
const infoModalTitle = document.getElementById("info-modal-title");
const infoModalImg = document.getElementById("info-modal-img");
const infoModalTag = document.getElementById("info-modal-tag");
const infoModalDesc = document.getElementById("info-modal-desc");
const infoModalClose = document.getElementById("info-modal-close");
const infoModalOk = document.getElementById("info-modal-ok");

const INFO_REFERENCES = {
  "counting_scope": {
    title: "📊 Counting Scope (Active Rules vs All Traffic)",
    img: "/static/img/intersection_box.png",
    tag: "📊 COUNTING SCOPE EXPLANATION",
    desc: "<b>🎯 Count Active Rules Only:</b> Total Vehicle Count will ONLY increment when vehicles cross an enabled side and direction. Vehicles on disabled sides or turned-off directions are ignored.<br><br><b>🌐 Count All Road Traffic:</b> Total Vehicle Count will increment for EVERY vehicle detected on any line across the entire road."
  },
  "boundary": {
    title: "🎯 Boundary Modes (Box, Horizontal, Vertical)",
    img: "/static/img/intersection_box.png",
    tag: "🎯 WHAT WILL IT COUNT IF ENABLED?",
    desc: "<b>4-Way Intersection Box:</b> Draws a centered 4-way box with North, South, West, and East boundaries. Ideal for complex road intersections.<br><br><b>Single Horizontal:</b> Draws a single horizontal boundary line across the road.<br><br><b>Vertical Line:</b> Draws a vertical line splitting left/right lanes. Perfect for 1-side lane counting."
  },
  "speed": {
    title: "⚡ Analysis & Stream Speed (1x, 2x, 3x)",
    img: "/static/img/intersection_box.png",
    tag: "⚡ STREAM SPEED EXPLANATION",
    desc: "<b>2x Fast-Forward (Default):</b> Processes 200% faster with zero accuracy loss for rapid counting results.<br><br><b>1x Normal Speed:</b> Frame-by-frame analysis at 100% video speed.<br><br><b>3x Ultra Fast:</b> Max speed processing for long multi-hour video streams."
  },
  "in_flow": {
    title: "🟢 IN Flow Counting",
    img: "/static/img/in_flow.png",
    tag: "🟢 WHAT WILL IT COUNT IF ENABLED?",
    desc: "<b>When 🟢 IN Flow is ACTIVE:</b> The AI detector will track and count all vehicles moving INWARD (entering the intersection or crossing the boundary towards the focal direction).<br><br><i>If un-checked/disabled, incoming vehicles will NOT be counted.</i>"
  },
  "out_flow": {
    title: "🔴 OUT Flow Counting",
    img: "/static/img/out_flow.png",
    tag: "🔴 WHAT WILL IT COUNT IF ENABLED?",
    desc: "<b>When 🔴 OUT Flow is ACTIVE:</b> The AI detector will track and count all vehicles moving OUTWARD (leaving the intersection or moving away from the focal direction).<br><br><i>If un-checked/disabled, outgoing vehicles will NOT be counted.</i>"
  },
  "in_out": {
    title: "🏷️ IN / OUT Naming Standard",
    img: "/static/img/in_flow.png",
    tag: "🏷️ REPORT & COUNTER LABELS",
    desc: "Labels traffic movement as <b>IN</b> (vehicles entering) and <b>OUT</b> (vehicles exiting). This is the standard traffic engineering convention."
  },
  "coming_going": {
    title: "🚗 COMING / GOING Naming Standard",
    img: "/static/img/in_flow.png",
    tag: "🏷️ REPORT & COUNTER LABELS",
    desc: "Labels traffic movement as <b>COMING</b> (vehicles approaching camera) and <b>GOING</b> (vehicles driving away). Perfect for highway surveillance."
  },
  "forward_backward": {
    title: "➡️ FORWARD / BACKWARD Naming Standard",
    img: "/static/img/in_flow.png",
    tag: "🏷️ REPORT & COUNTER LABELS",
    desc: "Labels traffic movement as <b>FORWARD</b> (downstream flow) and <b>BACKWARD</b> (reverse flow). Ideal for single-lane flow monitoring."
  },
  "reverse": {
    title: "🔄 Reverse Direction (Vector Inversion)",
    img: "/static/img/out_flow.png",
    tag: "🔄 WHAT DOES REVERSE DIRECTION DO?",
    desc: "Flips the vector normal of all boundary lines by 180°. Use this if IN and OUT are reversed on your video or if you want to count the opposite lane on a 1-side road camera!"
  },
  "compass": {
    title: "🧭 Compass Boundary Side Lines",
    img: "/static/img/compass.png",
    tag: "🧭 WHAT DO SIDE LINES COUNT?",
    desc: "Tracks vehicles crossing specific boundary sides:<br><br>• <b>North Line:</b> Top boundary.<br>• <b>South Line:</b> Bottom boundary.<br>• <b>West Line:</b> Left boundary.<br>• <b>East Line:</b> Right boundary."
  },
  "north": {
    title: "⬆️ North Boundary Line",
    img: "/static/img/compass.png",
    tag: "⬆️ TOP BOUNDARY LINE",
    desc: "Tracks and counts all vehicles crossing the <b>TOP (North)</b> line of the intersection boundary box."
  },
  "south": {
    title: "⬇️ South Boundary Line",
    img: "/static/img/compass.png",
    tag: "⬇️ BOTTOM BOUNDARY LINE",
    desc: "Tracks and counts all vehicles crossing the <b>BOTTOM (South)</b> line of the intersection boundary box."
  },
  "west": {
    title: "⬅️ West Boundary Line",
    img: "/static/img/compass.png",
    tag: "⬅️ LEFT BOUNDARY LINE",
    desc: "Tracks and counts all vehicles crossing the <b>LEFT (West)</b> line of the intersection boundary box."
  },
  "east": {
    title: "➡️ East Boundary Line",
    img: "/static/img/compass.png",
    tag: "➡️ RIGHT BOUNDARY LINE",
    desc: "Tracks and counts all vehicles crossing the <b>RIGHT (East)</b> line of the intersection boundary box."
  }
};

document.querySelectorAll(".info-trigger").forEach(btn => {
  btn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    const refKey = btn.getAttribute("data-ref");
    const infoData = INFO_REFERENCES[refKey];

    if (infoData && infoModal) {
      if (infoModalTitle) infoModalTitle.textContent = infoData.title;
      if (infoModalImg) infoModalImg.src = infoData.img;
      if (infoModalTag) infoModalTag.textContent = infoData.tag;
      if (infoModalDesc) infoModalDesc.innerHTML = infoData.desc;
      infoModal.hidden = false;
    }
  });
});

if (infoModalClose) infoModalClose.addEventListener("click", () => infoModal.hidden = true);
if (infoModalOk) infoModalOk.addEventListener("click", () => infoModal.hidden = true);

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
