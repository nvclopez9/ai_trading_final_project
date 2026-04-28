import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
interface DataPoint { date: string; close: number; volume?: number }

interface Props {
  data: DataPoint[]
  symbol: string
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div
      className="rounded-lg border px-3 py-2 text-xs"
      style={{ background: 'var(--surface-2)', borderColor: 'var(--border)' }}
    >
      <p style={{ color: 'var(--muted)' }}>{label}</p>
      <p className="font-mono font-semibold" style={{ color: 'var(--text)' }}>
        {d.close?.toFixed(2)}
      </p>
    </div>
  )
}

export function PriceChart({ data, symbol }: Props) {
  if (!data.length) return (
    <div className="flex items-center justify-center h-40" style={{ color: 'var(--muted)' }}>
      Sin datos históricos
    </div>
  )

  const first = data[0]?.close ?? 0
  const last = data[data.length - 1]?.close ?? 0
  const isUp = last >= first
  const color = isUp ? 'var(--up)' : 'var(--down)'
  const gradId = `grad_${symbol}`

  return (
    <div style={{ width: '100%', height: 200 }}>
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={color} stopOpacity={0.25} />
            <stop offset="95%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 10, fill: 'var(--muted)' }}
          tickLine={false}
          axisLine={false}
          interval="preserveStartEnd"
          tickFormatter={v => {
            try { return new Date(v).toLocaleDateString('es-ES', { month: 'short', day: 'numeric' }) } catch { return v }
          }}
        />
        <YAxis
          tick={{ fontSize: 10, fill: 'var(--muted)' }}
          tickLine={false}
          axisLine={false}
          domain={['auto', 'auto']}
          width={52}
          tickFormatter={v => v.toFixed(0)}
        />
        <Tooltip content={<CustomTooltip />} />
        <Area
          type="monotone"
          dataKey="close"
          stroke={color}
          strokeWidth={1.5}
          fill={`url(#${gradId})`}
          dot={false}
          activeDot={{ r: 4, fill: color }}
        />
      </AreaChart>
    </ResponsiveContainer>
    </div>
  )
}
