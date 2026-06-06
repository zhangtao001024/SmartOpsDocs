import { createRouter, createWebHistory } from 'vue-router'

const LoginView = () => import('../views/LoginView.vue')
const DashboardView = () => import('../views/DashboardView.vue')
const ServersView = () => import('../views/ServersView.vue')
const DockerView = () => import('../views/DockerView.vue')
const K8sView = () => import('../views/K8sView.vue')
const DocumentsView = () => import('../views/DocumentsView.vue')
const ChatView = () => import('../views/ChatView.vue')
const SettingsView = () => import('../views/SettingsView.vue')

const routes = [
  { path: '/login', component: LoginView },
  {
    path: '/',
    component: DashboardView,
    children: [
      { path: '', component: () => import('../views/DashboardContent.vue') },
      { path: 'servers', component: ServersView },
      { path: 'docker', component: DockerView },
      { path: 'k8s', component: K8sView },
      { path: 'documents', component: DocumentsView },
      { path: 'chat', component: ChatView },
      { path: 'settings', component: SettingsView }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  const token = localStorage.getItem('smartopsdocs_token')
  if (!token && to.path !== '/login') return '/login'
  if (token && to.path === '/login') return '/'
})

export default router
