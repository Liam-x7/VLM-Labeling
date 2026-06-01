// ============================================
// Annotation System - Frontend Logic
// ============================================

const state = {
  apiBase: localStorage.getItem("anno.apiBase") || "",
  token: localStorage.getItem("anno.token") || "",
  username: localStorage.getItem("anno.username") || "",
  role: localStorage.getItem("anno.role") || "",
  view: "auth",
  datasets: [],
  currentDataset: null,
  records: [],
  currentIndex: -1,
  currentRecord: null,
  dirty: false,
  autoSaveTimer: null,
  zoom: { scale: 1, x: 0, y: 0, panning: false, startX: 0, startY: 0 },
  batchDs: "",
  batchCp: "",
  adminTab: "pending",
  authPage: "login",
  pendingUsername: "",
};

// --- DOM refs ---
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const els = {
  authView: $("#authView"),
  manageView: $("#manageView"),
  annotateView: $("#annotateView"),
  statsView: $("#statsView"),
  adminView: $("#adminView"),
  fileTree: $("#fileTree"),
  fileUpload: $("#fileUpload"),
  toast: $("#toast"),

  // Auth pages
  loginPage: $("#loginPage"),
  registerPage: $("#registerPage"),
  loginForm: $("#loginForm"),
  registerForm: $("#registerForm"),
  loginUsername: $("#loginUsername"),
  loginPassword: $("#loginPassword"),
  loginSubmit: $("#loginSubmit"),
  loginError: $("#loginError"),
  regUsername: $("#regUsername"),
  regPassword: $("#regPassword"),
  regPasswordConfirm: $("#regPasswordConfirm"),
  registerSubmit: $("#registerSubmit"),
  registerError: $("#registerError"),
  goToRegister: $("#goToRegister"),
  goToLogin: $("#goToLogin"),

  // Manage
  backToManage: $("#backToManage"),
  backToManageFromStats: $("#backToManageFromStats"),
  backToManageFromAdmin: $("#backToManageFromAdmin"),
  annoBreadcrumb: $("#annoBreadcrumb"),
  adminActions: $("#adminActions"),
  adminBtn: $("#adminBtn"),
  currentUsername: $("#currentUsername"),
  logoutBtn: $("#logoutBtn"),

  // Annotation header
  prevBtn: $("#prevBtn"),
  nextBtn: $("#nextBtn"),
  saveBtn: $("#saveBtn"),
  saveStatus: $("#saveStatus"),
  progressFill: $("#progressFill"),
  progressText: $("#progressText"),
  annotatedStatus: $("#annotatedStatus"),

  // Image
  annoImage: $("#annoImage"),
  imageContainer: $("#imageContainer"),
  imageLoading: $("#imageLoading"),
  loadingText: $("#loadingText"),
  loadingBarFill: $("#loadingBarFill"),
  zoomHint: $("#zoomHint"),
  imageInfo: $("#imageInfo"),

  // Prompts
  systemInput: $("#systemInput"),
  userInput: $("#userInput"),
  answerInput: $("#answerInput"),

  // Stats
  statsDsList: $("#statsDsList"),
  statsTitle: $("#statsTitle"),
  statsTableWrap: $("#statsTableWrap"),

  // Admin
  adminTitle: $("#adminTitle"),
  adminTableWrap: $("#adminTableWrap"),

  // Modal
  batchReplaceModal: $("#batchReplaceModal"),
  modalTitle: $("#modalTitle"),
  modalClose: $("#modalClose"),
  modalCancel: $("#modalCancel"),
  modalConfirm: $("#modalConfirm"),
  replaceSystemCheck: $("#replaceSystemCheck"),
  replaceUserCheck: $("#replaceUserCheck"),
  replaceSystemInput: $("#replaceSystemInput"),
  replaceUserInput: $("#replaceUserInput"),

  // Change Password Modal
  changePasswordModal: $("#changePasswordModal"),
  cpModalClose: $("#cpModalClose"),
  cpModalCancel: $("#cpModalCancel"),
  cpModalConfirm: $("#cpModalConfirm"),
  cpOldPassword: $("#cpOldPassword"),
  cpNewPassword: $("#cpNewPassword"),
  cpNewPasswordConfirm: $("#cpNewPasswordConfirm"),
};

// ============================================
// Utilities
// ============================================

