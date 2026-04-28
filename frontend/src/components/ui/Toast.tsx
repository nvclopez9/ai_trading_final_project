import { createContext, useContext, useState, useCallback, useEffect } from 'react'
import type { ReactNode } from 'react'
import { CheckCircle, AlertCircle, Info, X } from 'lucide-react'

type ToastKind = 'success' | 'error' | 'info'
interface Toast { id: string; kind: ToastKind; message: string }

interface Ctx {
  toast: (message: string, kind?: ToastKind) => void
}

const ToastCtx = createContext<Ctx | null>(null)

export function useToast() {
  const ctx = useContext(ToastCtx)
  if (!ctx) throw new Error('useToast must be inside ToastProvider')
  return ctx
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const remove = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  const toast = useCallback((message: string, kind: ToastKind = 'info') => {
    const id = Math.random().toString(36).slice(2, 9)
    setToasts(prev => [...prev, { id, kind, message }])
    setTimeout(() => remove(id), 4000)
  }, [remove])

  return (
    <ToastCtx.Provider value={{ toast }}>
      {children}
      <div
        className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 max-w-sm"
        style={{ pointerEvents: 'none' }}
      >
        {toasts.map(t => <ToastItem key={t.id} toast={t} onClose={() => remove(t.id)} />)}
      </div>
    </ToastCtx.Provider>
  )
}

function ToastItem({ toast: t, onClose }: { toast: Toast; onClose: () => void }) {
  const [show, setShow] = useState(false)
  useEffect(() => { requestAnimationFrame(() => setShow(true)) }, [])

  const Icon = t.kind === 'success' ? CheckCircle : t.kind === 'error' ? AlertCircle : Info
  const color =
    t.kind === 'success' ? 'var(--up)' :
    t.kind === 'error'   ? 'var(--down)' :
                            'var(--blue)'
  const tint =
    t.kind === 'success' ? 'rgba(16,185,129,0.08)' :
    t.kind === 'error'   ? 'rgba(239,68,68,0.08)' :
                            'rgba(59,130,246,0.08)'

  return (
    <div
      className="flex items-start gap-3 px-4 py-3 rounded-xl border shadow-lg"
      style={{
        background: 'var(--surface)',
        borderColor: 'var(--border-2)',
        boxShadow: 'var(--shadow-lg)',
        pointerEvents: 'auto',
        transform: show ? 'translateX(0)' : 'translateX(20px)',
        opacity: show ? 1 : 0,
        transition: 'transform 200ms ease, opacity 200ms ease',
      }}
    >
      <div
        className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"
        style={{ background: tint }}
      >
        <Icon size={14} style={{ color }} />
      </div>
      <p className="flex-1 text-sm leading-snug" style={{ color: 'var(--text)' }}>{t.message}</p>
      <button onClick={onClose} className="opacity-50 hover:opacity-100" style={{ color: 'var(--muted)' }}>
        <X size={14} />
      </button>
    </div>
  )
}
