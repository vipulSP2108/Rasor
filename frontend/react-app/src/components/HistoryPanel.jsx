import React, { useState } from 'react'
import { 
  History, Trash2, Search, Sparkles, MessageCircle, ChevronDown, 
  ChevronUp, ChevronLeft, ChevronRight, ExternalLink, RefreshCw, ShoppingBag, ArrowRight, Tag,
  Calendar, Layers, Filter
} from 'lucide-react'
import { useApp } from '../context/AppContext'
import { getProductsByIds, searchProducts } from '../api/client'
import ProductCard from './ProductCard'
import toast from 'react-hot-toast'

const PAGE_SIZE = 4

export default function HistoryPanel({ onNavigate, onAddToCart }) {
  const { 
    config,
    historyRecords, 
    deleteHistoryRecord, 
    clearHistoryRecords, 
    productCache,
    cacheProducts,
    setSearchState,
    setChatMessages
  } = useApp()

  const [sourceFilter, setSourceFilter] = useState('all') // 'all' | 'chat' | 'search'
  const [searchTerm, setSearchTerm] = useState('')
  const [expandedRecordIds, setExpandedRecordIds] = useState({})
  const [recordPages, setRecordPages] = useState({})
  const [loadingRecordId, setLoadingRecordId] = useState(null)

  const handleFetchPicksInPlace = async (record) => {
    setLoadingRecordId(record.id)
    setExpandedRecordIds(prev => ({ ...prev, [record.id]: true }))
    try {
      // 1. If we have stored product IDs, fetch them directly in a single batch!
      if (record.productIds && record.productIds.length > 0) {
        const { data } = await getProductsByIds({ ids: record.productIds })
        const prods = data.products || []
        if (prods.length > 0) {
          cacheProducts(prods)
          toast.success(`Loaded ${prods.length} stored picks for "${record.query}"`)
          return
        }
      }

      // 2. Fallback: Search Shopify endpoint if no IDs stored
      const { data } = await searchProducts({
        query: record.query,
        data_source: 'shopify_storefront_live_api',
        primary_model: config.primaryModel,
        fallback_model: config.fallbackModel,
        max_results: 20,
        enable_deep_enrichment: false,
        enable_vqa_scanner: false,
        enable_semantic_engine: true,
        currency: config.currency,
      })
      const prods = data.products || []
      if (prods.length > 0) {
        cacheProducts(prods)
        toast.success(`Loaded ${prods.length} picks from Shopify for "${record.query}"`)
      } else {
        toast('No live products returned for this search', { icon: '🔍' })
      }
    } catch (err) {
      toast.error('Failed to fetch picks: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoadingRecordId(null)
    }
  }

  const toggleExpand = (record) => {
    const isCurrentlyExpanded = !!expandedRecordIds[record.id]
    const cachedProducts = (record.productIds || []).map(id => productCache[id]).filter(Boolean)

    if (isCurrentlyExpanded) {
      setExpandedRecordIds(prev => ({ ...prev, [record.id]: false }))
    } else {
      if (cachedProducts.length > 0) {
        setExpandedRecordIds(prev => ({ ...prev, [record.id]: true }))
      } else {
        // Fetch in-place immediately
        handleFetchPicksInPlace(record)
      }
    }
  }

  const handleDelete = (id, e) => {
    e.stopPropagation()
    deleteHistoryRecord(id)
    toast.success('Search record deleted')
  }

  const handleClearAll = () => {
    if (window.confirm('Are you sure you want to clear your entire search and stylist history?')) {
      clearHistoryRecords()
      toast.success('All history cleared')
    }
  }

  const handleReRun = (record) => {
    if (record.source === 'chat') {
      onNavigate('chat')
    } else {
      setSearchState({ query: record.query })
      onNavigate('home')
    }
  }

  const filteredRecords = historyRecords.filter(r => {
    if (sourceFilter !== 'all' && r.source !== sourceFilter) return false
    if (searchTerm.trim()) {
      const rawTerm = searchTerm.toLowerCase().trim()
      // Remove any prefix like "theme:", "design:", "tag:", etc. for flexible matching
      const normalizedTerm = rawTerm.replace(/^(theme|fandom|design|category|gender|color|fit|sleeve|size|occasion|budget|tag):\s*/i, '').trim()
      
      const meta = r.metadata || {}
      const metaPairs = [
        `theme: ${meta.fandom || ''}`,
        `fandom: ${meta.fandom || ''}`,
        `design: ${meta.design || ''}`,
        `category: ${meta.category || ''}`,
        `gender: ${meta.gender || ''}`,
        `color: ${meta.color || ''}`,
        `fit: ${meta.fit || ''}`,
        `sleeve: ${meta.sleeve || ''}`,
        `size: ${meta.size || ''}`,
        `occasion: ${meta.occasion || ''}`,
        `budget: ${meta.budgetCap || ''}`,
      ]

      const searchableHaystack = [
        r.query,
        r.source,
        ...Object.values(meta),
        ...Object.keys(meta),
        ...metaPairs
      ].filter(Boolean).join(' ').toLowerCase()

      return searchableHaystack.includes(rawTerm) || (normalizedTerm && searchableHaystack.includes(normalizedTerm))
    }
    return true
  })

  return (
    <div className="animate-fade-in" style={{ maxWidth: 1000, margin: '0 auto' }}>
      {/* Header Banner */}
      <div className="card" style={{ padding: '24px 28px', marginBottom: 24, background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.9), rgba(30, 41, 59, 0.8))' }}>
        <div className="flex items-center justify-between" style={{ flexWrap: 'wrap', gap: 14 }}>
          <div>
            <h2 style={{ fontSize: '1.4rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
              <History size={24} color="var(--accent-purple)" />
              Search & Stylist History
              <span className="badge badge-purple" style={{ fontSize: '0.75rem', padding: '3px 9px' }}>
                {historyRecords.length} Queries
              </span>
            </h2>
            <p className="text-sm text-muted">
              Lightweight audit history of all fashion searches, categorized attributes, and recommended product snapshots.
            </p>
          </div>
          {historyRecords.length > 0 && (
            <button 
              className="btn btn-ghost btn-sm" 
              onClick={handleClearAll}
              style={{ color: 'var(--accent-red)', borderColor: 'rgba(239, 68, 68, 0.3)', display: 'flex', alignItems: 'center', gap: 6 }}
            >
              <Trash2 size={14} />
              Clear All History
            </button>
          )}
        </div>

        {/* Filter Toolbar */}
        <div className="flex items-center justify-between" style={{ marginTop: 20, paddingTop: 16, borderTop: '1px solid rgba(255, 255, 255, 0.08)', flexWrap: 'wrap', gap: 12 }}>
          {/* Source Tabs */}
          <div className="flex gap-2">
            <button 
              className={`chat-chip ${sourceFilter === 'all' ? 'active' : ''}`}
              style={{ 
                background: sourceFilter === 'all' ? 'var(--accent-purple)' : 'rgba(255, 255, 255, 0.05)',
                color: sourceFilter === 'all' ? '#fff' : 'var(--text-secondary)'
              }}
              onClick={() => setSourceFilter('all')}
            >
              <Layers size={13} />
              All ({historyRecords.length})
            </button>
            <button 
              className={`chat-chip ${sourceFilter === 'chat' ? 'active' : ''}`}
              style={{ 
                background: sourceFilter === 'chat' ? 'var(--accent-purple)' : 'rgba(255, 255, 255, 0.05)',
                color: sourceFilter === 'chat' ? '#fff' : 'var(--text-secondary)'
              }}
              onClick={() => setSourceFilter('chat')}
            >
              <MessageCircle size={13} />
              AI Stylist Chat ({historyRecords.filter(r => r.source === 'chat').length})
            </button>
            <button 
              className={`chat-chip ${sourceFilter === 'search' ? 'active' : ''}`}
              style={{ 
                background: sourceFilter === 'search' ? 'var(--accent-purple)' : 'rgba(255, 255, 255, 0.05)',
                color: sourceFilter === 'search' ? '#fff' : 'var(--text-secondary)'
              }}
              onClick={() => setSourceFilter('search')}
            >
              <Search size={13} />
              Quick Search ({historyRecords.filter(r => r.source === 'search').length})
            </button>
          </div>

          {/* Quick Filter Input */}
          <div style={{ position: 'relative', width: 240 }}>
            <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input 
              className="input input-sm" 
              style={{ paddingLeft: 30, fontSize: '0.8rem' }}
              placeholder="Filter by query or tag…" 
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
            />
          </div>
        </div>
      </div>

      {/* History Cards List */}
      {filteredRecords.length === 0 ? (
        <div className="card text-center" style={{ padding: '48px 20px' }}>
          <History size={40} style={{ opacity: 0.3, margin: '0 auto 12px' }} />
          <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: 6 }}>No Search History Found</h3>
          <p className="text-sm text-muted" style={{ maxWidth: 400, margin: '0 auto 16px' }}>
            {historyRecords.length === 0 
              ? 'Start chatting with the AI Stylist or search the catalog to build your history.' 
              : 'No search records match your current filter.'}
          </p>
          <button className="btn btn-primary btn-sm" onClick={() => onNavigate('home')}>
            Go to Shop
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {filteredRecords.map(record => {
            const isExpanded = !!expandedRecordIds[record.id]
            const meta = record.metadata || {}
            // Retrieve products from cache if available
            const cachedProducts = (record.productIds || []).map(id => productCache[id]).filter(Boolean)

            return (
              <div 
                key={record.id} 
                className="card" 
                style={{ 
                  padding: '20px 24px', 
                  borderLeft: `4px solid ${record.source === 'chat' ? 'var(--accent-purple)' : 'var(--accent-green)'}`,
                  transition: 'var(--transition)'
                }}
              >
                {/* Top Row: Source, Date, Delete */}
                <div className="flex items-center justify-between" style={{ marginBottom: 12 }}>
                  <div className="flex items-center gap-3">
                    <span 
                      className={`badge ${record.source === 'chat' ? 'badge-purple' : 'badge-green'}`}
                      style={{ fontSize: '0.72rem', padding: '3px 8px', display: 'flex', alignItems: 'center', gap: 4 }}
                    >
                      {record.source === 'chat' ? <MessageCircle size={11} /> : <Search size={11} />}
                      {record.source === 'chat' ? 'AI Stylist Dialogue' : 'Quick Search'}
                    </span>
                    <span className="text-xs text-muted" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <Calendar size={12} />
                      {record.formattedDate}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <button 
                      className="btn btn-ghost btn-xs"
                      onClick={() => handleReRun(record)}
                      title="Re-run search"
                      style={{ fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: 4 }}
                    >
                      <RefreshCw size={12} />
                      Shop Again
                    </button>
                    <button 
                      className="btn btn-ghost btn-icon btn-xs"
                      onClick={(e) => handleDelete(record.id, e)}
                      title="Delete entry"
                      style={{ color: 'var(--text-muted)' }}
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>

                {/* Query Header */}
                <div style={{ marginBottom: 14 }}>
                  <h4 style={{ fontSize: '1.05rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>
                    "{record.query}"
                  </h4>
                </div>

                {/* Metadata Attribute Badges (Clickable for instant tag filtering) */}
                <div 
                  style={{ 
                    display: 'flex', 
                    flexWrap: 'wrap', 
                    gap: '6px 10px',
                    padding: '10px 14px',
                    background: 'rgba(255, 255, 255, 0.025)',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid rgba(255, 255, 255, 0.06)',
                    marginBottom: 14,
                    fontSize: '0.78rem'
                  }}
                >
                  <span 
                    className="badge" 
                    onClick={() => setSearchTerm(`Gender: ${meta.gender || 'All'}`)}
                    style={{ cursor: 'pointer', background: 'rgba(99, 102, 241, 0.15)', color: '#c7d2fe', border: '1px solid rgba(99, 102, 241, 0.3)', padding: '3px 8px' }}
                    title="Click to filter by this gender"
                  >
                    Gender: <strong>{meta.gender || 'All'}</strong>
                  </span>
                  <span 
                    className="badge" 
                    onClick={() => setSearchTerm(`Category: ${meta.category || 'Any'}`)}
                    style={{ cursor: 'pointer', background: 'rgba(99, 102, 241, 0.15)', color: '#c7d2fe', border: '1px solid rgba(99, 102, 241, 0.3)', padding: '3px 8px' }}
                    title="Click to filter by this category"
                  >
                    Category: <strong>{meta.category || 'Any'}</strong>
                  </span>
                  {meta.fandom && (
                    <span 
                      className="badge" 
                      onClick={() => setSearchTerm(`Theme: ${meta.fandom}`)}
                      style={{ cursor: 'pointer', background: 'rgba(239, 68, 68, 0.18)', color: '#fca5a5', border: '1px solid rgba(239, 68, 68, 0.35)', padding: '3px 8px' }}
                      title="Click to filter by this theme"
                    >
                      Theme: <strong>{meta.fandom}</strong>
                    </span>
                  )}
                  {meta.design && meta.design !== 'Any' && (
                    <span 
                      className="badge" 
                      onClick={() => setSearchTerm(`Design: ${meta.design}`)}
                      style={{ cursor: 'pointer', background: 'rgba(16, 185, 129, 0.15)', color: '#6ee7b7', border: '1px solid rgba(16, 185, 129, 0.3)', padding: '3px 8px' }}
                      title="Click to filter by this design"
                    >
                      Design: <strong>{meta.design}</strong>
                    </span>
                  )}
                  {meta.color && meta.color !== 'Any' && (
                    <span 
                      className="badge" 
                      onClick={() => setSearchTerm(`Color: ${meta.color}`)}
                      style={{ cursor: 'pointer', background: 'rgba(245, 158, 11, 0.15)', color: '#fcd34d', border: '1px solid rgba(245, 158, 11, 0.3)', padding: '3px 8px' }}
                      title="Click to filter by this color"
                    >
                      Color: <strong>{meta.color}</strong>
                    </span>
                  )}
                  {meta.fit && meta.fit !== 'Any' && (
                    <span 
                      className="badge" 
                      onClick={() => setSearchTerm(`Fit: ${meta.fit}`)}
                      style={{ cursor: 'pointer', background: 'rgba(168, 85, 247, 0.15)', color: '#d8b4fe', border: '1px solid rgba(168, 85, 247, 0.3)', padding: '3px 8px' }}
                      title="Click to filter by this fit"
                    >
                      Fit: <strong>{meta.fit}</strong>
                    </span>
                  )}
                  {meta.sleeve && meta.sleeve !== 'Any' && (
                    <span 
                      className="badge" 
                      onClick={() => setSearchTerm(`Sleeve: ${meta.sleeve}`)}
                      style={{ cursor: 'pointer', background: 'rgba(59, 130, 246, 0.15)', color: '#93c5fd', border: '1px solid rgba(59, 130, 246, 0.3)', padding: '3px 8px' }}
                      title="Click to filter by this sleeve"
                    >
                      Sleeve: <strong>{meta.sleeve}</strong>
                    </span>
                  )}
                  {meta.size && meta.size !== 'Any' && (
                    <span 
                      className="badge" 
                      onClick={() => setSearchTerm(`Size: ${meta.size}`)}
                      style={{ cursor: 'pointer', background: 'rgba(255, 255, 255, 0.08)', color: '#f1f5f9', border: '1px solid rgba(255, 255, 255, 0.15)', padding: '3px 8px' }}
                      title="Click to filter by this size"
                    >
                      Size: <strong>{meta.size}</strong>
                    </span>
                  )}
                  {meta.occasion && meta.occasion !== 'Any' && (
                    <span 
                      className="badge" 
                      onClick={() => setSearchTerm(`Occasion: ${meta.occasion}`)}
                      style={{ cursor: 'pointer', background: 'rgba(255, 255, 255, 0.08)', color: '#f1f5f9', border: '1px solid rgba(255, 255, 255, 0.15)', padding: '3px 8px' }}
                      title="Click to filter by this occasion"
                    >
                      Occasion: <strong>{meta.occasion}</strong>
                    </span>
                  )}
                  <span 
                    className="badge" 
                    onClick={() => setSearchTerm(`Budget: ${meta.budgetCap || ''}`)}
                    style={{ cursor: 'pointer', background: 'rgba(16, 185, 129, 0.15)', color: '#6ee7b7', border: '1px solid rgba(16, 185, 129, 0.3)', padding: '3px 8px' }}
                    title="Click to filter by budget"
                  >
                    Budget: <strong>{meta.budgetCap || 'No Cap'}</strong>
                  </span>
                </div>

                {/* Bottom Row: Thumbnails & Expand Button */}
                <div className="flex items-center justify-between" style={{ flexWrap: 'wrap', gap: 10 }}>
                  <div className="flex items-center gap-3">
                    {/* Sample image previews */}
                    {record.sampleThumbnails && record.sampleThumbnails.length > 0 && (
                      <div className="flex gap-1" style={{ alignItems: 'center' }}>
                        {record.sampleThumbnails.map((img, idx) => (
                          <img 
                            key={idx} 
                            src={img} 
                            alt="" 
                            style={{ width: 30, height: 36, objectFit: 'cover', borderRadius: 4, border: '1px solid rgba(255,255,255,0.1)' }} 
                          />
                        ))}
                      </div>
                    )}
                    <span className="text-xs text-muted">
                      ✨ <strong>{record.itemCount || (record.productIds || []).length}</strong> products recommended
                    </span>
                  </div>

                  <button 
                    className="btn btn-secondary btn-sm"
                    onClick={() => toggleExpand(record)}
                    disabled={loadingRecordId === record.id}
                    style={{ 
                      fontSize: '0.8rem', 
                      display: 'flex', 
                      alignItems: 'center', 
                      gap: 6, 
                      background: isExpanded ? 'rgba(99, 102, 241, 0.2)' : 'rgba(255, 255, 255, 0.06)',
                      border: '1px solid rgba(99, 102, 241, 0.35)',
                      color: isExpanded ? '#c7d2fe' : 'var(--text-primary)'
                    }}
                  >
                    {loadingRecordId === record.id ? (
                      <><span className="spinner spinner-sm" /> Fetching Live Picks…</>
                    ) : isExpanded ? (
                      <><ChevronUp size={14} /> Hide Recommendations</>
                    ) : (
                      <><ChevronDown size={14} /> View {record.itemCount || (record.productIds || []).length} Picks</>
                    )}
                  </button>
                </div>

                {/* Expanded Products Shelf */}
                {isExpanded && (
                  <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid rgba(255, 255, 255, 0.08)' }}>
                    {loadingRecordId === record.id ? (
                      <div style={{ padding: '32px 16px', textAlign: 'center', color: 'var(--text-muted)' }}>
                        <div className="spinner" style={{ margin: '0 auto 10px', width: 24, height: 24 }} />
                        <p className="text-sm">Fetching latest live catalog recommendations for "{record.query}"…</p>
                      </div>
                    ) : cachedProducts.length > 0 ? (
                      <div>
                        <div className="history-product-grid">
                          {cachedProducts
                            .slice(((recordPages[record.id] || 1) - 1) * PAGE_SIZE, (recordPages[record.id] || 1) * PAGE_SIZE)
                            .map(p => (
                              <ProductCard key={p.id} product={p} onAddToCart={onAddToCart} />
                            ))
                          }
                        </div>

                        {/* 4-Item Batch Pagination Controls */}
                        {cachedProducts.length > PAGE_SIZE && (
                          <div className="flex items-center justify-center gap-4" style={{ marginTop: 18, paddingTop: 14, borderTop: '1px solid rgba(255, 255, 255, 0.06)' }}>
                            <button 
                              className="btn btn-outline btn-sm" 
                              onClick={() => setRecordPages(prev => ({ 
                                ...prev, 
                                [record.id]: Math.max(1, (prev[record.id] || 1) - 1) 
                              }))}
                              disabled={(recordPages[record.id] || 1) === 1}
                              style={{ fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: 4 }}
                            >
                              <ChevronLeft size={14} /> Previous
                            </button>
                            <span className="text-xs text-muted" style={{ fontWeight: 600 }}>
                              Page {recordPages[record.id] || 1} of {Math.ceil(cachedProducts.length / PAGE_SIZE)}
                            </span>
                            <button 
                              className="btn btn-outline btn-sm" 
                              onClick={() => setRecordPages(prev => ({ 
                                ...prev, 
                                [record.id]: Math.min(Math.ceil(cachedProducts.length / PAGE_SIZE), (prev[record.id] || 1) + 1) 
                              }))}
                              disabled={(recordPages[record.id] || 1) === Math.ceil(cachedProducts.length / PAGE_SIZE)}
                              style={{ fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: 4 }}
                            >
                              Next <ChevronRight size={14} />
                            </button>
                          </div>
                        )}
                      </div>
                    ) : (
                      <div style={{ padding: '20px 16px', background: 'rgba(255, 255, 255, 0.02)', borderRadius: 'var(--radius-sm)', textAlign: 'center' }}>
                        <p className="text-xs text-muted" style={{ marginBottom: 10 }}>
                          Picks are ready to be fetched directly from live catalog.
                        </p>
                        <button className="btn btn-primary btn-xs" onClick={() => handleFetchPicksInPlace(record)}>
                          <RefreshCw size={12} style={{ marginRight: 4 }} />
                          Fetch Live Picks In-Place
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
