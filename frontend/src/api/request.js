import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '../router'

const request = axios.create({
  baseURL: '/api/v1',
  timeout: 60000,
})

request.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

/** 从 FastAPI 错误响应中提取用户可读信息（detail 可能是对象或 422 校验数组） */
export function extractErrorMessage(detail) {
  if (Array.isArray(detail)) {
    // FastAPI 422 校验错误：[{loc, msg, type}, ...]
    return detail.map((d) => d.msg || String(d)).join('；')
  }
  if (typeof detail === 'object' && detail !== null) {
    return detail.message
  }
  return detail
}

/** 401 全局处理：清 Pinia + localStorage 并跳登录（动态 import 避免循环依赖） */
export async function handleUnauthorized(message) {
  const { useAuthStore } = await import('../stores/auth')
  await useAuthStore().logout()
  if (router.currentRoute.value.path !== '/login') {
    ElMessage.error(message || '登录已过期，请重新登录')
    router.push('/login')
  }
}

request.interceptors.response.use(
  (response) => response.data,
  async (error) => {
    const status = error.response?.status
    const message = extractErrorMessage(error.response?.data?.detail)

    if (status === 401) {
      await handleUnauthorized(message)
    } else if (status === 403) {
      ElMessage.error(message || '无权访问')
    } else if (status === 429) {
      ElMessage.warning(message || '请求过于频繁，请稍后再试')
    } else if (message) {
      ElMessage.error(message)
    }
    return Promise.reject(error)
  }
)

export default request
