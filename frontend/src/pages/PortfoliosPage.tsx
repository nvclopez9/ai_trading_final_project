import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { usePortfolioCtx } from '../context/PortfolioContext'
import { portfolioApi } from '../lib/api'
import { fmtCurrency, pctColor } from '../lib/utils'
import { DeltaBadge } from '../components/ui/DeltaBadge'
import { useToast } from '../components/ui/Toast'
import { Plus, Loader2, BarChart2, Trash2, RotateCcw } from 'lucide-react'

function PortfolioCard({ id, name, risk, markets, onSelect, onDelete, onReset, isActive }: {
  id: number; name: string; risk: string; markets: string;
  onSelect: () => void; onDelete: () => void; onReset: () => void; isActive: boolean;
}) {
  const { data: value, isLoading } = useQuery({
    queryKey: ['portfolio-value', id],
    queryFn: () => portfolioApi.value(id),
    refetchInterval: 120_000,
  })

  const { data: positions = [] } = useQuery({
    queryKey: ['portfolio-positions', id],
    queryFn: () => portfolioApi.positions(id),
  })

  return (
    <div
      onClick={onSelect}
      className="rounded-2xl border p-5 cursor-pointer transition-all hover:border-[var(--accent)] group"
      style={{
        background: 'var(--surface)',
        borderColor: isActive ? 'var(--accent)' : 'var(--border)',
        boxShadow: isActive ? '0 0 0 1px var(--accent)' : 'none',
      }}
    >
      <div className="flex items-start justify-between mb-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-semibold" style={{ color: 'var(--text)' }}>{name}</h3>
            {isActive && (
              <span className="text-[10px] px-1.5 py-0.5 rounded-full font-medium"
                style={{ background: 'var(--accent-dim)', color: 'var(--accent)' }}>
                Activa
              </span>
            )}
          </div>
          <p className="text-xs mt-0.5" style={{ color: 'var(--muted)' }}>
            Riesgo: {risk} · {markets}
          </p>
        </div>
        <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={e => { e.stopPropagation(); onReset() }}
            className="p-1.5 rounded-lg hover:opacity-80"
            style={{ background: 'var(--surface-2)', color: 'var(--muted)' }}
            title="Resetear"
          >
            <RotateCcw size={12} />
          </button>
          {id !== 1 && (
            <button
              onClick={e => { e.stopPropagation(); onDelete() }}
              className="p-1.5 rounded-lg hover:opacity-80"
              style={{ background: 'rgba(239,68,68,0.12)', color: 'var(--down)' }}
              title="Eliminar"
            >
              <Trash2 size={12} />
            </button>
          )}
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 py-2" style={{ color: 'var(--muted)' }}>
          <Loader2 size={14} className="animate-spin" />
          <span className="text-xs">Cargando...</span>
        </div>
      ) : value ? (
        <div className="grid grid-cols-2 gap-3">
          <div>
            <p className="text-[10px] uppercase tracking-wider mb-0.5" style={{ color: 'var(--muted)' }}>Valor</p>
            <p className="font-bold mono text-base" style={{ color: 'var(--text)' }}>
              {fmtCurrency(value.total_value)}
            </p>
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-wider mb-0.5" style={{ color: 'var(--muted)' }}>P&L</p>
            <div className="flex items-center gap-1.5">
              <p className={`font-bold mono text-sm ${pctColor(value.total_pnl)}`}>
                {value.total_pnl >= 0 ? '+' : ''}{fmtCurrency(value.total_pnl)}
              </p>
            </div>
            <DeltaBadge value={value.total_pnl_pct} />
          </div>
        </div>
      ) : null}

      <div className="mt-3 pt-3 border-t flex items-center gap-1.5" style={{ borderColor: 'var(--border)' }}>
        <BarChart2 size={12} style={{ color: 'var(--muted)' }} />
        <span className="text-xs" style={{ color: 'var(--muted)' }}>{positions.length} posiciones</span>
      </div>
    </div>
  )
}

