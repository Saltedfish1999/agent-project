<template>
  <div>
    <el-card>
      <template #header>
        <div class="card-header" style="font-size: 16px; font-weight: bold">
          <span>AI智能助手</span>
          <div class="card-right">
            <el-icon class="history-entry" @click="addNewChat"><Plus /></el-icon>
            <el-icon class="history-entry" @click="openHistory"><Clock /></el-icon>
          </div>
        </div>
      </template>

      <div
        ref="listRef"
        style="
          height: 480px;
          overflow-y: auto;
          padding: 8px 4px;
          background-color: #fafafa;
          border-radius: 6px;
        "
      >
        <div
          v-for="(item, index) in messages"
          :key="index"
          :style="{
            display: 'flex',
            justifyContent: item.role === 'user' ? 'flex-end' : 'flex-start',
            marginBottom: '12px'
          }"
        >
          <div
            :style="{
              maxWidth: '70%',
              padding: '10px 12px',
              borderRadius: '8px',
              backgroundColor: item.role === 'user' ? '#409eff' : '#fff',
              color: item.role === 'user' ? '#fff' : '#333',
              lineHeight: '1.6',
              boxShadow: '0 1px 2px rgba(0, 0, 0, 0.06)'
            }"
          >
            <div
              v-if="item.role === 'assistant' && item.status"
              style="margin-bottom: 6px; font-size: 12px; color: #909399"
            >
              {{ item.status }}
            </div>

            <div
              v-if="item.role === 'assistant' && item.steps?.length"
              style="margin-bottom: 8px; font-size: 12px; color: #909399; line-height: 1.5"
            >
              <div v-for="(step, i) in item.steps" :key="i">· {{ step }}</div>
            </div>
            <div v-html="parseMarkdown(item.content)"></div>
            <div class="message-bottom">
              <div
                class="operate-message"
                v-if="item.role === 'assistant' && index != 0 && !loading"
              >
                <el-tooltip content="复制" placement="top">
                  <el-icon class="operate-icon" @click="handleCopy(item)"><CopyDocument /></el-icon>
                </el-tooltip>
                <el-tooltip v-if="index === messages.length - 1" content="重新生成" placement="top">
                  <el-icon class="operate-icon" @click="handleRegenerate(item)"
                    ><Refresh
                  /></el-icon>
                </el-tooltip>
              </div>
              <div v-if="isShowContinue(item, index)" class="continue-message">
                <el-button size="small" text bg @click="handleContinue(item)">继续生成</el-button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="search-box">
        <div class="search-box-contaier">
          <div class="search-box-input">
            <el-input
              v-model="input"
              type="textarea"
              :rows="3"
              placeholder="问问实验室怎么预约、开放时间..."
              @keydown.enter.exact.prevent="handleSend"
              @keydown.enter.shift.stop
            ></el-input>
          </div>
          <div class="search-box-tool">
            <div class="search-tool-left">
              <el-select
                v-model="currentModel"
                class="search-model-select"
                size="medium"
                :disabled="loading"
              >
                <el-option v-for="m in models" :key="m.id" :label="m.label" :value="m.id" />
              </el-select>
              <el-button :type="enable_web ? 'primary' : ''" @click="isWebSearch"
                >联网搜索</el-button
              >
            </div>
            <el-button v-if="loading" type="danger" @click="handleStop">停止生成</el-button>
            <el-button v-else type="primary" @click="handleSend" :loading="loading">发送</el-button>
          </div>
        </div>
      </div>
    </el-card>
    <el-drawer v-model="historyVisible" title="历史记录" direction="rtl" size="320px">
      <div v-loading="historyLoading">
        <div
          v-for="item in historyMessages"
          :key="item.thread_id"
          class="history-item"
          @click="handleSwitchMessage(item)"
        >
          <div class="history-title">{{ item.title }}</div>
          <div class="history-date">{{ item.update_time }}</div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import {
  chatApi,
  chatStreamApi,
  getConversation,
  getConversationMessages,
  getModelApi,
  continueChatApi,
  regenerateChatApi
} from '@/api/ai'
import { ref, reactive, nextTick, onMounted, computed } from 'vue'
import { marked } from 'marked'
import { ElMessage } from 'element-plus'
import DOMPurify from 'dompurify'

defineOptions({ name: 'AiChat' })
const WELCOME = {
  role: 'assistant',
  content:
    '你好，我是实验室预约助手。可以问规则和开放实验室，也可以说「帮我预约明天下午的实验室」，确认后我会帮你提交。'
}
const THREAD_KEY = 'ai-chat-thread-id'
const savedThreadId = sessionStorage.getItem(THREAD_KEY)

