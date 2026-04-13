<template>
  <nav class="app-sidebar" :class="{ 'is-collapsed': collapsed }">
    <div class="app-sidebar__brand">
      <slot name="brand">
        <div class="app-sidebar__logo">HA</div>
        <div v-if="!collapsed" class="app-sidebar__name">Hybrid Agent</div>
      </slot>
    </div>
    <div class="app-sidebar__items">
      <button
        v-for="item in items"
        :key="item.key"
        type="button"
        class="app-sidebar__item"
        :class="{ 'is-active': item.key === activeKey }"
        @click="$emit('select', item)"
      >
        <span class="app-sidebar__icon">
          <slot :name="`icon-${item.key}`">{{ item.icon || item.label.slice(0, 1) }}</slot>
        </span>
        <span v-if="!collapsed" class="app-sidebar__label">{{ item.label }}</span>
      </button>
    </div>
    <div class="app-sidebar__footer">
      <slot name="footer" />
    </div>
  </nav>
</template>

<script setup>
defineProps({
  items: {
    type: Array,
    default: () => [],
  },
  activeKey: {
    type: String,
    default: "",
  },
  collapsed: {
    type: Boolean,
    default: false,
  },
});

defineEmits(["select"]);
</script>

<style scoped>
.app-sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: var(--space-12);
  gap: var(--space-16);
  color: var(--color-text);
  border-radius: 28px;
  background: color-mix(in srgb, var(--color-surface-strong) 82%, transparent);
  box-shadow: var(--shadow-soft);
}

.app-sidebar__brand {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: var(--space-12);
  font-weight: var(--font-weight-semibold);
  letter-spacing: var(--letter-spacing-wide);
  padding: var(--space-10) var(--space-10) var(--space-16);
  border-bottom: 1px solid color-mix(in srgb, var(--color-border) 60%, transparent);
}

.app-sidebar__logo {
  width: 40px;
  height: 40px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: var(--color-accent-soft);
  color: var(--color-accent);
  font-size: var(--font-size-14);
  font-weight: var(--font-weight-semibold);
}

.app-sidebar__name {
  font-size: var(--font-size-14);
}

.app-sidebar__items {
  display: flex;
  flex-direction: column;
  gap: var(--space-8);
}

.app-sidebar__item {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: var(--space-12);
  min-height: 48px;
  padding: 10px 12px;
  border-radius: 18px;
  border: 1px solid color-mix(in srgb, var(--color-border) 35%, transparent);
  background: color-mix(in srgb, var(--color-surface) 64%, transparent);
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease, color 0.18s ease;
}

.app-sidebar__item:hover {
  transform: translateX(2px);
  background: color-mix(in srgb, var(--color-surface-muted) 86%, transparent);
  border-color: color-mix(in srgb, var(--color-accent) 26%, transparent);
}

.app-sidebar__item.is-active {
  background: linear-gradient(135deg, color-mix(in srgb, var(--color-accent-soft) 92%, white 8%), color-mix(in srgb, var(--color-accent-soft) 78%, transparent));
  border-color: color-mix(in srgb, var(--color-accent) 80%, transparent);
  color: var(--color-accent);
  font-weight: var(--font-weight-semibold);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--color-accent) 14%, transparent);
}

.app-sidebar__icon {
  width: 32px;
  height: 32px;
  flex: 0 0 32px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  font-size: var(--font-size-12);
  background: color-mix(in srgb, var(--color-surface) 86%, transparent);
  border: 1px solid color-mix(in srgb, var(--color-border) 70%, transparent);
}

.app-sidebar__label {
  font-size: var(--font-size-14);
  line-height: 1.1;
}

.app-sidebar__footer {
  margin-top: auto;
  display: flex;
  justify-content: flex-start;
  padding: var(--space-12) var(--space-10) var(--space-4);
  border-top: 1px solid color-mix(in srgb, var(--color-border) 60%, transparent);
}

.app-sidebar.is-collapsed {
  padding: var(--space-16) var(--space-8);
}

.app-sidebar.is-collapsed .app-sidebar__name {
  display: none;
}
</style>
