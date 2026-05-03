import { useState, useRef, useEffect, useCallback } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useLocation } from 'react-router-dom'
import { marketApi, watchlistApi, type SearchResult, type WatchlistItem, streamChat } from '../lib/api'
import { fmt, fmtPct, fmtVolume, pctColor } from '../lib/utils'
import { DeltaBadge } from '../components/ui/DeltaBadge'
import { TickerLogo } from '../components/ui/TickerLogo'
import { StatTile } from '../components/ui/StatTile'
import { PriceChart } from '../components/charts/PriceChart'
import { CompareChart } from '../components/charts/CompareChart'
import { usePortfolioCtx } from '../context/PortfolioContext'
import { Search, Loader2, Sparkles, X, Plus, Bookmark, BookmarkCheck } from 'lucide-react'

const PERIODS = ['1d', '5d', '1mo', '6mo', 'ytd', '1y', '5y', 'max'] as const
type Period = typeof PERIODS[number]

const PERIOD_LABELS: Record<Period, string> = {
  '1d': '1D', '5d': '1S', '1mo': '1M', '6mo': '6M',
  'ytd': 'YTD', '1y': '1A', '5y': '5A', 'max': 'MAX',
}

function getInterval(p: Period): string {
  if (p === '1d' || p === '5d') return '1h'
  if (p === '5y' || p === 'max') return '1wk'
  return '1d'
}

// ── Quick-access groups ──────────────────────────────────────────────────────
const QUICK_GROUPS = [
  {
    label: 'S&P 500',
    color: '#10B981',
    tickers: ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'META', 'TSLA', 'JPM', 'V', 'NFLX', 'XOM', 'UNH'],
  },
  {
    label: 'ETFs',
    color: '#A855F7',
    tickers: ['SPY', 'QQQ', 'VOO', 'DIA', 'IWM', 'VTI', 'ARKK', 'XLK', 'XLF', 'GLD', 'IBIT'],
  },
  {
    label: 'Europa',
    color: '#3B82F6',
    tickers: ['ASML.AS', 'MC.PA', 'SAP.DE', 'NESN.SW', 'SHEL.L', 'SIE.DE', 'AZN.L', 'TTE.PA', 'ADS.DE', 'BAS.DE'],
  },
  {
    label: 'Asia / ADR',
    color: '#F59E0B',
    tickers: ['TSM', 'BABA', 'SONY', 'TM', 'BIDU', '9988.HK', '7203.T', 'NVO'],
  },
  {
    label: 'Crypto',
    color: '#EAB308',
    tickers: ['BTC-USD', 'ETH-USD', 'SOL-USD', 'BNB-USD', 'XRP-USD', 'IBIT', 'FBTC'],
  },
] as const

// ── Region color map ─────────────────────────────────────────────────────────
const REGION_COLOR: Record<string, string> = {
  USA: '#10B981',
  Europa: '#3B82F6',
  Asia: '#F59E0B',
  LatAm: '#EF4444',
  Crypto: '#EAB308',
  ETF: '#A855F7',
  Índices: '#6B7280',
  Futuros: '#6B7280',
  Divisas: '#06B6D4',
  Fondos: '#8B5CF6',
  Global: '#6B7280',
}

