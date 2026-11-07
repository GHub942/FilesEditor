const modeDetails = {
  rename: {
    title: "File renamer",
    description: "Give files a consistent name with category-aware numbering."
  },
  extensions: {
    title: "Extension editor",
    description: "Update file extensions in batches, with a clear preview first."
  },
  undo: {
    title: "Undo changes",
    description: "Restore original filenames from a Files Editor undo log."
  }
};

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
  previewButton: document.querySelector("#previewButton"),
  applyButton: document.querySelector("#applyButton"),
  previewEmpty: document.querySelector("#previewEmpty"),
  previewResults: document.querySelector("#previewResults"),
  previewCount: document.querySelector("#previewCount"),
  previewSummary: document.querySelector("#previewSummary"),
  previewRows: document.querySelector("#previewRows"),
  moreFiles: document.querySelector("#moreFiles"),
  previewFooter: document.querySelector("#previewFooter"),
  previewFooterText: document.querySelector("#previewFooterText"),
  undoLogFile: document.querySelector("#undoLogFile"),
  undoLogName: document.querySelector("#undoLogName"),
  undoLogStatus: document.querySelector("#undoLogStatus"),
  toast: document.querySelector("#toast")
};

let currentMode = "rename";
let undoLog = null;
let currentPreview = null;
let toastTimer = null;

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => setMode(button.dataset.mode));
});

elements.recursive.addEventListener("change", () => {
  elements.excludeBox.hidden = !elements.recursive.checked;
  clearPreview();
});

elements.undoLogFile.addEventListener("change", loadUndoLog);
elements.previewButton.addEventListener("click", previewChanges);
elements.applyButton.addEventListener("click", applyChanges);

function setMode(mode) {
  if (!modeDetails[mode]) return;
  currentMode = mode;
  document.querySelectorAll(".nav-item").forEach((button) => {
    const active = button.dataset.mode === mode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-current", active ? "page" : "false");
  });
  document.querySelector("#pageTitle").textContent = modeDetails[mode].title;
  document.querySelector("#breadcrumbTitle").textContent = modeDetails[mode].title;
  document.querySelector("#pageDescription").textContent = modeDetails[mode].description;
  elements.renameOptions.hidden = mode !== "rename";
  elements.extensionOptions.hidden = mode !== "extensions";
  elements.undoOptions.hidden = mode !== "undo";
  elements.backupPanel.hidden = mode === "undo";
  elements.undoBackupPanel.hidden = mode !== "undo";
  elements.scanOptions.hidden = mode === "undo";
  elements.previewButton.querySelector("span:first-child").textContent =
    mode === "undo" ? "Preview restoration" : "Preview changes";
  clearPreview();
}

function clearPreview() {
  currentPreview = null;
  elements.previewCount.textContent = "--";
  elements.previewEmpty.hidden = false;
  elements.previewResults.hidden = true;
  elements.previewRows.replaceChildren();
  elements.moreFiles.hidden = true;
  elements.applyButton.hidden = true;
  elements.previewFooter.classList.remove("ready");
  elements.previewFooterText.textContent = "Nothing changes until you apply.";
}

function readFolderOptions() {
  const folder = elements.folder.value.trim();
  if (!folder) throw new Error("Enter the full path to a target folder.");

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
  if (!undoLog) throw new Error("Choose a valid undo log first.");
  return { log: undoLog };
}

