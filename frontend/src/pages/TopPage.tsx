import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { marketApi, type QuoteRow } from '../lib/api'
import { fmt, fmtVolume } from '../lib/utils'
import { DeltaBadge } from '../components/ui/DeltaBadge'
import { TickerLogo } from '../components/ui/TickerLogo'
import { Flame, Loader2, TrendingUp, TrendingDown, Activity } from 'lucide-react'

type Tab = 'gainers' | 'losers' | 'actives'

function TickerCard({ row, onClick }: { row: QuoteRow; onClick: () => void }) {
  return (
    <div
      onClick={onClick}
      className="rounded-2xl border p-4 cursor-pointer transition-all hover:border-[var(--accent)] hover:scale-[1.01]"
      style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
    >
      <div className="flex items-center gap-2 mb-3">
        <TickerLogo ticker={row.ticker} size={32} />
        <div className="min-w-0">
          <p className="font-bold mono text-sm" style={{ color: 'var(--text)' }}>{row.ticker}</p>
          {row.name && <p className="text-[10px] truncate" style={{ color: 'var(--muted)' }}>{row.name}</p>}
        </div>
      </div>
      <p className="font-bold text-lg mono mb-1" style={{ color: 'var(--text)' }}>{fmt(row.price, 2, '$')}</p>
      <DeltaBadge value={row.change_pct} big />
      {row.volume > 0 && (
        <p className="text-[10px] mt-2 mono" style={{ color: 'var(--dim)' }}>{fmtVolume(row.volume)} vol</p>
      )}
    </div>
  )
}

const TABS: { id: Tab; label: string; icon: typeof TrendingUp }[] = [
  { id: 'gainers', label: 'Gainers', icon: TrendingUp },
  { id: 'losers', label: 'Losers', icon: TrendingDown },
  { id: 'actives', label: 'Más activos', icon: Activity },
]

export function TopPage() {
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>('gainers')

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['hot-tickers'],
    queryFn: marketApi.hot,
    refetchInterval: 300_000,
    staleTime: 300_000,
  })

  const rows = data?.[tab] ?? []

  const handleView = (ticker: string) => {
    sessionStorage.setItem('market_ticker', ticker)
    navigate('/market')
  }

  return (
    <div className="flex-1 overflow-y-auto p-6" style={{ background: 'var(--bg)' }}>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Flame size={20} style={{ color: '#F97316' }} />
          <div>
            <h1 className="text-xl font-bold" style={{ color: 'var(--text)' }}>Top del Día</h1>
            <p className="text-sm" style={{ color: 'var(--muted)' }}>Mayores movimientos del universo S&P 500</p>
          </div>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs hover:opacity-80 disabled:opacity-40"
          style={{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--muted)' }}
        >
          {isFetching ? <Loader2 size={12} className="animate-spin" /> : '↻'} Refrescar
        </button>
      </div>

      {/* Tabs */}
      <div
        className="flex gap-1 p-1 rounded-xl mb-6 w-fit"
        style={{ background: 'var(--surface)' }}
      >
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all"
            style={{
              background: tab === id ? 'var(--surface-2)' : 'transparent',
              color: tab === id ? 'var(--text)' : 'var(--muted)',
            }}
          >
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 py-8" style={{ color: 'var(--muted)' }}>
          <Loader2 size={20} className="animate-spin" /> Cargando snapshot del mercado...
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
          {rows.map(row => (
            <TickerCard key={row.ticker} row={row} onClick={() => handleView(row.ticker)} />
          ))}
        </div>
      )}

      <p className="text-[10px] mt-6" style={{ color: 'var(--muted)' }}>
        Snapshot cacheado 5 min. Haz clic en una tarjeta para ver el detalle en Mercado.
      </p>
    </div>
  )
}
