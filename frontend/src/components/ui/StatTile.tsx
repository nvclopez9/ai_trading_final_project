import type { ReactNode } from 'react'

interface Props {
  label: string
  value: ReactNode
  sub?: ReactNode
  tone?: 'auto' | 'neutral' | 'up' | 'down'
  numericValue?: number | null
  hint?: string
}

export function StatTile({ label, value, sub, tone = 'neutral', numericValue, hint }: Props) {
  let valueColor = 'var(--text)'
  if (tone === 'auto' && numericValue != null) {
    valueColor = numericValue > 0 ? 'var(--up)' : numericValue < 0 ? 'var(--down)' : 'var(--muted)'
  } else if (tone === 'up') valueColor = 'var(--up)'
  else if (tone === 'down') valueColor = 'var(--down)'

  return (
    <div
      className="flex flex-col gap-1 p-4 rounded-xl border"
      style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
    >
      <p className="text-xs uppercase tracking-wider truncate" style={{ color: 'var(--muted)' }}>
        {label}
        {hint && <span className="ml-1 normal-case opacity-60">({hint})</span>}
      </p>
      <p
        className="text-xl font-bold mono truncate"
        style={{ color: valueColor }}
      >
        {value}
      </p>
      {sub && (
        <p className="text-xs truncate" style={{ color: 'var(--muted)' }}>{sub}</p>
      )}
    </div>
  )
}