function esc(s) {
  return String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function showError(el, msg) {
  el.textContent = msg;
  el.hidden = false;
}

function hideError(el) {
  el.hidden = true;
}

// ============================================
// API
// ============================================

function apiUrl(path) {
  const base = state.apiBase.replace(/\/$/, "");
  if (!base) {
    return path.startsWith("/") ? path : `/${path}`;
  }
  return `${base}${path}`;
}

async function request(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.token) {
    headers["Authorization"] = `Bearer ${state.token}`;
  }
  const response = await fetch(apiUrl(path), { headers, ...options });
  if (response.status === 401) {
    clearAuth();
    showView("auth");
    throw new Error("登录已过期，请重新登录");
  }
  const raw = await response.text();
  let payload = {};
  if (raw) {
    try { payload = JSON.parse(raw); } catch { throw new Error("Invalid JSON response"); }
  }
  if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
  return payload;
}

async function requestPublic(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  const response = await fetch(apiUrl(path), { headers, ...options });
  const raw = await response.text();
  let payload = {};
  if (raw) {
    try { payload = JSON.parse(raw); } catch { throw new Error("Invalid JSON response"); }
  }
  if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
  return payload;
}

function assetUrl(path) {
  const root = state.apiBase.replace(/\/api\/?$/, "");
  return `${root}${path}`;
}

// ============================================
// Auth
// ============================================

function saveAuth(token, username, role) {
  state.token = token;
  state.username = username;
  state.role = role;
  localStorage.setItem("anno.token", token);
  localStorage.setItem("anno.username", username);
  localStorage.setItem("anno.role", role);
}

function clearAuth() {
  state.token = "";
  state.username = "";
  state.role = "";
  localStorage.removeItem("anno.token");
  localStorage.removeItem("anno.username");
  localStorage.removeItem("anno.role");
}

function setSubmitLoading(btn, loading) {
  const text = btn.querySelector(".btn-text");
  const spinner = btn.querySelector(".btn-spinner");
  if (loading) {
    btn.disabled = true;
    if (text) text.hidden = true;
    if (spinner) spinner.hidden = false;
  } else {
    btn.disabled = false;
    if (text) text.hidden = false;
    if (spinner) spinner.hidden = true;
  }
}

function showAuthPage(page) {
  state.authPage = page;
  if (page === "login") {
    els.loginPage.classList.remove("hidden");
    els.registerPage.classList.add("hidden");
    hideError(els.loginError);
    els.loginUsername.focus();
  } else {
    els.loginPage.classList.add("hidden");
    els.registerPage.classList.remove("hidden");
    hideError(els.registerError);
    els.regUsername.focus();
  }
}

