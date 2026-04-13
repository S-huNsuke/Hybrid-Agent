<template>
  <div class="view-stack documents-view">
    <header class="page-header">
      <div>
        <p class="section-kicker">文档工作台</p>
        <h3>文档管理工作台</h3>
        <p>支持批量上传、任务追踪、失败重试、搜索筛选和排序。</p>
      </div>
      <div class="page-actions">
        <button class="ghost-button" type="button" @click="refreshDocuments" :disabled="loading">
          {{ loading ? "刷新中..." : "刷新列表" }}
        </button>
      </div>
    </header>

    <section class="panel upload-panel">
      <div class="panel-header">
        <div>
          <p class="section-kicker">上传</p>
          <h4>上传文档</h4>
        </div>
        <div class="upload-actions">
          <label class="file-input">
            <input
              type="file"
              accept=".pdf,.txt,.md,.doc,.docx"
              multiple
              @change="handleFileChange"
            />
            选择文件
          </label>
          <button
            class="ghost-button"
            type="button"
            :disabled="!selectedFiles.length || isSubmitting"
            @click="clearSelectedFiles"
          >
            清空
          </button>
          <button
            class="primary-button"
            type="button"
            :disabled="!selectedFiles.length || isSubmitting"
            @click="handleUpload"
          >
            {{ isSubmitting ? "提交中..." : "批量上传" }}
          </button>
        </div>
      </div>

      <div class="upload-meta">
        <div>
          <span class="meta-label">已选文件</span>
          <span class="meta-value">{{ selectedFiles.length ? `${selectedFiles.length} 个` : "未选择" }}</span>
        </div>
        <div>
          <span class="meta-label">总大小</span>
          <span class="meta-value">{{ selectedFiles.length ? formatSize(totalSelectedSize) : "-" }}</span>
        </div>
        <div>
          <span class="meta-label">状态</span>
          <span class="meta-value">{{ uploadStatusText }}</span>
        </div>
      </div>

      <p class="upload-hint">
        支持 `pdf/txt/md/doc/docx`，单文件不超过 {{ MAX_FILE_SIZE_LABEL }}，批量最多 {{ MAX_BATCH_FILES }} 个。
      </p>

      <div v-if="selectedFiles.length" class="selected-grid">
        <div v-for="file in selectedFiles" :key="fileKey(file)" class="selected-item">
          <div>
            <p class="selected-title">{{ file.name }}</p>
            <p class="selected-meta">{{ formatSize(file.size) }}</p>
          </div>
          <button class="ghost-button small" type="button" @click="removeSelectedFile(file)">
            移除
          </button>
        </div>
      </div>

      <p v-if="uploadNotice" class="notice-text">{{ uploadNotice }}</p>
      <p v-if="uploadError" class="error-text">{{ uploadError }}</p>
    </section>

    <section class="panel">
      <div class="panel-header">
        <div>
          <p class="section-kicker">任务</p>
          <h4>上传任务</h4>
          <p class="panel-meta">
            活跃 {{ activeTaskCount }} / 失败 {{ failedTaskCount }} / 总计 {{ tasks.length }}
          </p>
        </div>
        <button class="ghost-button" type="button" @click="refreshTasks" :disabled="!tasks.length">
          刷新任务
        </button>
      </div>

      <div v-if="!tasks.length" class="empty-state">
        <h4>暂无任务</h4>
        <p>上传文件后会生成任务记录，并在此处展示进度。</p>
      </div>

      <div v-else class="task-grid">
        <FeatureCard
          v-for="task in tasks"
          :key="task.task_id"
          label="任务"
          :title="task.filename || task.task_id.slice(0, 8)"
          :description="resolveTaskDescription(task)"
          :meta="humanTaskStatus(task.status)"
          compact
          :tone="taskTone(task)"
        >
          <template #footer>
            <div class="task-footer">
              <div class="progress-track">
                <div class="progress-fill" :style="{ width: `${task.progress || 0}%` }"></div>
              </div>
              <span class="progress-label">{{ task.progress || 0 }}%</span>
            </div>
            <div class="task-actions">
              <button class="ghost-button small" type="button" @click="selectTask(task)">
                详情
              </button>
              <button
                v-if="isTaskActive(task.status)"
                class="ghost-button small"
                type="button"
                @click="fetchTask(task.task_id)"
              >
                刷新
              </button>
              <button
                v-if="task.status === 'failed'"
                class="ghost-button small"
                type="button"
                @click="retryTask(task)"
              >
                重试
              </button>
            </div>
          </template>
        </FeatureCard>
      </div>

      <article v-if="selectedTask" class="task-detail">
        <div class="task-detail-head">
          <h5>任务详情</h5>
          <p class="panel-meta">任务 ID：{{ selectedTask.task_id }}</p>
        </div>
        <dl class="task-detail-grid">
          <dt>文件名</dt>
          <dd>{{ selectedTask.filename || "-" }}</dd>
          <dt>状态</dt>
          <dd>{{ humanTaskStatus(selectedTask.status) }}</dd>
          <dt>进度</dt>
          <dd>{{ selectedTask.progress ?? 0 }}%</dd>
          <dt>最近更新</dt>
          <dd>{{ formatTime(selectedTask.updated_at) }}</dd>
          <dt>任务消息</dt>
          <dd>{{ selectedTask.message || "-" }}</dd>
          <dt>失败原因</dt>
          <dd>{{ selectedTask.error || "-" }}</dd>
        </dl>
        <p
          v-if="selectedTask.status === 'failed' && !selectedTask.file"
          class="task-detail-hint"
        >
          当前任务未保留原始文件，无法直接重试，请重新选择文件上传。
        </p>
        <div class="task-actions task-detail-actions">
          <button class="ghost-button small" type="button" @click="fetchTask(selectedTask.task_id)">
            刷新该任务
          </button>
          <button
            v-if="selectedTask.status === 'failed'"
            class="ghost-button small"
            type="button"
            @click="retryTask(selectedTask)"
          >
            重试该任务
          </button>
        </div>
      </article>
    </section>

    <section class="panel">
      <div class="panel-header">
        <div>
          <p class="section-kicker">文档库</p>
          <h4>文档列表</h4>
        </div>
        <div class="table-tools">
          <input
            v-model="searchTerm"
            class="search-input"
            type="search"
            placeholder="搜索文件名或状态"
          />
          <select v-model="statusFilter" class="filter-select">
            <option value="all">全部状态</option>
            <option value="ready">就绪</option>
            <option value="processing">处理中</option>
            <option value="failed">失败</option>
          </select>
          <select v-model="dateFilter" class="filter-select">
            <option value="all">全部时间</option>
            <option value="today">今天</option>
            <option value="7d">最近 7 天</option>
            <option value="30d">最近 30 天</option>
          </select>
          <select v-model="sortBy" class="filter-select">
            <option value="uploaded_desc">最新上传</option>
            <option value="uploaded_asc">最早上传</option>
            <option value="name_asc">名称 A-Z</option>
            <option value="name_desc">名称 Z-A</option>
            <option value="size_desc">大小从大到小</option>
            <option value="size_asc">大小从小到大</option>
            <option value="status_asc">状态排序</option>
          </select>
          <button
            v-if="hasDocumentFilters"
            class="ghost-button small"
            type="button"
            @click="resetDocumentFilters"
          >
            清空筛选
          </button>
          <p class="panel-meta">显示 {{ filteredDocuments.length }} / {{ documents.length }} 份</p>
        </div>
      </div>

      <div v-if="loading" class="empty-state">
        <h4>加载中...</h4>
        <p>正在获取文档列表。</p>
      </div>
      <div v-else-if="!filteredDocuments.length" class="empty-state">
        <h4>{{ hasDocumentFilters ? "没有匹配结果" : "还没有文档" }}</h4>
        <p>{{ hasDocumentFilters ? "请调整筛选条件后重试。" : "请先上传文件，完成解析后会出现在这里。" }}</p>
      </div>
      <div v-else class="document-table">
        <div class="table-header">
          <span>名称</span>
          <span>大小</span>
          <span>状态</span>
          <span>上传时间</span>
          <span class="table-actions">操作</span>
        </div>
        <div v-for="doc in filteredDocuments" :key="doc.id" class="table-row">
          <span class="doc-name">{{ doc.filename }}</span>
          <span>{{ formatSize(doc.size) }}</span>
          <span class="status-pill" :class="statusClass(doc.status)">
            {{ humanDocumentStatus(doc.status) }}
          </span>
          <span>{{ formatTime(doc.upload_time) }}</span>
          <span class="table-actions">
            <button class="ghost-button small" type="button" @click="handleDelete(doc)">
              删除
            </button>
          </span>
        </div>
      </div>

      <p v-if="deleteError" class="error-text">{{ deleteError }}</p>
    </section>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import FeatureCard from "../components/FeatureCard.vue";
