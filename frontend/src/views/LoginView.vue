<template>
  <div class="login-view">
    <section class="login-panel">
      <div class="login-header">
        <p class="section-kicker">安全访问</p>
        <h3>{{ mode === "login" ? "欢迎回来" : "创建账号" }}</h3>
        <p class="login-subtitle">
          {{
            mode === "login"
              ? "使用你的账户登录 Hybrid-Agent 控制台。"
              : "注册后将自动登录。首个注册用户会自动成为 admin。"
          }}
        </p>
      </div>

      <div class="mode-switch">
        <button
          class="mode-pill"
          :class="{ active: mode === 'login' }"
          type="button"
          @click="mode = 'login'"
        >
          登录
        </button>
        <button
          class="mode-pill"
          :class="{ active: mode === 'register' }"
          type="button"
          @click="mode = 'register'"
        >
          注册
        </button>
      </div>

      <el-alert
        v-if="errorMessage"
        class="login-alert"
        type="error"
        :closable="false"
        show-icon
      >
        {{ errorMessage }}
      </el-alert>

      <el-alert
        v-if="successMessage"
        class="login-alert"
        type="success"
        :closable="false"
        show-icon
      >
        {{ successMessage }}
      </el-alert>

      <form class="login-form" @submit.prevent="handleSubmit">
        <label class="field">
          <span>用户名</span>
          <el-input
            v-model="form.username"
            placeholder="输入用户名"
            autocomplete="username"
          />
        </label>

        <label v-if="mode === 'register'" class="field">
          <span>邮箱</span>
          <el-input
            v-model="form.email"
            placeholder="输入邮箱（可选）"
            autocomplete="email"
          />
        </label>

        <label class="field">
          <span>密码</span>
          <el-input
            v-model="form.password"
            placeholder="输入密码"
            type="password"
            autocomplete="current-password"
            show-password
          />
        </label>

        <div class="login-actions">
          <el-button
            type="primary"
            native-type="submit"
            :loading="loading"
            :disabled="submitDisabled"
            class="login-button"
          >
            {{
              loading
                ? mode === "login"
                  ? "登录中..."
                  : "注册中..."
                : mode === "login"
                  ? "登录"
                  : "注册并登录"
            }}
          </el-button>
          <p class="login-footnote">
            {{ mode === "login" ? "登录" : "注册" }}后将自动跳转到 {{ redirectLabel }}。
          </p>
        </div>
      </form>
    </section>

    <aside class="login-aside">
      <div class="aside-card">
        <p class="section-kicker">使用收益</p>
        <h4>分组隔离 + 使用指标</h4>
        <p class="aside-copy">
          登录页现在只是入口，不该抢戏。重点是让用户在一个稳定、清晰的表单里完成访问。
        </p>
        <ul class="aside-list">
          <li>实时监控与使用日志</li>
          <li>文档与聊天按组隔离</li>
          <li>JWT 登录态与安全访问</li>
        </ul>
        <div class="aside-stats">
          <div class="aside-stat">
            <span class="aside-stat__label">访问方式</span>
            <strong>JWT</strong>
          </div>
          <div class="aside-stat">
            <span class="aside-stat__label">隔离范围</span>
            <strong>分组感知</strong>
          </div>
        </div>
      </div>
    </aside>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useUserStore } from "../stores/user";

const router = useRouter();
const route = useRoute();
const userStore = useUserStore();

const form = reactive({
  username: "",
  email: "",
  password: "",
});
const mode = ref("login");

const loading = ref(false);
const errorMessage = ref("");
const successMessage = ref("");

const redirectPath = computed(() => {
  const candidate = route.query.redirect;
  if (typeof candidate === "string" && candidate.startsWith("/")) {
    return candidate;
  }
  return "/";
});

const redirectLabel = computed(() =>
  redirectPath.value === "/" ? "概览页" : redirectPath.value
);

const submitDisabled = computed(
  () => loading.value || !form.username || !form.password
);

