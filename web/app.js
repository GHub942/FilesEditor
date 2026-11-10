const SUPPORTED_LANGUAGES = ["en", "fr"];
const DEFAULT_PREFERENCES = {
  theme: "system",
  pageSize: 50,
  excludedDirs: [".venv", "venv", "env", ".env", "temp", "tmp", ".temp", ".tmp", "node_modules", ".git", "__pycache__", ".idea", ".vscode"],
  excludedExtensions: [".tmp", ".bak"],
  askBackupBeforeApply: true
};
const HISTORY_LIMIT = 50;
const dictionaries = {};
const elements = {
  folder: document.querySelector("#folderPath"),
  recursive: document.querySelector("#recursive"),
  excludedDirs: document.querySelector("#excludedDirs"),
  excludeBox: document.querySelector("#excludeBox"),
  renameOptions: document.querySelector("#renameOptions"),
  extensionOptions: document.querySelector("#extensionOptions"),
  undoOptions: document.querySelector("#undoOptions"),
  backupPanel: document.querySelector("#backupPanel"),
  undoBackupPanel: document.querySelector("#undoBackupPanel"),
  scanOptions: document.querySelector("#scanOptions"),
  topbar: document.querySelector("#topbar"),
  workspaceView: document.querySelector("#workspaceView"),
  landingView: document.querySelector("#landingView"),
  pageHeading: document.querySelector("#pageHeading"),
  notFoundView: document.querySelector("#notFoundView"),
  settingsDialog: document.querySelector("#settingsDialog"),
  stepIndicator: document.querySelector("#stepIndicator"),
  pageTitle: document.querySelector("#pageTitle"),
  pageDescription: document.querySelector("#pageDescription"),
  breadcrumbTitle: document.querySelector("#breadcrumbTitle"),
  previewButton: document.querySelector("#previewButton"),
  applyButton: document.querySelector("#applyButton"),
  previewEmpty: document.querySelector("#previewEmpty"),
  previewResults: document.querySelector("#previewResults"),
  previewCount: document.querySelector("#previewCount"),
  previewSummary: document.querySelector("#previewSummary"),
  previewSearch: document.querySelector("#previewSearch"),
  previewFilterCount: document.querySelector("#previewFilterCount"),
  previewRows: document.querySelector("#previewRows"),
  previewPagination: document.querySelector("#previewPagination"),
  previousPreviewPage: document.querySelector("#previousPreviewPage"),
  nextPreviewPage: document.querySelector("#nextPreviewPage"),
  previewPageIndicator: document.querySelector("#previewPageIndicator"),
  previewFooter: document.querySelector("#previewFooter"),
  previewFooterText: document.querySelector("#previewFooterText"),
  undoLogFile: document.querySelector("#undoLogFile"),
  undoLogName: document.querySelector("#undoLogName"),
  undoLogStatus: document.querySelector("#undoLogStatus"),
  languageSelect: document.querySelector("#languageSelect"),
  forgetPreferences: document.querySelector("#forgetPreferences"),
  themeSelect: document.querySelector("#themeSelect"),
  pageSizeSelect: document.querySelector("#pageSizeSelect"),
  defaultExcludedDirs: document.querySelector("#defaultExcludedDirs"),
  defaultExcludedExtensions: document.querySelector("#defaultExcludedExtensions"),
  askBackupBeforeApply: document.querySelector("#askBackupBeforeApply"),
  presetSelect: document.querySelector("#presetSelect"),
  presetName: document.querySelector("#presetName"),
  historyEntries: document.querySelector("#historyEntries"),
  historyEmpty: document.querySelector("#historyEmpty"),
  toast: document.querySelector("#toast")
};

let currentMode = "rename";
let currentPage = "workspace";
let currentLanguage = "en";
let undoLog = null;
let currentPreview = null;
let currentPreviewPage = 0;
let preferences = { ...DEFAULT_PREFERENCES };
let presets = {};
let operationHistory = [];
let restoringHistoryId = null;
let toastTimer = null;

