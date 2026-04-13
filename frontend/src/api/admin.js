import http from "./http";

export function fetchStats() {
  return http.get("/stats");
}

export function fetchAdminUsers() {
  return http.get("/admin/users");
}

export function createAdminUser(payload) {
  return http.post("/admin/users", payload);
}

export function fetchAdminGroups() {
  return http.get("/admin/groups");
}

export function createAdminGroup(payload) {
  return http.post("/admin/groups", payload);
}

export function addAdminGroupMember(groupId, payload) {
  return http.post(`/admin/groups/${groupId}/members`, payload);
}

export function removeAdminGroupMember(groupId, userId) {
  return http.delete(`/admin/groups/${groupId}/members/${userId}`);
}
