<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const isAdmin = computed(() => auth.user?.role === 'admin')

const loading = ref(true)
const saving = ref(false)
const serverValue = ref(false)
const switchValue = ref(false)
const updatedAt = ref('')
const error = ref('')
const saved = ref(false)

const dirty = computed(() => switchValue.value !== serverValue.value)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get('/settings/cure-lock/')
    serverValue.value = !!data.curedReadonly
    switchValue.value = !!data.curedReadonly
    updatedAt.value = data.updated_at || ''
  } catch {
    error.value = '锁定状态加载失败'
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  error.value = ''
  saved.value = false
  try {
    const { data } = await api.patch('/settings/cure-lock/', {
      curedReadonly: switchValue.value,
    })
    serverValue.value = !!data.curedReadonly
    switchValue.value = !!data.curedReadonly
    updatedAt.value = data.updated_at || ''
    saved.value = true
  } catch (e) {
    error.value =
      e.response?.data?.curedReadonly?.[0] ||
      e.response?.data?.detail ||
      '保存失败'
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="lock-page">
    <header class="rack-head">
      <div>
        <h1>固化锁定</h1>
        <p class="sub">
          开启后，全站已固化挂签进入只读：已固化卷不得再登记浸渍，也不得改回浸渍中或原布；原布与浸渍中操作照旧。
        </p>
      </div>
    </header>

    <p v-if="error" class="error">{{ error }}</p>

    <section class="panel lock-card" :aria-busy="loading">
      <div class="lock-switch-row">
        <label class="lock-switch" :class="{ 'is-on': switchValue, 'is-locked': !isAdmin }">
          <input
            v-model="switchValue"
            type="checkbox"
            role="switch"
            :aria-checked="switchValue"
            :disabled="!isAdmin || loading || saving"
          />
          <span class="lock-track" aria-hidden="true"><span class="lock-thumb" /></span>
          <span class="lock-state">{{ switchValue ? '已锁定 · 只读' : '未锁定' }}</span>
        </label>
      </div>

      <p v-if="!isAdmin" class="hint lock-notice">
        操作工仅可查看当前状态；开关由管理员保管。
      </p>
      <p v-else-if="switchValue" class="hint lock-notice">
        锁定生效中：已固化卷面板的浸渍登记与改态按钮将停用，并由服务端强制拦截。
      </p>
      <p v-else class="hint lock-notice">
        当前未锁定，各状态布卷可照常登记浸渍、切换状态。
      </p>

      <p v-if="updatedAt" class="hint lock-updated">
        上次变更：{{ new Date(updatedAt).toLocaleString() }}
      </p>

      <div v-if="isAdmin" class="lock-actions">
        <button
          class="btn"
          type="button"
          :disabled="!dirty || saving || loading"
          @click="save"
        >
          {{ saving ? '保存中…' : '保存开关' }}
        </button>
        <button
          class="btn secondary"
          type="button"
          :disabled="!dirty || saving || loading"
          @click="switchValue = serverValue; saved = false"
        >
          撤销
        </button>
        <span v-if="saved" class="lock-saved">已保存，刷新后仍然有效。</span>
      </div>
    </section>
  </div>
</template>

<style scoped>
.lock-card {
  max-width: 640px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 28px;
}

.lock-switch-row {
  display: flex;
  align-items: center;
}

.lock-switch {
  display: inline-flex;
  align-items: center;
  gap: 14px;
  cursor: pointer;
  user-select: none;
}

.lock-switch.is-locked {
  cursor: default;
}

.lock-switch input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}

.lock-track {
  position: relative;
  width: 58px;
  height: 30px;
  border-radius: 999px;
  background: var(--canvas-deep);
  border: 1px solid var(--line);
  transition: background 0.18s ease;
  flex: none;
}

.lock-thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 1px 3px rgba(11, 31, 51, 0.35);
  transition: transform 0.18s ease;
}

.lock-switch.is-on .lock-track {
  background: var(--navy);
}

.lock-switch.is-on .lock-thumb {
  transform: translateX(28px);
}

.lock-switch input:focus-visible + .lock-track {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.lock-state {
  font-size: 1.08rem;
  font-weight: 700;
  color: var(--navy);
}

.lock-notice {
  margin: 0;
}

.lock-updated {
  margin: 0;
  font-size: 0.9rem;
}

.lock-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.lock-saved {
  color: var(--ok);
  font-size: 0.92rem;
}
</style>
