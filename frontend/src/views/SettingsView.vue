<template>
  <div class="view-stack settings-view">
    <header class="page-header">
      <div>
        <p class="section-kicker">设置工作台</p>
        <h3>个人设置</h3>
        <p>管理主题偏好、账号信息与模型提供商。</p>
      </div>
      <div class="page-actions">
        <button class="ghost-button" type="button" @click="refreshAll" :disabled="loading">
          {{ loading ? "刷新中..." : "刷新数据" }}
        </button>
      </div>
    </header>

    <section class="card-grid">
      <FeatureCard
        label="主题"
        title="界面主题"
        :description="isDark ? '当前为暗色主题' : '当前为亮色主题'"
        meta="可随时切换"
        compact
      />
      <FeatureCard
        label="账号"
        title="账号状态"
        :description="profile ? `已登录：${profile.username}` : '未获取到用户信息'"
        :meta="profile ? '已同步' : '需重新登录'"
        compact
      />
      <FeatureCard
        label="模型"
        title="提供商配置"
        :description="`${providers.length} 条配置`"
        :meta="activeProviders ? `${activeProviders} 可用` : '尚未启用'"
        compact
      />
    </section>

    <section class="panel">
      <div class="panel-header">
        <div>
          <p class="section-kicker">主题</p>
          <h4>主题偏好</h4>
        </div>
        <p class="panel-meta">当前主题：{{ isDark ? "暗色" : "亮色" }}</p>
      </div>
      <div class="theme-toggle">
        <div>
          <h5>{{ isDark ? "暗色模式" : "亮色模式" }}</h5>
          <p class="muted">切换会立即应用到全局界面。</p>
        </div>
        <button class="primary-button" type="button" @click="toggleTheme">
          切换到{{ isDark ? "亮色" : "暗色" }}
        </button>
      </div>
    </section>

    <section class="panel">
      <div class="panel-header">
        <div>
          <p class="section-kicker">账号</p>
          <h4>当前用户</h4>
        </div>
        <p class="panel-meta">来自 /api/v1/auth/me</p>
      </div>
      <div v-if="profile" class="profile-grid">
        <div class="profile-item">
          <span class="field-label">用户名</span>
          <strong>{{ profile.username }}</strong>
        </div>
        <div class="profile-item">
          <span class="field-label">用户 ID</span>
          <strong>{{ profile.id }}</strong>
        </div>
        <div class="profile-item">
          <span class="field-label">邮箱</span>
          <strong>{{ profile.email || "未设置" }}</strong>
        </div>
        <div class="profile-item">
          <span class="field-label">加入的组</span>
          <strong>{{ profile.group_ids?.length ? profile.group_ids.join(", ") : "暂无" }}</strong>
        </div>
      </div>
      <div v-else class="empty-state">
        <h4>无法获取用户信息</h4>
        <p>请检查登录状态，或重新登录后再刷新。</p>
      </div>
    </section>

    <section class="panel">
      <div class="panel-header">
        <div>
          <p class="section-kicker">提供商</p>
          <h4>模型提供商</h4>
        </div>
        <p class="panel-meta">
          {{ canManageProviders ? "/api/v1/providers" : "仅管理员可管理" }}
        </p>
      </div>
      <div class="provider-notice" :class="{ limited: providerAccessLevel !== 'manager' }">
        <strong>{{ providerAccessTitle }}</strong>
        <span>{{ providerAccessHint }}</span>
      </div>
      <p v-if="activeGroupId" class="panel-meta provider-scope-note">
        当前 Provider 作用域：{{ activeGroupId }}
      </p>
      <div v-if="!canManageProviders" class="empty-state readonly-provider-state">
        <h4>当前为只读视图</h4>
        <p>Provider 列表与操作按钮仅对 admin / group_admin 开放。</p>
      </div>
      <template v-else>
        <div v-if="providerLoading" class="empty-state">
          <h4>加载中...</h4>
          <p>正在同步提供商配置。</p>
        </div>
        <div v-else-if="!providers.length" class="empty-state">
          <h4>暂无配置</h4>
          <p>请在下方表单创建第一个提供商。</p>
        </div>
        <div v-else class="table provider-table">
          <div class="table-header">
            <span>名称</span>
            <span>类型</span>
            <span>模型</span>
            <span>状态</span>
            <span>操作</span>
          </div>
          <div v-for="provider in providers" :key="provider.id" class="table-row">
            <div>
              <div class="strong">{{ provider.display_name }}</div>
              <div class="muted">
                {{ provider.group_id ? `分组 ${provider.group_id}` : "全局" }}
              </div>
            </div>
            <div>
              <div class="strong">{{ provider.provider_type }}</div>
              <div class="muted">{{ provider.base_url || "默认地址" }}</div>
            </div>
            <div class="muted">
              {{ provider.models?.length ? provider.models.join(", ") : "未指定" }}
              <span v-if="provider.default_model" class="pill">
                默认：{{ provider.default_model }}
              </span>
            </div>
            <div>
              <span class="pill" :class="provider.is_active ? 'pill-active' : 'pill-muted'">
                {{ provider.is_active ? "启用" : "停用" }}
              </span>
              <span v-if="provider.has_api_key" class="muted">已配置密钥</span>
              <span v-else class="muted">未配置密钥</span>
              <div
                v-if="healthState[provider.id]?.checked"
                class="health-indicator"
              >
                <span
                  class="pill"
                  :class="healthStatusClass(healthState[provider.id]?.status)"
                >
                  {{ healthStatusLabel(healthState[provider.id]?.status) }}
                </span>
                <span class="muted health-text">
                  {{ healthState[provider.id]?.message || "检查完成" }}
                </span>
              </div>
            </div>
            <div class="provider-actions">
              <button
                class="ghost-button small"
                type="button"
                :disabled="checkingId === provider.id || !provider.has_api_key"
                @click="checkHealth(provider.id)"
              >
                {{ checkingId === provider.id ? "检查中..." : "健康检查" }}
              </button>
              <button
                v-if="canManageProviders"
                class="ghost-button small"
                type="button"
                :disabled="deletingId === provider.id"
                @click="removeProvider(provider.id)"
              >
                {{ deletingId === provider.id ? "删除中..." : "删除" }}
              </button>
            </div>
          </div>
        </div>
        <p v-if="providerError" class="error-text">{{ providerError }}</p>
      </template>
    </section>

    <section class="panel split-panel">
      <div v-if="canManageProviders" class="panel-block">
        <div class="panel-header">
          <div>
            <p class="section-kicker">新增提供商</p>
            <h4>新增提供商</h4>
          </div>
        </div>
        <form class="form-stack" @submit.prevent="submitProvider">
          <label class="field">
            <span class="field-label">显示名称</span>
            <input v-model.trim="form.display_name" type="text" placeholder="例如：OpenAI 主账号" />
          </label>
          <label class="field">
            <span class="field-label">提供商类型</span>
            <select v-model="form.provider_type">
              <option value="openai">openai</option>
              <option value="deepseek">deepseek</option>
              <option value="qwen">qwen</option>
              <option value="azure_openai">azure_openai</option>
              <option value="custom">custom</option>
            </select>
          </label>
          <label class="field">
            <span class="field-label">基础地址（可选）</span>
            <input v-model.trim="form.base_url" type="text" placeholder="https://api.openai.com" />
          </label>
          <label class="field">
            <span class="field-label">访问密钥（可选）</span>
            <input v-model.trim="form.api_key" type="password" placeholder="仅创建/更新时可提交" />
          </label>
          <label class="field">
            <span class="field-label">模型列表</span>
            <input
              v-model.trim="form.models"
              type="text"
              placeholder="gpt-4.1-mini, gpt-4.1"
            />
          </label>
          <label class="field">
            <span class="field-label">默认模型</span>
            <input v-model.trim="form.default_model" type="text" placeholder="gpt-4.1-mini" />
          </label>
          <label class="field">
            <span class="field-label">分组 ID（组管理员必填）</span>
            <input v-model.trim="form.group_id" type="text" placeholder="group-001" />
          </label>
          <label class="field checkbox-field">
            <input v-model="form.is_active" type="checkbox" />
            <span class="field-label">启用该提供商</span>
          </label>
          <button
            class="primary-button"
            type="submit"
            :disabled="creating || !form.display_name || !form.provider_type"
          >
            {{ creating ? "提交中..." : "创建提供商" }}
          </button>
          <p v-if="createError" class="error-text">{{ createError }}</p>
        </form>
      </div>
      <div class="panel-block help-block">
        <FeatureCard
          label="使用说明"
          title="使用说明"
          description="提供商访问密钥只在创建/更新时提交，读取时仅返回尾号提示；健康检查会探测 `/models` 接口。"
          tone="accent"
        />
        <FeatureCard
          label="权限说明"
          title="权限规则"
          description="管理员可管理全局或任意组，组管理员只能管理自身组的提供商。"
          tone="default"
        />
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";

