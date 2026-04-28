import { useQuery } from '@tanstack/react-query'
import { usePortfolioCtx } from '../context/PortfolioContext'
import { portfolioApi, type Position, type Transaction } from '../lib/api'
import { fmt, fmtCurrency, fmtPct, pctColor, fmtDate } from '../lib/utils'
import { StatTile } from '../components/ui/StatTile'
import { DeltaBadge } from '../components/ui/DeltaBadge'
import { TickerLogo } from '../components/ui/TickerLogo'
import { AllocationPie, PnLBarChart } from '../components/charts/PortfolioCharts'
import { TrendingUp, TrendingDown, RefreshCw, Loader2, AlertCircle } from 'lucide-react'

function HoldingRow({ pos }: { pos: Position }) {
  const pnlColor = pctColor(pos.pnl_pct)
  return (
    <div
      className="flex items-center gap-3 px-4 py-3 rounded-xl border transition-all hover:border-[var(--accent)] hover:border-opacity-40"
      style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
    >
      <TickerLogo ticker={pos.ticker} size={36} />

      <div className="flex-1 min-w-0">
        <p className="font-semibold text-sm mono" style={{ color: 'var(--text)' }}>{pos.ticker}</p>
        <p className="text-xs" style={{ color: 'var(--muted)' }}>{pos.qty} acciones · Precio medio: {fmt(pos.avg_price, 2, '$')}</p>
      </div>

      <div className="text-right min-w-[90px]">
        <p className="font-bold text-sm mono" style={{ color: 'var(--text)' }}>
          {fmtCurrency(pos.market_value)}
        </p>
        <DeltaBadge value={pos.pnl_pct} />
      </div>

      <div className="text-right min-w-[80px] hidden sm:block">
        <p className={`text-sm font-mono font-semibold ${pnlColor}`}>
          {pos.pnl != null ? (pos.pnl >= 0 ? '+' : '') + fmtCurrency(pos.pnl) : '—'}
        </p>
        {pos.after_hours_price && (
          <p className="text-[10px]" style={{ color: 'var(--muted)' }}>
            AH: {fmt(pos.after_hours_price, 2, '$')}
            <span className={pos.after_hours_change_pct != null ? pctColor(pos.after_hours_change_pct) : ''}>
              {pos.after_hours_change_pct != null ? ` (${fmtPct(pos.after_hours_change_pct)})` : ''}
            </span>
          </p>
        )}
      </div>
    </div>
  )
}

function TxRow({ tx }: { tx: Transaction }) {
  const isBuy = tx.side === 'BUY'
  return (
    <div className="flex items-center gap-3 px-3 py-2 text-sm">
      <div
        className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0"
        style={{ background: isBuy ? 'rgba(16,185,129,0.12)' : 'rgba(239,68,68,0.12)' }}
      >
        {isBuy
          ? <TrendingUp size={12} style={{ color: 'var(--up)' }} />
          : <TrendingDown size={12} style={{ color: 'var(--down)' }} />}
      </div>
      <span className="font-mono font-semibold w-12" style={{ color: isBuy ? 'var(--up)' : 'var(--down)' }}>
        {tx.side}
      </span>
      <span className="font-semibold" style={{ color: 'var(--text)' }}>{tx.ticker}</span>
      <span style={{ color: 'var(--muted)' }}>{tx.qty}@{fmt(tx.price, 2, '$')}</span>
      <span className="ml-auto text-xs" style={{ color: 'var(--muted)' }}>{fmtDate(tx.ts)}</span>
    </div>
  )
}

