import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { usePortfolioCtx } from '../context/PortfolioContext'
import { portfolioApi, watchlistApi, type Position, type Transaction, type WatchlistItem, type RealizedPnL, type SectorDistribution } from '../lib/api'
import { fmt, fmtCurrency, fmtPct, pctColor, fmtDate } from '../lib/utils'
import { StatTile } from '../components/ui/StatTile'
import { DeltaBadge } from '../components/ui/DeltaBadge'
import { TickerLogo } from '../components/ui/TickerLogo'
import { AllocationPie, PnLBarChart, PerformanceChart } from '../components/charts/PortfolioCharts'
import { TrendingUp, TrendingDown, RefreshCw, Loader2, AlertCircle, Trash2, AlertTriangle } from 'lucide-react'

function HoldingRow({ pos, onClick }: { pos: Position; onClick: () => void }) {
  const pnlColor = pctColor(pos.pnl_pct)
  return (
    <div
      onClick={onClick}
      className="flex items-center gap-3 px-4 py-3 rounded-xl border transition-all hover:border-[var(--accent)] hover:border-opacity-40 cursor-pointer"
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

function TxRow({ tx, onClick }: { tx: Transaction; onClick: () => void }) {
  const isBuy = tx.side === 'BUY'
  return (
    <div onClick={onClick} className="flex items-center gap-3 px-3 py-2 text-sm cursor-pointer rounded-lg hover:bg-[var(--surface-2)] transition-colors">
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
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [txLimit, setTxLimit] = useState(10)

  const { data: watchlistItems = [] } = useQuery({
    queryKey: ['watchlist', activeId],
    queryFn: () => watchlistApi.list(activeId),
    staleTime: 30_000,
  })
  const handleRemoveWatch = async (ticker: string) => {
    await watchlistApi.remove(activeId, ticker)
    qc.invalidateQueries({ queryKey: ['watchlist', activeId] })
  }

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
    queryFn: () => portfolioApi.transactions(activeId, 200),
    staleTime: 60_000,
  })

  const { data: cashData } = useQuery({
    queryKey: ['portfolio-cash', activeId],
    queryFn: () => portfolioApi.cash(activeId),
    refetchInterval: 60_000,
  })

  const { data: perfData } = useQuery({
    queryKey: ['portfolio-performance', activeId],
    queryFn: () => portfolioApi.performance(activeId),
    staleTime: 300_000,
  })

  const { data: realizedPnlData = [] } = useQuery({
    queryKey: ['portfolio-realized-pnl', activeId],
    queryFn: () => portfolioApi.realizedPnl(activeId),
    staleTime: 300_000,
  })

  const { data: sectorData } = useQuery({
    queryKey: ['portfolio-sectors', activeId],
    queryFn: () => portfolioApi.sectorDistribution(activeId),
    staleTime: 600_000,
    enabled: positions.length > 0,
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

      {perfData && perfData.dates.length >= 1 && (
        <div className="rounded-xl border p-4 mb-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
          <h2 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>
            Rendimiento vs índices
          </h2>
          <PerformanceChart data={perfData} />
        </div>
      )}

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
          {positions.map(pos => (
            <HoldingRow
              key={pos.ticker}
              pos={pos}
              onClick={() => navigate('/market', { state: { ticker: pos.ticker } })}
            />
          ))}
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

          {sectorData && Object.keys(sectorData.sectors).length > 0 && (
            <div className="rounded-xl border p-4" style={{
              background: 'var(--surface)',
              borderColor: sectorData.warning ? 'rgba(234,179,8,0.4)' : 'var(--border)',
            }}>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                  Sectores
                </h3>
                {sectorData.warning && (
                  <div className="flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded"
                    style={{ background: 'rgba(234,179,8,0.12)', color: '#EAB308' }}>
                    <AlertTriangle size={10} />
                    Concentración alta
                  </div>
                )}
              </div>
              <div className="flex flex-col gap-1.5">
                {Object.entries(sectorData.sectors).map(([sector, pct]) => (
                  <div key={sector}>
                    <div className="flex justify-between text-xs mb-0.5">
                      <span style={{ color: 'var(--muted)' }}>{sector}</span>
                      <span className="font-mono font-semibold" style={{ color: 'var(--text)' }}>{pct}%</span>
                    </div>
                    <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--surface-2)' }}>
                      <div
                        className="h-full rounded-full transition-all"
                        style={{
                          width: `${pct}%`,
                          background: pct > 50 ? '#EAB308' : 'var(--accent)',
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
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

          {realizedPnlData.length > 0 && (
            <div className="rounded-xl border p-4" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
              <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>
                P&L Realizado
              </h3>
              <div className="flex flex-col gap-1.5">
                {realizedPnlData.map((r: RealizedPnL) => (
                  <div key={r.ticker} className="flex items-center justify-between text-xs">
                    <span className="font-mono font-semibold" style={{ color: 'var(--text)' }}>{r.ticker}</span>
                    <span className={`font-mono font-semibold ${r.realized_pnl >= 0 ? 'text-[var(--up)]' : 'text-[var(--down)]'}`}>
                      {r.realized_pnl >= 0 ? '+' : ''}{r.realized_pnl.toFixed(2)} USD
                    </span>
                  </div>
                ))}
                <div className="border-t pt-1.5 mt-1 flex items-center justify-between text-xs font-semibold" style={{ borderColor: 'var(--border)' }}>
                  <span style={{ color: 'var(--muted)' }}>Total</span>
                  {(() => {
                    const total = realizedPnlData.reduce((s, r) => s + r.realized_pnl, 0)
                    return (
                      <span className={total >= 0 ? 'text-[var(--up)]' : 'text-[var(--down)]'}>
                        {total >= 0 ? '+' : ''}{total.toFixed(2)} USD
                      </span>
                    )
                  })()}
                </div>
              </div>
            </div>
          )}

          {transactions.length > 0 && (
            <div className="rounded-xl border p-4" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
              <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>
                Transacciones recientes
              </h3>
              <div className="divide-y" style={{ borderColor: 'var(--border)' }}>
                {transactions.slice(0, txLimit).map(tx => (
                  <TxRow
                    key={tx.id}
                    tx={tx}
                    onClick={() => navigate('/market', { state: { ticker: tx.ticker } })}
                  />
                ))}
              </div>
              {transactions.length > txLimit && (
                <button
                  onClick={() => setTxLimit(l => l + 10)}
                  className="w-full mt-2 py-1.5 rounded-lg text-xs hover:opacity-80 transition-opacity"
                  style={{ color: 'var(--accent)', background: 'rgba(59,130,246,0.08)' }}
                >
                  Ver más ({transactions.length - txLimit} restantes)
                </button>
              )}
              {txLimit > 10 && (
                <button
                  onClick={() => setTxLimit(10)}
                  className="w-full mt-1 py-1 rounded-lg text-xs hover:opacity-80 transition-opacity"
                  style={{ color: 'var(--muted)' }}
                >
                  Ver menos
                </button>
              )}
            </div>
          )}

          {watchlistItems.length > 0 && (
            <div className="rounded-xl border p-4" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
              <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>
                En seguimiento ({watchlistItems.length})
              </h3>
              <div className="flex flex-col gap-1">
                {watchlistItems.map((item: WatchlistItem) => (
                  <div key={item.ticker} className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-[var(--surface-2)]">
                    <span className="font-mono font-semibold text-xs flex-1" style={{ color: 'var(--text)' }}>{item.ticker}</span>
                    {item.price != null && (
                      <span className="text-xs font-mono" style={{ color: 'var(--muted)' }}>
                        ${item.price.toFixed(2)}
                      </span>
                    )}
                    {item.change_pct != null && (
                      <span className={`text-[10px] font-semibold ${item.change_pct >= 0 ? 'text-[var(--up)]' : 'text-[var(--down)]'}`}>
                        {item.change_pct >= 0 ? '+' : ''}{item.change_pct.toFixed(2)}%
                      </span>
                    )}
                    <button
                      onClick={() => handleRemoveWatch(item.ticker)}
                      className="ml-1 p-1 rounded hover:bg-[var(--surface-2)] opacity-50 hover:opacity-100 transition-opacity"
                    >
                      <Trash2 size={11} style={{ color: 'var(--muted)' }} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
      </div>
    </div>
  )
}