document.querySelectorAll(".nav-item[data-mode]").forEach((button) => {
  button.addEventListener("click", (event) => {
    event.preventDefault();
    setMode(button.dataset.mode);
  });
});
document.querySelector('[data-page="settings"]').addEventListener("click", openSettingsDialog);
document.querySelector("#closeSettingsButton").addEventListener("click", closeSettingsDialog);
elements.settingsDialog.addEventListener("close", removeSettingsQuery);
elements.recursive.addEventListener("change", () => {
  elements.excludeBox.hidden = !elements.recursive.checked;
  clearPreview();
});
elements.undoLogFile.addEventListener("change", loadUndoLog);
elements.previewButton.addEventListener("click", previewChanges);
elements.applyButton.addEventListener("click", applyChanges);
elements.previousPreviewPage.addEventListener("click", () => changePreviewPage(-1));
elements.nextPreviewPage.addEventListener("click", () => changePreviewPage(1));
elements.languageSelect.addEventListener("change", changeLanguage);
elements.forgetPreferences.addEventListener("change", changePreferencePersistence);
elements.themeSelect.addEventListener("change", updatePreferencesFromSettings);
elements.pageSizeSelect.addEventListener("change", updatePreferencesFromSettings);
elements.defaultExcludedDirs.addEventListener("change", updatePreferencesFromSettings);
elements.defaultExcludedExtensions.addEventListener("change", updatePreferencesFromSettings);
elements.askBackupBeforeApply.addEventListener("change", updatePreferencesFromSettings);
elements.previewSearch.addEventListener("input", () => {
  currentPreviewPage = 0;
  if (currentPreview) renderPreview(currentPreview);
});
document.querySelector("#savePresetButton").addEventListener("click", savePreset);
document.querySelector("#loadPresetButton").addEventListener("click", loadPreset);
document.querySelector("#deletePresetButton").addEventListener("click", deletePreset);
document.querySelector("#clearHistoryButton").addEventListener("click", clearHistory);
window.addEventListener("popstate", syncRouteFromLocation);
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  if (preferences.theme === "system") applyTheme();
});

initialize();

async function initialize() {
  try {
    await loadDictionaries();
    restorePreferences();
    elements.languageSelect.value = currentLanguage;
    renderSavedData();
    syncRouteFromLocation();
    applyTranslations();
    renderMode();
    renderPage();
  } catch (error) {
    showToast(error.message, true, 8000);
  }
}

function restorePreferences() {
  try {
    const saveEnabled = localStorage.getItem("files-editor-save-preferences") === "true";
    elements.forgetPreferences.checked = !saveEnabled;
    if (saveEnabled) {
      const savedLanguage = localStorage.getItem("files-editor-language");
      if (SUPPORTED_LANGUAGES.includes(savedLanguage)) currentLanguage = savedLanguage;
      const savedState = JSON.parse(localStorage.getItem("files-editor-state") || "{}");
      preferences = validatePreferences(savedState.preferences);
      presets = savedState.presets && typeof savedState.presets === "object" && !Array.isArray(savedState.presets)
        ? Object.fromEntries(Object.entries(savedState.presets).filter(([, preset]) =>
          preset && typeof preset.globalPrefix === "string" && typeof preset.separator === "string" &&
          Array.isArray(preset.categories) && preset.categoryPrefixes && typeof preset.categoryPrefixes === "object"
        ))
        : {};
      operationHistory = Array.isArray(savedState.history)
        ? savedState.history.filter((item) =>
          item && typeof item.id === "string" && ["rename", "extensions", "undo"].includes(item.kind) &&
          typeof item.folder === "string" && Number.isInteger(item.changed) &&
          typeof item.timestamp === "string" && item.undoLog && Array.isArray(item.undoLog.renamed_files)
        ).slice(-HISTORY_LIMIT)
        : [];
    } else {
      clearSavedPreferences();
      preferences = { ...DEFAULT_PREFERENCES };
      presets = {};
      operationHistory = [];
    }
  } catch (error) {
    elements.forgetPreferences.checked = true;
    currentLanguage = "en";
    preferences = { ...DEFAULT_PREFERENCES };
    presets = {};
    operationHistory = [];
    console.warn("Could not read saved preferences; using the no-save defaults.", error);
    try {
      clearSavedPreferences();
    } catch (clearError) {
      console.error("Could not clear unreadable saved preferences.", clearError);
    }
  }
}

function validatePreferences(saved = {}) {
  const parsedPageSize = Number(saved.pageSize);
  return {
    theme: ["system", "light", "dark", "high_contrast"].includes(saved.theme) ? saved.theme : DEFAULT_PREFERENCES.theme,
    pageSize: [50, 100, 500].includes(parsedPageSize) ? parsedPageSize : DEFAULT_PREFERENCES.pageSize,
    excludedDirs: Array.isArray(saved.excludedDirs) ? saved.excludedDirs.filter((item) => typeof item === "string") : [...DEFAULT_PREFERENCES.excludedDirs],
    excludedExtensions: Array.isArray(saved.excludedExtensions) ? saved.excludedExtensions.filter((item) => typeof item === "string") : [...DEFAULT_PREFERENCES.excludedExtensions],
    askBackupBeforeApply: typeof saved.askBackupBeforeApply === "boolean" ? saved.askBackupBeforeApply : DEFAULT_PREFERENCES.askBackupBeforeApply
  };
}

function renderSavedData() {
  elements.themeSelect.value = preferences.theme;
  elements.pageSizeSelect.value = String(preferences.pageSize);
  elements.defaultExcludedDirs.value = preferences.excludedDirs.join(", ");
  elements.defaultExcludedExtensions.value = preferences.excludedExtensions.join(", ");
  elements.askBackupBeforeApply.checked = preferences.askBackupBeforeApply;
  applyTheme();
  renderPresets();
  renderHistory();
}

