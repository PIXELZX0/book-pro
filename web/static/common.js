const PROVIDERS = [
  "open-ai",
  "anthropic",
  "openrouter",
  "venice",
  "kilo-code",
  "opencode-go",
  "opencode-zen",
];

const PROVIDER_LABEL = {
  "open-ai": "OPEN-AI",
  anthropic: "ANTHROPIC",
  openrouter: "OpenRouter",
  venice: "Venice",
  "kilo-code": "Kilo Code",
  "opencode-go": "OpenCode Go",
  "opencode-zen": "OpenCode Zen",
};

const DEFAULT_MODEL_BY_PROVIDER = {
  "open-ai": "gpt-4.1-mini",
  anthropic: "claude-sonnet-4-20250514",
  openrouter: "openai/gpt-4.1-mini",
  venice: "venice-uncensored",
  "kilo-code": "anthropic/claude-sonnet-4.5",
  "opencode-go": "claude-sonnet-4-5",
  "opencode-zen": "grok-4.6",
};

const MODEL_OPTIONS_BY_PROVIDER = {
  "open-ai": ["gpt-4.1", "gpt-4.1-mini", "gpt-4o", "gpt-4o-mini"],
  anthropic: ["claude-sonnet-4-20250514", "claude-3-7-sonnet-latest", "claude-3-5-sonnet-latest"],
  openrouter: ["openai/gpt-4.1-mini", "openai/gpt-4.1", "anthropic/claude-sonnet-4", "google/gemini-2.5-pro"],
  venice: ["venice-uncensored", "llama-3.3-70b", "qwen2.5-72b-instruct"],
  "kilo-code": ["anthropic/claude-sonnet-4.5", "openai/gpt-4.1-mini", "google/gemini-2.5-pro"],
  "opencode-go": ["claude-sonnet-4-5", "gpt-5", "grok-4"],
  "opencode-zen": [
    "grok-4.6",
    "grok-4.5",
    "claude-sonnet-4-5",
    "gpt-5.4-mini",
    "gemini-3-flash",
    "deepseek-v4-flash",
    "glm-5.2",
    "kimi-k3",
  ],
};

const CUSTOM_MODEL_VALUE = "__custom__";
const STORAGE_KEY = "book-pro-panel-settings";
const UI_LANGUAGES = ["ko", "en", "ja"];

const I18N_MESSAGES = { ko: {}, en: {}, ja: {} };

function registerI18nMessages(tables) {
  Object.keys(tables || {}).forEach((lang) => {
    I18N_MESSAGES[lang] = { ...(I18N_MESSAGES[lang] || {}), ...tables[lang] };
  });
}

function normalizeUiLanguage(value) {
  return UI_LANGUAGES.includes(value) ? value : "ko";
}

let currentUiLanguage = "ko";

function setUiLanguage(value) {
  currentUiLanguage = normalizeUiLanguage(value || "ko");
}

function t(key, params = {}) {
  const table = I18N_MESSAGES[currentUiLanguage] || I18N_MESSAGES.ko;
  const fallback = I18N_MESSAGES.ko[key] || key;
  const template = table[key] || fallback;
  return template.replace(/\{(\w+)\}/g, (_, name) => String(params[name] ?? ""));
}

function applyI18nToDom(lang) {
  if (lang !== undefined) setUiLanguage(lang);
  document.documentElement.lang = currentUiLanguage;

  document.querySelectorAll("[data-i18n]").forEach((node) => {
    const key = node.getAttribute("data-i18n");
    if (!key) return;
    node.textContent = t(key);
  });

  document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
    const key = node.getAttribute("data-i18n-placeholder");
    if (!key) return;
    node.setAttribute("placeholder", t(key));
  });

  document.querySelectorAll("[data-i18n-title]").forEach((node) => {
    const key = node.getAttribute("data-i18n-title");
    if (!key) return;
    node.setAttribute("title", t(key));
  });
}

function escapeHtml(text) {
  return (text || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function showToast(message, isError = false) {
  const toast = document.getElementById("toast");
  if (!toast) return;
  toast.textContent = message;
  toast.style.background = isError ? "#6b1010" : "#000000";
  toast.classList.add("show");
  window.clearTimeout(showToast._timer);
  showToast._timer = window.setTimeout(() => {
    toast.classList.remove("show");
  }, 2200);
}

function readSharedSettings() {
  const defaults = {
    selectedProvider: "open-ai",
    language: "ko",
    uiLanguage: "ko",
    models: { ...DEFAULT_MODEL_BY_PROVIDER },
    apiKeys: {
      "open-ai": "",
      anthropic: "",
      openrouter: "",
      venice: "",
      "kilo-code": "",
      "opencode-go": "",
      "opencode-zen": "",
    },
  };
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return defaults;
    const parsed = JSON.parse(raw);
    if (typeof parsed.selectedProvider === "string" && parsed.selectedProvider.trim()) {
      defaults.selectedProvider = parsed.selectedProvider.trim();
    }
    if (typeof parsed.language === "string" && parsed.language.trim()) {
      defaults.language = parsed.language.trim();
    }
    if (typeof parsed.uiLanguage === "string" && parsed.uiLanguage.trim()) {
      defaults.uiLanguage = parsed.uiLanguage.trim();
    }
    PROVIDERS.forEach((provider) => {
      const model = parsed.models?.[provider];
      if (typeof model === "string" && model.trim()) defaults.models[provider] = model.trim();
      const apiKey = parsed.apiKeys?.[provider];
      if (typeof apiKey === "string") defaults.apiKeys[provider] = apiKey;
    });
    return defaults;
  } catch (_error) {
    return defaults;
  }
}

function writeSharedSettings(patch) {
  const merged = { ...readSharedSettings(), ...(patch || {}) };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(merged));
  return merged;
}

function getRunConfigFrom(settings) {
  const provider = settings.selectedProvider;
  return {
    provider,
    model: settings.models[provider] || DEFAULT_MODEL_BY_PROVIDER[provider] || "",
    apiKey: settings.apiKeys[provider] || "",
    language: settings.language || "ko",
  };
}
