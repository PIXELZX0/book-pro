const DEFAULT_MODEL_BY_PROVIDER = {
  "open-ai": "gpt-4.1-mini",
  anthropic: "claude-sonnet-4-20250514",
  openrouter: "openai/gpt-4.1-mini",
  venice: "venice-uncensored",
  "kilo-code": "anthropic/claude-sonnet-4.5",
  "opencode-go": "claude-sonnet-4-5",
};

const STORAGE_KEY = "book-pro-panel-settings";

const state = {
  settings: {
    selectedProvider: "open-ai",
    language: "ko",
    models: { ...DEFAULT_MODEL_BY_PROVIDER },
    apiKeys: {
      "open-ai": "",
      anthropic: "",
      openrouter: "",
      venice: "",
      "kilo-code": "",
      "opencode-go": "",
    },
  },
  studioProjects: [],
  studioSeriesList: [],
  studioSession: { slug: null, messages: [] },
  studioSeries: null,
  studioBible: { slug: null, containerType: null, containerLabel: "" },
};

const el = {
  toast: document.getElementById("toast"),

  studioProjectList: document.getElementById("studio-project-list"),
  studioNewFormatSelect: document.getElementById("studio-new-format-select"),
  studioNewTitleInput: document.getElementById("studio-new-title-input"),
  studioNewGenreInput: document.getElementById("studio-new-genre-input"),
  studioNewPremiseInput: document.getElementById("studio-new-premise-input"),
  studioCreateBtn: document.getElementById("studio-create-btn"),
  studioEmptyState: document.getElementById("studio-empty-state"),
  studioChatArea: document.getElementById("studio-chat-area"),
  studioChatScroll: document.getElementById("studio-chat-scroll"),
  studioMessageInput: document.getElementById("studio-message-input"),
  studioSendBtn: document.getElementById("studio-send-btn"),
  studioFinalizeBtn: document.getElementById("studio-finalize-btn"),
  studioFinalizeForm: document.getElementById("studio-finalize-form"),
  studioFinalizeIndexInput: document.getElementById("studio-finalize-index-input"),
  studioFinalizeTitleInput: document.getElementById("studio-finalize-title-input"),
  studioFinalizeContentInput: document.getElementById("studio-finalize-content-input"),
  studioFinalizeSaveBtn: document.getElementById("studio-finalize-save-btn"),
  studioFinalizeCancelBtn: document.getElementById("studio-finalize-cancel-btn"),
  studioBookBibleBtn: document.getElementById("studio-book-bible-btn"),

  studioSeriesArea: document.getElementById("studio-series-area"),
  studioSeriesTitle: document.getElementById("studio-series-title"),
  studioSeriesBibleBtn: document.getElementById("studio-series-bible-btn"),
  studioVolumeList: document.getElementById("studio-volume-list"),
  studioNewVolumeTitleInput: document.getElementById("studio-new-volume-title-input"),
  studioNewVolumeIndexInput: document.getElementById("studio-new-volume-index-input"),
  studioAddVolumeBtn: document.getElementById("studio-add-volume-btn"),

  studioBibleArea: document.getElementById("studio-bible-area"),
  studioBibleBackBtn: document.getElementById("studio-bible-back-btn"),
  studioBibleChatScroll: document.getElementById("studio-bible-chat-scroll"),
  studioBibleMessageInput: document.getElementById("studio-bible-message-input"),
  studioBibleSendBtn: document.getElementById("studio-bible-send-btn"),
  studioBibleSettingInput: document.getElementById("studio-bible-setting-input"),
  studioBibleCharactersInput: document.getElementById("studio-bible-characters-input"),
  studioBibleSaveBtn: document.getElementById("studio-bible-save-btn"),
};