export function PortfoliosPage() {
  const { portfolios, activeId, setActiveId, reload } = usePortfolioCtx()
  const { toast } = useToast()
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState({ name: '', initial_cash: 10000, risk: 'moderado', markets: 'USA' })
  const [saving, setSaving] = useState(false)

  const handleCreate = async () => {
    if (!form.name.trim()) return
    setSaving(true)
    try {
      const p = await portfolioApi.create({ ...form, name: form.name.trim() })
      await reload()
      setActiveId(p.id)
      setCreating(false)
      setForm({ name: '', initial_cash: 10000, risk: 'moderado', markets: 'USA' })
      toast(`Cartera "${p.name}" creada con ${fmtCurrency(form.initial_cash)}`, 'success')
    } catch (e: unknown) {
      toast(e instanceof Error ? e.message : String(e), 'error')
    } finally { setSaving(false) }
  }

  const handleDelete = async (id: number) => {
    const target = portfolios.find(p => p.id === id)
    if (!confirm(`¿Eliminar la cartera "${target?.name}" y todas sus posiciones?`)) return
    try {
      await portfolioApi.delete(id)
      await reload()
      if (id === activeId) setActiveId(portfolios.find(p => p.id !== id)?.id ?? 1)
      toast(`Cartera "${target?.name}" eliminada`, 'success')
    } catch (e: unknown) { toast(e instanceof Error ? e.message : String(e), 'error') }
  }

  const handleReset = async (id: number) => {
    const target = portfolios.find(p => p.id === id)
    if (!confirm(`¿Resetear "${target?.name}"? Se borrarán posiciones y transacciones.`)) return
    try {
      await portfolioApi.reset(id)
      await reload()
      toast(`Cartera "${target?.name}" reseteada`, 'success')
    } catch (e: unknown) { toast(e instanceof Error ? e.message : String(e), 'error') }
  }

  return (
    <div className="flex-1 overflow-y-auto p-6" style={{ background: 'var(--bg)' }}>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--text)' }}>Mis Carteras</h1>
          <p className="text-sm" style={{ color: 'var(--muted)' }}>{portfolios.length} cartera{portfolios.length !== 1 ? 's' : ''} configurada{portfolios.length !== 1 ? 's' : ''}</p>
        </div>
        <button
          onClick={() => setCreating(true)}
          className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-medium transition-all hover:opacity-80"
          style={{ background: 'var(--accent)', color: 'white' }}
        >
          <Plus size={15} /> Nueva cartera
        </button>
      </div>

      {creating && (
        <div
          className="rounded-2xl border p-5 mb-5"
          style={{ background: 'var(--surface)', borderColor: 'var(--accent)' }}
        >
          <h3 className="font-semibold mb-4" style={{ color: 'var(--text)' }}>Nueva cartera</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
            {[
              { label: 'Nombre', key: 'name', type: 'text', placeholder: 'Mi Cartera Growth' },
              { label: 'Capital inicial (USD)', key: 'initial_cash', type: 'number', placeholder: '10000' },
            ].map(({ label, key, type, placeholder }) => (
              <div key={key}>
                <label className="text-xs mb-1 block" style={{ color: 'var(--muted)' }}>{label}</label>
                <input
                  type={type}
                  value={(form as any)[key]}
                  onChange={e => setForm(f => ({ ...f, [key]: type === 'number' ? Number(e.target.value) : e.target.value }))}
                  placeholder={placeholder}
                  className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                  style={{ background: 'var(--surface-2)', color: 'var(--text)', border: '1px solid var(--border)' }}
                />
              </div>
            ))}
            <div>
              <label className="text-xs mb-1 block" style={{ color: 'var(--muted)' }}>Riesgo</label>
              <select
                value={form.risk}
                onChange={e => setForm(f => ({ ...f, risk: e.target.value }))}
                className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                style={{ background: 'var(--surface-2)', color: 'var(--text)', border: '1px solid var(--border)' }}
              >
                <option value="conservador">Conservador</option>
                <option value="moderado">Moderado</option>
                <option value="agresivo">Agresivo</option>
              </select>
            </div>
            <div>
              <label className="text-xs mb-1 block" style={{ color: 'var(--muted)' }}>Mercados</label>
              <select
                value={form.markets}
                onChange={e => setForm(f => ({ ...f, markets: e.target.value }))}
                className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                style={{ background: 'var(--surface-2)', color: 'var(--text)', border: '1px solid var(--border)' }}
              >
                <option value="USA">USA</option>
                <option value="EUROPA">Europa</option>
                <option value="GLOBAL">Global</option>
                <option value="USA,EUROPA">USA + Europa</option>
              </select>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleCreate}
              disabled={saving}
              className="px-4 py-2 rounded-xl text-sm font-medium transition-all hover:opacity-80 disabled:opacity-50"
              style={{ background: 'var(--accent)', color: 'white' }}
            >
              {saving ? 'Creando...' : 'Crear'}
            </button>
            <button
              onClick={() => setCreating(false)}
              className="px-4 py-2 rounded-xl text-sm transition-all hover:opacity-80"
              style={{ background: 'var(--surface-2)', color: 'var(--muted)', border: '1px solid var(--border)' }}
            >
              Cancelar
            </button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {portfolios.map(p => (
          <PortfolioCard
            key={p.id}
            id={p.id}
            name={p.name}
            risk={p.risk}
            markets={p.markets}
            isActive={p.id === activeId}
            onSelect={() => setActiveId(p.id)}
            onDelete={() => handleDelete(p.id)}
            onReset={() => handleReset(p.id)}
          />
        ))}
      </div>
    </div>
  )
}