const messages = ref([{ ...WELCOME }])
const threadId = ref(savedThreadId || crypto.randomUUID())
const input = ref('')
const loading = ref(false)
const listRef = ref()
const historyVisible = ref(false)
const historyMessages = ref([])
const historyLoading = ref(false)
const models = ref([])
const currentModel = ref('')
const enable_web = ref(false)

let stopController = null

// 记录发送的信息
const rememberThread = () => sessionStorage.setItem(THREAD_KEY, threadId.value)

const scrollToBottom = () => {
  nextTick(() => {
    const elem = listRef.value
    if (elem) elem.scrollTop = elem.scrollHeight
  })
}

const openHistory = () => {
  historyVisible.value = true
}

const restoreMessages = async () => {
  if (!savedThreadId) return
  try {
    const res = await getConversationMessages(savedThreadId)
    if (res.code === 200 && res.data?.length) {
      messages.value = res.data.map((m) => ({
        role: m.role,
        content: m.content,
        incomplete: !!m.incomplete,
        steps: []
      }))
      scrollToBottom()
    }
  } catch {
    sessionStorage.removeItem(THREAD_KEY)
  }
}

// 打开新的对话输入框
const addNewChat = () => {
  if (loading.value) handleStop()
  threadId.value = crypto.randomUUID()
  sessionStorage.removeItem(THREAD_KEY)
  messages.value = [{ ...WELCOME }]
  input.value = ''
}

// 获取当前可用的大模型
const getModels = async () => {
  const res = await getModelApi()
  if (res.code === 200) {
    models.value = res.data
    currentModel.value = res.data[0]?.id || ''
  }
}

const isWebSearch = () => {
  enable_web.value = !enable_web.value
}

const handleStop = () => stopController?.abort()

// 获取对话历史
const getConversations = async () => {
  historyLoading.value = true
  const res = await getConversation({ page: 1, page_size: 10 })
  try {
    if (res.code === 200) {
      const { data } = res
      historyMessages.value = data.list
    }
  } finally {
    historyLoading.value = false
  }
}

// 重新生成
const handleContinue = async () => {
  const last = messages.value[messages.value.length - 1] // 获取最后一句话
  if (loading.value || !last || last.role !== 'assistant' || !last.incomplete) return

  loading.value = true
  stopController = new AbortController()
  last.status = '继续生成中...'

  try {
    await continueChatApi(
      { thread_id: threadId.value, content: last.content, model: currentModel.value },
      (evt) => {
        if (evt.type === 'token') last.content += evt.content || ''
        else if (evt.type === 'done') last.incomplete = false
        else if (evt.type === 'error') ElMessage.error(evt.message || '续写失败')
        scrollToBottom()
      },
      stopController.signal
    )
  } catch (err) {
    if (err?.name !== 'AbortError') ElMessage.error(err.message || '网络异常')
  } finally {
    stopController = null
    last.status = ''
    loading.value = false
    scrollToBottom()
  }
}

const isShowContinue = (item, index) => {
  return (
    item.role === 'assistant' &&
    item.incomplete &&
    !loading.value &&
    index === messages.value.length - 1
  )
}

const handleCopy = async (item) => {
  try {
    await navigator.clipboard.writeText(item.content)
    ElMessage.success('已复制')
  } catch {
    ElMessage.warning('复制失败')
  }
}