function escapeHtml(text) {
  return (text || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function showToast(message, isError = false) {
  if (!el.toast) return;
  el.toast.textContent = message;
  el.toast.style.background = isError ? "#6b1010" : "#000000";
  el.toast.classList.add("show");
  window.clearTimeout(showToast._timer);
  showToast._timer = window.setTimeout(() => {
    el.toast.classList.remove("show");
  }, 2200);
}

function loadSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw);

    if (typeof parsed.selectedProvider === "string" && parsed.selectedProvider.trim()) {
      state.settings.selectedProvider = parsed.selectedProvider.trim();
    }
    if (typeof parsed.language === "string" && parsed.language.trim()) {
      state.settings.language = parsed.language.trim();
    }
    if (parsed.models && typeof parsed.models === "object") {
      Object.keys(DEFAULT_MODEL_BY_PROVIDER).forEach((provider) => {
        const candidate = parsed.models[provider];
        if (typeof candidate === "string" && candidate.trim()) {
          state.settings.models[provider] = candidate.trim();
        }
      });
    }
    if (parsed.apiKeys && typeof parsed.apiKeys === "object") {
      Object.keys(state.settings.apiKeys).forEach((provider) => {
        const key = parsed.apiKeys[provider];
        if (typeof key === "string") {
          state.settings.apiKeys[provider] = key;
        }
      });
    }
  } catch (_error) {
    state.settings = {
      selectedProvider: "open-ai",
      language: "ko",
      models: { ...DEFAULT_MODEL_BY_PROVIDER },
      apiKeys: {
        "open-ai": "",
        anthropic: "",
        openrouter: "",
        venice: "",
        "kilo-code": "",
        "opencode-go": "",
      },
    };
  }
}

function getRunConfig() {
  const provider = state.settings.selectedProvider;
  return {
    provider,
    model: state.settings.models[provider] || DEFAULT_MODEL_BY_PROVIDER[provider] || "",
    apiKey: state.settings.apiKeys[provider] || "",
    language: state.settings.language || "ko",
  };
}

function showStudioPanel(panel) {
  el.studioEmptyState?.classList.toggle("hidden", panel !== "empty");
  el.studioSeriesArea?.classList.toggle("hidden", panel !== "series");
  el.studioChatArea?.classList.toggle("hidden", panel !== "chat");
  el.studioBibleArea?.classList.toggle("hidden", panel !== "bible");
}

async function loadStudioProjects() {
  if (!el.studioProjectList) return;
  try {
    const [booksResponse, seriesResponse] = await Promise.all([
      fetch(`/books?page=1&page_size=50`),
      fetch(`/studio/series`),
    ]);
    if (!booksResponse.ok) throw new Error(`HTTP ${booksResponse.status}`);
    if (!seriesResponse.ok) throw new Error(`HTTP ${seriesResponse.status}`);
    const booksPayload = await booksResponse.json();
    state.studioProjects = (booksPayload.items || []).filter((item) => item.is_studio && !item.series_slug);
    state.studioSeriesList = await seriesResponse.json();
  } catch (error) {
    showToast(error.message || "Failed to load studio projects", true);
    state.studioProjects = [];
    state.studioSeriesList = [];
  }
  renderStudioProjectList();
}

function renderStudioProjectList() {
  if (!el.studioProjectList) return;
  const seriesButtons = state.studioSeriesList.map(
    (item) => `
      <button type="button" class="btn btn-ghost full studio-series-item" data-slug="${escapeHtml(item.slug)}">
        📚 ${escapeHtml(item.series_title)} (${item.volumes.length}권)
      </button>
    `,
  );
  const bookButtons = state.studioProjects.map(
    (item) => `
      <button type="button" class="btn btn-ghost full studio-project-item" data-slug="${escapeHtml(item.slug)}">
        ${escapeHtml(item.book_title)}
      </button>
    `,
  );
  const allButtons = [...seriesButtons, ...bookButtons].join("");
  el.studioProjectList.innerHTML =
    allButtons || `<p class="chat-empty">아직 스튜디오 프로젝트가 없습니다.</p>`;

  el.studioProjectList.querySelectorAll(".studio-project-item").forEach((button) => {
    button.addEventListener("click", () => void openStudioProject(button.dataset.slug));
  });
  el.studioProjectList.querySelectorAll(".studio-series-item").forEach((button) => {
    button.addEventListener("click", () => void openStudioSeries(button.dataset.slug));
  });
}

async function createStudioProjectOrSeries() {
  const title = (el.studioNewTitleInput?.value || "").trim();
  if (!title) {
    showToast("제목을 입력해 주세요.", true);
    return;
  }
  const format = el.studioNewFormatSelect?.value === "long" ? "long" : "short";
  const config = getRunConfig();
  const body = {
    title,
    genre: (el.studioNewGenreInput?.value || "").trim(),
    premise: (el.studioNewPremiseInput?.value || "").trim(),
    language: config.language,
  };

  try {
    const endpoint = format === "long" ? "/studio/series" : "/studio/projects";
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(payload?.detail || `HTTP ${response.status}`);
    }
    const created = await response.json();
    if (el.studioNewTitleInput) el.studioNewTitleInput.value = "";
    if (el.studioNewGenreInput) el.studioNewGenreInput.value = "";
    if (el.studioNewPremiseInput) el.studioNewPremiseInput.value = "";
    await loadStudioProjects();
    if (format === "long") {
      await openStudioSeries(created.slug);
    } else {
      await openStudioProject(created.slug);
    }
  } catch (error) {
    showToast(error.message || "Failed to create project", true);
  }
}