async function handleLogin(e) {
  e.preventDefault();
  hideError(els.loginError);
  const username = els.loginUsername.value.trim();
  const password = els.loginPassword.value;
  if (!username || !password) {
    showError(els.loginError, "请输入用户名和密码");
    return;
  }
  setSubmitLoading(els.loginSubmit, true);
  try {
    const data = await requestPublic("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    saveAuth(data.token, data.username, data.role);
    enterApp();
  } catch (err) {
    showError(els.loginError, err.message);
  } finally {
    setSubmitLoading(els.loginSubmit, false);
  }
}

async function handleRegister(e) {
  e.preventDefault();
  hideError(els.registerError);
  const username = els.regUsername.value.trim();
  const password = els.regPassword.value;
  const confirm = els.regPasswordConfirm.value;
  if (!username || !password) {
    showError(els.registerError, "请输入用户名和密码");
    return;
  }
  if (password !== confirm) {
    showError(els.registerError, "两次密码不一致");
    return;
  }
  setSubmitLoading(els.registerSubmit, true);
  try {
    const data = await requestPublic("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    showToast(data.message, "success");
    // Save username for quick login
    state.pendingUsername = username;
    // Switch to login page
    showAuthPage("login");
    els.loginUsername.value = username;
    els.loginPassword.value = "";
    els.loginPassword.focus();
  } catch (err) {
    showError(els.registerError,err.message);
  } finally {
    setSubmitLoading(els.registerSubmit, false);
  }
}

async function handleLogout() {
  try {
    await request("/api/auth/logout", { method: "POST" });
  } catch { /* ignore */ }
  clearAuth();
  showView("auth");
  showAuthPage("login");
  els.loginUsername.value = "";
  els.loginPassword.value = "";
}

function enterApp() {
  els.currentUsername.textContent = state.username;
  els.adminActions.hidden = state.role !== "admin";
  showView("manage");
  loadDatasets();
}

// ============================================
// Toast
// ============================================

function showToast(msg, kind = "info") {
  const t = document.createElement("div");
  t.className = `toast ${kind}`;
  t.textContent = msg;
  els.toast.appendChild(t);
  setTimeout(() => t.remove(), 3000);
}

// ============================================
// View Management
// ============================================

function showView(view) {
  state.view = view;
  els.authView.classList.toggle("active", view === "auth");
  els.manageView.classList.toggle("active", view === "manage");
  els.annotateView.classList.toggle("active", view === "annotate");
  els.statsView.classList.toggle("active", view === "stats");
  els.adminView.classList.toggle("active", view === "admin");
}

// ============================================
// File Tree
// ============================================

async function scanImages(dsName) {
  try {
    const res = await request(`/api/datasets/${encodeURIComponent(dsName)}/scan`, { method: "POST" });
    showToast(res.message, "success");
    await loadDatasets();
  } catch (e) {
    showToast(e.message, "error");
  }
}

async function loadDatasets() {
  try {
    const res = await request("/api/datasets");
    state.datasets = res.datasets || [];
    renderFileTree();
  } catch (e) {
    els.fileTree.innerHTML = `<p class="tree-empty">连接后端失败: ${e.message}</p>`;
  }
}

function renderFileTree() {
  if (!state.datasets.length) {
    els.fileTree.innerHTML = `<p class="tree-empty">没有找到 JSONL 文件。<br/>上传或把文件放到 jsonl/ 目录。</p>`;
    return;
  }

  els.fileTree.innerHTML = state.datasets.map((ds, i) => `
    <div class="tree-dataset" data-index="${i}">
      <div class="tree-dataset-name" data-action="toggle-ds" data-index="${i}">
        <span class="arrow" id="arrow-${i}">▶</span>
        <span class="dataset-icon">📄</span>
        <span>${esc(ds.name)}</span>
        <span class="dataset-count">${ds.total} 条</span>
      </div>
      <div class="tree-checkpoints collapsed" id="cps-${i}">
        ${(ds.checkpoints || []).map(([cpName, cpCount]) => `
          <div class="tree-checkpoint" data-action="open-cp" data-ds="${esc(ds.name)}" data-cp="${esc(cpName)}">
            <span>└ ${esc(cpName)}</span>
            <span class="cp-count">${cpCount}</span>
            <button class="tree-gear-btn" data-action="batch-replace" data-ds="${esc(ds.name)}" data-cp="${esc(cpName)}" title="批量替换 Prompt">⚙</button>
          </div>
        `).join("")}
        <div class="tree-checkpoint scan-btn" data-action="scan" data-ds="${esc(ds.name)}">
          <span>+ 扫描新图片</span>
        </div>
        <div class="tree-checkpoint export-btn" data-action="export" data-ds="${esc(ds.name)}">
          <span>⬇ 导出 JSONL</span>
        </div>
      </div>
    </div>
  `).join("");
}

// ============================================
// Open Checkpoint for Annotation
// ============================================

async function openCheckpoint(dsName, cpName) {
  state.currentDataset = { name: dsName };
  showView("annotate");
  els.annoBreadcrumb.innerHTML = `${esc(dsName)} <span class="sep">/</span> ${esc(cpName)}`;

  try {
    const res = await request(`/api/datasets/${encodeURIComponent(dsName)}/records/${encodeURIComponent(cpName)}`);
    state.records = res.records || [];
    state.currentIndex = 0;
    state.dirty = false;
    if (state.records.length > 0) {
      await loadRecord(0);
    } else {
      showToast("此 checkpoint 没有记录", "info");
    }
  } catch (e) {
    showToast(e.message, "error");
  }
}

// ============================================
// Load Record
// ============================================

async function loadRecord(index) {
  if (index < 0 || index >= state.records.length) return;

  const rec = state.records[index];
  state.currentIndex = index;
  state.dirty = false;
  saveStatusClear();

  // Show loading state
  showImageLoading();

  try {
    const res = await request(`/api/records/${encodeURIComponent(state.currentDataset.name)}/${encodeURIComponent(rec.checkpoint)}/${rec.index}`);
    const d = res.record;
    state.currentRecord = d;

    els.imageInfo.textContent = `#${d.index}  ${d.image_name}  |  ${d.verdict}`;
    resetZoom();

    els.systemInput.value = d.system_prompt || "";
    els.userInput.value = d.user_content || "";

    const variants = d.assistant_variants || [];
    els.answerInput.value = variants[0] || "";

    // Load image with progress tracking
    if (d.image_url) {
      const imgUrl = assetUrl(d.image_url);
      try {
        const blob = await fetchImageWithProgress(imgUrl);
        if (state.currentIndex !== index) return; // navigated away
        const blobUrl = URL.createObjectURL(blob);
        els.annoImage.src = blobUrl;
        els.annoImage._blobUrl = blobUrl;
      } catch {
        if (state.currentIndex !== index) return;
        els.annoImage.src = "";
        showToast("图片加载失败", "error");
      }
    } else {
      els.annoImage.src = "";
    }
    hideImageLoading();

    // Preload next image
    if (index + 1 < state.records.length) {
      const nextRec = state.records[index + 1];
      const nextRes = request(`/api/records/${encodeURIComponent(state.currentDataset.name)}/${encodeURIComponent(nextRec.checkpoint)}/${nextRec.index}`)
        .then(nextData => {
          if (nextData.record && nextData.record.image_url) {
            const preloadImg = new Image();
            preloadImg.src = assetUrl(nextData.record.image_url);
          }
        }).catch(() => {});
    }

    updateNav();
    updateProgress();
  } catch (e) {
    console.error("loadRecord error:", e);
    hideImageLoading();
    showToast(e.message, "error");
  }
}

function updateNav() {
  els.prevBtn.disabled = state.currentIndex <= 0;
  els.nextBtn.disabled = state.currentIndex >= state.records.length - 1;
}

function updateProgress() {
  const total = state.records.length;
  const rec = state.currentRecord;
  const annotated = rec ? rec.annotated : false;

  const annotatedCount = state.records.filter(r => r.annotated).length;
  els.progressText.textContent = `已标注 ${annotatedCount} / ${total}`;
  els.progressFill.style.width = total ? `${(annotatedCount / total) * 100}%` : "0%";

  if (annotated) {
    els.annotatedStatus.textContent = "✓";
    els.annotatedStatus.className = "annotated-status yes";
  } else {
    els.annotatedStatus.textContent = "○";
    els.annotatedStatus.className = "annotated-status no";
  }
}

function saveStatusClear() {
  els.saveStatus.textContent = "";
  els.saveStatus.className = "save-status";
  els.saveBtn.classList.remove("saving");
}

function saveStatusSaved() {
  els.saveStatus.textContent = "已保存";
  els.saveStatus.className = "save-status saved";
}

function saveStatusSaving() {
  els.saveStatus.textContent = "保存中...";
  els.saveStatus.className = "save-status";
  els.saveBtn.classList.add("saving");
}

// ============================================
// Save
// ============================================

async function saveCurrentRecord() {
  if (!state.currentRecord) return;
  saveStatusSaving();

  const payload = {
    system_prompt: els.systemInput.value,
    user_content: els.userInput.value,
    assistant_content: els.answerInput.value,
  };

  try {
    const rec = state.currentRecord;
    const res = await request(
      `/api/records/${encodeURIComponent(state.currentDataset.name)}/${encodeURIComponent(rec.checkpoint)}/${rec.index}`,
      { method: "PUT", body: JSON.stringify(payload) }
    );
    if (res.record) {
      state.currentRecord = res.record;
      state.records[state.currentIndex] = { ...state.records[state.currentIndex], annotated: res.record.annotated };
    }
    state.dirty = false;
    saveStatusSaved();
    showToast("已保存", "success");
    updateProgress();
  } catch (e) {
    saveStatusClear();
    showToast("保存失败: " + e.message, "error");
  }
}

function scheduleAutoSave() {
  state.dirty = true;
  clearTimeout(state.autoSaveTimer);
  state.autoSaveTimer = setTimeout(() => {
    if (state.dirty) saveCurrentRecord();
  }, 1500);
}

// ============================================
// Image Loading with Progress
// ============================================

function showImageLoading() {
  // Clean up previous blob URL
  if (els.annoImage._blobUrl) {
    URL.revokeObjectURL(els.annoImage._blobUrl);
    els.annoImage._blobUrl = null;
  }
  els.imageLoading.classList.add("visible");
  els.loadingText.textContent = "加载中...";
  els.loadingBarFill.style.width = "0%";
  els.annoImage.style.opacity = "0.15";
}

function hideImageLoading() {
  els.imageLoading.classList.remove("visible");
  els.annoImage.style.opacity = "1";
}

async function fetchImageWithProgress(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);

  const contentLength = response.headers.get("Content-Length");
  const total = contentLength ? parseInt(contentLength, 10) : 0;
  const reader = response.body.getReader();
  const chunks = [];
  let loaded = 0;
  const startTime = performance.now();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
    loaded += value.length;

    const elapsed = (performance.now() - startTime) / 1000;
    const speed = loaded / elapsed;
    const speedText = speed > 1048576
      ? (speed / 1048576).toFixed(1) + " MB/s"
      : (speed / 1024).toFixed(0) + " KB/s";

    if (total > 0) {
      const pct = Math.round((loaded / total) * 100);
      els.loadingBarFill.style.width = pct + "%";
      const loadedKB = (loaded / 1024).toFixed(0);
      const totalKB = (total / 1024).toFixed(0);
      els.loadingText.textContent = `${loadedKB}/${totalKB} KB · ${speedText}`;
    } else {
      const loadedKB = (loaded / 1024).toFixed(0);
      els.loadingText.textContent = `${loadedKB} KB · ${speedText}`;
    }
  }

  return new Blob(chunks, { type: response.headers.get("Content-Type") || "image/jpeg" });
}

