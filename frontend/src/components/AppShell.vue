<template>
  <div class="app-shell" :style="shellStyle">
    <header class="app-shell__header">
      <slot name="header" />
    </header>
    <aside class="app-shell__sidebar">
      <slot name="sidebar" />
    </aside>
    <main class="app-shell__main">
      <slot />
    </main>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  sidebarCollapsed: { type: Boolean, default: false },
  sidebarWidth: { type: Number, default: 260 },
  sidebarCollapsedWidth: { type: Number, default: 72 },
});

const shellStyle = computed(() => {
  const width = props.sidebarCollapsed ? props.sidebarCollapsedWidth : props.sidebarWidth;
  return {
    "--app-sidebar-width": `${width}px`,
  };
});
</script>

<style scoped>
.app-shell {
  display: grid;
  grid-template-columns: var(--app-sidebar-width) 1fr;
  grid-template-rows: 76px 1fr;
  grid-template-areas:
    "sidebar header"
    "sidebar main";
  min-height: 100vh;
  background:
    radial-gradient(circle at top left, color-mix(in srgb, var(--color-accent-soft) 60%, transparent), transparent 24%),
    radial-gradient(circle at bottom right, rgba(255, 255, 255, 0.35), transparent 22%),
    linear-gradient(180deg, color-mix(in srgb, var(--color-bg) 92%, #ffffff 8%) 0%, var(--color-bg) 100%);
  color: var(--color-text);
}

.app-shell__header {
  grid-area: header;
  position: sticky;
  top: 0;
  z-index: 8;
  background: color-mix(in srgb, var(--color-surface) 90%, transparent);
  border-bottom: 1px solid color-mix(in srgb, var(--color-border) 65%, transparent);
  backdrop-filter: blur(18px);
}

.app-shell__sidebar {
  grid-area: sidebar;
  position: sticky;
  top: 0;
  height: 100vh;
  padding: var(--space-14);
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--color-surface-strong) 96%, transparent), color-mix(in srgb, var(--color-surface) 92%, transparent));
  border-right: 1px solid color-mix(in srgb, var(--color-border) 70%, transparent);
  backdrop-filter: blur(18px);
}

.app-shell__main {
  grid-area: main;
  padding: var(--space-24);
  background: transparent;
}

@media (max-width: 900px) {
  .app-shell {
    grid-template-columns: 1fr;
    grid-template-rows: 76px auto;
    grid-template-areas:
      "header"
      "main";
  }

  .app-shell__sidebar {
    display: none;
  }
}
</style>