import { checkProviderHealth } from "../api/auth";
import FeatureCard from "../components/FeatureCard.vue";
import { useTheme } from "../composables/useTheme";
import { useUserStore } from "../stores/user";

const { isDark, toggleTheme } = useTheme();
const userStore = useUserStore();

const creating = ref(false);
const createError = ref("");
const deletingId = ref("");
const checkingId = ref("");
const healthState = ref({});
const providers = computed(() => userStore.providers);
const providerLoading = computed(() => userStore.providerLoading);
const providerError = computed(() => userStore.providerError);
const loading = computed(() => providerLoading.value);

const form = ref({
  display_name: "",
  provider_type: "openai",
  base_url: "",
  api_key: "",
  models: "",
  default_model: "",
  group_id: "",
  is_active: true,
});

const profile = computed(() => userStore.profile);
const activeGroupId = computed(() => userStore.activeGroupId);
const activeProviders = computed(
  () => providers.value.filter((item) => item?.is_active).length,
);
const canManageProviders = computed(() => userStore.canManageProviders);
const providerAccessLevel = computed(() => userStore.providerAccessLevel);
const providerAccessHint = computed(() => userStore.providerAccessHint);
  const providerAccessTitle = computed(() => {
  if (providerAccessLevel.value === "manager") {
    return "管理模式";
  }
  if (providerAccessLevel.value === "readonly") {
    return "只读模式";
  }
  return "未登录状态";
});

