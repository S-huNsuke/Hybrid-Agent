<template>
  <div class="view-stack admin-view">
    <section v-if="!canAccessAdmin" class="panel">
      <div class="empty-state">
        <h4>无权限访问</h4>
        <p>当前账号不是 admin，管理后台已在 UI 层隐藏相关入口。</p>
      </div>
    </section>

    <template v-else>
    <header class="page-header">
      <div>
        <p class="section-kicker">管理工作台</p>
        <h3>管理后台</h3>
        <p>管理用户、组织与成员权限，支持基础分组协作。</p>
      </div>
      <div class="page-actions">
        <button class="ghost-button" type="button" @click="refreshAll" :disabled="loading">
          {{ loading ? "刷新中..." : "刷新数据" }}
        </button>
      </div>
    </header>

    <section class="card-grid">
      <FeatureCard
        label="用户"
        title="用户总数"
        :description="`${users.length} 位活跃成员`"
        :meta="loading ? '加载中' : '已同步'"
        compact
      />
      <FeatureCard
        label="分组"
        title="分组总数"
        :description="`${groups.length} 个团队`"
        :meta="loading ? '加载中' : '已同步'"
        compact
      />
      <FeatureCard
        label="关系"
        title="成员关系"
        :description="`${memberCount} 条关联`"
        :meta="loading ? '加载中' : '已同步'"
        compact
      />
    </section>

    <section class="panel">
      <div class="panel-header">
        <div>
          <p class="section-kicker">用户</p>
          <h4>用户列表</h4>
        </div>
        <p class="panel-meta">共 {{ users.length }} 位</p>
      </div>
      <div v-if="loading" class="empty-state">
        <h4>加载中...</h4>
        <p>正在获取用户数据。</p>
      </div>
      <div v-else-if="!users.length" class="empty-state">
        <h4>暂无用户</h4>
        <p>请先通过管理接口创建用户。</p>
      </div>
      <div v-else class="table">
        <div class="table-header">
          <span>用户名</span>
          <span>邮箱</span>
          <span>角色</span>
          <span>状态</span>
          <span>所属组</span>
        </div>
        <div v-for="user in users" :key="user.id" class="table-row">
          <span class="strong">{{ user.username }}</span>
          <span>{{ user.email || "-" }}</span>
          <span>
            <span class="pill" :class="user.role === 'admin' ? 'pill-active' : 'pill-muted'">
              {{ user.role }}
            </span>
          </span>
          <span>
            <span class="pill" :class="user.is_active ? 'pill-active' : 'pill-muted'">
              {{ user.is_active ? "启用" : "停用" }}
            </span>
          </span>
          <span class="group-tags">
            <span
              v-for="group in user.groups"
              :key="`${user.id}-${group.group_id}`"
              class="tag"
            >
              {{ group.group_name || group.group_id }} · {{ group.role }}
            </span>
            <span v-if="!user.groups.length" class="muted">暂无</span>
          </span>
        </div>
      </div>
    </section>

    <section class="panel">
      <div class="panel-header">
        <div>
          <p class="section-kicker">分组</p>
          <h4>组列表</h4>
        </div>
        <p class="panel-meta">共 {{ groups.length }} 个</p>
      </div>
      <div v-if="loading" class="empty-state">
        <h4>加载中...</h4>
        <p>正在获取分组数据。</p>
      </div>
      <div v-else-if="!groups.length" class="empty-state">
        <h4>暂无分组</h4>
        <p>请先创建团队或项目组。</p>
      </div>
      <div v-else class="group-grid">
        <article v-for="group in groups" :key="group.id" class="group-card">
          <header class="group-header">
            <div>
              <h5>{{ group.name }}</h5>
              <p>{{ group.description || "暂无描述" }}</p>
            </div>
            <span class="pill">{{ group.members.length }} 人</span>
          </header>
          <div class="group-members">
            <div v-if="!group.members.length" class="muted">暂无成员</div>
            <div v-else class="member-list">
              <div v-for="member in group.members" :key="member.user_id" class="member-row">
                <div>
                  <span class="strong">{{ member.username || member.user_id }}</span>
                  <span class="muted">· {{ member.role }}</span>
                </div>
                <button
                  class="ghost-button small"
                  type="button"
                  @click="removeMember(group.id, member.user_id)"
                >
                  移除
                </button>
              </div>
            </div>
          </div>
        </article>
      </div>
    </section>

    <section class="panel split-panel">
      <div class="panel-block">
        <div class="panel-header">
          <div>
            <p class="section-kicker">新建用户</p>
            <h4>新建账号</h4>
          </div>
        </div>
        <form class="form-stack" @submit.prevent="createUser">
          <label class="field">
            <span class="field-label">用户名</span>
            <input v-model.trim="newUserName" type="text" placeholder="例如：alice" />
          </label>
          <label class="field">
            <span class="field-label">邮箱</span>
            <input v-model.trim="newUserEmail" type="email" placeholder="alice@example.com" />
          </label>
          <label class="field">
            <span class="field-label">初始密码</span>
            <input v-model="newUserPassword" type="password" placeholder="至少 6 位" />
          </label>
          <label class="field">
            <span class="field-label">角色</span>
            <select v-model="newUserRole">
              <option value="member">member</option>
              <option value="group_admin">group_admin</option>
              <option value="admin">admin</option>
            </select>
          </label>
          <label class="field checkbox-field">
            <input v-model="newUserActive" type="checkbox" />
            <span class="field-label">启用账号</span>
          </label>
          <button
            class="primary-button"
            type="submit"
            :disabled="creatingUser || !newUserName || !newUserPassword"
          >
            {{ creatingUser ? "创建中..." : "创建账号" }}
          </button>
          <p v-if="userError" class="error-text">{{ userError }}</p>
        </form>
      </div>

      <div class="panel-block">
        <div class="panel-header">
          <div>
            <p class="section-kicker">新建分组</p>
            <h4>创建分组</h4>
          </div>
        </div>
        <form class="form-stack" @submit.prevent="createGroup">
          <label class="field">
            <span class="field-label">组名</span>
            <input v-model.trim="newGroupName" type="text" placeholder="例如：研发组" />
          </label>
          <label class="field">
            <span class="field-label">描述</span>
            <input v-model.trim="newGroupDesc" type="text" placeholder="用于标注团队用途" />
          </label>
          <button class="primary-button" type="submit" :disabled="creating || !newGroupName">
            {{ creating ? "创建中..." : "创建分组" }}
          </button>
          <p v-if="createError" class="error-text">{{ createError }}</p>
        </form>
      </div>

      <div class="panel-block">
        <div class="panel-header">
          <div>
            <p class="section-kicker">成员关系</p>
            <h4>成员变更</h4>
          </div>
        </div>
        <form class="form-stack" @submit.prevent="addMember">
          <label class="field">
            <span class="field-label">目标组</span>
            <select v-model="selectedGroupId">
              <option disabled value="">请选择分组</option>
              <option v-for="group in groups" :key="group.id" :value="group.id">
                {{ group.name }}
              </option>
            </select>
          </label>
          <label class="field">
            <span class="field-label">成员</span>
            <select v-model="selectedUserId" :disabled="!selectedGroupId">
              <option disabled value="">请选择用户</option>
              <option v-for="user in eligibleUsers" :key="user.id" :value="user.id">
                {{ user.username }}
              </option>
            </select>
          </label>
          <label class="field">
            <span class="field-label">角色</span>
            <select v-model="selectedRole" :disabled="!selectedGroupId">
              <option value="member">member</option>
              <option value="group_admin">group_admin</option>
            </select>
          </label>
          <button
            class="primary-button"
            type="submit"
            :disabled="addingMember || !selectedGroupId || !selectedUserId"
          >
            {{ addingMember ? "提交中..." : "添加成员" }}
          </button>
          <p v-if="memberError" class="error-text">{{ memberError }}</p>
        </form>
      </div>
    </section>

    <p v-if="error" class="error-text">{{ error }}</p>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import {
  createAdminGroup,
  createAdminUser,
  fetchAdminGroups,
  fetchAdminUsers,
  addAdminGroupMember,
  removeAdminGroupMember,
} from "../api/admin";
import FeatureCard from "../components/FeatureCard.vue";
import { useUserStore } from "../stores/user";