function clearSavedPreferences() {
  const preferenceKeys = [];
  for (let index = 0; index < localStorage.length; index += 1) {
    const key = localStorage.key(index);
    if (key?.startsWith("files-editor-")) preferenceKeys.push(key);
  }
  preferenceKeys.forEach((key) => localStorage.removeItem(key));
}

async function loadDictionaries() {
  for (const language of SUPPORTED_LANGUAGES) {
    const response = await fetch(`/locales/${language}.json`);
    if (!response.ok) throw new Error(`Could not load the ${language} translation file.`);
    dictionaries[language] = await response.json();
  }
}

function translate(key, values = {}) {
  const message = key.split(".").reduce((value, part) => value?.[part], dictionaries[currentLanguage]);
  if (typeof message !== "string") {
    console.error(`Missing ${currentLanguage} translation: ${key}`);
    return key;
  }
  return message.replace(/\{(\w+)\}/g, (_match, name) => String(values[name] ?? `{${name}}`));
}

function applyTranslations() {
  document.documentElement.lang = currentLanguage;
  document.title = translate("app.title");
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = translate(element.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
    element.placeholder = translate(element.dataset.i18nPlaceholder);
  });
  document.querySelectorAll("[data-i18n-aria-label]").forEach((element) => {
    element.setAttribute("aria-label", translate(element.dataset.i18nAriaLabel));
  });
  document.querySelectorAll("[data-i18n-title]").forEach((element) => {
    element.title = translate(element.dataset.i18nTitle);
  });
  renderMode();
  renderPage();
  if (currentPreview && currentPage === "workspace") renderPreview(currentPreview);
  if (undoLog) renderUndoLogStatus();
  renderPresets();
  renderHistory();
}

function changeLanguage() {
  const language = elements.languageSelect.value;
  if (!SUPPORTED_LANGUAGES.includes(language)) return;
  currentLanguage = language;
  if (!elements.forgetPreferences.checked) {
    try {
      savePreferences();
    } catch (error) {
      elements.forgetPreferences.checked = true;
      console.error("Could not save the language preference.", error);
      showToast(translate("messages.preferenceNotSaved"), true, 7000);
      try {
        clearSavedPreferences();
      } catch (clearError) {
        console.error("Could not clear the saved preferences.", clearError);
      }
    }
  }
  applyTranslations();
}

function changePreferencePersistence() {
  try {
    if (elements.forgetPreferences.checked) {
      clearSavedPreferences();
    } else {
      savePreferences();
    }
  } catch (error) {
    elements.forgetPreferences.checked = true;
    console.error("Could not update the preference persistence setting.", error);
    showToast(translate("messages.preferenceNotSaved"), true, 7000);
    try {
      clearSavedPreferences();
    } catch (clearError) {
      console.error("Could not clear the saved preferences.", clearError);
    }
  }
}

function savePreferences() {
  localStorage.setItem("files-editor-save-preferences", "true");
  localStorage.setItem("files-editor-language", currentLanguage);
  localStorage.setItem("files-editor-state", JSON.stringify({ preferences, presets, history: operationHistory }));
}

function persistSavedData() {
  if (elements.forgetPreferences.checked) return;
  try {
    savePreferences();
  } catch (error) {
    console.error("Could not save Files Editor preferences and local data.", error);
    elements.forgetPreferences.checked = true;
    try {
      clearSavedPreferences();
    } catch (clearError) {
      console.error("Could not clear the saved preferences.", clearError);
    }
    showToast(translate("messages.preferenceNotSaved"), true, 7000);
  }
}

function updatePreferencesFromSettings() {
  const previous = preferences;
  preferences = validatePreferences({
    theme: elements.themeSelect.value,
    pageSize: elements.pageSizeSelect.value,
    excludedDirs: parseCommaList(elements.defaultExcludedDirs.value),
    excludedExtensions: parseCommaList(elements.defaultExcludedExtensions.value),
    askBackupBeforeApply: elements.askBackupBeforeApply.checked
  });
  elements.defaultExcludedDirs.value = preferences.excludedDirs.join(", ");
  elements.defaultExcludedExtensions.value = preferences.excludedExtensions.join(", ");
  applyTheme();
  if (
    previous.pageSize !== preferences.pageSize ||
    JSON.stringify(previous.excludedDirs) !== JSON.stringify(preferences.excludedDirs) ||
    JSON.stringify(previous.excludedExtensions) !== JSON.stringify(preferences.excludedExtensions)
  ) clearPreview();
  persistSavedData();
}

function parseCommaList(value) {
  return [...new Set(value.split(",").map((item) => item.trim()).filter(Boolean))];
}

