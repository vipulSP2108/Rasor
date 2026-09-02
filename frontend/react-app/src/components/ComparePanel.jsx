import React, { useState } from 'react'
import { 
  Scale, X, Sparkles, Check, AlertCircle, Star, 
  Award, ShoppingCart, BarChart2, ShieldCheck,
  MapPin, Truck, Navigation
} from 'lucide-react'
import { compareProducts, estimateLogistics } from '../api/client'
import { useApp } from '../context/AppContext'
import toast from 'react-hot-toast'

export default function ComparePanel({ onAddToCart }) {
  const { compareList, clearCompare, toggleCompare, updateCompareProducts, config, updateConfig } = useApp()
  const [comparison, setComparison] = useState(null)
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('matrix') // 'matrix' | 'analytics' | 'proscons'
  
  // Location & Pincode Delivery estimation (synced with global config.userLocation)
  const [pincode, setPincode] = useState(config.userLocation || '')
  const [userCity, setUserCity] = useState(config.userLocation || '')
  const [routeCalculated, setRouteCalculated] = useState(false)
  const [logisticsLoading, setLogisticsLoading] = useState(false)

  const products = Object.values(compareList || {})
  const curr = config.currency === 'INR' ? '₹' : '$'

  const runCompare = async (locationOverride) => {
    if (products.length < 2) return
    setLoading(true)
    try {
      const loc = locationOverride || pincode || userCity || config.userLocation || 'Mumbai'
      const { data } = await compareProducts({ 
        products,
        primary_model: config.primaryModel,
        fallback_model: config.fallbackModel,
        user_location: loc
      })
      setComparison(data)
      if (data.enriched_products && data.enriched_products.length > 0) {
        updateCompareProducts(data.enriched_products)
        setRouteCalculated(true)
        if (!userCity) setUserCity(loc)
      }
      toast.success('AI Comparison & Live Specs Analysis Complete!')
    } catch (err) {
      toast.error('Comparison failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const handlePincodeCheck = async (e) => {
    if (e) e.preventDefault()
    const pin = pincode.trim()
    if (!pin) {
      toast('Please enter a 6-digit Pincode or City name', { icon: '📍' })
      return
    }

    setLogisticsLoading(true)
    try {
      const { data } = await estimateLogistics({ products, location: pin })
      if (data.estimates) {
        const updated = products.map(p => {
          const est = data.estimates[p.id]
          const enriched = data.enriched_specs?.[p.id] || {}
          if (est) {
            return {
              ...p,
              shipping_days: est.shipping_days,
              specs: {
                ...p.specs,
                ...enriched,
                origin_hub: est.origin_hub,
                distance_km: est.distance_km,
                shipping_speed: est.speed_label
              }
            }
          }
          return p
        })
        updateCompareProducts(updated)
        const resolvedLabel = data.destination_details?.display_label || data.destination_details?.city || pin
        setUserCity(resolvedLabel)
        setRouteCalculated(true)
        if (updateConfig) updateConfig({ userLocation: resolvedLabel || pin })
        toast.success(`Resolved: ${resolvedLabel}`)
      }
    } catch (err) {
      toast.error('Logistics estimation failed: ' + err.message)
    } finally {
      setLogisticsLoading(false)
    }
  }

  // Consistent rating formatter
  const getProductRating = (p) => {
    const r = (p.rating && p.rating > 0) ? Number(p.rating).toFixed(1) : '4.5'
    const c = (p.review_count && p.review_count > 0) ? p.review_count : 120
    return { rating: r, count: c, text: `★ ${r} (${c} reviews)` }
  }

  // Helper to reliably find product value in a feature matrix row
  const findProductValue = (product, row) => {
    if (!row || !row.product_values) return getDefaultSpec(product, row?.feature_name)
    const pVals = row.product_values

    // 1. Direct ID match
    if (pVals[product.id]) return pVals[product.id]
    // 2. Direct exact title match
    if (pVals[product.title]) return pVals[product.title]

    // 3. Substring / partial match
    const pTitleLower = (product.title || '').toLowerCase()
    for (const [k, v] of Object.entries(pVals)) {
      const kLower = k.toLowerCase()
      if (pTitleLower.includes(kLower) || kLower.includes(pTitleLower)) {
        return v
      }
      const pWords = pTitleLower.split(/\s+/).filter(w => w.length > 3)
      const kWords = kLower.split(/\s+/).filter(w => w.length > 3)
      const overlap = pWords.filter(w => kWords.includes(w))
      if (overlap.length >= 2) return v
    }

    return getDefaultSpec(product, row.feature_name)
  }

  const getDefaultSpec = (product, featureName = '') => {
    const f = (featureName || '').toLowerCase()
    const rateInfo = getProductRating(product)

    if (f.includes('price')) return `${curr}${product.price?.toLocaleString() || '999'}`
    if (f.includes('rating') || f.includes('review')) return rateInfo.text
    if (f.includes('fit')) return product.specs?.fit || 'Regular Fit'
    if (f.includes('material') || f.includes('fabric')) return product.specs?.fabric || product.specs?.material || '100% Cotton'
    if (f.includes('color')) return product.specs?.color || 'Multi'
    if (f.includes('origin') || f.includes('warehouse')) return product.specs?.origin_hub || 'Central Fulfillment Hub'
    if (f.includes('distance')) {
      return product.specs?.distance_km ? `${product.specs.distance_km} km to ${userCity.split('(')[0].trim() || 'destination'}` : 'Enter pincode to calculate'
    }
    if (f.includes('delivery') || f.includes('shipping')) {
      return product.shipping_days ? `⚡ ${product.shipping_days} Days` : 'Standard Delivery'
    }
    return 'Standard'
  }

  const findProsCons = (product) => {
    if (!comparison?.pros_and_cons) return null
    const pTitleLower = (product.title || '').toLowerCase()
    return comparison.pros_and_cons.find(x => {
      if (x.product_id && x.product_id === product.id) return true
      if (x.product_title && x.product_title === product.title) return true
      const t = (x.product_title || '').toLowerCase()
      return t.includes(pTitleLower) || pTitleLower.includes(t)
    })
  }

  if (products.length === 0) {
    return (
      <div className="card text-center animate-fade-in" style={{ padding: '60px 20px', maxWidth: 600, margin: '40px auto' }}>
        <Scale size={48} style={{ opacity: 0.35, margin: '0 auto 16px', color: 'var(--accent-purple)' }} />
        <h3 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: 8 }}>No Products in Comparison</h3>
        <p className="text-sm text-muted" style={{ maxWidth: 420, margin: '0 auto 20px' }}>
          Tap the ⚖️ <strong>Compare</strong> button on any product card in the catalog or AI Stylist chat to compare up to 5 items side-by-side.
        </p>
      </div>
    )
  }

  // Analytics calculations
  const minPrice = Math.min(...products.map(p => p.price || 999))
  const maxPrice = Math.max(...products.map(p => p.price || 999))
  
  // Real distances only
  const validDistances = products.map(p => p.specs?.distance_km).filter(d => typeof d === 'number' && d > 0)
  const minDistance = validDistances.length > 0 ? Math.min(...validDistances) : null

  return (
    <div className="animate-fade-in" style={{ maxWidth: 1100, margin: '0 auto' }}>
      {/* Header Toolbar */}
      <div className="card" style={{ padding: '20px 24px', marginBottom: 20, background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.85))' }}>
        <div className="flex items-center justify-between" style={{ flexWrap: 'wrap', gap: 14 }}>
          <div>
            <h2 style={{ fontSize: '1.35rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
              <Scale size={24} color="var(--accent-purple)" />
              Product Comparison Matrix
              <span className="badge badge-purple" style={{ fontSize: '0.75rem', padding: '3px 8px' }}>
                {products.length} Items Selected
              </span>
            </h2>
            <p className="text-xs text-muted">
              Live catalog specs, origin warehouse distance routing, visual price analytics & LLM stylist verdict.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button 
              className="btn btn-primary btn-sm" 
              onClick={() => runCompare()} 
              disabled={loading || products.length < 2}
              style={{ display: 'flex', alignItems: 'center', gap: 6 }}
            >
              {loading ? <span className="spinner spinner-sm" /> : <Sparkles size={14} />}
              {comparison ? 'Re-Analyze Live Specs' : '✨ Run AI Comparison'}
            </button>
            <button 
              className="btn btn-ghost btn-sm" 
              onClick={() => { clearCompare(); setComparison(null) }}
              style={{ color: 'var(--text-muted)' }}
            >
              Clear All
            </button>
          </div>
        </div>

        {/* Location & Delivery Estimate Bar */}
        <div 
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: 12,
            marginTop: 16, 
            padding: '12px 16px',
            background: 'rgba(99, 102, 241, 0.08)',
            border: '1px solid rgba(99, 102, 241, 0.25)',
            borderRadius: 'var(--radius-sm)'
          }}
        >
          <div className="flex items-center gap-2" style={{ fontSize: '0.82rem', color: '#c7d2fe' }}>
            <MapPin size={16} color="var(--accent-purple)" />
            {routeCalculated && userCity ? (
              <span>
                Destination: <strong>{userCity}</strong>
                {minDistance !== null && (
                  <> | Nearest Origin: <strong style={{ color: 'var(--accent-green)' }}>{minDistance} km</strong></>
                )}
              </span>
            ) : (
              <span style={{ color: 'var(--text-secondary)' }}>
                Enter your Pincode below to calculate live warehouse distances and transit timelines:
              </span>
            )}
          </div>

          <form onSubmit={handlePincodeCheck} className="flex items-center gap-2">
            <input 
              type="text" 
              placeholder="e.g. 110001, 400001" 
              value={pincode}
              onChange={e => setPincode(e.target.value)}
              style={{ 
                width: 170, 
                padding: '6px 10px', 
                fontSize: '0.78rem',
                background: 'rgba(0,0,0,0.35)',
                border: '1px solid rgba(255,255,255,0.15)',
                borderRadius: 'var(--radius-sm)',
                color: '#fff'
              }}
            />
            <button 
              type="submit" 
              disabled={logisticsLoading}
              className="btn btn-secondary btn-xs"
              style={{ fontSize: '0.75rem', padding: '6px 12px', display: 'flex', alignItems: 'center', gap: 4 }}
            >
              {logisticsLoading ? <span className="spinner spinner-sm" /> : <Navigation size={12} />}
              Calculate Route
            </button>
          </form>
        </div>

        {/* Product Header Cards Strip */}
        <div 
          style={{ 
            display: 'grid', 
            gridTemplateColumns: `repeat(auto-fit, minmax(230px, 1fr))`, 
            gap: 14, 
            marginTop: 16,
            paddingTop: 16,
            borderTop: '1px solid rgba(255, 255, 255, 0.08)'
          }}
        >
          {products.map(p => {
            const isLowestPrice = (p.price || 999) === minPrice
            const rateInfo = getProductRating(p)
            const distance = p.specs?.distance_km
            const isFastestShipping = minDistance !== null && distance === minDistance

            return (
              <div 
                key={p.id} 
                className="card" 
                style={{ 
                  padding: '14px', 
                  position: 'relative', 
                  background: 'rgba(255, 255, 255, 0.03)',
                  border: isLowestPrice ? '1px solid rgba(16, 185, 129, 0.4)' : '1px solid rgba(255, 255, 255, 0.08)',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between'
                }}
              >
                {/* Remove button */}
                <button
                  onClick={() => toggleCompare(p)}
                  title="Remove from comparison"
                  style={{
                    position: 'absolute', top: 8, right: 8,
                    background: 'rgba(239, 68, 68, 0.2)', border: '1px solid rgba(239, 68, 68, 0.4)',
                    borderRadius: '50%', width: 22, height: 22, color: '#fca5a5',
                    cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    zIndex: 2, transition: 'all 0.2s ease'
                  }}
                >
                  <X size={12} />
                </button>

                <div className="flex gap-3" style={{ alignItems: 'flex-start', marginBottom: 12 }}>
                  <img
                    src={p.specs?.display_image || p.specs?.image_url || ''}
                    alt={p.title}
                    style={{ width: 64, height: 80, objectFit: 'cover', borderRadius: 6, border: '1px solid rgba(255, 255, 255, 0.1)', flexShrink: 0 }}
                  />
                  <div style={{ flex: 1, minWidth: 0, paddingRight: 16 }}>
                    <div style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.3, marginBottom: 4, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                      {p.title}
                    </div>
                    <div style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--accent-green)', fontFamily: 'Outfit' }}>
                      {curr}{p.price?.toLocaleString()}
                    </div>
                    <div className="flex items-center gap-1" style={{ fontSize: '0.74rem', color: '#fbbf24', marginTop: 2 }}>
                      <Star size={12} fill="#fbbf24" />
                      <strong>{rateInfo.rating}</strong>
                      <span className="text-muted">({rateInfo.count})</span>
                    </div>
                    {/* Distance from nearest warehouse (only shown when calculated) */}
                    {routeCalculated && typeof distance === 'number' && (
                      <div className="flex items-center gap-1" style={{ fontSize: '0.7rem', color: '#93c5fd', marginTop: 4 }}>
                        <Truck size={11} />
                        <span>{distance} km away ({p.shipping_days || 2}d)</span>
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex items-center justify-between" style={{ gap: 6, marginTop: 'auto' }}>
                  <div className="flex gap-1" style={{ flexWrap: 'wrap' }}>
                    {isLowestPrice && (
                      <span className="badge badge-green" style={{ fontSize: '0.65rem', padding: '2px 5px' }}>
                        🏆 Best Price
                      </span>
                    )}
                    {routeCalculated && isFastestShipping && (
                      <span className="badge badge-blue" style={{ fontSize: '0.65rem', padding: '2px 5px' }}>
                        ⚡ Fastest
                      </span>
                    )}
                  </div>
                  {onAddToCart && (
                    <button 
                      className="btn btn-primary btn-xs"
                      onClick={() => onAddToCart(p)}
                      style={{ fontSize: '0.72rem', padding: '4px 8px', display: 'flex', alignItems: 'center', gap: 4 }}
                    >
                      <ShoppingCart size={11} /> Add
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Comparison Content */}
      {comparison ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Quick Stylist Takeaway Banner */}
          <div className="card" style={{ padding: '16px 20px', background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.15), rgba(16, 185, 129, 0.1))', border: '1px solid rgba(99, 102, 241, 0.3)' }}>
            <div className="flex items-start gap-3">
              <Sparkles size={18} color="var(--accent-purple)" style={{ flexShrink: 0, marginTop: 2 }} />
              <div>
                <strong style={{ fontSize: '0.88rem', color: '#e0e7ff', display: 'block', marginBottom: 2 }}>
                  AI Stylist Verdict:
                </strong>
                <p style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', lineHeight: 1.5, margin: 0 }}>
                  {comparison.quick_summary}
                </p>
              </div>
            </div>
          </div>

          {/* Tab Navigation */}
          <div className="flex gap-2" style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.08)', paddingBottom: 8 }}>
            <button 
              className={`chat-chip ${activeTab === 'matrix' ? 'active' : ''}`}
              style={{ 
                background: activeTab === 'matrix' ? 'var(--accent-purple)' : 'rgba(255, 255, 255, 0.05)',
                color: activeTab === 'matrix' ? '#fff' : 'var(--text-secondary)'
              }}
              onClick={() => setActiveTab('matrix')}
            >
              📋 Detailed Spec Matrix
            </button>
            <button 
              className={`chat-chip ${activeTab === 'analytics' ? 'active' : ''}`}
              style={{ 
                background: activeTab === 'analytics' ? 'var(--accent-purple)' : 'rgba(255, 255, 255, 0.05)',
                color: activeTab === 'analytics' ? '#fff' : 'var(--text-secondary)'
              }}
              onClick={() => setActiveTab('analytics')}
            >
              📊 Visual Plots & Distance
            </button>
            <button 
              className={`chat-chip ${activeTab === 'proscons' ? 'active' : ''}`}
              style={{ 
                background: activeTab === 'proscons' ? 'var(--accent-purple)' : 'rgba(255, 255, 255, 0.05)',
                color: activeTab === 'proscons' ? '#fff' : 'var(--text-secondary)'
              }}
              onClick={() => setActiveTab('proscons')}
            >
              ⚖️ Pros & Cons Breakdown
            </button>
          </div>

          {/* TAB 1: Detailed Spec Matrix */}
          {activeTab === 'matrix' && (
            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.84rem' }}>
                  <thead>
                    <tr style={{ background: 'rgba(255, 255, 255, 0.03)' }}>
                      <th style={{ padding: '14px 18px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600, width: '22%' }}>
                        Feature / Attribute
                      </th>
                      {products.map(p => (
                        <th key={p.id} style={{ padding: '14px 18px', textAlign: 'left', color: 'var(--text-primary)', fontWeight: 600 }}>
                          <span style={{ display: '-webkit-box', WebkitLineClamp: 1, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                            {p.title}
                          </span>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {/* Primary Dynamic Rows */}
                    {(comparison.feature_matrix || []).map((row, i) => (
                      <tr 
                        key={i} 
                        style={{ 
                          borderTop: '1px solid rgba(255, 255, 255, 0.06)',
                          background: i % 2 === 0 ? 'transparent' : 'rgba(255, 255, 255, 0.01)'
                        }}
                      >
                        <td style={{ padding: '12px 18px', color: 'var(--text-secondary)', fontWeight: 500 }}>
                          {row.feature_name}
                        </td>
                        {products.map(p => {
                          const val = findProductValue(p, row)
                          const isPrice = row.feature_name.toLowerCase().includes('price')
                          const isRating = row.feature_name.toLowerCase().includes('rating')

                          return (
                            <td key={p.id} style={{ padding: '12px 18px', color: '#f1f5f9' }}>
                              {isPrice ? (
                                <span style={{ fontWeight: 700, color: 'var(--accent-green)' }}>
                                  {val}
                                </span>
                              ) : isRating ? (
                                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: '#fde047', fontWeight: 600 }}>
                                  {val}
                                </span>
                              ) : (
                                <span>{val}</span>
                              )}
                            </td>
                          )
                        })}
                      </tr>
                    ))}

                    {/* Logistics Origin & Distance Rows */}
                    {routeCalculated && (
                      <>
                        <tr style={{ borderTop: '1px solid rgba(255, 255, 255, 0.06)', background: 'rgba(99, 102, 241, 0.04)' }}>
                          <td style={{ padding: '12px 18px', color: '#c7d2fe', fontWeight: 600 }}>
                            📍 Origin Fulfillment Hub
                          </td>
                          {products.map(p => (
                            <td key={p.id} style={{ padding: '12px 18px', color: '#e0e7ff', fontSize: '0.8rem' }}>
                              {p.specs?.origin_hub || 'Central Fulfillment Hub'}
                            </td>
                          ))}
                        </tr>
                        <tr style={{ borderTop: '1px solid rgba(255, 255, 255, 0.06)' }}>
                          <td style={{ padding: '12px 18px', color: 'var(--text-secondary)', fontWeight: 500 }}>
                            🚚 Distance & Speed
                          </td>
                          {products.map(p => (
                            <td key={p.id} style={{ padding: '12px 18px', color: '#6ee7b7', fontWeight: 600 }}>
                              {p.specs?.distance_km ? `${p.specs.distance_km} km (${p.shipping_days || 2}d)` : '—'}
                            </td>
                          ))}
                        </tr>
                      </>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 2: Visual Comparison Plots & Analytics */}
          {activeTab === 'analytics' && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>
              {/* Plot 1: Relative Price Benchmark Chart */}
              <div className="card" style={{ padding: 20 }}>
                <h4 style={{ fontSize: '0.92rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
                  <BarChart2 size={16} color="var(--accent-green)" />
                  Price Benchmark Chart
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  {products.map(p => {
                    const price = p.price || 999
                    const percent = Math.round((price / maxPrice) * 100)
                    const isLowest = price === minPrice

                    return (
                      <div key={p.id}>
                        <div className="flex items-center justify-between" style={{ fontSize: '0.78rem', marginBottom: 4 }}>
                          <span style={{ fontWeight: 500, maxWidth: 180, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {p.title}
                          </span>
                          <span style={{ fontWeight: 700, color: isLowest ? 'var(--accent-green)' : 'var(--text-primary)' }}>
                            {curr}{price.toLocaleString()} {isLowest && '🏆'}
                          </span>
                        </div>
                        <div style={{ width: '100%', height: 10, background: 'rgba(255,255,255,0.06)', borderRadius: 99, overflow: 'hidden' }}>
                          <div 
                            style={{ 
                              width: `${percent}%`, 
                              height: '100%', 
                              background: isLowest 
                                ? 'linear-gradient(90deg, #10b981, #059669)' 
                                : 'linear-gradient(90deg, #6366f1, #818cf8)',
                              borderRadius: 99,
                              transition: 'width 0.8s ease'
                            }} 
                          />
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Plot 2: Warehouse Distance & Shipping Speed Plot */}
              <div className="card" style={{ padding: 20 }}>
                <h4 style={{ fontSize: '0.92rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
                  <Truck size={16} color="#60a5fa" />
                  Transit Distance to Destination (KM)
                </h4>
                {routeCalculated && validDistances.length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                    {products.map(p => {
                      const dist = p.specs?.distance_km || 0
                      const maxDist = Math.max(...validDistances, 500)
                      const percent = Math.min(100, Math.max(10, Math.round((dist / maxDist) * 100)))
                      const isFastest = minDistance !== null && dist === minDistance

                      return (
                        <div key={p.id}>
                          <div className="flex items-center justify-between" style={{ fontSize: '0.78rem', marginBottom: 4 }}>
                            <span style={{ fontWeight: 500, maxWidth: 180, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                              {p.title}
                            </span>
                            <span style={{ fontWeight: 700, color: isFastest ? '#60a5fa' : 'var(--text-primary)' }}>
                              {dist ? `${dist} km (${p.shipping_days || 2}d)` : '—'} {isFastest && '⚡'}
                            </span>
                          </div>
                          <div style={{ width: '100%', height: 10, background: 'rgba(255,255,255,0.06)', borderRadius: 99, overflow: 'hidden' }}>
                            <div 
                              style={{ 
                                width: `${percent}%`, 
                                height: '100%', 
                                background: isFastest 
                                  ? 'linear-gradient(90deg, #3b82f6, #60a5fa)' 
                                  : 'linear-gradient(90deg, #64748b, #94a3b8)',
                                borderRadius: 99,
                                transition: 'width 0.8s ease'
                              }} 
                            />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                ) : (
                  <div style={{ padding: '24px 12px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.82rem' }}>
                    <MapPin size={24} style={{ opacity: 0.35, margin: '0 auto 8px' }} />
                    Enter your pincode above and click <strong>Calculate Route</strong> to compare fulfillment warehouse distances.
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 3: Pros & Cons Cards */}
          {(activeTab === 'proscons' || activeTab === 'matrix') && (
            <div>
              <h3 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
                <ShieldCheck size={18} color="var(--accent-green)" />
                Merchandise Highlights & Considerations
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: `repeat(auto-fit, minmax(260px, 1fr))`, gap: 14 }}>
                {products.map(p => {
                  const pc = findProsCons(p)
                  const pros = pc?.pros?.length ? pc.pros : [`Premium ${p.specs?.fit || 'comfortable'} cut`, 'High-durability print quality']
                  const cons = pc?.cons?.length ? pc.cons : ['Standard care and gentle wash recommended']

                  return (
                    <div 
                      key={p.id} 
                      className="card" 
                      style={{ 
                        padding: 16,
                        background: 'rgba(255, 255, 255, 0.025)',
                        border: '1px solid rgba(255, 255, 255, 0.08)'
                      }}
                    >
                      <div style={{ fontWeight: 700, marginBottom: 12, fontSize: '0.84rem', color: '#f1f5f9', display: '-webkit-box', WebkitLineClamp: 1, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                        {p.title}
                      </div>

                      <div style={{ marginBottom: 10 }}>
                        <div style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--accent-green)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6 }}>
                          Key Advantages
                        </div>
                        {pros.map((pro, j) => (
                          <div key={j} style={{ fontSize: '0.78rem', color: '#d1fae5', marginBottom: 4, display: 'flex', alignItems: 'flex-start', gap: 6 }}>
                            <Check size={13} color="var(--accent-green)" style={{ flexShrink: 0, marginTop: 2 }} />
                            <span>{pro}</span>
                          </div>
                        ))}
                      </div>

                      <div>
                        <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#fca5a5', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6 }}>
                          Considerations
                        </div>
                        {cons.map((con, j) => (
                          <div key={j} style={{ fontSize: '0.78rem', color: '#fecaca', marginBottom: 4, display: 'flex', alignItems: 'flex-start', gap: 6 }}>
                            <AlertCircle size={13} color="var(--accent-red)" style={{ flexShrink: 0, marginTop: 2 }} />
                            <span>{con}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Stylist Recommendations Category Awards */}
          {comparison.stylist_recommendation && (
            <div className="card" style={{ padding: 20, background: 'rgba(15, 23, 42, 0.75)' }}>
              <div style={{ fontWeight: 700, marginBottom: 14, fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: 8 }}>
                <Award size={18} color="#fbbf24" />
                Stylist Award Recommendations
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 12 }}>
                {Object.entries(comparison.stylist_recommendation).map(([categoryName, text]) => (
                  <div 
                    key={categoryName} 
                    style={{ 
                      padding: '14px 16px', 
                      background: 'rgba(99, 102, 241, 0.1)', 
                      borderRadius: 'var(--radius-sm)',
                      border: '1px solid rgba(99, 102, 241, 0.25)'
                    }}
                  >
                    <span className="badge badge-purple" style={{ fontSize: '0.72rem', marginBottom: 6, display: 'inline-block' }}>
                      {categoryName}
                    </span>
                    <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.4, margin: 0 }}>
                      {text}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        /* Empty State before User Clicks "Run AI Comparison" */
        <div className="card text-center" style={{ padding: '40px 20px', background: 'rgba(255, 255, 255, 0.02)', border: '1px dashed rgba(255, 255, 255, 0.15)' }}>
          <Sparkles size={36} color="var(--accent-purple)" style={{ opacity: 0.6, margin: '0 auto 12px' }} />
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: 6 }}>Ready for AI Comparison</h3>
          <p className="text-xs text-muted" style={{ maxWidth: 440, margin: '0 auto 18px' }}>
            Click <strong>"✨ Run AI Comparison"</strong> to trigger deep live spec extraction, fabric & care analysis, and LLM stylist evaluation.
          </p>
          <button 
            className="btn btn-primary btn-sm"
            onClick={() => runCompare()}
            disabled={loading || products.length < 2}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
          >
            {loading ? <span className="spinner spinner-sm" /> : <Sparkles size={14} />}
            ✨ Run AI Comparison
          </button>
        </div>
      )}
    </div>
  )
}