const userStore = useUserStore();
const canAccessAdmin = computed(() => userStore.canAccessAdmin);

const loading = ref(false);
const error = ref("");
const users = ref([]);
const groups = ref([]);
const creating = ref(false);
const creatingUser = ref(false);
const addingMember = ref(false);
const newUserName = ref("");
const newUserEmail = ref("");
const newUserPassword = ref("");
const newUserRole = ref("member");
const newUserActive = ref(true);
const userError = ref("");
const newGroupName = ref("");
const newGroupDesc = ref("");
const createError = ref("");
const memberError = ref("");
const selectedGroupId = ref("");
const selectedUserId = ref("");
const selectedRole = ref("member");

const memberCount = computed(() =>
  groups.value.reduce((total, group) => total + (group.members?.length || 0), 0)
);

const selectedGroup = computed(() =>
  groups.value.find((group) => group.id === selectedGroupId.value)
);

const eligibleUsers = computed(() => {
  if (!selectedGroup.value) {
    return users.value;
  }
  const memberIds = new Set(
    (selectedGroup.value.members || []).map((member) => member.user_id)
  );
  return users.value.filter((user) => !memberIds.has(user.id));
});

async function refreshAll() {
  if (!canAccessAdmin.value) {
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    const [usersResponse, groupsResponse] = await Promise.all([
      fetchAdminUsers(),
      fetchAdminGroups(),
    ]);
    users.value = usersResponse.data || [];
    groups.value = groupsResponse.data || [];
  } catch (err) {
    error.value = resolveError(err, "无法获取管理数据，请检查权限或网络。");
  } finally {
    loading.value = false;
  }
}

