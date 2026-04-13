import { defineStore } from "pinia";

import {
  createProvider,
  deleteProvider,
  fetchProviders,
  getCurrentUser,
  getProvider,
  login as loginRequest,
  logout as logoutRequest,
  register as registerRequest,
  updateProvider,
} from "../api/auth";
import {
  addAdminGroupMember,
  createAdminGroup,
  fetchAdminGroups,
  fetchAdminUsers,
  removeAdminGroupMember,
} from "../api/admin";

const TOKEN_STORAGE_KEY = "hybrid-agent-token";
const ACTIVE_GROUP_STORAGE_KEY = "hybrid-agent-active-group";

function readStorage(key) {
  if (typeof localStorage === "undefined") {
    return "";
  }
  return localStorage.getItem(key) || "";
}

function normalizeProviderList(data) {
  if (Array.isArray(data)) {
    return data;
  }
  if (Array.isArray(data?.providers)) {
    return data.providers;
  }
  if (Array.isArray(data?.items)) {
    return data.items;
  }
  if (Array.isArray(data?.data)) {
    return data.data;
  }
  return [];
}

function resolveApiError(error, fallback) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) {
    return detail.trim();
  }
  if (typeof error?.message === "string" && error.message.trim()) {
    return error.message.trim();
  }
  return fallback;
}

