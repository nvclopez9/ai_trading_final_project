import { useState, useRef, useEffect } from 'react'
import {
  Send, Trash2, Wrench, CheckCircle, AlertCircle, Loader2, Bot, User,
  TrendingUp, Briefcase, BookOpen, Target, Sparkles, ChevronRight,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { streamChat, clearChat } from '../lib/api'
import { usePortfolioCtx } from '../context/PortfolioContext'
import { randomId } from '../lib/utils'
import { useToast } from '../components/ui/Toast'

interface ToolEvent { tool: string; status: 'start' | 'done' | 'error'; input?: string; error?: string }

interface Message {
  id: string
  role: 'user' | 'assistant' | 'tool'
  content: string
  toolEvents?: ToolEvent[]
  loading?: boolean
}

interface PillCategory {
  label: string
  description: string
  icon: LucideIcon
  color: string
  pills: string[]
}

const PILL_CATEGORIES: PillCategory[] = [
  {
    label: 'Mercado y análisis',
    description: 'Consulta precios, tendencias y métricas en tiempo real',
    icon: TrendingUp,
    color: 'var(--accent)',
    pills: [
      '¿Cómo está AAPL hoy?',
      'Analiza NVDA en detalle',
      'Dame los 5 tickers más calientes',
      'Briefing del mercado',
      'Compara AAPL con MSFT',
      '¿Cuál es el mejor momento para comprar TSLA?',
    ],
  },
  {
    label: 'Mi cartera',
    description: 'Compra, vende y gestiona tus posiciones',
    icon: Briefcase,
    color: '#3B82F6',
    pills: [
      'Muéstrame mi cartera',
      'Compra 10 acciones de AAPL',
      'Vende 5 MSFT',
      '¿Cuánto cash tengo disponible?',
      'Muéstrame mis ganancias y pérdidas',
      'Sugiere cómo rebalancear mi cartera',
    ],
  },
  {
    label: 'Conceptos',
    description: 'Aprende términos y estrategias de inversión',
    icon: BookOpen,
    color: '#A855F7',
    pills: [
      '¿Qué es el P/E ratio?',
      '¿Qué significa diversificar?',
      'Explícame el análisis técnico',
      '¿Qué es un ETF?',
      'Diferencia entre value y growth investing',
      '¿Cómo funciona el mercado after-hours?',
    ],
  },
  {
    label: 'Plan de inversión',
    description: 'Recibe recomendaciones y evaluaciones del agente',
    icon: Target,
    color: '#F59E0B',
    pills: [
      'Propón un plan de inversión para este mes',
      '¿Por qué recomiendas ese plan?',
      'Evalúa si invertir en NVDA es buena idea',
      'Qué riesgos tiene mi cartera actual',
      'Sugiere acciones para un perfil conservador',
      'Optimiza mi cartera para largo plazo',
    ],
  },
]

function PromptCategoryCard({ cat, onPick }: { cat: PillCategory; onPick: (p: string) => void }) {
  const [expanded, setExpanded] = useState(false)
  const Icon = cat.icon
  const visiblePills = expanded ? cat.pills : cat.pills.slice(0, 4)
  const remaining = cat.pills.length - 4

  return (
    <div
      className="rounded-xl p-4 transition-all duration-200 card-hover"
      style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
      }}
    >
      <div className="flex items-start gap-3 mb-3">
        <div
          className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{ background: `color-mix(in oklab, ${cat.color} 14%, transparent)` }}
        >
          <Icon size={16} style={{ color: cat.color }} />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold leading-tight" style={{ color: 'var(--text)' }}>
            {cat.label}
          </h3>
          <p className="text-xs mt-0.5 leading-snug" style={{ color: 'var(--muted)' }}>
            {cat.description}
          </p>
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        {visiblePills.map(pill => (
          <button
            key={pill}
            onClick={() => onPick(pill)}
            className="group flex items-center justify-between gap-2 w-full px-3 py-2 rounded-lg text-xs text-left transition-all"
            style={{
              background: 'var(--surface-2)',
              color: 'var(--text)',
              border: '1px solid transparent',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.borderColor = cat.color
              e.currentTarget.style.background = `color-mix(in oklab, ${cat.color} 8%, var(--surface-2))`
            }}
            onMouseLeave={e => {
              e.currentTarget.style.borderColor = 'transparent'
              e.currentTarget.style.background = 'var(--surface-2)'
            }}
          >
            <span className="flex-1 truncate">{pill}</span>
            <ChevronRight
              size={12}
              className="opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
              style={{ color: cat.color }}
            />
          </button>
        ))}
      </div>

      {remaining > 0 && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="mt-2 text-[11px] font-medium hover:underline"
          style={{ color: cat.color }}
        >
          {expanded ? 'Ver menos' : `Ver ${remaining} más`}
        </button>
      )}
    </div>
  )
}

