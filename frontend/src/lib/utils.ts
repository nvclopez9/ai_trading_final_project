export function cn(...classes: (string | undefined | null | false)[]) {
  return classes.filter(Boolean).join(' ')
}

export function fmt(n: number | null | undefined, decimals = 2, prefix = ''): string {
  if (n == null || isNaN(n)) return '—'
  return `${prefix}${n.toLocaleString('es-ES', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}`
}

export function fmtCurrency(n: number | null | undefined, currency = 'USD'): string {
  if (n == null || isNaN(n)) return '—'
  const abs = Math.abs(n)
  const sign = n < 0 ? '-' : ''
  if (abs >= 1e12) return `${sign}${(abs / 1e12).toFixed(2)}T`
  if (abs >= 1e9) return `${sign}${(abs / 1e9).toFixed(2)}B`
  if (abs >= 1e6) return `${sign}${(abs / 1e6).toFixed(2)}M`
  return `${sign}${abs.toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${currency}`
}

export function fmtPct(n: number | null | undefined): string {
  if (n == null || isNaN(n)) return '—'
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`
}

export function pctColor(n: number | null | undefined): string {
  if (n == null) return 'text-[var(--muted)]'
  return n > 0 ? 'text-[var(--up)]' : n < 0 ? 'text-[var(--down)]' : 'text-[var(--muted)]'
}

export function fmtDate(s: string | null | undefined): string {
  if (!s) return '—'
  try {
    return new Date(s).toLocaleDateString('es-ES', { day: '2-digit', month: 'short', year: 'numeric' })
  } catch {
    return s
  }
}

export function fmtVolume(v: number | null | undefined): string {
  if (v == null) return '—'
  if (v >= 1e9) return `${(v / 1e9).toFixed(1)}B`
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`
  if (v >= 1e3) return `${(v / 1e3).toFixed(0)}K`
  return String(v)
}

export function randomId(): string {
  return Math.random().toString(36).slice(2, 10)
}
