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

// Video Source Selection & Batch Elements
const tabBatchBtn = document.getElementById("tab-batch-btn");
const tabFileBtn = document.getElementById("tab-file-btn");
const tabUrlBtn = document.getElementById("tab-url-btn");
const sourceBatchSection = document.getElementById("source-batch-section");
const sourceFileSection = document.getElementById("source-file-section");
const sourceUrlSection = document.getElementById("source-url-section");
const batchBuildBtn = document.getElementById("batch-build-btn");
const batchStepperBar = document.getElementById("batch-stepper-bar");
const batchReportContainer = document.getElementById("batch-report-container");
const batchGrandTotalDisplay = document.getElementById("batch-grand-total-display");
const batchMatrixBody = document.getElementById("batch-matrix-body");
const batchMatrixFoot = document.getElementById("batch-matrix-foot");
const thVideo1 = document.getElementById("th-video-1");
const thVideo2 = document.getElementById("th-video-2");
const thVideo3 = document.getElementById("th-video-3");
const reportMainTitle = document.getElementById("report-main-title");
const reportMainSub = document.getElementById("report-main-sub");
const pdfBtnLabel = document.getElementById("pdf-btn-label");
const xlsxBtnLabel = document.getElementById("xlsx-btn-label");

const videoUrlInput = document.getElementById("video-url-input");
const urlClearBtn = document.getElementById("url-clear-btn");
const urlPasteBtn = document.getElementById("url-paste-btn");
const urlStatusCard = document.getElementById("url-status-card");
const urlStatusIcon = document.getElementById("url-status-icon");
const urlStatusTitle = document.getElementById("url-status-title");
const urlStatusMeta = document.getElementById("url-status-meta");

// Detailed Upload & Cloud Ingestion Progress Elements
const uploadProgressCard = document.getElementById("upload-progress-card");
const uploadStageLabel = document.getElementById("upload-stage-label");
const uploadPctLabel = document.getElementById("upload-pct-label");
const uploadProgressFill = document.getElementById("upload-progress-fill");
const uploadBytesLabel = document.getElementById("upload-bytes-label");
const uploadSpeedLabel = document.getElementById("upload-speed-label");
const uploadEtaLabel = document.getElementById("upload-eta-label");
const uploadRetryWarning = document.getElementById("upload-retry-warning");
const retryChunkNum = document.getElementById("retry-chunk-num");
const retryAttemptNum = document.getElementById("retry-attempt-num");

let currentSourceTab = "batch"; // 'batch', 'file', or 'url'
let currentBatchId = null;
let batchPollTimer = null;

const speedMap = {
  "1": "1x Realtime",
  "2": "2x Fast-Forward",
  "4": "4x Ultra-Fast",
  "8": "8x Maximum Speed"
};

const LINE_COLORS = ["#4f8cff", "#ff7a45", "#3ddc84", "#ff5c5c", "#c084fc", "#facc15"];

let currentJobId = null;
let pollTimer = null;

// ═══════════════════════════════════════════════════════════════
//  LANE SELECTOR — Banani→Gulshan / Gulshan→Mohakhali
// ═══════════════════════════════════════════════════════════════
// activeLane: 'banani_gulshan' → count Coming vehicles (enable_in=true, enable_out=false)
//             'gulshan_mohakhali' → count Going vehicles (enable_in=false, enable_out=true)
let activeLane = 'banani_gulshan';

const laneBtnBananiGulshan = document.getElementById('lane-btn-banani-gulshan');
const laneBtnGulshanMohakhali = document.getElementById('lane-btn-gulshan-mohakhali');
const laneBadgeBananiGulshan = document.getElementById('lane-badge-banani-gulshan');
const laneBadgeGulshanMohakhali = document.getElementById('lane-badge-gulshan-mohakhali');
const laneActiveLabel = document.getElementById('lane-active-label');
const laneActiveInfo = document.getElementById('lane-active-info');
const laneInfoDot = laneActiveInfo ? laneActiveInfo.querySelector('.lane-info-dot') : null;
const laneMapWrapper = document.querySelector('.lane-map-wrapper');

function setActiveLane(lane) {
  activeLane = lane;

  const isBanani = lane === 'banani_gulshan';

  // Update button states
  if (laneBtnBananiGulshan) {
    laneBtnBananiGulshan.classList.toggle('lane-btn-active', isBanani);
    laneBtnBananiGulshan.classList.toggle('lane-btn-inactive', !isBanani);
    const r = laneBtnBananiGulshan.querySelector('.lane-btn-radio');
    if (r) r.textContent = isBanani ? '✓' : '○';
  }
  if (laneBtnGulshanMohakhali) {
    laneBtnGulshanMohakhali.classList.toggle('lane-btn-active', !isBanani);
    laneBtnGulshanMohakhali.classList.toggle('lane-btn-inactive', isBanani);
    const r = laneBtnGulshanMohakhali.querySelector('.lane-btn-radio');
    if (r) r.textContent = !isBanani ? '✓' : '○';
  }

  // Update badges
  if (laneBadgeBananiGulshan) {
    laneBadgeBananiGulshan.textContent = isBanani ? 'ACTIVE' : 'OFF';
    laneBadgeBananiGulshan.classList.toggle('lane-badge-off', !isBanani);
  }
  if (laneBadgeGulshanMohakhali) {
    laneBadgeGulshanMohakhali.textContent = !isBanani ? 'ACTIVE' : 'OFF';
    laneBadgeGulshanMohakhali.classList.toggle('lane-badge-off', isBanani);
  }

  // Update info bar
  if (laneInfoDot) {
    laneInfoDot.style.background = isBanani ? '#4f8cff' : '#facc15';
  }
  if (laneActiveLabel) {
    if (isBanani) {
      laneActiveLabel.innerHTML = 'Counting: <strong>Banani to Gulshan</strong> — Only this lane is counted (🟢 Green Box). Other lanes show 🔴 Red Box';
    } else {
      laneActiveLabel.innerHTML = 'Counting: <strong>Gulshan to Mohakhali</strong> — Only this lane is counted (🟢 Green Box). Other lanes show 🔴 Red Box';
    }
  }

  // Update map wrapper border color
  if (laneMapWrapper) {
    laneMapWrapper.style.borderColor = isBanani
      ? 'rgba(79,140,255,0.5)'
      : 'rgba(250,204,21,0.5)';
  }

  // Sync the underlying toggle-in / toggle-out checkboxes
  const toggleIn = document.getElementById('toggle-in');
  const toggleOut = document.getElementById('toggle-out');
  if (toggleIn) toggleIn.checked = isBanani;        // Banani to Gulshan
  if (toggleOut) toggleOut.checked = !isBanani;     // Gulshan to Mohakhali

  if (isBanani) {
    document.querySelectorAll('.line-in-check').forEach(c => c.checked = true);
    document.querySelectorAll('.line-out-check').forEach(c => c.checked = false);
  } else {
    document.querySelectorAll('.line-in-check').forEach(c => c.checked = false);
    document.querySelectorAll('.line-out-check').forEach(c => c.checked = true);
  }

  if (typeof syncDirectionButtons === 'function') syncDirectionButtons();
  if (typeof updateSidebarRules === 'function') updateSidebarRules();

  showToast(
    isBanani
      ? '🔵 Active lane: Banani to Gulshan. Only this lane counted (Green box).'
      : '🟡 Active lane: Gulshan to Mohakhali. Only this lane counted (Green box).',
    isBanani ? 'info' : 'warning'
  );

  // If a job is running, push live rule update
  if (typeof pushLiveRuleUpdate === 'function') pushLiveRuleUpdate();
}

if (laneBtnBananiGulshan) {
  laneBtnBananiGulshan.addEventListener('click', () => setActiveLane('banani_gulshan'));
}
if (laneBtnGulshanMohakhali) {
  laneBtnGulshanMohakhali.addEventListener('click', () => setActiveLane('gulshan_mohakhali'));
}

// Helper: get active lane counting config for job start
function getLaneCountingConfig() {
  return {
    enableIn: true,
    enableOut: true,
    enabledLinesIn: ['North', 'South', 'West', 'East', 'Traffic Flow', 'Gulshan Entry', 'Mohakhali Flow'],
    enabledLinesOut: ['North', 'South', 'West', 'East', 'Traffic Flow', 'Gulshan Entry', 'Mohakhali Flow'],
  };
}


function showError(msg) {
  errorMsg.textContent = msg;
  errorMsg.hidden = false;
}

function clearError() {
  errorMsg.hidden = true;
  errorMsg.textContent = "";
}

