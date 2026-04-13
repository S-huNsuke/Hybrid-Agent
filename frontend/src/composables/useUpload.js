import { ref } from "vue";
import { useDocumentsStore } from "../stores/documents";

export function useUpload() {
  const documentsStore = useDocumentsStore();
  const uploading = ref(false);
  const progress = ref(0);
  const status = ref("idle");
  const error = ref(null);
  const taskId = ref(null);
  let pollHandle = null;

  function start() {
    uploading.value = true;
    progress.value = 0;
    status.value = "queued";
    error.value = null;
  }

  function update(value) {
    progress.value = value;
  }

  function finish() {
    uploading.value = false;
    progress.value = 100;
    status.value = "done";
  }

  function _clearPoll() {
    if (pollHandle) {
      window.clearInterval(pollHandle);
      pollHandle = null;
    }
  }

  function _syncFromStore(id) {
    const task = documentsStore.getTask(id);
    if (!task) {
      return;
    }
    status.value = task.status || status.value;
    progress.value = task.progress ?? progress.value;
    error.value = task.error || null;
    if (task.status === "done" || task.status === "failed") {
      uploading.value = false;
      _clearPoll();
    }
  }

  async function startUpload(file) {
    start();
    try {
      const result = await documentsStore.createUploadTask(file);
      if (!result?.success) {
        uploading.value = false;
        status.value = "failed";
        error.value = result?.error || "Upload failed";
        return null;
      }
      taskId.value = result.task.task_id;
      documentsStore.ensurePolling(taskId.value);
      _clearPoll();
      pollHandle = window.setInterval(() => {
        _syncFromStore(taskId.value);
      }, 500);
      return result.task;
    } catch (err) {
      uploading.value = false;
      status.value = "failed";
      error.value = err?.message || "Upload failed";
      return null;
    }
  }

  return {
    uploading,
    progress,
    status,
    error,
    taskId,
    start,
    update,
    finish,
    startUpload,
  };
}
