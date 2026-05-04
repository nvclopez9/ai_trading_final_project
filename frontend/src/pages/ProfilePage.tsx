import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Save } from 'lucide-react'
import { prefsApi } from '../lib/api'
import type { Preferences } from '../lib/api'
import { useToast } from '../components/ui/Toast'

const SECTORS = [
  'Tecnología', 'Salud', 'Energía', 'Finanzas', 'Consumo',
  'Industria', 'Inmobiliario', 'Materiales', 'Comunicaciones', 'Utilities',
]

const RISK_OPTIONS = [
  { value: 'conservador', icon: '🛡️', label: 'Conservador', desc: 'Prioriza la seguridad sobre el rendimiento' },
  { value: 'moderado',    icon: '⚖️', label: 'Moderado',    desc: 'Equilibrio entre crecimiento y seguridad' },
  { value: 'agresivo',   icon: '🚀', label: 'Agresivo',    desc: 'Máximo crecimiento, mayor tolerancia al riesgo' },
]

const HORIZON_OPTIONS = [
  { value: 'corto', label: 'Corto plazo', desc: 'Menos de 2 años' },
  { value: 'medio', label: 'Medio plazo', desc: '2 a 5 años' },
  { value: 'largo', label: 'Largo plazo', desc: 'Más de 5 años' },
]