import { useDocumentsStore } from "../stores/documents";
import { useUserStore } from "../stores/user";

const MAX_BATCH_FILES = 20;
const MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024;
const MAX_FILE_SIZE_LABEL = "20 MB";
const ACCEPTED_EXTENSIONS = new Set(["pdf", "txt", "md", "doc", "docx"]);

const documentsStore = useDocumentsStore();
const userStore = useUserStore();
const selectedFiles = ref([]);
const uploadError = ref("");
const uploadNotice = ref("");
const deleteError = ref("");
const isSubmitting = ref(false);
const selectedTaskId = ref("");
const searchTerm = ref("");
const statusFilter = ref("all");
const dateFilter = ref("all");
const sortBy = ref("uploaded_desc");
const activeGroupId = computed(() => userStore.activeGroupId);

const documents = computed(() => documentsStore.items || []);
const loading = computed(() => documentsStore.loading);
const tasks = computed(() => documentsStore.taskList || []);
const totalSelectedSize = computed(() =>
  selectedFiles.value.reduce((total, file) => total + (file?.size || 0), 0)
);
const activeTaskCount = computed(
  () => tasks.value.filter((task) => isTaskActive(task.status)).length
);
const failedTaskCount = computed(
  () => tasks.value.filter((task) => task.status === "failed").length
);
const selectedTask = computed(() => {
  if (!tasks.value.length) {
    return null;
  }
  return tasks.value.find((task) => task.task_id === selectedTaskId.value) || tasks.value[0];
});
const uploadStatusText = computed(() => {
  if (isSubmitting.value) {
    return "提交中";
  }
  if (activeTaskCount.value > 0) {
    return `处理中 (${activeTaskCount.value})`;
  }
  return "就绪";
});
const hasDocumentFilters = computed(() =>
  Boolean(searchTerm.value.trim())
  || statusFilter.value !== "all"
  || dateFilter.value !== "all"
  || sortBy.value !== "uploaded_desc"
);
const filteredDocuments = computed(() => {
  const keyword = searchTerm.value.trim().toLowerCase();
  const now = Date.now();
  const dayMs = 24 * 60 * 60 * 1000;

  const matched = documents.value.filter((doc) => {
    const filename = String(doc.filename || "").toLowerCase();
    const normalizedStatus = String(doc.status || "ready").toLowerCase();
    const keywordMatched = keyword
      ? filename.includes(keyword) || normalizedStatus.includes(keyword)
      : true;

    const statusMatched = statusFilter.value === "all" || normalizedStatus === statusFilter.value;

    let dateMatched = true;
    if (dateFilter.value !== "all") {
      const uploadedAt = new Date(doc.upload_time || "");
      if (Number.isNaN(uploadedAt.getTime())) {
        dateMatched = false;
      } else if (dateFilter.value === "today") {
        const startOfToday = new Date();
        startOfToday.setHours(0, 0, 0, 0);
        dateMatched = uploadedAt.getTime() >= startOfToday.getTime();
      } else if (dateFilter.value === "7d") {
        dateMatched = uploadedAt.getTime() >= now - 7 * dayMs;
      } else if (dateFilter.value === "30d") {
        dateMatched = uploadedAt.getTime() >= now - 30 * dayMs;
      }
    }

    return keywordMatched && statusMatched && dateMatched;
  });

  const sorted = [...matched];
  sorted.sort((left, right) => {
    const nameLeft = String(left.filename || "");
    const nameRight = String(right.filename || "");
    const sizeLeft = Number(left.size || 0);
    const sizeRight = Number(right.size || 0);
    const statusLeft = String(left.status || "ready");
    const statusRight = String(right.status || "ready");
    const timeLeft = new Date(left.upload_time || "").getTime() || 0;
    const timeRight = new Date(right.upload_time || "").getTime() || 0;

    if (sortBy.value === "uploaded_asc") {
      return timeLeft - timeRight;
    }
    if (sortBy.value === "uploaded_desc") {
      return timeRight - timeLeft;
    }
    if (sortBy.value === "name_asc") {
      return nameLeft.localeCompare(nameRight, "zh-CN");
    }
    if (sortBy.value === "name_desc") {
      return nameRight.localeCompare(nameLeft, "zh-CN");
    }
    if (sortBy.value === "size_asc") {
      return sizeLeft - sizeRight;
    }
    if (sortBy.value === "size_desc") {
      return sizeRight - sizeLeft;
    }
    if (sortBy.value === "status_asc") {
      return statusLeft.localeCompare(statusRight, "zh-CN");
    }
    return 0;
  });

  return sorted;
});
const taskPollingSignature = computed(() =>
  tasks.value.map((task) => `${task.task_id}:${task.status}:${task.progress || 0}`).join("|")
);