async function createUser() {
  if (!newUserName.value || !newUserPassword.value) {
    userError.value = "请输入用户名和初始密码。";
    return;
  }
  userError.value = "";
  creatingUser.value = true;
  try {
    await createAdminUser({
      username: newUserName.value,
      email: newUserEmail.value || null,
      password: newUserPassword.value,
      role: newUserRole.value,
      is_active: newUserActive.value,
    });
    newUserName.value = "";
    newUserEmail.value = "";
    newUserPassword.value = "";
    newUserRole.value = "member";
    newUserActive.value = true;
    await refreshAll();
  } catch (err) {
    userError.value = resolveError(err, "创建账号失败，请检查权限或参数。");
  } finally {
    creatingUser.value = false;
  }
}

async function createGroup() {
  if (!newGroupName.value) {
    createError.value = "请输入组名。";
    return;
  }
  createError.value = "";
  creating.value = true;
  try {
    await createAdminGroup({
      name: newGroupName.value,
      description: newGroupDesc.value || null,
    });
    newGroupName.value = "";
    newGroupDesc.value = "";
    await refreshAll();
  } catch (err) {
    createError.value = resolveError(err, "创建失败，请检查权限或名称。");
  } finally {
    creating.value = false;
  }
}

async function addMember() {
  if (!selectedGroupId.value || !selectedUserId.value) {
    memberError.value = "请选择分组与成员。";
    return;
  }
  memberError.value = "";
  addingMember.value = true;
  try {
    await addAdminGroupMember(selectedGroupId.value, {
      user_id: selectedUserId.value,
      role: selectedRole.value,
    });
    selectedUserId.value = "";
    await refreshAll();
  } catch (err) {
    memberError.value = resolveError(err, "添加成员失败，请检查权限或角色。");
  } finally {
    addingMember.value = false;
  }
}

