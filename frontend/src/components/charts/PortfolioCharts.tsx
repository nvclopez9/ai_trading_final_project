import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, ReferenceLine,
} from 'recharts'
import type { Position } from '../../lib/api'

const COLORS = [
  '#3B82F6','#10B981','#F59E0B','#EF4444','#8B5CF6',
  '#06B6D4','#EC4899','#84CC16','#F97316','#6366F1',
]

const TooltipPie = ({ active, payload }: any) => {
  if (!active || !payload?.length) return null
  const d = payload[0]
  return (
    <div className="rounded-lg border px-3 py-2 text-xs" style={{ background: 'var(--surface-2)', borderColor: 'var(--border)' }}>
      <p className="font-semibold" style={{ color: 'var(--text)' }}>{d.name}</p>
      <p style={{ color: 'var(--muted)' }}>{d.value?.toFixed(2)} USD</p>
      <p style={{ color: 'var(--muted)' }}>{d.payload?.pct?.toFixed(1)}%</p>
    </div>
  )
}

const TooltipBar = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null
  const val: number = payload[0].value
  return (
    <div className="rounded-lg border px-3 py-2 text-xs" style={{ background: 'var(--surface-2)', borderColor: 'var(--border)' }}>
      <p className="font-semibold" style={{ color: 'var(--text)' }}>{label}</p>
      <p style={{ color: val >= 0 ? 'var(--up)' : 'var(--down)' }}>
        {val >= 0 ? '+' : ''}{val.toFixed(2)} USD
      </p>
    </div>
  )
}

export function PnLBarChart({ positions }: { positions: Position[] }) {
  const data = positions
    .filter(p => p.pnl != null)
    .map(p => ({ ticker: p.ticker, pnl: +(p.pnl!.toFixed(2)) }))
    .sort((a, b) => b.pnl - a.pnl)

  if (!data.length) return <p style={{ color: 'var(--muted)' }} className="text-center text-sm py-8">Sin datos P&L</p>

  return (
    <div style={{ width: '100%', height: Math.max(160, data.length * 36) }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
          <XAxis
            type="number"
            tick={{ fontSize: 10, fill: 'var(--muted)' }}
            tickLine={false}
            axisLine={false}
            tickFormatter={v => `$${v >= 0 ? '+' : ''}${v.toFixed(0)}`}
          />
          <YAxis
            type="category"
            dataKey="ticker"
            tick={{ fontSize: 11, fill: 'var(--text)', fontFamily: 'monospace' }}
            tickLine={false}
            axisLine={false}
            width={44}
          />
          <Tooltip content={<TooltipBar />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
          <ReferenceLine x={0} stroke="var(--border)" />
          <Bar dataKey="pnl" radius={[0, 4, 4, 0]}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.pnl >= 0 ? 'var(--up)' : 'var(--down)'} fillOpacity={0.85} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export function AllocationPie({ positions }: { positions: Position[] }) {
  const data = positions
    .filter(p => (p.market_value ?? 0) > 0)
    .map(p => ({ name: p.ticker, value: p.market_value!, pct: 0 }))
  const total = data.reduce((a, b) => a + b.value, 0)
  data.forEach(d => { d.pct = total ? (d.value / total) * 100 : 0 })

  if (!data.length) return <p style={{ color: 'var(--muted)' }} className="text-center text-sm py-8">Sin posiciones</p>

  return (
    <div style={{ width: '100%', height: 240 }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" innerRadius={55} outerRadius={90} paddingAngle={2}>
            {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
          </Pie>
          <Tooltip content={<TooltipPie />} />
          <Legend
            formatter={(v) => <span style={{ color: 'var(--muted)', fontSize: 11 }}>{v}</span>}
            iconSize={8}
            iconType="circle"
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}
