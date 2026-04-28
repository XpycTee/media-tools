let activeVideoJobId = null;
let pollingTimer = null;
let pollingInFlight = false;

function createSortable(container) {
  if (!container) return;
  new Sortable(container, { animation: 150, group: "shared" });
}

function getAppMode() {
  return document.body?.dataset?.appMode || "browser";
}

function isDesktopMode() {
  return getAppMode() === "desktop";
}

function hasDesktopPicker() {
  return isDesktopMode() && Boolean(window.pywebview?.api?.pick_media_source);
}

function hasDesktopSavePicker() {
  return isDesktopMode() && Boolean(window.pywebview?.api?.pick_merge_output);
}

function extractComparableName(fileLike) {
  if (!fileLike) return "";
  if (typeof fileLike === "string") return fileLike;
  return fileLike.relative_name || fileLike.webkitRelativePath || fileLike.name || fileLike.display_name || "";
}

function extractNumberFromFilename(name) {
  const base = (name || "").split("/").pop();
  const m = base.match(/(\d+)/);
  return m ? parseInt(m[1], 10) : null;
}

function sortFilesByNumberThenAlpha(fileArray) {
  return fileArray.sort((a, b) => {
    const aName = extractComparableName(a);
    const bName = extractComparableName(b);
    const aNum = extractNumberFromFilename(aName);
    const bNum = extractNumberFromFilename(bName);
    if (aNum !== null && bNum !== null) {
      if (aNum !== bNum) return aNum - bNum;
      return aName.localeCompare(bName, undefined, { sensitivity: "base" });
    }
    if (aNum !== null) return -1;
    if (bNum !== null) return 1;
    return aName.localeCompare(bName, undefined, {
      sensitivity: "base",
      numeric: true,
    });
  });
}

function setProgressBar(barId, percentId, value) {
  const bar = document.getElementById(barId);
  const percent = document.getElementById(percentId);
  const safe = Math.max(0, Math.min(100, Number(value) || 0));
  if (bar) bar.style.width = `${safe}%`;
  if (percent) percent.textContent = `${safe.toFixed(1)}%`;
}

function setProgressStatus(text) {
  const status = document.getElementById("video-progress-status");
  if (status) status.textContent = text;
}

function setCurrentFileLabel(value) {
  const current = document.getElementById("video-current-file");
  const label = value ? `Текущий файл: ${value}` : "Текущий файл: -";
  if (current) current.textContent = label;
}

function setCompileButtonDisabled(disabled) {
  const btn = document.querySelector(".compile-btn");
  if (btn) btn.disabled = Boolean(disabled);
}

function openProgressOverlay() {
  const overlay = document.getElementById("video-progress-overlay");
  if (!overlay) return;
  overlay.classList.add("visible");
  overlay.setAttribute("aria-hidden", "false");
}

function closeProgressOverlay() {
  const overlay = document.getElementById("video-progress-overlay");
  if (!overlay) return;
  overlay.classList.remove("visible");
  overlay.setAttribute("aria-hidden", "true");
}

function renderResults(results, error) {
  const container = document.getElementById("video-progress-results");
  if (!container) return;
  container.classList.remove("hidden");
  container.innerHTML = "";

  const list = document.createElement("ul");
  list.className = "video-progress-results-list";
  const entries = Object.entries(results || {});

  if (!entries.length && !error) {
    const empty = document.createElement("p");
    empty.className = "video-result-info";
    empty.textContent = "Нет обработанных файлов.";
    container.appendChild(empty);
    return;
  }

  if (entries.length) {
    entries.forEach(([file, message]) => {
      const li = document.createElement("li");
      li.className = "video-result-item";
      const isSuccess = typeof message === "string" && message.startsWith("Created ");
      li.classList.add(isSuccess ? "video-result-item--success" : "video-result-item--error");
      li.textContent = `${file}: ${message}`;
      list.appendChild(li);
    });
    container.appendChild(list);
  }

  if (error) {
    const err = document.createElement("p");
    err.className = "video-result-error";
    err.textContent = `Ошибка: ${error}`;
    container.appendChild(err);
  }
}

