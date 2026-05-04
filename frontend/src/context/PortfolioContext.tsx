import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'
import { portfolioApi, type Portfolio } from '../lib/api'

const STORAGE_KEY = 'activePortfolioId'

interface PortfolioCtx {
  portfolios: Portfolio[]
  activeId: number
  setActiveId: (id: number) => void
  reload: () => void
}

const Ctx = createContext<PortfolioCtx>({
  portfolios: [], activeId: 1, setActiveId: () => {}, reload: () => {},
})

function readStoredId(): number {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    return v ? parseInt(v, 10) : 1
  } catch { return 1 }
}

export function PortfolioProvider({ children }: { children: ReactNode }) {
  const [portfolios, setPortfolios] = useState<Portfolio[]>([])
  const [activeId, setActiveIdState] = useState<number>(readStoredId)

  const setActiveId = (id: number) => {
    setActiveIdState(id)
    try { localStorage.setItem(STORAGE_KEY, String(id)) } catch {}
  }

  const load = async () => {
    try {
      const list = await portfolioApi.list()
      setPortfolios(list)
      if (list.length && !list.find(p => p.id === activeId)) {
        setActiveId(list[0].id)
      }
    } catch {}
  }

  useEffect(() => { load() }, [])

  return (
    <Ctx.Provider value={{ portfolios, activeId, setActiveId, reload: load }}>
      {children}
    </Ctx.Provider>
  )
}

export const usePortfolioCtx = () => useContext(Ctx)