// ============================================
// Image Zoom
// ============================================

function resetZoom() {
  state.zoom = { scale: 1, x: 0, y: 0, panning: false, startX: 0, startY: 0 };
  applyZoom();
}

function applyZoom() {
  const z = state.zoom;
  els.annoImage.style.transform = `translate(${z.x}px, ${z.y}px) scale(${z.scale})`;
  els.zoomHint.textContent = `${Math.round(z.scale * 100)}%`;
  els.zoomHint.classList.add("visible");
  clearTimeout(els.zoomHint._timer);
  els.zoomHint._timer = setTimeout(() => els.zoomHint.classList.remove("visible"), 800);
}

function initZoom() {
  const container = els.imageContainer;

  container.addEventListener("wheel", (e) => {
    e.preventDefault();
    const z = state.zoom;
    const delta = e.deltaY > 0 ? -0.1 : 0.1;
    z.scale = Math.min(5, Math.max(0.2, z.scale + delta));
    applyZoom();
  }, { passive: false });

  container.addEventListener("dblclick", () => resetZoom());

  container.addEventListener("mousedown", (e) => {
    if (state.zoom.scale <= 1) return;
    e.preventDefault();
    state.zoom.panning = true;
    state.zoom.startX = e.clientX - state.zoom.x;
    state.zoom.startY = e.clientY - state.zoom.y;
  });

  window.addEventListener("mousemove", (e) => {
    if (!state.zoom.panning) return;
    state.zoom.x = e.clientX - state.zoom.startX;
    state.zoom.y = e.clientY - state.zoom.startY;
    applyZoom();
  });

  window.addEventListener("mouseup", () => {
    state.zoom.panning = false;
  });
}