function resetProgressUi() {
  setProgressStatus("Подготовка задачи...");
  setCurrentFileLabel(null);
  setProgressBar("video-overall-bar", "video-overall-percent", 0);
  setProgressBar("video-current-bar", "video-current-percent", 0);
  const results = document.getElementById("video-progress-results");
  if (results) {
    results.classList.add("hidden");
    results.innerHTML = "";
  }
}

function stopPolling() {
  if (pollingTimer) {
    clearInterval(pollingTimer);
    pollingTimer = null;
  }
  pollingInFlight = false;
}

function applyStatus(status) {
  setProgressBar("video-overall-bar", "video-overall-percent", status.overall_percent);
  setProgressBar(
    "video-current-bar",
    "video-current-percent",
    status.current_file_percent
  );
  setCurrentFileLabel(status.current_file);

  if (status.status === "queued") {
    setProgressStatus("Задача в очереди...");
    return;
  }
  if (status.status === "running") {
    setProgressStatus(
      `Обработка: ${status.processed || 0}/${status.total || 0}`
    );
    return;
  }
  if (status.status === "completed") {
    setProgressStatus("Готово");
    renderResults(status.results, null);
    setCompileButtonDisabled(false);
    return;
  }

  setProgressStatus("Завершено с ошибкой");
  renderResults(status.results, status.error || "Неизвестная ошибка");
  setCompileButtonDisabled(false);
}

async function pollJobStatus() {
  if (!activeVideoJobId || pollingInFlight) return;
  pollingInFlight = true;
  try {
    const response = await fetch(`/api/video/merge/status/${activeVideoJobId}`);
    if (!response.ok) {
      let msg = `HTTP ${response.status}`;
      try {
        const body = await response.json();
        if (body && body.error) msg = body.error;
      } catch (err) {}
      throw new Error(msg);
    }

    const status = await response.json();
    applyStatus(status);
    if (status.status === "completed" || status.status === "failed") {
      stopPolling();
      activeVideoJobId = null;
    }
  } catch (err) {
    stopPolling();
    activeVideoJobId = null;
    setProgressStatus("Ошибка при получении статуса");
    renderResults({}, err.message || "Не удалось получить прогресс");
    setCompileButtonDisabled(false);
  } finally {
    pollingInFlight = false;
  }
}

function startPolling() {
  stopPolling();
  pollJobStatus();
  pollingTimer = setInterval(pollJobStatus, 800);
}

function collectCompilePayload() {
  const data = {};
  const videoItems = [...document.querySelectorAll("#video-column .file-item")];
  const columns = [...document.querySelectorAll('.column:not([data-type="video"])')];

  videoItems.forEach((videoItem, index) => {
    const videoKey = videoItem.dataset.filepath || videoItem.dataset.filename;
    data[videoKey] = { audio: [], subtitles: [] };
    columns.forEach((col) => {
      const type = col.dataset.type;
      const files = [...col.querySelectorAll(".file-item")];
      const file = files[index];
      if (!file) return;
      const trackInput = col.querySelector(".track-name-input");
      const trackName = trackInput?.value?.trim() || trackInput?.placeholder || "";
      const fileRef = file.dataset.filepath || file.dataset.filename;
      if (type === "audio") data[videoKey].audio.push({ name: trackName, file: fileRef });
      if (type === "subtitle") {
        const defaultRadio = col.querySelector('.default-subtitle-radio');
        const isDefault = defaultRadio ? defaultRadio.checked : false;
        data[videoKey].subtitles.push({ name: trackName, file: fileRef, default: isDefault });
      }
    });
  });
  return data;
}