// Floating Toast Notification System (replaces blocking browser alerts)
function showToast(msg, type = "info") {
  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    container.className = "toast-container";
    document.body.appendChild(container);
  }
  const toast = document.createElement("div");
  toast.className = `toast-pill ${type}`;
  toast.innerHTML = `<span>${msg}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    if (toast.parentNode) {
      toast.parentNode.removeChild(toast);
    }
  }, 3200);
}

// Format byte counts into human-readable MBs
function formatBytes(bytes) {
  if (!bytes || bytes <= 0) return "0.0 MB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

function showProgressCard(initialStage) {
  if (uploadProgressCard) uploadProgressCard.hidden = false;
  if (uploadStageLabel && initialStage) uploadStageLabel.textContent = initialStage;
}

function hideProgressCard() {
  if (uploadProgressCard) uploadProgressCard.hidden = true;
  hideRetryWarning();
}

function showRetryWarning(chunkNum, attemptNum) {
  if (retryChunkNum) retryChunkNum.textContent = chunkNum;
  if (retryAttemptNum) retryAttemptNum.textContent = attemptNum;
  if (uploadRetryWarning) uploadRetryWarning.hidden = false;
}

function hideRetryWarning() {
  if (uploadRetryWarning) uploadRetryWarning.hidden = true;
}

function updateProgressCard(opts) {
  showProgressCard();
  if (opts.stage && uploadStageLabel) uploadStageLabel.textContent = opts.stage;
  const pct = Math.min(100, Math.max(0, opts.pct || 0));
  if (uploadPctLabel) uploadPctLabel.textContent = `${pct}%`;
  if (uploadProgressFill) uploadProgressFill.style.width = `${pct}%`;

  if (uploadBytesLabel) {
    if (opts.totalBytes && opts.totalBytes > 0) {
      uploadBytesLabel.textContent = `${formatBytes(opts.uploadedBytes)} / ${formatBytes(opts.totalBytes)}`;
    } else {
      uploadBytesLabel.textContent = formatBytes(opts.uploadedBytes);
    }
  }

  if (uploadSpeedLabel) {
    if (opts.speedBytesPerSec > 0) {
      uploadSpeedLabel.textContent = `~${formatBytes(opts.speedBytesPerSec)}/s`;
    } else {
      uploadSpeedLabel.textContent = "~0.0 MB/s";
    }
  }

  if (uploadEtaLabel) {
    if (opts.etaSec !== undefined && opts.etaSec !== null) {
      if (opts.etaSec <= 0 || pct >= 100) {
        uploadEtaLabel.textContent = "Done";
      } else if (opts.etaSec < 60) {
        uploadEtaLabel.textContent = `ETA: ~${opts.etaSec}s`;
      } else {
        const mins = Math.floor(opts.etaSec / 60);
        const secs = opts.etaSec % 60;
        uploadEtaLabel.textContent = `ETA: ~${mins}m ${secs}s`;
      }
    } else {
      uploadEtaLabel.textContent = "ETA: --";
    }
  }
}

// Source Tab Switching & Link Resolver
let checkUrlTimer = null;
let resolvedCloudMetadata = null;

function switchToBatchTab() {
  currentSourceTab = "batch";
  if (tabBatchBtn) tabBatchBtn.classList.add("active");
  if (tabFileBtn) tabFileBtn.classList.remove("active");
  if (tabUrlBtn) tabUrlBtn.classList.remove("active");
  if (sourceBatchSection) sourceBatchSection.hidden = false;
  if (sourceFileSection) sourceFileSection.hidden = true;
  if (sourceUrlSection) sourceUrlSection.hidden = true;
  if (batchBuildBtn) batchBuildBtn.style.display = "flex";
  if (startBtn) startBtn.style.display = "none";
  clearError();
}

function switchToUrlTab(urlVal) {
  currentSourceTab = "url";
  if (tabUrlBtn) tabUrlBtn.classList.add("active");
  if (tabBatchBtn) tabBatchBtn.classList.remove("active");
  if (tabFileBtn) tabFileBtn.classList.remove("active");
  if (sourceFileSection) sourceFileSection.hidden = true;
  if (sourceBatchSection) sourceBatchSection.hidden = true;
  if (sourceUrlSection) sourceUrlSection.hidden = false;
  if (batchBuildBtn) batchBuildBtn.style.display = "none";
  if (startBtn) startBtn.style.display = "flex";
  clearError();

  if (urlVal && videoUrlInput) {
    videoUrlInput.value = urlVal.trim();
    if (urlClearBtn) urlClearBtn.style.display = "block";
    inspectAndVerifyUrl(urlVal.trim());
  }
}

function switchToFileTab() {
  currentSourceTab = "file";
  if (tabFileBtn) tabFileBtn.classList.add("active");
  if (tabBatchBtn) tabBatchBtn.classList.remove("active");
  if (tabUrlBtn) tabUrlBtn.classList.remove("active");
  if (sourceFileSection) sourceFileSection.hidden = false;
  if (sourceBatchSection) sourceBatchSection.hidden = true;
  if (sourceUrlSection) sourceUrlSection.hidden = true;
  if (batchBuildBtn) batchBuildBtn.style.display = "none";
  if (startBtn) startBtn.style.display = "flex";
  clearError();
}

if (tabBatchBtn) tabBatchBtn.addEventListener("click", switchToBatchTab);
if (tabFileBtn) tabFileBtn.addEventListener("click", switchToFileTab);
if (tabUrlBtn) tabUrlBtn.addEventListener("click", () => switchToUrlTab());

const batchDebounceTimers = {};

function isCloudUrl(str) {
  if (!str) return false;
  const s = str.trim().replace(/^["'<]+|["'>]+$/g, "");
  return /^https?:\/\//i.test(s) ||
         /drive\.google\.com/i.test(s) ||
         /docs\.google\.com/i.test(s) ||
         /dropbox\.com/i.test(s) ||
         (/^[a-zA-Z0-9_-]{25,50}$/.test(s) && !s.includes(".") && !s.includes("/"));
}

async function checkBatchPath(targetIndex) {
  const input = document.getElementById(`batch-path-${targetIndex}`);
  const statusBadge = document.getElementById(`batch-status-${targetIndex}`);
  const card = document.getElementById(`batch-card-${targetIndex}`);
  const statusCard = document.getElementById(`batch-status-card-${targetIndex}`);
  const statusIcon = document.getElementById(`batch-status-icon-${targetIndex}`);
  const statusTitle = document.getElementById(`batch-status-title-${targetIndex}`);
  const statusMeta = document.getElementById(`batch-status-meta-${targetIndex}`);

  const raw = (input ? input.value : "").trim().replace(/^["'<]+|["'>]+$/g, "");
  if (!raw) {
    if (statusBadge) {
      statusBadge.textContent = "Not selected";
      statusBadge.className = "batch-box-status";
      statusBadge.title = "";
    }
    if (statusCard) statusCard.style.display = "none";
    if (card) {
      card.classList.remove("verified");
      card.classList.remove("error");
    }
    return null;
  }

  // Show inspecting state
  if (statusBadge) {
    statusBadge.textContent = "⏳ Checking…";
    statusBadge.className = "batch-box-status";
  }
  if (statusCard) {
    statusCard.style.display = "flex";
    statusCard.className = "batch-status-card";
    if (statusIcon) statusIcon.textContent = "⏳";
    if (statusTitle) statusTitle.textContent = "Inspecting video source…";
    if (statusMeta) statusMeta.textContent = isCloudUrl(raw)
      ? "Connecting to cloud source to retrieve video metadata…"
      : "Checking local video file on server…";
  }

  // If input is a Google Drive or Cloud URL
  if (isCloudUrl(raw)) {
    try {
      const res = await fetch("/api/check_url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: raw })
      });
      const data = await res.json();
      const prov = data.provider || (raw.includes("drive.google") || raw.includes("docs.google") ? "Google Drive" : "Cloud Link");
      const filename = data.filename || (prov === "Google Drive" ? "gdrive_video.mp4" : "cloud_video.mp4");
      const sizeStr = data.size_formatted || "Cloud Stream";

      if (statusBadge) {
        statusBadge.textContent = `🟢 ${prov}: ${filename}`;
        statusBadge.className = "batch-box-status verified";
        statusBadge.title = `${prov}: ${filename} (${sizeStr})`;
      }
      if (statusCard) {
        statusCard.style.display = "flex";
        statusCard.className = "batch-status-card verified";
        if (statusIcon) statusIcon.textContent = "🟢";
        if (statusTitle) statusTitle.textContent = `${prov} Video: ${filename}`;
        if (statusMeta) statusMeta.textContent = `Size: ${sizeStr} • Verified & ready for AI analysis!`;
      }
      if (card) {
        card.classList.remove("error");
        card.classList.add("verified");
      }
      clearError();
      return raw;
    } catch (e) {
      const prov = (raw.includes("drive.google") || raw.includes("docs.google")) ? "Google Drive" : "Cloud Link";
      if (statusBadge) {
        statusBadge.textContent = `🟢 ${prov} Ready`;
        statusBadge.className = "batch-box-status verified";
      }
      if (statusCard) {
        statusCard.style.display = "flex";
        statusCard.className = "batch-status-card verified";
        if (statusIcon) statusIcon.textContent = "☁️";
        if (statusTitle) statusTitle.textContent = `${prov} Video Attached`;
        if (statusMeta) statusMeta.textContent = "Link recognized. Ready to stream & analyze.";
      }
      if (card) {
        card.classList.remove("error");
        card.classList.add("verified");
      }
      return raw;
    }
  }

  // Local filesystem path
  try {
    const res = await fetch("/api/check_path", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: raw })
    });
    const data = await res.json();
    if (data.valid) {
      if (statusBadge) {
        statusBadge.textContent = `🟢 Ready: ${data.filename} (${data.size_formatted})`;
        statusBadge.className = "batch-box-status verified";
        statusBadge.title = data.path;
      }
      if (statusCard) {
        statusCard.style.display = "flex";
        statusCard.className = "batch-status-card verified";
        if (statusIcon) statusIcon.textContent = "📁";
        if (statusTitle) statusTitle.textContent = `Local Video: ${data.filename}`;
        if (statusMeta) statusMeta.textContent = `Size: ${data.size_formatted} • Verified & ready for AI analysis!`;
      }
      if (card) {
        card.classList.remove("error");
        card.classList.add("verified");
      }
      clearError();
      return data.path;
    } else {
      if (statusBadge) {
        statusBadge.textContent = "⚠️ Not found";
        statusBadge.className = "batch-box-status error";
      }
      if (statusCard) {
        statusCard.style.display = "flex";
        statusCard.className = "batch-status-card error";
        if (statusIcon) statusIcon.textContent = "⚠️";
        if (statusTitle) statusTitle.textContent = "Video File Not Found";
        if (statusMeta) statusMeta.textContent = `File not found on server: ${raw}`;
      }
      if (card) {
        card.classList.remove("verified");
        card.classList.add("error");
      }
      return null;
    }
  } catch (e) {
    if (statusBadge) {
      statusBadge.textContent = "Check error";
      statusBadge.className = "batch-box-status error";
    }
    return null;
  }
}

function initBatchBoxListeners() {
  [1, 2, 3].forEach(idx => {
    const input = document.getElementById(`batch-path-${idx}`);
    if (input) {
      input.addEventListener("input", () => {
        clearTimeout(batchDebounceTimers[idx]);
        batchDebounceTimers[idx] = setTimeout(() => checkBatchPath(idx), 350);
      });
      input.addEventListener("blur", () => checkBatchPath(idx));
    }
  });

  document.querySelectorAll(".batch-paste-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const idx = btn.getAttribute("data-target");
      const pathInput = document.getElementById(`batch-path-${idx}`);
      try {
        const text = await navigator.clipboard.readText();
        if (text && text.trim()) {
          if (pathInput) {
            pathInput.value = text.trim();
            checkBatchPath(idx);
          }
          showToast(`Pasted video link into Box ${idx}`, "success");
        } else {
          showError(`Clipboard is empty. Copy your Google Drive or video link first.`);
        }
      } catch (err) {
        if (pathInput) {
          pathInput.focus();
          pathInput.select();
        }
        showToast(`Please press Ctrl+V to paste link into Box ${idx}`, "info");
      }
    });
  });

  document.querySelectorAll(".batch-browse-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const idx = btn.getAttribute("data-target");
      const fileInp = document.getElementById(`batch-file-input-${idx}`);
      if (fileInp) fileInp.click();
    });
  });

  document.querySelectorAll(".batch-hidden-file").forEach(inp => {
    inp.addEventListener("change", async () => {
      const idMatch = inp.id.match(/\d+$/);
      if (!idMatch) return;
      const idx = idMatch[0];
      const file = inp.files[0];
      if (!file) return;

      const pathInput = document.getElementById(`batch-path-${idx}`);
      const statusBadge = document.getElementById(`batch-status-${idx}`);
      const card = document.getElementById(`batch-card-${idx}`);
      const statusCard = document.getElementById(`batch-status-card-${idx}`);
      const statusIcon = document.getElementById(`batch-status-icon-${idx}`);
      const statusTitle = document.getElementById(`batch-status-title-${idx}`);
      const statusMeta = document.getElementById(`batch-status-meta-${idx}`);

      if (statusBadge) {
        statusBadge.textContent = "Uploading…";
        statusBadge.className = "batch-box-status";
      }
      if (statusCard) {
        statusCard.style.display = "flex";
        statusCard.className = "batch-status-card";
        if (statusIcon) statusIcon.textContent = "⏳";
        if (statusTitle) statusTitle.textContent = `Uploading ${file.name}…`;
        if (statusMeta) statusMeta.textContent = "Preparing chunks for upload…";
      }

      try {
        const uploadedPath = await uploadFileInChunks(file, (pct) => {
          if (statusBadge) statusBadge.textContent = `Uploading ${pct}%…`;
          if (statusMeta) statusMeta.textContent = `Uploading chunked video: ${pct}%`;
        });
        if (pathInput) pathInput.value = uploadedPath;
        const sizeStr = `${(file.size / (1024 * 1024)).toFixed(1)} MB`;
        if (statusBadge) {
          statusBadge.textContent = `🟢 Ready: ${sizeStr}`;
          statusBadge.className = "batch-box-status verified";
        }
        if (statusCard) {
          statusCard.style.display = "flex";
          statusCard.className = "batch-status-card verified";
          if (statusIcon) statusIcon.textContent = "📁";
          if (statusTitle) statusTitle.textContent = `Uploaded: ${file.name}`;
          if (statusMeta) statusMeta.textContent = `Size: ${sizeStr} • Ready for batch analysis!`;
        }
        if (card) {
          card.classList.remove("error");
          card.classList.add("verified");
        }
        clearError();
      } catch (e) {
        if (statusBadge) {
          statusBadge.textContent = "Upload failed";
          statusBadge.className = "batch-box-status error";
        }
        if (statusCard) {
          statusCard.style.display = "flex";
          statusCard.className = "batch-status-card error";
          if (statusIcon) statusIcon.textContent = "⚠️";
          if (statusTitle) statusTitle.textContent = "Upload Failed";
          if (statusMeta) statusMeta.textContent = e.message;
        }
        if (card) {
          card.classList.remove("verified");
          card.classList.add("error");
        }
        showError(`Failed to upload ${file.name}: ${e.message}`);
      }
    });
  });

  document.querySelectorAll(".batch-sample-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const idx = btn.getAttribute("data-target");
      const sampleVal = btn.getAttribute("data-sample");
      const pathInput = document.getElementById(`batch-path-${idx}`);
      if (pathInput) {
        pathInput.value = sampleVal;
        checkBatchPath(idx);
      }
    });
  });

  document.querySelectorAll(".batch-clear-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const idx = btn.getAttribute("data-target");
      const pathInput = document.getElementById(`batch-path-${idx}`);
      const fileInp = document.getElementById(`batch-file-input-${idx}`);
      const statusBadge = document.getElementById(`batch-status-${idx}`);
      const statusCard = document.getElementById(`batch-status-card-${idx}`);
      const card = document.getElementById(`batch-card-${idx}`);
      if (pathInput) pathInput.value = "";
      if (fileInp) fileInp.value = "";
      if (statusBadge) {
        statusBadge.textContent = "Not selected";
        statusBadge.className = "batch-box-status";
        statusBadge.title = "";
      }
      if (statusCard) statusCard.style.display = "none";
      if (card) {
        card.classList.remove("verified");
        card.classList.remove("error");
      }
      clearError();
    });
  });
}

// Call on startup
initBatchBoxListeners();

async function inspectAndVerifyUrl(rawUrl) {
  clearTimeout(checkUrlTimer);
  rawUrl = (rawUrl || "").trim().replace(/^["'<]+|["'>]+$/g, "");
  if (!rawUrl) {
    if (urlStatusCard) urlStatusCard.style.display = "none";
    resolvedCloudMetadata = null;
    return;
  }

  // Show inspecting state
  if (urlStatusCard) {
    urlStatusCard.style.display = "flex";
    urlStatusCard.className = "url-status-card";
    if (urlStatusIcon) urlStatusIcon.textContent = "⏳";
    if (urlStatusTitle) urlStatusTitle.textContent = "Inspecting video link…";
    if (urlStatusMeta) urlStatusMeta.textContent = "Connecting to cloud source to retrieve video filename & size…";
  }

  checkUrlTimer = setTimeout(async () => {
    try {
      const res = await fetch("/api/check_url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: rawUrl })
      });
      const data = await res.json();
      if (data.valid) {
        resolvedCloudMetadata = data;
        if (urlStatusCard) {
          urlStatusCard.style.display = "flex";
          urlStatusCard.className = "url-status-card verified";
          if (urlStatusIcon) urlStatusIcon.textContent = "🟢";
          if (urlStatusTitle) urlStatusTitle.textContent = `${data.provider} Video: ${data.filename}`;
          if (urlStatusMeta) urlStatusMeta.textContent = `Size: ${data.size_formatted} • Verified & ready for AI analysis!`;
        }
        clearError();
      } else {
        resolvedCloudMetadata = null;
        if (urlStatusCard) {
          urlStatusCard.style.display = "flex";
          urlStatusCard.className = "url-status-card";
          if (urlStatusIcon) urlStatusIcon.textContent = "☁️";
          if (urlStatusTitle) urlStatusTitle.textContent = "Cloud Video Link Detected";
          if (urlStatusMeta) urlStatusMeta.textContent = "Link format recognized. Ready to start counting.";
        }
      }
    } catch (err) {
      if (urlStatusCard) {
        urlStatusCard.style.display = "flex";
        urlStatusCard.className = "url-status-card";
        if (urlStatusIcon) urlStatusIcon.textContent = "🔗";
        if (urlStatusTitle) urlStatusTitle.textContent = "Video Link Attached";
        if (urlStatusMeta) urlStatusMeta.textContent = "Click 'Start Counting' to stream and analyze.";
      }
    }
  }, 300);
}

if (videoUrlInput) {
  videoUrlInput.addEventListener("input", () => {
    const val = videoUrlInput.value.trim();
    if (urlClearBtn) urlClearBtn.style.display = val ? "block" : "none";
    clearError();
    inspectAndVerifyUrl(val);
  });

  videoUrlInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      startJob();
    }
  });
}

if (urlClearBtn) {
  urlClearBtn.addEventListener("click", () => {
    if (videoUrlInput) videoUrlInput.value = "";
    urlClearBtn.style.display = "none";
    if (urlStatusCard) urlStatusCard.style.display = "none";
    resolvedCloudMetadata = null;
    clearError();
  });
}

if (urlPasteBtn) {
  urlPasteBtn.addEventListener("click", async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text && text.trim()) {
        switchToUrlTab(text.trim());
      } else {
        showError("Clipboard is empty. Copy your video link first.");
      }
    } catch (err) {
      if (videoUrlInput) {
        videoUrlInput.focus();
        videoUrlInput.select();
      }
      showError("Please press Ctrl+V to paste the link into the box.");
    }
  });
}

// Global & Dropzone Paste Handler (captures Ctrl+V anywhere on the page)
window.addEventListener("paste", (e) => {
  const activeEl = document.activeElement;
  if (activeEl && activeEl.tagName === "INPUT" && (activeEl.id === "video-url-input" || activeEl.classList.contains("batch-path-input"))) {
    return; // Regular paste into input; input event listener will trigger inspection
  }
  if (activeEl && (activeEl.tagName === "INPUT" || activeEl.tagName === "TEXTAREA")) {
    return;
  }

  const pastedText = (e.clipboardData || window.clipboardData)?.getData("text");
  if (pastedText) {
    const trimmed = pastedText.trim();
    if (
      trimmed.includes("drive.google.com") ||
      trimmed.includes("dropbox.com") ||
      trimmed.startsWith("http://") ||
      trimmed.startsWith("https://") ||
      trimmed.length >= 25
    ) {
      e.preventDefault();
      if (currentSourceTab === "batch") {
        for (let i = 1; i <= 3; i++) {
          const inp = document.getElementById(`batch-path-${i}`);
          if (inp && !inp.value.trim()) {
            inp.value = trimmed;
            checkBatchPath(i);
            showToast(`Pasted video link into Box ${i}`, "success");
            return;
          }
        }
        const inp1 = document.getElementById("batch-path-1");
        if (inp1) {
          inp1.value = trimmed;
          checkBatchPath(1);
          showToast(`Pasted video link into Box 1`, "success");
        }
        return;
      }
      switchToUrlTab(trimmed);
    }
  }
});


// Resilient 4MB Chunked Upload with Exponential Backoff Auto-Retries & Live Speed Metrics
async function uploadFileInChunks(file, onProgress) {
  const CHUNK_SIZE = 4 * 1024 * 1024; // 4MB safe proxy slices
  const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
  const uploadId = Date.now().toString(36) + Math.random().toString(36).substring(2, 9);
  let completedFilePath = null;

  showProgressCard(`Uploading "${file.name}" to Railway in 4MB chunks…`);
  const startTime = Date.now();
  let uploadedBytes = 0;

  for (let i = 0; i < totalChunks; i++) {
    const start = i * CHUNK_SIZE;
    const end = Math.min(file.size, start + CHUNK_SIZE);
    const chunkBlob = file.slice(start, end);
    const chunkSize = end - start;

    const chunkFormData = new FormData();
    chunkFormData.append("upload_id", uploadId);
    chunkFormData.append("chunk_index", i);
    chunkFormData.append("total_chunks", totalChunks);
    chunkFormData.append("filename", file.name);
    chunkFormData.append("chunk", chunkBlob, file.name);

    // Auto-retry up to 3 times per chunk with exponential backoff
    const MAX_RETRIES = 3;
    let chunkSuccess = false;
    let lastError = null;

    for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
      try {
        if (attempt > 1) {
          showRetryWarning(i + 1, attempt);
          await new Promise(r => setTimeout(r, 1000 * Math.pow(2, attempt - 2)));
        } else {
          hideRetryWarning();
        }

        const res = await fetch("/api/upload_chunk", { method: "POST", body: chunkFormData });
        const textResp = await res.text();
        let responseData = null;
        try {
          responseData = JSON.parse(textResp);
        } catch (parseErr) {
          if (!res.ok) {
            throw new Error(`Server returned HTTP ${res.status}: ${textResp.trim() || res.statusText}`);
          }
          throw new Error(`Invalid server response: ${textResp.slice(0, 100)}`);
        }

        if (!res.ok) {
          throw new Error(responseData.error || `Upload failed with status ${res.status}`);
        }

        chunkSuccess = true;
        hideRetryWarning();

        if (responseData && responseData.status === "complete") {
          completedFilePath = responseData.file_path;
        }
        break;
      } catch (err) {
        lastError = err;
        console.warn(`Chunk ${i + 1}/${totalChunks} attempt ${attempt} failed:`, err);
        if (attempt === MAX_RETRIES) {
          hideRetryWarning();
          throw new Error(`Failed to upload chunk ${i + 1}/${totalChunks} after ${MAX_RETRIES} attempts: ${err.message}`);
        }
      }
    }

    uploadedBytes += chunkSize;
    const elapsedSec = Math.max(0.1, (Date.now() - startTime) / 1000);
    const speedBytesPerSec = uploadedBytes / elapsedSec;
    const remainingBytes = file.size - uploadedBytes;
    const etaSec = speedBytesPerSec > 0 ? Math.ceil(remainingBytes / speedBytesPerSec) : 0;
    const pct = Math.round((uploadedBytes / file.size) * 100);

    updateProgressCard({
      stage: `Uploading chunk ${i + 1} of ${totalChunks} to Railway…`,
      pct: pct,
      uploadedBytes: uploadedBytes,
      totalBytes: file.size,
      speedBytesPerSec: speedBytesPerSec,
      etaSec: etaSec
    });

    if (onProgress) {
      onProgress(pct);
    }
  }

  return completedFilePath;
}

// Fetch Cloud Video (Google Drive, Dropbox, direct MP4) directly on Railway Server
async function fetchCloudVideo(url) {
  showProgressCard("Connecting to cloud video source from Railway datacenter…");
  clearError();

  const res = await fetch("/api/fetch_url", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: url })
  });

  const data = await res.json();
  if (!res.ok || !data.download_id) {
    throw new Error(data.error || "Failed to initiate cloud download.");
  }

  const downloadId = data.download_id;
  const startTime = Date.now();

  return new Promise((resolve, reject) => {
    const timer = setInterval(async () => {
      try {
        const pollRes = await fetch(`/api/fetch_url_progress/${downloadId}`);
        const pollData = await pollRes.json();

        if (pollData.error) {
          clearInterval(timer);
          hideProgressCard();
          reject(new Error(pollData.error));
          return;
        }

        if (pollData.status === "error") {
          clearInterval(timer);
          hideProgressCard();
          reject(new Error(pollData.error || "Cloud download failed."));
          return;
        }

        const downloaded = pollData.downloaded_bytes || 0;
        const total = pollData.total_bytes || 0;
        const pct = pollData.progress || 0;
        const elapsedSec = Math.max(0.1, (Date.now() - startTime) / 1000);
        const speed = downloaded / elapsedSec;
        const remaining = total > downloaded ? total - downloaded : 0;
        const eta = speed > 0 && total > 0 ? Math.ceil(remaining / speed) : 0;

        updateProgressCard({
          stage: pollData.status === "connecting"
            ? "Connecting to cloud source…"
            : `Streaming "${pollData.filename || 'video'}" directly into Railway…`,
          pct: Math.round(pct),
          uploadedBytes: downloaded,
          totalBytes: total,
          speedBytesPerSec: speed,
          etaSec: eta
        });

        if (pollData.done && pollData.status === "complete") {
          clearInterval(timer);
          resolve({
            filePath: pollData.file_path,
            filename: pollData.filename
          });
        }
      } catch (err) {
        clearInterval(timer);
        hideProgressCard();
        reject(err);
      }
    }, 1000);
  });
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
    const sideInItem = sideIn.closest(".rule-item");
    if (toggleIn.checked) {
      if (sideInItem) sideInItem.style.display = "flex";
      sideIn.textContent = `ENABLED (${inChecked} Sides)`;
      sideIn.style.color = "#3ddc84";
      if (badgeIn) badgeIn.textContent = "ACTIVE";
    } else {
      if (sideInItem) sideInItem.style.display = "none";
      if (badgeIn) badgeIn.textContent = "OFF";
    }
  }

  if (sideOut && toggleOut) {
    const sideOutItem = sideOut.closest(".rule-item");
    if (toggleOut.checked) {
      if (sideOutItem) sideOutItem.style.display = "flex";
      sideOut.textContent = `ENABLED (${outChecked} Sides)`;
      sideOut.style.color = "#ff4d4d";
      if (badgeOut) badgeOut.textContent = "ACTIVE";
    } else {
      if (sideOutItem) sideOutItem.style.display = "none";
      if (badgeOut) badgeOut.textContent = "OFF";
    }
  }

  const sideStatus = document.getElementById("side-status");
  if (sideStatus) {
    if (toggleOut && toggleOut.checked && (!toggleIn || !toggleIn.checked)) {
      sideStatus.textContent = "🔴 Counting GOING Vehicles Only (Backside / Tail)";
      sideStatus.style.color = "#ff4d4d";
    } else if (toggleIn && toggleIn.checked && (!toggleOut || !toggleOut.checked)) {
      sideStatus.textContent = "🟢 Counting COMING Vehicles Only (Face Showing)";
      sideStatus.style.color = "#3ddc84";
    } else if (toggleIn && toggleIn.checked && toggleOut && toggleOut.checked) {
      sideStatus.textContent = "🌐 Counting ALL Road Traffic (Going & Coming)";
      sideStatus.style.color = "var(--accent)";
    } else {
      sideStatus.textContent = "⚠️ All Counting Rules Disabled";
      sideStatus.style.color = "var(--text-dim)";
    }
  }

  if (typeof syncDirectionButtons === "function") syncDirectionButtons();
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
        active_lane: activeLane,
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

// Direct Direction Mode Toggle Buttons (Forward Going vs Face Showing Coming)
const dirBtnGoing = document.getElementById("dir-btn-going");
const dirBtnComing = document.getElementById("dir-btn-coming");

function syncDirectionButtons() {
  const toggleIn = document.getElementById("toggle-in");
  const toggleOut = document.getElementById("toggle-out");
  const inActive = toggleIn ? toggleIn.checked : false;
  const outActive = toggleOut ? toggleOut.checked : false;

  if (dirBtnGoing) {
    if (outActive) {
      dirBtnGoing.style.borderColor = "#ff4d4d";
      dirBtnGoing.style.background = "rgba(255, 77, 77, 0.25)";
      dirBtnGoing.style.color = "#fff";
      dirBtnGoing.style.boxShadow = "0 0 10px rgba(255, 77, 77, 0.3)";
    } else {
      dirBtnGoing.style.borderColor = "rgba(255, 255, 255, 0.12)";
      dirBtnGoing.style.background = "rgba(255, 255, 255, 0.04)";
      dirBtnGoing.style.color = "var(--text-dim)";
      dirBtnGoing.style.boxShadow = "none";
    }
  }

  if (dirBtnComing) {
    if (inActive) {
      dirBtnComing.style.borderColor = "#3ddc84";
      dirBtnComing.style.background = "rgba(61, 220, 132, 0.25)";
      dirBtnComing.style.color = "#fff";
      dirBtnComing.style.boxShadow = "0 0 10px rgba(61, 220, 132, 0.3)";
    } else {
      dirBtnComing.style.borderColor = "rgba(255, 255, 255, 0.12)";
      dirBtnComing.style.background = "rgba(255, 255, 255, 0.04)";
      dirBtnComing.style.color = "var(--text-dim)";
      dirBtnComing.style.boxShadow = "none";
    }
  }
}

if (dirBtnGoing) {
  dirBtnGoing.addEventListener("click", () => {
    const toggleIn = document.getElementById("toggle-in");
    const toggleOut = document.getElementById("toggle-out");
    if (toggleOut) toggleOut.checked = true;
    if (toggleIn) toggleIn.checked = false;
    document.querySelectorAll(".line-out-check").forEach(c => c.checked = true);
    document.querySelectorAll(".line-in-check").forEach(c => c.checked = false);
    syncDirectionButtons();
    updateSidebarRules();
    showToast("🔴 Going Vehicles (Backside) direction activated", "warning");
  });
}

if (dirBtnComing) {
  dirBtnComing.addEventListener("click", () => {
    const toggleIn = document.getElementById("toggle-in");
    const toggleOut = document.getElementById("toggle-out");
    if (toggleIn) toggleIn.checked = true;
    if (toggleOut) toggleOut.checked = false;
    document.querySelectorAll(".line-in-check").forEach(c => c.checked = true);
    document.querySelectorAll(".line-out-check").forEach(c => c.checked = false);
    syncDirectionButtons();
    updateSidebarRules();
    showToast("🟢 Coming Vehicles (Face Showing) direction activated", "success");
  });
}

// Coming Vehicles (Face Showing) Only Preset Handler
const presetComingOnlyBtn = document.getElementById("preset-coming-only-btn");
if (presetComingOnlyBtn) {
  presetComingOnlyBtn.addEventListener("click", () => {
    const toggleIn = document.getElementById("toggle-in");
    const toggleOut = document.getElementById("toggle-out");
    const directionModeSelect = document.getElementById("direction-mode-select");

    if (directionModeSelect) directionModeSelect.value = "COMING_GOING";
    if (toggleIn) toggleIn.checked = true;
    if (toggleOut) toggleOut.checked = false;

    // Check all IN lines, uncheck OUT lines
    document.querySelectorAll(".line-in-check").forEach(chk => chk.checked = true);
    document.querySelectorAll(".line-out-check").forEach(chk => chk.checked = false);

    syncDirectionButtons();
    updateSidebarRules();
    showToast("🟢 Configured for Coming Vehicles (Face Showing) Only! Going flow is OFF.", "success");
  });
}

// Going Vehicles (Backside) Only Preset Handler
const presetGoingOnlyBtn = document.getElementById("preset-going-only-btn");
if (presetGoingOnlyBtn) {
  presetGoingOnlyBtn.addEventListener("click", () => {
    const toggleIn = document.getElementById("toggle-in");
    const toggleOut = document.getElementById("toggle-out");
    const directionModeSelect = document.getElementById("direction-mode-select");

    if (directionModeSelect) directionModeSelect.value = "COMING_GOING";
    if (toggleIn) toggleIn.checked = false;
    if (toggleOut) toggleOut.checked = true;

    // Check all OUT lines, uncheck IN lines
    document.querySelectorAll(".line-in-check").forEach(chk => chk.checked = false);
    document.querySelectorAll(".line-out-check").forEach(chk => chk.checked = true);

    syncDirectionButtons();
    updateSidebarRules();
    showToast("🔴 Configured for Going Vehicles (Backside) Only! Coming flow is OFF.", "warning");
  });
}

// Both Directions Preset Handler
const presetBothFlowsBtn = document.getElementById("preset-both-flows-btn");
if (presetBothFlowsBtn) {
  presetBothFlowsBtn.addEventListener("click", () => {
    const toggleIn = document.getElementById("toggle-in");
    const toggleOut = document.getElementById("toggle-out");
    const directionModeSelect = document.getElementById("direction-mode-select");

    if (directionModeSelect) directionModeSelect.value = "COMING_GOING";
    if (toggleIn) toggleIn.checked = true;
    if (toggleOut) toggleOut.checked = true;

    // Check all lines
    document.querySelectorAll(".line-in-check").forEach(chk => chk.checked = true);
    document.querySelectorAll(".line-out-check").forEach(chk => chk.checked = true);

    syncDirectionButtons();
    updateSidebarRules();
    showToast("⚡ Configured for Both Directions! (Coming & Going traffic enabled)", "info");
  });
}

// 1-Side Lane Preset Handler
const preset1SideBtn = document.getElementById("preset-1side-btn");
if (preset1SideBtn) {
  preset1SideBtn.addEventListener("click", () => {
    const toggleIn = document.getElementById("toggle-in");
    const toggleOut = document.getElementById("toggle-out");

    if (toggleIn) toggleIn.checked = true;
    if (toggleOut) toggleOut.checked = false;

    // Check North IN, uncheck others
    document.querySelectorAll(".line-in-check").forEach(chk => chk.checked = (chk.value === "North"));
    document.querySelectorAll(".line-out-check").forEach(chk => chk.checked = false);

    syncDirectionButtons();
    updateSidebarRules();
    showToast("🚗 Configured for 1-Side Coming Lane! (North IN lane active, Going flow disabled)", "success");
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

  let file = null;
  let url = null;

  const urlVal = (videoUrlInput ? videoUrlInput.value : "").trim();
  const fileVal = fileInput ? fileInput.files[0] : null;

  if (currentSourceTab === "file" && !fileVal && urlVal) {
    currentSourceTab = "url";
  }

  if (currentSourceTab === "file") {
    file = fileVal;
    if (!file) {
      showError("Please select a video file or paste a video link.");
      return;
    }
  } else {
    url = urlVal;
    if (!url) {
      showError("Please enter a valid video or cloud link URL.");
      return;
    }
  }

  startBtn.disabled = true;
  startBtn.textContent = "Preparing…";

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

  // Use active lane config (Banani→Gulshan or Gulshan→Mohakhali)
  const laneConfig = getLaneCountingConfig();
  const enableIn = laneConfig.enableIn;
  const enableOut = laneConfig.enableOut;
  const enabledLinesIn = laneConfig.enabledLinesIn;
  const enabledLinesOut = laneConfig.enabledLinesOut;
  const allEnabledLines = Array.from(new Set([...enabledLinesIn, ...enabledLinesOut]));

  try {
    let uploadedFilePath = null;
    let videoFilename = "video.mp4";

    if (currentSourceTab === "file") {
      videoFilename = file.name;
      uploadedFilePath = await uploadFileInChunks(file, (pct) => {
        startBtn.textContent = `Uploading ${pct}%…`;
      });
    } else {
      startBtn.textContent = "Fetching Cloud Video…";
      const cloudRes = await fetchCloudVideo(url);
      uploadedFilePath = cloudRes.filePath;
      videoFilename = cloudRes.filename;
    }

    hideProgressCard();
    startBtn.textContent = "Starting Analysis…";

    const startFormData = new FormData();
    if (uploadedFilePath) {
      startFormData.append("file_path", uploadedFilePath);
    }
    startFormData.append("filename", videoFilename);
    startFormData.append("speed", speed);
    startFormData.append("line_mode", lineMode);
    startFormData.append("direction_mode", directionMode);
    startFormData.append("active_lane", activeLane);
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
    showError("Video ingestion error: " + err.message);
    resetStartBtn();
  }
}

function resetStartBtn() {
  startBtn.disabled = false;
  startBtn.textContent = "Start Counting";
  hideProgressCard();
}

function resetCancelBtn() {
  cancelBtn.disabled = false;
  cancelBtn.textContent = "🛑 Stop & Get PDF";
}

function beginRunView() {
  hideProgressCard();
  reportCard.hidden = true;
  runCard.hidden = false;
  runTitle.textContent = "Processing…";
  streamImg.onerror = () => {
    if (currentJobId) {
      setTimeout(() => {
        if (currentJobId) {
          streamImg.src = `/api/stream/${currentJobId}?t=${Date.now()}`;
        }
      }, 1000);
    }
  };
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

  if (!isInActive && !isOutActive) {
    sideLinesBlock.hidden = true;
    return;
  }

  const enabledIn = Array.from(document.querySelectorAll(".line-in-check:checked")).map(c => c.value.toLowerCase());
  const enabledOut = Array.from(document.querySelectorAll(".line-out-check:checked")).map(c => c.value.toLowerCase());

  let totalInCount = 0;
  let totalOutCount = 0;

  entries.forEach(([name, v]) => {
    totalInCount += (v.in || 0);
    totalOutCount += (v.out || 0);
  });

  sideLinesBlock.hidden = false;

  let html = `<div class="live-flow-summary-badge" style="display: flex; gap: 8px; margin-bottom: 10px;">`;
  if (isInActive) {
    html += `
      <div style="flex: 1; background: rgba(16, 185, 129, 0.15); border: 1px solid #10b981; border-radius: 8px; padding: 6px 10px; text-align: center;">
        <span style="font-size: 0.7rem; color: #3ddc84; font-weight: 700; display: block;">🟢 COMING FLOW</span>
        <span style="font-size: 1.1rem; color: #fff; font-weight: 800;">${totalInCount}</span>
      </div>`;
  }
  if (isOutActive) {
    html += `
      <div style="flex: 1; background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; border-radius: 8px; padding: 6px 10px; text-align: center;">
        <span style="font-size: 0.7rem; color: #ff4d4d; font-weight: 700; display: block;">🔴 GOING FLOW (Back)</span>
        <span style="font-size: 1.1rem; color: #fff; font-weight: 800;">${totalOutCount}</span>
      </div>`;
  }
  html += `</div>`;

  let activeLineCardsHtml = "";

  entries.forEach(([name, v], i) => {
    const sideKey = name.replace(" Line", "").toLowerCase();
    const inActive = isInActive && (enabledIn.length === 0 || enabledIn.includes(sideKey));
    const outActive = isOutActive && (enabledOut.length === 0 || enabledOut.includes(sideKey));

    // Auto-hide lines that are NOT active in the enabled rules
    if (!inActive && !outActive) return;

    let lineTotal = 0;
    if (inActive) lineTotal += (v.in || 0);
    if (outActive) lineTotal += (v.out || 0);

    activeLineCardsHtml += `
      <div class="line-row" style="flex-direction: column; align-items: stretch; gap: 4px; padding: 8px 10px; background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 8px; margin-bottom: 6px;">
        <div style="display: flex; align-items: center; justify-content: space-between;">
          <span class="line-row-name" style="font-weight: 700; font-size: 0.82rem; color: #fff;">
            <span class="line-dot" style="background:${LINE_COLORS[i % LINE_COLORS.length]}"></span>
            ${escapeHtml(name)}
          </span>
          <span style="font-size: 0.78rem; color: #3ddc84; font-weight: 700;">Active: ${lineTotal}</span>
        </div>
        <div style="display: flex; gap: 6px; margin-top: 4px;">`;

    if (inActive) {
      activeLineCardsHtml += `
          <span style="flex: 1; font-size: 0.72rem; padding: 4px 6px; border-radius: 5px; background: rgba(16, 185, 129, 0.18); color: #3ddc84; border: 1px solid rgba(16, 185, 129, 0.4); font-weight: 700; text-align: center;">
            🟢 COMING: ${v.in || 0}
          </span>`;
    }

    if (outActive) {
      activeLineCardsHtml += `
          <span style="flex: 1; font-size: 0.72rem; padding: 4px 6px; border-radius: 5px; background: rgba(239, 68, 68, 0.18); color: #ff4d4d; border: 1px solid rgba(239, 68, 68, 0.4); font-weight: 700; text-align: center;">
            🔴 GOING (Tail): ${v.out || 0}
          </span>`;
    }

    activeLineCardsHtml += `
        </div>
      </div>`;
  });

  lineRows.innerHTML = html + activeLineCardsHtml;
}

function formatCategoryName(name) {
  const map = {
    "Bus / Mini Bus": "Bus",
    "Sedan / Private Car": "Car",
    "Microbus (inc. Ambulance)": "Microbus",
    "Three-Wheeler (CNG)": "CNG",
    "Jeep / Pickup / SUV": "Pickup",
    "Motorized Rickshaw (Easybike)": "Easybike",
    "Rickshaw / Van": "Rickshaw",
    "Truck (Heavy & Medium)": "Truck",
    "Mini Truck / Covered Van": "Covered Van",
    "Human Hauler / Leguna / Tempo": "Leguna",
    "Animal / Push Cart (Thela Gari)": "Thela Gari",
    "Other / Agricultural": "Other",
  };
  return map[name] || name;
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
      <span class="category-row-name">${escapeHtml(formatCategoryName(name))}</span>
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

    if (data.status === "running") {
      runTitle.textContent = `Analyzing Video (${data.progress}%)…`;
      sideStatus.textContent = "Live Analysis Active 🟢";
      sideStatus.classList.add("is-live");
    } else if (data.status === "starting") {
      runTitle.textContent = "Starting AI Engine…";
      sideStatus.textContent = "Initializing AI Engine… ⏳";
    }

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

const CATEGORY_ICONS = {
  "Bus": "🚌",
  "Large Bus": "🚌",
  "Mini Bus": "🚐",
  "Bus / Mini Bus": "🚌",
  "Car": "🚗",
  "Private Car": "🚗",
  "Sedan": "🚗",
  "Sedan / Private Car": "🚗",
  "Microbus": "🚐",
  "Pickup": "🛻",
  "SUV": "🚙",
  "Jeep": "🚙",
  "Jeep / Pickup / SUV": "🚙",
  "Truck": "🚚",
  "Medium Truck": "🚚",
  "Heavy Truck": "🚛",
  "Heavy Truck / Container": "🚛",
  "Covered Van": "🚐",
  "Motorcycle": "🏍️",
  "Motorbike": "🏍️",
  "CNG": "🛺",
  "Three-Wheeler (CNG)": "🛺",
  "Auto": "🛺",
  "Rickshaw": "🚲",
  "Rickshaw / Van": "🚲",
  "Motorized Rickshaw": "🛺",
  "Easybike": "🛺",
  "Bicycle": "🚲",
  "Human Hauler": "🚐",
  "Leguna": "🚐",
  "Thela Gari": "🛒",
};

function getCategoryIcon(name) {
  return CATEGORY_ICONS[name] || "🚗";
}

function resetBatchBuildBtn() {
  if (!batchBuildBtn) return;
  batchBuildBtn.disabled = false;
  batchBuildBtn.innerHTML = `
    <div class="btn-inner-content">
      <span class="btn-icon">🔨</span>
      <div class="btn-text-group">
        <span class="btn-main-title">BUILD &amp; RUN 3-VIDEO AUTO ANALYSIS</span>
        <span class="btn-sub-title">Auto-Analyze Video 1 ➔ Video 2 ➔ Video 3 Sequentially &amp; Build 1 Consolidated Result Sheet</span>
      </div>
    </div>`;
}

async function startBatchJob() {
  clearError();
  const p1 = (document.getElementById("batch-path-1")?.value || "").trim();
  const p2 = (document.getElementById("batch-path-2")?.value || "").trim();
  const p3 = (document.getElementById("batch-path-3")?.value || "").trim();

  if (!p1 || !p2 || !p3) {
    showError("Please specify all 3 video paths in Box 1, Box 2, and Box 3 (or click the Sample buttons).");
    return;
  }

  if (batchBuildBtn) {
    batchBuildBtn.disabled = true;
    batchBuildBtn.innerHTML = `
      <div class="btn-inner-content">
        <span class="btn-icon">⏳</span>
        <div class="btn-text-group">
          <span class="btn-main-title">BUILDING 3-VIDEO BATCH PIPELINE…</span>
          <span class="btn-sub-title">Validating video files and initializing sequential AI engine</span>
        </div>
      </div>`;
  }

  // Pre-fetch any cloud URLs (Google Drive / Dropbox / URL) using fetchCloudVideo
  const rawPaths = [p1, p2, p3];
  const finalPaths = [];

  for (let i = 0; i < rawPaths.length; i++) {
    const p = rawPaths[i];
    const vidNum = i + 1;
    if (isCloudUrl(p)) {
      if (batchBuildBtn) {
        batchBuildBtn.innerHTML = `
          <div class="btn-inner-content">
            <span class="btn-icon">☁️</span>
            <div class="btn-text-group">
              <span class="btn-main-title">FETCHING CLOUD VIDEO ${vidNum} OF 3…</span>
              <span class="btn-sub-title">Streaming video into server for processing</span>
            </div>
          </div>`;
      }
      showToast(`Fetching Video ${vidNum} from cloud (Google Drive / URL)…`, "info");
      try {
        const cloudRes = await fetchCloudVideo(p);
        finalPaths.push(cloudRes.filePath);
        const statusBadge = document.getElementById(`batch-status-${vidNum}`);
        if (statusBadge) {
          statusBadge.textContent = `🟢 Ready: ${cloudRes.filename}`;
          statusBadge.className = "batch-box-status verified";
        }
        const statusCard = document.getElementById(`batch-status-card-${vidNum}`);
        if (statusCard) {
          statusCard.style.display = "flex";
          statusCard.className = "batch-status-card verified";
          const iconEl = document.getElementById(`batch-status-icon-${vidNum}`);
          const titleEl = document.getElementById(`batch-status-title-${vidNum}`);
          const metaEl = document.getElementById(`batch-status-meta-${vidNum}`);
          if (iconEl) iconEl.textContent = "🟢";
          if (titleEl) titleEl.textContent = `Fetched: ${cloudRes.filename}`;
          if (metaEl) metaEl.textContent = `Downloaded to server and ready for AI batch analysis.`;
        }
      } catch (err) {
        showError(`Failed to fetch cloud video ${vidNum}: ${err.message}`);
        resetBatchBuildBtn();
        hideProgressCard();
        return;
      }
    } else {
      finalPaths.push(p);
    }
  }
  hideProgressCard();

  const speedSelect = document.getElementById("speed-select");
  const lineModeSelect = document.getElementById("line-mode-select");
  const directionModeSelect = document.getElementById("direction-mode-select");
  const toggleIn = document.getElementById("toggle-in");
  const toggleOut = document.getElementById("toggle-out");
  const countScopeRadio = document.querySelector('input[name="count_scope_mode"]:checked');

  const speed = speedSelect ? speedSelect.value : "2";
  const lineMode = lineModeSelect ? lineModeSelect.value : "smart_flow";
  const directionMode = directionModeSelect ? directionModeSelect.value : "COMING_GOING";
  const countScopeMode = countScopeRadio ? countScopeRadio.value : "active_only";

  // Use active lane config (Banani→Gulshan or Gulshan→Mohakhali)
  const laneConfig = getLaneCountingConfig();
  const enableIn = laneConfig.enableIn;
  const enableOut = laneConfig.enableOut;
  const enabledLinesIn = laneConfig.enabledLinesIn;
  const enabledLinesOut = laneConfig.enabledLinesOut;
  const allEnabledLines = Array.from(new Set([...enabledLinesIn, ...enabledLinesOut]));

  try {
    const res = await fetch("/api/batch/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        videos: finalPaths,
        speed,
        active_lane: activeLane,
        line_mode: lineMode,
        direction_mode: directionMode,
        enable_in: enableIn,
        enable_out: enableOut,
        count_scope_mode: countScopeMode,
        enabled_lines: allEnabledLines,
        enabled_lines_in: enabledLinesIn,
        enabled_lines_out: enabledLinesOut
      })
    });

    const data = await res.json();
    if (!res.ok || !data.batch_id) {
      showError(data.error || "Failed to start 3-video batch.");
      resetBatchBuildBtn();
      return;
    }

    currentBatchId = data.batch_id;
    beginBatchRunView(finalPaths);
  } catch (e) {
    showError("Batch launch error: " + e.message);
    resetBatchBuildBtn();
  }
}

function beginBatchRunView(videoPaths) {
  hideProgressCard();
  reportCard.hidden = true;
  if (batchReportContainer) batchReportContainer.hidden = true;
  runCard.hidden = false;

  if (batchStepperBar) {
    batchStepperBar.hidden = false;
    for (let i = 1; i <= 3; i++) {
      const stepItem = document.getElementById(`stepper-step-${i}`);
      const nameEl = document.getElementById(`stepper-name-${i}`);
      const statEl = document.getElementById(`stepper-status-${i}`);
      if (stepItem) stepItem.className = "batch-step-item" + (i === 1 ? " active" : "");
      if (nameEl) {
        const rawPath = videoPaths[i - 1] || `Video ${i}`;
        nameEl.textContent = rawPath.split("/").pop();
      }
      if (statEl) statEl.textContent = i === 1 ? "Analyzing…" : "Waiting";
    }
  }

  runTitle.textContent = "Sequential Batch Pipeline Running (Video 1 of 3)…";
  resetCancelBtn();
  sideTotal.textContent = "0";
  sideStatus.textContent = "Analyzing Video 1 of 3 🟢";
  sideStatus.classList.add("is-live");
  sideLinesBlock.hidden = true;
  sideCategoriesBlock.hidden = true;
  sideMetaBlock.hidden = false;

  runCard.scrollIntoView({ behavior: "smooth", block: "start" });
  clearInterval(batchPollTimer);
  batchPollTimer = setInterval(pollBatchStatus, 500);
}

let activeStreamJobId = null;

async function pollBatchStatus() {
  if (!currentBatchId) return;
  try {
    const res = await fetch(`/api/batch/status/${currentBatchId}`);
    const data = await res.json();
    if (!res.ok) return;

    const curIdx = data.current_index || 0;
    const curVideoNum = curIdx + 1;
    const curJob = data.current_job;

    // Update Stepper visual states
    if (batchStepperBar) {
      for (let i = 1; i <= 3; i++) {
        const stepItem = document.getElementById(`stepper-step-${i}`);
        const statEl = document.getElementById(`stepper-status-${i}`);
        if (i < curVideoNum) {
          if (stepItem) stepItem.className = "batch-step-item done";
          if (statEl) {
            const vRes = data.results && data.results[i - 1];
            statEl.textContent = `✓ Done (${vRes ? vRes.count : 0} counted)`;
          }
        } else if (i === curVideoNum && !data.done) {
          if (stepItem) stepItem.className = "batch-step-item active";
          if (statEl) statEl.textContent = `Analyzing ${curJob ? curJob.progress : 0}%…`;
        } else if (data.done && data.status === "complete") {
          if (stepItem) stepItem.className = "batch-step-item done";
          if (statEl) {
            const vRes = data.results && data.results[i - 1];
            statEl.textContent = `✓ Done (${vRes ? vRes.count : 0} counted)`;
          }
        } else {
          if (stepItem) stepItem.className = "batch-step-item";
          if (statEl) statEl.textContent = "Waiting";
        }
      }
    }

    // Switch video preview stream when active sub-job transitions
    if (data.current_job_id && data.current_job_id !== activeStreamJobId) {
      activeStreamJobId = data.current_job_id;
      streamImg.src = `/api/stream/${activeStreamJobId}?t=${Date.now()}`;
    }

    if (curJob) {
      runTitle.textContent = `Analyzing Video ${curVideoNum} of 3: ${curJob.video || ""} (${curJob.progress}%)…`;
      sideStatus.textContent = `Analyzing Video ${curVideoNum} of 3 🟢`;
      sideTotal.textContent = curJob.count;
      statProgress.textContent = `${curJob.progress}%`;
      statFrames.textContent = curJob.total_frames ? `frame ${curJob.frame_idx}/${curJob.total_frames}` : "";
      progressFill.style.width = `${curJob.progress}%`;

      renderLines(curJob.lines, "COMING_GOING");
      renderCategories(curJob.categories);
    }

    if (data.done) {
      clearInterval(batchPollTimer);
      batchPollTimer = null;
      resetBatchBuildBtn();
      resetCancelBtn();

      sideStatus.textContent = data.status === "complete" ? "All 3 Videos Completed! 🏁" : "Batch Stopped";
      sideStatus.classList.remove("is-live");

      renderBatchReport(data);
      currentBatchId = null;
      activeStreamJobId = null;
      loadHistory();
    }
  } catch (err) {
    // transient network glitch, keep polling
  }
}

function renderBatchReport(data) {
  runCard.hidden = true;
  reportCard.hidden = false;
  if (batchReportContainer) batchReportContainer.hidden = false;

  const isStopped = data.status === "cancelled";
  const totals = data.consolidated?.totals || {};
  const grandTotal = totals.grand_total || 0;

  if (reportMainTitle) reportMainTitle.textContent = "3-Video Analysis Completed!";
  if (reportCountLabel) reportCountLabel.textContent = `${grandTotal} total vehicles counted across 3 videos ${isStopped ? "(Stopped)" : ""}`;
  if (batchGrandTotalDisplay) batchGrandTotalDisplay.textContent = grandTotal;

  // Set column headers with filenames
  const results = data.results || [];
  const v1Name = results[0]?.video || "Video 1";
  const v2Name = results[1]?.video || "Video 2";
  const v3Name = results[2]?.video || "Video 3";

  if (thVideo1) thVideo1.textContent = `Video 1: ${v1Name}`;
  if (thVideo2) thVideo2.textContent = `Video 2: ${v2Name}`;
  if (thVideo3) thVideo3.textContent = `Video 3: ${v3Name}`;

  // Populate Matrix Table Body
  const matrix = data.consolidated?.categories || {};
  const catEntries = Object.entries(matrix).sort((a, b) => b[1].total - a[1].total);

  if (batchMatrixBody) {
    if (!catEntries.length) {
      batchMatrixBody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding: 20px; color: var(--text-dim);">No vehicle counts recorded.</td></tr>`;
    } else {
      batchMatrixBody.innerHTML = catEntries.map(([catName, rowData]) => {
        const icon = getCategoryIcon(catName);
        return `
          <tr>
            <td>
              <span style="font-size: 1.1rem; margin-right: 6px;">${icon}</span>
              <strong>${escapeHtml(catName)}</strong>
            </td>
            <td>${rowData.video1 || 0}</td>
            <td>${rowData.video2 || 0}</td>
            <td>${rowData.video3 || 0}</td>
            <td class="td-total-col">
              <span style="background: rgba(61, 220, 132, 0.2); color: #3ddc84; font-weight: 800; padding: 2px 10px; border-radius: 6px; border: 1px solid rgba(61, 220, 132, 0.4);">
                ${rowData.total || 0}
              </span>
            </td>
            <td style="color: var(--text-dim);">${rowData.share || 0}%</td>
          </tr>
        `;
      }).join("");
    }
  }

  // Populate Matrix Footer
  if (batchMatrixFoot) {
    batchMatrixFoot.innerHTML = `
      <tr>
        <td>GRAND TOTAL</td>
        <td>${totals.video1 || 0}</td>
        <td>${totals.video2 || 0}</td>
        <td>${totals.video3 || 0}</td>
        <td class="td-grand-total">${grandTotal}</td>
        <td>100.0%</td>
      </tr>
    `;
  }

  // Set download links
  if (downloadPdf && data.report_pdf) {
    downloadPdf.href = data.report_pdf;
    if (pdfBtnLabel) pdfBtnLabel.textContent = "Download Consolidated PDF Report";
  }
  if (downloadXlsx && data.report_xlsx) {
    downloadXlsx.href = data.report_xlsx;
    if (xlsxBtnLabel) xlsxBtnLabel.textContent = "Download Consolidated Excel (.xlsx) Report";
  }

  reportCard.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function cancelJob() {
  if (currentBatchId) {
    cancelBtn.disabled = true;
    cancelBtn.textContent = "Stopping Batch…";
    try {
      await fetch(`/api/batch/cancel/${currentBatchId}`, { method: "POST" });
    } catch (e) {}
    return;
  }
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
  if (videoUrlInput) {
    videoUrlInput.value = "";
    if (urlClearBtn) urlClearBtn.style.display = "none";
  }
  updateDropZoneLabel();
  clearError();
  resetStartBtn();
  resetBatchBuildBtn();
  resetCancelBtn();
  hideProgressCard();
  reportCard.hidden = true;
  if (batchReportContainer) batchReportContainer.hidden = true;
  if (batchStepperBar) batchStepperBar.hidden = true;
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

  let videoDisplayName = "";
  const urlVal = (videoUrlInput ? videoUrlInput.value : "").trim();
  const file = fileInput ? fileInput.files[0] : null;

  if (currentSourceTab === "file" && !file && urlVal) {
    currentSourceTab = "url";
  }

  if (currentSourceTab === "file") {
    if (!file) {
      showError("Please select a video file or paste a video link first.");
      return;
    }
    videoDisplayName = file.name;
  } else {
    if (!urlVal) {
      showError("Please enter or paste a valid video link first.");
      return;
    }
    if (resolvedCloudMetadata && resolvedCloudMetadata.filename) {
      videoDisplayName = `${resolvedCloudMetadata.provider}: ${resolvedCloudMetadata.filename}`;
    } else {
      let parsedName = urlVal.split("/").filter(Boolean).pop() || "Cloud Video";
      if (parsedName.includes("?")) parsedName = parsedName.split("?")[0];
      if (urlVal.includes("drive.google.com")) parsedName = "Google Drive Video";
      else if (urlVal.includes("dropbox.com")) parsedName = "Dropbox Video: " + parsedName;
      videoDisplayName = parsedName;
    }
  }

  const speedSelect = document.getElementById("speed-select");
  const lineModeSelect = document.getElementById("line-mode-select");
  const toggleIn = document.getElementById("toggle-in");
  const toggleOut = document.getElementById("toggle-out");
  const directionRadio = document.querySelector('input[name="direction_mode"]:checked');
  const activeLines = Array.from(document.querySelectorAll(".line-check:checked")).map(c => c.value);

  const modeMap = {
    "smart_flow": "✨ Smart Trajectory Flow (Zero Miss)",
    "dual_gate": "⚡ Dual-Gate Virtual Trap",
    "box": "4-Way Intersection Box",
    "horizontal": "Single Horizontal Line",
    "vertical": "Vertical Boundary Line"
  };
  const termMap = { "IN_OUT": "IN / OUT", "COMING_GOING": "COMING / GOING", "FORWARD_BACKWARD": "FORWARD / BACKWARD" };

  const modeText = modeMap[lineModeSelect ? lineModeSelect.value : "smart_flow"] || "✨ Smart Trajectory Flow (Zero Miss)";
  const speedText = speedMap[speedSelect ? speedSelect.value : "2"] || "2x Fast-Forward";
  const directionModeSelect = document.getElementById("direction-mode-select");
  const directionVal = directionModeSelect ? directionModeSelect.value : "COMING_GOING";
  const namingText = termMap[directionVal] || "COMING / GOING";

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

  if (videoVal) videoVal.textContent = videoDisplayName;
  if (modeVal) modeVal.textContent = modeText;
  if (speedVal) speedVal.textContent = speedText;
  if (namingVal) namingVal.textContent = namingText;
  if (flowsVal) flowsVal.textContent = flowStr;
  if (linesVal) linesVal.textContent = linesStr;

  let summary = `The AI engine will analyze '${videoDisplayName}' using ${modeText} at ${speedText}. `;
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

if (batchBuildBtn) batchBuildBtn.addEventListener("click", startBatchJob);
startBtn.addEventListener("click", startJob);
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