function fileKey(file) {
  return `${file.name}-${file.size || 0}-${file.lastModified || 0}`;
}

function collectValidationErrors(files) {
  const errors = [];
  if (files.length > MAX_BATCH_FILES) {
    errors.push(`单次最多上传 ${MAX_BATCH_FILES} 个文件`);
  }
  for (const file of files) {
    const extension = String(file.name || "").split(".").pop()?.toLowerCase();
    if (!extension || !ACCEPTED_EXTENSIONS.has(extension)) {
      errors.push(`${file.name}: 不支持的文件类型`);
      continue;
    }
    if (Number(file.size || 0) > MAX_FILE_SIZE_BYTES) {
      errors.push(`${file.name}: 超过 ${MAX_FILE_SIZE_LABEL}`);
    }
  }
  return errors;
}

async function refreshDocuments() {
  deleteError.value = "";
  try {
    await documentsStore.loadDocuments();
  } catch (_error) {
    deleteError.value = "获取文档失败，请稍后重试。";
  }
}

function handleFileChange(event) {
  const incomingFiles = Array.from(event.target.files || []);
  event.target.value = "";
  if (!incomingFiles.length) {
    return;
  }

  const mergedMap = new Map();
  for (const file of [...selectedFiles.value, ...incomingFiles]) {
    mergedMap.set(fileKey(file), file);
  }
  const mergedFiles = Array.from(mergedMap.values()).slice(0, MAX_BATCH_FILES);
  const validationErrors = collectValidationErrors(mergedFiles);
  if (validationErrors.length) {
    uploadError.value = validationErrors.join("；");
    return;
  }

  uploadError.value = "";
  uploadNotice.value = "";
  selectedFiles.value = mergedFiles;
}