async function pickMergeOutputTarget(videoCount, items) {
  if (!hasDesktopSavePicker() || videoCount <= 0) return null;

  const firstVideoKey = Object.keys(items)[0];
  const suggestedName = firstVideoKey
    ? `muxed_${firstVideoKey.split(/[\\/]/).pop()}`
    : "muxed_output.mkv";

  try {
    const payload = await window.pywebview.api.pick_merge_output(videoCount, suggestedName);
    if (!payload) return null;
    if (payload.error) throw new Error(payload.error);
    if (!payload.path) return { cancelled: true };
    return payload;
  } catch (err) {
    throw new Error(err?.message || "Не удалось выбрать место сохранения");
  }
}

function createFileItem({ name, path, relativePath }) {
  const item = document.createElement("div");
  item.className = "file-item";
  item.dataset.filename = name;
  item.dataset.filepath = path;
  item.dataset.relativePath = relativePath || name;
  item.innerHTML = `<span class="file-item-name" title="${name}">${name}</span><button class="delete-btn btn btn--danger" type="button" onclick="removeFile(event)">Удалить</button>`;
  return item;
}

function appendFilesToColumn(columnContent, entries) {
  entries.forEach((entry) => {
    columnContent.appendChild(
      createFileItem({
        name: entry.display_name,
        path: entry.path,
        relativePath: entry.relative_name,
      })
    );
  });
}

function updateTrackNameClearButton(input) {
  if (!input) return;
  const wrap = input.closest(".track-name-wrap");
  const clearButton = wrap?.querySelector(".track-name-clear");
  if (!clearButton) return;
  clearButton.classList.toggle("is-visible", Boolean(input.value));
}

function maybeApplyTrackNameHint(columnElem, selectionKind, trackNameHint) {
  if (selectionKind !== "directory" || !trackNameHint) return;
  const input = columnElem?.querySelector(".track-name-input");
  if (input && !input.value) {
    input.value = trackNameHint;
    updateTrackNameClearButton(input);
  }
}

function normalizeBrowserFiles(fileList, columnType, selectionKind) {
  let fileArray = fileList ? Array.from(fileList) : [];
  fileArray = sortFilesByNumberThenAlpha(fileArray);

  const entries = [];
  fileArray.forEach((file) => {
    const ext = file.name.split(".").pop().toLowerCase();
    if (columnType === "video" && ext !== "mkv") return;
    if (columnType === "audio" && ext !== "mka") return;
    if (columnType === "subtitle" && !["srt", "ass", "vtt"].includes(ext)) return;

    const path = file.webkitRelativePath || file.name;
    entries.push({
      path,
      display_name: file.name,
      relative_name: path,
    });
  });

  let trackNameHint = null;
  if (selectionKind === "directory" && entries.length > 0) {
    const firstPath = entries[0].relative_name || entries[0].display_name;
    if (firstPath.includes("/")) {
      trackNameHint = firstPath.split("/")[0];
    }
  }

  return {
    selection_kind: selectionKind,
    track_name_hint: trackNameHint,
    files: entries,
  };
}

function handleVideoFiles(event, columnId) {
  // В десктопном режиме используем диалог выбора файлов
  if (hasDesktopPicker()) {
    event.preventDefault();
    openDesktopPicker("video", columnId);
    // Сброс значения input, чтобы можно было выбрать те же файлы снова
    event.target.value = "";
    return;
  }
  const columnContent = document.getElementById(columnId);
  if (!columnContent) return;
  const payload = normalizeBrowserFiles(event.target.files, "video", "file");
  appendFilesToColumn(columnContent, payload.files);
  event.target.value = "";
}

function handleBrowserSourceSelection(event, columnId, columnType, selectionKind) {
  const columnContent = document.getElementById(columnId);
  const columnElem = columnContent?.closest(".column") || columnContent;
  if (!columnContent) return;

  const payload = normalizeBrowserFiles(event.target.files, columnType, selectionKind);
  appendFilesToColumn(columnContent, payload.files);
  maybeApplyTrackNameHint(columnElem, payload.selection_kind, payload.track_name_hint);
  event.target.value = "";
}

function handleTrackNameInput(event) {
  updateTrackNameClearButton(event.target);
}

