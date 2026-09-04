<template>
  <div class="chat-layout">
    <SessionSidebar @changed="onSessionChanged" />

    <div class="chat-main">
      <div class="chat-header">
        <div class="header-left">
          <b>{{ currentTitle }}</b>
          <el-tag v-if="currentKbName" size="small" type="info" style="margin-left: 8px">
            知识库：{{ currentKbName }}
          </el-tag>
        </div>
        <div class="header-right">
          <el-dropdown @command="onCommand">
            <span class="user-chip">
              <el-avatar :size="26">{{ userInitial }}</el-avatar>
              {{ auth.user?.username }}
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">个人中心 / 修改密码</el-dropdown-item>
                <el-dropdown-item v-if="auth.isAdmin" command="admin" divided>知识库管理后台</el-dropdown-item>
                <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>

      <MessageList
        ref="messageListRef"
        :messages="messages"
        :streaming="isStreaming"
        @feedback="onFeedback"
        @quick-ask="onSend"
      />

      <ChatInput :disabled="isStreaming" @send="onSend" />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { chatApi } from '../api/chat'
import { kbApi } from '../api/admin'
import { sessionApi } from '../api/session'
import ChatInput from '../components/chat/ChatInput.vue'
import MessageList from '../components/chat/MessageList.vue'
import SessionSidebar from '../components/chat/SessionSidebar.vue'
import { useAuthStore } from '../stores/auth'
import { useSessionStore } from '../stores/session'

const router = useRouter()
const auth = useAuthStore()
const sessionStore = useSessionStore()

const messages = ref([])
// 当前活动流的会话 id；null = 无流。绑定到会话而非全局，切换会话时可中止旧流
const streamingSessionId = ref(null)
let currentStreamAbort = null
let loadSeq = 0 // loadMessages 竞态守卫：只接受最新一次请求的结果

const kbs = ref([])
const messageListRef = ref(null)

const currentTitle = computed(
  () => sessionStore.sessions.find((s) => s.id === sessionStore.currentId)?.title || '新会话'
)
const currentKbName = computed(() => {
  const session = sessionStore.sessions.find((s) => s.id === sessionStore.currentId)
  if (!session?.kb_id) return null
  return kbs.value.find((k) => k.id === session.kb_id)?.name || null
})
const userInitial = computed(() => (auth.user?.username || '?').slice(0, 1).toUpperCase())
const isStreaming = computed(() => streamingSessionId.value !== null)

onMounted(async () => {
  // kb 列表只用于展示 tag，失败不应拖垮会话列表（独立容错）
  kbApi.list().then((data) => (kbs.value = data)).catch(() => {})

  try {
    const sessions = await sessionStore.fetchSessions()
    // 校验 currentId 仍在列表中（换账号登录等场景下可能残留），不在则纠正
    if (
      sessionStore.currentId &&
      !sessions.some((s) => s.id === sessionStore.currentId)
    ) {
      sessionStore.setCurrent(null)
    }
    if (sessionStore.currentId) {
      await loadMessages(sessionStore.currentId)
    } else if (sessions.length) {
      sessionStore.setCurrent(sessions[0].id)
      await loadMessages(sessions[0].id)
    }
  } catch (_) {
    /* 拦截器已提示 */
  }
})

/** 加载历史消息（带竞态守卫：快速切换会话时旧响应被丢弃） */
async function loadMessages(sessionId) {
  const seq = ++loadSeq
  const data = await sessionApi.messages(sessionId, { page: 1, page_size: 200 })
  if (seq !== loadSeq) return // 已有更新的加载请求
  messages.value = data.items.map((m) => ({ ...m, citations: [] }))
  scrollToBottom(false)
}

/** 侧边栏会话切换 / 新建 / 删除：中止不属于目标会话的流，重载消息区 */
async function onSessionChanged(sessionId) {
  if (streamingSessionId.value && streamingSessionId.value !== sessionId) {
    currentStreamAbort?.()
  }
  if (sessionId) {
    await loadMessages(sessionId)
  } else {
    loadSeq++ // 使在途的旧加载结果失效
    messages.value = []
  }
}

async function onSend(question) {
  // 并发保护：流进行中直接拒绝（双 Enter/连点场景）
  if (streamingSessionId.value) return
  streamingSessionId.value = '' // 先占位，防 createSession 网络窗口期重复进入

  try {
    // 未选择会话时自动创建
    if (!sessionStore.currentId) {
      await sessionStore.createSession()
    }
    const sessionId = sessionStore.currentId
    streamingSessionId.value = sessionId

    const userMsg = { role: 'user', content: question, status: 'completed' }
    const assistantMsg = {
      role: 'assistant',
      content: '',
      status: 'generating',
      citations: [],
      feedback: null,
    }
    messages.value.push(userMsg, assistantMsg)
    scrollToBottom()

    const { abort, promise } = chatApi.stream(sessionId, question)
    currentStreamAbort = abort

    const stopStreaming = () => {
      abort()
      assistantMsg.status = assistantMsg.content ? 'stopped' : 'failed'
      assistantMsg.error_message = '已停止生成'
    }
    assistantMsg._stop = stopStreaming

    try {
      const events = await promise
      for (const ev of events) {
        if (ev.event === 'citations') {
          assistantMsg.citations = ev.data?.citations || []
        } else if (ev.event === 'token') {
          assistantMsg.content += ev.data?.content || ''
          scrollToBottom(true)
        } else if (ev.event === 'done') {
          assistantMsg.id = ev.data?.message_id
          assistantMsg.status = 'completed'
          assistantMsg.citations_count = assistantMsg.citations.length
        } else if (ev.event === 'error') {
          assistantMsg.status = 'failed'
          assistantMsg.error_message = ev.data?.message || '生成失败'
        }
      }
      if (assistantMsg.status === 'generating') {
        assistantMsg.status = 'completed'
        assistantMsg.citations_count = assistantMsg.citations.length
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        assistantMsg.status = assistantMsg.content ? 'stopped' : 'failed'
      } else {
        assistantMsg.status = 'failed'
        assistantMsg.error_message = err.message || '生成失败'
      }
    } finally {
      streamingSessionId.value = null
      currentStreamAbort = null
      // 标题可能已被后端自动生成，刷新会话列表
      sessionStore.fetchSessions().catch(() => {})
    }
  } catch (_) {
    streamingSessionId.value = null
    currentStreamAbort = null
  }
}

async function onFeedback(message, rating) {
  if (message.feedback === rating) {
    await chatApi.removeFeedback(message.id)
    message.feedback = null
  } else {
    await chatApi.feedback(message.id, { rating })
    message.feedback = rating
  }
}

function onCommand(command) {
  if (command === 'logout') {
    auth.logout()
    router.push('/login')
  } else if (command === 'profile') {
    router.push('/profile')
  } else if (command === 'admin') {
    router.push('/admin')
  }
}

function scrollToBottom(smooth = true) {
  requestAnimationFrame(() => {
    messageListRef.value?.scrollToBottom(smooth)
  })
}
</script>

<style scoped>
.chat-layout {
  display: flex;
  height: 100%;
  background: #f5f7fa;
}
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.chat-header {
  height: 56px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
}
.header-left { display: flex; align-items: center; }
.user-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: #303133;
  font-size: 14px;
  outline: none;
}
</style>