async function handleSubmit() {
  if (submitDisabled.value) {
    return;
  }

  loading.value = true;
  errorMessage.value = "";
  successMessage.value = "";

  try {
    if (mode.value === "login") {
      await userStore.login({
        username: form.username.trim(),
        password: form.password,
      });
      successMessage.value = "登录成功，即将跳转。";
    } else {
      await userStore.register({
        username: form.username.trim(),
        email: form.email.trim() || null,
        password: form.password,
      });
      successMessage.value = "注册成功，即将跳转。";
    }
    await router.replace(redirectPath.value);
  } catch (error) {
    const message =
      error?.response?.data?.detail ||
      error?.message ||
      "登录失败，请检查用户名和密码。";
    errorMessage.value = message;
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login-view {
  display: grid;
  grid-template-columns: minmax(0, 1.08fr) minmax(320px, 0.92fr);
  gap: 28px;
  align-items: start;
}

.login-panel {
  display: grid;
  gap: 20px;
  background:
    radial-gradient(circle at top right, color-mix(in srgb, var(--ha-accent-soft, var(--color-accent-soft)) 55%, transparent), transparent 28%),
    var(--ha-surface);
  border: 1px solid color-mix(in srgb, var(--ha-border) 78%, transparent);
  border-radius: 28px;
  padding: 32px;
  box-shadow: var(--shadow-soft);
}

.login-header h3 {
  margin: 8px 0 10px;
  font-size: 34px;
  line-height: 1.1;
  color: var(--ha-text);
}

.login-subtitle {
  margin: 0;
  color: var(--ha-muted);
  line-height: 1.7;
  max-width: 46ch;
}

.login-alert {
  margin: 0;
  border-radius: 18px;
}

.mode-switch {
  display: inline-flex;
  gap: 8px;
  padding: 6px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--ha-surface-2, var(--color-surface-muted)) 88%, transparent);
  border: 1px solid color-mix(in srgb, var(--ha-border) 70%, transparent);
}

.mode-pill {
  appearance: none;
  border: 1px solid transparent;
  background: transparent;
  color: var(--ha-muted);
  border-radius: 999px;
  padding: 9px 16px;
  min-width: 84px;
  cursor: pointer;
  transition: background 0.18s ease, color 0.18s ease, border-color 0.18s ease;
}

.mode-pill.active {
  background: var(--ha-accent);
  color: #fff;
  border-color: var(--ha-accent);
}

.login-form {
  display: grid;
  gap: 18px;
}

.field {
  display: grid;
  gap: 8px;
  color: var(--ha-muted);
  font-size: 13px;
}

.field span {
  font-size: var(--font-size-12);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.login-actions {
  display: grid;
  gap: 10px;
  margin-top: 4px;
}

.login-button {
  width: 100%;
  min-height: 46px;
  border-radius: 16px;
  font-weight: 700;
}

.login-footnote {
  margin: 0;
  font-size: 12px;
  color: var(--ha-muted);
  line-height: 1.6;
}

.login-aside {
  position: sticky;
  top: 12px;
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--ha-surface-2) 92%, transparent), color-mix(in srgb, var(--ha-surface) 96%, transparent));
  border: 1px solid color-mix(in srgb, var(--ha-border) 75%, transparent);
  border-radius: 28px;
  padding: 28px;
  box-shadow: var(--shadow-soft);
}

.aside-card h4 {
  margin: 10px 0 14px;
  font-size: 24px;
  color: var(--ha-text);
  line-height: 1.2;
}

.aside-copy {
  margin: 0 0 18px;
  color: var(--ha-muted);
  line-height: 1.7;
}

.aside-list {
  margin: 0 0 20px;
  padding-left: 18px;
  color: var(--ha-muted);
  display: grid;
  gap: 10px;
}

.aside-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.aside-stat {
  display: grid;
  gap: 6px;
  padding: 14px 16px;
  border-radius: 18px;
  background: color-mix(in srgb, var(--ha-surface) 92%, transparent);
  border: 1px solid color-mix(in srgb, var(--ha-border) 68%, transparent);
}

.aside-stat__label {
  font-size: var(--font-size-12);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--ha-muted);
}

@media (max-width: 980px) {
  .login-view {
    grid-template-columns: 1fr;
  }

  .login-panel,
  .login-aside {
    padding: 24px;
  }

  .login-header h3 {
    font-size: 28px;
  }

  .login-aside {
    position: static;
  }
}
</style>
