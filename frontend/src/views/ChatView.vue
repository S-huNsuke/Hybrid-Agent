<template>
  <div class="chat-page">
    <aside class="chat-page__sessions">
      <header class="sessions-panel__header">
        <div>
          <p class="section-kicker">会话</p>
          <h3>对话工作台</h3>
          <p class="sessions-panel__intro">按主题切换、重命名或清理会话。</p>
        </div>
        <button class="ghost-btn" type="button" @click="createSession">
          新建
        </button>
      </header>

      <div class="sessions-panel__meta">
        <div class="meta-chip">
          <span class="meta-chip__label">总会话</span>
          <strong>{{ sessions.length }}</strong>
        </div>
        <div class="meta-chip">
          <span class="meta-chip__label">当前</span>
          <strong>{{ activeSessionTitle }}</strong>
        </div>
      </div>

      <div class="session-list">
        <article
          v-for="session in sessions"
          :key="session.id"
          class="session-card"
          :class="{ active: session.id === activeSessionId }"
        >
          <button
            class="session-card__main"
            type="button"
            @click="selectSession(session.id)"
          >
            <div class="session-card__title-row">
              <strong>{{ session.title || "新会话" }}</strong>
              <span class="session-card__time">
                {{ formatSessionTime(session.updatedAt || session.createdAt) }}
              </span>
            </div>
            <p class="session-card__preview">
              {{ sessionPreview(session) }}
            </p>
          </button>
          <div class="session-card__actions">
            <button class="inline-action" type="button" @click.stop="renameSession(session)">
              重命名
            </button>
            <button class="inline-action danger" type="button" @click.stop="removeSession(session.id)">
              删除
            </button>
          </div>
        </article>
      </div>
    </aside>

    <section class="chat-page__main">
      <header class="chat-hero">
        <div class="chat-hero__heading">
          <p class="section-kicker">对话</p>
          <h3>{{ activeSessionTitle }}</h3>
          <p class="chat-hero__subtitle">
            把当前对话、模型状态和文档来源维持在同一个稳定工作区里。
          </p>
        </div>

        <div class="chat-hero__controls">
          <label class="model-select">
            <span class="field-label">模型</span>
            <select v-model="selectedModel" :disabled="modelLoading">
              <option v-for="model in models" :key="model.id" :value="model.id">
                {{ formatModelOption(model) }}
              </option>
            </select>
          </label>
          <button class="ghost-btn" type="button" @click="resetSession">
            清空会话
          </button>
        </div>
      </header>

      <section class="chat-overview">
        <article class="overview-card">
          <span class="overview-card__label">会话编号</span>
          <strong>{{ sessionLabel }}</strong>
          <p>当前选中会话的后端持久化 ID。</p>
        </article>
        <article class="overview-card">
          <span class="overview-card__label">运行状态</span>
          <strong>{{ sending ? "回复中..." : "就绪" }}</strong>
          <p>{{ sending ? "模型正在生成内容，请稍候。" : "可以继续提问或切换会话。" }}</p>
        </article>
        <article class="overview-card">
          <span class="overview-card__label">当前模型</span>
          <strong>{{ activeModelLabel }}</strong>
          <p>{{ activeModelHint }}</p>
        </article>
      </section>

      <section class="chat-stage">
        <div class="chat-stage__messages" role="log" aria-live="polite">
          <div v-if="!messages.length" class="empty-state">
            <h4>开始一次对话</h4>
            <p>选择左侧会话或直接新建，然后在下方输入问题。</p>
          </div>

          <article
            v-for="message in messages"
            :key="message.id"
            class="message-card"
            :class="message.role"
          >
            <div class="message-card__rail">
              <span class="message-card__avatar">
                {{ message.role === "user" ? "你" : "AI" }}
              </span>
            </div>
            <div class="message-card__body">
              <header class="message-card__header">
                <div class="message-card__identity">
                  <strong>{{ message.role === "user" ? "你" : "助手" }}</strong>
                  <span v-if="message.modelUsed && message.role === 'assistant'" class="message-card__model">
                    {{ message.modelUsed }}
                  </span>
                </div>
                <span v-if="message.timestamp" class="message-card__time">
                  {{ formatTime(message.timestamp) }}
                </span>
              </header>

              <div class="message-card__content">
                {{ message.content }}
              </div>

              <footer
                v-if="message.sources && message.sources.length"
                class="message-card__footer"
              >
                <span class="sources-label">来源</span>
                <span>{{ message.sources.length }} 条上下文</span>
              </footer>
            </div>
          </article>
        </div>

        <form class="composer" @submit.prevent="handleSend">
          <textarea
            v-model="prompt"
            class="composer__input"
            placeholder="输入你的问题，回车发送，Shift+Enter 换行"
            rows="4"
            :disabled="sending"
            @keydown.enter.exact.prevent="handleSend"
          />

          <div class="composer__footer">
            <div class="composer__hint">
              <strong>当前模型</strong>
              <span>{{ activeModelLabel }}</span>
            </div>
            <button
              class="primary-btn"
              type="submit"
              :disabled="sending || !prompt.trim()"
            >
              {{ sending ? "发送中..." : "发送" }}
            </button>
          </div>

          <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
        </form>
      </section>
    </section>

    <aside class="chat-page__context">
      <section class="context-panel">
        <header class="context-panel__header">
          <div>
            <p class="section-kicker">上下文</p>
            <h4>来源与线索</h4>
          </div>
          <span class="context-panel__count">{{ activeSources.length }} 条</span>
        </header>

        <div v-if="!activeSources.length" class="empty-state empty-state--compact">
          <h4>暂无来源</h4>
          <p>发送问题后，相关文档片段会出现在这里。</p>
        </div>

        <div v-else class="context-panel__list">
          <FeatureCard
            v-for="(source, index) in activeSources"
            :key="`${source.filename}-${index}`"
            label="来源"
            :title="source.filename || `Document ${index + 1}`"
            :description="source.content || '未提供摘要内容'"
            :meta="`#${index + 1}`"
            compact
            tone="accent"
          >
            <template #footer>
              <span>截取片段 · {{ source.content?.length || 0 }} 字</span>
            </template>
          </FeatureCard>
        </div>
      </section>
    </aside>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";

