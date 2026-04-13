import { createRouter, createWebHistory } from "vue-router";

import { useUserStore } from "../stores/user";

const routes = [
  {
    path: "/",
    name: "overview",
    component: () => import("../views/OverviewView.vue"),
  },
  {
    path: "/login",
    name: "login",
    component: () => import("../views/LoginView.vue"),
    meta: { public: true },
  },
  {
    path: "/chat",
    name: "chat",
    component: () => import("../views/ChatView.vue"),
  },
  {
    path: "/documents",
    name: "documents",
    component: () => import("../views/DocumentsView.vue"),
  },
  {
    path: "/admin",
    name: "admin",
    component: () => import("../views/AdminView.vue"),
    meta: { roles: ["admin"] },
  },
  {
    path: "/settings",
    name: "settings",
    component: () => import("../views/SettingsView.vue"),
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach(async (to) => {
  const userStore = useUserStore();

  if (to.meta.public) {
    if (to.name === "login" && userStore.isAuthenticated) {
      return { name: "overview" };
    }
    return true;
  }

  if (!userStore.isAuthenticated) {
    return {
      name: "login",
      query: { redirect: to.fullPath },
    };
  }

  if (!userStore.profile) {
    try {
      await userStore.fetchCurrentUser();
    } catch {
      return {
        name: "login",
        query: { redirect: to.fullPath },
      };
    }
  }

  const requiredRoles = Array.isArray(to.meta.roles) ? to.meta.roles : [];
  if (requiredRoles.length) {
    const currentRole = String(userStore.profile?.role || "").toLowerCase();
    const allowed = requiredRoles.map((role) => String(role).toLowerCase());
    if (!allowed.includes(currentRole)) {
      return { name: "overview" };
    }
  }

  return true;
});

export default router;