// ============================================
// Upload
// ============================================

function checkAuth(response) {
  if (response.status === 401) {
    clearAuth();
    showView("auth");
    throw new Error("登录已过期");
  }
  return response;
}

async function uploadFile(file) {
  if (!file.name.endsWith(".jsonl")) {
    showToast("只支持 .jsonl 文件", "error");
    return;
  }

  try {
    const body = new FormData();
    body.append("file", file);
    const response = checkAuth(await fetch(apiUrl("/api/datasets/upload"), {
      method: "POST",
      body,
      headers: { "Authorization": `Bearer ${state.token}` },
    }));
    const raw = await response.text();
    let payload = {};
    if (raw) payload = JSON.parse(raw);
    if (!response.ok) throw new Error(payload.error || "Upload failed");
    showToast(`上传成功: ${file.name}`, "success");
    await loadDatasets();
  } catch (e) {
    showToast(e.message, "error");
  }
}

// ============================================
// JSONL Export
// ============================================

async function exportDataset(dsName) {
  try {
    const response = checkAuth(await fetch(apiUrl(`/api/datasets/${encodeURIComponent(dsName)}/export`), {
      headers: { "Authorization": `Bearer ${state.token}` },
    }));
    if (!response.ok) {
      const raw = await response.text();
      let payload = {};
      try { payload = JSON.parse(raw); } catch {}
      throw new Error(payload.error || "导出失败");
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = dsName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast(`已导出 ${dsName}`, "success");
  } catch (e) {
    showToast(e.message, "error");
  }
}

// ============================================
// Data Analysis
// ============================================

async function showStats() {
  showView("stats");
  renderStatsDsList();
}

function renderStatsDsList() {
  if (!state.datasets.length) {
    els.statsDsList.innerHTML = `<p class="tree-empty">没有数据集</p>`;
    return;
  }

  els.statsDsList.innerHTML = state.datasets.map((ds, i) => `
    <div class="stats-ds-item" data-action="show-stats" data-ds="${esc(ds.name)}" data-total="${ds.total}">
      <span class="ds-icon">📄</span>
      <span>${esc(ds.name)}</span>
      <span class="ds-count">${ds.total} 条</span>
    </div>
  `).join("");
}

async function loadStats(dsName) {
  try {
    const res = await request(`/api/datasets/${encodeURIComponent(dsName)}/stats`);
    renderStatsTable(dsName, res);
  } catch (e) {
    showToast(e.message, "error");
  }
}

function renderStatsTable(dsName, stats) {
  els.statsTitle.textContent = `${dsName} — 标注统计`;

  let html = `<table class="stats-table">
    <thead><tr>
      <th>Checkpoint</th>
      <th>总数</th>
      <th>已标注</th>
      <th>未标注</th>
      <th>进度</th>
    </tr></thead><tbody>`;

  for (const cp of stats.checkpoints) {
    const pct = cp.total ? Math.round((cp.annotated / cp.total) * 100) : 0;
    html += `<tr>
      <td>${esc(cp.name)}</td>
      <td>${cp.total}</td>
      <td>${cp.annotated}</td>
      <td>${cp.total - cp.annotated}</td>
      <td>
        <div class="stats-progress-bar"><div class="stats-progress-fill" style="width:${pct}%"></div></div>
        <span class="stats-pct">${pct}%</span>
      </td>
    </tr>`;
  }

  html += `<tr class="row-total">
    <td>总计</td>
    <td>${stats.total}</td>
    <td>${stats.annotated}</td>
    <td>${stats.unannotated}</td>
    <td>
      <div class="stats-progress-bar"><div class="stats-progress-fill" style="width:${stats.total ? Math.round((stats.annotated / stats.total) * 100) : 0}%"></div></div>
      <span class="stats-pct">${stats.total ? Math.round((stats.annotated / stats.total) * 100) : 0}%</span>
    </td>
  </tr>`;

  html += `</tbody></table>`;
  els.statsTableWrap.innerHTML = html;
}

// ============================================
// Admin User Management
// ============================================

async function showAdmin() {
  showView("admin");
  state.adminTab = "pending";
  document.querySelectorAll(".admin-nav-btn").forEach(b => b.classList.toggle("active", b.dataset.tab === "pending"));
  await loadAdminData();
}

async function loadAdminData() {
  try {
    const res = await request("/api/admin/users");
    renderAdminTable(res.users || []);
  } catch (e) {
    els.adminTableWrap.innerHTML = `<p class="tree-empty">加载失败: ${e.message}</p>`;
  }
}

function renderAdminTable(users) {
  if (!users.length) {
    els.adminTableWrap.innerHTML = `<p class="tree-empty">暂无用户</p>`;
    return;
  }

  const filtered = state.adminTab === "pending" ? users.filter(u => u.status === "pending") : users;
  els.adminTitle.textContent = state.adminTab === "pending" ? "待审批用户" : "所有用户";

  if (!filtered.length) {
    els.adminTableWrap.innerHTML = `<p class="tree-empty">暂无${state.adminTab === "pending" ? "待审批" : ""}用户</p>`;
    return;
  }

  let html = `<table class="admin-table">
    <thead><tr>
      <th>用户名</th>
      <th>状态</th>
      <th>注册时间</th>
      <th>操作</th>
    </tr></thead><tbody>`;

  for (const u of filtered) {
    const isPending = u.status === "pending";
    html += `<tr>
      <td>${esc(u.username)}</td>
      <td><span class="role-badge ${isPending ? 'role-pending' : 'role-' + u.role}">${esc(isPending ? '待审批' : u.role)}</span></td>
      <td>${esc(u.created_at || "")}</td>
      <td>`;
    if (isPending) {
      html += `<button class="admin-approve-btn" data-user="${esc(u.username)}">通过</button>
               <button class="admin-reject-btn" data-user="${esc(u.username)}">拒绝</button>`;
    } else {
      html += `<button class="admin-revoke-btn" data-user="${esc(u.username)}">撤销</button>`;
    }
    html += `</td></tr>`;
  }

  html += `</tbody></table>`;
  els.adminTableWrap.innerHTML = html;
}

const ACTION_LABELS = { approve: "批准", reject: "拒绝", revoke: "撤销" };

async function adminAction(username, action) {
  try {
    await request(`/api/admin/users/${encodeURIComponent(username)}/${action}`, { method: "POST" });
    showToast(`已${ACTION_LABELS[action]} ${username}`, "success");
    await loadAdminData();
  } catch (e) {
    showToast(e.message, "error");
  }
}

// ============================================
// Batch Replace Modal
// ============================================

function openBatchReplaceModal(dsName, cpName) {
  state.batchDs = dsName;
  state.batchCp = cpName;
  els.modalTitle.textContent = `批量替换 — ${dsName} / ${cpName}`;
  els.replaceSystemCheck.checked = false;
  els.replaceUserCheck.checked = false;
  els.replaceSystemInput.value = "";
  els.replaceUserInput.value = "";
  els.replaceSystemInput.disabled = true;
  els.replaceUserInput.disabled = true;
  els.batchReplaceModal.hidden = false;
}

function closeBatchReplaceModal() {
  els.batchReplaceModal.hidden = true;
}

async function executeBatchReplace() {
  const ds = state.batchDs;
  const cp = state.batchCp;
  const doSystem = els.replaceSystemCheck.checked;
  const doUser = els.replaceUserCheck.checked;

  if (!doSystem && !doUser) {
    showToast("请至少选择一项进行替换", "error");
    return;
  }

  const payload = {
    checkpoint: cp,
    system_prompt: doSystem ? els.replaceSystemInput.value : null,
    user_content: doUser ? els.replaceUserInput.value : null,
  };

  try {
    const res = await request(`/api/datasets/${encodeURIComponent(ds)}/batch-replace`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    showToast(res.message, "success");
    closeBatchReplaceModal();
  } catch (e) {
    showToast(e.message, "error");
  }
}

// ============================================
// Change Password
// ============================================

function openChangePasswordModal() {
  els.cpOldPassword.value = "";
  els.cpNewPassword.value = "";
  els.cpNewPasswordConfirm.value = "";
  els.changePasswordModal.hidden = false;
}

async function executeChangePassword() {
  const oldPwd = els.cpOldPassword.value;
  const newPwd = els.cpNewPassword.value;
  const confirmPwd = els.cpNewPasswordConfirm.value;

  if (!oldPwd || !newPwd) {
    showToast("请填写完整", "error");
    return;
  }
  if (newPwd !== confirmPwd) {
    showToast("两次密码不一致", "error");
    return;
  }

  try {
    await request("/api/auth/change-password", {
      method: "POST",
      body: JSON.stringify({ old_password: oldPwd, new_password: newPwd }),
    });
    showToast("密码修改成功", "success");
    els.changePasswordModal.hidden = true;
  } catch (e) {
    showToast(e.message, "error");
  }
}

// ============================================
// Event Binding
// ============================================

function bindEvents() {
  // Auth page switching
  els.goToRegister.addEventListener("click", (e) => {
    e.preventDefault();
    showAuthPage("register");
  });

  els.goToLogin.addEventListener("click", (e) => {
    e.preventDefault();
    showAuthPage("login");
  });

  // Auth forms
  els.loginForm.addEventListener("submit", handleLogin);
  els.registerForm.addEventListener("submit", handleRegister);

  // Password toggle buttons
  document.querySelectorAll(".password-toggle").forEach(btn => {
    btn.addEventListener("click", () => {
      const input = document.getElementById(btn.dataset.target);
      if (!input) return;
      const isPassword = input.type === "password";
      input.type = isPassword ? "text" : "password";
      btn.setAttribute("aria-label", isPassword ? "隐藏密码" : "显示密码");
    });
  });

  // Logout
  els.logoutBtn.addEventListener("click", handleLogout);

  // Change password
  $("#changePasswordBtn").addEventListener("click", () => openChangePasswordModal());

  // File upload
  els.fileUpload.addEventListener("change", (e) => {
    if (e.target.files.length) uploadFile(e.target.files[0]);
    e.target.value = "";
  });

  // Stats
  $("#statsBtn").addEventListener("click", showStats);
  els.backToManageFromStats.addEventListener("click", () => showView("manage"));

  // Admin
  els.adminBtn.addEventListener("click", showAdmin);
  els.backToManageFromAdmin.addEventListener("click", () => showView("manage"));

  // Admin nav tabs
  document.querySelectorAll(".admin-nav-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".admin-nav-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      state.adminTab = btn.dataset.tab;
      loadAdminData();
    });
  });

  // Back to manage
  els.backToManage.addEventListener("click", () => showView("manage"));

  // File tree delegation
  els.fileTree.addEventListener("click", (e) => {
    const actionEl = e.target.closest("[data-action]");
    if (!actionEl) return;
    const action = actionEl.dataset.action;

    if (action === "toggle-ds") {
      const idx = actionEl.dataset.index;
      const cps = document.getElementById(`cps-${idx}`);
      const arrow = document.getElementById(`arrow-${idx}`);
      if (cps.classList.contains("collapsed")) {
        cps.classList.remove("collapsed");
        arrow.textContent = "▼";
      } else {
        cps.classList.add("collapsed");
        arrow.textContent = "▶";
      }
    } else if (action === "open-cp") {
      openCheckpoint(actionEl.dataset.ds, actionEl.dataset.cp);
    } else if (action === "scan") {
      scanImages(actionEl.dataset.ds);
    } else if (action === "export") {
      exportDataset(actionEl.dataset.ds);
    } else if (action === "batch-replace") {
      openBatchReplaceModal(actionEl.dataset.ds, actionEl.dataset.cp);
    }
  });

  // Admin table delegation
  els.adminTableWrap.addEventListener("click", (e) => {
    const btn = e.target;
    if (btn.classList.contains("admin-approve-btn")) adminAction(btn.dataset.user, "approve");
    else if (btn.classList.contains("admin-reject-btn")) adminAction(btn.dataset.user, "reject");
    else if (btn.classList.contains("admin-revoke-btn")) adminAction(btn.dataset.user, "revoke");
  });

  // Stats delegation
  els.statsDsList.addEventListener("click", (e) => {
    const actionEl = e.target.closest("[data-action]");
    if (actionEl && actionEl.dataset.action === "show-stats") {
      loadStats(actionEl.dataset.ds);
    }
  });

  // Annotation navigation
  els.prevBtn.addEventListener("click", () => {
    if (state.currentIndex > 0) loadRecord(state.currentIndex - 1);
  });
  els.nextBtn.addEventListener("click", () => {
    if (state.currentIndex < state.records.length - 1) loadRecord(state.currentIndex + 1);
  });

  // Save
  els.saveBtn.addEventListener("click", saveCurrentRecord);

  // Auto-save on input
  [els.systemInput, els.userInput, els.answerInput].forEach(el => {
    el.addEventListener("input", scheduleAutoSave);
  });

  // Keyboard shortcuts
  document.addEventListener("keydown", (e) => {
    if (state.view !== "annotate") return;
    if (e.target.tagName === "TEXTAREA" || e.target.tagName === "INPUT") return;
    if (e.key === "ArrowLeft") els.prevBtn.click();
    else if (e.key === "ArrowRight") els.nextBtn.click();
    else if (e.key === "s" || e.key === "S") saveCurrentRecord();
  });

  // Zoom
  initZoom();

  // Collapse toggle for prompt sections
  document.querySelectorAll(".prompt-toggle").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.dataset.target;
      const body = document.getElementById(targetId);
      if (!body) return;
      const isCollapsed = body.classList.toggle("collapsed");
      btn.textContent = isCollapsed ? "展开" : "收起";
    });
  });

  // Batch replace modal
  els.modalClose.addEventListener("click", closeBatchReplaceModal);
  els.modalCancel.addEventListener("click", closeBatchReplaceModal);
  els.modalConfirm.addEventListener("click", executeBatchReplace);

  els.replaceSystemCheck.addEventListener("change", () => {
    els.replaceSystemInput.disabled = !els.replaceSystemCheck.checked;
    if (els.replaceSystemCheck.checked) els.replaceSystemInput.focus();
  });

  els.replaceUserCheck.addEventListener("change", () => {
    els.replaceUserInput.disabled = !els.replaceUserCheck.checked;
    if (els.replaceUserCheck.checked) els.replaceUserInput.focus();
  });

  // Change password modal
  els.cpModalClose.addEventListener("click", () => { els.changePasswordModal.hidden = true; });
  els.cpModalCancel.addEventListener("click", () => { els.changePasswordModal.hidden = true; });
  els.cpModalConfirm.addEventListener("click", executeChangePassword);
}

// ============================================
// Bootstrap
// ============================================

async function bootstrap() {
  bindEvents();

  if (state.token) {
    try {
      const res = await request("/api/auth/me");
      state.username = res.username;
      state.role = res.role;
      enterApp();
      return;
    } catch {
      clearAuth();
    }
  }

  showView("auth");
  showAuthPage("login");
}

bootstrap();
