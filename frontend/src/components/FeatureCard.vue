<template>
  <article class="feature-card" :class="cardClass">
    <header class="feature-head">
      <p class="feature-label">{{ label }}</p>
      <p v-if="meta" class="feature-meta">{{ meta }}</p>
    </header>
    <h3>{{ title }}</h3>
    <p v-if="description" class="feature-desc">{{ description }}</p>
    <div v-else-if="$slots.body" class="feature-desc">
      <slot name="body" />
    </div>
    <footer v-if="$slots.footer" class="feature-footer">
      <slot name="footer" />
    </footer>
  </article>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  label: {
    type: String,
    required: true,
  },
  title: {
    type: String,
    required: true,
  },
  description: {
    type: String,
    default: "",
  },
  meta: {
    type: String,
    default: "",
  },
  tone: {
    type: String,
    default: "default",
  },
  compact: {
    type: Boolean,
    default: false,
  },
});

const cardClass = computed(() => ({
  "is-compact": props.compact,
  [`tone-${props.tone}`]: true,
}));
</script>

<style scoped>
.feature-card {
  display: grid;
  gap: var(--space-12);
  min-height: 100%;
}

.feature-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-8);
}

.feature-meta {
  font-size: var(--font-size-12);
  color: var(--muted);
}

.feature-desc {
  color: var(--text);
  line-height: 1.65;
}

.feature-footer {
  margin-top: var(--space-12);
  font-size: var(--font-size-12);
  color: var(--muted);
}

.is-compact {
  padding: var(--space-16);
}

.tone-default {
  border-color: var(--line);
}

.tone-accent {
  border-color: color-mix(in srgb, var(--accent) 45%, transparent);
}

.tone-warn {
  border-color: rgba(209, 67, 67, 0.35);
}

.tone-success {
  border-color: rgba(24, 176, 110, 0.4);
}
</style>
