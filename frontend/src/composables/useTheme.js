import { computed, ref, watch } from "vue";

const STORAGE_KEY = "hybrid-agent-theme";
const systemTheme =
  typeof window !== "undefined" &&
  window.matchMedia &&
  window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
const theme = ref(localStorage.getItem(STORAGE_KEY) || systemTheme);

const TOKENS = {
  light: {
    "--ha-bg": "#f6f7fb",
    "--ha-surface": "#ffffff",
    "--ha-surface-2": "#f0f2f6",
    "--ha-text": "#101318",
    "--ha-muted": "#5f6b7a",
    "--ha-border": "#d9dee7",
    "--ha-accent": "#2f6bff",
    "--ha-accent-2": "#16a34a",
    "--el-color-primary": "#2f6bff",
    "--el-color-success": "#16a34a",
    "--el-color-info": "#64748b",
    "--el-text-color-primary": "#101318",
    "--el-text-color-regular": "#2b3340",
    "--el-bg-color": "#ffffff",
    "--el-border-color": "#d9dee7",
  },
  dark: {
    "--ha-bg": "#0f141a",
    "--ha-surface": "#151b23",
    "--ha-surface-2": "#1b2430",
    "--ha-text": "#f2f4f8",
    "--ha-muted": "#9aa4b2",
    "--ha-border": "#2b3646",
    "--ha-accent": "#5c8dff",
    "--ha-accent-2": "#3ddc84",
    "--el-color-primary": "#5c8dff",
    "--el-color-success": "#3ddc84",
    "--el-color-info": "#94a3b8",
    "--el-text-color-primary": "#f2f4f8",
    "--el-text-color-regular": "#cbd5e1",
    "--el-bg-color": "#151b23",
    "--el-border-color": "#2b3646",
  },
};

function applyTheme(value) {
  const root = document.documentElement;
  root.dataset.theme = value;
  const app = document.getElementById("app");
  if (app) {
    app.dataset.theme = value;
  }
  const vars = TOKENS[value] || TOKENS.light;
  Object.entries(vars).forEach(([key, val]) => {
    root.style.setProperty(key, val);
  });
  localStorage.setItem(STORAGE_KEY, value);
}

watch(theme, applyTheme, { immediate: true });

export function useTheme() {
  const isDark = computed(() => theme.value === "dark");

  function toggleTheme() {
    theme.value = isDark.value ? "light" : "dark";
  }

  return {
    theme,
    isDark,
    toggleTheme,
  };
}