export function ProfilePage() {
  const qc = useQueryClient()
  const { toast } = useToast()

  const { data: prefs } = useQuery({
    queryKey: ['preferences'],
    queryFn: prefsApi.get,
  })

  const [risk, setRisk] = useState<string>('moderado')
  const [horizon, setHorizon] = useState<string>('medio')
  const [sectors, setSectors] = useState<string[]>([])
  const [excluded, setExcluded] = useState<string[]>([])
  const [tickerInput, setTickerInput] = useState('')
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (!prefs) return
    setRisk(prefs.risk_profile ?? 'moderado')
    setHorizon(prefs.time_horizon ?? 'medio')
    setSectors(prefs.favorite_sectors ?? [])
    setExcluded(prefs.excluded_tickers ?? [])
  }, [prefs])

  const mutation = useMutation({
    mutationFn: (body: Partial<Preferences>) => prefsApi.update(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['preferences'] })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
      toast('Preferencias guardadas correctamente', 'success')
    },
    onError: (e: unknown) => {
      toast(e instanceof Error ? e.message : 'Error guardando preferencias', 'error')
    },
  })

  const toggleSector = (s: string) => {
    setSectors(prev => prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s])
  }

  const addTicker = () => {
    const t = tickerInput.trim().toUpperCase()
    if (!t || excluded.includes(t)) return
    setExcluded(prev => [...prev, t])
    setTickerInput('')
  }

  const removeTicker = (t: string) => {
    setExcluded(prev => prev.filter(x => x !== t))
  }

  const handleSave = () => {
    mutation.mutate({
      risk_profile: risk,
      time_horizon: horizon,
      favorite_sectors: sectors,
      excluded_tickers: excluded,
    })
  }

  const cardBase: React.CSSProperties = {
    background: 'var(--surface)',
    border: '2px solid var(--border)',
    borderRadius: 12,
    padding: '12px 16px',
    cursor: 'pointer',
    transition: 'border-color 0.15s, background 0.15s',
    textAlign: 'left',
    width: '100%',
  }

  const cardActive: React.CSSProperties = {
    border: '2px solid var(--accent)',
    background: 'var(--accent-dim)',
  }

  return (
    <div
      className="flex-1 overflow-y-auto px-6 py-8"
      style={{ background: 'var(--bg)', color: 'var(--text)' }}
    >
      <div className="max-w-2xl mx-auto flex flex-col gap-8">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-semibold" style={{ color: 'var(--text)' }}>Perfil de Inversor</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--muted)' }}>Configura tus preferencias de inversión</p>
        </div>

        {/* Risk profile */}
        <section>
          <SectionLabel>Perfil de riesgo</SectionLabel>
          <div className="grid grid-cols-3 gap-3 mt-3">
            {RISK_OPTIONS.map(opt => (
              <button
                key={opt.value}
                onClick={() => setRisk(opt.value)}
                style={{
                  ...cardBase,
                  ...(risk === opt.value ? cardActive : {}),
                }}
              >
                <span className="text-xl">{opt.icon}</span>
                <p
                  className="font-medium text-sm mt-1.5"
                  style={{ color: risk === opt.value ? 'var(--accent)' : 'var(--text)' }}
                >
                  {opt.label}
                </p>
                <p className="text-xs mt-0.5" style={{ color: 'var(--muted)' }}>{opt.desc}</p>
              </button>
            ))}
          </div>
        </section>

        {/* Time horizon */}
        <section>
          <SectionLabel>Horizonte temporal</SectionLabel>
          <div className="grid grid-cols-3 gap-3 mt-3">
            {HORIZON_OPTIONS.map(opt => (
              <button
                key={opt.value}
                onClick={() => setHorizon(opt.value)}
                style={{
                  ...cardBase,
                  ...(horizon === opt.value ? cardActive : {}),
                }}
              >
                <p
                  className="font-medium text-sm"
                  style={{ color: horizon === opt.value ? 'var(--accent)' : 'var(--text)' }}
                >
                  {opt.label}
                </p>
                <p className="text-xs mt-0.5" style={{ color: 'var(--muted)' }}>{opt.desc}</p>
              </button>
            ))}
          </div>
        </section>

        {/* Favorite sectors */}
        <section>
          <SectionLabel>Sectores favoritos</SectionLabel>
          <div className="flex flex-wrap gap-2 mt-3">
            {SECTORS.map(s => {
              const active = sectors.includes(s)
              return (
                <button
                  key={s}
                  onClick={() => toggleSector(s)}
                  className="px-3 py-1.5 rounded-full text-xs font-medium transition-all"
                  style={{
                    background: active ? 'var(--accent)' : 'var(--surface)',
                    color: active ? 'white' : 'var(--muted)',
                    border: active ? '1px solid var(--accent)' : '1px solid var(--border)',
                  }}
                >
                  {s}
                </button>
              )
            })}
          </div>
        </section>

        {/* Excluded tickers */}
        <section>
          <SectionLabel>Tickers excluidos</SectionLabel>
          <p className="text-xs mt-0.5 mb-3" style={{ color: 'var(--muted)' }}>
            Acciones que el agente evitará recomendar.
          </p>
          <div className="flex gap-2 mb-3">
            <input
              value={tickerInput}
              onChange={e => setTickerInput(e.target.value.toUpperCase())}
              onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addTicker() } }}
              placeholder="Ej: AAPL"
              className="flex-1 px-3 py-2 rounded-lg text-sm outline-none"
              style={{
                background: 'var(--surface)',
                color: 'var(--text)',
                border: '1px solid var(--border)',
              }}
            />
            <button
              onClick={addTicker}
              className="px-4 py-2 rounded-lg text-sm font-medium transition-opacity hover:opacity-80"
              style={{ background: 'var(--accent)', color: 'white' }}
            >
              Añadir
            </button>
          </div>
          {excluded.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {excluded.map(t => (
                <span
                  key={t}
                  className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono"
                  style={{
                    background: 'var(--surface)',
                    color: 'var(--text)',
                    border: '1px solid var(--border)',
                  }}
                >
                  {t}
                  <button
                    onClick={() => removeTicker(t)}
                    className="hover:opacity-60 transition-opacity ml-0.5"
                    style={{ color: 'var(--muted)', lineHeight: 1 }}
                    aria-label={`Eliminar ${t}`}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
        </section>

        {/* Save */}
        <div className="flex justify-end pb-4">
          <button
            onClick={handleSave}
            disabled={mutation.isPending}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium transition-opacity hover:opacity-80 disabled:opacity-50"
            style={{ background: 'var(--accent)', color: 'white' }}
          >
            <Save size={15} />
            {mutation.isPending ? 'Guardando...' : saved ? 'Guardado ✓' : 'Guardar cambios'}
          </button>
        </div>
      </div>
    </div>
  )
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p
      style={{
        fontSize: 10,
        textTransform: 'uppercase',
        letterSpacing: '0.1em',
        color: 'var(--muted)',
        fontWeight: 600,
      }}
    >
      {children}
    </p>
  )
}
