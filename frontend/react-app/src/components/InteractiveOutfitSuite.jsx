import React, { useState, useEffect } from 'react'
import { 
  Sparkles, ShoppingBag, Zap, Check, ArrowRight, RefreshCw, 
  Maximize2, X, ChevronDown, ChevronUp, Tag, Info, AlertTriangle, 
  Sliders, Eye, Plus, CheckCircle2, ShieldCheck
} from 'lucide-react'
import { useApp } from '../context/AppContext'
import toast from 'react-hot-toast'

export function getProductImageUrl(item, fallbackType = 'top') {
  if (!item) {
    return fallbackType === 'top'
      ? 'https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=800&q=80'
      : 'https://images.unsplash.com/photo-1542272604-780c96856592?auto=format&fit=crop&w=800&q=80'
  }

  const candidates = [
    item.image_url,
    item.images?.[0],
    item.specs?.image_url,
    item.specs?.display_image,
    item.specs?.images?.[0],
    item.thumb,
    item.image,
    item.source_url
  ]

  for (const c of candidates) {
    if (c && typeof c === 'string' && (c.startsWith('http') || c.startsWith('data:') || c.startsWith('/'))) {
      return c
    }
  }

  const cat = (item.category || item.specs?.subclass || item.title || '').toLowerCase()
  if (cat.includes('hoodie') || cat.includes('sweatshirt')) {
    return 'https://images.unsplash.com/photo-1556905055-8f358a7a47b2?auto=format&fit=crop&w=800&q=80'
  }
  if (cat.includes('jogger') || cat.includes('sweatpant') || cat.includes('cargo')) {
    return 'https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?auto=format&fit=crop&w=800&q=80'
  }
  if (cat.includes('jean') || cat.includes('denim')) {
    return 'https://images.unsplash.com/photo-1542272604-780c96856592?auto=format&fit=crop&w=800&q=80'
  }
  if (cat.includes('jacket')) {
    return 'https://images.unsplash.com/photo-1551028719-00167b16eac5?auto=format&fit=crop&w=800&q=80'
  }
  if (cat.includes('shoe') || cat.includes('sneaker') || cat.includes('slider') || cat.includes('footwear')) {
    return 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=800&q=80'
  }
  if (cat.includes('t-shirt') || cat.includes('tee') || cat.includes('shirt') || fallbackType === 'top') {
    return 'https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=800&q=80'
  }
  return 'https://images.unsplash.com/photo-1542272604-780c96856592?auto=format&fit=crop&w=800&q=80'
}

