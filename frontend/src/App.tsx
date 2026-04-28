import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useEffect } from 'react'
import { PortfolioProvider } from './context/PortfolioContext'
import { Sidebar } from './components/layout/Sidebar'
import { ChatPage } from './pages/ChatPage'
import { PortfolioPage } from './pages/PortfolioPage'
import { PortfoliosPage } from './pages/PortfoliosPage'
import { MarketPage } from './pages/MarketPage'
import { TopPage } from './pages/TopPage'
import { NewsPage } from './pages/NewsPage'
import { HelpPage } from './pages/HelpPage'
import { ProfilePage } from './pages/ProfilePage'
import { ToastProvider } from './components/ui/Toast'

const qc = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30_000 },
  },
})

// Handles prefill from news page navigation
function ChatPageWithPrefill() {
  return <ChatPage />
}

// Handles market_ticker from top page navigation
function MarketPageWithState() {
  useEffect(() => {
    sessionStorage.removeItem('market_ticker')
  }, [])

  return <MarketPage />
}

function AppLayout() {
  return (
    <div className="flex h-screen w-full" style={{ background: 'var(--bg)' }}>
      <Sidebar />
      <main className="flex-1 min-w-0 flex flex-col overflow-hidden">
        <Routes>
          <Route path="/" element={<Navigate to="/chat" replace />} />
          <Route path="/chat" element={<ChatPageWithPrefill />} />
          <Route path="/portfolio" element={<PortfolioPage />} />
          <Route path="/portfolios" element={<PortfoliosPage />} />
          <Route path="/market" element={<MarketPageWithState />} />
          <Route path="/top" element={<TopPage />} />
          <Route path="/news" element={<NewsPage />} />
          <Route path="/help" element={<HelpPage />} />
          <Route path="/profile" element={<ProfilePage />} />
        </Routes>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <PortfolioProvider>
          <BrowserRouter>
            <AppLayout />
          </BrowserRouter>
        </PortfolioProvider>
      </ToastProvider>
    </QueryClientProvider>
  )
}
