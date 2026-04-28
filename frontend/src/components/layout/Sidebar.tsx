import { NavLink, useNavigate } from 'react-router-dom'
import {
  MessageSquare, BarChart2, Briefcase, TrendingUp, Flame, Newspaper, HelpCircle, User,
  ChevronDown, Plus, Trash2, RefreshCw
} from 'lucide-react'
import { useState } from 'react'
import { usePortfolioCtx } from '../../context/PortfolioContext'
import { portfolioApi } from '../../lib/api'
import { useToast } from '../ui/Toast'

const NAV = [
  { to: '/chat', icon: MessageSquare, label: 'Chat IA' },
  { to: '/portfolio', icon: Briefcase, label: 'Mi Cartera' },
  { to: '/portfolios', icon: BarChart2, label: 'Mis Carteras' },
  { to: '/market', icon: TrendingUp, label: 'Mercado' },
  { to: '/top', icon: Flame, label: 'Top del Día' },
  { to: '/news', icon: Newspaper, label: 'Noticias' },
  { to: '/help', icon: HelpCircle, label: 'Ayuda' },
  { to: '/profile', icon: User, label: 'Mi Perfil' },
]

export function Sidebar() {
  const { portfolios, activeId, setActiveId, reload } = usePortfolioCtx()
  const navigate = useNavigate()
  const { toast } = useToast()
  const [open, setOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState('')

  const active = portfolios.find(p => p.id === activeId)

  const handleCreate = async () => {
    if (!newName.trim()) return
    try {
      const p = await portfolioApi.create({ name: newName.trim(), initial_cash: 10000, risk: 'moderado', markets: 'USA' })
      await reload()
      setActiveId(p.id)
      setNewName('')
      setCreating(false)
      toast(`Cartera "${p.name}" creada`, 'success')
    } catch (e: unknown) {
      toast(e instanceof Error ? e.message : String(e), 'error')
    }
  }

  const handleDelete = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm('¿Eliminar esta cartera?')) return
    try {
      await portfolioApi.delete(id)
      await reload()
      if (id === activeId && portfolios.length > 1) {
        setActiveId(portfolios.find(p => p.id !== id)?.id ?? 1)
      }
      toast('Cartera eliminada', 'success')
    } catch (e: unknown) {
      toast(e instanceof Error ? e.message : String(e), 'error')
    }
  }

  return (
    <aside
      className="w-56 flex-shrink-0 flex flex-col h-screen border-r"
      style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
    >
      {/* Logo */}
      <div className="px-5 py-5 border-b" style={{ borderColor: 'var(--border)' }}>
        <div className="flex items-center gap-2.5">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center text-white font-bold text-sm"
            style={{
              background: 'linear-gradient(135deg, var(--accent) 0%, var(--accent-2) 100%)',
              boxShadow: '0 4px 12px var(--accent-glow)',
            }}
          >
            IA
          </div>
          <div className="flex flex-col leading-tight">
            <span className="font-semibold text-sm" style={{ color: 'var(--text)' }}>
              Bot Inversiones
            </span>
            <span className="text-[10px]" style={{ color: 'var(--muted)' }}>
              v1.0
            </span>
          </div>
        </div>
      </div>

      {/* Portfolio selector */}
      <div className="px-3 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
        <p className="text-[10px] uppercase tracking-wider mb-1.5" style={{ color: 'var(--muted)' }}>Cartera activa</p>
        <button
          onClick={() => setOpen(!open)}
          className="w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-colors hover:opacity-80"
          style={{ background: 'var(--surface-2)', color: 'var(--text)' }}
        >
          <span className="truncate font-medium">{active?.name ?? '—'}</span>
          <ChevronDown size={14} style={{ color: 'var(--muted)' }} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
        </button>

        {open && (
          <div
            className="mt-1 rounded-lg border overflow-hidden"
            style={{ background: 'var(--surface-2)', borderColor: 'var(--border)' }}
          >
            {portfolios.map(p => (
              <div
                key={p.id}
                onClick={() => { setActiveId(p.id); setOpen(false) }}
                className="flex items-center justify-between px-3 py-2 cursor-pointer text-sm hover:opacity-80 transition-colors"
                style={{
                  background: p.id === activeId ? 'var(--accent-dim)' : 'transparent',
                  color: p.id === activeId ? 'var(--accent)' : 'var(--text)',
                }}
              >
                <span className="truncate">{p.name}</span>
                {p.id !== 1 && (
                  <button onClick={(e) => handleDelete(p.id, e)} className="opacity-40 hover:opacity-100 ml-2">
                    <Trash2 size={12} />
                  </button>
                )}
              </div>
            ))}
            {creating ? (
              <div className="px-3 py-2 flex gap-1">
                <input
                  autoFocus
                  value={newName}
                  onChange={e => setNewName(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') handleCreate(); if (e.key === 'Escape') setCreating(false) }}
                  placeholder="Nombre..."
                  className="flex-1 bg-transparent text-xs outline-none"
                  style={{ color: 'var(--text)' }}
                />
                <button onClick={handleCreate} className="text-xs font-medium" style={{ color: 'var(--accent)' }}>OK</button>
              </div>
            ) : (
              <button
                onClick={() => setCreating(true)}
                className="w-full flex items-center gap-2 px-3 py-2 text-xs transition-colors hover:opacity-80"
                style={{ color: 'var(--muted)' }}
              >
                <Plus size={12} /> Nueva cartera
              </button>
            )}
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            onClick={() => {
              if (to === '/portfolio' || to === '/chat') navigate(to)
            }}
            className={({ isActive }) =>
              `relative flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all duration-150 ${
                isActive ? 'font-medium' : 'hover:bg-[var(--surface-2)]'
              }`
            }
            style={({ isActive }) => ({
              background: isActive ? 'var(--accent-dim)' : 'transparent',
              color: isActive ? 'var(--accent)' : 'var(--muted)',
            })}
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <span
                    className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full"
                    style={{ background: 'var(--accent)', boxShadow: '0 0 8px var(--accent-glow)' }}
                  />
                )}
                <Icon size={16} />
                {label}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-3 py-4 border-t text-[10px]" style={{ borderColor: 'var(--border)', color: 'var(--muted)' }}>
        <div className="flex items-center gap-1">
          <RefreshCw size={10} />
          <span>Datos vía Yahoo Finance</span>
        </div>
        <p className="mt-1 leading-tight opacity-60">Solo educativo. No es asesoramiento financiero.</p>
      </div>
    </aside>
  )
}