async function openStudioProject(slug) {
  if (!slug) return;
  try {
    const response = await fetch(`/studio/projects/${encodeURIComponent(slug)}`);
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(payload?.detail || `HTTP ${response.status}`);
    }
    const project = await response.json();
    state.studioSession = {
      slug,
      messages: project.messages || [],
      chapterCount: project.chapter_count || 0,
      bookTitle: project.book_title || "",
    };
    state.studioSeries = null;
    showStudioPanel("chat");
    closeStudioFinalizeForm();
    renderStudioChat();
  } catch (error) {
    showToast(error.message || "Failed to open project", true);
  }
}

async function openStudioSeries(slug) {
  if (!slug) return;
  try {
    const response = await fetch(`/studio/series/${encodeURIComponent(slug)}`);
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(payload?.detail || `HTTP ${response.status}`);
    }
    state.studioSeries = await response.json();
    showStudioPanel("series");
    renderStudioSeries();
  } catch (error) {
    showToast(error.message || "Failed to open series", true);
  }
}

function renderStudioSeries() {
  const series = state.studioSeries;
  if (!series) return;
  if (el.studioSeriesTitle) el.studioSeriesTitle.textContent = series.series_title;
  if (!el.studioVolumeList) return;

  el.studioVolumeList.innerHTML = series.volumes.length
    ? series.volumes
        .map(
          (volume) => `
            <button type="button" class="btn btn-ghost full studio-volume-item" data-slug="${escapeHtml(volume.slug)}">
              ${volume.volume_index}권. ${escapeHtml(volume.book_title)} (${volume.chapter_count}장)
            </button>
          `,
        )
        .join("")
    : `<p class="chat-empty">아직 권이 없습니다. 아래에서 첫 권을 추가하세요.</p>`;

  el.studioVolumeList.querySelectorAll(".studio-volume-item").forEach((button) => {
    button.addEventListener("click", () => void openStudioProject(button.dataset.slug));
  });

  if (el.studioNewVolumeIndexInput) {
    el.studioNewVolumeIndexInput.value = String(series.volumes.length + 1);
  }
}