import FeatureCard from "../components/FeatureCard.vue";
import { fetchModels } from "../api/chat";
import { useChatStore } from "../stores/chat";
import { useUserStore } from "../stores/user";

const chatStore = useChatStore();
const userStore = useUserStore();
const prompt = ref("");
const errorMessage = ref("");
const models = ref([]);
const modelLoading = ref(false);
const activeSources = ref([]);

const messages = computed(() => chatStore.messages);
const sessions = computed(() => chatStore.sessionList);
const activeSessionId = computed(() => chatStore.activeSessionId);
const activeSessionTitle = computed(
  () => chatStore.activeSession?.title || "新会话",
);
const sending = computed(() => chatStore.sending);
const activeGroupId = computed(() => userStore.activeGroupId);
const selectedModel = computed({
  get: () => chatStore.selectedModel,
  set: (value) => {
    chatStore.setSelectedModel(value);
  },
});

const activeModel = computed(() =>
  models.value.find((model) => model.id === selectedModel.value),
);

const activeModelLabel = computed(() => {
  if (activeModel.value) {
    return formatModelOption(activeModel.value);
  }
  if (selectedModel.value) {
    return selectedModel.value;
  }
  return "未就绪";
});

const activeModelHint = computed(() => {
  if (activeModel.value?.description) {
    return activeModel.value.description;
  }
  if (selectedModel.value === "auto") {
    return "根据问题复杂度自动切换运行时模型。";
  }
  return "当前会话将沿用这个模型继续生成。";
});

const sessionLabel = computed(() =>
  chatStore.sessionId ? `#${chatStore.sessionId.slice(0, 8)}` : "未建立",
);

function formatModelOption(model) {
  if (!model) {
    return "未就绪";
  }
  return model.provider ? `${model.name} · ${model.provider}` : model.name;
}

function formatTime(timestamp) {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatSessionTime(timestamp) {
  if (!timestamp) {
    return "";
  }
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toLocaleDateString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
  });
}

function sessionPreview(session) {
  const assistant = [...(session.messages || [])]
    .reverse()
    .find((message) => message.role === "assistant" && message.content);
  const user = [...(session.messages || [])]
    .reverse()
    .find((message) => message.role === "user" && message.content);
  return (assistant?.content || user?.content || "暂无消息").slice(0, 48);
}

