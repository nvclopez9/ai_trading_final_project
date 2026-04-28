const BASE = '/api'

async function _fetch<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...opts?.headers },
    ...opts,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
  return res.json()
}

// --- Portfolio ---
export const portfolioApi = {
  list: () => _fetch<Portfolio[]>('/portfolios'),
  get: (id: number) => _fetch<Portfolio>(`/portfolios/${id}`),
  create: (body: CreatePortfolioBody) => _fetch<Portfolio>('/portfolios', { method: 'POST', body: JSON.stringify(body) }),
  delete: (id: number) => _fetch<{ok:boolean}>(`/portfolios/${id}`, { method: 'DELETE' }),
  reset: (id: number) => _fetch<{ok:boolean}>(`/portfolios/${id}/reset`, { method: 'POST' }),
  value: (id: number) => _fetch<PortfolioValue>(`/portfolios/${id}/value`),
  positions: (id: number) => _fetch<Position[]>(`/portfolios/${id}/positions`),
  transactions: (id: number, limit = 50) => _fetch<Transaction[]>(`/portfolios/${id}/transactions?limit=${limit}`),
  cash: (id: number) => _fetch<{cash:number}>(`/portfolios/${id}/cash`),
  buy: (id: number, body: TradeBody) => _fetch<TradeResult>(`/portfolios/${id}/buy`, { method: 'POST', body: JSON.stringify(body) }),
  sell: (id: number, body: TradeBody) => _fetch<TradeResult>(`/portfolios/${id}/sell`, { method: 'POST', body: JSON.stringify(body) }),
}

// --- Market ---
export const marketApi = {
  ticker: (symbol: string) => _fetch<TickerStatus>(`/market/ticker/${symbol}`),
  history: (symbol: string, period = '6mo', interval = '1d') =>
    _fetch<TickerHistory>(`/market/ticker/${symbol}/history?period=${period}&interval=${interval}`),
  news: (symbol: string, limit = 10) => _fetch<{symbol:string, items:NewsItem[]}>(`/market/ticker/${symbol}/news?limit=${limit}`),
  logo: (symbol: string) => _fetch<{symbol:string, url:string|null}>(`/market/ticker/${symbol}/logo`),
  hot: () => _fetch<HotTickers>(`/market/hot`),
  compare: (tickers: string[]) => _fetch<TickerStatus[]>(`/market/compare?tickers=${tickers.join(',')}`),
  fundamentals: (symbol: string) => _fetch<Fundamentals>(`/market/fundamentals/${symbol}`),
}

// --- News ---
export const newsApi = {
  portal: () => _fetch<NewsItem[]>(`/news/portal`),
  ticker: (symbol: string, limit = 10) => _fetch<NewsItem[]>(`/news/ticker/${symbol}?limit=${limit}`),
}

// --- Preferences ---
export const prefsApi = {
  get: () => _fetch<Preferences>(`/preferences`),
  update: (body: Partial<Preferences>) => _fetch<Preferences>(`/preferences`, { method: 'PUT', body: JSON.stringify(body) }),
}

// --- Chat (SSE) ---
export function streamChat(
  message: string,
  sessionId: string,
  portfolioId: number,
  onEvent: (type: string, data: Record<string, unknown>) => void,
): AbortController {
  const ctrl = new AbortController()

  fetch(`${BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId, portfolio_id: portfolioId }),
    signal: ctrl.signal,
  }).then(async (res) => {
    const reader = res.body?.getReader()
    if (!reader) return
    const decoder = new TextDecoder()
    let buf = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const parts = buf.split('\n\n')
      buf = parts.pop() ?? ''
      for (const part of parts) {
        const lines = part.trim().split('\n')
        let eventType = 'message'
        let dataStr = ''
        for (const line of lines) {
          if (line.startsWith('event: ')) eventType = line.slice(7).trim()
          else if (line.startsWith('data: ')) dataStr = line.slice(6)
        }
        if (dataStr) {
          try { onEvent(eventType, JSON.parse(dataStr)) } catch {}
        }
      }
    }
  }).catch((e) => {
    if (e.name !== 'AbortError') onEvent('error', { message: String(e) })
  })

  return ctrl
}

export async function clearChat(sessionId: string) {
  return _fetch('/chat/clear', { method: 'POST', body: JSON.stringify({ session_id: sessionId }) })
}

// --- Types ---
export interface Portfolio {
  id: number; name: string; initial_cash: number; risk: string;
  markets: string; currency: string; created_at: string; notes: string | null;
}
export interface CreatePortfolioBody {
  name: string; initial_cash: number; risk: string; markets: string; currency?: string; notes?: string;
}
export interface PortfolioValue {
  total_value: number; total_cost: number; total_pnl: number; total_pnl_pct: number;
  stale_tickers: string[]; total_value_after_hours: number | null;
  after_hours_delta: number | null; after_hours_delta_pct: number | null;
}
export interface Position {
  ticker: string; qty: number; avg_price: number; current_price: number | null;
  cost_basis: number; market_value: number | null; pnl: number | null; pnl_pct: number | null;
  after_hours_price: number | null; after_hours_change_pct: number | null; after_hours_value: number | null;
}
export interface Transaction {
  id: number; ticker: string; side: 'BUY' | 'SELL'; qty: number; price: number; ts: string;
}
export interface TradeBody { ticker: string; qty: number; price?: number; }
export interface TradeResult { ticker: string; qty: number; price: number; new_qty: number; new_avg_price: number; portfolio_id: number; }
export interface TickerStatus {
  symbol: string; name: string; price: number | null; prev_close: number | null;
  change_pct: number | null; pe_ratio: number | null; market_cap: number | null;
  market_cap_str: string | null; sector: string | null; industry: string | null;
  '52w_high': number | null; '52w_low': number | null; volume: number | null;
  avg_volume: number | null; dividend_yield: number | null; beta: number | null;
  currency: string; after_hours_price: number | null; after_hours_change_pct: number | null;
  logo_url: string | null;
}
export interface TickerHistory {
  symbol: string; period: string; interval: string;
  data: { date: string; open: number; high: number; low: number; close: number; volume: number }[];
}
export interface NewsItem {
  title: string; source: string; date: string; link: string; thumbnail: string | null; _origin?: string;
}
export interface HotTickers { gainers: QuoteRow[]; losers: QuoteRow[]; actives: QuoteRow[]; }
export interface QuoteRow { ticker: string; price: number; change_pct: number; volume: number; name?: string; }
export interface Fundamentals {
  symbol: string; name: string; sector: string | null; industry: string | null;
  pe_ratio: number | null; forward_pe: number | null; peg_ratio: number | null;
  price_to_book: number | null; eps: number | null; revenue: number | null;
  gross_margins: number | null; operating_margins: number | null; profit_margins: number | null;
  return_on_equity: number | null; return_on_assets: number | null; debt_to_equity: number | null;
  current_ratio: number | null; beta: number | null; '52w_high': number | null; '52w_low': number | null;
  dividend_yield: number | null; payout_ratio: number | null; market_cap: number | null;
  enterprise_value: number | null; float_shares: number | null; short_ratio: number | null;
  analyst_target: number | null; recommendation: string | null;
}
export interface Preferences {
  risk_profile: string; time_horizon: string; favorite_sectors: string[];
  excluded_tickers: string[]; onboarded: boolean;
}