function clearSelectedFiles() {
  selectedFiles.value = [];
}

function removeSelectedFile(file) {
  selectedFiles.value = selectedFiles.value.filter((item) => item !== file);
}

async function handleUpload() {
  if (!selectedFiles.value.length || isSubmitting.value) {
    return;
  }
  isSubmitting.value = true;
  uploadError.value = "";
  uploadNotice.value = "";

  try {
    const results = await documentsStore.createUploadTasks(selectedFiles.value, { concurrency: 3 });
    const successResults = results.filter((result) => result?.success);
    const failedResults = results.filter((result) => !result?.success);

    if (successResults.length) {
      uploadNotice.value = `已提交 ${successResults.length} 个任务，正在处理中。`;
    }
    if (failedResults.length) {
      const failureReason = failedResults
        .map((result) => result?.error)
        .filter(Boolean)
        .slice(0, 3)
        .join("；");
      uploadError.value = `有 ${failedResults.length} 个文件提交失败。${failureReason}`;
    }

    selectedFiles.value = failedResults
      .map((result) => result?.file)
      .filter(Boolean);
    documentsStore.ensureActivePolling();
    refreshTasks();
  } catch (_error) {
    uploadError.value = "上传失败，请稍后重试。";
  } finally {
    isSubmitting.value = false;
  }
}