const SESSION_ID = randomId()

function ToolIndicator({ events }: { events: ToolEvent[] }) {
  return (
    <div className="flex flex-col gap-1 my-1">
      {events.map((ev, i) => {
        const Icon = ev.status === 'start' ? Loader2 : ev.status === 'done' ? CheckCircle : AlertCircle
        const color = ev.status === 'error' ? 'var(--down)' : ev.status === 'done' ? 'var(--up)' : 'var(--accent)'
        return (
          <div key={i} className="flex items-center gap-2 text-xs px-2 py-1 rounded-md" style={{ background: 'var(--surface-2)' }}>
            <Icon size={11} style={{ color }} className={ev.status === 'start' ? 'animate-spin' : ''} />
            <Wrench size={10} style={{ color: 'var(--muted)' }} />
            <span className="font-mono" style={{ color: 'var(--muted)' }}>{ev.tool}</span>
            {ev.input && <span className="truncate opacity-50" style={{ color: 'var(--muted)', maxWidth: 160 }}>{ev.input}</span>}
          </div>
        )
      })}
    </div>
  )
}

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === 'user'
  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'} mb-4`}>
      <div
        className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"
        style={{
          background: isUser ? 'var(--accent)' : 'var(--surface-2)',
          border: '1px solid var(--border)',
        }}
      >
        {isUser ? <User size={13} color="white" /> : <Bot size={13} style={{ color: 'var(--accent)' }} />}
      </div>
      <div className={`flex flex-col gap-1 max-w-[78%] ${isUser ? 'items-end' : 'items-start'}`}>
        {msg.toolEvents && msg.toolEvents.length > 0 && <ToolIndicator events={msg.toolEvents} />}
        <div
          className="rounded-2xl px-4 py-3 text-sm leading-relaxed"
          style={{
            background: isUser ? 'var(--accent)' : 'var(--surface)',
            color: isUser ? 'white' : 'var(--text)',
            borderBottomRightRadius: isUser ? 4 : undefined,
            borderBottomLeftRadius: !isUser ? 4 : undefined,
            border: isUser ? 'none' : '1px solid var(--border)',
            whiteSpace: 'pre-wrap',
          }}
        >
          {msg.loading ? (
            <span className="flex items-center gap-2" style={{ color: 'var(--muted)' }}>
              <Loader2 size={14} className="animate-spin" /> Pensando...
            </span>
          ) : (
            msg.content
          )}
        </div>
      </div>
    </div>
  )
}

