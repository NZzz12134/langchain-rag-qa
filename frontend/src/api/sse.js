/**
 * SSE 流式请求：POST + fetch ReadableStream 解析 event:/data: 格式。
 * 返回 { abort, promise }，promise resolve 全部事件数组。
 * 401/429 与 axios 拦截器保持一致的处理（清凭证、提示、跳转）。
 */
import { ElMessage } from 'element-plus'
import router from '../router'
import { extractErrorMessage, handleUnauthorized } from './request'

export function streamPost(url, body) {
  const controller = new AbortController()

  const promise = (async () => {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem('token')}`,
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    })

    if (!response.ok) {
      let message = `请求失败 (${response.status})`
      let detail
      try {
        const data = await response.json()
        detail = data?.detail
        message = extractErrorMessage(detail) || message
      } catch (_) {
        /* ignore */
      }
      if (response.status === 401) {
        await handleUnauthorized(message)
      } else if (response.status === 429) {
        ElMessage.warning(message || '请求过于频繁，请稍后再试')
      }
      throw new Error(message)
    }

    if (!response.body) {
      throw new Error('浏览器不支持流式响应')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    const events = []

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      let idx
      while ((idx = buffer.indexOf('\n\n')) !== -1) {
        const block = buffer.slice(0, idx)
        buffer = buffer.slice(idx + 2)
        const event = { event: 'message', data: null }
        for (const line of block.split('\n')) {
          if (line.startsWith('event:')) event.event = line.slice(6).trim()
          else if (line.startsWith('data:')) {
            const raw = line.slice(5).trim()
            try {
              event.data = JSON.parse(raw)
            } catch (_) {
              event.data = raw
            }
          }
          // ': ping' 注释行直接忽略
        }
        if (event.event !== 'ping') {
          events.push(event)
        }
      }
    }
    return events
  })()

  return { abort: () => controller.abort(), promise }
}