async function addStudioVolume() {
  const series = state.studioSeries;
  if (!series?.slug) return;
  const title = (el.studioNewVolumeTitleInput?.value || "").trim();
  if (!title) {
    showToast("권 제목을 입력해 주세요.", true);
    return;
  }
  const volumeIndex = parseInt(el.studioNewVolumeIndexInput?.value || "1", 10) || 1;

  try {
    const response = await fetch(`/studio/series/${encodeURIComponent(series.slug)}/volumes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, volume_index: volumeIndex }),
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(payload?.detail || `HTTP ${response.status}`);
    }
    if (el.studioNewVolumeTitleInput) el.studioNewVolumeTitleInput.value = "";
    await openStudioSeries(series.slug);
  } catch (error) {
    showToast(error.message || "Failed to add volume", true);
  }
}

function studioBubbleHtml(role, text) {
  const side = role === "user" ? "right" : "left";
  return `
    <div class="chat-row chat-row-${side}">
      <div class="chat-bubble chat-bubble-${side}">${escapeHtml(text)}</div>
    </div>
  `;
}

function renderStudioChat() {
  if (!el.studioChatScroll) return;
  el.studioChatScroll.innerHTML = state.studioSession.messages
    .map((message) => studioBubbleHtml(message.role, message.content))
    .join("");
  el.studioChatScroll.scrollTop = el.studioChatScroll.scrollHeight;
}

async function submitStudioMessage() {
  const slug = state.studioSession.slug;
  if (!slug) {
    showToast("먼저 프로젝트를 선택해 주세요.", true);
    return;
  }
  const message = (el.studioMessageInput?.value || "").trim();
  if (!message) {
    showToast("메시지를 입력해 주세요.", true);
    return;
  }

  state.studioSession.messages.push({ role: "user", content: message });
  renderStudioChat();
  if (el.studioMessageInput) el.studioMessageInput.value = "";
  if (el.studioSendBtn) el.studioSendBtn.disabled = true;

  el.studioChatScroll.insertAdjacentHTML("beforeend", studioBubbleHtml("assistant", ""));
  const bubble = el.studioChatScroll.querySelector(".chat-row:last-child .chat-bubble");

  try {
    const config = getRunConfig();
    const response = await fetch(`/studio/projects/${encodeURIComponent(slug)}/messages/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        provider: config.provider,
        model: config.model,
        api_key: config.apiKey,
        language: config.language,
      }),
    });

    if (!response.ok || !response.body) {
      const payload = await response.json().catch(() => null);
      throw new Error(payload?.detail || `HTTP ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let streamed = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      streamed += decoder.decode(value, { stream: true });
      if (bubble) bubble.textContent = streamed;
      el.studioChatScroll.scrollTop = el.studioChatScroll.scrollHeight;
    }
    streamed += decoder.decode();

    state.studioSession.messages.push({ role: "assistant", content: streamed });
  } catch (error) {
    if (bubble) bubble.textContent = error.message || "Error";
    showToast(error.message || "Failed to send message", true);
  } finally {
    if (el.studioSendBtn) el.studioSendBtn.disabled = false;
  }
}

function openStudioFinalizeForm() {
  if (!state.studioSession.slug) {
    showToast("먼저 프로젝트를 선택해 주세요.", true);
    return;
  }
  const lastAssistant = [...state.studioSession.messages].reverse().find((m) => m.role === "assistant");
  if (el.studioFinalizeIndexInput) {
    el.studioFinalizeIndexInput.value = String((state.studioSession.chapterCount || 0) + 1);
  }
  if (el.studioFinalizeContentInput) {
    el.studioFinalizeContentInput.value = lastAssistant?.content || "";
  }
  el.studioFinalizeForm?.classList.remove("hidden");
}

function closeStudioFinalizeForm() {
  el.studioFinalizeForm?.classList.add("hidden");
}

async function saveStudioFinalizeForm() {
  const slug = state.studioSession.slug;
  if (!slug) return;

  const chapterIndex = parseInt(el.studioFinalizeIndexInput?.value || "1", 10) || 1;
  const chapterTitle = (el.studioFinalizeTitleInput?.value || "").trim();
  const content = (el.studioFinalizeContentInput?.value || "").trim();
  if (!chapterTitle || !content) {
    showToast("챕터 제목과 내용을 입력해 주세요.", true);
    return;
  }

  try {
    const response = await fetch(`/studio/projects/${encodeURIComponent(slug)}/chapters/finalize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chapter_index: chapterIndex, chapter_title: chapterTitle, content }),
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(payload?.detail || `HTTP ${response.status}`);
    }
    const result = await response.json();
    state.studioSession.chapterCount = result.chapter_count;
    if (el.studioFinalizeTitleInput) el.studioFinalizeTitleInput.value = "";
    closeStudioFinalizeForm();
    showToast(`${result.chapter_index}장 "${result.chapter_title}" 저장 완료`);
  } catch (error) {
    showToast(error.message || "Failed to finalize chapter", true);
  }
}

function bibleEndpointBase(containerType, slug) {
  return containerType === "series"
    ? `/studio/series/${encodeURIComponent(slug)}`
    : `/studio/projects/${encodeURIComponent(slug)}`;
}

function joinBibleCharactersText(characters) {
  return (characters || []).map((character) => character.markdown || `## ${character.name}`).join("\n\n");
}