export default function InteractiveOutfitSuite({
  bundleData,
  mode = 'bundle',
  ownedItem = null,
  onAddToCart,
  onAutonomousCheckout,
  onFollowUp,
  onSelectAlternative
}) {
  const { addToCartLocal } = useApp()

  // ---------------------------------------------------------------------------
  // Low Budget Fallback State ($P_min)
  // ---------------------------------------------------------------------------
  if (mode === 'budget_too_low' || bundleData?.status === 'budget_too_low') {
    const altData = bundleData?.alternatives
    return (
      <div className="interactive-suite-container low-budget-card animate-fade">
        <div className="suite-header-bar">
          <div className="suite-badge-pill warning">
            <AlertTriangle size={15} />
            <span>Budget Constraint Guidance</span>
          </div>
          <span className="suite-budget-req">
            Store Minimum: ₹{bundleData?.min_total_required || altData?.min_total || '998'}
          </span>
        </div>

        <p className="suite-rationale-text text-secondary" style={{ marginTop: 10, fontSize: '0.92rem', lineHeight: 1.55 }}>
          {altData?.message || "With your current budget, coordinating both pieces exceeds the lowest available catalog prices."}
        </p>

        {altData?.options && (
          <div className="budget-alternatives-list" style={{ marginTop: 16 }}>
            <span className="budget-alt-heading">
              💡 Suggested Stylist Adjustments:
            </span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 10 }}>
              {altData.options.map((opt, idx) => (
                <button
                  key={idx}
                  type="button"
                  className="budget-option-pill"
                  onClick={() => {
                    if (onSelectAlternative) {
                      onSelectAlternative(opt, idx)
                    } else if (onFollowUp) {
                      onFollowUp(opt)
                    }
                  }}
                >
                  <ArrowRight size={14} style={{ color: 'var(--accent-amber)', flexShrink: 0 }} />
                  <span>{opt}</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    )
  }

  // ---------------------------------------------------------------------------
  // Match My Outfit Mode (Item A Constant Anchor)
  // ---------------------------------------------------------------------------
  if (mode === 'match_my_outfit' || bundleData?.mode === 'match_my_outfit') {
    return <MatchMyOutfitView 
      bundleData={bundleData} 
      ownedItem={ownedItem} 
      onAddToCart={onAddToCart}
      onAutonomousCheckout={onAutonomousCheckout}
      onFollowUp={onFollowUp}
    />
  }

  // ---------------------------------------------------------------------------
  // Multi-Item Bundle Mode (Both Non-Constant with Combos & Swapping)
  // ---------------------------------------------------------------------------
  return <MultiBundleCoordinatorView 
    bundleData={bundleData}
    onAddToCart={onAddToCart}
    onAutonomousCheckout={onAutonomousCheckout}
    onFollowUp={onFollowUp}
  />
}

// =============================================================================
// SUB-VIEW 1: Multi-Item Bundle Coordinator (Combos, Swapping, Size, Inspection)
// =============================================================================
function MultiBundleCoordinatorView({ bundleData, onAddToCart, onAutonomousCheckout, onFollowUp }) {
  const { addToCartLocal } = useApp()

  // Build combos array from server or fallbacks
  const combos = React.useMemo(() => {
    if (bundleData?.combos && bundleData.combos.length > 0) {
      return bundleData.combos
    }
    const list = []
    if (bundleData?.hero_bundle) {
      list.push({
        id: 'combo-1',
        name: 'Combo 1: Hero Coordinated',
        badge: 'Top Stylist Match',
        tagline: 'Optimal Aesthetic Harmony',
        bundle: bundleData.hero_bundle
      })
    }
    if (bundleData?.alternative_bundle && bundleData.alternative_bundle !== bundleData.hero_bundle) {
      list.push({
        id: 'combo-2',
        name: 'Combo 2: High Contrast',
        badge: 'Streetwear Alternative',
        tagline: 'Distinct Silhouette & Tone',
        bundle: bundleData.alternative_bundle
      })
    }
    if (bundleData?.value_bundle && bundleData.value_bundle !== bundleData.hero_bundle && bundleData.value_bundle !== bundleData.alternative_bundle) {
      list.push({
        id: 'combo-3',
        name: 'Combo 3: Best Value',
        badge: 'Budget Maximizer',
        tagline: `Save ₹${Math.round(bundleData.value_bundle.budget_savings || 0)} under budget`,
        bundle: bundleData.value_bundle
      })
    }
    return list
  }, [bundleData])

  const [selectedComboIdx, setSelectedComboIdx] = useState(0)
  const activeBundle = combos[selectedComboIdx]?.bundle || bundleData?.hero_bundle || bundleData

  const initialTop = activeBundle?.items?.[0] || null
  const initialBottom = activeBundle?.items?.[1] || null

  // Active items currently in the visual slot (can be customized via swap)
  const [activeTop, setActiveTop] = useState(initialTop)
  const [activeBottom, setActiveBottom] = useState(initialBottom)

  // Size selections
  const [topSize, setTopSize] = useState('M')
  const [bottomSize, setBottomSize] = useState('32')

  // Swapping shelf drawers ('top' | 'bottom' | null)
  const [openShelf, setOpenShelf] = useState(null)

  // Lightbox inspection modal
  const [inspectItem, setInspectItem] = useState(null)

  // Success animation states
  const [addedComplete, setAddedComplete] = useState(false)
  const [addedPieceKey, setAddedPieceKey] = useState(null)
  const [showSubScores, setShowSubScores] = useState(false)

  // Sync active items when switching combos
  useEffect(() => {
    if (activeBundle?.items?.length >= 2) {
      setActiveTop(activeBundle.items[0])
      setActiveBottom(activeBundle.items[1])
      setOpenShelf(null)
    }
  }, [selectedComboIdx, activeBundle])

  if (!activeTop || !activeBottom) {
    if (bundleData?.status === 'insufficient_categories' || bundleData?.status === 'no_products_found') {
      return (
        <div className="interactive-suite-container animate-fade" style={{ padding: '16px 20px', background: 'rgba(30, 41, 59, 0.6)', borderRadius: 'var(--radius-md)', border: '1px solid rgba(255,255,255,0.08)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--accent-purple)', fontWeight: 600 }}>
            <Sparkles size={16} />
            <span>Multi-Piece Coordination Guidance</span>
          </div>
          <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', marginTop: 8, lineHeight: 1.5 }}>
            To assemble coordinated combinations, please specify target pieces and budget (e.g. <em>"2 shirts under 2000"</em>, <em>"2 uppers and 1 lower under 3k"</em>, or <em>"hoodie and joggers"</em>).
          </p>
        </div>
      )
    }
    return null
  }

  // Dynamic calculations
  const currentPrice = (activeTop.price || 0) + (activeBottom.price || 0)
  const currentBudget = bundleData?.budget || 0
  const currentSavings = currentBudget > currentPrice ? Math.round(currentBudget - currentPrice) : 0
  const styleScorePercent = Math.round((activeBundle?.style_score || 0.88) * 100)

  // Top and bottom candidate shelves for swapping
  const topShelves = bundleData?.shelves?.tops || []
  const bottomShelves = bundleData?.shelves?.bottoms || []

  // Add complete outfit to cart
  const handleAddCompleteOutfit = () => {
    const topItemWithMeta = { ...activeTop, selectedSize: topSize }
    const bottomItemWithMeta = { ...activeBottom, selectedSize: bottomSize }

    if (onAddToCart) {
      onAddToCart(topItemWithMeta)
      onAddToCart(bottomItemWithMeta)
    } else {
      addToCartLocal(topItemWithMeta, 1)
      addToCartLocal(bottomItemWithMeta, 1)
    }
    setAddedComplete(true)
    toast.success(`🎉 Added Complete Outfit to Cart! (Sizes: Upper ${topSize}, Lower ${bottomSize}) • Total: ₹${currentPrice}`)
    setTimeout(() => setAddedComplete(false), 2400)
  }

  // Add individual piece
  const handleAddPiece = (piece, size, key) => {
    const itemWithMeta = { ...piece, selectedSize: size }
    if (onAddToCart) {
      onAddToCart(itemWithMeta)
    } else {
      addToCartLocal(itemWithMeta, 1)
    }
    setAddedPieceKey(key)
    toast.success(`Added ${piece.title} (Size: ${size}) to Cart!`)
    setTimeout(() => setAddedPieceKey(null), 2000)
  }

  // 1-Click Fast Buy
  const handleAutonomousBuy = () => {
    const topItemWithMeta = { ...activeTop, selectedSize: topSize }
    const bottomItemWithMeta = { ...activeBottom, selectedSize: bottomSize }
    addToCartLocal(topItemWithMeta, 1)
    addToCartLocal(bottomItemWithMeta, 1)
    if (onAutonomousCheckout) {
      onAutonomousCheckout({ mode: 'cascade_failover', autoStart: true })
    } else {
      toast.success('Initiating 1-Click Autonomous Checkout...')
    }
  }

  return (
    <div className="interactive-suite-container animate-fade">
      {/* ── 1. Suite Header & Combination Selector Tabs ── */}
      <div className="suite-header-bar">
        <div className="suite-badge-pill hero">
          <Sparkles size={15} />
          <span>AI Stylist Coordinated Looks</span>
        </div>

        <div className="suite-price-savings-cluster">
          {currentSavings > 0 && (
            <span className="suite-savings-tag">
              Save ₹{currentSavings} under budget
            </span>
          )}
          <div className="suite-cohesion-meter">
            <span className="meter-val">{styleScorePercent}%</span>
            <span className="meter-lbl">Harmony</span>
          </div>
        </div>
      </div>

      {/* Combination Tabs (Combo 1, Combo 2, Combo 3) */}
      {combos.length > 1 && (
        <div className="suite-combos-tabs-row">
          {combos.map((combo, idx) => (
            <button
              key={combo.id || idx}
              type="button"
              className={`suite-combo-tab-btn ${selectedComboIdx === idx ? 'active' : ''}`}
              onClick={() => setSelectedComboIdx(idx)}
            >
              <div className="tab-btn-title-row">
                <span className="tab-num-badge">#{idx + 1}</span>
                <strong>{combo.name || `Look ${idx + 1}`}</strong>
              </div>
              <span className="tab-tagline">{combo.badge || combo.tagline || 'Curated Aesthetic'}</span>
            </button>
          ))}
        </div>
      )}

      {/* ── 2. Side-by-Side Coordinated Pieces Display ── */}
      <div className="suite-pieces-split-layout">
        {/* Piece #1: Upper */}
        <div className="suite-piece-card top-card">
          <div className="piece-card-header">
            <span className="piece-type-badge top">
              {activeTop.category ? `Piece #1 • ${activeTop.category.toUpperCase()}` : 'Piece #1 • Upper'}
            </span>
            <button 
              type="button" 
              className="piece-inspect-btn"
              onClick={() => setInspectItem(activeTop)}
              title="Inspect Upper Garment Details"
            >
              <Eye size={13} />
              <span>Details</span>
            </button>
          </div>

          <div className="piece-image-wrap" onClick={() => setInspectItem(activeTop)}>
            <img 
              src={getProductImageUrl(activeTop, 'top')} 
              alt={activeTop.title || activeTop.name || 'Upper Garment'} 
              className="piece-photo" 
              onError={(e) => {
                e.target.onerror = null
                e.target.src = 'https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=800&q=80'
              }}
            />
            <div className="image-zoom-overlay">
              <Maximize2 size={16} />
            </div>
          </div>

          <div className="piece-details-body">
            <h4 className="piece-item-title" title={activeTop.title}>
              {activeTop.title || activeTop.name}
            </h4>
            
            <div className="piece-pricing-row">
              <span className="current-price">₹{activeTop.price}</span>
              {activeTop.mrp && Number(activeTop.mrp) > activeTop.price && (
                <span className="mrp-price">₹{activeTop.mrp}</span>
              )}
              {activeTop.rating && (
                <span className="rating-pill">★ {activeTop.rating}</span>
              )}
            </div>

            {/* Size Selector */}
            <div className="piece-size-selector-row">
              <span className="size-label">Size:</span>
              <div className="size-pills-wrap">
                {['S', 'M', 'L', 'XL', '2XL'].map(sz => (
                  <button
                    key={sz}
                    type="button"
                    className={`size-pill ${topSize === sz ? 'selected' : ''}`}
                    onClick={() => setTopSize(sz)}
                  >
                    {sz}
                  </button>
                ))}
              </div>
            </div>

            {/* Piece Actions */}
            <div className="piece-card-actions">
              <button
                type="button"
                className={`btn-piece-add ${addedPieceKey === 'top' ? 'added' : ''}`}
                onClick={() => handleAddPiece(activeTop, topSize, 'top')}
              >
                {addedPieceKey === 'top' ? <Check size={14} /> : <Plus size={14} />}
                <span>{addedPieceKey === 'top' ? 'Added Top' : `Add Top Only (₹${activeTop.price})`}</span>
              </button>

              {topShelves.length > 1 && (
                <button
                  type="button"
                  className={`btn-piece-swap ${openShelf === 'top' ? 'active' : ''}`}
                  onClick={() => setOpenShelf(openShelf === 'top' ? null : 'top')}
                  title="Browse alternative matching tops"
                >
                  <RefreshCw size={13} />
                  <span>{openShelf === 'top' ? 'Close Shelf' : 'Swap Upper'}</span>
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Cohesion & Color Science Connector */}
        <div className="suite-center-connector">
          <div className="connector-vertical-line" />
          <div className="connector-harmony-badge">
            <Sparkles size={16} />
            <span className="connector-score">{styleScorePercent}% Match</span>
            <span className="connector-vibe">
              {activeBundle?.pairing_type ? activeBundle.pairing_type.replace('_', ' ') : 'Coordinated'}
            </span>
          </div>
          <div className="connector-vertical-line" />
        </div>

        {/* Piece #2: Lower */}
        <div className="suite-piece-card bottom-card">
          <div className="piece-card-header">
            <span className="piece-type-badge bottom">
              {activeBottom.category ? `Piece #2 • ${activeBottom.category.toUpperCase()}` : 'Piece #2 • Lower'}
            </span>
            <button 
              type="button" 
              className="piece-inspect-btn"
              onClick={() => setInspectItem(activeBottom)}
              title="Inspect Lower Garment Details"
            >
              <Eye size={13} />
              <span>Details</span>
            </button>
          </div>

          <div className="piece-image-wrap" onClick={() => setInspectItem(activeBottom)}>
            <img 
              src={getProductImageUrl(activeBottom, 'bottom')} 
              alt={activeBottom.title || activeBottom.name || 'Lower Garment'} 
              className="piece-photo" 
              onError={(e) => {
                e.target.onerror = null
                e.target.src = 'https://images.unsplash.com/photo-1542272604-780c96856592?auto=format&fit=crop&w=800&q=80'
              }}
            />
            <div className="image-zoom-overlay">
              <Maximize2 size={16} />
            </div>
          </div>

          <div className="piece-details-body">
            <h4 className="piece-item-title" title={activeBottom.title}>
              {activeBottom.title || activeBottom.name}
            </h4>
            
            <div className="piece-pricing-row">
              <span className="current-price">₹{activeBottom.price}</span>
              {activeBottom.mrp && Number(activeBottom.mrp) > activeBottom.price && (
                <span className="mrp-price">₹{activeBottom.mrp}</span>
              )}
              {activeBottom.rating && (
                <span className="rating-pill">★ {activeBottom.rating}</span>
              )}
            </div>

            {/* Size Selector */}
            <div className="piece-size-selector-row">
              <span className="size-label">Waist:</span>
              <div className="size-pills-wrap">
                {['28', '30', '32', '34', '36'].map(sz => (
                  <button
                    key={sz}
                    type="button"
                    className={`size-pill ${bottomSize === sz ? 'selected' : ''}`}
                    onClick={() => setBottomSize(sz)}
                  >
                    {sz}
                  </button>
                ))}
              </div>
            </div>

            {/* Piece Actions */}
            <div className="piece-card-actions">
              <button
                type="button"
                className={`btn-piece-add ${addedPieceKey === 'bottom' ? 'added' : ''}`}
                onClick={() => handleAddPiece(activeBottom, bottomSize, 'bottom')}
              >
                {addedPieceKey === 'bottom' ? <Check size={14} /> : <Plus size={14} />}
                <span>{addedPieceKey === 'bottom' ? 'Added Lower' : `Add Lower Only (₹${activeBottom.price})`}</span>
              </button>

              {bottomShelves.length > 1 && (
                <button
                  type="button"
                  className={`btn-piece-swap ${openShelf === 'bottom' ? 'active' : ''}`}
                  onClick={() => setOpenShelf(openShelf === 'bottom' ? null : 'bottom')}
                  title="Browse alternative matching bottoms"
                >
                  <RefreshCw size={13} />
                  <span>{openShelf === 'bottom' ? 'Close Shelf' : 'Swap Lower'}</span>
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ── 3. Interactive Swapping Tray (Opens inline when user clicks Swap Upper/Lower) ── */}
      {openShelf && (
        <div className="suite-shelf-drawer animate-slide-down">
          <div className="shelf-drawer-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <RefreshCw size={15} style={{ color: 'var(--accent-purple)' }} />
              <strong>
                {openShelf === 'top' ? 'Select Alternative Upper Garment:' : 'Select Alternative Lower Garment:'}
              </strong>
            </div>
            <button 
              type="button" 
              className="shelf-drawer-close"
              onClick={() => setOpenShelf(null)}
            >
              <X size={16} />
            </button>
          </div>

          <div className="shelf-candidates-scroll">
            {(openShelf === 'top' ? topShelves : bottomShelves).map((cand, idx) => {
              const isCurrent = (openShelf === 'top' ? activeTop.id : activeBottom.id) === cand.id
              return (
                <div 
                  key={cand.id || idx} 
                  className={`shelf-candidate-card ${isCurrent ? 'current-active' : ''}`}
                  onClick={() => {
                    if (openShelf === 'top') {
                      setActiveTop(cand)
                      toast.success(`Swapped upper to: ${cand.title}`)
                    } else {
                      setActiveBottom(cand)
                      toast.success(`Swapped lower to: ${cand.title}`)
                    }
                    setOpenShelf(null)
                  }}
                >
                  <div className="cand-thumb-wrap">
                    <img 
                      src={getProductImageUrl(cand, openShelf === 'top' ? 'top' : 'bottom')} 
                      alt={cand.title} 
                      className="cand-thumb" 
                      onError={(e) => {
                        e.target.onerror = null
                        e.target.src = openShelf === 'top'
                          ? 'https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=800&q=80'
                          : 'https://images.unsplash.com/photo-1542272604-780c96856592?auto=format&fit=crop&w=800&q=80'
                      }}
                    />
                    {isCurrent && <span className="cand-active-tag">In Outfit</span>}
                  </div>
                  <div className="cand-info">
                    <span className="cand-title" title={cand.title}>{cand.title}</span>
                    <div className="cand-price-row">
                      <strong>₹{cand.price}</strong>
                      {cand.rating && <span className="cand-rating">★ {cand.rating}</span>}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* ── 4. Stylist Rationale & Color Theory Sub-Scores ── */}
      <div className="suite-rationale-box">
        <div className="rationale-header-row">
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <Sparkles size={14} style={{ color: 'var(--accent-purple)' }} />
            <strong style={{ fontSize: '0.84rem' }}>Stylist Insight:</strong>
          </div>
          {activeBundle?.sub_scores && (
            <button
              type="button"
              className="btn-text-accordion"
              onClick={() => setShowSubScores(v => !v)}
            >
              {showSubScores ? 'Hide Color Science ▲' : 'View Color Science Details ▼'}
            </button>
          )}
        </div>

        <p className="suite-rationale-text">
          {activeBundle?.rationale || "Harmonious tonal balance between upper and lower pieces with zero style collisions."}
        </p>

        {showSubScores && activeBundle?.sub_scores && (
          <div className="suite-subscores-grid animate-fade">
            <div className="subscore-metric">
              <span className="metric-label">Hue Harmony (LCh):</span>
              <span className="metric-value">{Math.round((activeBundle.sub_scores.hue_harmony || 0) * 100)}%</span>
            </div>
            <div className="subscore-metric">
              <span className="metric-label">Value Contrast:</span>
              <span className="metric-value">{Math.round((activeBundle.sub_scores.value_contrast || 0) * 100)}%</span>
            </div>
            <div className="subscore-metric">
              <span className="metric-label">Chroma Affinity:</span>
              <span className="metric-value">{Math.round((activeBundle.sub_scores.chroma_comp || 0) * 100)}%</span>
            </div>
            <div className="subscore-metric">
              <span className="metric-label">Neutral Balance:</span>
              <span className="metric-value">{Math.round((activeBundle.sub_scores.neutral_bonus || 0) * 100)}%</span>
            </div>
          </div>
        )}
      </div>

      {/* ── 5. Main Action Bar (Non-Forceful, Empowering) ── */}
      <div className="suite-footer-action-bar">
        <div className="suite-total-cluster">
          <span className="suite-total-label">Complete Outfit Total:</span>
          <div className="suite-total-numbers">
            <span className="suite-total-val">₹{currentPrice}</span>
            <span className="suite-pieces-count">(Upper + Lower)</span>
          </div>
        </div>

        <div className="suite-actions-group">
          <button
            type="button"
            className="btn btn-primary btn-lg suite-add-all-btn"
            onClick={handleAddCompleteOutfit}
          >
            {addedComplete ? <CheckCircle2 size={18} /> : <ShoppingBag size={18} />}
            <span>{addedComplete ? 'Outfit in Cart!' : `Add Complete Outfit (₹${currentPrice})`}</span>
          </button>

          <button
            type="button"
            className="btn btn-outline suite-fastbuy-btn"
            onClick={handleAutonomousBuy}
            title="Convenient autonomous 1-click checkout"
          >
            <Zap size={16} />
            <span>1-Click Buy</span>
          </button>
        </div>
      </div>

      {/* ── 6. Conversational Refinement Quick Chips ── */}
      <div className="suite-refinement-chips-bar">
        <span className="refine-hint">💬 Ask Stylist to Tweak:</span>
        <div className="refine-chips-list">
          {[
            "🔄 Swap Lower with Joggers",
            "🎨 Show higher contrast styles",
            "💰 Keep total under ₹2000",
            "👕 Try oversized hoodie instead"
          ].map((chipPrompt, idx) => (
            <button
              key={idx}
              type="button"
              className="suite-refine-chip"
              onClick={() => onFollowUp && onFollowUp(chipPrompt)}
            >
              <span>{chipPrompt}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Lightbox Modal */}
      {inspectItem && (
        <ProductInspectionModal item={inspectItem} onClose={() => setInspectItem(null)} />
      )}
    </div>
  )
}

// =============================================================================
// SUB-VIEW 2: Match My Outfit Mode (Owned Anchor + Catalog Match)
// =============================================================================
function MatchMyOutfitView({ bundleData, ownedItem, onAddToCart, onAutonomousCheckout, onFollowUp }) {
  const { addToCartLocal } = useApp()
  const constant = ownedItem || bundleData?.constant_item
  const matchedResults = bundleData?.matched_results || []
  const [selectedMatchIdx, setSelectedMatchIdx] = useState(0)

  const activeMatch = matchedResults[selectedMatchIdx] || bundleData?.top_recommendation
  const product = activeMatch?.product

  const [size, setSize] = useState('32')
  const [inspectItem, setInspectItem] = useState(null)
  const [added, setAdded] = useState(false)
  const [showSubScores, setShowSubScores] = useState(false)

  if (!product) return null

  const matchPercent = Math.round((activeMatch?.style_score || 0.88) * 100)

  const handleAddMatch = () => {
    const itemWithMeta = { ...product, selectedSize: size }
    if (onAddToCart) {
      onAddToCart(itemWithMeta)
    } else {
      addToCartLocal(itemWithMeta, 1)
    }
    setAdded(true)
    toast.success(`Added ${product.title} (Size: ${size}) to Cart!`)
    setTimeout(() => setAdded(false), 2200)
  }

  const handleBuyMatch = () => {
    const itemWithMeta = { ...product, selectedSize: size }
    addToCartLocal(itemWithMeta, 1)
    if (onAutonomousCheckout) {
      onAutonomousCheckout({ mode: 'cascade_failover', autoStart: true })
    }
  }

  return (
    <div className="interactive-suite-container animate-fade">
      {/* Header */}
      <div className="suite-header-bar">
        <div className="suite-badge-pill hero">
          <Sparkles size={15} />
          <span>Match My Outfit • Recommended Pairings</span>
        </div>

        <div className="suite-price-savings-cluster">
          <div className="suite-cohesion-meter">
            <span className="meter-val">{matchPercent}%</span>
            <span className="meter-lbl">Harmony</span>
          </div>
        </div>
      </div>

      {/* Matched Candidate Tabs if multiple matches exist */}
      {matchedResults.length > 1 && (
        <div className="suite-combos-tabs-row">
          {matchedResults.slice(0, 4).map((m, idx) => (
            <button
              key={idx}
              type="button"
              className={`suite-combo-tab-btn ${selectedMatchIdx === idx ? 'active' : ''}`}
              onClick={() => setSelectedMatchIdx(idx)}
            >
              <div className="tab-btn-title-row">
                <span className="tab-num-badge">#{idx + 1}</span>
                <strong>{m.product?.title?.slice(0, 22) || `Option ${idx + 1}`}…</strong>
              </div>
              <span className="tab-tagline">₹{m.product?.price} • {Math.round((m.style_score || 0.85) * 100)}% Harmony</span>
            </button>
          ))}
        </div>
      )}

      {/* Side-by-Side: Owned Constant + Catalog Match */}
      <div className="suite-pieces-split-layout">
        {/* Anchor: Owned Garment */}
        <div className="suite-piece-card constant-card">
          <div className="piece-card-header">
            <span className="piece-type-badge anchor">
              <Sparkles size={12} style={{ display: 'inline', marginRight: 4 }} />
              Anchor • You Own This
            </span>
          </div>

          <div className="piece-image-wrap">
            <img 
              src={getProductImageUrl(constant, 'top')} 
              alt="Owned Garment" 
              className="piece-photo" 
              onError={(e) => {
                e.target.onerror = null
                e.target.src = 'https://images.unsplash.com/photo-1556905055-8f358a7a47b2?auto=format&fit=crop&w=800&q=80'
              }}
            />
          </div>

          <div className="piece-details-body">
            <h4 className="piece-item-title">
              {constant?.description || constant?.name || `${constant?.color || ''} ${constant?.category || 'Owned Garment'}`}
            </h4>
            <div className="piece-meta-row" style={{ display: 'flex', gap: 6, marginTop: 8 }}>
              <span className="piece-tag">{constant?.category || 'Garment'}</span>
              {constant?.color && <span className="piece-tag color">{constant.color}</span>}
              {constant?.fit && <span className="piece-tag">{constant.fit}</span>}
            </div>
          </div>
        </div>

        {/* Center Harmony Connector */}
        <div className="suite-center-connector">
          <div className="connector-vertical-line" />
          <div className="connector-harmony-badge">
            <Sparkles size={16} />
            <span className="connector-score">{matchPercent}% Match</span>
            <span className="connector-vibe">Color Science</span>
          </div>
          <div className="connector-vertical-line" />
        </div>

        {/* Catalog Match Piece */}
        <div className="suite-piece-card target-card">
          <div className="piece-card-header">
            <span className="piece-type-badge match">Catalog Recommendation</span>
            <button 
              type="button" 
              className="piece-inspect-btn"
              onClick={() => setInspectItem(product)}
              title="Inspect Garment Details"
            >
              <Eye size={13} />
              <span>Details</span>
            </button>
          </div>

          <div className="piece-image-wrap" onClick={() => setInspectItem(product)}>
            <img 
              src={getProductImageUrl(product, 'bottom')} 
              alt={product.title || product.name || 'Catalog Piece'} 
              className="piece-photo" 
              onError={(e) => {
                e.target.onerror = null
                e.target.src = 'https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?auto=format&fit=crop&w=800&q=80'
              }}
            />
            <div className="image-zoom-overlay">
              <Maximize2 size={16} />
            </div>
          </div>

          <div className="piece-details-body">
            <h4 className="piece-item-title" title={product.title}>
              {product.title || product.name}
            </h4>

            <div className="piece-pricing-row">
              <span className="current-price">₹{product.price}</span>
              {product.rating && (
                <span className="rating-pill">★ {product.rating}</span>
              )}
            </div>

            {/* Size Selector */}
            <div className="piece-size-selector-row">
              <span className="size-label">Size:</span>
              <div className="size-pills-wrap">
                {['28', '30', '32', '34', '36'].map(sz => (
                  <button
                    key={sz}
                    type="button"
                    className={`size-pill ${size === sz ? 'selected' : ''}`}
                    onClick={() => setSize(sz)}
                  >
                    {sz}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Rationale Box */}
      <div className="suite-rationale-box">
        <div className="rationale-header-row">
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <Sparkles size={14} style={{ color: 'var(--accent-purple)' }} />
            <strong style={{ fontSize: '0.84rem' }}>Stylist Insight:</strong>
          </div>
          {activeMatch?.sub_scores && (
            <button
              type="button"
              className="btn-text-accordion"
              onClick={() => setShowSubScores(v => !v)}
            >
              {showSubScores ? 'Hide Science ▲' : 'View Science Details ▼'}
            </button>
          )}
        </div>

        <p className="suite-rationale-text">
          {activeMatch?.rationale || "Complementary color harmony calibrated to flatter your owned piece effortlessly."}
        </p>

        {showSubScores && activeMatch?.sub_scores && (
          <div className="suite-subscores-grid animate-fade">
            <div className="subscore-metric">
              <span className="metric-label">Hue Harmony:</span>
              <span className="metric-value">{Math.round((activeMatch.sub_scores.hue_harmony || 0) * 100)}%</span>
            </div>
            <div className="subscore-metric">
              <span className="metric-label">Value Contrast:</span>
              <span className="metric-value">{Math.round((activeMatch.sub_scores.value_contrast || 0) * 100)}%</span>
            </div>
            <div className="subscore-metric">
              <span className="metric-label">Chroma Affinity:</span>
              <span className="metric-value">{Math.round((activeMatch.sub_scores.chroma_comp || 0) * 100)}%</span>
            </div>
            <div className="subscore-metric">
              <span className="metric-label">Neutral Balance:</span>
              <span className="metric-value">{Math.round((activeMatch.sub_scores.neutral_bonus || 0) * 100)}%</span>
            </div>
          </div>
        )}
      </div>

      {/* Footer Action Bar */}
      <div className="suite-footer-action-bar">
        <div className="suite-total-cluster">
          <span className="suite-total-label">Matching Item Price:</span>
          <div className="suite-total-numbers">
            <span className="suite-total-val">₹{product.price}</span>
          </div>
        </div>

        <div className="suite-actions-group">
          <button
            type="button"
            className="btn btn-primary btn-lg suite-add-all-btn"
            onClick={handleAddMatch}
          >
            {added ? <CheckCircle2 size={18} /> : <ShoppingBag size={18} />}
            <span>{added ? 'Added to Cart!' : `Add Match to Cart (₹${product.price})`}</span>
          </button>

          <button
            type="button"
            className="btn btn-outline suite-fastbuy-btn"
            onClick={handleBuyMatch}
          >
            <Zap size={16} />
            <span>1-Click Buy</span>
          </button>
        </div>
      </div>

      {/* Lightbox Modal */}
      {inspectItem && (
        <ProductInspectionModal item={inspectItem} onClose={() => setInspectItem(null)} />
      )}
    </div>
  )
}

// =============================================================================
// SUB-COMPONENT: Product Inspection Lightbox Modal
// =============================================================================
function ProductInspectionModal({ item, onClose }) {
  if (!item) return null

  return (
    <div className="modal-backdrop animate-fade" onClick={onClose}>
      <div className="modal-content product-inspection-modal animate-scale-up" onClick={e => e.stopPropagation()}>
        <button type="button" className="modal-close-btn" onClick={onClose}>
          <X size={18} />
        </button>

        <div className="inspection-grid">
          <div className="inspection-photo-col">
            <img 
              src={getProductImageUrl(item, 'top')} 
              alt={item.title || item.name} 
              className="inspection-large-img" 
              onError={(e) => {
                e.target.onerror = null
                e.target.src = 'https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=800&q=80'
              }}
            />
          </div>

          <div className="inspection-info-col">
            <span className="inspection-merchant-tag">{item.merchant || 'Bewakoof Official'}</span>
            <h3 className="inspection-title">{item.title || item.name}</h3>

            <div className="inspection-price-row">
              <span className="inspect-price">₹{item.price}</span>
              {item.mrp && Number(item.mrp) > item.price && (
                <span className="inspect-mrp">₹{item.mrp}</span>
              )}
              {item.rating && (
                <span className="rating-pill">★ {item.rating} ({item.review_count || 120} reviews)</span>
              )}
            </div>

            <div className="inspection-specs-list">
              <div className="spec-row">
                <span className="spec-key">Category:</span>
                <span className="spec-val">{item.category || 'Apparel'}</span>
              </div>
              {item.specs?.fit && (
                <div className="spec-row">
                  <span className="spec-key">Fit:</span>
                  <span className="spec-val">{item.specs.fit}</span>
                </div>
              )}
              {item.specs?.fabric && (
                <div className="spec-row">
                  <span className="spec-key">Fabric:</span>
                  <span className="spec-val">{item.specs.fabric}</span>
                </div>
              )}
              {item.specs?.color && (
                <div className="spec-row">
                  <span className="spec-key">Color:</span>
                  <span className="spec-val">{item.specs.color}</span>
                </div>
              )}
              <div className="spec-row">
                <span className="spec-key">Delivery:</span>
                <span className="spec-val">{item.shipping_speed || '🚚 Standard (2-3 Days)'}</span>
              </div>
            </div>

            <div style={{ marginTop: 24 }}>
              <button 
                type="button" 
                className="btn btn-primary" 
                style={{ width: '100%', justifyContent: 'center' }}
                onClick={onClose}
              >
                Back to Outfit Suite
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
