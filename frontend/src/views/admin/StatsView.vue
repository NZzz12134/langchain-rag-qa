<template>
  <div>
    <div class="page-header"><h3>数据看板</h3></div>

    <el-row :gutter="16" v-loading="loading">
      <el-col :span="4" v-for="card in cards" :key="card.label">
        <el-card class="stat-card">
          <div class="stat-value">{{ card.value }}</div>
          <div class="stat-label">{{ card.label }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-top: 16px">
      <template #header><b>近 30 天问答趋势</b></template>
      <div ref="qaChartRef" style="height: 320px"></div>
    </el-card>

    <el-card style="margin-top: 16px">
      <template #header><b>各知识库文档状态分布</b></template>
      <div ref="docChartRef" style="height: 300px"></div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import { statsApi } from '../../api/admin'

const loading = ref(false)
const overview = ref({})
const daily = ref([])
const docStats = ref([])
const qaChartRef = ref(null)
const docChartRef = ref(null)
let qaChart = null
let docChart = null

function onResize() {
  qaChart?.resize()
  docChart?.resize()
}

const cards = computed(() => [
  { label: '注册用户', value: overview.value.user_count ?? '-' },
  { label: '会话总数', value: overview.value.session_count ?? '-' },
  { label: '累计问答', value: overview.value.assistant_answer_count ?? '-' },
  { label: '今日提问', value: overview.value.today_qa ?? '-' },
  { label: '知识库数', value: overview.value.kb_count ?? '-' },
  { label: '文档总数', value: overview.value.document_count ?? '-' },
  { label: '知识分块', value: overview.value.chunk_count ?? '-' },
  { label: '解析成功率', value: overview.value.parse_success_rate != null ? `${overview.value.parse_success_rate}%` : '-' },
  { label: '点赞 / 点踩', value: `${overview.value.feedback_like ?? 0} / ${overview.value.feedback_dislike ?? 0}` },
])

async function fetchAll() {
  loading.value = true
  try {
    ;[overview.value, daily.value, docStats.value] = await Promise.all([
      statsApi.overview(),
      statsApi.dailyQa(),
      statsApi.documents(),
    ])
  } finally {
    loading.value = false
  }
  await nextTick()
  renderCharts()
}

function renderCharts() {
  // 问答趋势
  qaChart = echarts.init(qaChartRef.value)
  qaChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['提问', '回答', '点赞', '点踩'] },
    grid: { left: 40, right: 20, top: 40, bottom: 30 },
    xAxis: { type: 'category', data: daily.value.map((d) => d.day.slice(5)) },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      { name: '提问', type: 'line', smooth: true, data: daily.value.map((d) => d.questions), itemStyle: { color: '#409eff' } },
      { name: '回答', type: 'line', smooth: true, data: daily.value.map((d) => d.answers), itemStyle: { color: '#67c23a' } },
      { name: '点赞', type: 'bar', data: daily.value.map((d) => d.likes), itemStyle: { color: '#e6a23c' } },
      { name: '点踩', type: 'bar', data: daily.value.map((d) => d.dislikes), itemStyle: { color: '#f56c6c' } },
    ],
  })

  // 文档状态分布（堆叠柱状）
  docChart = echarts.init(docChartRef.value)
  docChart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: ['成功', '失败', '解析中', '待解析'] },
    grid: { left: 40, right: 20, top: 40, bottom: 30 },
    xAxis: { type: 'category', data: docStats.value.map((d) => d.kb_name) },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      { name: '成功', type: 'bar', stack: 'total', data: docStats.value.map((d) => d.statuses.succeeded || 0), itemStyle: { color: '#67c23a' } },
      { name: '失败', type: 'bar', stack: 'total', data: docStats.value.map((d) => d.statuses.failed || 0), itemStyle: { color: '#f56c6c' } },
      { name: '解析中', type: 'bar', stack: 'total', data: docStats.value.map((d) => d.statuses.parsing || 0), itemStyle: { color: '#e6a23c' } },
      { name: '待解析', type: 'bar', stack: 'total', data: docStats.value.map((d) => d.statuses.pending || 0), itemStyle: { color: '#909399' } },
    ],
  })
}

onMounted(() => {
  fetchAll()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  qaChart?.dispose()
  docChart?.dispose()
})
</script>

<style scoped>
.page-header { margin-bottom: 16px; }
.stat-card { text-align: center; }
.stat-value { font-size: 24px; font-weight: 700; color: #303133; }
.stat-label { font-size: 12px; color: #909399; margin-top: 4px; }
</style>