// ── Debounced search dropdown ────────────────────────────────────────────────
function SearchDropdown({
  results,
  isFetching,
  hasQuery,
  onCommit,
}: {
  results: SearchResult[]
  isFetching: boolean
  hasQuery: boolean
  onCommit: (s: string) => void
}) {
  if (!hasQuery) return null
  return (
    <div
      className="absolute top-full mt-1 left-0 right-0 rounded-xl border z-50 overflow-y-auto"
      style={{
        background: 'var(--surface)',
        borderColor: 'var(--border)',
        boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
        maxHeight: 320,
      }}
    >
      {isFetching && results.length === 0 && (
        <div className="flex items-center gap-2 px-3 py-2 text-xs" style={{ color: 'var(--muted)' }}>
          <Loader2 size={12} className="animate-spin" /> Buscando...
        </div>
      )}
      {!isFetching && results.length === 0 && (
        <p className="px-3 py-2 text-xs" style={{ color: 'var(--muted)' }}>No se encontraron resultados</p>
      )}
      {results.map(r => {
        const col = REGION_COLOR[r.region] ?? '#6B7280'
        return (
          <button
            key={r.symbol}
            onMouseDown={() => onCommit(r.symbol)}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-[var(--surface-2)] transition-colors"
          >
            <span className="font-mono font-bold flex-shrink-0 w-[5.5rem]" style={{ color: 'var(--text)' }}>{r.symbol}</span>
            <span className="flex-1 text-xs truncate" style={{ color: 'var(--muted)' }}>{r.name}</span>
            <span
              className="text-[10px] px-1.5 py-0.5 rounded font-semibold flex-shrink-0"
              style={{ background: col + '22', color: col }}
            >
              {r.region}
            </span>
            <span className="text-[10px] flex-shrink-0 hidden sm:block" style={{ color: 'var(--dim)' }}>{r.exchange}</span>
          </button>
        )
      })}
    </div>
  )
}

// ── Ticker search input ──────────────────────────────────────────────────────
function TickerSearch({ value, onSelect }: { value: string; onSelect: (s: string) => void }) {
  const [input, setInput] = useState(value)
  const [open, setOpen] = useState(false)
  const [debouncedQ, setDebouncedQ] = useState('')
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => { setInput(value) }, [value])

  useEffect(() => {
    if (input.length < 1) { setDebouncedQ(''); return }
    const t = setTimeout(() => setDebouncedQ(input), 350)
    return () => clearTimeout(t)
  }, [input])

  const { data: results = [], isFetching } = useQuery({
    queryKey: ['ticker-search', debouncedQ],
    queryFn: () => marketApi.search(debouncedQ, 10),
    enabled: debouncedQ.length >= 1,
    staleTime: 60_000,
  })

  const commit = (s: string) => {
    const sym = s.trim().toUpperCase()
    if (!sym) return
    setInput(sym)
    setOpen(false)
    onSelect(sym)
  }

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div ref={ref} className="relative flex-1 max-w-sm">
      <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none z-10" style={{ color: 'var(--muted)' }} />
      {isFetching && (
        <Loader2 size={12} className="animate-spin absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none z-10" style={{ color: 'var(--muted)' }} />
      )}
      <input
        value={input}
        onChange={e => { setInput(e.target.value.toUpperCase()); setOpen(true) }}
        onKeyDown={e => {
          if (e.key === 'Enter') commit(input)
          if (e.key === 'Escape') setOpen(false)
        }}
        onFocus={() => setOpen(true)}
        placeholder="Buscar ticker, empresa, índice..."
        className="w-full pl-9 pr-9 py-2 rounded-xl text-sm outline-none"
        style={{ background: 'var(--surface)', color: 'var(--text)', border: '1px solid var(--border)' }}
      />
      {open && (
        <SearchDropdown
          results={results}
          isFetching={isFetching}
          hasQuery={debouncedQ.length >= 1}
          onCommit={commit}
        />
      )}
    </div>
  )
}