async function loadModels() {
  modelLoading.value = true;
  try {
    const { data } = await fetchModels(
      activeGroupId.value ? { group_id: activeGroupId.value } : {},
    );
    models.value = Array.isArray(data) && data.length ? data : buildModelFallback();
  } catch {
    models.value = buildModelFallback();
  } finally {
    syncSelectedModel(models.value);
    modelLoading.value = false;
  }
}

function buildModelFallback() {
  const candidates = [selectedModel.value, "auto"]
    .filter((item, index, arr) => item && arr.indexOf(item) === index)
    .map((id) => ({
      id,
      name: id === "auto" ? "自动选择" : id,
      description: "",
      provider: "",
    }));
  return candidates;
}

function syncSelectedModel(nextModels) {
  if (!Array.isArray(nextModels) || !nextModels.length) {
    return;
  }
  const hasSelected = nextModels.some((model) => model.id === selectedModel.value);
  if (!hasSelected) {
    selectedModel.value = nextModels[0].id;
  }
}

function createSession() {
  chatStore.createSession();
  activeSources.value = [];
  prompt.value = "";
  errorMessage.value = "";
}

function selectSession(sessionId) {
  chatStore.setActiveSession(sessionId);
  activeSources.value = [];
  prompt.value = "";
  errorMessage.value = "";
}

async function renameSession(session) {
  const nextTitle =
    typeof window === "undefined"
      ? session.title
      : window.prompt("输入新的会话名称", session.title || "新会话");
  if (nextTitle) {
    await chatStore.renameSession(session.id, nextTitle);
  }
}

async function removeSession(sessionId) {
  const confirmed =
    typeof window === "undefined" ||
    window.confirm("确定删除该会话吗？此操作不可撤销。");
  if (!confirmed) {
    return;
  }
  await chatStore.deleteSession(sessionId);
  activeSources.value = [];
}

function resetSession() {
  chatStore.reset();
  activeSources.value = [];
  prompt.value = "";
  errorMessage.value = "";
}

async function handleSend() {
  if (sending.value) {
    return;
  }
  const content = prompt.value.trim();
  if (!content) {
    return;
  }

  errorMessage.value = "";
  prompt.value = "";

  try {
    const assistantId = await chatStore.sendMessage({
      message: content,
      model: selectedModel.value,
      use_rag: true,
      stream: false,
    });

    const assistantMessage = chatStore.messages.find(
      (message) => message.id === assistantId,
    );
    if (assistantMessage?.status === "done") {
      activeSources.value = assistantMessage.sources || [];
    } else if (assistantMessage?.status === "error") {
      errorMessage.value = assistantMessage.error || "请求失败，请稍后重试";
    }
  } catch {
    errorMessage.value = "网络错误，请稍后重试";
  }
}

onMounted(() => {
  loadModels();
  chatStore.loadRemoteSessions();
  if (!sessions.value.length) {
    createSession();
  }
});

watch(activeGroupId, async () => {
  activeSources.value = [];
  errorMessage.value = "";
  await loadModels();
  await chatStore.loadRemoteSessions();
  if (!sessions.value.length) {
    createSession();
  }
});
</script>

<style scoped>
.chat-page {
  display: grid;
  grid-template-columns: minmax(260px, 0.88fr) minmax(0, 1.85fr) minmax(300px, 0.95fr);
  gap: 20px;
  align-items: start;
}

.chat-page__sessions,
.chat-page__main,
.chat-page__context {
  min-width: 0;
}

.chat-page__sessions,
.chat-hero,
.chat-stage,
.context-panel {
  border: 1px solid color-mix(in srgb, var(--line) 70%, transparent);
  border-radius: 28px;
  background: color-mix(in srgb, var(--panel) 90%, transparent);
  box-shadow: var(--shadow-soft);
}

.chat-page__sessions {
  display: grid;
  gap: 16px;
  padding: 18px;
}

.sessions-panel__header,
.context-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.sessions-panel__header h3,
.chat-hero__heading h3,
.context-panel__header h4 {
  margin: 4px 0 0;
}

