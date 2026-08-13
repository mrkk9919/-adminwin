export interface User {
  id: number
  tg_user_id: number
  username: string | null
  first_name: string
  last_name: string | null
  language_code: string | null
  is_bot: boolean
  is_banned: boolean
  ban_reason: string | null
  last_active_at: string | null
  created_at: string
  updated_at: string
  full_name: string
}

export interface UserListResponse {
  items: User[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface DashboardStats {
  total_users: number
  active_users: number
  banned_users: number
  bot_users: number
}

export interface UserBanRequest {
  is_banned: boolean
  ban_reason: string | null
}

export interface Bot {
  id: number
  name: string
  username: string | null
  is_active: boolean
  bot_token_masked: string
  created_at: string
  updated_at: string
}

export interface BotListResponse {
  items: Bot[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface BotCreateRequest {
  name: string
  bot_token: string
  is_active?: boolean
}

export interface BotUpdateRequest {
  name?: string
  bot_token?: string
  is_active?: boolean
}