async function removeMember(groupId, userId) {
  memberError.value = "";
  try {
    await removeAdminGroupMember(groupId, userId);
    await refreshAll();
  } catch (err) {
    memberError.value = resolveError(err, "移除失败，请检查权限或成员。");
  }
}

function resolveError(err, fallback) {
  const message = err?.response?.data?.detail || err?.message;
  if (message && typeof message === "string") {
    return message;
  }
  return fallback;
}

onMounted(() => {
  refreshAll();
});
</script>

<style scoped>
.admin-view .page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-20);
  flex-wrap: wrap;
}

.card-grid {
  display: grid;
  gap: var(--space-16);
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 26px;
  padding: 24px;
  box-shadow: var(--shadow-soft);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-12);
  margin-bottom: var(--space-16);
}

.panel-meta {
  font-size: var(--font-size-12);
  color: var(--muted);
}

.table {
  display: grid;
  gap: var(--space-12);
}

.table-header,
.table-row {
  display: grid;
  grid-template-columns: minmax(150px, 1fr) minmax(180px, 1.15fr) minmax(110px, 0.75fr) minmax(110px, 0.75fr) minmax(240px, 1.8fr);
  gap: var(--space-12);
  align-items: start;
}

.table-header {
  font-size: var(--font-size-12);
  text-transform: uppercase;
  letter-spacing: var(--letter-spacing-wide);
  color: var(--muted);
}

.table-row {
  padding: 14px 0;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 60%, transparent);
}

.group-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-8);
}

.tag {
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: var(--font-size-12);
}

.group-grid {
  display: grid;
  gap: var(--space-16);
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
}

.group-card {
  border: 1px solid var(--line);
  border-radius: 22px;
  padding: 18px;
  background: var(--panel-strong);
  box-shadow: var(--shadow-soft);
}

.group-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-12);
  margin-bottom: var(--space-12);
}

.group-header h5 {
  margin: 0;
  font-size: var(--font-size-20);
}

.pill {
  padding: 2px 10px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: var(--font-size-12);
}

.member-list {
  display: grid;
  gap: var(--space-8);
}

.member-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-12);
  padding: 10px 12px;
  border-radius: 16px;
  background: var(--panel);
}

.split-panel {
  display: grid;
  gap: var(--space-16);
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
}

.panel-block {
  display: grid;
  gap: var(--space-12);
}

.form-stack {
  display: grid;
  gap: 14px;
}

.field {
  display: grid;
  gap: var(--space-8);
}

.field input,
.field select {
  min-height: 44px;
  padding: 10px 14px;
  border-radius: 16px;
  border: 1px solid color-mix(in srgb, var(--line) 75%, transparent);
  background: color-mix(in srgb, var(--panel-strong) 96%, transparent);
  color: var(--text);
}

.field-label {
  font-size: var(--font-size-12);
  color: var(--muted);
}

.strong {
  font-weight: var(--font-weight-600);
}

.muted {
  color: var(--muted);
  font-size: var(--font-size-12);
}

.ghost-button {
  border: 1px solid var(--line);
  background: transparent;
  color: var(--text);
  padding: 6px 12px;
  border-radius: 14px;
}

.ghost-button.small {
  padding: 4px 10px;
  font-size: var(--font-size-12);
}

.primary-button {
  background: var(--accent);
  color: #fff;
  border: none;
  min-height: 44px;
  padding: 8px 16px;
  border-radius: 16px;
}

.error-text {
  margin-top: var(--space-8);
  color: #e04848;
}

.empty-state {
  padding: 20px;
  border-radius: 20px;
  background: var(--panel-strong);
}

@media (max-width: 1180px) {
  .table-header {
    display: none;
  }

  .table-row {
    grid-template-columns: 1fr;
    gap: 10px;
    padding: 16px;
    border: 1px solid color-mix(in srgb, var(--line) 60%, transparent);
    border-radius: 20px;
    background: color-mix(in srgb, var(--panel-strong) 92%, transparent);
    margin-bottom: 10px;
  }

  .member-row,
  .group-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
