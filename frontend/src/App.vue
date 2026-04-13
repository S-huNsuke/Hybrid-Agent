<template>
  <AppShell :sidebar-collapsed="false" :sidebar-width="236" :sidebar-collapsed-width="88">
    <template #header>
      <AppHeader
        :title="pageTitle"
        :subtitle="pageEyebrow"
        :user-name="profileName"
        :group-name="groupName"
      >
        <template #actions>
          <label v-if="isAuthenticated && availableGroups.length" class="group-switcher">
            <span>当前组</span>
            <select :value="activeGroupId" @change="handleGroupChange">
              <option
                v-for="groupId in availableGroups"
                :key="groupId"
                :value="groupId"
              >
                {{ groupId }}
              </option>
            </select>
          </label>
          <el-tag class="app-tag" type="info" effect="plain">工作台</el-tag>
          <el-tag
            class="app-tag"
            v-if="isAuthenticated"
            type="success"
            effect="plain"
          >
            在线
          </el-tag>
          <el-tag class="app-tag" v-else type="warning" effect="plain">访客</el-tag>
          <button class="ghost-button" type="button" @click="toggleTheme">
            {{ isDark ? "暗色" : "亮色" }}
          </button>
          <button
            v-if="isAuthenticated"
            class="primary-button"
            type="button"
            @click="handleLogout"
          >
            退出
          </button>
          <RouterLink
            v-else
            class="primary-button"
            :to="{ name: 'login', query: { redirect: route.fullPath } }"
          >
            登录
          </RouterLink>
        </template>
      </AppHeader>
    </template>

    <template #sidebar>
      <AppSidebar
        :items="navItems"
        :active-key="activeKey"
        :collapsed="false"
        @select="handleNavSelect"
      >
        <template #brand>
          <div class="brand-slot">
            <div class="brand-mark">HA</div>
            <div class="brand-copy">
              <strong>Hybrid-Agent</strong>
              <span>工作台</span>
            </div>
          </div>
        </template>
        <template #icon-overview>⌂</template>
        <template #icon-login>⇢</template>
        <template #icon-chat>✦</template>
        <template #icon-documents>▤</template>
        <template #icon-admin>⚙</template>
        <template #icon-settings>◌</template>
        <template #footer>
          <div class="sidebar-footer">
            <span class="sidebar-dot" :class="{ active: isAuthenticated }"></span>
          </div>
        </template>
      </AppSidebar>
    </template>

    <section class="main-panel">
      <RouterView />
    </section>
  </AppShell>
</template>

<script setup>
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";

import AppHeader from "./components/AppHeader.vue";
import AppShell from "./components/AppShell.vue";
import AppSidebar from "./components/AppSidebar.vue";
import { useTheme } from "./composables/useTheme";
import { useUserStore } from "./stores/user";

const { isDark, toggleTheme } = useTheme();
const userStore = useUserStore();
const route = useRoute();
const router = useRouter();

const isAuthenticated = computed(() => userStore.isAuthenticated);
const canAccessAdmin = computed(() => userStore.canAccessAdmin);
const profileName = computed(
  () => userStore.profile?.username || userStore.profile?.email || "未登录",
);
const availableGroups = computed(() => userStore.availableGroupIds);
const activeGroupId = computed(() => userStore.activeGroupId);
const pageEyebrow = computed(() =>
  isAuthenticated.value ? "运营控制台" : "公开访问",
);
const groupName = computed(() => activeGroupId.value || "");

const baseNavItems = [
  { key: "overview", label: "概览", to: "/", public: false },
  { key: "login", label: "登录", to: "/login", public: true, hideWhenAuthed: true },
  { key: "chat", label: "聊天", to: "/chat", public: false },
  { key: "documents", label: "文档", to: "/documents", public: false },
  { key: "admin", label: "管理", to: "/admin", public: false },
  { key: "settings", label: "设置", to: "/settings", public: false },
];

