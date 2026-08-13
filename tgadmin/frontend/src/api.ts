import type {
  DashboardStats,
  User,
  UserListResponse,
  UserBanRequest,
  Bot,
  BotListResponse,
  BotCreateRequest,
  BotUpdateRequest,
} from './types'

const API_BASE = import.meta.env.VITE_API_BASE || ''

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail || '请求失败')
  }
  if (resp.status === 204) return undefined as T
  return resp.json()
}

// Dashboard
export function fetchDashboardStats(): Promise<DashboardStats> {
  return request('/api/dashboard/stats')
}

// Users
export function fetchUsers(params: {
  page?: number
  page_size?: number
  search?: string
  status?: string
}): Promise<UserListResponse> {
  const query = new URLSearchParams()
  if (params.page) query.set('page', String(params.page))
  if (params.page_size) query.set('page_size', String(params.page_size))
  if (params.search) query.set('search', params.search)
  if (params.status) query.set('status', params.status)
  return request(`/api/users?${query}`)
}

export function fetchUser(userId: number): Promise<User> {
  return request(`/api/users/${userId}`)
}

export function banUser(userId: number, data: UserBanRequest): Promise<User> {
  return request(`/api/users/${userId}/ban`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export function deleteUser(userId: number): Promise<void> {
  return request(`/api/users/${userId}`, { method: 'DELETE' })
}

// Bots
export function fetchBots(params: {
  page?: number
  page_size?: number
  search?: string
  status?: string
}): Promise<BotListResponse> {
  const query = new URLSearchParams()
  if (params.page) query.set('page', String(params.page))
  if (params.page_size) query.set('page_size', String(params.page_size))
  if (params.search) query.set('search', params.search)
  if (params.status) query.set('status', params.status)
  return request(`/api/bots?${query}`)
}

export function createBot(data: BotCreateRequest): Promise<Bot> {
  return request('/api/bots', { method: 'POST', body: JSON.stringify(data) })
}

export function updateBot(botId: number, data: BotUpdateRequest): Promise<Bot> {
  return request(`/api/bots/${botId}`, { method: 'PUT', body: JSON.stringify(data) })
}

export function toggleBot(botId: number): Promise<Bot> {
  return request(`/api/bots/${botId}/toggle`, { method: 'PUT' })
}

export function deleteBot(botId: number): Promise<void> {
  return request(`/api/bots/${botId}`, { method: 'DELETE' })
}

export function revealBotToken(botId: number): Promise<{ id: number; bot_token: string }> {
  return request(`/api/bots/${botId}/token`)
}