// ── Quick-access tabs + chips ────────────────────────────────────────────────
function QuickAccess({ activeSymbol, onSelect }: { activeSymbol: string; onSelect: (s: string) => void }) {
  const [activeGroup, setActiveGroup] = useState(0)
  const group = QUICK_GROUPS[activeGroup]

  return (
    <div className="mb-5">
      <div className="flex gap-1 mb-2 flex-wrap">
        {QUICK_GROUPS.map((g, i) => (
          <button
            key={g.label}
            onClick={() => setActiveGroup(i)}
            className="px-2.5 py-1 rounded-full text-xs font-medium transition-all"
            style={{
              background: i === activeGroup ? g.color + '22' : 'var(--surface)',
              color: i === activeGroup ? g.color : 'var(--muted)',
              border: `1px solid ${i === activeGroup ? g.color + '55' : 'var(--border)'}`,
            }}
          >
            {g.label}
          </button>
        ))}
      </div>
      <div className="flex gap-1.5 flex-wrap">
        {group.tickers.map(s => (
          <button
            key={s}
            onClick={() => onSelect(s)}
            className="px-2.5 py-1 rounded-full text-xs transition-all hover:opacity-80 font-mono font-semibold"
            style={{
              background: s === activeSymbol ? group.color + '22' : 'var(--surface)',
              color: s === activeSymbol ? group.color : 'var(--muted)',
              border: `1px solid ${s === activeSymbol ? group.color + '55' : 'var(--border)'}`,
            }}
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  )
}

// ── Compare: chip input with real-time search ────────────────────────────────
function CompareInput({ base, onChange }: { base: string; onChange: (tickers: string[]) => void }) {
  const [chips, setChips] = useState<string[]>([])
  const [input, setInput] = useState('')
  const [open, setOpen] = useState(false)
  const [debouncedQ, setDebouncedQ] = useState('')
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (input.length < 1) { setDebouncedQ(''); return }
    const t = setTimeout(() => setDebouncedQ(input), 350)
    return () => clearTimeout(t)
  }, [input])

  const { data: rawResults = [], isFetching } = useQuery({
    queryKey: ['ticker-search-cmp', debouncedQ],
    queryFn: () => marketApi.search(debouncedQ, 8),
    enabled: debouncedQ.length >= 1,
    staleTime: 60_000,
  })

  const results = rawResults.filter(
    r => r.symbol !== base.toUpperCase() && !chips.includes(r.symbol),
  )

  const addChip = useCallback((s: string) => {
    const sym = s.trim().toUpperCase()
    if (!sym || sym === base.toUpperCase() || chips.includes(sym)) return
    const next = [...chips, sym]
    setChips(next)
    setInput('')
    setDebouncedQ('')
    setOpen(false)
    onChange(next)
  }, [chips, base, onChange])

  const removeChip = useCallback((sym: string) => {
    const next = chips.filter(c => c !== sym)
    setChips(next)
    onChange(next)
  }, [chips, onChange])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div ref={ref} className="relative">
      <div
        className="flex flex-wrap gap-1.5 items-center min-h-[38px] px-2 py-1.5 rounded-xl border"
        style={{ background: 'var(--surface-2)', borderColor: 'var(--border)' }}
      >
        {chips.map(c => (
          <span
            key={c}
            className="flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-mono font-semibold"
            style={{ background: 'rgba(59,130,246,0.15)', color: 'var(--blue)', border: '1px solid rgba(59,130,246,0.3)' }}
          >
            {c}
            <button onClick={() => removeChip(c)} className="hover:opacity-70 transition-opacity">
              <X size={10} />
            </button>
          </span>
        ))}
        {isFetching && <Loader2 size={12} className="animate-spin flex-shrink-0" style={{ color: 'var(--muted)' }} />}
        <input
          value={input}
          onChange={e => { setInput(e.target.value.toUpperCase()); setOpen(true) }}
          onFocus={() => setOpen(true)}
          onKeyDown={e => {
            if ((e.key === 'Enter' || e.key === ',') && input) { e.preventDefault(); addChip(input) }
            if (e.key === 'Backspace' && !input && chips.length) removeChip(chips[chips.length - 1])
          }}
          placeholder={chips.length === 0 ? 'Buscar ticker para comparar...' : ''}
          className="flex-1 min-w-[120px] bg-transparent text-sm outline-none"
          style={{ color: 'var(--text)' }}
        />
      </div>
      {open && debouncedQ.length >= 1 && results.length > 0 && (
        <div
          className="absolute top-full mt-1 left-0 right-0 rounded-xl border z-50 overflow-y-auto"
          style={{
            background: 'var(--surface)',
            borderColor: 'var(--border)',
            boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
            maxHeight: 240,
          }}
        >
          {results.map(r => {
            const col = REGION_COLOR[r.region] ?? '#6B7280'
            return (
              <button
                key={r.symbol}
                onMouseDown={() => addChip(r.symbol)}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-[var(--surface-2)] transition-colors"
              >
                <Plus size={11} className="flex-shrink-0" style={{ color: 'var(--muted)' }} />
                <span className="font-mono font-bold flex-shrink-0 w-[5rem]" style={{ color: 'var(--text)' }}>{r.symbol}</span>
                <span className="flex-1 text-xs truncate" style={{ color: 'var(--muted)' }}>{r.name}</span>
                <span
                  className="text-[10px] px-1.5 py-0.5 rounded font-semibold flex-shrink-0"
                  style={{ background: col + '22', color: col }}
                >
                  {r.region}
                </span>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ── AI analysis panel ────────────────────────────────────────────────────────
function AnalysisPanel({ text, loading }: { text: string; loading: boolean }) {
  if (!text && !loading) return null
  return (
    <div
      className="rounded-2xl border p-5 mb-5"
      style={{ background: 'var(--surface)', borderColor: 'rgba(59,130,246,0.3)' }}
    >
      <div className="flex items-center gap-2 mb-3">
        <Sparkles size={14} style={{ color: 'var(--accent)' }} />
        <h2 className="text-sm font-semibold" style={{ color: 'var(--accent)' }}>Análisis IA</h2>
        {loading && <Loader2 size={13} className="animate-spin ml-auto" style={{ color: 'var(--muted)' }} />}
      </div>
      <div className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--text)' }}>
        {text || <span style={{ color: 'var(--muted)' }}>Analizando...</span>}
      </div>
    </div>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────────
export function MarketPage() {
  const { activeId } = usePortfolioCtx()
  const qc = useQueryClient()
  const navigate = useNavigate()
  const location = useLocation()
  const [symbol, setSymbol] = useState<string>((location.state as any)?.ticker ?? 'AAPL')
  const [period, setPeriod] = useState<Period>('6mo')
  const [compareChips, setCompareChips] = useState<string[]>([])

  useEffect(() => {
    const t = (location.state as any)?.ticker
    if (t) { setSymbol(t); window.history.replaceState({}, '') }
  }, [location.state])

  const [analyzeText, setAnalyzeText] = useState('')
  const [analyzing, setAnalyzing] = useState(false)
  const analyzeAbort = useRef<AbortController | null>(null)

  const { data: watchlist = [] } = useQuery({
    queryKey: ['watchlist', activeId],
    queryFn: () => watchlistApi.list(activeId),
    staleTime: 30_000,
  })
  const isWatched = watchlist.some((w: WatchlistItem) => w.ticker === symbol)

  const handleToggleWatch = async () => {
    if (isWatched) {
      await watchlistApi.remove(activeId, symbol)
    } else {
      await watchlistApi.add(activeId, symbol)
    }
    qc.invalidateQueries({ queryKey: ['watchlist', activeId] })
  }

  const handleExplain = (label: string, val: string) => {
    const msg = `Explícame qué significa ${label} = ${val} para ${symbol}. ¿Es un valor bueno o malo para una empresa de su sector (${ticker?.sector ?? 'el suyo'})? Dame una explicación simple y concreta.`
    sessionStorage.setItem('chat_prefill', msg)
    navigate('/chat')
  }

  const { data: ticker, isLoading: loadTicker, error: errTicker } = useQuery({
    queryKey: ['ticker', symbol],
    queryFn: () => marketApi.ticker(symbol),
    enabled: !!symbol,
  })

  const { data: histData, isLoading: loadHist, error: errHist } = useQuery({
    queryKey: ['ticker-history', symbol, period],
    queryFn: () => marketApi.history(symbol, period, getInterval(period)),
    enabled: !!symbol,
  })

  const { data: fundamentals } = useQuery({
    queryKey: ['fundamentals', symbol],
    queryFn: () => marketApi.fundamentals(symbol),
    enabled: !!symbol,
  })

  const allCompareSymbols = [symbol, ...compareChips]
  const { data: compareData } = useQuery({
    queryKey: ['compare', allCompareSymbols],
    queryFn: () => marketApi.compare(allCompareSymbols),
    enabled: compareChips.length > 0,
  })

  const { data: compareHistData } = useQuery({
    queryKey: ['compare-history', allCompareSymbols, period],
    queryFn: async () =>
      Promise.all(allCompareSymbols.map(s => marketApi.history(s, period, getInterval(period)).then(h => ({ symbol: s, data: h.data })))),
    enabled: compareChips.length > 0,
  })

  const handleSymbolSelect = (s: string) => {
    setSymbol(s)
    setAnalyzeText('')
    setAnalyzing(false)
    analyzeAbort.current?.abort()
  }

  const handleAnalyze = () => {
    if (analyzing) {
      analyzeAbort.current?.abort()
      setAnalyzing(false)
      return
    }
    setAnalyzeText('')
    setAnalyzing(true)
    const prompt = `Analiza ${symbol} de forma detallada: precio actual, tendencia, fundamentales clave, riesgos principales y tu recomendación (comprar/mantener/vender) con justificación. Sé concreto y usa los datos disponibles.`
    analyzeAbort.current = streamChat(prompt, `market-${symbol}`, activeId, (type, data) => {
      if (type === 'message') {
        setAnalyzeText(prev => prev + ((data.content as string) ?? ''))
        setAnalyzing(false)
      } else if (type === 'error') {
        setAnalyzeText('Error al analizar: ' + (data.message as string))
        setAnalyzing(false)
      } else if (type === 'done') {
        setAnalyzing(false)
      }
    })
  }

  const pct = ticker?.change_pct
  const chartData = histData?.data ?? []

  return (
    <div className="flex-1 overflow-y-auto p-6" style={{ background: 'var(--bg)' }}>
      <h1 className="text-xl font-bold mb-4" style={{ color: 'var(--text)' }}>Mercado</h1>

      {/* Search bar */}
      <div className="flex gap-2 mb-3">
        <TickerSearch value={symbol} onSelect={handleSymbolSelect} />
        <button
          onClick={() => handleSymbolSelect(symbol)}
          className="px-4 py-2 rounded-xl text-sm font-medium hover:opacity-80 transition-opacity"
          style={{ background: 'var(--accent)', color: 'white' }}
        >
          Buscar
        </button>
      </div>

      {/* Quick-access tabs */}
      <QuickAccess activeSymbol={symbol} onSelect={handleSymbolSelect} />

      {loadTicker && (
        <div className="flex items-center gap-2 py-4" style={{ color: 'var(--muted)' }}>
          <Loader2 size={16} className="animate-spin" /> Cargando {symbol}...
        </div>
      )}

      {errTicker && (
        <div className="py-4 text-sm" style={{ color: 'var(--down)' }}>
          No se encontraron datos para "{symbol}".
        </div>
      )}

      {ticker && (
        <>
          {/* Ticker header */}
          <div
            className="flex items-center gap-4 mb-5 rounded-2xl border p-5"
            style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
          >
            <TickerLogo ticker={ticker.symbol} logoUrl={ticker.logo_url} size={48} />
            <div className="flex-1 min-w-0">
              <p className="font-bold text-lg mono" style={{ color: 'var(--text)' }}>{ticker.symbol}</p>
              <p className="text-sm truncate" style={{ color: 'var(--muted)' }}>{ticker.name}</p>
              {ticker.sector && (
                <p className="text-xs" style={{ color: 'var(--dim)' }}>{ticker.sector} · {ticker.industry}</p>
              )}
            </div>
            <div className="text-right">
              <p className="text-2xl font-bold mono" style={{ color: 'var(--text)' }}>
                {fmt(ticker.price, 2, '$')}
              </p>
              <DeltaBadge value={pct} big />
              {ticker.after_hours_price && (
                <p className="text-xs mt-1" style={{ color: 'var(--muted)' }}>
                  AH: {fmt(ticker.after_hours_price, 2, '$')}
                  <span className={pctColor(ticker.after_hours_change_pct)}>
                    {ticker.after_hours_change_pct != null ? ` (${fmtPct(ticker.after_hours_change_pct)})` : ''}
                  </span>
                </p>
              )}
            </div>
            <button
              onClick={handleToggleWatch}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-sm font-medium transition-all hover:opacity-90"
              style={{
                background: isWatched ? 'rgba(16,185,129,0.12)' : 'var(--surface-2)',
                color: isWatched ? 'var(--up)' : 'var(--muted)',
                border: `1px solid ${isWatched ? 'rgba(16,185,129,0.3)' : 'var(--border)'}`,
              }}
            >
              {isWatched ? <><BookmarkCheck size={13} /> En seguimiento</> : <><Bookmark size={13} /> Seguir</>}
            </button>
            <button
              onClick={handleAnalyze}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-medium transition-all hover:opacity-90 ml-2"
              style={{
                background: analyzing ? 'rgba(59,130,246,0.2)' : 'rgba(59,130,246,0.12)',
                color: 'var(--accent)',
                border: '1px solid rgba(59,130,246,0.3)',
              }}
            >
              {analyzing
                ? <><Loader2 size={13} className="animate-spin" /> Analizando...</>
                : <><Sparkles size={13} /> Analizar con IA</>}
            </button>
          </div>

          <AnalysisPanel text={analyzeText} loading={analyzing} />

          {/* Key stats */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
            <StatTile label="Mkt Cap" value={ticker.market_cap_str ?? '—'} />
            <StatTile label="P/E ratio" value={fmt(ticker.pe_ratio, 2)} />
            <StatTile label="Volumen" value={fmtVolume(ticker.volume)} />
            <StatTile label="Máx 52s" value={fmt(ticker['52w_high'], 2, '$')} />
          </div>

          {/* Price chart */}
          <div
            className="rounded-2xl border p-5 mb-5"
            style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold" style={{ color: 'var(--text)' }}>
                Evolución del precio · {symbol}
              </h2>
              <div className="flex gap-1">
                {PERIODS.map(p => (
                  <button
                    key={p}
                    onClick={() => setPeriod(p)}
                    className="px-2.5 py-1 rounded-lg text-xs mono font-semibold transition-all hover:opacity-80"
                    style={{
                      background: p === period ? 'var(--accent)' : 'var(--surface-2)',
                      color: p === period ? 'white' : 'var(--muted)',
                    }}
                  >
                    {PERIOD_LABELS[p]}
                  </button>
                ))}
              </div>
            </div>
            {loadHist ? (
              <div className="h-48 flex items-center justify-center" style={{ color: 'var(--muted)' }}>
                <Loader2 size={20} className="animate-spin" />
              </div>
            ) : errHist ? (
              <p className="text-center text-sm py-8" style={{ color: 'var(--down)' }}>
                No se pudo cargar el historial para {symbol} en {period}.
              </p>
            ) : (
              <PriceChart data={chartData} symbol={symbol} />
            )}
          </div>

          {/* Fundamentals */}
          {fundamentals && (
            <div
              className="rounded-2xl border p-5 mb-5"
              style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
            >
              <h2 className="text-sm font-semibold mb-4" style={{ color: 'var(--text)' }}>Fundamentales</h2>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 text-sm">
                {([
                  ['P/E trailing', fmt(fundamentals.pe_ratio, 2)],
                  ['P/E forward', fmt(fundamentals.forward_pe, 2)],
                  ['PEG', fmt(fundamentals.peg_ratio, 2)],
                  ['P/B', fmt(fundamentals.price_to_book, 2)],
                  ['EPS', fmt(fundamentals.eps, 2, '$')],
                  ['ROE', fundamentals.return_on_equity != null ? fmtPct(fundamentals.return_on_equity * 100) : '—'],
                  ['Margen bruto', fundamentals.gross_margins != null ? fmtPct(fundamentals.gross_margins * 100) : '—'],
                  ['Margen neto', fundamentals.profit_margins != null ? fmtPct(fundamentals.profit_margins * 100) : '—'],
                  ['D/E', fmt(fundamentals.debt_to_equity, 2)],
                  ['Beta', fmt(fundamentals.beta, 2)],
                  ['Div yield', fundamentals.dividend_yield != null ? fmtPct(fundamentals.dividend_yield * 100) : '—'],
                  ['Objetivo analistas', fmt(fundamentals.analyst_target, 2, '$')],
                ] as [string, string][]).map(([label, val]) => (
                  <div key={label} className="group relative">
                    <p className="text-[10px] uppercase tracking-wider mb-0.5" style={{ color: 'var(--muted)' }}>{label}</p>
                    <div className="flex items-center gap-1.5">
                      <p className="font-mono font-semibold text-sm" style={{ color: 'var(--text)' }}>{val}</p>
                      {val !== '—' && (
                        <button
                          onClick={() => handleExplain(label, val)}
                          title="Explícame esto"
                          className="opacity-0 group-hover:opacity-100 transition-opacity text-[10px] px-1.5 py-0.5 rounded"
                          style={{ background: 'rgba(59,130,246,0.12)', color: 'var(--accent)' }}
                        >
                          ?
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Compare */}
          <div
            className="rounded-2xl border p-5"
            style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
          >
            <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--text)' }}>Comparar con otros tickers</h2>
            <div className="mb-4">
              <CompareInput base={symbol} onChange={setCompareChips} />
              <p className="text-xs mt-1.5" style={{ color: 'var(--dim)' }}>
                Escribe y selecciona de la lista, o pulsa Enter. Backspace elimina el último.
              </p>
            </div>

            {compareChips.length > 0 && compareHistData && compareHistData.length > 1 && (
              <div className="mb-5">
                <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>
                  Evolución comparada · {period}
                </h3>
                <CompareChart series={compareHistData} period={period} />
              </div>
            )}

            {compareChips.length > 0 && compareData && compareData.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr>
                      {['Ticker', 'Precio', 'Cambio', 'P/E', 'Mkt Cap', 'Beta'].map(h => (
                        <th
                          key={h}
                          className="text-left py-2 pr-4 text-xs uppercase tracking-wider"
                          style={{ color: 'var(--muted)' }}
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {compareData.map(t => (
                      <tr
                        key={t.symbol}
                        className="border-t transition-colors hover:bg-[var(--surface-2)]"
                        style={{ borderColor: 'var(--border)' }}
                      >
                        <td className="py-2 pr-4 font-mono font-semibold" style={{ color: t.symbol === symbol ? 'var(--accent)' : 'var(--text)' }}>
                          <button onClick={() => handleSymbolSelect(t.symbol)} className="hover:underline flex items-center gap-1.5">
                            <TickerLogo ticker={t.symbol} size={20} />
                            {t.symbol}
                          </button>
                        </td>
                        <td className="py-2 pr-4 mono" style={{ color: 'var(--text)' }}>{fmt(t.price, 2, '$')}</td>
                        <td className="py-2 pr-4"><DeltaBadge value={t.change_pct} /></td>
                        <td className="py-2 pr-4 mono" style={{ color: 'var(--muted)' }}>{fmt(t.pe_ratio, 2)}</td>
                        <td className="py-2 pr-4 mono" style={{ color: 'var(--muted)' }}>{t.market_cap_str ?? '—'}</td>
                        <td className="py-2 pr-4 mono" style={{ color: 'var(--muted)' }}>{fmt(t.beta, 2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {compareChips.length === 0 && (
              <p className="text-sm py-4 text-center" style={{ color: 'var(--dim)' }}>
                Añade tickers para comparar precios y métricas
              </p>
            )}
          </div>
        </>
      )}
    </div>
  )
}