const navItems = computed(() =>
  baseNavItems
    .filter((item) => !(item.key === "admin" && !canAccessAdmin.value))
    .filter((item) => !(item.hideWhenAuthed && isAuthenticated.value))
    .map((item) => ({
      ...item,
      locked: !isAuthenticated.value && !item.public,
    })),
);

const activeKey = computed(() => String(route.name || "overview"));

const pageTitle = computed(() => {
  switch (route.name) {
    case "overview":
      return "概览";
    case "login":
      return "登录";
    case "chat":
      return "聊天工作台";
    case "documents":
      return "文档中心";
    case "admin":
      return "组织管理";
    case "settings":
      return "设置";
    default:
      return "工作台";
  }
});

function resolveNavTo(item) {
  if (item.locked) {
    return { name: "login", query: { redirect: item.to } };
  }
  return item.to;
}

async function handleNavSelect(item) {
  await router.push(resolveNavTo(item));
}

function handleGroupChange(event) {
  const nextGroupId = event?.target?.value || "";
  userStore.setActiveGroupId(nextGroupId);
}

async function handleLogout() {
  await userStore.logout();
  if (route.name !== "login") {
    await router.push({ name: "login", query: { redirect: route.fullPath } });
  }
}
</script>

<style scoped>
.brand-slot {
  display: flex;
  align-items: center;
  gap: var(--space-12);
}

.brand-mark {
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  border-radius: 16px;
  background: var(--ha-accent-soft, var(--color-accent-soft));
  color: var(--ha-accent, var(--color-accent));
  font-weight: 700;
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--color-accent) 18%, transparent);
}

.brand-copy {
  display: grid;
  gap: 2px;
}

.brand-copy strong {
  font-size: var(--font-size-14);
  letter-spacing: 0.04em;
}

.brand-copy span {
  font-size: var(--font-size-12);
  color: var(--ha-muted, var(--color-muted));
}

.app-tag {
  border-radius: 999px;
}

.group-switcher {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid color-mix(in srgb, var(--color-border) 70%, transparent);
  background: color-mix(in srgb, var(--color-surface-strong) 82%, transparent);
  font-size: var(--font-size-12);
}

.group-switcher span {
  color: var(--ha-muted, var(--color-muted));
}

.group-switcher select {
  border: 0;
  background: transparent;
  color: var(--ha-text, var(--color-text));
  font: inherit;
  min-width: 92px;
}

.sidebar-meta {
  margin: 0;
  color: var(--ha-muted, var(--color-muted));
  font-size: var(--font-size-12);
}

.sidebar-footer {
  display: flex;
  justify-content: center;
  width: 100%;
}

.sidebar-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--color-border) 90%, transparent);
  box-shadow: 0 0 0 6px color-mix(in srgb, var(--color-surface) 80%, transparent);
}

.sidebar-dot.active {
  background: var(--color-accent);
}

.ghost-button,
.primary-button {
  appearance: none;
  border: 1px solid transparent;
  border-radius: 999px;
  padding: 7px 14px;
  font-size: var(--font-size-14);
  cursor: pointer;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.ghost-button {
  background: color-mix(in srgb, var(--color-surface) 70%, transparent);
  color: var(--ha-text, var(--color-text));
  border-color: color-mix(in srgb, var(--ha-border, var(--color-border)) 70%, transparent);
}

.primary-button {
  background: var(--ha-accent, var(--color-accent));
  color: #fff;
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.12);
}

.ghost-button:hover,
.primary-button:hover {
  transform: translateY(-1px);
}

.main-panel {
  min-height: calc(100vh - 104px);
  border-radius: 28px;
  padding: var(--space-20);
  background:
    radial-gradient(circle at top right, color-mix(in srgb, var(--color-accent-soft) 62%, transparent), transparent 34%),
    color-mix(in srgb, var(--color-surface) 94%, transparent);
  border: 1px solid color-mix(in srgb, var(--color-border) 70%, transparent);
  box-shadow: var(--shadow-soft);
  backdrop-filter: blur(14px);
}

@media (max-width: 980px) {
  .brand-copy {
    display: none;
  }

  .main-panel {
    min-height: auto;
    padding: var(--space-20);
  }
}
</style>