export function ChatPage() {
  const { activeId } = usePortfolioCtx()
  const { toast } = useToast()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = (text: string) => {
    if (!text.trim() || loading) return
    const userMsg: Message = { id: randomId(), role: 'user', content: text.trim() }
    const botMsg: Message = { id: randomId(), role: 'assistant', content: '', loading: true, toolEvents: [] }

    setMessages(prev => [...prev, userMsg, botMsg])
    setInput('')
    setLoading(true)

    abortRef.current = streamChat(text.trim(), SESSION_ID, activeId, (type, data) => {
      if (type === 'token') {
        // Token streaming: append each fragment and hide spinner on first token
        setMessages(prev => prev.map(m =>
          m.id === botMsg.id
            ? { ...m, content: (m.content ?? '') + String((data as any).content ?? ''), loading: false }
            : m
        ))
      } else if (type === 'tool_call') {
        setMessages(prev => prev.map(m =>
          m.id === botMsg.id
            ? { ...m, toolEvents: [...(m.toolEvents ?? []), data as unknown as ToolEvent] }
            : m
        ))
      } else if (type === 'message') {
        // Full message fallback (legacy path)
        setMessages(prev => prev.map(m =>
          m.id === botMsg.id
            ? { ...m, content: String((data as any).content ?? ''), loading: false }
            : m
        ))
      } else if (type === 'error') {
        setMessages(prev => prev.map(m =>
          m.id === botMsg.id
            ? { ...m, content: `Error: ${(data as any).message}`, loading: false }
            : m
        ))
      } else if (type === 'done') {
        // Post-process: strip truncated preamble fragments that appear before the
        // first ## heading. Pattern: leading text (<200 chars) that does not end
        // with punctuation or a newline, immediately followed by a ## heading.
        setMessages(prev => prev.map(m => {
          if (m.id !== botMsg.id) return m
          const cleaned = m.content.replace(
            /^([^\n]{1,199}?)(?=##)/,
            (match) => /[.,;:!?\n]$/.test(match.trimEnd()) ? match : ''
          )
          return cleaned !== m.content ? { ...m, content: cleaned } : m
        }))
        setLoading(false)
      }
    })
  }

  const handleClear = async () => {
    if (messages.length === 0) return
    abortRef.current?.abort()
    setMessages([])
    setLoading(false)
    await clearChat(SESSION_ID)
    toast('Conversación borrada', 'success')
  }

  return (
    <div className="flex flex-col flex-1 min-h-0" style={{ background: 'var(--bg)' }}>
      {/* Header */}
      <div
        className="flex items-center justify-between px-6 py-4 border-b flex-shrink-0"
        style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}
      >
        <div>
          <h1 className="font-semibold text-base" style={{ color: 'var(--text)' }}>Chat IA</h1>
          <p className="text-xs" style={{ color: 'var(--muted)' }}>Agente de inversiones · Cartera #{activeId}</p>
        </div>
        <button
          onClick={handleClear}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-opacity hover:opacity-80"
          style={{ background: 'var(--surface-2)', color: 'var(--muted)', border: '1px solid var(--border)' }}
        >
          <Trash2 size={12} /> Limpiar
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        {messages.length === 0 && (
          <div className="max-w-4xl mx-auto">
            {/* Hero */}
            <div className="flex flex-col items-center text-center mb-8 mt-4">
              <div
                className="w-16 h-16 rounded-2xl flex items-center justify-center mb-4 relative"
                style={{
                  background: 'linear-gradient(135deg, var(--accent) 0%, var(--accent-2) 100%)',
                  boxShadow: '0 8px 32px var(--accent-glow)',
                }}
              >
                <Bot size={30} color="white" />
              </div>
              <h2 className="font-bold text-2xl mb-2" style={{ color: 'var(--text)' }}>
                ¿En qué puedo ayudarte?
              </h2>
              <p className="text-sm max-w-md" style={{ color: 'var(--muted)' }}>
                Soy tu agente de inversiones. Puedo analizar tickers, gestionar tu cartera,
                explicar conceptos y proponer estrategias.
              </p>
            </div>

            {/* Suggestions header */}
            <div className="flex items-center gap-2 mb-3 px-1">
              <Sparkles size={13} style={{ color: 'var(--accent)' }} />
              <span
                className="text-[11px] font-semibold uppercase tracking-wider"
                style={{ color: 'var(--muted)' }}
              >
                Sugerencias
              </span>
              <div className="flex-1 h-px" style={{ background: 'var(--border)' }} />
            </div>

            {/* Category cards: 2x2 grid on md+ */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {PILL_CATEGORIES.map(cat => (
                <PromptCategoryCard key={cat.label} cat={cat} onPick={send} />
              ))}
            </div>

            {/* Tip */}
            <div
              className="mt-6 px-4 py-3 rounded-xl flex items-start gap-2.5"
              style={{ background: 'var(--surface)', border: '1px dashed var(--border-2)' }}
            >
              <span style={{ color: 'var(--muted)' }}>💡</span>
              <p className="text-xs leading-relaxed" style={{ color: 'var(--muted)' }}>
                <span style={{ color: 'var(--text)', fontWeight: 500 }}>Tip:</span>{' '}
                Puedes encadenar acciones — pídeme "analiza NVDA y si los fundamentales son buenos, compra 3 acciones". Confirmaré antes de ejecutar operaciones.
              </p>
            </div>
          </div>
        )}
        {messages.map(msg => <MessageBubble key={msg.id} msg={msg} />)}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div
        className="px-6 py-4 border-t flex-shrink-0"
        style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}
      >
        <form
          onSubmit={e => { e.preventDefault(); send(input) }}
          className="flex gap-3 items-end"
        >
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input) }
            }}
            placeholder="Escribe tu pregunta… (Enter para enviar, Shift+Enter para nueva línea)"
            rows={1}
            disabled={loading}
            className="flex-1 resize-none rounded-xl px-4 py-3 text-sm outline-none transition-all"
            style={{
              background: 'var(--surface-2)',
              color: 'var(--text)',
              border: '1px solid var(--border)',
              maxHeight: 120,
              lineHeight: '1.5',
            }}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 transition-all hover:opacity-80 disabled:opacity-30"
            style={{ background: 'var(--accent)' }}
          >
            {loading ? <Loader2 size={16} color="white" className="animate-spin" /> : <Send size={16} color="white" />}
          </button>
        </form>
        <p className="text-[10px] text-center mt-2" style={{ color: 'var(--muted)' }}>
          Solo educativo. No es asesoramiento financiero.
        </p>
      </div>
    </div>
  )
}
