import React, { useState } from 'react'
import {
  ShoppingBag, MessageCircle, Search, Settings, BookOpen,
  BarChart2, ChevronLeft, ChevronRight, Zap, Star, FileText, Scale, History, User, PackageCheck, Sparkles
} from 'lucide-react'
import { useApp } from '../context/AppContext'

const NAV_ITEMS = [
  { id: 'home', icon: <ShoppingBag size={18} />, label: 'Shop', section: 'commerce' },
  { id: 'outfits', icon: <Sparkles size={18} />, label: 'Outfit Studio', section: 'commerce' },
  { id: 'orders', icon: <PackageCheck size={18} />, label: 'Orders & Ledger', section: 'commerce' },
  { id: 'history', icon: <History size={18} />, label: 'History', section: 'commerce' },
  { id: 'compare', icon: <Scale size={18} />, label: 'Compare', section: 'commerce' },
  { id: 'features', icon: <Zap size={18} />, label: 'Features', section: 'commerce' },
  { id: 'profile', icon: <User size={18} />, label: 'My Profile', section: 'account' },
  { id: 'settings', icon: <Settings size={18} />, label: 'Settings', section: 'account' },
]

export default function Sidebar({ activePage, onNavigate }) {
  const [collapsed, setCollapsed] = useState(false)
  const { compareList, historyRecords = [] } = useApp()

  const compareCount = Object.keys(compareList || {}).length
  const historyCount = historyRecords.length

  const sections = ['commerce', 'account']
  const sectionLabels = { commerce: 'Commerce', account: 'Account & Settings' }

  return (
    <aside className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
      {/* Logo */}
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon">🛍️</div>
        {!collapsed && <span className="sidebar-logo-text">Rasor</span>}
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">
        {sections.map(section => (
          <div
            key={section}
            style={section === 'account' ? {
              marginTop: 'auto',
              paddingTop: 10,
              borderTop: '1px solid var(--border)'
            } : undefined}
          >
            {!collapsed && (
              <div className="sidebar-section-label">{sectionLabels[section]}</div>
            )}
            {NAV_ITEMS.filter(n => n.section === section).map(item => (
              <button
                key={item.id}
                className={`sidebar-nav-item ${activePage === item.id ? 'active' : ''}`}
                onClick={() => onNavigate(item.id)}
                title={collapsed ? item.label : undefined}
              >
                <span className="nav-icon">{item.icon}</span>
                {!collapsed && <span className="nav-label">{item.label}</span>}
                {item.id === 'compare' && compareCount > 0 && (
                  <span className="sidebar-badge badge-compare">
                    {compareCount}
                  </span>
                )}
              </button>
            ))}
          </div>
        ))}
      </nav>

      {/* Toggle */}
      <div className="sidebar-toggle">
        <button onClick={() => setCollapsed(c => !c)}>
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>
    </aside>
  )
}
