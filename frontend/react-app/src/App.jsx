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
import ProfilePanel from './components/ProfilePanel'
import OrdersPanel from './components/OrdersPanel'
import OutfitStudio from './components/OutfitStudio'
import { useApp } from './context/AppContext'

function AppShell() {
  const [page, setPage] = useState('home')
  const [tab, setTab] = useState('chat')   // 'chat' | 'outfits' | 'search' on home page
  const [cartOpen, setCartOpen] = useState(false)
  const [autoStartCascade, setAutoStartCascade] = useState(false)
  const [addModal, setAddModal] = useState(null) // Product object or null
  const { addToCartLocal, config, updateConfig } = useApp()

  const handleAddToCart = (product) => setAddModal(product)
  const handleAddConfirmed = (product, qty, shopifyData) => {
    addToCartLocal(product, qty, shopifyData)
    setAddModal(null)
  }

  const handleAutonomousCheckout = ({ mode = 'cascade_failover', autoStart = true } = {}) => {
    updateConfig({ demoMode: mode })
    setAutoStartCascade(autoStart)
    setCartOpen(true)
  }

  const navigate = (p) => {
    if (p === 'chat') {
      setPage('home')
      setTab('chat')
    } else if (p === 'outfits') {
      setPage('home')
      setTab('outfits')
    } else if (p === 'search') {
      setPage('home')
      setTab('search')
    } else {
      setPage(p)
    }
    if (cartOpen) setCartOpen(false)
  }

  return (
    <div className="app-shell">
      <Sidebar 
        activePage={page === 'home' ? (tab === 'outfits' ? 'outfits' : 'home') : page} 
        onNavigate={navigate} 
      />

      <div className="main-area">
        <Topbar onOpenCart={() => setCartOpen(true)} onNavigate={navigate} />

        <main className="main-content">
          {/* Home: Chat + Outfits + Search */}
          {page === 'home' && (
            <div>
              {/* Hero */}
              <div className="hero-banner">
                <h1>Rasor Agentic Commerce</h1>
                <p>
                  Your AI-powered personal stylist. Discover fashion, harmonize coordinated outfits with color theory, and checkout autonomously.
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
                <button className={`tab-item ${tab === 'outfits' ? 'active' : ''}`} onClick={() => setTab('outfits')}>
                  ✨ Outfit Studio
                </button>
                <button className={`tab-item ${tab === 'search' ? 'active' : ''}`} onClick={() => setTab('search')}>
                  🔍 Quick Search
                </button>
              </div>

              {/* Persistent Views: Keeping all 3 views mounted preserves complete chat history, state, and scroll position */}
              <div style={{ display: tab === 'chat' ? 'block' : 'none' }}>
                <ChatInterface onAddToCart={handleAddToCart} onAutonomousCheckout={handleAutonomousCheckout} onNavigate={navigate} />
              </div>
              <div style={{ display: tab === 'outfits' ? 'block' : 'none' }}>
                <OutfitStudio onAddToCart={handleAddToCart} onAutonomousCheckout={handleAutonomousCheckout} onNavigate={navigate} />
              </div>
              <div style={{ display: tab === 'search' ? 'block' : 'none' }}>
                <SearchPage onAddToCart={handleAddToCart} onAutonomousCheckout={handleAutonomousCheckout} />
              </div>
            </div>
          )}

          {page === 'chat' && <ChatInterface onAddToCart={handleAddToCart} onAutonomousCheckout={handleAutonomousCheckout} onNavigate={navigate} />}
          {page === 'outfits' && <OutfitStudio onAddToCart={handleAddToCart} onAutonomousCheckout={handleAutonomousCheckout} onNavigate={navigate} />}
          {page === 'search' && <SearchPage onAddToCart={handleAddToCart} onAutonomousCheckout={handleAutonomousCheckout} />}
          {page === 'profile' && <ProfilePanel />}
          {page === 'history' && <HistoryPanel onNavigate={navigate} onAddToCart={handleAddToCart} />}
          {page === 'features' && <FeatureShowcase />}
          {page === 'settings' && <SettingsPanel />}
          {(page === 'orders' || page === 'ledger') && <OrdersPanel onOpenCart={() => setCartOpen(true)} />}
          {page === 'compare' && <ComparePanel onAddToCart={handleAddToCart} />}
        </main>
      </div>

      {/* Cart Drawer */}
      {cartOpen && (
        <CartDrawer 
          onClose={() => {
            setCartOpen(false)
            setAutoStartCascade(false)
          }} 
          autoStartCascade={autoStartCascade}
          onResetAutoStartCascade={() => setAutoStartCascade(false)}
        />
      )}

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
