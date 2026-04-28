import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'

interface SeriesItem { symbol: string; data: { date: string; close: number }[] }

const COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899', '#06B6D4']

interface Props {
  series: SeriesItem[]
  period: string
}

const TooltipLine = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border px-3 py-2 text-xs" style={{ background: 'var(--surface-2)', borderColor: 'var(--border)' }}>
      <p className="mb-1" style={{ color: 'var(--muted)' }}>{label}</p>
      {payload.map((p: any) => (
        <p key={p.dataKey} style={{ color: p.stroke }}>
          <span className="font-mono font-semibold">{p.name}</span>
          {' '}
          {p.value != null ? `${p.value >= 0 ? '+' : ''}${p.value.toFixed(2)}%` : '—'}
        </p>
      ))}
    </div>
  )
}

export function CompareChart({ series }: Props) {
  if (!series.length) return null

  // Normalize: convert each series to % return from its first point
  const normalized = series.map(s => {
    const first = s.data[0]?.close ?? 1
    return {
      symbol: s.symbol,
      points: s.data.map(d => ({
        date: d.date,
        pct: first ? +((d.close / first - 1) * 100).toFixed(2) : 0,
      })),
    }
  })

  // Merge by date using the first series as the date spine
  const spine = normalized[0]?.points ?? []
  const merged = spine.map(point => {
    const row: Record<string, string | number> = { date: point.date }
    for (const s of normalized) {
      const match = s.points.find(p => p.date === point.date)
      if (match) row[s.symbol] = match.pct
    }
    return row
  })

  const dateFormatter = (v: string) => {
    try { return new Date(v).toLocaleDateString('es-ES', { month: 'short', day: 'numeric' }) } catch { return v }
  }

  return (
    <div style={{ width: '100%', height: 220 }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={merged} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 10, fill: 'var(--muted)' }}
            tickLine={false}
            axisLine={false}
            interval="preserveStartEnd"
            tickFormatter={dateFormatter}
          />
          <YAxis
            tick={{ fontSize: 10, fill: 'var(--muted)' }}
            tickLine={false}
            axisLine={false}
            width={48}
            tickFormatter={v => `${v >= 0 ? '+' : ''}${v.toFixed(0)}%`}
          />
          <Tooltip content={<TooltipLine />} />
          <Legend
            formatter={(v) => <span style={{ color: 'var(--muted)', fontSize: 11, fontFamily: 'monospace' }}>{v}</span>}
            iconSize={8}
            iconType="circle"
          />
          {normalized.map((s, i) => (
            <Line
              key={s.symbol}
              type="monotone"
              dataKey={s.symbol}
              stroke={COLORS[i % COLORS.length]}
              strokeWidth={1.5}
              dot={false}
              activeDot={{ r: 4 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