function resolveTaskDescription(task) {
  if (task.error) {
    return task.error;
  }
  if (task.status === "done") {
    return "解析完成，文档已入库。";
  }
  if (task.status === "failed") {
    return task.message || "任务处理失败，请查看详情并重试。";
  }
  if (task.status === "processing") {
    return "解析处理中，正在写入索引。";
  }
  if (task.status === "retrying") {
    return "正在发起重试任务。";
  }
  return task.message || "任务已排队等待处理。";
}

function taskTone(task) {
  if (task.status === "failed") {
    return "warn";
  }
  if (task.status === "done") {
    return "success";
  }
  return "accent";
}

function humanTaskStatus(status) {
  if (status === "queued") {
    return "排队中";
  }
  if (status === "processing") {
    return "处理中";
  }
  if (status === "retrying") {
    return "重试中";
  }
  if (status === "done") {
    return "已完成";
  }
  if (status === "failed") {
    return "失败";
  }
  return "未知";
}

function humanDocumentStatus(status) {
  const normalized = String(status || "ready").toLowerCase();
  if (normalized === "ready" || normalized === "done") {
    return "就绪";
  }
  if (normalized === "processing" || normalized === "queued" || normalized === "retrying") {
    return "处理中";
  }
  if (normalized === "failed") {
    return "失败";
  }
  return "未知";
}

function isTaskActive(status) {
  return status === "queued" || status === "processing" || status === "retrying";
}

function selectTask(task) {
  if (!task?.task_id) {
    return;
  }
  selectedTaskId.value = task.task_id;
}

function ensureTaskSelection() {
  if (!tasks.value.length) {
    selectedTaskId.value = "";
    return;
  }
  const exists = tasks.value.some((task) => task.task_id === selectedTaskId.value);
  if (!exists) {
    selectedTaskId.value = tasks.value[0].task_id;
  }
}

async function refreshTasks() {
  const activeTasks = tasks.value.filter((task) => isTaskActive(task.status));
  if (!activeTasks.length) {
    if (selectedTask.value?.task_id) {
      await fetchTask(selectedTask.value.task_id);
    }
    return;
  }
  await Promise.all(activeTasks.map((task) => fetchTask(task.task_id)));
}

async function fetchTask(taskId) {
  if (!taskId) {
    return;
  }
  try {
    const data = await documentsStore.pollTask(taskId);
    if (data?.status === "done") {
      await refreshDocuments();
    }
    if (data?.status === "failed") {
      uploadError.value = data.error || data.message || "任务处理失败";
    }
  } catch (_error) {
    uploadError.value = "任务状态不可用，请稍后重试。";
  }
}

async function retryTask(task) {
  if (!task?.task_id) {
    return;
  }
  uploadError.value = "";
  uploadNotice.value = "";
  const result = await documentsStore.retryUpload(task.task_id);
  if (!result?.success) {
    uploadError.value = result?.error || "重试失败";
    return;
  }
  uploadNotice.value = "已发起重试任务，请等待刷新。";
  documentsStore.ensureActivePolling();
}

