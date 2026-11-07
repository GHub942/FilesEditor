const SUPPORTED_LANGUAGES = ["en", "fr"];
const PREVIEW_PAGE_SIZE = 25;
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
  toast: document.querySelector("#toast")
};

let currentMode = "rename";
let currentPage = "workspace";
let currentLanguage = "en";
let undoLog = null;
let currentPreview = null;
let currentPreviewPage = 0;
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
window.addEventListener("popstate", syncRouteFromLocation);

initialize();

async function initialize() {
  try {
    await loadDictionaries();
    restorePreferences();
    elements.languageSelect.value = currentLanguage;
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
    } else {
      clearSavedPreferences();
    }
  } catch (error) {
    elements.forgetPreferences.checked = true;
    currentLanguage = "en";
    console.warn("Could not read saved preferences; using the no-save defaults.", error);
  }
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
}

function setMode(mode) {
  if (!["rename", "extensions", "undo"].includes(mode)) return;
  currentMode = mode;
  currentPage = "workspace";
  const route = { rename: "/tools/01", extensions: "/tools/02", undo: "/tools/undo" }[mode];
  history.pushState({}, "", route);
  renderMode();
  renderPage();
  clearPreview();
}

function openSettingsDialog() {
  if (new URL(window.location.href).searchParams.get("settings") !== "true") {
    const url = new URL(window.location.href);
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
  if (new URL(window.location.href).searchParams.get("settings") === "true") {
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
  elements.previewButton.querySelector("[data-i18n]").dataset.i18n =
    currentMode === "undo" ? "actions.previewRestoration" : "actions.previewChanges";
  elements.previewButton.querySelector("[data-i18n]").textContent =
    translate(elements.previewButton.querySelector("[data-i18n]").dataset.i18n);
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
  const settingsOpen = new URL(window.location.href).searchParams.get("settings") === "true";
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
      request.excludedDirs = excludedText
        .split(",")
        .map((name) => name.trim())
        .filter(Boolean);
    }
  }
  return request;
}

function readModeOptions() {
  if (currentMode === "rename") {
    const categories = [...document.querySelectorAll("#categoryFilters input:checked")]
      .map((input) => input.value);
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
    renderPreview(response);
    if (response.totalFiles === 0) showToast(translate("messages.noChanges"));
  } catch (error) {
    clearPreview();
    showToast(error.message, true);
  } finally {
    setBusy(elements.previewButton, false);
  }
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

  const pageCount = Math.max(1, Math.ceil(preview.totalFiles / PREVIEW_PAGE_SIZE));
  currentPreviewPage = Math.min(currentPreviewPage, pageCount - 1);
  const firstEntry = currentPreviewPage * PREVIEW_PAGE_SIZE;
  const shownEntries = preview.entries.slice(firstEntry, firstEntry + PREVIEW_PAGE_SIZE);
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
  const pageCount = Math.ceil(currentPreview.totalFiles / PREVIEW_PAGE_SIZE);
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
