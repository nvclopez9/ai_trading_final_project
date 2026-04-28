import { HelpCircle, MessageSquare, Briefcase, TrendingUp, Flame, Newspaper, Terminal, Zap } from 'lucide-react'

const SECTIONS = [
  {
    icon: MessageSquare,
    title: 'Chat IA',
    color: 'var(--accent)',
    items: [
      'Pregunta sobre tickers: "¿Cómo está AAPL hoy?"',
      'Operaciones: "Compra 10 acciones de MSFT"',
      'Briefing: "Dame un resumen del mercado"',
      'RAG: "¿Qué es el ratio P/E?" o "Explícame el análisis técnico"',
      'Slash commands: /precio AAPL, /cartera, /briefing',
    ],
  },
  {
    icon: Briefcase,
    title: 'Mi Cartera',
    color: '#10B981',
    items: [
      'Ve posiciones abiertas con P&L en tiempo real',
      'Gráfico de distribución (pie chart)',
      'Valor after-hours cuando el mercado USA está cerrado',
      'Historial de transacciones reciente',
      'Cambia la cartera activa desde el selector del sidebar',
    ],
  },
  {
    icon: TrendingUp,
    title: 'Mercado',
    color: '#F59E0B',
    items: [
      'Busca cualquier ticker: acciones, ETFs, crypto-ETPs',
      'Gráfico histórico con 6 periodos (1mo → 5y)',
      'Fundamentales: P/E, ROE, márgenes, deuda/capital',
      'Compara hasta 6 tickers en tabla lado a lado',
      'Precio after-hours disponible si el mercado está cerrado',
    ],
  },
  {
    icon: Flame,
    title: 'Top del Día',
    color: '#F97316',
    items: [
      'Gainers: acciones con mayor subida del día',
      'Losers: acciones con mayor bajada del día',
      'Más activos: mayor volumen de negociación',
      'Snapshot cacheado 5 min (pulsa Refrescar para actualizar)',
      'Haz clic en una tarjeta para ir al detalle en Mercado',
    ],
  },
  {
    icon: Newspaper,
    title: 'Noticias',
    color: '#8B5CF6',
    items: [
      'Portal: agregado de 8 mega-caps y ETFs de índice',
      'Por ticker: busca noticias de cualquier símbolo',
      '"Analizar con IA" envía la noticia al chat para análisis profundo',
      'Thumbnails de imagen cuando están disponibles',
      'Refresco automático cada 5 minutos',
    ],
  },
]

const SLASH_CMDS = [
  ['/precio TICKER', 'Precio y estado actual del ticker'],
  ['/historico TICKER', 'Resumen de los últimos 6 meses'],
  ['/comprar N TICKER', 'Compra simulada con confirmación'],
  ['/vender N TICKER', 'Venta simulada con confirmación'],
  ['/cartera', 'Vista detallada de posiciones y P&L'],
  ['/noticias TICKER', 'Últimas noticias del ticker'],
  ['/briefing', 'Resumen del mercado y tu cartera'],
  ['/limpiar', 'Limpia el historial de chat'],
  ['/ayuda', 'Lista de comandos disponibles'],
]

export function HelpPage() {
  return (
    <div className="flex-1 overflow-y-auto p-6" style={{ background: 'var(--bg)' }}>
      <div className="flex items-center gap-2 mb-6">
        <HelpCircle size={20} style={{ color: 'var(--accent)' }} />
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--text)' }}>Ayuda</h1>
          <p className="text-sm" style={{ color: 'var(--muted)' }}>Guía de uso del bot de inversiones</p>
        </div>
      </div>

      {/* Quick start */}
      <div
        className="rounded-2xl border p-5 mb-6"
        style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
      >
        <div className="flex items-center gap-2 mb-3">
          <Zap size={16} style={{ color: '#F59E0B' }} />
          <h2 className="font-semibold" style={{ color: 'var(--text)' }}>Inicio rápido</h2>
        </div>
        <ol className="space-y-1.5 text-sm" style={{ color: 'var(--muted)' }}>
          <li><span className="mono text-xs px-1.5 py-0.5 rounded mr-2" style={{ background: 'var(--surface-2)', color: 'var(--text)' }}>1</span>Ve al <strong style={{ color: 'var(--text)' }}>Chat</strong> y pregunta cualquier cosa sobre el mercado.</li>
          <li><span className="mono text-xs px-1.5 py-0.5 rounded mr-2" style={{ background: 'var(--surface-2)', color: 'var(--text)' }}>2</span>Pide al agente que compre o venda acciones simuladas.</li>
          <li><span className="mono text-xs px-1.5 py-0.5 rounded mr-2" style={{ background: 'var(--surface-2)', color: 'var(--text)' }}>3</span>Revisa tu <strong style={{ color: 'var(--text)' }}>Cartera</strong> para ver P&L y distribución.</li>
          <li><span className="mono text-xs px-1.5 py-0.5 rounded mr-2" style={{ background: 'var(--surface-2)', color: 'var(--text)' }}>4</span>Explora <strong style={{ color: 'var(--text)' }}>Mercado</strong> para análisis técnico y fundamentales.</li>
        </ol>
      </div>

      {/* Feature sections */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {SECTIONS.map(({ icon: Icon, title, color, items }) => (
          <div
            key={title}
            className="rounded-2xl border p-5"
            style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
          >
            <div className="flex items-center gap-2 mb-3">
              <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: `${color}20` }}>
                <Icon size={14} style={{ color }} />
              </div>
              <h3 className="font-semibold text-sm" style={{ color: 'var(--text)' }}>{title}</h3>
            </div>
            <ul className="space-y-1.5">
              {items.map((item, i) => (
                <li key={i} className="flex items-start gap-2 text-xs" style={{ color: 'var(--muted)' }}>
                  <span style={{ color }} className="mt-0.5 flex-shrink-0">•</span>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      {/* Slash commands */}
      <div className="rounded-2xl border p-5 mb-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
        <div className="flex items-center gap-2 mb-4">
          <Terminal size={16} style={{ color: 'var(--accent)' }} />
          <h2 className="font-semibold" style={{ color: 'var(--text)' }}>Slash commands</h2>
        </div>
        <div className="space-y-2">
          {SLASH_CMDS.map(([cmd, desc]) => (
            <div key={cmd} className="flex items-start gap-3 text-sm">
              <code
                className="flex-shrink-0 px-2 py-0.5 rounded text-xs mono font-semibold"
                style={{ background: 'var(--surface-2)', color: 'var(--accent)' }}
              >
                {cmd}
              </code>
              <span style={{ color: 'var(--muted)' }}>{desc}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Disclaimer */}
      <div
        className="rounded-2xl border p-4 text-xs leading-relaxed"
        style={{ background: 'rgba(239,68,68,0.05)', borderColor: 'rgba(239,68,68,0.2)', color: 'var(--muted)' }}
      >
        <strong style={{ color: 'var(--down)' }}>Aviso legal:</strong>{' '}
        Esta aplicación es un proyecto educativo. Toda la información proporcionada por el agente
        de IA es únicamente con fines didácticos y NO constituye asesoramiento financiero.
        Las operaciones son simuladas y no tienen ningún efecto real. No tomes decisiones de
        inversión basándote en esta herramienta.
      </div>
    </div>
  )
}
