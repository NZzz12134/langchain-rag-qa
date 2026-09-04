<template>
  <el-container class="admin-layout">
    <el-aside width="220px">
      <div class="logo">📚 知识库管理</div>
      <el-menu :default-active="$route.path" router>
        <el-menu-item index="/admin/kbs">
          <el-icon><FolderOpened /></el-icon>知识库列表
        </el-menu-item>
        <el-menu-item index="/admin/documents">
          <el-icon><Document /></el-icon>文档管理
        </el-menu-item>
        <el-menu-item index="/admin/stats">
          <el-icon><DataAnalysis /></el-icon>数据看板
        </el-menu-item>
      </el-menu>
      <div class="back-link">
        <el-button link type="primary" @click="$router.push('/')">
          <el-icon><Back /></el-icon> 返回聊天
        </el-button>
      </div>
    </el-aside>
    <el-main class="admin-main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
import { Back, DataAnalysis, Document, FolderOpened } from '@element-plus/icons-vue'
</script>

<style scoped>
.admin-layout { height: 100%; }
.el-aside {
  background: #fff;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
}
.logo {
  padding: 20px 16px;
  font-weight: 700;
  font-size: 15px;
  color: #303133;
  border-bottom: 1px solid #f0f2f5;
}
.el-menu { border-right: none; flex: 1; }
.back-link { padding: 16px; border-top: 1px solid #f0f2f5; }
.admin-main { background: #f5f7fa; padding: 20px; }
</style>
