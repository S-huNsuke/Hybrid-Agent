import { defineStore } from "pinia";

import {
  buildChatHeaders,
  deleteChatSession,
  fetchChatSessions,
  getChatEndpoint,
  renameChatSession,
  resolveModelUsed,
  sendChat,
} from "../api/chat";
import { useSSE } from "../composables/useSSE";
import { useUserStore } from "./user";

const CHAT_STORAGE_KEY = "hybrid-agent-chat-sessions";

function createId(prefix) {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
}

function normalizePayload(payload) {
  return {
    message: payload.message,
    session_id: payload.session_id || null,
    group_id: payload.group_id || null,
    model: payload.model || "auto",
    use_rag: payload.use_rag ?? true,
    stream: payload.stream ?? true,
  };
}

function loadPersistedSessions() {
  if (typeof localStorage === "undefined") {
    return [];
  }
  try {
    const raw = localStorage.getItem(CHAT_STORAGE_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function createSession(overrides = {}) {
  const now = new Date().toISOString();
  return {
    id: createId("session"),
    title: "新会话",
    createdAt: now,
    updatedAt: now,
    selectedModel: "auto",
    messages: [],
    ...overrides,
  };
}

function inferTitle(messages) {
  const firstUserMessage = messages.find((message) => message.role === "user");
  if (!firstUserMessage?.content) {
    return "新会话";
  }
  return firstUserMessage.content.slice(0, 18);
}

function mapRemoteSession(remoteSession, localSession) {
  return {
    id: remoteSession.id,
    title: remoteSession.title || localSession?.title || "新会话",
    createdAt: remoteSession.created_at || localSession?.createdAt || new Date().toISOString(),
    updatedAt:
      remoteSession.updated_at ||
      remoteSession.last_message_at ||
      localSession?.updatedAt ||
      new Date().toISOString(),
    selectedModel: localSession?.selectedModel || "auto",
    messages: localSession?.messages || [],
    userId: remoteSession.user_id || null,
    groupId: remoteSession.group_id || null,
  };
}

export const useChatStore = defineStore("chat", {
  state: () => {
    const persisted = loadPersistedSessions();
    const sessions = persisted.length ? persisted : [createSession()];
    const activeSessionId = sessions[0]?.id || "";
    return {
      sessions,
      activeSessionId,
      selectedModel: sessions[0]?.selectedModel || "auto",
      sending: false,
      streaming: false,
      lastError: "",
    };
  },
  getters: {
    activeSession(state) {
      return (
        state.sessions.find((session) => session.id === state.activeSessionId) ||
        state.sessions[0] ||
        null
      );
    },
    messages(state) {
      const active = state.sessions.find((session) => session.id === state.activeSessionId);
      return active?.messages || [];
    },
    sessionId(state) {
      const active = state.sessions.find((session) => session.id === state.activeSessionId);
      return active?.id || "";
    },
    sessionList(state) {
      return state.sessions;
    },
  },
  actions: {
    persistSessions() {
      if (typeof localStorage === "undefined") {
        return;
      }
      localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(this.sessions));
    },
    async loadRemoteSessions() {
      const userStore = useUserStore();
      try {
        const response = await fetchChatSessions(
          userStore.activeGroupId ? { group_id: userStore.activeGroupId } : {},
        );
        const data = response?.data;
        const remoteSessions = Array.isArray(data?.sessions) ? data.sessions : [];
        const localById = new Map(this.sessions.map((session) => [session.id, session]));
        if (remoteSessions.length) {
          this.sessions = remoteSessions.map((session) =>
            mapRemoteSession(session, localById.get(session.id)),
          );
          if (!this.sessions.find((session) => session.id === this.activeSessionId)) {
            this.activeSessionId = this.sessions[0]?.id || "";
          }
          this.selectedModel =
            this.sessions.find((session) => session.id === this.activeSessionId)?.selectedModel ||
            "auto";
          this.persistSessions();
        }
      } catch {
        // keep local session list as fallback
      }
    },
    ensureActiveSession() {
      if (!this.sessions.length) {
        const session = createSession();
        this.sessions = [session];
        this.activeSessionId = session.id;
        this.selectedModel = session.selectedModel;
        this.persistSessions();
      }
    },
    setActiveSession(sessionId) {
      this.ensureActiveSession();
      const target = this.sessions.find((session) => session.id === sessionId);
      if (!target) {
        return;
      }
      this.activeSessionId = target.id;
      this.selectedModel = target.selectedModel || "auto";
      this.lastError = "";
    },
    createSession(title = "新会话") {
      const userStore = useUserStore();
      const session = createSession({
        title,
        groupId: userStore.activeGroupId || null,
      });
      this.sessions = [session, ...this.sessions];
      this.activeSessionId = session.id;
      this.selectedModel = session.selectedModel;
      this.persistSessions();
      return session;
    },
    async renameSession(sessionId, title) {
      const target = this.sessions.find((session) => session.id === sessionId);
      if (!target) {
        return;
      }
      const nextTitle = title?.trim() || target.title;
      target.title = nextTitle;
      target.updatedAt = new Date().toISOString();
      try {
        await renameChatSession(sessionId, { title: nextTitle });
      } catch {
        // keep local title as fallback
      }
      this.persistSessions();
    },
    async deleteSession(sessionId) {
      this.sessions = this.sessions.filter((session) => session.id !== sessionId);
      if (this.activeSessionId === sessionId) {
        if (!this.sessions.length) {
          const session = createSession();
          this.sessions = [session];
          this.activeSessionId = session.id;
        } else {
          this.activeSessionId = this.sessions[0].id;
        }
        this.selectedModel = this.sessions[0]?.selectedModel || "auto";
      }
      try {
        await deleteChatSession(sessionId);
      } catch {
        // keep local delete as fallback
      }
      this.persistSessions();
    },
    setSelectedModel(model) {
      this.selectedModel = model || "auto";
      const active = this.activeSession;
      if (active) {
        active.selectedModel = this.selectedModel;
        active.updatedAt = new Date().toISOString();
        this.persistSessions();
      }
    },
    appendMessage(message) {
      this.ensureActiveSession();
      const active = this.activeSession;
      if (!active) {
        return;
      }
      active.messages.push(message);
      active.updatedAt = new Date().toISOString();
      active.title = inferTitle(active.messages);
      this.persistSessions();
    },
    updateMessage(id, patch) {
      const target = this.messages.find((msg) => msg.id === id);
      if (!target) {
        return;
      }
      Object.assign(target, patch);
      const active = this.activeSession;
      if (active) {
        active.updatedAt = new Date().toISOString();
        this.persistSessions();
      }
    },
    appendAssistantContent(id, delta) {
      const target = this.messages.find((msg) => msg.id === id);
      if (!target) {
        return;
      }
      target.content += delta;
      const active = this.activeSession;
      if (active) {
        active.updatedAt = new Date().toISOString();
        this.persistSessions();
      }
    },
    reset() {
      const active = this.activeSession;
      if (!active) {
        return;
      }
      active.messages = [];
      active.title = "新会话";
      active.updatedAt = new Date().toISOString();
      this.selectedModel = "auto";
      active.selectedModel = "auto";
      this.sending = false;
      this.streaming = false;
      this.lastError = "";
      this.persistSessions();
    },
    async sendMessage({ message, model, use_rag = true, stream = true }) {
      if (!message) {
        return null;
      }

      this.ensureActiveSession();
      const active = this.activeSession;
      if (!active) {
        return null;
      }

      const sessionId = active.id;
      this.activeSessionId = sessionId;

      const userMessage = {
        id: createId("user"),
        role: "user",
        content: message,
        status: "sent",
        timestamp: new Date().toISOString(),
      };
      this.appendMessage(userMessage);

      const assistantId = createId("assistant");
      const userStore = useUserStore();
      const assistantMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        status: stream ? "streaming" : "pending",
        timestamp: new Date().toISOString(),
        sources: [],
        error: null,
        modelUsed: "",
        meta: {
          toolCalls: [],
          toolResults: [],
        },
      };
      this.appendMessage(assistantMessage);

      this.sending = true;
      this.streaming = stream;
      this.lastError = "";

      const effectiveModel = model || active.selectedModel || this.selectedModel;
      this.setSelectedModel(effectiveModel);

      const payload = normalizePayload({
        message,
        session_id: sessionId,
        group_id: userStore.activeGroupId || active.groupId || null,
        model: effectiveModel,
        use_rag,
        stream,
      });

      if (!stream) {
        try {
          const response = await sendChat(payload);
          const data = response?.data;
          if (data?.success) {
            this.updateMessage(assistantId, {
              content: data.message || "",
              status: "done",
              sources: data.sources || [],
              modelUsed: resolveModelUsed(data, effectiveModel),
            });
            await this.loadRemoteSessions();
          } else {
            const error = data?.error || "请求失败";
            this.updateMessage(assistantId, {
              status: "error",
              error,
            });
            this.lastError = error;
          }
        } catch (err) {
          const error = err?.message || "请求失败";
          this.updateMessage(assistantId, {
            status: "error",
            error,
          });
          this.lastError = error;
        } finally {
          this.sending = false;
          this.streaming = false;
        }
        return assistantId;
      }

      const { stream: streamSSE } = useSSE();
      const endpoint = getChatEndpoint();
      const headers = buildChatHeaders();

      streamSSE({
        url: endpoint,
        method: "POST",
        headers,
        body: JSON.stringify(payload),
        onMessage: (payloadEvent) => {
          if (payloadEvent?.content) {
            this.appendAssistantContent(assistantId, payloadEvent.content);
          }
          if (payloadEvent?.tool_call) {
            assistantMessage.meta.toolCalls.push(payloadEvent.tool_call);
          }
          if (payloadEvent?.tool_result) {
            assistantMessage.meta.toolResults.push(payloadEvent.tool_result);
          }
        },
        onError: (payloadEvent) => {
          const errorMessage =
            payloadEvent?.error || payloadEvent?.raw || "流式请求失败";
          this.updateMessage(assistantId, {
            status: "error",
            error: errorMessage,
          });
          this.lastError = errorMessage;
        },
        onDone: (payloadEvent) => {
          if (payloadEvent?.sources) {
            this.updateMessage(assistantId, {
              sources: payloadEvent.sources,
            });
          }
          this.updateMessage(assistantId, {
            modelUsed: resolveModelUsed(payloadEvent, effectiveModel),
          });
          this.updateMessage(assistantId, {
            status: "done",
          });
          this.sending = false;
          this.streaming = false;
          this.loadRemoteSessions();
        },
      });

      return assistantId;
    },
  },
});
