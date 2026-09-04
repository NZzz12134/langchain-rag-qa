<template>
  <div class="forbidden">
    <el-result icon="warning" title="403 无权访问" sub-title="该页面仅管理员可访问，如需权限请联系管理员">
      <template #extra>
        <el-button type="primary" @click="$router.push('/')">返回聊天</el-button>
      </template>
    </el-result>
  </div>
</template>

<script setup>
</script>

<style scoped>
.forbidden { height: 100%; display: flex; align-items: center; justify-content: center; }
</style>
