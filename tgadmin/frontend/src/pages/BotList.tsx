import { useState, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchBots, createBot, updateBot, toggleBot, deleteBot } from '../api'
import type { Bot, BotListResponse } from '../types'
import BotFormModal from '../components/BotFormModal'

export default function BotList() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [data, setData] = useState<BotListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const search = searchParams.get('search') || ''
  const status = searchParams.get('status') || ''
  const page = parseInt(searchParams.get('page') || '1', 10)

  const [searchInput, setSearchInput] = useState(search)
  const [statusFilter, setStatusFilter] = useState(status)

  // null = closed, undefined bot = create mode, Bot = edit mode
  const [formMode, setFormMode] = useState<'create' | Bot | null>(null)

  const loadBots = useCallback(() => {
    setLoading(true)
    setError('')
    fetchBots({ page, search, status })
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [page, search, status])

  useEffect(() => {
    loadBots()
  }, [loadBots])

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

  async function handleFormSubmit(
    payload: { name: string; bot_token?: string; is_active?: boolean },
    botId?: number,
  ) {
    if (botId) {
      await updateBot(botId, payload)
    } else {
      await createBot({ name: payload.name, bot_token: payload.bot_token!, is_active: payload.is_active })
    }
    setFormMode(null)
    loadBots()
  }

  function handleToggle(bot: Bot) {
    toggleBot(bot.id)
      .then(loadBots)
      .catch((e) => alert(e.message))
  }

  function handleDelete(bot: Bot) {
    if (!confirm(`确定要删除机器人「${bot.name}」吗？此操作不可撤销。`)) return
    deleteBot(bot.id)
      .then(loadBots)
      .catch((e) => alert(e.message))
  }

  return (
    <>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h5 className="mb-0">机器人管理</h5>
        <button className="btn btn-primary" onClick={() => setFormMode('create')}>
          <i className="bi bi-plus-lg me-1" /> 新增机器人
        </button>
      </div>

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
                  placeholder="名称 或 用户名"
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
                <option value="active">已启用</option>
                <option value="inactive">已禁用</option>
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

      {/* Bot Table */}
      <div className="card">
        <div className="card-header d-flex justify-content-between align-items-center">
          <h6 className="mb-0">
            机器人列表{' '}
            {data && <span className="badge bg-secondary ms-1">{data.total}</span>}
          </h6>
        </div>
        <div className="table-responsive">
          <table className="table table-hover mb-0">
            <thead>
              <tr>
                <th>ID</th>
                <th>名称</th>
                <th>用户名</th>
                <th>Token</th>
                <th>状态</th>
                <th>创建时间</th>
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
                    暂无机器人，点击右上角“新增机器人”添加
                  </td>
                </tr>
              )}
              {!loading &&
                data?.items.map((bot) => (
                  <tr key={bot.id}>
                    <td>{bot.id}</td>
                    <td>{bot.name}</td>
                    <td>
                      {bot.username ? (
                        <a href={`https://t.me/${bot.username}`} target="_blank" rel="noreferrer">
                          @{bot.username}
                        </a>
                      ) : (
                        <span className="text-muted">-</span>
                      )}
                    </td>
                    <td><code>{bot.bot_token_masked}</code></td>
                    <td>
                      {bot.is_active ? (
                        <span className="badge bg-success">已启用</span>
                      ) : (
                        <span className="badge bg-secondary">已禁用</span>
                      )}
                    </td>
                    <td>
                      {bot.created_at
                        ? new Date(bot.created_at).toLocaleString('zh-CN', {
                            year: 'numeric', month: '2-digit', day: '2-digit',
                            hour: '2-digit', minute: '2-digit',
                          })
                        : '-'}
                    </td>
                    <td>
                      <div className="btn-group btn-group-sm">
                        <button
                          className="btn btn-outline-primary"
                          title="编辑"
                          onClick={() => setFormMode(bot)}
                        >
                          <i className="bi bi-pencil" />
                        </button>
                        <button
                          className={`btn btn-outline-${bot.is_active ? 'secondary' : 'success'}`}
                          title={bot.is_active ? '禁用' : '启用'}
                          onClick={() => handleToggle(bot)}
                        >
                          <i className={`bi bi-${bot.is_active ? 'pause-circle' : 'play-circle'}`} />
                        </button>
                        <button
                          className="btn btn-outline-danger"
                          title="删除"
                          onClick={() => handleDelete(bot)}
                        >
                          <i className="bi bi-trash" />
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
                <li className="page-item disabled">
                  <span className="page-link">{page} / {data.total_pages}</span>
                </li>
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

      {/* Create/Edit Modal */}
      {formMode && (
        <BotFormModal
          bot={formMode === 'create' ? null : formMode}
          onClose={() => setFormMode(null)}
          onSubmit={handleFormSubmit}
        />
      )}
    </>
  )
}
