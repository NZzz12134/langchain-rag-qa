<template>
  <div ref="containerRef" class="message-list">
    <div v-if="!messages.length" class="welcome">
      <div class="welcome-icon">📚</div>
      <h3>欢迎使用知识库问答</h3>
      <p>管理员上传知识文档后，即可针对知识库内容提问，回答会标注引用来源</p>
      <div class="suggestions">
        <div v-for="q in suggestions" :key="q" class="suggestion-chip" @click="$emit('quickAsk', q)">
          {{ q }}
        </div>
      </div>
    </div>

    <div v-for="(msg, idx) in messages" :key="idx" class="message-row" :class="msg.role">
      <MessageItem
        :message="msg"
        :streaming="streaming && idx === messages.length - 1"
        @feedback="(r) => $emit('feedback', msg, r)"
      />
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import MessageItem from './MessageItem.vue'

defineProps({
  messages: { type: Array, default: () => [] },
  streaming: { type: Boolean, default: false },
})
defineEmits(['feedback', 'quickAsk'])

const containerRef = ref(null)
const suggestions = [
  '知识库中有哪些重要内容？',
  '关于XX有哪些说明？',
  '这份文档的要点是什么？',
]

function scrollToBottom(smooth = true) {
  const el = containerRef.value
  if (!el) return
  el.scrollTo({ top: el.scrollHeight, behavior: smooth ? 'smooth' : 'auto' })
}

defineExpose({ scrollToBottom })

onMounted(() => scrollToBottom(false))
</script>

<style scoped>
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 24px 16%;
}
@media (max-width: 1200px) {
  .message-list { padding: 24px 8%; }
}
.welcome {
  text-align: center;
  margin-top: 15vh;
  color: #606266;
}
.welcome-icon { font-size: 52px; margin-bottom: 12px; }
.welcome h3 { color: #303133; margin-bottom: 8px; }
.welcome p { font-size: 14px; color: #909399; }
.suggestions {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-top: 24px;
  flex-wrap: wrap;
}
.suggestion-chip {
  background: #fff;
  border: 1px solid #dcdfe6;
  border-radius: 18px;
  padding: 8px 16px;
  font-size: 13px;
  cursor: pointer;
  color: #606266;
  transition: all 0.2s;
}
.suggestion-chip:hover {
  border-color: #409eff;
  color: #409eff;
}
.message-row { margin-bottom: 20px; }
.message-row.user { display: flex; justify-content: flex-end; }
.message-row.assistant { display: flex; justify-content: flex-start; }
</style>