function parseModels(value) {
  if (!value) {
    return [];
  }
  return value
    .split(/[,;\n]/g)
    .map((item) => item.trim())
    .filter(Boolean);
}

function resolveError(err, fallback) {
  const message = err?.response?.data?.detail || err?.message;
  if (message && typeof message === "string") {
    return message;
  }
  return fallback;
}

function healthStatusLabel(status) {
  const map = {
    healthy: "健康",
    missing_api_key: "缺少密钥",
    missing_base_url: "缺少地址",
    auth_error: "认证失败",
    http_error: "接口异常",
    network_error: "网络异常",
    unknown_error: "未知异常",
  };
  return map[String(status || "unknown_error")] || "未知异常";
}

function healthStatusClass(status) {
  if (status === "healthy") {
    return "health-ok-pill";
  }
  if (status === "missing_api_key" || status === "missing_base_url") {
    return "health-warn-pill";
  }
  return "health-failed-pill";
}

async function loadProviders() {
  try {
    await userStore.loadProviders(
      activeGroupId.value ? { group_id: activeGroupId.value } : {},
    );
  } catch {
    // surface error from store.providerError
  }
}

async function submitProvider() {
  creating.value = true;
  createError.value = "";
  try {
    const payload = {
      provider_type: form.value.provider_type,
      display_name: form.value.display_name,
      base_url: form.value.base_url || null,
      api_key: form.value.api_key || null,
      models: parseModels(form.value.models),
      default_model: form.value.default_model || null,
      group_id: form.value.group_id || activeGroupId.value || null,
      is_active: Boolean(form.value.is_active),
    };
    await userStore.createProvider(payload);
    form.value.api_key = "";
    form.value.display_name = "";
    form.value.models = "";
    form.value.default_model = "";
    form.value.base_url = "";
  } catch (err) {
    createError.value = resolveError(err, "创建提供商失败，请检查参数。");
  } finally {
    creating.value = false;
  }
}

async function removeProvider(providerId) {
  if (!providerId || deletingId.value) {
    return;
  }
  const confirmed =
    typeof window === "undefined" ||
    window.confirm("确定要删除该提供商配置吗？该操作无法撤销。");
  if (!confirmed) {
    return;
  }
  deletingId.value = providerId;
  try {
    await userStore.deleteProvider(providerId);
  } catch {
    // surface error from store.providerError
  } finally {
    deletingId.value = "";
  }
}

async function checkHealth(providerId) {
  if (!providerId || checkingId.value) {
    return;
  }
  checkingId.value = providerId;
  try {
    const response = await checkProviderHealth(providerId);
    const data = response?.data || {};
    healthState.value = {
      ...healthState.value,
      [providerId]: {
        checked: true,
        ok: Boolean(data.ok),
        status: data.status || (data.ok ? "healthy" : "unknown_error"),
        message: data.message || "",
        latency_ms: data.latency_ms,
        error: data.error || "",
      },
    };
  } catch (err) {
    healthState.value = {
      ...healthState.value,
      [providerId]: {
        checked: true,
        ok: false,
        status: "unknown_error",
        message: "健康检查请求失败",
        latency_ms: null,
        error: resolveError(err, "健康检查失败"),
      },
    };
  } finally {
    checkingId.value = "";
  }
}

async function refreshAll() {
  await loadProviders();
  if (!userStore.profile && userStore.isAuthenticated) {
    try {
      await userStore.fetchCurrentUser();
    } catch {
      // ignore; surface profile empty state
    }
  }
}

onMounted(() => {
  if (activeGroupId.value && !form.value.group_id) {
    form.value.group_id = activeGroupId.value;
  }
  refreshAll();
});

watch(activeGroupId, async (nextGroupId) => {
  if (!form.value.group_id) {
    form.value.group_id = nextGroupId || "";
  }
  await loadProviders();
});
</script>

<style scoped>
.settings-view .page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-20);
  flex-wrap: wrap;
}

