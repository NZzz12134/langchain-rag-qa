import request from './request'
import { streamPost } from './sse'

export const chatApi = {
  /** SSE 流式问答 */
  stream(sessionId, question) {
    return streamPost('/api/v1/chat/stream', { session_id: sessionId, question })
  },
  citations(messageId) {
    return request.get(`/messages/${messageId}/citations`)
  },
  feedback(messageId, data) {
    return request.post(`/messages/${messageId}/feedback`, data)
  },
  removeFeedback(messageId) {
    return request.delete(`/messages/${messageId}/feedback`)
  },
}