.sessions-panel__intro {
  margin: 6px 0 0;
  color: var(--muted);
  line-height: 1.6;
}

.sessions-panel__meta {
  display: grid;
  gap: 10px;
}

.meta-chip {
  display: grid;
  gap: 4px;
  padding: 12px 14px;
  border-radius: 18px;
  background: color-mix(in srgb, var(--panel-strong) 92%, transparent);
  border: 1px solid color-mix(in srgb, var(--line) 58%, transparent);
}

.meta-chip__label {
  font-size: var(--font-size-12);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--muted);
}

.session-list {
  display: grid;
  gap: 12px;
}

.session-card {
  display: grid;
  gap: 10px;
  padding: 14px;
  border-radius: 22px;
  border: 1px solid color-mix(in srgb, var(--line) 58%, transparent);
  background: color-mix(in srgb, var(--panel-strong) 90%, transparent);
  transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease;
}

.session-card:hover {
  transform: translateY(-1px);
  border-color: color-mix(in srgb, var(--accent) 28%, transparent);
}

.session-card.active {
  border-color: color-mix(in srgb, var(--accent) 82%, transparent);
  background: color-mix(in srgb, var(--accent-soft) 70%, var(--panel));
}

.session-card__main {
  display: grid;
  gap: 10px;
  width: 100%;
  padding: 0;
  border: 0;
  background: transparent;
  text-align: left;
  color: inherit;
  cursor: pointer;
}

.session-card__title-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
}

.session-card__title-row strong {
  font-size: var(--font-size-14);
  line-height: 1.35;
}

.session-card__time,
.session-card__preview {
  font-size: var(--font-size-12);
  color: var(--muted);
}

.session-card__preview {
  margin: 0;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.session-card__actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.inline-action {
  appearance: none;
  border: none;
  background: transparent;
  padding: 0;
  font-size: var(--font-size-12);
  color: var(--muted);
  cursor: pointer;
}

.inline-action.danger {
  color: var(--color-amber-700);
}

.chat-page__main {
  display: grid;
  gap: 18px;
}

.chat-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  padding: 20px;
}

.chat-hero__heading {
  min-width: 0;
}

.chat-hero__subtitle {
  margin: 8px 0 0;
  max-width: 56ch;
  color: var(--muted);
  line-height: 1.65;
}

.chat-hero__controls {
  display: flex;
  align-items: flex-end;
  justify-content: flex-end;
  gap: 12px;
  flex-wrap: wrap;
}

.model-select {
  display: grid;
  gap: 6px;
  min-width: 240px;
}

.model-select select {
  min-height: 42px;
  padding: 8px 14px;
  border-radius: 999px;
  border: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  background: color-mix(in srgb, var(--panel-strong) 96%, transparent);
  color: var(--text);
}

.chat-overview {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.overview-card {
  display: grid;
  gap: 8px;
  min-height: 108px;
  padding: 16px 18px;
  border-radius: 22px;
  border: 1px solid color-mix(in srgb, var(--line) 68%, transparent);
  background: color-mix(in srgb, var(--panel-strong) 88%, transparent);
  align-content: start;
}

.overview-card__label {
  font-size: var(--font-size-12);
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.overview-card strong {
  font-size: var(--font-size-20);
  line-height: 1.15;
}

.overview-card p {
  margin: 0;
  color: var(--muted);
  line-height: 1.6;
}

.chat-stage {
  display: grid;
  grid-template-rows: minmax(520px, 1fr) auto;
  gap: 0;
  overflow: hidden;
}

.chat-stage__messages {
  display: grid;
  align-content: start;
  gap: 16px;
  max-height: 560px;
  overflow-y: auto;
  padding: 20px;
}

.empty-state {
  display: grid;
  gap: 8px;
  padding: 22px;
  border-radius: 20px;
  border: 1px dashed color-mix(in srgb, var(--line) 70%, transparent);
  background: color-mix(in srgb, var(--panel-strong) 94%, transparent);
  color: var(--muted);
}

.empty-state h4,
.empty-state p {
  margin: 0;
}

.empty-state--compact {
  padding: 18px;
}

.message-card {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr);
  gap: 14px;
  align-items: start;
}

.message-card.user {
  justify-self: end;
}

.message-card.user .message-card__body {
  background: color-mix(in srgb, var(--accent-soft) 58%, var(--panel-strong));
}

.message-card__rail {
  display: flex;
  justify-content: center;
  padding-top: 4px;
}

.message-card__avatar {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  border-radius: 14px;
  background: color-mix(in srgb, var(--panel-strong) 94%, transparent);
  border: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  font-size: var(--font-size-12);
  font-weight: var(--font-weight-semibold);
  color: var(--accent);
}

.message-card__body {
  display: grid;
  gap: 10px;
  min-width: 0;
  max-width: min(760px, 100%);
  padding: 16px 18px;
  border-radius: 24px;
  border: 1px solid color-mix(in srgb, var(--line) 70%, transparent);
  background: color-mix(in srgb, var(--panel-strong) 94%, transparent);
  box-shadow: var(--shadow-soft);
}

.message-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.message-card__identity {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.message-card__identity strong {
  line-height: 1.2;
}

.message-card__model {
  display: inline-flex;
  align-items: center;
  padding: 4px 9px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--accent-soft) 70%, transparent);
  color: var(--accent);
  font-size: var(--font-size-12);
  line-height: 1.1;
}