function applyTheme() {
  const resolvedTheme = preferences.theme === "system"
    ? (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
    : preferences.theme;
  document.body.dataset.theme = resolvedTheme;
  document.body.dataset.themeChoice = preferences.theme;
  const themeColor = resolvedTheme === "dark" ? "#111a20" : "#f5f7fb";
  document.querySelector('meta[name="theme-color"]').content = themeColor;
}

function renderPresets() {
  const selected = elements.presetSelect.value;
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = translate("presets.choose");
  elements.presetSelect.replaceChildren(placeholder);
  for (const name of Object.keys(presets).sort((left, right) => left.localeCompare(right))) {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    elements.presetSelect.append(option);
  }
  elements.presetSelect.value = Object.hasOwn(presets, selected) ? selected : "";
  document.querySelector("#loadPresetButton").disabled = !elements.presetSelect.value;
  document.querySelector("#deletePresetButton").disabled = !elements.presetSelect.value;
}

function savePreset() {
  const name = elements.presetName.value.trim();
  if (!name || name.length > 80) {
    showToast(translate("messages.invalidPresetName"), true);
    return;
  }
  presets[name] = readModeOptionsForRename();
  elements.presetName.value = "";
  renderPresets();
  elements.presetSelect.value = name;
  renderPresets();
  persistSavedData();
  showToast(translate("messages.presetSaved", { name }));
}

function readModeOptionsForRename() {
  const categories = [...document.querySelectorAll("#categoryFilters input:checked")].map((input) => input.value);
  const categoryPrefixes = {};
  document.querySelectorAll("[data-prefix]").forEach((input) => {
    categoryPrefixes[input.dataset.prefix] = input.value;
  });
  return {
    globalPrefix: document.querySelector("#globalPrefix").value,
    separator: document.querySelector("#separator").value,
    padding: document.querySelector("#padding").value,
    categories,
    categoryPrefixes
  };
}

function loadPreset() {
  const preset = presets[elements.presetSelect.value];
  if (!preset) return;
  document.querySelector("#globalPrefix").value = preset.globalPrefix;
  document.querySelector("#separator").value = preset.separator;
  document.querySelector("#padding").value = preset.padding;
  document.querySelectorAll("#categoryFilters input").forEach((input) => {
    input.checked = preset.categories.includes(input.value);
  });
  document.querySelectorAll("[data-prefix]").forEach((input) => {
    input.value = preset.categoryPrefixes[input.dataset.prefix] || input.dataset.prefix;
  });
  clearPreview();
  showToast(translate("messages.presetLoaded", { name: elements.presetSelect.value }));
}

function deletePreset() {
  const name = elements.presetSelect.value;
  if (!name || !Object.hasOwn(presets, name)) return;
  delete presets[name];
  renderPresets();
  persistSavedData();
  showToast(translate("messages.presetDeleted", { name }));
}

function renderHistory() {
  elements.historyEntries.replaceChildren();
  elements.historyEmpty.hidden = operationHistory.length > 0;
  for (const item of [...operationHistory].reverse()) {
    const entry = document.createElement("article");
    entry.className = "history-entry";
    const detail = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = translate(`history.kind.${item.kind}`, { count: item.changed });
    const meta = document.createElement("small");
    meta.textContent = `${item.folder} · ${new Date(item.timestamp).toLocaleString(currentLanguage)}`;
    meta.title = item.folder;
    const restore = document.createElement("button");
    restore.className = "secondary-button";
    restore.type = "button";
    restore.textContent = translate("history.restore");
    restore.addEventListener("click", () => restoreHistoryItem(item));
    detail.append(title, meta);
    entry.append(detail, restore);
    elements.historyEntries.append(entry);
  }
}

function recordOperation(result, kind, folder) {
  if (!result.undoLog || !Array.isArray(result.undoLog.renamed_files)) return;
  operationHistory.push({
    id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    kind,
    folder,
    changed: result.changed,
    timestamp: new Date().toISOString(),
    undoLog: result.undoLog
  });
  operationHistory = operationHistory.slice(-HISTORY_LIMIT);
  persistSavedData();
  renderHistory();
}

async function restoreHistoryItem(item) {
  undoLog = item.undoLog;
  restoringHistoryId = item.id;
  elements.folder.value = item.folder;
  elements.undoLogName.textContent = translate("history.selected");
  renderUndoLogStatus();
  currentMode = "undo";
  currentPage = "workspace";
  history.pushState({}, "", "/tools/undo");
  renderMode();
  renderPage();
  await previewChanges();
}

function clearHistory() {
  if (!operationHistory.length) return;
  if (!window.confirm(translate("messages.confirmClearHistory"))) return;
  operationHistory = [];
  persistSavedData();
  renderHistory();
}

function setMode(mode) {
  if (!["rename", "extensions", "undo"].includes(mode)) return;
  restoringHistoryId = null;
  currentMode = mode;
  currentPage = "workspace";
  const route = { rename: "/tools/01", extensions: "/tools/02", undo: "/tools/undo" }[mode];
  history.pushState({}, "", route);
  renderMode();
  renderPage();
  clearPreview();
}

function openSettingsDialog() {
  const url = new URL(window.location.href);
  if (url.searchParams.get("settings") !== "true") {
    url.searchParams.set("settings", "true");
    history.pushState({}, "", `${url.pathname}${url.search}${url.hash}`);
  }
  if (!elements.settingsDialog.open) elements.settingsDialog.showModal();
  renderPage();
}

function closeSettingsDialog() {
  if (elements.settingsDialog.open) elements.settingsDialog.close();
  removeSettingsQuery();
}

function removeSettingsQuery() {
  const url = new URL(window.location.href);
  if (url.searchParams.get("settings") !== "true") return;
  url.searchParams.delete("settings");
  history.replaceState(history.state, "", `${url.pathname}${url.search}${url.hash}`);
  renderPage();
}

function syncRouteFromLocation() {
  const route = window.location.pathname.replace(/\/+$/, "") || "/";
  const modes = { "/tools/01": "rename", "/tools/02": "extensions", "/tools/undo": "undo" };
  currentMode = modes[route] || "rename";
  currentPage = route === "/home" ? "landing" : modes[route] ? "workspace" : "notFound";
  renderMode();
  renderPage();
  if (new URLSearchParams(window.location.search).get("settings") === "true") {
    if (!elements.settingsDialog.open) elements.settingsDialog.showModal();
  } else if (elements.settingsDialog.open) {
    elements.settingsDialog.close();
  }
}

function renderMode() {
  document.querySelectorAll(".nav-item[data-mode]").forEach((button) => {
    const active = button.dataset.mode === currentMode && currentPage === "workspace";
    button.classList.toggle("active", active);
    button.setAttribute("aria-current", active ? "page" : "false");
  });
  elements.renameOptions.hidden = currentMode !== "rename";
  elements.extensionOptions.hidden = currentMode !== "extensions";
  elements.undoOptions.hidden = currentMode !== "undo";
  elements.backupPanel.hidden = currentMode === "undo";
  elements.undoBackupPanel.hidden = currentMode !== "undo";
  elements.scanOptions.hidden = currentMode === "undo";
  const previewLabel = elements.previewButton.querySelector("[data-i18n]");
  previewLabel.dataset.i18n =
    currentMode === "undo" ? "actions.previewRestoration" : "actions.previewChanges";
  previewLabel.textContent = translate(previewLabel.dataset.i18n);
}

function renderPage() {
  const landing = currentPage === "landing";
  const notFound = currentPage === "notFound";
  const workspace = currentPage === "workspace";
  elements.landingView.hidden = !landing;
  elements.workspaceView.hidden = !workspace;
  elements.pageHeading.hidden = !workspace;
  elements.notFoundView.hidden = !notFound;
  elements.stepIndicator.hidden = !workspace;
  elements.topbar.hidden = notFound;
  const pageKey = { rename: "renamer", extensions: "extensions", undo: "undo" }[currentMode];
  const navigationKey = landing ? "navigation.home" : notFound ? "navigation.notFound" : `navigation.${pageKey}`;
  if (workspace) {
    elements.pageTitle.textContent = translate(`pages.${pageKey}.title`);
    elements.pageDescription.textContent = translate(`pages.${pageKey}.description`);
  }
  document.title = notFound
    ? `${translate("notFound.title")} | ${translate("app.title")}`
    : landing
      ? `${translate("landing.title")} | ${translate("app.title")}`
      : translate("app.title");
  elements.breadcrumbTitle.textContent = translate(navigationKey);
  const settingsButton = document.querySelector('[data-page="settings"]');
  const homeButton = document.querySelector('.sidebar-quick-nav a[href="/home"]');
  const settingsOpen = new URLSearchParams(window.location.search).get("settings") === "true";
  homeButton.classList.toggle("active", landing);
  homeButton.setAttribute("aria-current", landing ? "page" : "false");
  settingsButton.classList.toggle("active", settingsOpen);
  settingsButton.setAttribute("aria-pressed", String(settingsOpen));
}

function clearPreview() {
  currentPreview = null;
  currentPreviewPage = 0;
  elements.previewCount.textContent = "--";
  elements.previewEmpty.hidden = false;
  elements.previewResults.hidden = true;
  elements.previewRows.replaceChildren();
  elements.previewSearch.value = "";
  elements.previewFilterCount.textContent = "";
  elements.previewPagination.hidden = true;
  elements.applyButton.hidden = true;
  elements.previewFooter.classList.remove("ready");
  elements.previewFooterText.textContent = translate("preview.noChangesYet");
}

function readFolderOptions() {
  const folder = elements.folder.value.trim();
  if (!folder) throw new Error(translate("messages.folderRequired"));

  const request = { folder };
  if (currentMode !== "undo") {
    request.recursive = elements.recursive.checked;
    const excludedText = elements.excludedDirs.value.trim();
    if (excludedText.toUpperCase() === "TAKE ALL") {
      request.takeAll = true;
    } else {
      request.excludedDirs = [...preferences.excludedDirs, ...parseCommaList(excludedText)];
      request.excludedExtensions = preferences.excludedExtensions;
    }
  }
  return request;
}

function readModeOptions() {
  if (currentMode === "rename") {
    return readModeOptionsForRename();
  }
  if (currentMode === "extensions") {
    const targets = {};
    document.querySelectorAll("[data-extension]").forEach((input) => {
      targets[input.dataset.extension] = input.value;
    });
    return { targets };
  }
  if (!undoLog) throw new Error(translate("messages.selectUndoLog"));
  return { log: undoLog };
}

async function previewChanges() {
  setBusy(elements.previewButton, true, "actions.scanning");
  try {
    const request = {
      ...readFolderOptions(),
      ...readModeOptions(),
      kind: currentMode
    };
    const response = await apiRequest("/api/preview", request);
    currentPreview = response;
    currentPreviewPage = 0;
    elements.previewSearch.value = "";
    renderPreview(response);
    if (response.totalFiles === 0) showToast(translate("messages.noChanges"));
  } catch (error) {
    clearPreview();
    showToast(error.message, true);
  } finally {
    setBusy(elements.previewButton, false);
  }
}

function filteredPreviewEntries(preview) {
  const search = elements.previewSearch.value.trim().toLocaleLowerCase();
  return preview.entries.filter((entry) =>
    !search || `${entry.old}\n${entry.new}`.toLocaleLowerCase().includes(search)
  );
}

function renderPreview(preview) {
  elements.previewEmpty.hidden = true;
  elements.previewResults.hidden = false;
  elements.previewCount.textContent = String(preview.totalFiles);
  elements.previewSummary.replaceChildren();
  elements.previewRows.replaceChildren();

  const summaryLeft = document.createElement("span");
  summaryLeft.textContent = preview.totalFiles === 1
    ? translate("preview.oneFileWillChange")
    : translate("preview.manyFilesWillChange", { count: preview.totalFiles });
  const summaryRight = document.createElement("strong");
  summaryRight.textContent = preview.folder;
  summaryRight.title = preview.folder;
  elements.previewSummary.append(summaryLeft, summaryRight);

  const entries = filteredPreviewEntries(preview);
  elements.previewFilterCount.textContent = translate("preview.filterCount", {
    shown: entries.length,
    total: preview.totalFiles
  });
  const pageSize = preferences.pageSize;
  const pageCount = Math.max(1, Math.ceil(entries.length / pageSize));
  currentPreviewPage = Math.min(currentPreviewPage, pageCount - 1);
  const firstEntry = currentPreviewPage * pageSize;
  const shownEntries = entries.slice(firstEntry, firstEntry + pageSize);
  for (const entry of shownEntries) {
    const row = document.createElement("tr");
    const original = document.createElement("td");
    const arrow = document.createElement("td");
    const renamed = document.createElement("td");
    original.textContent = entry.old;
    original.title = entry.old;
    arrow.textContent = "->";
    renamed.textContent = entry.new;
    renamed.title = entry.new;
    renamed.className = "new-name";
    row.append(original, arrow, renamed);
    elements.previewRows.append(row);
  }

  elements.previewPagination.hidden = pageCount <= 1;
  elements.previousPreviewPage.disabled = currentPreviewPage === 0;
  elements.nextPreviewPage.disabled = currentPreviewPage >= pageCount - 1;
  elements.previewPageIndicator.textContent = translate("preview.pageIndicator", {
    current: currentPreviewPage + 1,
    total: pageCount
  });
  elements.applyButton.hidden = preview.totalFiles === 0;
  elements.applyButton.dataset.i18n = currentMode === "undo" ? "actions.restoreFiles" : "actions.applyChanges";
  elements.applyButton.textContent = translate(elements.applyButton.dataset.i18n);
  elements.previewFooter.classList.add("ready");
  elements.previewFooterText.textContent = preview.totalFiles
    ? translate("preview.reviewThenApply")
    : translate("preview.noFilesNeedChanges");
}

function changePreviewPage(direction) {
  if (!currentPreview) return;
  const filteredCount = filteredPreviewEntries(currentPreview).length;
  const pageCount = Math.ceil(filteredCount / preferences.pageSize);
  const nextPage = currentPreviewPage + direction;
  if (nextPage < 0 || nextPage >= pageCount) return;
  currentPreviewPage = nextPage;
  renderPreview(currentPreview);
}

async function applyChanges() {
  if (!currentPreview) return;
  const isUndo = currentMode === "undo";
  const confirmation = translate(
    `messages.confirm${isUndo ? "Restore" : "Rename"}${currentPreview.totalFiles === 1 ? "One" : "Many"}`,
    {
      count: currentPreview.totalFiles,
      folder: currentPreview.folder
    }
  );
  if (!window.confirm(confirmation)) return;

  if (preferences.askBackupBeforeApply) {
    const backupCheckboxes = isUndo
      ? ["#undoBackupCopy", "#undoBackupZip"]
      : ["#backupCopy", "#backupZip"];
    if (window.confirm(translate("messages.askBackup"))) {
      backupCheckboxes.forEach((selector) => {
        document.querySelector(selector).checked = true;
      });
    }
  }

  setBusy(elements.applyButton, true, "actions.applying");
  try {
    const backups = currentMode === "undo"
      ? {
          copy: document.querySelector("#undoBackupCopy").checked,
          zip: document.querySelector("#undoBackupZip").checked,
          log: false
        }
      : {
          copy: document.querySelector("#backupCopy").checked,
          zip: document.querySelector("#backupZip").checked,
          log: document.querySelector("#backupLog").checked
        };
    const result = await apiRequest("/api/apply", {
      previewId: currentPreview.previewId,
      backups
    });
    if (restoringHistoryId) {
      operationHistory = operationHistory.filter((item) => item.id !== restoringHistoryId);
    }
    recordOperation(result, currentMode, currentPreview.folder);
    const successKey = currentMode === "undo" ? "messages.fileRestored" : "messages.fileUpdated";
    const pluralKey = currentMode === "undo" ? "messages.filesRestored" : "messages.filesUpdated";
    const successMessage = translate(result.changed === 1 ? successKey : pluralKey, {
      count: result.changed
    });
    const backupMessage = result.backups?.length
      ? translate("messages.backupLocation", { paths: result.backups.join(", ") })
      : "";
    const logMessage = result.log ? translate("messages.undoLogLocation", { path: result.log }) : "";
    showToast(`${successMessage}${backupMessage}${logMessage}`, false, 9000);
    clearPreview();
    restoringHistoryId = null;
  } catch (error) {
    showToast(error.message, true, 8000);
  } finally {
    setBusy(elements.applyButton, false);
  }
}

async function loadUndoLog(event) {
  const file = event.target.files?.[0];
  undoLog = null;
  clearPreview();
  if (!file) {
    elements.undoLogName.textContent = translate("undo.chooseLog");
    elements.undoLogStatus.textContent = translate("undo.folderHelp");
    return;
  }
  if (!file.name.toLowerCase().endsWith(".json") || file.size > 5 * 1024 * 1024) {
    elements.undoLogFile.value = "";
    elements.undoLogName.textContent = translate("undo.fileTooLarge");
    elements.undoLogStatus.textContent = translate("undo.folderHelp");
    showToast(translate("undo.fileTooLarge"), true);
    return;
  }
  try {
    const parsed = JSON.parse(await file.text());
    if (!parsed || !Array.isArray(parsed.renamed_files) || typeof parsed.target_directory !== "string") {
      throw new Error(translate("undo.invalidFile"));
    }
    undoLog = parsed;
    elements.undoLogName.textContent = file.name;
    elements.folder.value = parsed.target_directory;
    renderUndoLogStatus();
  } catch (error) {
    elements.undoLogFile.value = "";
    elements.undoLogName.textContent = translate("undo.invalidFile");
    elements.undoLogStatus.textContent = translate("undo.folderHelp");
    showToast(error.message, true);
  }
}

function renderUndoLogStatus() {
  if (!undoLog) return;
  const translationKey = undoLog.renamed_files.length === 1 ? "undo.selectedOne" : "undo.selectedMany";
  elements.undoLogStatus.textContent = translate(translationKey, {
    count: undoLog.renamed_files.length,
    folder: undoLog.target_directory
  });
}

async function apiRequest(url, payload) {
  let response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
  } catch {
    throw new Error(translate("messages.serverUnavailable"));
  }
  let result;
  try {
    result = await response.json();
  } catch {
    throw new Error(translate("messages.invalidServerResponse"));
  }
  if (!response.ok) throw new Error(translateServerError(result.error || ""));
  return result;
}