function parseBibleCharactersText(text) {
  const blocks = (text || "")
    .split(/\n(?=##\s)/)
    .map((block) => block.trim())
    .filter(Boolean);
  return blocks.map((block) => {
    const firstLine = block.split("\n")[0] || "";
    const name = firstLine.replace(/^##\s*/, "").trim() || "이름없음";
    return { name, markdown: block };
  });
}

async function openStudioBible(containerType, slug, containerLabel) {
  if (!slug) return;
  try {
    const response = await fetch(`${bibleEndpointBase(containerType, slug)}/bible`);
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(payload?.detail || `HTTP ${response.status}`);
    }
    const bible = await response.json();
    state.studioBible = {
      slug,
      containerType,
      containerLabel,
      messages: bible.messages || [],
    };
    if (el.studioBibleSettingInput) el.studioBibleSettingInput.value = bible.setting_markdown || "";
    if (el.studioBibleCharactersInput) {
      el.studioBibleCharactersInput.value = joinBibleCharactersText(bible.characters);
    }
    showStudioPanel("bible");
    renderStudioBibleChat();
  } catch (error) {
    showToast(error.message || "Failed to open setting bible", true);
  }
}

function closeStudioBible() {
  if (state.studioSeries) {
    showStudioPanel("series");
  } else if (state.studioSession.slug) {
    showStudioPanel("chat");
  } else {
    showStudioPanel("empty");
  }
}

function renderStudioBibleChat() {
  if (!el.studioBibleChatScroll) return;
  el.studioBibleChatScroll.innerHTML = state.studioBible.messages
    .map((message) => studioBubbleHtml(message.role, message.content))
    .join("");
  el.studioBibleChatScroll.scrollTop = el.studioBibleChatScroll.scrollHeight;
}

async function submitStudioBibleMessage() {
  const { slug, containerType } = state.studioBible;
  if (!slug) {
    showToast("먼저 설정집을 열어 주세요.", true);
    return;
  }
  const message = (el.studioBibleMessageInput?.value || "").trim();
  if (!message) {
    showToast("메시지를 입력해 주세요.", true);
    return;
  }

  state.studioBible.messages.push({ role: "user", content: message });
  renderStudioBibleChat();
  if (el.studioBibleMessageInput) el.studioBibleMessageInput.value = "";
  if (el.studioBibleSendBtn) el.studioBibleSendBtn.disabled = true;

  el.studioBibleChatScroll.insertAdjacentHTML("beforeend", studioBubbleHtml("assistant", ""));
  const bubble = el.studioBibleChatScroll.querySelector(".chat-row:last-child .chat-bubble");

  try {
    const config = getRunConfig();
    const response = await fetch(`${bibleEndpointBase(containerType, slug)}/bible/messages/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        provider: config.provider,
        model: config.model,
        api_key: config.apiKey,
        language: config.language,
      }),
    });

    if (!response.ok || !response.body) {
      const payload = await response.json().catch(() => null);
      throw new Error(payload?.detail || `HTTP ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let streamed = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      streamed += decoder.decode(value, { stream: true });
      if (bubble) bubble.textContent = streamed;
      el.studioBibleChatScroll.scrollTop = el.studioBibleChatScroll.scrollHeight;
    }
    streamed += decoder.decode();

    state.studioBible.messages.push({ role: "assistant", content: streamed });
  } catch (error) {
    if (bubble) bubble.textContent = error.message || "Error";
    showToast(error.message || "Failed to send message", true);
  } finally {
    if (el.studioBibleSendBtn) el.studioBibleSendBtn.disabled = false;
  }
}

async function saveStudioBible() {
  const { slug, containerType } = state.studioBible;
  if (!slug) {
    showToast("먼저 설정집을 열어 주세요.", true);
    return;
  }
  const settingMarkdown = el.studioBibleSettingInput?.value || "";
  const characters = parseBibleCharactersText(el.studioBibleCharactersInput?.value || "");

  try {
    const response = await fetch(`${bibleEndpointBase(containerType, slug)}/bible/finalize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ setting_markdown: settingMarkdown, characters }),
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(payload?.detail || `HTTP ${response.status}`);
    }
    showToast("설정집 저장 완료");
  } catch (error) {
    showToast(error.message || "Failed to save setting bible", true);
  }
}

function bindEvents() {
  el.studioCreateBtn?.addEventListener("click", () => void createStudioProjectOrSeries());
  el.studioSendBtn?.addEventListener("click", () => void submitStudioMessage());
  el.studioFinalizeBtn?.addEventListener("click", () => openStudioFinalizeForm());
  el.studioFinalizeCancelBtn?.addEventListener("click", () => closeStudioFinalizeForm());
  el.studioFinalizeSaveBtn?.addEventListener("click", () => void saveStudioFinalizeForm());
  el.studioBookBibleBtn?.addEventListener("click", () => {
    if (state.studioSession.slug) {
      void openStudioBible("book", state.studioSession.slug, state.studioSession.bookTitle || "");
    }
  });
  el.studioSeriesBibleBtn?.addEventListener("click", () => {
    if (state.studioSeries?.slug) {
      void openStudioBible("series", state.studioSeries.slug, state.studioSeries.series_title || "");
    }
  });
  el.studioBibleBackBtn?.addEventListener("click", () => closeStudioBible());
  el.studioBibleSendBtn?.addEventListener("click", () => void submitStudioBibleMessage());
  el.studioBibleSaveBtn?.addEventListener("click", () => void saveStudioBible());
  el.studioAddVolumeBtn?.addEventListener("click", () => void addStudioVolume());
}

async function init() {
  loadSettings();
  bindEvents();
  await loadStudioProjects();
}

void init();