function clearTrackName(button) {
  const wrap = button.closest(".track-name-wrap");
  const input = wrap?.querySelector(".track-name-input");
  if (!input) return;
  input.value = "";
  updateTrackNameClearButton(input);
  input.focus();
}

function handleDefaultSubtitleChange(radio) {
  // Устанавливаем data-атрибут для колонки
  const column = radio.closest('.column');
  if (!column) return;
  // Снимаем атрибут у всех колонок субтитров
  document.querySelectorAll('.column[data-type="subtitle"]').forEach(col => {
    col.dataset.defaultSubtitle = 'false';
  });
  // Устанавливаем атрибут для выбранной колонки
  column.dataset.defaultSubtitle = radio.checked ? 'true' : 'false';
}

function removeFile(event) {
  event.preventDefault();
  const item = event.target.closest(".file-item");
  if (item) item.remove();
}

function getNextTrackPlaceholder(type) {
  const sameTypeColumns = document.querySelectorAll(`.column[data-type="${type}"]`);
  return `Дорожка ${sameTypeColumns.length + 1}`;
}

function buildUploadControls(type, id) {
  const mediaLabel = type === "audio" ? "аудио" : "субтитры";
  const accept = type === "audio" ? ".mka" : ".srt,.ass,.vtt";

  if (isDesktopMode()) {
    return `<div class="video-upload-actions video-upload-actions--single">
      <button class="btn-upload video-upload-button" type="button" onclick="openDesktopPicker('${type}', '${id}')">Загрузить ${mediaLabel}</button>
    </div>`;
  }

  return `<div class="video-upload-actions">
    <label class="upload-label btn-upload">Выбрать папку<input type="file" multiple webkitdirectory accept="${accept}" onchange="handleBrowserSourceSelection(event,'${id}','${type}','directory')"></label>
    <label class="upload-label btn-upload">Выбрать файл<input type="file" multiple accept="${accept}" onchange="handleBrowserSourceSelection(event,'${id}','${type}','file')"></label>
  </div>`;
}

function addColumn(type) {
  const columnsContainer = document.getElementById("columns");
  const id = `${type}-${Date.now()}`;
  const title = type === "audio" ? "Озвучка" : "Субтитры";
  const placeholder = getNextTrackPlaceholder(type);
  const column = document.createElement("div");
  column.className = "column panel";
  column.dataset.type = type;
  // Добавляем радио-кнопку "Включить по умолчанию" только для субтитров
  const defaultRadioHtml = type === "subtitle"
    ? `<div class="default-subtitle-wrap"><label class="default-subtitle-label"><input type="radio" name="default-subtitle" class="default-subtitle-radio" onchange="handleDefaultSubtitleChange(this)"> Включить по умолчанию</label></div>`
    : '';
  column.innerHTML = `<div class="column-header"><div class="column-header-top"><span class="column-title">${title}</span><button class="delete-btn btn btn--danger" type="button" onclick="removeColumn(this)">Удалить</button></div><div class="track-name-wrap"><input type="text" class="track-name-input field" placeholder="${placeholder}" oninput="handleTrackNameInput(event)" /><button class="track-name-clear" type="button" aria-label="Очистить поле" onclick="clearTrackName(this)"></button></div>${defaultRadioHtml}</div><div class="column-content" id="${id}" data-type="${type}"></div>${buildUploadControls(type, id)}`;
  columnsContainer.appendChild(column);
  createSortable(column.querySelector(".column-content"));
}

function removeColumn(button) {
  const column = button.closest(".column");
  const content = column?.querySelector(".column-content");
  if (content && content.children.length > 0) {
    if (!confirm("Колонка содержит файлы. Удалить?")) return;
  }
  if (column) column.remove();
}

function askDesktopSelectionKind(type) {
  let label;
  if (type === "audio") label = "озвучки";
  else if (type === "subtitle") label = "субтитров";
  else if (type === "video") label = "видео";
  else label = "файлов";
  const pickDirectory = window.confirm(
    `Выбрать папку для ${label}?\n\nНажмите OK для папки или Cancel для выбора файла.`
  );
  return pickDirectory ? "directory" : "file";
}

