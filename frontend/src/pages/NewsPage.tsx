import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { newsApi, type NewsItem } from '../lib/api'
import { Newspaper, Loader2, ExternalLink, Search, RefreshCw } from 'lucide-react'
import { fmtDate } from '../lib/utils'

function NewsCard({ item, onAnalyze }: { item: NewsItem; onAnalyze: (item: NewsItem) => void }) {
  const ticker = item._origin ?? ''
  return (
    <div
      className="rounded-2xl border overflow-hidden transition-all hover:border-[var(--accent)]"
      style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
    >
      {item.thumbnail && (
        <img
          src={item.thumbnail}
          alt=""
          onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
          className="w-full h-36 object-cover"
        />
      )}
      <div className="p-4">
        <div className="flex items-center gap-2 mb-2">
          {ticker && (
            <span
              className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded"
              style={{ background: 'rgba(59,130,246,0.12)', color: 'var(--accent)' }}
            >
              {ticker}
            </span>
          )}
          <span className="text-[10px]" style={{ color: 'var(--muted)' }}>
            {item.source} · {fmtDate(item.date)}
          </span>
        </div>
        <p className="text-sm font-medium leading-snug mb-3" style={{ color: 'var(--text)', display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
          {item.title}
        </p>
        <div className="flex gap-2">
          {item.link && (
            <a
              href={item.link}
              target="_blank"
              rel="noopener noreferrer"
              onClick={e => e.stopPropagation()}
              className="flex items-center gap-1 text-xs hover:opacity-80 transition-opacity"
              style={{ color: 'var(--muted)' }}
            >
              <ExternalLink size={11} /> Leer
            </a>
          )}
          <button
            onClick={() => onAnalyze(item)}
            className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-full font-medium transition-all hover:opacity-80 ml-auto"
            style={{ background: 'rgba(59,130,246,0.12)', color: 'var(--accent)' }}
          >
            Analizar con IA →
          </button>
        </div>
      </div>
    </div>
  )
}

const POPULAR_TICKERS = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'META', 'TSLA', 'SPY', 'QQQ', 'AMD']

export function NewsPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [tab, setTab] = useState<'portal' | 'search'>('portal')
  const [searchTicker, setSearchTicker] = useState('AAPL')
  const [searchInput, setSearchInput] = useState('AAPL')
  const [searchTriggered, setSearchTriggered] = useState(false)

  const { data: portalNews = [], isLoading: loadPortal, refetch: refetchPortal } = useQuery({
    queryKey: ['news-portal'],
    queryFn: newsApi.portal,
    staleTime: 300_000,
    enabled: tab === 'portal',
  })

  const { data: tickerNews = [], isLoading: loadSearch } = useQuery({
    queryKey: ['news-ticker', searchTicker],
    queryFn: () => newsApi.ticker(searchTicker, 12),
    enabled: tab === 'search' && searchTriggered,
    staleTime: 300_000,
  })

  const handleAnalyze = (item: NewsItem) => {
    const ticker = item._origin ?? (tab === 'search' ? searchTicker : '')
    const parts: string[] = []
    if (ticker) {
      parts.push(`Analiza esta noticia sobre ${ticker}:`)
    } else {
      parts.push('Analiza esta noticia:')
    }
    parts.push(item.title)
    if (item.source) parts.push(`Fuente: ${item.source}`)
    if (item.link) parts.push(`URL: ${item.link}`)
    sessionStorage.setItem('chat_prefill', parts.join('\n'))
    navigate('/chat')
  }

  const handleSearch = () => {
    const sym = searchInput.trim().toUpperCase()
    if (!sym) return
    setSearchTicker(sym)
    setSearchTriggered(true)
  }

  const items = tab === 'portal' ? portalNews : tickerNews

  return (
    <div className="flex-1 overflow-y-auto p-6" style={{ background: 'var(--bg)' }}>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Newspaper size={20} style={{ color: 'var(--accent)' }} />
          <div>
            <h1 className="text-xl font-bold" style={{ color: 'var(--text)' }}>Noticias</h1>
            <p className="text-sm" style={{ color: 'var(--muted)' }}>Portal de titulares y buscador por ticker</p>
          </div>
        </div>
        {tab === 'portal' && (
          <button
            onClick={() => { qc.invalidateQueries({ queryKey: ['news-portal'] }); refetchPortal() }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs hover:opacity-80"
            style={{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--muted)' }}
          >
            <RefreshCw size={12} /> Refrescar
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 rounded-xl mb-5 w-fit" style={{ background: 'var(--surface)' }}>
        {[['portal', 'Portal'], ['search', 'Por ticker']].map(([id, label]) => (
          <button
            key={id}
            onClick={() => setTab(id as any)}
            className="px-4 py-2 rounded-lg text-sm font-medium transition-all"
            style={{
              background: tab === id ? 'var(--surface-2)' : 'transparent',
              color: tab === id ? 'var(--text)' : 'var(--muted)',
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'search' && (
        <div className="mb-5">
          <div className="flex gap-2 mb-3">
            <div className="relative flex-1 max-w-xs">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--muted)' }} />
              <input
                value={searchInput}
                onChange={e => setSearchInput(e.target.value.toUpperCase())}
                onKeyDown={e => { if (e.key === 'Enter') handleSearch() }}
                placeholder="Ticker (ej. AAPL)"
                className="w-full pl-9 pr-4 py-2 rounded-xl text-sm outline-none"
                style={{ background: 'var(--surface)', color: 'var(--text)', border: '1px solid var(--border)' }}
              />
            </div>
            <button onClick={handleSearch} className="px-4 py-2 rounded-xl text-sm font-medium hover:opacity-80" style={{ background: 'var(--accent)', color: 'white' }}>
              Buscar
            </button>
          </div>
          <div className="flex gap-1.5 flex-wrap">
            {POPULAR_TICKERS.map(t => (
              <button
                key={t}
                onClick={() => { setSearchInput(t); setSearchTicker(t); setSearchTriggered(true) }}
                className="px-2.5 py-1 rounded-full text-xs mono font-semibold hover:opacity-80"
                style={{
                  background: t === searchTicker && searchTriggered ? 'rgba(59,130,246,0.15)' : 'var(--surface)',
                  color: t === searchTicker && searchTriggered ? 'var(--accent)' : 'var(--muted)',
                  border: `1px solid ${t === searchTicker && searchTriggered ? 'var(--accent)' : 'var(--border)'}`,
                }}
              >
                {t}
              </button>
            ))}
          </div>
        </div>
      )}

      {(loadPortal || loadSearch) && (
        <div className="flex items-center gap-2 py-8" style={{ color: 'var(--muted)' }}>
          <Loader2 size={20} className="animate-spin" /> Cargando noticias...
        </div>
      )}

      {!loadPortal && !loadSearch && items.length === 0 && (
        <div className="text-center py-10" style={{ color: 'var(--muted)' }}>
          {tab === 'search' && !searchTriggered
            ? 'Escribe un ticker y pulsa Buscar para ver noticias.'
            : 'No hay noticias disponibles ahora mismo.'}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {items.slice(0, 24).map((item, i) => (
          <NewsCard key={i} item={item} onAnalyze={handleAnalyze} />
        ))}
      </div>

      <p className="text-[10px] mt-6" style={{ color: 'var(--muted)' }}>
        Noticias vía Yahoo Finance. Los análisis con IA usan el agente con tools de mercado.
      </p>
    </div>
  )
}
