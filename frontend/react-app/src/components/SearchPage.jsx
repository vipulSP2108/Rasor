import React, { useState, useEffect, useMemo } from 'react'
import { Search, Sliders, Grid, List, ChevronDown, ChevronUp, Package, Trash2, ChevronLeft, ChevronRight, History, RotateCcw, Sparkles, Truck, Star } from 'lucide-react'
import { searchProducts, estimateLogistics } from '../api/client'
import { useApp } from '../context/AppContext'
import ProductCard from './ProductCard'
import BatchedProductGrid from './BatchedProductGrid'
import toast from 'react-hot-toast'

const QUICK_SEARCHES = [
  'Black oversized t-shirt',
  'Marvel graphic tee',
  'Gym dry-fit top',
  'Polo shirts for men',
  'Pastel hoodie women',
]

export default function SearchPage({ onAddToCart }) {
  const { 
    config, 
    searchState, 
    setSearchState, 
    searchHistory, 
    saveSearchSnapshot, 
    restoreSearchSnapshot, 
    clearSearchHistory,
    addHistoryRecord
  } = useApp()

  const {
    query = '',
    results = [],
    discardedProducts = [],
    evaluations = [],
    canonicalQuery = null,
    status = null,
  } = searchState

  const [loading, setLoading] = useState(false)
  const [loadingStage, setLoadingStage] = useState(0)
  const [layout, setLayout] = useState('grid')
  const [currentPage, setCurrentPage] = useState(1)
  const [showEval, setShowEval] = useState(false)
  const [showDiscarded, setShowDiscarded] = useState(false)
  const [sortMode, setSortMode] = useState('relevance') // 'relevance' | 'fastest_delivery' | 'slowest_delivery' | 'price_asc' | 'price_desc' | 'rating'
  const [isDeliverySorted, setIsDeliverySorted] = useState(false)
  const [fastDeliveryOnly, setFastDeliveryOnly] = useState(false)
  const [approvalFilter, setApprovalFilter] = useState('all') // 'all' | 'pre_approved' | 'requires_approval'
  const [minRatingFilter, setMinRatingFilter] = useState(0)
  const [calculatingLogistics, setCalculatingLogistics] = useState(false)
  const pageSize = 12

  // On-demand logistics calculation: runs ONLY delivery agent on existing candidates when delivery sort is selected
  const handleSortChange = async (newSort) => {
    setSortMode(newSort)

    if ((newSort === 'fastest_delivery' || newSort === 'slowest_delivery') && !isDeliverySorted && results.length > 0) {
      setCalculatingLogistics(true)
      const toastId = toast.loading('Calculating warehouse distances & delivery estimates...')
      try {
        const { data } = await estimateLogistics({
          products: results,
          location: config.userLocation || 'Mumbai, Maharashtra'
        })

        const estimates = data.estimates || {}
        const enrichedSpecs = data.enriched_specs || {}

        const updatedProducts = results.map(p => {
          const est = estimates[p.id]
          const spec = enrichedSpecs[p.id] || p.specs || {}
          if (est) {
            return {
              ...p,
              shipping_days: est.shipping_days,
              shipping_speed: est.speed_label,
              is_fast_shipping_requested: true,
              specs: {
                ...spec,
                shipping_days: est.shipping_days,
                shipping_speed: est.speed_label,
                origin_hub: est.origin_hub,
                distance_km: est.distance_km,
                destination_display: est.destination_display,
              }
            }
          }
          return { ...p, is_fast_shipping_requested: true }
        })

        setSearchState({
          ...searchState,
          results: updatedProducts
        })
        setIsDeliverySorted(true)
        toast.success('Live transit calculated! Sorted by fastest delivery.', { id: toastId })
      } catch (err) {
        console.error('Failed to calculate logistics:', err)
        toast.error('Could not calculate delivery times: ' + (err.response?.data?.detail || err.message), { id: toastId })
      } finally {
        setCalculatingLogistics(false)
      }
    }
  }

  // Reset pagination to page 1 whenever any filter or sort changes
  useEffect(() => {
    setCurrentPage(1)
  }, [fastDeliveryOnly, approvalFilter, minRatingFilter, sortMode])

  // Client-side filtering & sorting
  const sortedResults = useMemo(() => {
    if (!results || results.length === 0) return []
    let list = [...results]

    // 1. Quick Filters
    if (fastDeliveryOnly) {
      list = list.filter(p => Number(p.shipping_days ?? p.specs?.shipping_days ?? 3) <= 2)
    }
    const hitlLimit = Number(config.maxCostHitl || 800)
    if (approvalFilter === 'pre_approved') {
      list = list.filter(p => Number(p.price || 0) <= hitlLimit)
    } else if (approvalFilter === 'requires_approval') {
      list = list.filter(p => Number(p.price || 0) > hitlLimit)
    }
    if (minRatingFilter > 0) {
      list = list.filter(p => Number(p.rating || 0) >= minRatingFilter)
    }

    // 2. Multi-Mode Sorting
    if (sortMode === 'fastest_delivery') {
      list.sort((a, b) => {
        const scoreA = a.relevance_score ?? 0.5
        const scoreB = b.relevance_score ?? 0.5
        const tierA = Math.floor(scoreA * 10) / 10
        const tierB = Math.floor(scoreB * 10) / 10
        if (tierA !== tierB) return tierB - tierA
        const daysA = a.shipping_days ?? a.specs?.shipping_days ?? 99
        const daysB = b.shipping_days ?? b.specs?.shipping_days ?? 99
        return daysA - daysB
      })
    } else if (sortMode === 'slowest_delivery') {
      list.sort((a, b) => {
        const scoreA = a.relevance_score ?? 0.5
        const scoreB = b.relevance_score ?? 0.5
        const tierA = Math.floor(scoreA * 10) / 10
        const tierB = Math.floor(scoreB * 10) / 10
        if (tierA !== tierB) return tierB - tierA
        const daysA = a.shipping_days ?? a.specs?.shipping_days ?? 99
        const daysB = b.shipping_days ?? b.specs?.shipping_days ?? 99
        return daysB - daysA
      })
    } else if (sortMode === 'price_asc') {
      list.sort((a, b) => (a.price || 0) - (b.price || 0))
    } else if (sortMode === 'price_desc') {
      list.sort((a, b) => (b.price || 0) - (a.price || 0))
    } else if (sortMode === 'rating') {
      list.sort((a, b) => {
        const rA = (a.rating || 0) * Math.log10((a.review_count || 1) + 1)
        const rB = (b.rating || 0) * Math.log10((b.review_count || 1) + 1)
        return rB - rA
      })
    } else {
      // Relevance default
      list.sort((a, b) => (b.relevance_score ?? 0.5) - (a.relevance_score ?? 0.5))
    }

    return list
  }, [results, sortMode, fastDeliveryOnly, approvalFilter, minRatingFilter, config.maxCostHitl])

  useEffect(() => {
    let interval
    if (loading) {
      setLoadingStage(0)
      interval = setInterval(() => {
        setLoadingStage(s => Math.min(s + 1, 2))
      }, 2500)
    }
    return () => clearInterval(interval)
  }, [loading])

  const isVqaApplicable = config.enableVqaScanner || /iron\s*man|spiderman|spider-man|batman|deadpool|anime|marvel|dc|print|graphic|art|scene|character|back\s*print|logo|drawing|cartoon|illustration|standing|flying|pattern|washed|tie-dye/i.test(query)

  const stages = [
    "🤖 Stage 1: LLM Normalized Taxonomy...",
    "📡 Stage 2: Querying catalog...",
    isVqaApplicable ? "👁️ Stage 3: Exhaustive VQA Scanning..." : "⚡ Stage 3: Neural Scoring & Catalog Validation..."
  ]

  const runSearch = async (q = query) => {
    if (!q.trim()) return
    setLoading(true)
    setSearchState({
      query: q,
      results: [],
      discardedProducts: [],
      evaluations: [],
      canonicalQuery: null,
      status: null,
    })
    setCurrentPage(1)

    try {
      const { data } = await searchProducts({
        query: q,
        data_source: config.dataSource,
        primary_model: config.primaryModel,
        fallback_model: config.fallbackModel,
        max_results: config.maxResults,
        enable_deep_enrichment: config.enableDeepEnrichment,
        max_deep_fetches: config.maxDeepFetches,
        enable_vqa_scanner: config.enableVqaScanner,
        vqa_strict_filter: config.vqaStrictFilter,
        vqa_limit: config.vqaLimit ?? 8,
        truth_hierarchy: config.truthHierarchy,
        enable_semantic_engine: config.enableSemanticEngine,
        currency: config.currency,
        user_location: config.userLocation,
      })
      const prods = data.products || []
      const disc = data.discarded_products || []
      const evals = data.evaluations || []
      const cq = data.canonical_query
      const st = data.status
      const serverDeliverySorted = data.is_delivery_sorted || false

      setIsDeliverySorted(serverDeliverySorted)
      // Auto-switch to fastest delivery sort if server used it
      if (serverDeliverySorted) setSortMode('fastest_delivery')
      else setSortMode('relevance')

      setSearchState({
        query: q,
        results: prods,
        discardedProducts: disc,
        evaluations: evals,
        canonicalQuery: cq,
        status: st,
      })

      if (prods.length > 0) {
        saveSearchSnapshot({
          query: q,
          results: prods,
          discardedProducts: disc,
          evaluations: evals,
          canonicalQuery: cq,
          status: st,
        })
        addHistoryRecord({
          source: 'search',
          query: q,
          canonicalQuery: cq,
          products: prods,
        })
      } else {
        toast('No matching products found', { icon: '🔍' })
      }
    } catch (err) {
      toast.error('Search failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const handleRestore = (s) => {
    restoreSearchSnapshot(s.id)
    toast.success(`Restored previous search: "${s.query}"`)
  }

  return (
    <div>
      {/* Search Box */}
      <div className="card" style={{ padding: '20px', marginBottom: 24 }}>
        <div className="flex gap-3" style={{ marginBottom: 14 }}>
          <div style={{ position: 'relative', flex: 1 }}>
            <Search size={16} style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input
              className="input"
              style={{ paddingLeft: 40 }}
              placeholder="e.g. Solid black t-shirt for men, oversized fit"
              value={query}
              onChange={e => setSearchState({ query: e.target.value })}
              onKeyDown={e => e.key === 'Enter' && runSearch()}
            />
          </div>
          <button className="btn btn-primary" onClick={() => runSearch()} disabled={loading || !query.trim()}>
            {loading ? <span className="spinner" /> : <><Search size={16} /> Search</>}
          </button>
        </div>

        {/* Recent Search Snapshots */}
        {searchHistory && searchHistory.length > 0 && (
          <div style={{ marginBottom: 12, paddingBottom: 10, borderBottom: '1px solid rgba(255, 255, 255, 0.07)' }}>
            <div className="flex items-center justify-between" style={{ marginBottom: 6 }}>
              <span className="text-xs text-muted" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <History size={12} color="var(--accent-purple)" />
                <strong>Recent Searches & Snapshots:</strong> (Click to restore instantly)
              </span>
              <button 
                className="btn btn-ghost btn-xs" 
                onClick={clearSearchHistory}
                style={{ fontSize: '0.7rem', color: 'var(--text-muted)', padding: '1px 6px' }}
              >
                Clear History
              </button>
            </div>
            <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
              {searchHistory.map(s => (
                <button
                  key={s.id}
                  className="chat-chip"
                  style={{ 
                    fontSize: '0.78rem',
                    background: query.toLowerCase() === s.query.toLowerCase() ? 'rgba(99, 102, 241, 0.25)' : 'rgba(255, 255, 255, 0.05)',
                    borderColor: query.toLowerCase() === s.query.toLowerCase() ? 'var(--accent-purple)' : 'rgba(255, 255, 255, 0.1)',
                  }}
                  onClick={() => handleRestore(s)}
                  title={`Restores exact ${s.resultsCount} picks from ${s.timestamp}`}
                >
                  <RotateCcw size={11} style={{ opacity: 0.7 }} />
                  <span>{s.query}</span>
                  <span className="badge badge-purple" style={{ fontSize: '0.65rem', padding: '1px 5px', marginLeft: 4 }}>
                    {s.resultsCount}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Quick Suggestion Chips */}
        <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
          <span className="text-xs text-muted" style={{ display: 'flex', alignItems: 'center', marginRight: 4 }}>
            💡 Quick Ideas:
          </span>
          {QUICK_SEARCHES.map(q => (
            <button
              key={q}
              className="chat-chip"
              onClick={() => { setSearchState({ query: q }); runSearch(q) }}
            >{q}</button>
          ))}
        </div>
      </div>

      {/* Canonical Query Badge */}
      {canonicalQuery && (
        <div className="alert alert-info" style={{ marginBottom: 16 }}>
          <Sliders size={16} />
          <span>
            <strong>Normalized Intent:</strong>{' '}
            {[
              canonicalQuery.gender && `Gender: ${canonicalQuery.gender}`,
              canonicalQuery.category && `Category: ${canonicalQuery.category}`,
              canonicalQuery.color && `Color: ${canonicalQuery.color}`,
              canonicalQuery.fit && `Fit: ${canonicalQuery.fit}`,
              canonicalQuery.design && `Design: ${canonicalQuery.design}`,
            ].filter(Boolean).join(' · ')}
          </span>
        </div>
      )}

      {/* Results */}
      {loading ? (
        <div className="loading-state">
          <div className="spinner" />
          <p>{stages[loadingStage]}</p>
        </div>
      ) : results.length > 0 ? (
        <>
          {/* Results header: status + filters + sorting + layout */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 16 }}>
            {/* Top Bar: Status + Badges + Layout */}
            <div className="flex items-center justify-between" style={{ flexWrap: 'wrap', gap: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <span className="text-sm text-muted">
                  Showing {sortedResults.length} of {results.length} products
                </span>
                {isDeliverySorted && (
                  <span style={{
                    display: 'inline-flex', alignItems: 'center', gap: 4,
                    fontSize: '0.72rem', fontWeight: 700, padding: '2px 8px',
                    borderRadius: 4, background: 'rgba(16,185,129,0.15)',
                    border: '1px solid rgba(16,185,129,0.35)', color: '#34d399'
                  }}>
                    <Truck size={11} /> Delivery-aware sort active
                  </span>
                )}
              </div>

              <div className="flex gap-2" style={{ alignItems: 'center' }}>
                {/* Sort Selector Dropdown */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span className="text-xs text-muted" style={{ fontWeight: 600 }}>Sort:</span>
                  <select 
                    className="select"
                    value={sortMode}
                    onChange={e => handleSortChange(e.target.value)}
                    disabled={calculatingLogistics}
                    style={{ padding: '4px 10px', fontSize: '0.78rem', height: 32, borderRadius: 6 }}
                  >
                    <option value="relevance">Best Match</option>
                    <option value="fastest_delivery">Fastest Delivery</option>
                    <option value="slowest_delivery">Slowest Delivery</option>
                    <option value="price_asc">Price: Low to High</option>
                    <option value="price_desc">Price: High to Low</option>
                    <option value="rating">Highest Rated</option>
                  </select>
                </div>

                <button className={`btn btn-icon btn-ghost ${layout === 'grid' ? 'active' : ''}`} onClick={() => setLayout('grid')}><Grid size={16} /></button>
                <button className={`btn btn-icon btn-ghost ${layout === 'carousel' ? 'active' : ''}`} onClick={() => setLayout('carousel')}><List size={16} /></button>
              </div>
            </div>

            {/* Quick Filter Chips Bar */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <span className="text-xs text-muted" style={{ fontWeight: 600 }}>Filters:</span>

              {/* Fast Delivery Only Chip — only shown when delivery data is active/resolved */}
              {isDeliverySorted && (
                <button
                  className="chat-chip"
                  onClick={() => setFastDeliveryOnly(!fastDeliveryOnly)}
                  style={{
                    fontSize: '0.74rem', padding: '3px 10px',
                    background: fastDeliveryOnly ? 'rgba(16,185,129,0.25)' : 'rgba(255,255,255,0.05)',
                    borderColor: fastDeliveryOnly ? '#10b981' : 'rgba(255,255,255,0.12)',
                    color: fastDeliveryOnly ? '#34d399' : '#cbd5e1'
                  }}
                >
                  Express (≤ 2 Days)
                </button>
              )}

              {/* Pre-Approved Only Chip */}
              <button
                className="chat-chip"
                onClick={() => setApprovalFilter(f => f === 'pre_approved' ? 'all' : 'pre_approved')}
                style={{
                  fontSize: '0.74rem', padding: '3px 10px',
                  background: approvalFilter === 'pre_approved' ? 'rgba(16,185,129,0.25)' : 'rgba(255,255,255,0.05)',
                  borderColor: approvalFilter === 'pre_approved' ? '#10b981' : 'rgba(255,255,255,0.12)',
                  color: approvalFilter === 'pre_approved' ? '#34d399' : '#cbd5e1'
                }}
              >
                Pre-Approved (≤ ₹{config.maxCostHitl || 800})
              </button>

              {/* Requires Approval Chip */}
              <button
                className="chat-chip"
                onClick={() => setApprovalFilter(f => f === 'requires_approval' ? 'all' : 'requires_approval')}
                style={{
                  fontSize: '0.74rem', padding: '3px 10px',
                  background: approvalFilter === 'requires_approval' ? 'rgba(239,68,68,0.25)' : 'rgba(255,255,255,0.05)',
                  borderColor: approvalFilter === 'requires_approval' ? '#ef4444' : 'rgba(255,255,255,0.12)',
                  color: approvalFilter === 'requires_approval' ? '#f87171' : '#cbd5e1'
                }}
              >
                Requires Approval (&gt; ₹{config.maxCostHitl || 800})
              </button>

              {/* 4.0+ Stars Rating Chip */}
              <button
                className="chat-chip"
                onClick={() => setMinRatingFilter(minRatingFilter === 4 ? 0 : 4)}
                style={{
                  fontSize: '0.74rem', padding: '3px 10px',
                  background: minRatingFilter === 4 ? 'rgba(251,191,36,0.2)' : 'rgba(255,255,255,0.05)',
                  borderColor: minRatingFilter === 4 ? '#fbbf24' : 'rgba(255,255,255,0.12)',
                  color: minRatingFilter === 4 ? '#fbbf24' : '#cbd5e1'
                }}
              >
                Rating 4.0+
              </button>

              {/* Reset Filters button if any active */}
              {(fastDeliveryOnly || approvalFilter !== 'all' || minRatingFilter > 0 || sortMode !== 'relevance') && (
                <button
                  className="btn btn-ghost btn-xs"
                  onClick={() => {
                    setFastDeliveryOnly(false)
                    setApprovalFilter('all')
                    setMinRatingFilter(0)
                    setSortMode('relevance')
                  }}
                  style={{ fontSize: '0.7rem', color: '#f87171', padding: '2px 6px' }}
                >
                  Reset All Filters
                </button>
              )}
            </div>
          </div>

          {sortedResults.length === 0 ? (
            <div className="card" style={{ padding: '32px 20px', textAlign: 'center', marginTop: 12 }}>
              <p className="text-sm text-muted" style={{ marginBottom: 12 }}>
                No products match the selected filters ({results.length} total items found).
              </p>
              <button
                className="btn btn-outline btn-sm"
                onClick={() => {
                  setFastDeliveryOnly(false)
                  setApprovalFilter('all')
                  setMinRatingFilter(0)
                  setSortMode('relevance')
                }}
              >
                Clear Filters
              </button>
            </div>
          ) : (
            <BatchedProductGrid 
              products={sortedResults.slice((currentPage - 1) * pageSize, currentPage * pageSize)} 
              onAddToCart={onAddToCart} 
              layout={layout === 'carousel' ? 'carousel' : 'grid'}
              batchSize={4}
              batchDelay={120}
            />
          )}

          {/* Pagination */}
          {sortedResults.length > pageSize && (
            <div className="flex items-center justify-center gap-4" style={{ marginTop: 24 }}>
              <button 
                className="btn btn-outline" 
                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                disabled={currentPage === 1}
              >
                <ChevronLeft size={16} /> Previous
              </button>
              <span className="text-sm text-muted">Page {currentPage} of {Math.ceil(sortedResults.length / pageSize)}</span>
              <button 
                className="btn btn-outline" 
                onClick={() => setCurrentPage(p => Math.min(Math.ceil(sortedResults.length / pageSize), p + 1))}
                disabled={currentPage === Math.ceil(sortedResults.length / pageSize)}
              >
                Next <ChevronRight size={16} />
              </button>
            </div>
          )}
        </>
      ) : status ? (
        <div className="empty-state">
          <div className="empty-state-icon">🔍</div>
          <h3>No Results</h3>
          <p>{status}</p>
        </div>
      ) : null}

      {/* Debug Accordions */}
      {!loading && canonicalQuery && (
        <div style={{ marginTop: 40, borderTop: '1px solid var(--border)', paddingTop: 20 }}>
          
          <button 
            className="flex items-center justify-between w-full" 
            style={{ padding: '12px', background: 'var(--surface)', borderRadius: 8, marginBottom: 12, border: '1px solid var(--border)', cursor: 'pointer' }}
            onClick={() => setShowEval(!showEval)}
          >
            <div className="flex items-center gap-2">
              <Search size={16} color="var(--accent-blue)" />
              <strong>Inspect Raw Canonical Query & Evaluations</strong>
            </div>
            {showEval ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
          {showEval && (
            <div className="card" style={{ padding: 16, marginBottom: 20, fontSize: '13px' }}>
              <h4 style={{ margin: '0 0 10px 0' }}>Canonical Query Object:</h4>
              <pre style={{ background: 'var(--bg)', padding: 12, borderRadius: 4, overflowX: 'auto' }}>
                {JSON.stringify(canonicalQuery, null, 2)}
              </pre>
              
              <h4 style={{ margin: '20px 0 10px 0' }}>LLM Evaluations ({evaluations.length}):</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {evaluations.map((e, i) => (
                  <div key={i} style={{ padding: 8, background: 'var(--bg)', borderRadius: 4, borderLeft: e.match_score >= 0.8 ? '3px solid var(--accent-green)' : (e.match_score >= 0.5 ? '3px solid var(--accent-orange)' : '3px solid var(--accent-red)') }}>
                    <strong>{e.product_id}</strong> (Score: {e.match_score})<br/>
                    <span className="text-muted">{e.reasoning}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <button 
            className="flex items-center justify-between w-full" 
            style={{ padding: '12px', background: 'var(--surface)', borderRadius: 8, marginBottom: 12, border: '1px solid var(--border)', cursor: 'pointer' }}
            onClick={() => setShowDiscarded(!showDiscarded)}
          >
            <div className="flex items-center gap-2">
              <Trash2 size={16} color="var(--accent-red)" />
              <strong>View Discarded / Low Relevance Candidates ({discardedProducts.length})</strong>
            </div>
            {showDiscarded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
          {showDiscarded && (
            <div className="product-grid" style={{ opacity: 0.6 }}>
              {discardedProducts.map(p => <ProductCard key={p.id} product={p} onAddToCart={onAddToCart} />)}
            </div>
          )}

        </div>
      )}
    </div>
  )
}
