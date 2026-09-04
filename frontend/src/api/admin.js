import request from './request'

export const kbApi = {
  list() {
    return request.get('/kbs')
  },
  adminList() {
    return request.get('/admin/kbs')
  },
  create(data) {
    return request.post('/admin/kbs', data)
  },
  update(id, data) {
    return request.patch(`/admin/kbs/${id}`, data)
  },
  remove(id) {
    return request.delete(`/admin/kbs/${id}`)
  },
}

export const documentApi = {
  list(params) {
    return request.get('/admin/documents', { params })
  },
  upload(kbId, file) {
    const form = new FormData()
    form.append('file', file)
    return request.post(`/admin/documents?kb_id=${kbId}`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  createUrl(kbId, url) {
    return request.post(`/admin/documents/url?kb_id=${kbId}`, { url })
  },
  detail(id) {
    return request.get(`/admin/documents/${id}`)
  },
  reparse(id) {
    return request.post(`/admin/documents/${id}/reparse`)
  },
  retry(id) {
    return request.post(`/admin/documents/${id}/retry`)
  },
  remove(id) {
    return request.delete(`/admin/documents/${id}`)
  },
  chunks(id, params) {
    return request.get(`/admin/documents/${id}/chunks`, { params })
  },
}

export const statsApi = {
  overview() {
    return request.get('/admin/stats/overview')
  },
  dailyQa() {
    return request.get('/admin/stats/daily-qa')
  },
  documents() {
    return request.get('/admin/stats/documents')
  },
}
