import { defineStore } from "pinia";
import {
  fetchDocuments,
  uploadDocument,
  deleteDocument,
  fetchUploadTask,
  unwrapApiResponse,
  extractApiError,
} from "../api/documents";
import { useUserStore } from "./user";

export const useDocumentsStore = defineStore("documents", {
  state: () => ({
    items: [],
    loading: false,
    error: null,
    tasks: {},
    taskOrder: [],
  }),
  getters: {
    taskList(state) {
      if (state.taskOrder.length) {
        return state.taskOrder
          .map((taskId) => state.tasks[taskId])
          .filter(Boolean);
      }
      return Object.values(state.tasks);
    },
    getTask(state) {
      return (taskId) => state.tasks[taskId];
    },
  },
  actions: {
    setItems(items) {
      this.items = items;
    },
    setLoading(loading) {
      this.loading = loading;
    },
    setError(error) {
      this.error = error;
    },
    _ensurePollerMap() {
      if (!this._pollers) {
        this._pollers = {};
      }
    },
    _normalizeTaskStatus(status) {
      if (!status) {
        return "queued";
      }
      const value = String(status).toLowerCase();
      if (["queued", "processing", "done", "failed", "retrying"].includes(value)) {
        return value;
      }
      return "queued";
    },
    _ensureTaskOrder(taskId) {
      if (!taskId) {
        return;
      }
      if (!this.taskOrder.includes(taskId)) {
        this.taskOrder = [taskId, ...this.taskOrder];
      }
    },
    _createLocalTaskId() {
      return `local-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
    },
    _normalizeTask(task) {
      if (!task || !task.task_id) {
        return null;
      }
      const status = this._normalizeTaskStatus(task.status);
      const progressValue = Number(task.progress);
      const progress = Number.isFinite(progressValue)
        ? Math.min(Math.max(Math.round(progressValue), 0), 100)
        : 0;
      const now = new Date().toISOString();
      return {
        ...task,
        status,
        progress,
        error: task.error || null,
        message: task.message || "",
        updated_at: task.updated_at || now,
      };
    },
    _setTask(task) {
      const normalizedTask = this._normalizeTask(task);
      if (!normalizedTask) {
        return;
      }
      this._ensureTaskOrder(normalizedTask.task_id);
      this.tasks = {
        ...this.tasks,
        [normalizedTask.task_id]: {
          ...this.tasks[normalizedTask.task_id],
          ...normalizedTask,
        },
      };
    },
    _isTerminal(status) {
      return status === "done" || status === "failed";
    },
    _isActive(status) {
      return status === "queued" || status === "processing" || status === "retrying";
    },
    _createFailedTaskFromFile(file, message) {
      const taskId = this._createLocalTaskId();
      this._setTask({
        task_id: taskId,
        status: "failed",
        progress: 0,
        message,
        error: message,
        document_id: null,
        filename: file?.name,
        size: file?.size,
        file: file || null,
      });
      return taskId;
    },
    async loadDocuments() {
      const userStore = useUserStore();
      this.setLoading(true);
      this.setError(null);
      try {
        const response = await fetchDocuments(
          userStore.activeGroupId ? { group_id: userStore.activeGroupId } : {},
        );
        const data = unwrapApiResponse(response);
        if (data?.success) {
          this.setItems(data.documents || []);
        } else {
          this.setError(data?.error || "Failed to load documents");
        }
      } catch (err) {
        this.setError(extractApiError(err, "Failed to load documents"));
      } finally {
        this.setLoading(false);
      }
    },
    async removeDocument(docId) {
      const userStore = useUserStore();
      this.setLoading(true);
      this.setError(null);
      try {
        const response = await deleteDocument(
          docId,
          userStore.activeGroupId ? { group_id: userStore.activeGroupId } : {},
        );
        const data = unwrapApiResponse(response);
        if (data?.success) {
          this.items = this.items.filter((item) => item.id !== docId);
          return true;
        }
        this.setError(data?.error || "Failed to delete document");
        return false;
      } catch (err) {
        this.setError(extractApiError(err, "Failed to delete document"));
        return false;
      } finally {
        this.setLoading(false);
      }
    },
    async createUploadTask(file, options = {}) {
      const userStore = useUserStore();
      this.setError(null);
      if (!file) {
        return { success: false, error: "missing file", file: null };
      }

      const formData = new FormData();
      formData.append("file", file);

      const sourceTaskId = options?.sourceTaskId || null;
      try {
        const response = await uploadDocument(
          formData,
          userStore.activeGroupId ? { group_id: userStore.activeGroupId } : {},
        );
        const data = unwrapApiResponse(response);
        if (!data?.success) {
          const failureMessage = data?.error || "Upload failed";
          this.setError(failureMessage);
          const failedTaskId = this._createFailedTaskFromFile(file, failureMessage);
          if (sourceTaskId) {
            this._setTask({
              task_id: sourceTaskId,
              status: "failed",
              message: `重试失败：${failureMessage}`,
              error: failureMessage,
              retry_failed_task_id: failedTaskId,
            });
          }
          return { success: false, error: failureMessage, taskId: failedTaskId, file };
        }
        const task = {
          task_id: data.task_id,
          status: data.status || "queued",
          progress: data.progress ?? 0,
          message: data.message,
          error: null,
          document_id: null,
          filename: data.filename || file?.name,
          size: data.size ?? file?.size,
          file,
        };
        this._setTask(task);
        if (sourceTaskId) {
          this._setTask({
            task_id: sourceTaskId,
            status: "failed",
            message: "已发起重试任务，请查看最新任务进度。",
            error: null,
            retry_task_id: task.task_id,
          });
        }
        this.ensurePolling(task.task_id);
        return { success: true, task, file };
      } catch (err) {
        const message = extractApiError(err, "Upload failed");
        this.setError(message);
        const failedTaskId = this._createFailedTaskFromFile(file, message);
        if (sourceTaskId) {
          this._setTask({
            task_id: sourceTaskId,
            status: "failed",
            message: `重试失败：${message}`,
            error: message,
            retry_failed_task_id: failedTaskId,
          });
        }
        return { success: false, error: message, taskId: failedTaskId, file };
      }
    },
    async createUploadTasks(files = [], options = {}) {
      if (!files.length) {
        return [];
      }
      const dedupedFiles = [];
      const seen = new Set();
      for (const file of files) {
        if (!file?.name) {
          // eslint-disable-next-line no-continue
          continue;
        }
        const key = `${file.name}-${file.size || 0}-${file.lastModified || 0}`;
        if (seen.has(key)) {
          // eslint-disable-next-line no-continue
          continue;
        }
        seen.add(key);
        dedupedFiles.push(file);
      }

      if (!dedupedFiles.length) {
        return [];
      }

      const concurrencyValue = Number(options?.concurrency);
      const concurrency = Number.isFinite(concurrencyValue)
        ? Math.min(Math.max(Math.round(concurrencyValue), 1), 6)
        : 3;
      const workerCount = Math.min(concurrency, dedupedFiles.length);
      const results = new Array(dedupedFiles.length);
      let cursor = 0;

      const worker = async () => {
        while (cursor < dedupedFiles.length) {
          const currentIndex = cursor;
          cursor += 1;
          const currentFile = dedupedFiles[currentIndex];
          // eslint-disable-next-line no-await-in-loop
          results[currentIndex] = await this.createUploadTask(currentFile);
        }
      };

      await Promise.all(Array.from({ length: workerCount }, () => worker()));
      return results.filter(Boolean);
    },
    async retryUpload(taskId) {
      const task = this.tasks[taskId];
      if (!task) {
        const error = "任务不存在，无法重试";
        this.setError(error);
        return { success: false, error };
      }
      const file = task.file;
      if (!file) {
        const error = "无法重试：任务未保留原始文件，请重新选择文件上传";
        this.setError(error);
        this._setTask({
          task_id: taskId,
          status: "failed",
          message: error,
          error,
        });
        return { success: false, error };
      }

      this._setTask({
        task_id: taskId,
        status: "failed",
        error: null,
        message: "已提交重试请求，正在创建新任务...",
      });

      return this.createUploadTask(file, { sourceTaskId: taskId });
    },
    async pollTask(taskId) {
      try {
        const response = await fetchUploadTask(taskId);
        const data = unwrapApiResponse(response);
        if (data?.task_id) {
          this._setTask({
            ...data,
            filename: data.filename || this.tasks[taskId]?.filename,
            size: data.size ?? this.tasks[taskId]?.size,
            file: this.tasks[taskId]?.file || null,
            poll_error_count: 0,
          });
          return data;
        }
        return null;
      } catch (_err) {
        return null;
      }
    },
    ensurePolling(taskId, intervalMs = 1500, maxAttempts = 120) {
      this._ensurePollerMap();
      if (!taskId || this._pollers[taskId]) {
        return;
      }
      const existing = this.tasks[taskId];
      if (existing && this._isTerminal(existing.status)) {
        return;
      }
      let attempts = 0;
      let missedCount = 0;
      const tick = async () => {
        attempts += 1;
        const task = await this.pollTask(taskId);
        if (!task) {
          missedCount += 1;
        } else {
          missedCount = 0;
        }
        const status = task?.status || this.tasks[taskId]?.status;
        if (task && this._isTerminal(status)) {
          this.stopPolling(taskId);
          if (status === "done") {
            await this.loadDocuments();
          }
          return;
        }
        if (attempts >= maxAttempts || missedCount >= 8) {
          this._setTask({
            task_id: taskId,
            message: "任务状态轮询已暂停，请手动刷新任务。",
          });
          this.stopPolling(taskId);
          return;
        }
        const nextInterval = missedCount >= 3 ? Math.min(intervalMs * 2, 5000) : intervalMs;
        this._pollers[taskId] = window.setTimeout(tick, nextInterval);
      };
      this._pollers[taskId] = window.setTimeout(tick, intervalMs);
    },
    ensureActivePolling(intervalMs = 1500, maxAttempts = 120) {
      for (const task of this.taskList) {
        if (task?.task_id && this._isActive(task.status)) {
          this.ensurePolling(task.task_id, intervalMs, maxAttempts);
        }
      }
    },
    stopPolling(taskId) {
      this._ensurePollerMap();
      const handle = this._pollers[taskId];
      if (handle) {
        window.clearTimeout(handle);
        delete this._pollers[taskId];
      }
    },
    stopAllPolling() {
      this._ensurePollerMap();
      for (const taskId of Object.keys(this._pollers)) {
        this.stopPolling(taskId);
      }
    },
  },
});
