import request from './request'

export const authApi = {
  register(data) {
    return request.post('/auth/register', data)
  },
  login(data) {
    return request.post('/auth/login', data)
  },
  me() {
    return request.get('/auth/me')
  },
  changePassword(data) {
    return request.post('/auth/change-password', data)
  },
}
