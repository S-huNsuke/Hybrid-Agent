<template>
  <div class="app-header">
    <div class="app-header__left">
      <button
        v-if="showMenuButton"
        class="app-header__menu"
        type="button"
        aria-label="Toggle sidebar"
        @click="$emit('toggle-sidebar')"
      >
        <span class="app-header__menu-bar" />
        <span class="app-header__menu-bar" />
        <span class="app-header__menu-bar" />
      </button>
      <div class="app-header__title">
        <div class="app-header__title-text">{{ title }}</div>
        <div v-if="subtitle" class="app-header__subtitle">{{ subtitle }}</div>
      </div>
    </div>
    <div class="app-header__right">
      <div v-if="groupName" class="app-header__pill">{{ groupName }}</div>
      <div v-if="userName" class="app-header__user">{{ userName }}</div>
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, default: "Hybrid Agent" },
  subtitle: { type: String, default: "" },
  userName: { type: String, default: "" },
  groupName: { type: String, default: "" },
  showMenuButton: { type: Boolean, default: false },
});

defineEmits(["toggle-sidebar"]);
</script>

<style scoped>
.app-header {
  min-height: 76px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-16);
  padding: 12px var(--space-24);
  background: transparent;
}

.app-header__left {
  display: flex;
  align-items: center;
  gap: var(--space-16);
  min-width: 0;
}

.app-header__menu {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  border: 1px solid var(--color-border);
  background: var(--color-surface-strong);
  display: inline-flex;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
  padding: 10px;
  cursor: pointer;
}

.app-header__menu-bar {
  display: block;
  height: 2px;
  width: 100%;
  background: var(--color-text);
  opacity: 0.8;
}

.app-header__title-text {
  font-size: var(--font-size-20);
  font-weight: var(--font-weight-semibold);
  letter-spacing: 0.04em;
}

.app-header__subtitle {
  font-size: var(--font-size-12);
  color: var(--color-muted);
  margin-top: 4px;
}

.app-header__right {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-10);
  flex-wrap: wrap;
}

.app-header__pill {
  padding: 7px 12px;
  border-radius: 999px;
  background: var(--color-accent-soft);
  color: var(--color-accent);
  font-size: var(--font-size-12);
  font-weight: var(--font-weight-semibold);
  line-height: 1;
}

.app-header__user {
  font-size: var(--font-size-12);
  color: var(--color-text);
  padding: 7px 12px;
  border-radius: 999px;
  border: 1px solid color-mix(in srgb, var(--color-border) 70%, transparent);
  background: color-mix(in srgb, var(--color-surface-strong) 80%, transparent);
  line-height: 1;
}
@media (max-width: 900px) {
  .app-header {
    padding: 12px var(--space-16);
  }

  .app-header__title-text {
    font-size: var(--font-size-16);
  }

  .app-header__right {
    gap: var(--space-8);
  }
}
</style>
