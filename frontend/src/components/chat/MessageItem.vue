<template>
  <div class="message-item">
    <div v-if="message.role === 'user'" class="bubble user-bubble">{{ message.content }}</div>

    <div v-else class="assistant-block">
      <div class="bubble assistant-bubble">
        <CitationCard
          v-if="message.citations?.length"
          :citations="message.citations"
          style="margin-bottom: 10px"
        />
        <!-- 历史消息的引用：按需拉取详情 -->
        <div
          v-if="!message.citations?.length && (message.citations_count || 0) > 0"
          class="citation-hint"
          @click="loadHistoryCitations"
        >
          <el-icon><Document /></el-icon>
          引用 {{ message.citations_count }} 个知识库片段
          <el-icon v-if="historyLoading" class="is-loading"><Loading /></el-icon>
        </div>
        <!-- 生成中状态提示：检索中 → 生成中 → 流式输出 -->
        <div v-if="message.status === 'generating' && !message.content" class="thinking-tip">
          <el-icon class="is-loading"><Loading /></el-icon>
          <template v-if="message.citations?.length">
            已找到 {{ message.citations.length }} 个相关片段，正在生成回答…
          </template>
          <template v-else>
            正在检索知识库…
          </template>
        </div>
        <div
          v-else-if="message.content"
          class="markdown-body"
          :class="{ 'streaming-cursor': streaming && message.status === 'generating' }"
          v-html="renderMarkdown(message.content)"
        ></div>
        <div v-if="message.status === 'failed'" class="error-tip">
          <el-icon><WarningFilled /></el-icon>
          {{ message.error_message || '生成失败，请重试' }}
        </div>
        <div v-if="message.status === 'stopped' && message.content" class="stopped-tip">
          已停止生成
        </div>
      </div>

      <div v-if="message.id && message.status === 'completed'" class="actions">
        <el-button
          link
          size="small"
          :type="message.feedback === 'like' ? 'primary' : 'info'"
          @click="$emit('feedback', 'like')"
        >
          <el-icon><CaretTop /></el-icon> 有帮助
        </el-button>
        <el-button
          link
          size="small"
          :type="message.feedback === 'dislike' ? 'danger' : 'info'"
          @click="$emit('feedback', 'dislike')"
        >
          <el-icon><CaretBottom /></el-icon> 无帮助
        </el-button>
        <el-button v-if="message._stop && streaming" link size="small" type="danger" @click="message._stop()">
          停止生成
        </el-button>
      </div>

      <!-- 历史引用详情弹窗 -->
      <el-dialog v-model="historyDialogVisible" title="引用片段详情" width="640px">
        <div v-loading="historyLoading">
          <div v-for="(c, idx) in historyCitations" :key="c.chunk_id" class="history-cite">
            <div class="cite-meta">
              <span class="citation-badge">{{ idx + 1 }}</span>
              {{ c.filename || '未知来源' }}
              <template v-if="c.page"> · 第 {{ c.page }} 页</template>
              <template v-else-if="c.row_start"> · 第 {{ c.row_start }}-{{ c.row_end }} 行</template>
              <template v-if="c.heading_path"> · {{ c.heading_path }}</template>
            </div>
            <div class="cite-text">{{ c.text }}</div>
          </div>
          <el-empty v-if="!historyLoading && !historyCitations.length" description="暂无引用" />
        </div>
      </el-dialog>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { CaretBottom, CaretTop, Document, Loading, WarningFilled } from '@element-plus/icons-vue'
import { chatApi } from '../../api/chat'
import { renderMarkdown } from '../../utils/markdown'
import CitationCard from './CitationCard.vue'

const props = defineProps({
  message: { type: Object, required: true },
  streaming: { type: Boolean, default: false },
})
defineEmits(['feedback'])

const historyDialogVisible = ref(false)
const historyLoading = ref(false)
const historyCitations = ref([])

async function loadHistoryCitations() {
  if (!props.message.id) return
  historyDialogVisible.value = true
  historyLoading.value = true
  try {
    historyCitations.value = await chatApi.citations(props.message.id)
  } catch (_) {
    /* 拦截器已提示 */
    historyCitations.value = []
  } finally {
    historyLoading.value = false
  }
}
</script>

<style scoped>
.message-item { max-width: 76%; }
.bubble {
  padding: 12px 16px;
  border-radius: 10px;
  font-size: 14px;
  line-height: 1.7;
}
.user-bubble {
  background: #409eff;
  color: #fff;
  white-space: pre-wrap;
  word-break: break-word;
}
.assistant-block { width: 100%; }
.assistant-bubble {
  background: #fff;
  color: #303133;
  border: 1px solid #e4e7ed;
  word-break: break-word;
  min-width: 200px; /* 生成中空内容时气泡不至于过小 */
}
.thinking-tip {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #909399;
  font-size: 14px;
  padding: 4px 0;
}
.citation-hint {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: #409eff;
  cursor: pointer;
  background: #ecf5ff;
  border-radius: 6px;
  padding: 4px 10px;
  margin-bottom: 10px;
}
.citation-hint:hover { background: #d9ecff; }
.actions { margin-top: 6px; padding-left: 4px; }
.error-tip {
  color: #f56c6c;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
}
.stopped-tip { color: #909399; font-size: 13px; margin-top: 8px; }
.history-cite { border: 1px solid #e4e7ed; border-radius: 8px; padding: 10px 12px; margin-bottom: 8px; }
.cite-meta { font-size: 12px; color: #909399; margin-bottom: 6px; display: flex; align-items: center; gap: 6px; }
.citation-badge {
  width: 18px;
  height: 18px;
  min-width: 18px;
  background: #409eff;
  color: #fff;
  border-radius: 50%;
  font-size: 11px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.cite-text { font-size: 13px; color: #303133; white-space: pre-wrap; word-break: break-word; }
</style>
