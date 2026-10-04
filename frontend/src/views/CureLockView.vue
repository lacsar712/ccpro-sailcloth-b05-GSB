<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const isAdmin = computed(() => auth.user?.role === 'admin')

const locked = ref(false)
const loaded = ref(false)
const saving = ref(false)
const error = ref('')
const savedAt = ref(null)
const updatedBy = ref(null)
const updatedAt = ref(null)

async function load() {
  error.value = ''
  try {
    const { data } = await api.get('/cure-lock/')
    locked.value = data.locked
    updatedAt.value = data.updatedAt
    updatedBy.value = data.updatedBy
    loaded.value = true
  } catch {
    error.value = '固化锁定状态加载失败'
  }
}

async function save() {
  if (!isAdmin.value) return
  saving.value = true
  error.value = ''
  try {
    const { data } = await api.patch('/cure-lock/', { locked: locked.value })
    locked.value = data.locked
    updatedAt.value = data.updatedAt
    updatedBy.value = data.updatedBy
    savedAt.value = new Date().toLocaleString()
  } catch (e) {
    error.value = e.response?.data?.detail || '保存失败'
    // 保存失败必须可见：回滚到服务器状态
    await load()
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <h1>固化锁定</h1>
    <p class="sub">
      开启「已固化挂签只读」后，全站已固化布卷即冻结：右侧面板不能再登记浸渍，也不能改回浸渍中或原布。原布与浸渍中操作不受影响。
    </p>
    <p v-if="error" class="error">{{ error }}</p>

    <div class="panel lock-panel" :class="{ 'is-locked': locked }">
      <div class="lock-row">
        <div>
          <p class="lock-title">已固化挂签只读</p>
          <p class="hint">
            当前状态：
            <strong :class="locked ? 'error' : 'ok'">
              {{ locked ? '已锁定' : '未锁定' }}
            </strong>
          </p>
        </div>
        <label class="switch-wrap">
          <input
            v-model="locked"
            type="checkbox"
            role="switch"
            class="lock-switch"
            :disabled="!isAdmin || saving || !loaded"
          />
          <span class="switch-track" aria-hidden="true" />
        </label>
      </div>

      <p v-if="locked" class="lock-note">
        锁定期间，已固化卷的浸渍登记与状态回退将在服务端被拒绝。
      </p>
      <p v-else-if="loaded && isAdmin" class="lock-note">
        未锁定时，各状态布卷操作照旧。
      </p>

      <div v-if="!isAdmin" class="lock-perm hint">
        操作工仅可查看开关状态；如需切换，请联系管理员。
      </div>

      <div class="lock-foot">
        <button
          v-if="isAdmin"
          class="btn"
          type="button"
          :disabled="saving || !loaded"
          @click="save"
        >
          {{ saving ? '保存中…' : '保存开关' }}
        </button>
        <p v-if="savedAt" class="ok">已于 {{ savedAt }} 保存（刷新后仍有效）</p>
      </div>
      <p v-if="updatedAt" class="hint lock-meta">
        上次设置：{{ new Date(updatedAt).toLocaleString() }}<template v-if="updatedBy"> · {{ updatedBy }}</template>
      </p>
    </div>
  </div>
</template>

<style scoped>
.lock-panel {
  max-width: 640px;
  display: grid;
  gap: 14px;
}
.lock-panel.is-locked {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(196, 163, 90, 0.18);
}
.lock-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.lock-title {
  margin: 0 0 6px;
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--navy);
}
.lock-note {
  margin: 0;
  color: var(--muted);
  font-size: 0.92rem;
}
.lock-foot {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}
.lock-meta {
  margin: 0;
  font-size: 0.85rem;
}

.switch-wrap {
  position: relative;
  display: inline-block;
  width: 56px;
  height: 32px;
  flex: none;
}
.lock-switch {
  position: absolute;
  opacity: 0;
  width: 100%;
  height: 100%;
  margin: 0;
  min-width: 0;
  cursor: pointer;
}
.lock-switch:disabled {
  cursor: not-allowed;
}
.switch-track {
  position: absolute;
  inset: 0;
  border-radius: 999px;
  background: var(--canvas-deep);
  border: 1px solid var(--line);
  transition: background 0.15s ease;
}
.switch-track::after {
  content: '';
  position: absolute;
  top: 3px;
  left: 3px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.25);
  transition: transform 0.15s ease;
}
.lock-switch:checked + .switch-track {
  background: var(--navy);
  border-color: var(--navy);
}
.lock-switch:checked + .switch-track::after {
  transform: translateX(24px);
}
.lock-switch:focus-visible + .switch-track {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
</style>