async function handleDelete(doc) {
  if (!doc?.id) {
    return;
  }
  deleteError.value = "";
  try {
    const success = await documentsStore.removeDocument(doc.id);
    if (!success) {
      deleteError.value = documentsStore.error || "删除失败";
    }
  } catch (_error) {
    deleteError.value = "删除失败，请稍后重试。";
  }
}

function resetDocumentFilters() {
  searchTerm.value = "";
  statusFilter.value = "all";
  dateFilter.value = "all";
  sortBy.value = "uploaded_desc";
}

function formatSize(size) {
  if (!size && size !== 0) {
    return "-";
  }
  const units = ["B", "KB", "MB", "GB"];
  let value = size;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(value >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

function formatTime(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "-";
  }
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function statusClass(status) {
  if (status === "ready" || status === "done") {
    return "status-ready";
  }
  if (status === "processing" || status === "queued" || status === "retrying") {
    return "status-processing";
  }
  if (status === "failed") {
    return "status-failed";
  }
  return "status-default";
}

watch(taskPollingSignature, () => {
  ensureTaskSelection();
  documentsStore.ensureActivePolling();
}, { immediate: true });

onMounted(async () => {
  await refreshDocuments();
  documentsStore.ensureActivePolling();
});

watch(activeGroupId, async () => {
  selectedTaskId.value = "";
  uploadError.value = "";
  uploadNotice.value = "";
  deleteError.value = "";
  await refreshDocuments();
  documentsStore.ensureActivePolling();
});

onBeforeUnmount(() => {
  documentsStore.stopAllPolling();
});
</script>

<style scoped>
.documents-view {
  gap: var(--space-24);
}

.upload-panel {
  display: grid;
  gap: var(--space-16);
}

.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-16);
}

.panel-header h4 {
  margin: 0;
}

.panel-meta {
  margin: 0;
  color: var(--muted);
  font-size: var(--font-size-13);
}

.upload-actions {
  display: flex;
  align-items: center;
  gap: var(--space-12);
}

.upload-hint {
  margin: 0;
  color: var(--muted);
  font-size: var(--font-size-12);
}

.file-input {
  display: inline-flex;
  align-items: center;
  gap: var(--space-8);
  padding: 8px 14px;
  border-radius: 999px;
  border: 1px dashed var(--line);
  background: var(--panel-strong);
  color: var(--text);
  cursor: pointer;
  font-size: var(--font-size-14);
}

.file-input input {
  display: none;
}

.upload-meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-12);
  padding: var(--space-12) var(--space-16);
  border-radius: var(--radius-16);
  border: 1px solid var(--line);
  background: var(--panel-strong);
}

.meta-label {
  color: var(--muted);
  font-size: var(--font-size-12);
  margin-right: var(--space-8);
}

.meta-value {
  font-weight: var(--font-weight-semibold);
}

.progress-row {
  display: flex;
  align-items: center;
  gap: var(--space-12);
}

.progress-track {
  position: relative;
  flex: 1;
  height: 8px;
  border-radius: 999px;
  background: var(--panel-strong);
  border: 1px solid var(--line);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--accent);
  transition: width 0.2s ease;
}

.progress-label {
  font-size: var(--font-size-12);
  color: var(--muted);
  min-width: 44px;
  text-align: right;
}

.error-text {
  margin: 0;
  color: #d14343;
  font-size: var(--font-size-13);
}

.notice-text {
  margin: 0;
  color: #1c8f5b;
  font-size: var(--font-size-13);
}

.task-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: var(--space-16);
}

.task-footer {
  display: flex;
  align-items: center;
  gap: var(--space-8);
}

.task-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-8);
  margin-top: var(--space-8);
}

.task-detail {
  margin-top: var(--space-16);
  padding: var(--space-16);
  border-radius: var(--radius-16);
  border: 1px solid var(--line);
  background: var(--panel-strong);
  display: grid;
  gap: var(--space-12);
}

.task-detail-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-12);
}

.task-detail-head h5 {
  margin: 0;
  font-size: var(--font-size-16);
}

