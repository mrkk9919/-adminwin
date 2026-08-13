import { useState, useRef, useEffect } from 'react'
import type { User } from '../types'

interface BanModalProps {
  user: User
  onClose: () => void
  onConfirm: (userId: number, isBan: boolean, reason: string) => void
}

export default function BanModal({ user, onClose, onConfirm }: BanModalProps) {
  const isBanned = user.is_banned
  const [reason, setReason] = useState('')
  const [loading, setLoading] = useState(false)
  const modalRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // Show modal using Bootstrap JS
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

  async function handleConfirm() {
    setLoading(true)
    try {
      onConfirm(user.id, !isBanned, reason)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal fade" ref={modalRef} tabIndex={-1}>
      <div className="modal-dialog">
        <div className="modal-content">
          <div className="modal-header">
            <h5 className="modal-title">{isBanned ? '解封用户' : '封禁用户'}</h5>
            <button type="button" className="btn-close" data-bs-dismiss="modal" onClick={onClose} />
          </div>
          <div className="modal-body">
            <p>
              用户: <strong>{user.full_name}</strong> (@{user.username || user.tg_user_id})
            </p>
            {!isBanned && (
              <div className="mb-3">
                <label className="form-label">原因（可选）</label>
                <textarea
                  className="form-control"
                  rows={3}
                  placeholder="请输入封禁原因..."
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                />
              </div>
            )}
          </div>
          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" data-bs-dismiss="modal" onClick={onClose}>
              取消
            </button>
            <button
              type="button"
              className={`btn ${isBanned ? 'btn-success' : 'btn-danger'}`}
              onClick={handleConfirm}
              disabled={loading}
            >
              {loading && <span className="spinner-border spinner-border-sm me-1" />}
              {isBanned ? '确认解封' : '确认封禁'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
