import axios from 'axios'

const DEFAULT_ERROR_MESSAGE = '请求失败'

const client = axios.create({
  baseURL: '',
  timeout: 30000
})

function readResponseDetail(error) {
  const detail = error.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || item.message || String(item)).join('；')
  }
  if (typeof detail === 'string' && detail.trim()) return detail
  if (detail && typeof detail === 'object') return detail.message || detail.error || ''
  return ''
}

export function getApiErrorMessage(error, fallback = DEFAULT_ERROR_MESSAGE) {
  if (!error) return fallback
  if (error.userMessage && (error.userMessage !== DEFAULT_ERROR_MESSAGE || fallback === DEFAULT_ERROR_MESSAGE)) {
    return error.userMessage
  }
  if (!axios.isAxiosError(error)) return error.message || fallback

  const detailMessage = readResponseDetail(error)
  if (detailMessage) return detailMessage

  if (error.code === 'ECONNABORTED') return '请求超时，请检查后端服务或网络'
  if (!error.response) return '无法连接后端服务，请确认 API 已启动'
  if (fallback !== DEFAULT_ERROR_MESSAGE) return fallback

  const statusMessages = {
    400: '请求参数有误',
    403: '当前账号没有权限执行该操作',
    404: '请求的资源不存在',
    409: '数据状态已变化，请刷新后重试',
    413: '文件过大，请调整后再上传',
    422: '提交内容未通过校验',
    500: '后端服务处理失败',
    502: '后端网关不可用',
    503: '后端服务暂时不可用',
  }
  return statusMessages[error.response.status] || fallback
}

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('smartopsdocs_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error)) {
      const detailMessage = readResponseDetail(error)
      if (detailMessage || error.code === 'ECONNABORTED' || !error.response) {
        error.userMessage = getApiErrorMessage(error)
      }
    }
    if (error.response?.status === 401) {
      localStorage.removeItem('smartopsdocs_token')
      error.userMessage = location.pathname === '/login' ? getApiErrorMessage(error, '登录失败') : '登录已过期，请重新登录'
      if (location.pathname !== '/login') location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default client