export const useUserStore = defineStore("user", {
  state: () => ({
    profile: null,
    token: readStorage(TOKEN_STORAGE_KEY),
    adminUsers: [],
    adminGroups: [],
    adminLoading: false,
    adminError: "",
    providers: [],
    providerLoading: false,
    providerError: "",
    settings: {
      activeProviderId: "",
      activeGroupId: readStorage(ACTIVE_GROUP_STORAGE_KEY),
    },
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.token),
    normalizedRole: (state) => String(state.profile?.role || "").toLowerCase(),
    availableGroupIds: (state) => {
      const groupIds = state.profile?.group_ids;
      return Array.isArray(groupIds) ? groupIds.filter(Boolean) : [];
    },
    hasMultipleGroups() {
      return this.availableGroupIds.length > 1;
    },
    activeGroupId(state) {
      if (state.settings.activeGroupId) {
        return state.settings.activeGroupId;
      }
      const groupIds = Array.isArray(state.profile?.group_ids) ? state.profile.group_ids : [];
      return groupIds[0] || "";
    },
    providerAccessLevel(state) {
      const role = String(state.profile?.role || "").toLowerCase();
      const groupRoles = Object.values(state.profile?.group_roles || {}).map((value) =>
        String(value || "").toLowerCase(),
      );
      if (role === "admin" || groupRoles.some((value) => ["admin", "group_admin"].includes(value))) {
        return "manager";
      }
      if (!role) {
        return "unknown";
      }
      return "readonly";
    },
    providerAccessHint() {
      if (this.providerAccessLevel === "manager") {
        return "你可以创建、删除并健康检查 Provider。";
      }
      if (this.providerAccessLevel === "readonly") {
        return "当前账号为只读角色，请联系管理员管理 Provider。";
      }
      return "请先登录后再查看 Provider 配置。";
    },
    canAccessAdmin(state) {
      return String(state.profile?.role || "").toLowerCase() === "admin";
    },
    canManageProviders(state) {
      const role = String(state.profile?.role || "").toLowerCase();
      const groupRoles = Object.values(state.profile?.group_roles || {}).map((value) =>
        String(value || "").toLowerCase(),
      );
      return role === "admin" || groupRoles.some((value) => ["admin", "group_admin"].includes(value));
    },
  },
  actions: {
    setToken(token) {
      this.token = token;
      if (token) {
        localStorage.setItem(TOKEN_STORAGE_KEY, token);
      } else {
        localStorage.removeItem(TOKEN_STORAGE_KEY);
      }
    },
    setProfile(profile) {
      this.profile = profile;
      this.syncActiveGroupId();
    },
    clear() {
      this.profile = null;
      this.token = "";
      this.settings.activeGroupId = "";
      localStorage.removeItem(TOKEN_STORAGE_KEY);
      localStorage.removeItem(ACTIVE_GROUP_STORAGE_KEY);
    },
    syncActiveGroupId() {
      const groups = this.availableGroupIds;
      if (!groups.length) {
        this.settings.activeGroupId = "";
        localStorage.removeItem(ACTIVE_GROUP_STORAGE_KEY);
        return;
      }

      const persisted = localStorage.getItem(ACTIVE_GROUP_STORAGE_KEY) || "";
      const current = this.settings.activeGroupId || persisted;
      const next = groups.includes(current) ? current : groups[0];
      this.settings.activeGroupId = next;
      localStorage.setItem(ACTIVE_GROUP_STORAGE_KEY, next);
    },
    setActiveGroupId(groupId) {
      const next = groupId || "";
      if (next && !this.availableGroupIds.includes(next)) {
        return;
      }
      this.settings.activeGroupId = next;
      if (next) {
        localStorage.setItem(ACTIVE_GROUP_STORAGE_KEY, next);
      } else {
        localStorage.removeItem(ACTIVE_GROUP_STORAGE_KEY);
      }
    },
    async login(payload) {
      const response = await loginRequest(payload);
      const token = response?.data?.access_token || "";
      this.setToken(token);
      const me = await this.fetchCurrentUser();
      return me;
    },
    async register(payload) {
      const response = await registerRequest(payload);
      const token = response?.data?.access_token || "";
      this.setToken(token);
      const me = await this.fetchCurrentUser();
      return me;
    },
    async fetchCurrentUser() {
      if (!this.token) {
        this.profile = null;
        return null;
      }
      try {
        const response = await getCurrentUser();
        this.setProfile(response?.data || null);
        return this.profile;
      } catch (error) {
        this.clear();
        throw error;
      }
    },
    async logout() {
      if (this.token) {
        try {
          await logoutRequest();
        } catch {
          // ignore network/logout errors; local state still cleared
        }
      }
      this.clear();
    },
    setAdminUsers(users) {
      this.adminUsers = Array.isArray(users) ? users : [];
    },
    setAdminGroups(groups) {
      this.adminGroups = Array.isArray(groups) ? groups : [];
    },
    setAdminLoading(isLoading) {
      this.adminLoading = Boolean(isLoading);
    },
    setAdminError(message) {
      this.adminError = message || "";
    },
    setProviders(providers) {
      this.providers = Array.isArray(providers) ? providers : [];
    },
    setProviderLoading(isLoading) {
      this.providerLoading = Boolean(isLoading);
    },
    setProviderError(message) {
      this.providerError = message || "";
    },
    setSettings(nextSettings) {
      this.settings = {
        ...this.settings,
        ...(nextSettings || {}),
      };
    },
    setActiveProviderId(providerId) {
      this.settings.activeProviderId = providerId || "";
    },
    async loadProviders(params = {}) {
      if (!this.canManageProviders) {
        this.setProviders([]);
        this.setProviderError("");
        return [];
      }
      this.setProviderLoading(true);
      this.setProviderError("");
      try {
        const requestParams = {
          ...params,
        };
        if (!requestParams.group_id && this.activeGroupId) {
          requestParams.group_id = this.activeGroupId;
        }
        const response = await fetchProviders(requestParams);
        const providers = normalizeProviderList(response?.data);
        this.setProviders(providers);
        return providers;
      } catch (error) {
        this.setProviderError(resolveApiError(error, "Failed to load providers"));
        throw error;
      } finally {
        this.setProviderLoading(false);
      }
    },
    async fetchProvider(providerId) {
      this.setProviderLoading(true);
      this.setProviderError("");
      try {
        const response = await getProvider(providerId);
        return response?.data || null;
      } catch (error) {
        this.setProviderError(resolveApiError(error, "Failed to load provider"));
        throw error;
      } finally {
        this.setProviderLoading(false);
      }
    },
    async createProvider(payload) {
      this.setProviderLoading(true);
      this.setProviderError("");
      try {
        const response = await createProvider({
          ...payload,
          group_id: payload?.group_id || this.activeGroupId || null,
        });
        await this.loadProviders();
        return response?.data;
      } catch (error) {
        this.setProviderError(resolveApiError(error, "Failed to create provider"));
        throw error;
      } finally {
        this.setProviderLoading(false);
      }
    },
    async updateProvider(providerId, payload) {
      this.setProviderLoading(true);
      this.setProviderError("");
      try {
        const response = await updateProvider(providerId, payload);
        await this.loadProviders();
        return response?.data;
      } catch (error) {
        this.setProviderError(resolveApiError(error, "Failed to update provider"));
        throw error;
      } finally {
        this.setProviderLoading(false);
      }
    },
    async deleteProvider(providerId) {
      this.setProviderLoading(true);
      this.setProviderError("");
      try {
        const response = await deleteProvider(providerId);
        await this.loadProviders();
        if (this.settings.activeProviderId === providerId) {
          this.setActiveProviderId("");
        }
        return response?.data;
      } catch (error) {
        this.setProviderError(resolveApiError(error, "Failed to delete provider"));
        throw error;
      } finally {
        this.setProviderLoading(false);
      }
    },
    async loadAdminUsers() {
      this.setAdminLoading(true);
      this.setAdminError("");
      try {
        const response = await fetchAdminUsers();
        const users = response?.data?.users ?? response?.data ?? [];
        this.setAdminUsers(users);
        return users;
      } catch (error) {
        this.setAdminError(error?.message || "Failed to load users");
        throw error;
      } finally {
        this.setAdminLoading(false);
      }
    },
    async loadAdminGroups() {
      this.setAdminLoading(true);
      this.setAdminError("");
      try {
        const response = await fetchAdminGroups();
        const groups = response?.data?.groups ?? response?.data ?? [];
        this.setAdminGroups(groups);
        return groups;
      } catch (error) {
        this.setAdminError(error?.message || "Failed to load groups");
        throw error;
      } finally {
        this.setAdminLoading(false);
      }
    },
    async createGroup(payload) {
      this.setAdminLoading(true);
      this.setAdminError("");
      try {
        const response = await createAdminGroup(payload);
        await this.loadAdminGroups();
        return response?.data;
      } catch (error) {
        this.setAdminError(error?.message || "Failed to create group");
        throw error;
      } finally {
        this.setAdminLoading(false);
      }
    },
    async addGroupMember(groupId, payload) {
      this.setAdminLoading(true);
      this.setAdminError("");
      try {
        const response = await addAdminGroupMember(groupId, payload);
        await this.loadAdminGroups();
        return response?.data;
      } catch (error) {
        this.setAdminError(error?.message || "Failed to add member");
        throw error;
      } finally {
        this.setAdminLoading(false);
      }
    },
    async removeGroupMember(groupId, userId) {
      this.setAdminLoading(true);
      this.setAdminError("");
      try {
        const response = await removeAdminGroupMember(groupId, userId);
        await this.loadAdminGroups();
        return response?.data;
      } catch (error) {
        this.setAdminError(error?.message || "Failed to remove member");
        throw error;
      } finally {
        this.setAdminLoading(false);
      }
    },
  },
});
