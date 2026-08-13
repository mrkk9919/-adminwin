import { useState, useRef, useEffect } from 'react'
import type { Bot } from '../types'
import { revealBotToken } from '../api'

interface BotFormModalProps {
  bot: Bot | null // null = creating a new bot
  onClose: () => void
  onSubmit: (data: { name: string; bot_token?: string; is_active?: boolean }, botId?: number) => Promise<void>
}

export default function BotFormModal({ bot, onClose, onSubmit }: BotFormModalProps) {
  const isEdit = !!bot
  const [name, setName] = useState(bot?.name || '')
  const [token, setToken] = useState('')
  const [isActive, setIsActive] = useState(bot?.is_active ?? true)
  const [showToken, setShowToken] = useState(!isEdit)
  const [tokenLoading, setTokenLoading] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const modalRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const bootstrap = (window as unknown as Record<string, unknown>).bootstrap as {
      Modal: new (el: HTMLElement) => { show: () => void; hide: () => void }
    }
    if (bootstrap && modalRef.current) {
      const modal = new bootstrap.Modal(modalRef.current)
      modal.show()

      const el = modalRef.current
      el.addEventListener('hidden.bs.modal', () => {
        onClose()
        modal.hide()
      })
    }
  }, [onClose])

  async function handleRevealToken() {
    if (!bot) return
    setTokenLoading(true)
    setError('')
    try {
      const res = await revealBotToken(bot.id)
      setToken(res.bot_token)
      setShowToken(true)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setTokenLoading(false)
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    if (!name.trim()) {
      setError('请输入备注名称')
      return
    }
    if (!isEdit && !token.trim()) {
      setError('请输入 Bot Token')
      return
    }
    setLoading(true)
    try {
      const payload: { name: string; bot_token?: string; is_active?: boolean } = { name: name.trim() }
      if (!isEdit) {
        payload.bot_token = token.trim()
        payload.is_active = isActive
      } else if (token.trim()) {
        payload.bot_token = token.trim()
      }
      await onSubmit(payload, bot?.id)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal fade" ref={modalRef} tabIndex={-1}>
      <div className="modal-dialog">
        <div className="modal-content">
          <form onSubmit={handleSubmit}>
            <div className="modal-header">
              <h5 className="modal-title">{isEdit ? '编辑机器人' : '新增机器人'}</h5>
              <button type="button" className="btn-close" data-bs-dismiss="modal" onClick={onClose} />
            </div>
            <div className="modal-body">
              {error && <div className="alert alert-danger py-2">{error}</div>}

              <div className="mb-3">
                <label className="form-label">备注名称</label>
                <input
                  type="text"
                  className="form-control"
                  placeholder="例如：客服机器人"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  autoFocus
                />
              </div>

              <div className="mb-3">
                <label className="form-label">
                  Bot Token{' '}
                  {isEdit && !showToken && (
                    <button
                      type="button"
                      className="btn btn-link btn-sm p-0 ms-1"
                      onClick={handleRevealToken}
                      disabled={tokenLoading}
                    >
                      {tokenLoading ? '加载中...' : '查看/修改'}
                    </button>
                  )}
                </label>
                {isEdit && !showToken ? (
                  <input type="text" className="form-control" value={bot!.bot_token_masked} disabled readOnly />
                ) : (
                  <input
                    type="text"
                    className="form-control font-monospace"
                    placeholder="从 @BotFather 获取的 Token"
                    value={token}
                    onChange={(e) => setToken(e.target.value)}
                  />
                )}
                <div className="form-text">
                  {isEdit ? '留空表示不修改 Token。' : '将通过 Telegram API 校验 Token 有效性并自动获取用户名。'}
                </div>
              </div>

              {!isEdit && (
                <div className="form-check form-switch">
                  <input
                    className="form-check-input"
                    type="checkbox"
                    id="botActiveSwitch"
                    checked={isActive}
                    onChange={(e) => setIsActive(e.target.checked)}
                  />
                  <label className="form-check-label" htmlFor="botActiveSwitch">
                    创建后立即启用
                  </label>
                </div>
              )}
            </div>
            <div className="modal-footer">
              <button type="button" className="btn btn-secondary" data-bs-dismiss="modal" onClick={onClose}>
                取消
              </button>
              <button type="submit" className="btn btn-primary" disabled={loading}>
                {loading && <span className="spinner-border spinner-border-sm me-1" />}
                {isEdit ? '保存' : '创建'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
