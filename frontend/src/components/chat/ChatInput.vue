<template>
  <div class="chat-input-wrap">
    <div class="chat-input-box">
      <el-input
        v-model="text"
        type="textarea"
        :rows="3"
        resize="none"
        :disabled="disabled"
        placeholder="输入您的问题，例如：这份文档的要点是什么？按 Enter 发送，Shift+Enter 换行"
        @keydown.enter.exact.prevent="onEnter"
      />
      <div class="input-footer">
        <span class="hint">回答基于知识库内容，仅供购物参考</span>
        <el-button type="primary" :disabled="disabled || !text.trim()" :loading="disabled" @click="send">
          {{ disabled ? '生成中…' : '发送' }}
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

defineProps({ disabled: { type: Boolean, default: false } })
const emit = defineEmits(['send'])

const text = ref('')

function send() {
  const question = text.value.trim()
  if (!question) return
  emit('send', question)
  text.value = ''
}

/** 中文输入法组词回车（isComposing）不触发发送 */
function onEnter(event) {
  if (!event.isComposing) send()
}
</script>

<style scoped>
.chat-input-wrap {
  padding: 16px 16%;
  background: #f5f7fa;
}
@media (max-width: 1200px) {
  .chat-input-wrap { padding: 16px 8%; }
}
.chat-input-box {
  background: #fff;
  border: 1px solid #dcdfe6;
  border-radius: 12px;
  padding: 10px 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}
.chat-input-box :deep(.el-textarea__inner) {
  border: none;
  box-shadow: none;
  padding: 4px 0;
}
.input-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 6px;
}
.hint { font-size: 12px; color: #c0c4cc; }
</style>
