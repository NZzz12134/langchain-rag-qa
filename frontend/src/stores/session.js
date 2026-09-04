import { defineStore } from 'pinia'
import { sessionApi } from '../api/session'

export const useSessionStore = defineStore('session', {
  state: () => ({
    sessions: [],
    currentId: null,
    loaded: false,
  }),
  actions: {
    async fetchSessions() {
      const data = await sessionApi.list({ page: 1, page_size: 100 })
      this.sessions = data.items
      this.loaded = true
      return data.items
    },
    async createSession(title, kbId = null) {
      const session = await sessionApi.create({ title, kb_id: kbId })
      this.sessions.unshift(session)
      this.currentId = session.id
      return session
    },
    async renameSession(id, title) {
      await sessionApi.rename(id, title)
      const s = this.sessions.find((x) => x.id === id)
      if (s) s.title = title
    },
    async removeSession(id) {
      await sessionApi.remove(id)
      this.sessions = this.sessions.filter((x) => x.id !== id)
      if (this.currentId === id) {
        // 删除当前会话后自动选中剩余第一个，避免回到空欢迎页
        this.currentId = this.sessions.length ? this.sessions[0].id : null
      }
    },
    setCurrent(id) {
      this.currentId = id
    },
  },
})
