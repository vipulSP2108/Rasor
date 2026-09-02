import React from 'react';
import { useState } from 'react'
import { Toaster } from 'react-hot-toast'
import { AppProvider } from './context/AppContext'
import Sidebar from './components/Sidebar'
import Topbar from './components/Topbar'
import ChatInterface from './components/ChatInterface'
import SearchPage from './components/SearchPage'
import CartDrawer from './components/CartDrawer'
import ComparePanel from './components/ComparePanel'
import SettingsPanel from './components/SettingsPanel'
import FeatureShowcase from './components/FeatureShowcase'
import HistoryPanel from './components/HistoryPanel'
import AddToCartModal from './components/AddToCartModal'
import { useApp } from './context/AppContext'

function AppShell() {
  const [page, setPage] = useState('home')
  const [tab, setTab] = useState('chat')   // 'chat' | 'search' on home page
  const [cartOpen, setCartOpen] = useState(false)
  const [addModal, setAddModal] = useState(null) // Product object or null
  const { addToCartLocal, config, updateConfig } = useApp()

  const handleAddToCart = (product) => setAddModal(product)
  const handleAddConfirmed = (product, qty, shopifyData) => {
    addToCartLocal(product, qty, shopifyData)
    setAddModal(null)
  }

  const navigate = (p) => {
    setPage(p)
    if (cartOpen) setCartOpen(false)
  }

  return (
    <div className="app-shell">
      <Sidebar activePage={page} onNavigate={navigate} />

      <div className="main-area">
        <Topbar onOpenCart={() => setCartOpen(true)} onNavigate={navigate} />

        <main className="main-content">
          {/* Home: Chat + Search */}
          {page === 'home' && (
            <div>
              {/* Hero */}
              <div className="hero-banner">
                <h1>Rasor Agentic Commerce</h1>
                <p>
                  Your AI-powered personal stylist. Discover fashion, get personalized recommendations, and check out — all through natural conversation.
                </p>
                <div className="protocol-badges">
                  <span className="protocol-badge ap2">AP2</span>
                  <span className="protocol-badge uap">UAP</span>
                  <span className="protocol-badge acp">ACP</span>
                  <span className="protocol-badge tap">TAP</span>
                </div>
              </div>

              {/* Tab bar */}
              <div className="tab-bar">
                <button className={`tab-item ${tab === 'chat' ? 'active' : ''}`} onClick={() => setTab('chat')}>
                  💬 AI Stylist Chat
                </button>
                <button className={`tab-item ${tab === 'search' ? 'active' : ''}`} onClick={() => setTab('search')}>
                  🔍 Quick Search
                </button>
              </div>

              {tab === 'chat'
                ? <ChatInterface onAddToCart={handleAddToCart} />
                : <SearchPage onAddToCart={handleAddToCart} />
              }
            </div>
          )}

          {page === 'chat' && <ChatInterface onAddToCart={handleAddToCart} />}
          {page === 'history' && <HistoryPanel onNavigate={navigate} onAddToCart={handleAddToCart} />}
          {page === 'features' && <FeatureShowcase />}
          {page === 'settings' && <SettingsPanel />}
          {page === 'ledger' && <SettingsPanel initialSection="ledger" />}
          {page === 'compare' && <ComparePanel onAddToCart={handleAddToCart} />}
        </main>
      </div>

      {/* Cart Drawer */}
      {cartOpen && <CartDrawer onClose={() => setCartOpen(false)} />}

      {/* Add to Cart Modal */}
      {addModal && (
        <AddToCartModal
          product={addModal}
          onConfirm={handleAddConfirmed}
          onClose={() => setAddModal(null)}
          config={config}
        />
      )}

      <Toaster
        position="bottom-right"
        toastOptions={{
          style: {
            background: 'var(--bg-elevated)',
            color: 'var(--text-primary)',
            border: '1px solid var(--border)',
            fontSize: '0.875rem',
          },
        }}
      />
    </div>
  )
}

export default function App() {
  return (
    <AppProvider>
      <AppShell />
    </AppProvider>
  )
}
