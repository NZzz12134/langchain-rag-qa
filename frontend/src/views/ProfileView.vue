<template>
  <div class="profile-page">
    <el-card style="max-width: 480px; margin: 60px auto">
      <template #header>
        <div style="display: flex; align-items: center; justify-content: space-between">
          <b>个人中心</b>
          <el-button link type="primary" @click="$router.push('/')">← 返回聊天</el-button>
        </div>
      </template>

      <el-descriptions :column="1" border style="margin-bottom: 24px">
        <el-descriptions-item label="用户名">{{ auth.user?.username }}</el-descriptions-item>
        <el-descriptions-item label="角色">
          <el-tag :type="auth.isAdmin ? 'danger' : 'info'" size="small">
            {{ auth.isAdmin ? '管理员' : '普通用户' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="邮箱">{{ auth.user?.email || '未填写' }}</el-descriptions-item>
      </el-descriptions>

      <h4 style="margin-bottom: 12px">修改密码</h4>
      <el-form :model="form" label-position="top">
        <el-form-item label="原密码">
          <el-input v-model="form.old_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="新密码（至少 6 位）">
          <el-input v-model="form.new_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="确认新密码">
          <el-input v-model="form.confirm" type="password" show-password />
        </el-form-item>
        <el-button type="primary" :loading="loading" @click="submit">确认修改</el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import { authApi } from '../api/auth'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const form = reactive({ old_password: '', new_password: '', confirm: '' })

async function submit() {
  if (!form.old_password || !form.new_password) {
    ElMessage.warning('请填写完整')
    return
  }
  if (form.new_password.length < 6) {
    ElMessage.warning('新密码至少 6 位')
    return
  }
  if (form.new_password !== form.confirm) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  loading.value = true
  try {
    await authApi.changePassword({ old_password: form.old_password, new_password: form.new_password })
    await ElMessageBox.alert('密码修改成功，请重新登录', '提示')
    auth.logout()
    router.push('/login')
  } catch (_) {
    /* 拦截器已提示 */
  } finally {
    loading.value = false
  }
}
</script>
