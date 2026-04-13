import { ref } from "vue";

function parseEventChunk(rawChunk) {
  const lines = rawChunk.split(/\r?\n/);
  const dataLines = [];
  for (const line of lines) {
    if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }
  if (!dataLines.length) {
    return null;
  }
  const data = dataLines.join("\n").trim();
  if (!data) {
    return null;
  }
  try {
    return JSON.parse(data);
  } catch (error) {
    return { raw: data, parseError: error };
  }
}

export function useSSE() {
  const connected = ref(false);
  const events = ref([]);
  const error = ref(null);

  function connect() {
    connected.value = true;
  }

  function disconnect() {
    connected.value = false;
  }

  function pushEvent(event) {
    events.value.push(event);
  }

  async function stream({
    url,
    method = "POST",
    headers = {},
    body,
    signal,
    onMessage,
    onError,
    onDone,
  }) {
    const controller = signal ? null : new AbortController();
    const activeSignal = signal || controller.signal;
    let doneCalled = false;

    connect();
    try {
      const response = await fetch(url, {
        method,
        headers,
        body,
        signal: activeSignal,
      });

      if (!response.ok || !response.body) {
        const failure = {
          error: `SSE request failed (${response.status})`,
          status: response.status,
        };
        error.value = failure;
        onError?.(failure);
        disconnect();
        return { abort: () => controller?.abort() };
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });

        const chunks = buffer.split(/\r?\n\r?\n/);
        buffer = chunks.pop() || "";

        for (const chunk of chunks) {
          const payload = parseEventChunk(chunk);
          if (!payload) {
            continue;
          }
          pushEvent(payload);

          if (payload.error) {
            error.value = payload;
            onError?.(payload);
            doneCalled = true;
            continue;
          }

          if (payload.done) {
            onDone?.(payload);
            doneCalled = true;
            continue;
          }

          onMessage?.(payload);
        }
      }
    } catch (err) {
      if (err?.name !== "AbortError") {
        const failure = { error: err?.message || "SSE request failed" };
        error.value = failure;
        onError?.(failure);
      }
    } finally {
      disconnect();
      if (!doneCalled) {
        onDone?.({ done: true });
      }
    }

    return { abort: () => controller?.abort() };
  }

  return {
    connected,
    events,
    error,
    connect,
    disconnect,
    pushEvent,
    stream,
  };
}
