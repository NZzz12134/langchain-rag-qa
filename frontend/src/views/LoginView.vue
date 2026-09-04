<template>
  <div class="auth-page">
    <el-card class="auth-card">
      <h2 class="title">RAG 知识库问答系统</h2>
      <p class="subtitle">上传任意领域的知识文档，即可获得带引用溯源的智能问答</p>
      <el-form :model="form" @keyup.enter="submit" label-position="top">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="请输入用户名" size="large" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" placeholder="请输入密码" size="large" show-password />
        </el-form-item>
        <el-button type="primary" size="large" style="width: 100%" :loading="loading" @click="submit">
          登 录
        </el-button>
        <div class="footer">
          <span>还没有账号？</span>
          <el-link type="primary" @click="$router.push('/register')">立即注册</el-link>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { authApi } from '../api/auth'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const loading = ref(false)
const form = reactive({ username: '', password: '' })

async function submit() {
  if (!form.username || !form.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    const data = await authApi.login(form)
    auth.setAuth(data.access_token, data.user)
    ElMessage.success('登录成功')
    router.push(route.query.redirect || '/')
  } catch (_) {
    /* 拦截器已提示 */
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-page {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
.auth-card {
  width: 400px;
  padding: 12px 8px;
  border-radius: 12px;
}
.title { text-align: center; color: #303133; }
.subtitle { text-align: center; color: #909399; font-size: 13px; margin: 8px 0 24px; }
.footer { margin-top: 16px; text-align: center; font-size: 14px; color: #909399; }
</style>
