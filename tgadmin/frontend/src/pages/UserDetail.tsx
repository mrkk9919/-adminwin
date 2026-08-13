import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useEffect } from 'react'
import { fetchUser, banUser, deleteUser } from '../api'
import type { User } from '../types'

export default function UserDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!id) return
    fetchUser(Number(id))
      .then(setUser)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  function handleBan() {
    if (!user) return
    const reason = prompt('请输入封禁原因:')
    if (reason === null) return
    banUser(user.id, { is_banned: true, ban_reason: reason || null })
      .then(setUser)
      .catch((e) => alert('操作失败: ' + e.message))
  }

  function handleUnban() {
    if (!user) return
    if (!confirm('确认解封该用户？')) return
    banUser(user.id, { is_banned: false, ban_reason: null })
      .then(setUser)
      .catch((e) => alert('操作失败: ' + e.message))
  }

  function handleDelete() {
    if (!user) return
    if (!confirm('确认删除该用户？此操作不可恢复！')) return
    deleteUser(user.id)
      .then(() => navigate('/users'))
      .catch((e) => alert('删除失败: ' + e.message))
  }

  function formatDateTime(dt: string | null) {
    if (!dt) return '-'
    return new Date(dt).toLocaleString('zh-CN', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    })
  }

  if (loading) {
    return (
      <div className="text-center text-muted py-5">
        <div className="spinner-border spinner-border-sm me-2" />
        加载中...
      </div>
    )
  }

  if (error || !user) {
    return <div className="alert alert-danger">{error || '用户不存在'}</div>
  }

  return (
    <>
      <h5 className="mb-4">用户详情</h5>

      <div className="mb-3">
        <Link to="/users" className="btn btn-outline-secondary btn-sm">
          <i className="bi bi-arrow-left me-1" /> 返回列表
        </Link>
      </div>

      <div className="row g-4">
        {/* User Info Card */}
        <div className="col-lg-8">
          <div className="card">
            <div className="card-header d-flex justify-content-between align-items-center">
              <h6 className="mb-0">基本信息</h6>
              {user.is_banned ? (
                <span className="badge bg-danger">已封禁</span>
              ) : (
                <span className="badge bg-success">正常</span>
              )}
            </div>
            <div className="card-body">
              <div className="row g-3">
                <InfoItem label="内部 ID" value={String(user.id)} />
                <InfoItem label="Telegram ID" value={<code>{user.tg_user_id}</code>} />
                <InfoItem
                  label="用户名"
                  value={
                    user.username ? (
                      <a href={`https://t.me/${user.username}`} target="_blank" rel="noreferrer">
                        @{user.username}
                      </a>
                    ) : (
                      <span className="text-muted">未设置</span>
                    )
                  }
                />
                <InfoItem label="姓名" value={user.full_name} />
                <InfoItem label="语言" value={user.language_code || '-'} />
                <InfoItem
                  label="类型"
                  value={
                    user.is_bot ? (
                      <span className="badge bg-info">Bot</span>
                    ) : (
                      '普通用户'
                    )
                  }
                />
                <InfoItem label="注册时间" value={formatDateTime(user.created_at)} />
                <InfoItem label="最后活跃" value={formatDateTime(user.last_active_at)} />
              </div>
            </div>
          </div>
        </div>

        {/* Actions Card */}
        <div className="col-lg-4">
          <div className="card">
            <div className="card-header">
              <h6 className="mb-0">操作</h6>
            </div>
            <div className="card-body d-grid gap-2">
              {/* 在 Telegram 中打开用户 */}
              <a
                href={user.username
                  ? `https://t.me/${user.username}`
                  : `tg://user?id=${user.tg_user_id}`}
                target="_blank"
                rel="noreferrer"
                className="btn btn-info text-white"
              >
                <i className="bi bi-telegram me-1" /> 在 Telegram 中打开
              </a>

              {/* 打开 Wing Bank Bot */}
              <a
                href="https://t.me/wingbankkh_bot"
                target="_blank"
                rel="noreferrer"
                className="btn btn-outline-success"
              >
                <i className="bi bi-robot me-1" /> 打开 Wing Bank Bot
              </a>

              {/* 复制 Telegram ID */}
              <button
                className="btn btn-outline-secondary"
                onClick={() => {
                  navigator.clipboard.writeText(String(user.tg_user_id))
                    .then(() => alert('已复制 Telegram ID: ' + user.tg_user_id))
                    .catch(() => alert('复制失败'))
                }}
              >
                <i className="bi bi-clipboard me-1" /> 复制 Telegram ID
              </button>

              <hr />

              {user.is_banned ? (
                <button className="btn btn-success" onClick={handleUnban}>
                  <i className="bi bi-check-circle me-1" /> 解封用户
                </button>
              ) : (
                <button className="btn btn-danger" onClick={handleBan}>
                  <i className="bi bi-x-circle me-1" /> 封禁用户
                </button>
              )}
              <button className="btn btn-outline-danger" onClick={handleDelete}>
                <i className="bi bi-trash me-1" /> 删除用户
              </button>
            </div>
          </div>

          {user.is_banned && user.ban_reason && (
            <div className="card mt-3">
              <div className="card-header">
                <h6 className="mb-0">封禁原因</h6>
              </div>
              <div className="card-body">
                <p className="mb-0">{user.ban_reason}</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  )
}

function InfoItem({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="col-md-6">
      <label className="form-label text-muted">{label}</label>
      <p className="mb-0">{value}</p>
    </div>
  )
}