export function PortfolioPage() {
  const { activeId, portfolios } = usePortfolioCtx()
  const portfolio = portfolios.find(p => p.id === activeId)

  const { data: value, isLoading: loadingValue, refetch: refetchValue } = useQuery({
    queryKey: ['portfolio-value', activeId],
    queryFn: () => portfolioApi.value(activeId),
    refetchInterval: 60_000,
  })

  const { data: positions = [], isLoading: loadingPos } = useQuery({
    queryKey: ['portfolio-positions', activeId],
    queryFn: () => portfolioApi.positions(activeId),
    refetchInterval: 60_000,
  })

  const { data: transactions = [] } = useQuery({
    queryKey: ['portfolio-transactions', activeId],
    queryFn: () => portfolioApi.transactions(activeId, 20),
  })

  const { data: cashData } = useQuery({
    queryKey: ['portfolio-cash', activeId],
    queryFn: () => portfolioApi.cash(activeId),
    refetchInterval: 60_000,
  })

  const loading = loadingValue || loadingPos

  return (
    <div className="flex-1 overflow-y-auto" style={{ background: 'var(--bg)' }}>
      {/* Sticky header */}
      <div
        className="sticky top-0 z-20 px-6 py-4 border-b backdrop-blur-md flex items-center justify-between"
        style={{
          borderColor: 'var(--border)',
          background: 'rgba(10,10,10,0.85)',
        }}
      >
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--text)' }}>
            {portfolio?.name ?? 'Mi Cartera'}
          </h1>
          <p className="text-xs" style={{ color: 'var(--muted)' }}>
            Riesgo: {portfolio?.risk} · Mercados: {portfolio?.markets}
          </p>
        </div>
        <button
          onClick={() => refetchValue()}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs hover:bg-[var(--surface-2)]"
          style={{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--muted)' }}
        >
          <RefreshCw size={12} /> Actualizar
        </button>
      </div>

      <div className="p-6">

      {loading && (
        <div className="flex items-center gap-2 py-4" style={{ color: 'var(--muted)' }}>
          <Loader2 size={16} className="animate-spin" /> Cargando cartera...
        </div>
      )}

      {/* Summary tiles */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-6">
        {value ? (
          <>
            <StatTile
              label="Valor total"
              value={fmtCurrency(value.total_value)}
              sub={value.total_value_after_hours ? `AH: ${fmtCurrency(value.total_value_after_hours)}` : undefined}
            />
            <StatTile
              label="P&L total"
              value={`${value.total_pnl >= 0 ? '+' : ''}${fmtCurrency(value.total_pnl)}`}
              sub={fmtPct(value.total_pnl_pct)}
              tone="auto"
              numericValue={value.total_pnl}
            />
            <StatTile
              label="Inversión"
              value={fmtCurrency(value.total_cost)}
            />
            <StatTile
              label="Variación AH"
              value={value.after_hours_delta != null ? `${value.after_hours_delta >= 0 ? '+' : ''}${fmtCurrency(value.after_hours_delta)}` : '—'}
              sub={value.after_hours_delta_pct != null ? fmtPct(value.after_hours_delta_pct) : 'Sin datos AH'}
              tone="auto"
              numericValue={value.after_hours_delta}
            />
          </>
        ) : (
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="rounded-xl border p-4 animate-pulse" style={{ background: 'var(--surface)', borderColor: 'var(--border)', height: 72 }} />
          ))
        )}
        <StatTile
          label="Cash libre"
          value={cashData != null ? fmtCurrency(cashData.cash) : '—'}
          sub="Disponible para invertir"
        />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Holdings */}
        <div className="xl:col-span-2 flex flex-col gap-2">
          <h2 className="text-sm font-semibold uppercase tracking-wider mb-1" style={{ color: 'var(--muted)' }}>
            Posiciones ({positions.length})
          </h2>
          {positions.length === 0 && !loading && (
            <div
              className="flex flex-col items-center gap-2 py-10 rounded-xl border"
              style={{ borderColor: 'var(--border)', color: 'var(--muted)' }}
            >
              <AlertCircle size={24} />
              <p className="text-sm">Sin posiciones. Usa el chat para comprar.</p>
            </div>
          )}
          {positions.map(pos => <HoldingRow key={pos.ticker} pos={pos} />)}
        </div>

        {/* Sidebar: pie + pnl chart + transactions */}
        <div className="flex flex-col gap-4">
          {positions.length > 0 && (
            <div className="rounded-xl border p-4" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
              <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>
                Distribución
              </h3>
              <AllocationPie positions={positions} />
            </div>
          )}

          {positions.length > 0 && (
            <div className="rounded-xl border p-4" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
              <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>
                P&L por posición
              </h3>
              <PnLBarChart positions={positions} />
            </div>
          )}

          {transactions.length > 0 && (
            <div className="rounded-xl border p-4" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
              <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>
                Transacciones recientes
              </h3>
              <div className="divide-y" style={{ borderColor: 'var(--border)' }}>
                {transactions.slice(0, 10).map(tx => <TxRow key={tx.id} tx={tx} />)}
              </div>
            </div>
          )}
        </div>
      </div>
      </div>
    </div>
  )
}
