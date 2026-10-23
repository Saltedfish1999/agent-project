<template>
  <div class="history-list">
    <div class="history-header">
      <div class="history-title">
        <el-icon><Clock /></el-icon>
        <span>历史对话</span>
      </div>
      <el-icon class="history-close" @click="$emit('close')"><Close /></el-icon>
    </div>
    <el-input
      v-model="searchMessage"
      placeholder="搜索历史对话"
      @keyup.enter="searchList"
      @clear="searchList"
    >
      <template #prefix>
        <el-icon class="el-input__icon"><search /></el-icon>
      </template>
    </el-input>
    <el-button type="primary" :icon="Plus" @click="handleAdd">新建对话</el-button>
    <div v-loading="loadingMore" class="history-scroll" @scroll="onScroll">
      <template v-for="value in list" :key="value.label">
        <div class="history-group">{{ value.label }}</div>
        <div v-for="item in value.items" :key="item.thread_id">
          <div
            class="history-item"
            :class="{ active: item.thread_id === activeId }"
            @click="$emit('select', item)"
          >
            <div class="history-content">
              <el-icon class="item-icon"><ChatDotRound /></el-icon>
              <div class="history-text">
                <span>{{ item.summary || '搜索历史对话' }}</span>
                <span>{{ item.title }}</span>
              </div>
            </div>
            <el-dropdown trigger="click" @command="(cmd) => handleHistoryCommand(cmd, item)">
              <el-icon class="item-more" @click.stop><MoreFilled /></el-icon>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="rename">重命名</el-dropdown-item>
                  <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
      </template>
      <div v-if="loadingMore" class="history-loading">正在加载…</div>
      <div v-else-if="!hasMore && list.length" class="history-end">没有更多了</div>
      <div v-if="!list.length" class="history-empty">
        {{ searchMessage.trim() ? '没有找到相关对话' : '暂无历史对话' }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { Plus } from '@element-plus/icons-vue'
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getConversation, deleteConversationMessages, renameMessages } from '@/api/ai'
const emit = defineEmits(['close', 'add', 'select'])
const props = defineProps({
  activeId: {
    type: String,
    default: ''
  }
})

const historyMessages = ref([])
const page = ref(1)
const hasMore = ref(true)
const loadingMore = ref(false)
const searchMessage = ref('')

const list = computed(() => {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)

  const groups = [
    { label: '今天', items: [] },
    { label: '昨天', items: [] },
    { label: '更早', items: [] }
  ]
  for (const item of historyMessages.value) {
    const time = item.create_time ? new Date(item.create_time) : null
    const valid = time && !Number.isNaN(time.getTime())

    if (valid && time >= today) groups[0].items.push(item)
    else if (valid && time >= yesterday) groups[1].items.push(item)
    else groups[2].items.push(item)
  }
  return groups.filter((g) => g.items.length)
})

const onScroll = (e) => {
  const el = e.target
  const distance = el.scrollHeight - el.scrollTop - el.clientHeight
  if (distance < 60) loadMore()
}

const loadMore = async () => {
  if (loadingMore.value || !hasMore.value) return
  loadingMore.value = true
  try {
    const res = await getConversation({
      page: page.value,
      page_size: 10,
      keyword: searchMessage.value || ''
    })
    if (res.code !== 200) return

    const list = res.data.list || []
    const merged = new Map(historyMessages.value.map((item) => [item.thread_id, item]))
    for (const item of list) merged.set(item.thread_id, item)
    historyMessages.value = [...merged.values()]

    page.value += 1
    hasMore.value = list.length === 10 && merged.size < res.data.total
  } finally {
    loadingMore.value = false
  }
}

const handleHistoryCommand = async (cmd, item) => {
  if (cmd === 'rename') await handleRename(item)
  else if (cmd === 'delete') await handleDelete(item)
}

const handleRename = async (item) => {
  let value
  try {
    const result = await ElMessageBox.prompt('请输入新的对话名称', '重命名', {
      inputValue: item.summary,
      inputPlaceholder: '最多 20 个字',
      inputValidator: (v) => {
        const name = (v || '').trim()
        if (!name) return '名称不能为空'
        if (name.length > 20) return '名称不能超过 20 个字'
        return true
      },
      confirmButtonText: '保存',
      cancelButtonText: '取消'
    })
    value = result.value
  } catch {
    return
  }
  const res = await renameMessages(item.thread_id, value)
  if (res.code !== 200) {
    ElMessage.error('修改失败')
    return
  }
  item.summary = res.data?.summary ?? value.trim()
  ElMessage.success('修改成功')
}

const handleDelete = async (item) => {
  try {
    await ElMessageBox.confirm('删除后该话无法恢复，确认删除？', '删除对话', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }

  const res = await deleteConversationMessages(item.thread_id)
  if (res.code !== 200) return

  historyMessages.value = historyMessages.value.filter((i) => i.thread_id !== item.thread_id)
  if (item.thread_id === props.activeId) emit('add')
  ElMessage.success('已删除')
}

const searchList = () => {
  loadingMore.value = false
  historyMessages.value = []
  page.value = 1
  hasMore.value = true
  return loadMore()
}

const handleAdd = () => {
  emit('add')
  emit('close')
}

onMounted(() => {
  loadMore()
})
</script>

<style scoped>
.history-list {
  position: absolute;
  top: 68px;
  right: 12px;
  bottom: 160px;
  width: 360px;
  z-index: 20;

  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 20px 16px 12px;

  background: #fff;
  border: 1px solid rgba(0, 0, 0, 0.04);
  border-radius: 14px;
  box-shadow:
    0 12px 40px rgba(0, 0, 0, 0.14),
    0 2px 8px rgba(0, 0, 0, 0.06);
}
.history-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  margin: 0 -6px;
  padding: 0 6px;
}
.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.history-title {
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 4px;
}
.history-close {
  cursor: pointer;
}
.history-close:hover {
  color: #1677ff;
}
.history-group {
  font-size: 14px;
  color: #909399;
  padding: 6px 8px 4px;
}
.history-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s;
  gap: 4px;
}
.history-item:hover {
  background: #f0f6ff;
  .item-icon {
    background: #e6f0ff;
    color: #1677ff;
  }
}
.history-item.active {
  background: #ecf5ff;
}
.history-item.active .item-name {
  font-weight: 600;
}
.history-content {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}
.history-text {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  gap: 2px;
}
.history-text > span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: block;
}
.item-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #f0f2f5;
  color: #606266;
  font-size: 16px;
}
.history-item.active .item-icon {
  background: #d9ecff;
  color: #409eff;
}
.history-end {
  display: flex;
  justify-content: center;
}
</style>
