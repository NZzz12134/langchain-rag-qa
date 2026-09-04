<template>
  <div class="sidebar">
    <div class="sidebar-header">
      <el-button type="primary" style="width: 100%" @click="openCreateDialog">
        <el-icon><Plus /></el-icon>&nbsp;新建会话
      </el-button>
    </div>

    <div class="session-list">
      <div
        v-for="s in sessions"
        :key="s.id"
        class="session-item"
        :class="{ active: s.id === currentId }"
        @click="onSelect(s)"
      >
        <div class="session-info">
          <div class="session-title">
            {{ s.title }}
            <el-tag v-if="s.kb_id" size="small" type="info" effect="plain" class="kb-tag">
              {{ kbName(s.kb_id) }}
            </el-tag>
          </div>
          <div class="session-preview">{{ s.last_message_preview || '暂无消息' }}</div>
        </div>
        <el-dropdown trigger="click" @command="(cmd) => onItemCommand(cmd, s)">
          <el-icon class="more-btn" @click.stop><MoreFilled /></el-icon>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="rename">重命名</el-dropdown-item>
              <el-dropdown-item command="delete" divided>
                <span style="color: #f56c6c">删除会话</span>
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>

      <el-empty v-if="!sessions.length" description="暂无会话，点击上方新建" :image-size="60" />
    </div>

    <!-- 新建会话弹窗：标题 + 检索范围（知识库） -->
    <el-dialog v-model="createDialogVisible" title="新建会话" width="440px">
      <el-form label-width="90px">
        <el-form-item label="会话标题">
          <el-input v-model="createForm.title" maxlength="200" placeholder="可留空，将根据首个问题自动生成" />
        </el-form-item>
        <el-form-item label="检索范围">
          <el-select v-model="createForm.kbId" style="width: 100%" placeholder="选择知识库">
            <el-option :value="null" label="全部知识库" />
            <el-option v-for="k in kbs" :key="k.id" :value="k.id" :label="k.name" />
          </el-select>
          <div class="kb-hint">选择后该会话只检索对应知识库；「全部」则跨库检索取最相关</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MoreFilled, Plus } from '@element-plus/icons-vue'
import { kbApi } from '../../api/admin'
import { useSessionStore } from '../../stores/session'

const store = useSessionStore()
const sessions = computed(() => store.sessions)
const currentId = computed(() => store.currentId)

const emit = defineEmits(['changed'])

const kbs = ref([])
const createDialogVisible = ref(false)
const creating = ref(false)
const createForm = reactive({ title: '', kbId: null })

onMounted(async () => {
  kbApi.list().then((data) => (kbs.value = data)).catch(() => {})
})

function kbName(kbId) {
  return kbs.value.find((k) => k.id === kbId)?.name || ''
}

function openCreateDialog() {
  createForm.title = ''
  createForm.kbId = null
  createDialogVisible.value = true
}

async function submitCreate() {
  creating.value = true
  try {
    const session = await store.createSession(createForm.title.trim() || '新会话', createForm.kbId)
    createDialogVisible.value = false
    emit('changed', session.id)
  } catch (_) {
    /* 拦截器已提示 */
  } finally {
    creating.value = false
  }
}

async function onSelect(session) {
  store.setCurrent(session.id)
  emit('changed', session.id)
}

async function onItemCommand(command, session) {
  if (command === 'rename') {
    try {
      const { value } = await ElMessageBox.prompt('请输入新标题', '重命名会话', {
        inputValue: session.title,
        confirmButtonText: '确定',
        cancelButtonText: '取消',
      })
      await store.renameSession(session.id, value || session.title)
    } catch (_) { /* ignore */ }
  } else if (command === 'delete') {
    try {
      await ElMessageBox.confirm(`确定删除会话「${session.title}」吗？`, '提示', {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消',
      })
      await store.removeSession(session.id)
      ElMessage.success('已删除')
      emit('changed', store.currentId)
    } catch (_) { /* ignore */ }
  }
}
</script>

<style scoped>
.sidebar {
  width: 280px;
  background: #fff;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
}
.sidebar-header { padding: 16px; }
.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px 16px;
}
.session-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 4px;
}
.session-item:hover { background: #f5f7fa; }
.session-item.active { background: #ecf5ff; }
.session-info { flex: 1; min-width: 0; }
.session-title {
  font-size: 14px;
  color: #303133;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: flex;
  align-items: center;
  gap: 4px;
}
.kb-tag { max-width: 90px; overflow: hidden; text-overflow: ellipsis; }
.session-preview {
  font-size: 12px;
  color: #909399;
  margin-top: 3px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.more-btn { color: #c0c4cc; }
.more-btn:hover { color: #409eff; }
.kb-hint { font-size: 12px; color: #909399; line-height: 1.5; margin-top: 4px; }
</style>