.task-detail-grid {
  margin: 0;
  display: grid;
  grid-template-columns: 120px minmax(0, 1fr);
  gap: var(--space-8) var(--space-12);
}

.task-detail-grid dt {
  color: var(--muted);
  font-size: var(--font-size-12);
}

.task-detail-grid dd {
  margin: 0;
  font-size: var(--font-size-13);
  word-break: break-word;
}

.task-detail-hint {
  margin: 0;
  color: #b36b00;
  font-size: var(--font-size-12);
}

.task-detail-actions {
  margin-top: 0;
  justify-content: flex-start;
}

.document-table {
  display: grid;
  gap: var(--space-12);
}

.table-tools {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  flex-wrap: wrap;
}

.search-input,
.filter-select {
  border-radius: 999px;
  border: 1px solid var(--line);
  background: var(--panel-strong);
  color: var(--text);
  padding: 8px 14px;
  font-size: var(--font-size-13);
}

.search-input {
  min-width: 180px;
}

.filter-select {
  min-width: 140px;
}

.selected-grid {
  display: grid;
  gap: var(--space-12);
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.selected-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-12);
  padding: var(--space-12) var(--space-16);
  border-radius: var(--radius-16);
  border: 1px solid var(--line);
  background: var(--panel-strong);
}

.selected-title {
  margin: 0;
  font-size: var(--font-size-14);
  font-weight: var(--font-weight-semibold);
}

.selected-meta {
  margin: 4px 0 0;
  font-size: var(--font-size-12);
  color: var(--muted);
}

.table-header,
.table-row {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) 120px 120px 160px 120px;
  gap: var(--space-12);
  align-items: center;
  padding: var(--space-12) var(--space-16);
  border-radius: var(--radius-16);
  border: 1px solid var(--line);
  background: var(--panel-strong);
  font-size: var(--font-size-14);
}

.table-header {
  font-size: var(--font-size-12);
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: var(--letter-spacing-wide);
}

.doc-name {
  font-weight: var(--font-weight-semibold);
}

.table-actions {
  display: inline-flex;
  justify-content: flex-end;
}

.ghost-button.small {
  padding: 6px 12px;
  font-size: var(--font-size-12);
}

.status-pill {
  display: inline-flex;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: var(--font-size-12);
  font-weight: var(--font-weight-semibold);
  border: 1px solid transparent;
}

.status-ready {
  color: var(--accent);
  background: var(--accent-soft);
  border-color: color-mix(in srgb, var(--accent) 40%, transparent);
}

.status-processing {
  color: #b36b00;
  background: rgba(227, 150, 34, 0.18);
  border-color: rgba(227, 150, 34, 0.35);
}

.status-failed {
  color: #d14343;
  background: rgba(209, 67, 67, 0.16);
  border-color: rgba(209, 67, 67, 0.3);
}

.status-default {
  color: var(--muted);
  background: var(--panel);
  border-color: var(--line);
}

.empty-state {
  text-align: center;
  padding: var(--space-24);
  border-radius: var(--radius-16);
  border: 1px dashed var(--line);
  background: var(--panel-strong);
}

.empty-state h4 {
  margin: 0 0 8px;
}

.ghost-button,
.primary-button {
  appearance: none;
  border: 1px solid transparent;
  border-radius: 999px;
  padding: 8px 16px;
  font-size: var(--font-size-14);
  cursor: pointer;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
  white-space: nowrap;
}

.ghost-button {
  background: transparent;
  color: var(--text);
  border-color: var(--line);
}

.primary-button {
  background: var(--accent);
  color: #fff;
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.12);
}

.ghost-button:hover,
.primary-button:hover {
  transform: translateY(-1px);
}

.ghost-button:disabled,
.primary-button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
  transform: none;
  box-shadow: none;
}

@media (max-width: 980px) {
  .upload-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .task-detail-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .table-header,
  .table-row {
    grid-template-columns: minmax(0, 1fr);
    gap: var(--space-8);
  }

  .table-actions {
    justify-content: flex-start;
  }
}
</style>
