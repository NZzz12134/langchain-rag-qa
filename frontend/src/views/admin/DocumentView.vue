<template>
  <div>
    <div class="page-header">
      <h3>文档管理</h3>
      <div class="header-actions">
        <el-select v-model="filterKb" placeholder="全部知识库" clearable style="width: 180px" @change="onFilterKbChange">
          <el-option v-for="k in kbs" :key="k.id" :label="k.name" :value="k.id" />
        </el-select>
        <el-select v-model="filterStatus" placeholder="全部状态" clearable style="width: 140px" @change="onFilterChange">
          <el-option label="待解析" value="pending" />
          <el-option label="解析中" value="parsing" />
          <el-option label="解析成功" value="succeeded" />
          <el-option label="解析失败" value="failed" />
        </el-select>
        <el-input
          v-model="filterKeyword"
          placeholder="搜索文件名"
          clearable
          style="width: 200px"
          @keyup.enter="onFilterChange"
          @clear="onFilterChange"
        >
          <template #append>
            <el-button @click="fetchList"><el-icon><Search /></el-icon></el-button>
          </template>
        </el-input>
        <el-upload
          :show-file-list="false"
          :http-request="onUpload"
          :disabled="!uploadKb"
          accept=".pdf,.docx,.xlsx,.csv,.md,.markdown,.txt"
        >
          <el-button type="primary" :disabled="!uploadKb">
            <el-icon><Upload /></el-icon>&nbsp;上传文档
          </el-button>
        </el-upload>
        <el-button @click="openUrlDialog" :disabled="!uploadKb">
          <el-icon><Link /></el-icon>&nbsp;抓取网页
        </el-button>
      </div>
    </div>

    <div class="upload-tip">
      <span>上传目标知识库：</span>
      <el-select v-model="uploadKb" placeholder="请先选择知识库" size="small" style="width: 200px" @change="onUploadKbChange">
        <el-option v-for="k in kbs" :key="k.id" :label="k.name" :value="k.id" />
      </el-select>
      <span class="tip-text">支持 pdf / docx / xlsx / csv / md / txt，单文件 ≤ 50MB；切换后下方列表同步过滤</span>
    </div>

    <el-table :data="docs" v-loading="loading" border stripe>
      <el-table-column prop="filename" label="文件名" min-width="220" show-overflow-tooltip>
        <template #default="{ row }">
          <el-link v-if="row.file_type === 'url'" :href="row.source_url" target="_blank" type="primary">
            {{ row.filename }}
          </el-link>
          <span v-else>{{ row.filename }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="file_type" label="类型" width="80" align="center">
        <template #default="{ row }">
          <el-tag size="small" type="info">{{ row.file_type.toUpperCase() }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="大小" width="90" align="center">
        <template #default="{ row }">{{ formatSize(row.file_size) }}</template>
      </el-table-column>
      <el-table-column label="解析状态" width="140" align="center">
        <template #default="{ row }">
          <el-tag :type="statusType(row.parse_status)" size="small">
            {{ statusLabel(row.parse_status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="进度 / 分块" width="120" align="center">
        <template #default="{ row }">
          <el-progress
            v-if="row.parse_status === 'parsing'"
            :percentage="row.parse_progress"
            :stroke-width="8"
          />
          <span v-else-if="row.parse_status === 'succeeded'">{{ row.chunk_count }} 块</span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="错误信息" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">
          <el-tooltip v-if="row.error_message" :content="row.error_message" placement="top">
            <span style="color: #f56c6c; font-size: 12px">{{ row.error_message }}</span>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="上传时间" width="160">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="220" align="center">
        <template #default="{ row }">
          <el-button v-if="row.parse_status === 'succeeded'" link type="primary" @click="showChunks(row)">
            分块预览
          </el-button>
          <el-button
            v-if="['succeeded', 'failed'].includes(row.parse_status)"
            link
            type="primary"
            @click="onReparse(row)"
          >
            重新解析
          </el-button>
          <el-button v-if="row.parse_status === 'failed'" link type="warning" @click="onRetry(row)">
            重试
          </el-button>
          <el-button link type="danger" @click="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="page"
      :page-size="pageSize"
      :total="total"
      layout="total, prev, pager, next"
      style="margin-top: 16px; justify-content: flex-end"
      @current-change="fetchList"
    />

    <el-dialog v-model="urlDialog" title="抓取网页" width="480px">
      <el-form label-width="70px">
        <el-form-item label="URL" required>
          <el-input v-model="urlInput" placeholder="https://example.com/product/123" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="urlDialog = false">取消</el-button>
        <el-button type="primary" @click="submitUrl">开始抓取</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="chunkDialog" :title="`分块预览 - ${chunkDoc?.filename || ''}`" width="720px">
      <el-pagination
        v-model:current-page="chunkPage"
        :page-size="10"
        :total="chunkTotal"
        layout="total, prev, pager, next"
        small
        style="margin-bottom: 10px"
        @current-change="loadChunks"
      />
      <div v-for="c in chunks" :key="c.id" class="chunk-item">
        <div class="chunk-meta">
          #{{ c.seq }}
          <template v-if="c.page_number"> · 第 {{ c.page_number }} 页</template>
          <template v-if="c.row_start"> · 第 {{ c.row_start }}-{{ c.row_end }} 行</template>
          <template v-if="c.heading_path"> · {{ c.heading_path }}</template>
        </div>
        <div class="chunk-content">{{ c.content }}</div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Link, Search, Upload } from '@element-plus/icons-vue'
import { documentApi, kbApi } from '../../api/admin'

const kbs = ref([])
const docs = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = 20
const total = ref(0)
const filterKb = ref(null)
const filterStatus = ref(null)
const filterKeyword = ref('')
const uploadKb = ref(null)

const urlDialog = ref(false)
const urlInput = ref('')

const chunkDialog = ref(false)
const chunkDoc = ref(null)
const chunks = ref([])
const chunkPage = ref(1)
const chunkTotal = ref(0)

let pollTimer = null

function statusType(status) {
  return { pending: 'info', parsing: 'warning', succeeded: 'success', failed: 'danger' }[status]
}
function statusLabel(status) {
  return { pending: '待解析', parsing: '解析中', succeeded: '解析成功', failed: '解析失败' }[status]
}
function formatSize(bytes) {
  if (bytes == null) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}
function formatTime(t) {
  return t ? t.replace('T', ' ').slice(0, 19) : '-'
}

/** 上传目标知识库变更：列表过滤双向联动（上传目标和列表过滤始终一致，避免传错库） */
function onUploadKbChange(val) {
  filterKb.value = val
  page.value = 1
  fetchList()
}

/** 列表过滤变更：同步上传目标 + 重置页码 */
function onFilterKbChange(val) {
  uploadKb.value = val
  page.value = 1
  fetchList()
}

/** 状态/关键词过滤变更：重置页码（防止停在越界页显示空表） */
function onFilterChange() {
  page.value = 1
  fetchList()
}

async function fetchList() {
  loading.value = true
  try {
    const data = await documentApi.list({
      page: page.value,
      page_size: pageSize,
      kb_id: filterKb.value || undefined,
      status: filterStatus.value || undefined,
      keyword: filterKeyword.value || undefined,
    })
    docs.value = data.items
    total.value = data.total
    // 有解析中的任务则 3s 轮询
    const hasActive = data.items.some((d) => ['pending', 'parsing'].includes(d.parse_status))
    if (hasActive && !pollTimer) {
      pollTimer = setInterval(fetchList, 3000)
    } else if (!hasActive && pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  } catch (_) {
    // 拦截器已提示；轮询失败静默（下次轮询自恢复）
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  } finally {
    loading.value = false
  }
}

async function onUpload({ file }) {
  if (!uploadKb.value) {
    ElMessage.warning('请先选择目标知识库')
    return
  }
  try {
    await documentApi.upload(uploadKb.value, file)
    ElMessage.success('上传成功，后台解析中')
    fetchList()
  } catch (_) { /* 拦截器已提示 */ }
}

async function openUrlDialog() {
  urlInput.value = ''
  urlDialog.value = true
}

async function submitUrl() {
  if (!urlInput.value.startsWith('http')) {
    ElMessage.warning('请输入合法的 http(s) 链接')
    return
  }
  if (!uploadKb.value) {
    ElMessage.warning('请先选择目标知识库')
    return
  }
  try {
    await documentApi.createUrl(uploadKb.value, urlInput.value)
    ElMessage.success('已提交抓取任务')
    urlDialog.value = false
    fetchList()
  } catch (_) {
    /* 拦截器已提示 */
  }
}

async function onReparse(row) {
  try {
    await documentApi.reparse(row.id)
    ElMessage.success('已重新提交解析')
    fetchList()
  } catch (_) {
    /* 拦截器已提示 */
  }
}

async function onRetry(row) {
  try {
    await documentApi.retry(row.id)
    ElMessage.success('已重试')
    fetchList()
  } catch (_) {
    /* 拦截器已提示 */
  }
}

async function onDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除「${row.filename}」吗？其分块与向量索引将一并删除。`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await documentApi.remove(row.id)
    ElMessage.success('已删除')
    fetchList()
  } catch (_) { /* ignore */ }
}

async function showChunks(row) {
  chunkDoc.value = row
  chunkPage.value = 1
  chunkDialog.value = true
  await loadChunks()
}

async function loadChunks() {
  const data = await documentApi.chunks(chunkDoc.value.id, { page: chunkPage.value, page_size: 10 })
  chunks.value = data.items
  chunkTotal.value = data.total
}

onMounted(async () => {
  kbs.value = await kbApi.adminList()
  if (kbs.value.length) {
    uploadKb.value = kbs.value[0].id
    filterKb.value = kbs.value[0].id // 初始列表与上传目标一致
  }
  fetchList()
})

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-wrap: wrap;
  gap: 10px;
}
.header-actions { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.upload-tip {
  margin-bottom: 14px;
  font-size: 13px;
  color: #606266;
  display: flex;
  align-items: center;
  gap: 8px;
}
.tip-text { color: #909399; font-size: 12px; }
.chunk-item { border: 1px solid #e4e7ed; border-radius: 8px; padding: 10px 12px; margin-bottom: 8px; }
.chunk-meta { font-size: 12px; color: #909399; margin-bottom: 6px; }
.chunk-content { font-size: 13px; color: #303133; white-space: pre-wrap; word-break: break-word; }
</style>
