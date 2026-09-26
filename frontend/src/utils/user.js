import { ref } from 'vue'
import { getUserInfo, logout as clearLoginData, setToken, setUserInfo } from './auth'

const userInfo = ref(getUserInfo()) // 响应式对象 可以随时更新最新的值

export function useUser() {
  function saveLoginData(data) {
    setToken(data.token)
    setUserInfo(data.user)
    userInfo.value = data.user
  }

  function updateUser(user) {
    setUserInfo(user)
    userInfo.value = user
  }

  function reloadUser() {
    userInfo.value = getUserInfo()
  }

  // 退出登录：清空本地存储，同时重置响应式用户信息
  function logoutUser() {
    clearLoginData()
    userInfo.value = null
  }

  return {
    userInfo,
    saveLoginData,
    updateUser,
    reloadUser,
    logoutUser
  }
}