async function previewChanges() {
  setBusy(elements.previewButton, true, "Scanning...");
  try {
    const request = {
      ...readFolderOptions(),
      ...readModeOptions(),
      kind: currentMode
    };
    const response = await apiRequest("/api/preview", request);
    currentPreview = response;
    renderPreview(response);
    if (response.totalFiles === 0) showToast("No changes are needed for the selected files.", false);
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

  const summaryLeft = document.createElement("span");
  summaryLeft.textContent = preview.totalFiles === 1 ? "1 file will change" : `${preview.totalFiles} files will change`;
  const summaryRight = document.createElement("strong");
  summaryRight.textContent = preview.folder;
  summaryRight.title = preview.folder;
  elements.previewSummary.append(summaryLeft, summaryRight);

  const shownEntries = preview.entries.slice(0, 100);
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

  const remaining = preview.totalFiles - shownEntries.length;
  elements.moreFiles.hidden = remaining <= 0;
  elements.moreFiles.textContent = remaining > 0
    ? `Showing 100 of ${preview.totalFiles} changes. Apply will process all ${preview.totalFiles} files.`
    : "";
  elements.applyButton.hidden = preview.totalFiles === 0;
  elements.applyButton.textContent = currentMode === "undo" ? "Restore files" : "Apply changes";
  elements.previewFooter.classList.add("ready");
  elements.previewFooterText.textContent = preview.totalFiles
    ? "Review the list, then confirm to continue."
    : "No files need changes.";
}

async function applyChanges() {
  if (!currentPreview) return;
  const action = currentMode === "undo" ? "restore" : "rename";
  if (!window.confirm(`This will ${action} ${currentPreview.totalFiles} file(s) in:\n${currentPreview.folder}\n\nContinue?`)) {
    return;
  }

  setBusy(elements.applyButton, true, "Applying...");
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
    const logMessage = result.log ? ` Undo log: ${result.log}` : "";
    const backupMessage = result.backups?.length ? ` Backup: ${result.backups.join(", ")}.` : "";
    showToast(`${result.changed} file(s) ${currentMode === "undo" ? "restored" : "updated"}.${backupMessage}${logMessage}`, false, 9000);
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
    elements.undoLogName.textContent = "Choose an undo log";
    elements.undoLogStatus.textContent = "The target folder must match the one recorded in the log.";
    return;
  }
  if (!file.name.toLowerCase().endsWith(".json") || file.size > 5 * 1024 * 1024) {
    elements.undoLogFile.value = "";
    elements.undoLogName.textContent = "Choose a JSON file smaller than 5 MB";
    elements.undoLogStatus.textContent = "This log could not be loaded.";
    showToast("Select a JSON undo log smaller than 5 MB.", true);
    return;
  }
  try {
    const parsed = JSON.parse(await file.text());
    if (!parsed || !Array.isArray(parsed.renamed_files) || typeof parsed.target_directory !== "string") {
      throw new Error("This file is not a Files Editor undo log.");
    }
    undoLog = parsed;
    elements.undoLogName.textContent = file.name;
    elements.undoLogStatus.textContent = `${parsed.renamed_files.length} recorded change(s). Target: ${parsed.target_directory}`;
    elements.folder.value = parsed.target_directory;
  } catch (error) {
    elements.undoLogFile.value = "";
    elements.undoLogName.textContent = "The selected file is not a valid undo log";
    elements.undoLogStatus.textContent = error.message;
    showToast(error.message, true);
  }
}

async function apiRequest(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  let result;
  try {
    result = await response.json();
  } catch {
    throw new Error("The local server returned an invalid response.");
  }
  if (!response.ok) throw new Error(result.error || `Request failed (${response.status}).`);
  return result;
}

function setBusy(button, busy, label) {
  if (busy) {
    button.dataset.originalHtml = button.innerHTML;
    button.disabled = true;
    button.textContent = label;
    return;
  }
  button.disabled = false;
  if (button.dataset.originalHtml) {
    button.innerHTML = button.dataset.originalHtml;
    delete button.dataset.originalHtml;
  }
}

function showToast(message, isError, duration = 5000) {
  window.clearTimeout(toastTimer);
  elements.toast.textContent = message;
  elements.toast.classList.toggle("error", isError);
  elements.toast.classList.add("visible");
  toastTimer = window.setTimeout(() => elements.toast.classList.remove("visible"), duration);
}
