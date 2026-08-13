import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { fetchDashboardStats } from '../api'
import type { DashboardStats } from '../types'

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    fetchDashboardStats()
      .then(setStats)
      .catch((e) => setError(e.message))
  }, [])

  const cards = stats
    ? [
        { label: '总用户数', value: stats.total_users, icon: 'bi-people-fill', color: 'primary' },
        { label: '活跃用户', value: stats.active_users, icon: 'bi-person-check-fill', color: 'success' },
        { label: '已封禁', value: stats.banned_users, icon: 'bi-person-x-fill', color: 'danger' },
        { label: 'Bot 用户', value: stats.bot_users, icon: 'bi-robot', color: 'info' },
      ]
    : []

  return (
    <>
      <h5 className="mb-4">仪表盘</h5>

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="row g-4 mb-4">
        {cards.map((c) => (
          <div className="col-sm-6 col-xl-3" key={c.label}>
            <div className="card stat-card">
              <div className="card-body">
                <div className="d-flex align-items-center justify-content-between">
                  <div>
                    <p className="text-muted mb-1">{c.label}</p>
                    <h3 className="mb-0">{c.value}</h3>
                  </div>
                  <div className={`stat-icon bg-${c.color}-subtle text-${c.color}`}>
                    <i className={`bi ${c.icon}`} />
                  </div>
                </div>
              </div>
            </div>
          </div>
        ))}
        {!stats && !error && (
          <div className="col-12 text-center text-muted py-5">
            <div className="spinner-border spinner-border-sm me-2" />
            加载中...
          </div>
        )}
      </div>

      {stats && (
        <div className="row g-4">
          <div className="col-12">
            <div className="card">
              <div className="card-header">
                <h6 className="mb-0">快捷操作</h6>
              </div>
              <div className="card-body">
                <div className="d-flex gap-3 flex-wrap">
                  <Link to="/users" className="btn btn-outline-primary">
                    <i className="bi bi-people me-1" /> 查看用户列表
                  </Link>
                  <Link to="/users?status=banned" className="btn btn-outline-danger">
                    <i className="bi bi-shield-x me-1" /> 查看封禁用户
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