.card-grid {
  display: grid;
  gap: var(--space-16);
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 26px;
  padding: 24px;
  box-shadow: var(--shadow-soft);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-12);
  margin-bottom: var(--space-16);
}

.panel-meta {
  font-size: var(--font-size-12);
  color: var(--muted);
}

.theme-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-16);
  padding: 18px;
  border-radius: 22px;
  background: var(--panel-strong);
}

.profile-grid {
  display: grid;
  gap: var(--space-12);
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.profile-item {
  display: grid;
  gap: var(--space-8);
  padding: 14px;
  border-radius: 18px;
  background: var(--panel-strong);
}

.table {
  display: grid;
  gap: var(--space-12);
}

.provider-notice {
  display: flex;
  align-items: flex-start;
  gap: var(--space-8);
  padding: 14px 16px;
  margin-bottom: var(--space-16);
  border-radius: 18px;
  border: 1px dashed var(--line);
  color: var(--muted);
  background: color-mix(in srgb, var(--panel-strong) 75%, transparent);
  font-size: var(--font-size-13);
  line-height: 1.6;
}

.provider-notice.limited {
  border-color: color-mix(in srgb, var(--color-amber-700) 35%, transparent);
}

.readonly-provider-state {
  border: 1px dashed var(--line);
}

.table-header,
.table-row {
  display: grid;
  grid-template-columns: minmax(180px, 1.25fr) minmax(150px, 1fr) minmax(200px, 1.3fr) minmax(160px, 0.9fr) minmax(180px, 0.9fr);
  gap: var(--space-12);
  align-items: start;
}

.table-header {
  font-size: var(--font-size-12);
  text-transform: uppercase;
  letter-spacing: var(--letter-spacing-wide);
  color: var(--muted);
}

.table-row {
  padding: 14px 0;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 60%, transparent);
}

.split-panel {
  display: grid;
  gap: var(--space-16);
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
}

.panel-block {
  display: grid;
  gap: var(--space-12);
}

.form-stack {
  display: grid;
  gap: 14px;
}

.field {
  display: grid;
  gap: var(--space-8);
}

.field input,
.field select {
  min-height: 44px;
  padding: 10px 14px;
  border-radius: 16px;
  border: 1px solid color-mix(in srgb, var(--line) 75%, transparent);
  background: color-mix(in srgb, var(--panel-strong) 96%, transparent);
  color: var(--text);
}

.checkbox-field {
  display: flex;
  align-items: center;
  gap: var(--space-8);
}

.field-label {
  font-size: var(--font-size-12);
  color: var(--muted);
}

.strong {
  font-weight: var(--font-weight-600);
}

.muted {
  color: var(--muted);
  font-size: var(--font-size-12);
}

.pill {
  display: inline-flex;
  align-items: center;
  gap: var(--space-4);
  padding: 2px 10px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: var(--font-size-12);
  margin-left: var(--space-8);
}

.provider-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-8);
}

.health-indicator {
  display: grid;
  gap: var(--space-8);
  margin-top: var(--space-8);
}

.health-ok {
  color: var(--color-green-700, #15803d);
}

.health-failed {
  color: var(--color-amber-700);
}

.pill-active {
  background: color-mix(in srgb, var(--accent) 16%, transparent);
  color: var(--accent);
}

.pill-muted {
  background: color-mix(in srgb, var(--line) 40%, transparent);
  color: var(--muted);
}

.health-ok-pill {
  background: color-mix(in srgb, #16a34a 16%, transparent);
  color: #15803d;
}

.health-warn-pill {
  background: color-mix(in srgb, #d97706 16%, transparent);
  color: #b45309;
}

.health-failed-pill {
  background: color-mix(in srgb, #dc2626 16%, transparent);
  color: #b91c1c;
}

.health-text {
  line-height: 1.3;
}

.ghost-button {
  border: 1px solid var(--line);
  background: transparent;
  color: var(--text);
  padding: 6px 12px;
  border-radius: 14px;
}

.ghost-button.small {
  padding: 4px 10px;
  font-size: var(--font-size-12);
}

.primary-button {
  background: var(--accent);
  color: #fff;
  border: none;
  min-height: 44px;
  padding: 8px 16px;
  border-radius: 16px;
}

.error-text {
  margin-top: var(--space-8);
  color: #e04848;
}

.empty-state {
  padding: 20px;
  border-radius: 20px;
  background: var(--panel-strong);
}

@media (max-width: 1180px) {
  .table-header {
    display: none;
  }

  .table-row {
    grid-template-columns: 1fr;
    gap: 10px;
    padding: 16px;
    border: 1px solid color-mix(in srgb, var(--line) 60%, transparent);
    border-radius: 20px;
    background: color-mix(in srgb, var(--panel-strong) 92%, transparent);
    margin-bottom: 10px;
  }
}
</style>
