import { useState } from 'react'

interface Props {
  ticker: string
  logoUrl?: string | null
  size?: number
}

export function TickerLogo({ ticker, logoUrl, size = 24 }: Props) {
  const [failed, setFailed] = useState(false)
  const fmpUrl = `https://financialmodelingprep.com/image-stock/${ticker.toUpperCase()}.png`
  const src = (!failed && logoUrl) ? logoUrl : (!failed ? fmpUrl : null)

  if (!src || failed) {
    return (
      <div
        className="flex items-center justify-center rounded-full font-mono font-bold text-white flex-shrink-0"
        style={{
          width: size, height: size, fontSize: size * 0.35,
          background: 'var(--accent-dim, #1e3a5f)',
          border: '1px solid var(--border)',
        }}
      >
        {ticker.slice(0, 2)}
      </div>
    )
  }

  return (
    <img
      src={src}
      alt={ticker}
      onError={() => setFailed(true)}
      className="rounded-full object-contain flex-shrink-0"
      style={{
        width: size, height: size,
        background: 'var(--surface-2)',
        border: '1px solid var(--border)',
      }}
    />
  )
}