function translateServerError(message) {
  const exact = {
    "Enter a folder path.": "errors.enterFolder",
    "The selected path is not a folder.": "errors.notFolder",
    "Invalid request size.": "errors.invalidRequestSize",
    "Request body is empty or too large.": "errors.emptyOrLargeRequest",
    "Request body must contain valid JSON.": "errors.invalidJson",
    "Request body must be a JSON object.": "errors.invalidRequestObject",
    "Unknown operation.": "errors.unknownOperation",
    "The selected folder must match the folder recorded in the undo log.": "errors.wrongFolder",
    "The selected JSON file is not a valid undo log.": "errors.invalidUndoLog",
    "The undo log does not contain a target folder.": "errors.missingUndoRoot",
    "The undo log contains an invalid entry.": "errors.invalidLogEntry",
    "An undo log entry is missing its file paths.": "errors.missingLogPaths",
    "The undo log contains a path outside the selected folder.": "errors.outsideFolder",
    "The undo log contains a file move; only same-folder renames can be restored.": "errors.unsupportedMove",
    "This preview expired. Preview the changes again before applying them.": "errors.expiredPreview",
    "There are no changes to apply.": "errors.noChanges",
    "Backup settings are invalid.": "errors.invalidBackupSettings",
    "Backup options must be enabled or disabled.": "errors.backupOptionsBoolean",
    "Subfolder scanning must be enabled or disabled.": "errors.invalidRecursive",
    "Excluded folders must be a list of folder names.": "errors.excludedList",
    "Excluded extensions must be a list of file extensions.": "errors.excludedExtensionsList",
    "The prefix and separator must be text.": "errors.prefixAndSeparatorText",
    "Category prefixes must be an object.": "errors.categoryPrefixesObject",
    "Choose one or more valid categories.": "errors.validCategories",
    "Extension targets must be an object.": "errors.extensionTargetsObject",
    "Number padding must be a whole number.": "errors.wholeNumberPadding",
    "Number padding must be between 1 and 12.": "errors.paddingRange",
    "Requests must come from this local web app.": "errors.localRequestsOnly",
    "Endpoint not found.": "errors.endpointNotFound"
  };
  if (exact[message]) return translate(exact[message]);

  const patterns = [
    [/^Folder could not be opened: (.*)$/, "errors.folderOpen", (match) => ({ detail: match[1] })],
    [/^The folder recorded in the log is unavailable: (.*)$/, "errors.undoFolderUnavailable", (match) => ({ detail: match[1] })],
    [/^Could not list the selected folder: (.*)$/, "errors.folderList", (match) => ({ detail: match[1] })],
    [/^Could not scan a folder: (.*)$/, "errors.folderScan", (match) => ({ detail: match[1] })],
    [/^Enter a valid prefix for (.*)\.$/, "errors.invalidPrefix", (match) => ({ category: match[1] })],
    [/^Invalid extension for (.*): (.*)$/, "errors.invalidExtension", (match) => ({ category: match[1], extension: match[2] })],
    [/^Enter a valid extension for (.*)\.$/, "errors.validExtension", (match) => ({ category: match[1] })],
    [/^A file in the preview is no longer available: (.*)$/, "errors.fileNotAvailable", (match) => ({ path: match[1] })],
    [/^A source file is no longer available: (.*)$/, "errors.sourceNotAvailable", (match) => ({ path: match[1] })],
    [/^Two files would receive the same name: (.*)$/, "errors.duplicateDestination", (match) => ({ path: match[1] })],
    [/^A destination already exists: (.*)$/, "errors.destinationExists", (match) => ({ path: match[1] })],
    [/^A destination appeared during the operation: (.*)$/, "errors.destinationAppeared", (match) => ({ path: match[1] })],
    [/^Could not create the requested backup: (.*)$/, "errors.createBackup", (match) => ({ detail: match[1] })],
    [/^Could not load the web interface: (.*)$/, "errors.loadInterface", (match) => ({ detail: match[1] })],
    [/^File changes were rolled back: (.*?)(?: Rollback also reported: (.*))?$/, "errors.rollback", (match) => ({ detail: match[1] })],
    [/^A file operation failed: (.*)$/, "errors.applyFailed", (match) => ({ detail: match[1] })]
  ];
  for (const [pattern, key, valuesForMatch] of patterns) {
    const match = message.match(pattern);
    if (match) {
      const translated = translate(key, valuesForMatch(match));
      return key === "errors.rollback" && match[2]
        ? translated + translate("errors.rollbackAlsoFailed", { detail: match[2] })
        : translated;
    }
  }
  if (message.includes("outside the selected folder")) return translate("errors.outsideFolder");
  return message || translate("messages.unknownError");
}

function setBusy(button, busy, messageKey) {
  const label = button.querySelector("[data-i18n]");
  if (busy) {
    button.dataset.originalLabelKey = label?.dataset.i18n || "";
    if (label) label.textContent = translate(messageKey);
    button.disabled = true;
    return;
  }
  button.disabled = false;
  if (label && button.dataset.originalLabelKey) {
    label.dataset.i18n = button.dataset.originalLabelKey;
    label.textContent = translate(button.dataset.originalLabelKey);
  }
  delete button.dataset.originalLabelKey;
}

function showToast(message, isError = false, duration = 5000) {
  window.clearTimeout(toastTimer);
  elements.toast.textContent = message;
  elements.toast.classList.toggle("error", isError);
  elements.toast.classList.add("visible");
  toastTimer = window.setTimeout(() => elements.toast.classList.remove("visible"), duration);
}
