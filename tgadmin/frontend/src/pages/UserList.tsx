import { useState, useEffect, useCallback } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { fetchUsers, banUser } from '../api'
import type { User, UserListResponse } from '../types'
import BanModal from '../components/BanModal'

export default function UserList() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [data, setData] = useState<UserListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Filters from URL
  const search = searchParams.get('search') || ''
  const status = searchParams.get('status') || ''
  const page = parseInt(searchParams.get('page') || '1', 10)

  const [searchInput, setSearchInput] = useState(search)
  const [statusFilter, setStatusFilter] = useState(status)

  // Ban modal state
  const [banTarget, setBanTarget] = useState<User | null>(null)

  const loadUsers = useCallback(() => {
    setLoading(true)
    setError('')
    fetchUsers({ page, search, status })
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [page, search, status])

  useEffect(() => {
    loadUsers()
  }, [loadUsers])

  function handleFilter(e: React.FormEvent) {
    e.preventDefault()
    const params: Record<string, string> = {}
    if (searchInput) params.search = searchInput
    if (statusFilter) params.status = statusFilter
    setSearchParams(params)
  }

  function handleReset() {
    setSearchInput('')
    setStatusFilter('')
    setSearchParams({})
  }

  function handleBanConfirm(userId: number, isBan: boolean, reason: string) {
    banUser(userId, { is_banned: isBan, ban_reason: isBan ? reason || null : null })
      .then(() => {
        setBanTarget(null)
        loadUsers()
      })
      .catch((e) => alert(e.message))
  }

  // Build pagination range
  function paginationRange(current: number, total: number): (number | '...')[] {
    const pages: (number | '...')[] = []
    for (let i = 1; i <= total; i++) {
      if (i === 1 || i === total || (i >= current - 1 && i <= current + 1)) {
        pages.push(i)
      } else if (pages[pages.length - 1] !== '...') {
        pages.push('...')
      }
    }
    return pages
  }

  return (
    <>
      <h5 className="mb-4">用户管理</h5>

      {/* Filters */}
      <div className="card mb-4">
        <div className="card-body">
          <form onSubmit={handleFilter} className="row g-3 align-items-end">
            <div className="col-md-5">
              <label className="form-label">搜索</label>
              <div className="input-group">
                <span className="input-group-text"><i className="bi bi-search" /></span>
                <input
                  type="text"
                  className="form-control"
                  placeholder="用户名、姓名 或 Telegram ID"
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                />
              </div>
            </div>
            <div className="col-md-3">
              <label className="form-label">状态</label>
              <select
                className="form-select"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <option value="">全部</option>
                <option value="active">活跃</option>
                <option value="banned">已封禁</option>
              </select>
            </div>
            <div className="col-md-4 d-flex gap-2">
              <button type="submit" className="btn btn-primary">
                <i className="bi bi-funnel me-1" /> 筛选
              </button>
              <button type="button" className="btn btn-outline-secondary" onClick={handleReset}>
                重置
              </button>
            </div>
          </form>
        </div>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}

      {/* User Table */}
      <div className="card">
        <div className="card-header d-flex justify-content-between align-items-center">
          <h6 className="mb-0">
            用户列表{' '}
            {data && <span className="badge bg-secondary ms-1">{data.total}</span>}
          </h6>
        </div>
        <div className="table-responsive">
          <table className="table table-hover mb-0">
            <thead>
              <tr>
                <th>ID</th>
                <th>Telegram ID</th>
                <th>用户名</th>
                <th>姓名</th>
                <th>状态</th>
                <th>注册时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={7} className="text-center text-muted py-4">
                    <div className="spinner-border spinner-border-sm me-2" />
                    加载中...
                  </td>
                </tr>
              )}
              {!loading && data?.items.length === 0 && (
                <tr>
                  <td colSpan={7} className="text-center text-muted py-4">
                    暂无用户数据
                  </td>
                </tr>
              )}
              {!loading &&
                data?.items.map((user) => (
                  <tr key={user.id}>
                    <td>{user.id}</td>
                    <td><code>{user.tg_user_id}</code></td>
                    <td>
                      {user.username ? (
                        <a href={`https://t.me/${user.username}`} target="_blank" rel="noreferrer">
                          @{user.username}
                        </a>
                      ) : (
                        <span className="text-muted">-</span>
                      )}
                    </td>
                    <td>{user.full_name}</td>
                    <td>
                      {user.is_banned ? (
                        <span className="badge bg-danger">已封禁</span>
                      ) : (
                        <span className="badge bg-success">正常</span>
                      )}
                    </td>
                    <td>
                      {user.created_at
                        ? new Date(user.created_at).toLocaleString('zh-CN', {
                            year: 'numeric', month: '2-digit', day: '2-digit',
                            hour: '2-digit', minute: '2-digit',
                          })
                        : '-'}
                    </td>
                    <td>
                      <div className="btn-group btn-group-sm">
                        <Link to={`/users/${user.id}`} className="btn btn-outline-primary" title="详情">
                          <i className="bi bi-eye" />
                        </Link>
                        {/* 打开 Telegram 聊天 */}
                        <a
                          href={user.username
                            ? `https://t.me/${user.username}`
                            : `tg://user?id=${user.tg_user_id}`}
                          target="_blank"
                          rel="noreferrer"
                          className="btn btn-outline-info"
                          title="在 Telegram 中打开"
                        >
                          <i className="bi bi-telegram" />
                        </a>
                        {/* 复制 Telegram ID */}
                        <button
                          className="btn btn-outline-secondary"
                          title="复制 Telegram ID"
                          onClick={() => {
                            navigator.clipboard.writeText(String(user.tg_user_id))
                              .then(() => alert('已复制: ' + user.tg_user_id))
                              .catch(() => alert('复制失败'))
                          }}
                        >
                          <i className="bi bi-clipboard" />
                        </button>
                        <button
                          className={`btn btn-outline-${user.is_banned ? 'success' : 'danger'}`}
                          title={user.is_banned ? '解封' : '封禁'}
                          onClick={() => setBanTarget(user)}
                        >
                          <i className={`bi bi-${user.is_banned ? 'check-circle' : 'x-circle'}`} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {data && data.total_pages > 1 && (
          <div className="card-footer">
            <nav>
              <ul className="pagination justify-content-center mb-0">
                <li className={`page-item ${page <= 1 ? 'disabled' : ''}`}>
                  <button
                    className="page-link"
                    onClick={() => setSearchParams((prev) => {
                      const p = new URLSearchParams(prev)
                      p.set('page', String(page - 1))
                      return p
                    })}
                  >
                    上一页
                  </button>
                </li>
                {paginationRange(page, data.total_pages).map((p, i) =>
                  p === '...' ? (
                    <li className="page-item disabled" key={`dots-${i}`}>
                      <span className="page-link">...</span>
                    </li>
                  ) : (
                    <li className={`page-item ${p === page ? 'active' : ''}`} key={p}>
                      <button
                        className="page-link"
                        onClick={() => setSearchParams((prev) => {
                          const params = new URLSearchParams(prev)
                          params.set('page', String(p))
                          return params
                        })}
                      >
                        {p}
                      </button>
                    </li>
                  ),
                )}
                <li className={`page-item ${page >= data.total_pages ? 'disabled' : ''}`}>
                  <button
                    className="page-link"
                    onClick={() => setSearchParams((prev) => {
                      const p = new URLSearchParams(prev)
                      p.set('page', String(page + 1))
                      return p
                    })}
                  >
                    下一页
                  </button>
                </li>
              </ul>
            </nav>
          </div>
        )}
      </div>

      {/* Ban/Unban Modal */}
      {banTarget && (
        <BanModal
          user={banTarget}
          onClose={() => setBanTarget(null)}
          onConfirm={handleBanConfirm}
        />
      )}
    </>
  )
}
