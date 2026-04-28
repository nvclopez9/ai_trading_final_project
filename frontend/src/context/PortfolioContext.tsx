import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'
import { portfolioApi, type Portfolio } from '../lib/api'

interface PortfolioCtx {
  portfolios: Portfolio[]
  activeId: number
  setActiveId: (id: number) => void
  reload: () => void
}

const Ctx = createContext<PortfolioCtx>({
  portfolios: [], activeId: 1, setActiveId: () => {}, reload: () => {},
})

export function PortfolioProvider({ children }: { children: ReactNode }) {
  const [portfolios, setPortfolios] = useState<Portfolio[]>([])
  const [activeId, setActiveId] = useState<number>(1)

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
