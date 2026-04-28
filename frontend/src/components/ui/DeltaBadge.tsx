import { fmtPct } from '../../lib/utils'

interface Props {
  value: number | null | undefined
  big?: boolean
}

export function DeltaBadge({ value, big }: Props) {
  if (value == null) return <span style={{ color: 'var(--muted)' }}>—</span>
  const up = value >= 0
  const color = up ? 'var(--up)' : 'var(--down)'
  const bg = up ? 'rgba(16,185,129,0.12)' : 'rgba(239,68,68,0.12)'
  const size = big ? 'text-sm px-2 py-0.5' : 'text-xs px-1.5 py-0.5'
  return (
    <span
      className={`inline-flex items-center rounded-full font-mono font-semibold ${size}`}
      style={{ color, background: bg }}
    >
      {fmtPct(value)}
    </span>
  )
}