async function openDesktopPicker(type, columnId) {
  if (!hasDesktopPicker()) {
    alert("Desktop picker недоступен.");
    return;
  }

  const columnContent = document.getElementById(columnId);
  const columnElem = columnContent?.closest(".column") || columnContent;
  if (!columnContent) return;

  const selectionKind = askDesktopSelectionKind(type);

  try {
    const payload = await window.pywebview.api.pick_media_source(type, selectionKind);
    if (!payload) return;
    if (payload.error) {
      alert(payload.error);
      return;
    }

    const files = sortFilesByNumberThenAlpha([...(payload.files || [])]);
    appendFilesToColumn(columnContent, files);
    maybeApplyTrackNameHint(columnElem, payload.selection_kind, payload.track_name_hint);
  } catch (err) {
    alert(err?.message || "Не удалось открыть диалог выбора.");
  }
}

async function compileMedia() {
  const items = collectCompilePayload();
  const videoCount = Object.keys(items).length;
  const hasVideos = videoCount > 0;

  openProgressOverlay();
  resetProgressUi();

  if (!hasVideos) {
    setProgressStatus("Добавьте хотя бы один видеофайл.");
    renderResults({}, null);
    return;
  }

  setCompileButtonDisabled(true);
  setProgressStatus("Подготовка места сохранения...");

  try {
    const outputTarget = await pickMergeOutputTarget(videoCount, items);
    if (outputTarget?.cancelled) {
      setProgressStatus("Сохранение отменено");
      renderResults({}, null);
      setCompileButtonDisabled(false);
      return;
    }

    const payload = outputTarget ? { items, output: outputTarget } : items;
    setProgressStatus("Запуск объединения...");

    const response = await fetch("/api/video/merge/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      let msg = `HTTP ${response.status}`;
      try {
        const body = await response.json();
        if (body && body.error) msg = body.error;
      } catch (err) {}
      throw new Error(msg);
    }

    const responsePayload = await response.json();
    if (!responsePayload.job_id) {
      throw new Error("Сервер не вернул job_id");
    }
    activeVideoJobId = responsePayload.job_id;
    startPolling();
  } catch (err) {
    setProgressStatus("Ошибка запуска задачи");
    renderResults({}, err.message || "Не удалось запустить задачу");
    setCompileButtonDisabled(false);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  createSortable(document.getElementById("video-column"));
  const cols = document.getElementById("columns");
  if (cols) {
    new Sortable(cols, {
      animation: 150,
      draggable: '.column:not([data-type="video"])',
      handle: ".column-header-top",
    });
  }

  const closeBtn = document.getElementById("video-progress-close-btn");
  if (closeBtn) {
    closeBtn.addEventListener("click", closeProgressOverlay);
  }

  // В десктопном режиме заменяем input для видео на кнопку, как для аудио/субтитров
  if (isDesktopMode()) {
    const videoColumn = document.querySelector('.column[data-type="video"]');
    if (videoColumn) {
      const label = videoColumn.querySelector('.upload-label');
      if (label) {
        // Создаём контейнер с кнопкой, идентичный тому, что используется для аудио/субтитров
        const newContainer = document.createElement('div');
        newContainer.className = 'video-upload-actions video-upload-actions--single';
        newContainer.innerHTML = '<button class="btn-upload video-upload-button" type="button" onclick="openDesktopPicker(\'video\', \'video-column\')">Загрузить видео</button>';
        // Заменяем label на новый контейнер
        label.replaceWith(newContainer);
      }
    }
  }
});

window.handleVideoFiles = handleVideoFiles;
window.handleBrowserSourceSelection = handleBrowserSourceSelection;
window.removeFile = removeFile;
window.addColumn = addColumn;
window.removeColumn = removeColumn;
window.handleTrackNameInput = handleTrackNameInput;
window.clearTrackName = clearTrackName;
window.compileMedia = compileMedia;
window.openDesktopPicker = openDesktopPicker;
