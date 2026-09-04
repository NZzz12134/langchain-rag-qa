<template>
  <div class="citation-card">
    <div class="citation-header">
      <el-icon><Document /></el-icon>
      <span>引用来源（{{ citations.length }}）</span>
    </div>
    <div
      v-for="(c, idx) in citations"
      :key="c.id"
      class="citation-item"
      @click="showDetail(c)"
    >
      <span class="citation-badge">{{ idx + 1 }}</span>
      <div class="citation-info">
        <div class="citation-meta">
          {{ c.filename || '未知来源' }}
          <template v-if="c.page"> · 第 {{ c.page }} 页</template>
          <template v-else-if="c.row_start"> · 第 {{ c.row_start }}-{{ c.row_end }} 行</template>
          <template v-if="c.heading_path"> · {{ c.heading_path }}</template>
        </div>
        <div class="citation-text">{{ c.text }}</div>
      </div>
    </div>

    <el-dialog v-model="detailVisible" title="引用片段详情" width="640px">
      <div class="detail-meta">
        <div><b>来源：</b>{{ detail?.filename }}</div>
        <div v-if="detail?.page"><b>页码：</b>{{ detail.page }}</div>
        <div v-if="detail?.row_start"><b>行号：</b>{{ detail.row_start }} - {{ detail.row_end }}</div>
        <div v-if="detail?.heading_path"><b>章节：</b>{{ detail.heading_path }}</div>
        <div v-if="detail?.score != null"><b>相关度：</b>{{ (detail.score * 100).toFixed(1) }}%</div>
      </div>
      <div class="detail-text">{{ detail?.text }}</div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Document } from '@element-plus/icons-vue'

defineProps({
  citations: { type: Array, default: () => [] },
})

const detailVisible = ref(false)
const detail = ref(null)

function showDetail(citation) {
  detail.value = citation
  detailVisible.value = true
}
</script>

<style scoped>
.citation-card {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px 12px;
}
.citation-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #475569;
  font-weight: 600;
  margin-bottom: 8px;
}
.citation-item {
  display: flex;
  gap: 8px;
  padding: 6px 0;
  cursor: pointer;
  border-top: 1px dashed #e2e8f0;
}
.citation-item:first-of-type { border-top: none; }
.citation-item:hover .citation-text { color: #409eff; }
.citation-badge {
  width: 20px;
  height: 20px;
  min-width: 20px;
  background: #409eff;
  color: #fff;
  border-radius: 50%;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 2px;
}
.citation-info { flex: 1; min-width: 0; }
.citation-meta { font-size: 12px; color: #94a3b8; margin-bottom: 2px; }
.citation-text {
  font-size: 13px;
  color: #475569;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  transition: color 0.2s;
}
.detail-meta { margin-bottom: 12px; font-size: 13px; color: #606266; line-height: 1.9; }
.detail-text {
  background: #f8fafc;
  border-radius: 8px;
  padding: 14px;
  font-size: 14px;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
