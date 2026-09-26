import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from '@/utils/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: '/manager/home' },
    {
      path: '/manager',
      name: 'Layout',
      component: () => import('@/layouts/Layout.vue'),
      children: [
        { path: 'register', name: 'Register', component: () => import('@/view/register.vue') },
        { path: 'home', name: 'Home', component: () => import('@/view/home.vue') },
        { path: 'lab', name: 'Lab', component: () => import('@/view/lab.vue') },
        { path: 'prefile', name: 'Prefile', component: () => import('@/view/prefile.vue') },
        { path: 'password', name: 'Password', component: () => import('@/view/password.vue') },
        { path: 'user', name: 'User', component: () => import('@/view/user.vue') },
        { path: 'lab', name: 'Lab', component: () => import('@/view/lab.vue') },
        { path: 'equipment', name: 'Equipment', component: () => import('@/view/equipment.vue') },
        { path: 'lablist', name: 'LabList', component: () => import('@/view/labList.vue') },
        {
          path: 'lab-equipment',
          name: 'LabEquipment',
          component: () => import('@/view/labEquipment.vue')
        },
        {
          path: 'my-reservation',
          name: 'MyReservation',
          component: () => import('@/view/myReservation.vue')
        },
        {
          path: 'audit-reservation',
          name: 'AuditReservation',
          component: () => import('@/view/auditReservation.vue')
        },
        {
          path: 'AI-Chat',
          name: 'AIChat',
          component: () => import('@/view/aiChat.vue')
        }
      ]
    },
    { path: '/login', name: 'Login', component: () => import('@/view/login.vue') },
    { path: '/register', name: 'Register', component: () => import('@/view/register.vue') }
  ]
})

// 路由守卫：验证token
router.beforeEach((to, from) => {
  const token = getToken()

  if (to.path === '/login' || to.path === '/register') {
    return true
  } else {
    return token ? true : '/login'
  }
})

export default router