.message-card__time {
  margin-left: auto;
  font-size: var(--font-size-12);
  color: var(--muted);
}

.message-card__content {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.75;
}

.message-card__footer {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: var(--font-size-12);
  color: var(--muted);
}

.sources-label {
  font-weight: var(--font-weight-semibold);
  color: var(--text);
}

.composer {
  display: grid;
  gap: 14px;
  padding: 18px 20px 20px;
  border-top: 1px solid color-mix(in srgb, var(--line) 58%, transparent);
  background: color-mix(in srgb, var(--panel) 88%, transparent);
}

.composer__input {
  width: 100%;
  min-height: 126px;
  padding: 14px 16px;
  border-radius: 22px;
  border: 1px solid color-mix(in srgb, var(--line) 75%, transparent);
  background: color-mix(in srgb, var(--panel-strong) 96%, transparent);
  color: var(--text);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-14);
  line-height: 1.65;
  resize: vertical;
}

.composer__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.composer__hint {
  display: grid;
  gap: 4px;
  color: var(--muted);
  font-size: var(--font-size-12);
  line-height: 1.5;
}

.composer__hint strong {
  color: var(--text);
}

.primary-btn,
.ghost-btn {
  min-height: 42px;
  padding: 8px 18px;
  border-radius: 999px;
  border: 1px solid transparent;
  font-weight: var(--font-weight-semibold);
  cursor: pointer;
}

.primary-btn {
  background: var(--accent);
  color: #fff;
  box-shadow: var(--shadow-soft);
}

.primary-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.ghost-btn {
  background: transparent;
  border-color: color-mix(in srgb, var(--line) 72%, transparent);
  color: var(--text);
}

.field-label {
  font-size: var(--font-size-12);
  color: var(--muted);
}

.error-text {
  margin: 0;
  font-size: var(--font-size-12);
  color: var(--color-amber-700);
}

.context-panel {
  position: sticky;
  top: 12px;
  display: grid;
  gap: 16px;
  padding: 18px;
}

.context-panel__count {
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--accent-soft) 65%, transparent);
  color: var(--accent);
  font-size: var(--font-size-12);
  line-height: 1;
}

.context-panel__list {
  display: grid;
  gap: 12px;
}

@media (max-width: 1280px) {
  .chat-page {
    grid-template-columns: minmax(240px, 0.9fr) minmax(0, 1.4fr);
  }

  .chat-page__context {
    grid-column: 1 / -1;
  }

  .context-panel {
    position: static;
  }
}

@media (max-width: 1024px) {
  .chat-page {
    grid-template-columns: 1fr;
  }

  .chat-hero {
    flex-direction: column;
  }

  .chat-hero__controls {
    width: 100%;
    justify-content: space-between;
  }

  .chat-overview {
    grid-template-columns: 1fr;
  }

  .chat-stage {
    grid-template-rows: auto auto;
  }

  .chat-stage__messages {
    max-height: none;
  }

  .message-card {
    grid-template-columns: 36px minmax(0, 1fr);
  }

  .message-card__body {
    max-width: 100%;
  }

  .composer__footer {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