const handleSend = async () => {
  const text = input.value.trim()
  if (!text || loading.value) return

  messages.value.push({ role: 'user', content: text })
  rememberThread()
  input.value = ''
  loading.value = true
  scrollToBottom()

  const assistant = reactive({
    role: 'assistant',
    content: '',
    status: '正在思考...',
    steps: [] // 过程流水，不会进入下次history
  })

  messages.value.push(assistant)
  const history = messages.value
    .filter((item) => item.role === 'user' || item.role === 'assistant')
    .slice(0, -1)
    .map(({ role, content }) => ({ role, content }))

  try {
    stopController = new AbortController()
    // 第二个参数是回调：每解析出一条 SSE 事件就进一次
    await chatStreamApi(
      {
        messages: history,
        thread_id: threadId.value,
        model: currentModel.value,
        enable_web: enable_web.value
      },
      (evt) => {
        if (evt.type === 'status') {
          assistant.status = evt.message || '正在思考…'
        } else if (evt.type === 'tool_start') {
          const label = evt.label || evt.name || '工具'
          assistant.status = `正在${label}…`
          assistant.steps.push(`开始：${label}`)
        } else if (evt.type === 'tool_end') {
          const label = evt.label || evt.name || '工具'
          assistant.status = `${label}完成`
          assistant.steps.push(`完成：${label}`)
        } else if (evt.type === 'token') {
          assistant.content += evt.content || '' // 打字机：追加，不是覆盖
          assistant.status = '' // 开始出字后清掉「正在…」，避免叠在一起
        } else if (evt.type === 'done') {
          assistant.status = ''
          // 注意：不要在这里再 append 一整段正文，否则会双份
        } else if (evt.type === 'error') {
          assistant.status = ''
          if (!assistant.content) {
            assistant.content = evt.message || '请求失败'
          }

          ElMessage.error(evt.message || '请求失败')
        }
        scrollToBottom()
      },
      stopController.signal
    )
  } catch (err) {
    assistant.status = ''
    if (err?.name === 'AbortError') {
      assistant.incomplete = true
      if (!assistant.content) assistant.content = '已停止生成'
    } else {
      if (!assistant.content) {
        assistant.content = err.message || '网络异常'
      }
      ElMessage.error(err.message || '网络异常')
    }
  } finally {
    stopController = null
    loading.value = false
    assistant.status = ''
    scrollToBottom()
  }
}
const handleRegenerate = async (item) => {
  if (loading.value || !item.content) return

  const backup = item.content // 失败时恢复，别让用户什么都没有
  item.content = ''
  item.status = '正在重新生成...'
  item.steps = []
  item.incomplete = false
  item.regenCount = (item.regenCount || 0) + 1

  loading.value = true
  stopController = new AbortController()

  try {
    await regenerateChatApi(
      {
        thread_id: threadId.value,
        model: item.model || currentModel.value,
        attempt: item.regenCount
      },
      (evt) => {
        if (evt.type === 'status') {
          item.status = evt.message || '正在重新生成...'
        } else if (evt.type === 'token') {
          item.content += evt.content || ''
          item.status = ''
        } else if (evt.type === 'done') {
          item.status = ''
        } else if (evt.type === 'error') {
          item.status = ''
          ElMessage.error(evt.message || '重新生成失败')
        }
        scrollToBottom()
      },
      stopController.signal
    )
  } catch (err) {
    if (err?.name === 'AbortError') {
      item.incomplete = !!item.content // 保留已生成的部分
    } else {
      item.content = backup // 把旧回答还回去
      ElMessage.error(err.message || '重新生成失败')
    }
  } finally {
    stopController = null
    loading.value = false
    item.status = ''
    scrollToBottom()
  }
}

const handleSwitchMessage = async (item) => {
  if (loading.value) {
    ElMessage.warning('对话正在生成中...')
    return
  }
  if (item.thread_id === threadId.value) {
    historyVisible.value = false
    return
  }
  loading.value = true
  try {
    const res = await getConversationMessages(item.thread_id)
    if (res.code === 200) {
      const list = res.data || []
      messages.value = list.length
        ? list.map((m) => ({
            role: m.role,
            content: m.content,
            incomplete: !!m.incomplete,
            steps: []
          }))
        : [{ ...WELCOME }]
      threadId.value = item.thread_id
      rememberThread()
      historyVisible.value = false
      scrollToBottom()
    }
  } finally {
    loading.value = false
  }
}

// 将markdown转换为HTML字符串
const parseMarkdown = (text) => {
  if (!text) return
  marked.setOptions({ breaks: true }) // 转换\n为<br>
  // 使用 marked 解析，然后用 DOMPurify 清理
  const rawHtml = marked.parse(text)
  return DOMPurify.sanitize(rawHtml)
}

onMounted(() => {
  getModels()
  getConversations()
  restoreMessages()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-right {
  display: flex;
  gap: 4px;
}
.history-entry {
  cursor: pointer;
  color: #909399;
}
.history-entry:hover {
  color: #409eff;
}
.history-item {
  cursor: pointer;
  color: #909399;
}
.history-item:hover {
  color: #409eff;
}
.message-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 6px;
}
.operate-message {
  font-size: 16px;
  display: flex;
  gap: 6px;
}
.operate-icon {
  cursor: pointer;
  color: #909399;
}
.operate-icon:hover {
  color: #409eff;
}
.continue-message {
  margin-top: 6px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.search-box {
  border: 1px solid #e0e0e0;
  border-radius: 12px;
}
.search-box-input {
  padding: 12px 12px 0 16px;
}
.search-box-input :deep(.el-textarea__inner) {
  border: none;
  box-shadow: none;
  background-color: transparent;
  padding: 0;
  resize: none;
  font-size: 16px;
}
.search-box-tool {
  padding: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.search-tool-left {
  display: flex;
  gap: 4px;
}
.search-model-select {
  min-width: 150px;
}
</style>
