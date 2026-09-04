import React, { useState } from 'react'
import { Sparkles, ShoppingBag, Zap, Check, ArrowRight, ShieldCheck, Tag, Info, AlertTriangle } from 'lucide-react'
import { useApp } from '../context/AppContext'
import toast from 'react-hot-toast'

export default function OutfitBundleCard({ 
  bundle, 
  mode = 'bundle', // 'bundle' | 'match_my_outfit' | 'budget_too_low'
  ownedItem = null,
  alternatives = null,
  onAddToCart,
  onAutonomousCheckout,
  onSelectAlternative
}) {
  const { addToCartLocal, updateConfig } = useApp()
  const [added, setAdded] = useState(false)
  const [showSubScores, setShowSubScores] = useState(false)

  // ---------------------------------------------------------------------------
  // Low Budget Fallback State ($P_min)
  // ---------------------------------------------------------------------------
  if (mode === 'budget_too_low' || bundle?.status === 'budget_too_low') {
    const altData = alternatives || bundle?.alternatives
    return (
      <div className="outfit-bundle-card low-budget-card animate-fade">
        <div className="bundle-header">
          <div className="bundle-badge low-budget">
            <AlertTriangle size={14} />
            <span>Budget Constraint Notice</span>
          </div>
          <span className="bundle-price-tag">
            Store Minimum: ₹{bundle?.min_total_required || altData?.min_total || '998'}
          </span>
        </div>

        <p className="bundle-rationale text-secondary" style={{ marginTop: 8, fontSize: '0.9rem', lineHeight: 1.5 }}>
          {altData?.message || "With your current budget, coordinating both pieces exceeds the lowest available catalog prices."}
        </p>

        {altData?.options && (
          <div className="budget-alternatives-list" style={{ marginTop: 14 }}>
            <span style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--accent-amber)', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
              Suggested Next Steps:
            </span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
              {altData.options.map((opt, idx) => (
                <button
                  key={idx}
                  className="budget-option-pill"
                  onClick={() => onSelectAlternative && onSelectAlternative(opt, idx)}
                >
                  <ArrowRight size={13} style={{ color: 'var(--accent-amber)', flexShrink: 0 }} />
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
  if (mode === 'match_my_outfit') {
    const constant = ownedItem || bundle?.constant_item
    const rec = bundle?.top_recommendation || (bundle?.matched_results && bundle?.matched_results[0])
    const product = rec?.product

    if (!product) return null

    const matchPercent = Math.round((rec?.style_score || 0.85) * 100)

    const handleAddMatched = () => {
      if (onAddToCart) {
        onAddToCart(product)
      } else {
        addToCartLocal(product, 1)
        toast.success(`Added ${product.title || product.name} to cart!`)
      }
      setAdded(true)
      setTimeout(() => setAdded(false), 2200)
    }

    const handleBuyMatched = () => {
      addToCartLocal(product, 1)
      if (onAutonomousCheckout) {
        onAutonomousCheckout({ mode: 'cascade_failover', autoStart: true })
      }
    }

    return (
      <div className="outfit-bundle-card animate-fade">
        {/* Header */}
        <div className="bundle-header">
          <div className="bundle-badge hero">
            <Sparkles size={14} />
            <span>Match My Outfit • Recommended Pairing</span>
          </div>
          <div className="bundle-cohesion-pill">
            <span className="cohesion-number">{matchPercent}%</span>
            <span className="cohesion-label">Aesthetic Harmony</span>
          </div>
        </div>

        {/* Side-by-Side Coordinated Pieces */}
        <div className="outfit-pieces-grid">
          {/* Constant Item A (User's Owned Item) */}
          <div className="outfit-piece-card constant-piece">
            <div className="piece-anchor-badge">Anchor • You Own This</div>
            <div className="piece-image-placeholder">
              {constant?.image_url ? (
                <img src={constant.image_url} alt="Owned Item" className="piece-img" />
              ) : (
                <div className="piece-icon-box">🧥</div>
              )}
            </div>
            <div className="piece-info">
              <strong className="piece-title">{constant?.description || constant?.name || `${constant?.color || ''} ${constant?.category || 'Garment'}`}</strong>
              <div className="piece-meta-row">
                <span className="piece-tag">{constant?.category || 'Owned'}</span>
                {constant?.color && <span className="piece-tag color">{constant.color}</span>}
                {constant?.fit && <span className="piece-tag">{constant.fit}</span>}
              </div>
            </div>
          </div>

          {/* Harmony Connector */}
          <div className="coordination-connector">
            <div className="connector-line" />
            <div className="connector-circle">
              <Sparkles size={14} />
            </div>
            <span className="connector-type-label">Color Theory Match</span>
            <div className="connector-line" />
          </div>

          {/* Recommended Match Product (Item B) */}
          <div className="outfit-piece-card target-piece">
            <div className="piece-anchor-badge match">Catalog Recommendation</div>
            <div className="piece-image-placeholder">
              {product.images && product.images[0] ? (
                <img src={product.images[0]} alt={product.title} className="piece-img" />
              ) : (
                <div className="piece-icon-box">👖</div>
              )}
            </div>
            <div className="piece-info">
              <strong className="piece-title" title={product.title || product.name}>
                {product.title || product.name}
              </strong>
              <div className="piece-meta-row">
                <span className="piece-price">₹{product.price}</span>
                {product.rating && (
                  <span className="piece-rating">★ {product.rating}</span>
                )}
                <span className="piece-tag">{product.category}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Stylist Rationale */}
        <div className="bundle-rationale-box">
          <div className="rationale-header">
            <Info size={14} style={{ color: 'var(--accent-purple)' }} />
            <span>Stylist Rationale:</span>
          </div>
          <p className="rationale-text">
            {rec?.rationale || "Complementary color harmony creates a balanced, modern streetwear outfit."}
          </p>

          {rec?.sub_scores && (
            <div className="sub-scores-toggle-row">
              <button 
                type="button" 
                className="btn-text-link"
                onClick={() => setShowSubScores(v => !v)}
              >
                {showSubScores ? 'Hide Perceptual Details ▲' : 'View Color Science Details ▼'}
              </button>
            </div>
          )}

          {showSubScores && rec?.sub_scores && (
            <div className="sub-scores-grid animate-fade">
              <div className="sub-score-item">
                <span>Hue Harmony (LCh):</span>
                <strong>{Math.round((rec.sub_scores.hue_harmony || 0) * 100)}%</strong>
              </div>
              <div className="sub-score-item">
                <span>Value Contrast:</span>
                <strong>{Math.round((rec.sub_scores.value_contrast || 0) * 100)}%</strong>
              </div>
              <div className="sub-score-item">
                <span>Chroma Compatibility:</span>
                <strong>{Math.round((rec.sub_scores.chroma_compatibility || 0) * 100)}%</strong>
              </div>
              <div className="sub-score-item">
                <span>Neutral Balance:</span>
                <strong>{Math.round((rec.sub_scores.neutral_bonus || 0) * 100)}%</strong>
              </div>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="bundle-actions-row">
          <button 
            type="button" 
            className="btn btn-outline"
            onClick={handleAddMatched}
          >
            {added ? <Check size={16} /> : <ShoppingBag size={16} />}
            <span>{added ? 'Added to Cart' : `Add Match to Cart (₹${product.price})`}</span>
          </button>

          <button 
            type="button" 
            className="btn btn-primary"
            onClick={handleBuyMatched}
          >
            <Zap size={16} />
            <span>Autonomous Buy Now (₹{product.price})</span>
          </button>
        </div>
      </div>
    )
  }

  // ---------------------------------------------------------------------------
  // Multi-Item Bundle Mode (Both Items Non-Constant)
  // ---------------------------------------------------------------------------
  const items = bundle?.items || []
  if (items.length < 2) return null

  const topPiece = items[0]
  const bottomPiece = items[1]
  const totalPrice = bundle?.total_price || (topPiece.price + bottomPiece.price)
  const savings = bundle?.budget_savings || 0
  const styleScorePercent = Math.round((bundle?.style_score || 0.88) * 100)

  const handleAddBundleToCart = () => {
    items.forEach(it => {
      addToCartLocal(it, 1)
    })
    setAdded(true)
    toast.success(`Added full outfit (2 pieces) to cart! Total: ₹${totalPrice}`)
    setTimeout(() => setAdded(false), 2500)
  }

  const handleAutonomousBuyBundle = () => {
    items.forEach(it => {
      addToCartLocal(it, 1)
    })
    if (onAutonomousCheckout) {
      onAutonomousCheckout({ mode: 'cascade_failover', autoStart: true })
    }
  }

  return (
    <div className="outfit-bundle-card animate-fade">
      {/* Bundle Header */}
      <div className="bundle-header">
        <div className="bundle-badge hero">
          <Sparkles size={14} />
          <span>Curated Outfit Bundle</span>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {savings > 0 && (
            <span className="bundle-savings-badge">
              Save ₹{Math.round(savings)} under budget
            </span>
          )}
          <div className="bundle-cohesion-pill">
            <span className="cohesion-number">{styleScorePercent}%</span>
            <span className="cohesion-label">Cohesion Score</span>
          </div>
        </div>
      </div>

      {/* Side-by-Side Pieces */}
      <div className="outfit-pieces-grid">
        {/* Piece 1: Upper */}
        <div className="outfit-piece-card">
          <div className="piece-anchor-badge top">Piece #1 • Upper</div>
          <div className="piece-image-placeholder">
            {topPiece.images && topPiece.images[0] ? (
              <img src={topPiece.images[0]} alt={topPiece.title} className="piece-img" />
            ) : (
              <div className="piece-icon-box">🧥</div>
            )}
          </div>
          <div className="piece-info">
            <strong className="piece-title" title={topPiece.title || topPiece.name}>
              {topPiece.title || topPiece.name}
            </strong>
            <div className="piece-meta-row">
              <span className="piece-price">₹{topPiece.price}</span>
              {topPiece.rating && <span className="piece-rating">★ {topPiece.rating}</span>}
              <span className="piece-tag">{topPiece.category}</span>
            </div>
          </div>
        </div>

        {/* Pairing Type Link */}
        <div className="coordination-connector">
          <div className="connector-line" />
          <div className="connector-circle">
            <Sparkles size={14} />
          </div>
          <span className="connector-type-label">
            {bundle?.pairing_type ? bundle.pairing_type.replace('_', ' ') : 'Coordinated Pair'}
          </span>
          <div className="connector-line" />
        </div>

        {/* Piece 2: Lower */}
        <div className="outfit-piece-card">
          <div className="piece-anchor-badge bottom">Piece #2 • Lower</div>
          <div className="piece-image-placeholder">
            {bottomPiece.images && bottomPiece.images[0] ? (
              <img src={bottomPiece.images[0]} alt={bottomPiece.title} className="piece-img" />
            ) : (
              <div className="piece-icon-box">👖</div>
            )}
          </div>
          <div className="piece-info">
            <strong className="piece-title" title={bottomPiece.title || bottomPiece.name}>
              {bottomPiece.title || bottomPiece.name}
            </strong>
            <div className="piece-meta-row">
              <span className="piece-price">₹{bottomPiece.price}</span>
              {bottomPiece.rating && <span className="piece-rating">★ {bottomPiece.rating}</span>}
              <span className="piece-tag">{bottomPiece.category}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Rationale & Sub-Scores */}
      <div className="bundle-rationale-box">
        <div className="rationale-header">
          <Info size={14} style={{ color: 'var(--accent-purple)' }} />
          <span>Stylist Rationale:</span>
        </div>
        <p className="rationale-text">
          {bundle?.rationale || "Harmonious balance of tones and tailored textures with zero style collisions."}
        </p>

        {bundle?.sub_scores && (
          <div className="sub-scores-toggle-row">
            <button 
              type="button" 
              className="btn-text-link"
              onClick={() => setShowSubScores(v => !v)}
            >
              {showSubScores ? 'Hide Color Theory Sub-Scores ▲' : 'View Color Theory Sub-Scores ▼'}
            </button>
          </div>
        )}

        {showSubScores && bundle?.sub_scores && (
          <div className="sub-scores-grid animate-fade">
            <div className="sub-score-item">
              <span>Hue Harmony:</span>
              <strong>{Math.round((bundle.sub_scores.hue_harmony || 0) * 100)}%</strong>
            </div>
            <div className="sub-score-item">
              <span>Value Contrast:</span>
              <strong>{Math.round((bundle.sub_scores.value_contrast || 0) * 100)}%</strong>
            </div>
            <div className="sub-score-item">
              <span>Chroma Affinity:</span>
              <strong>{Math.round((bundle.sub_scores.chroma_compatibility || 0) * 100)}%</strong>
            </div>
            <div className="sub-score-item">
              <span>Neutral Balance:</span>
              <strong>{Math.round((bundle.sub_scores.neutral_bonus || 0) * 100)}%</strong>
            </div>
          </div>
        )}
      </div>

      {/* Footer Price & Buttons */}
      <div className="bundle-footer-bar">
        <div className="bundle-total-info">
          <span className="total-label">Complete Outfit Total:</span>
          <div className="total-price-row">
            <span className="total-amount">₹{totalPrice}</span>
            <span className="items-count-tag">(2 pieces included)</span>
          </div>
        </div>

        <div className="bundle-actions-row">
          <button 
            type="button" 
            className="btn btn-outline"
            onClick={handleAddBundleToCart}
          >
            {added ? <Check size={16} /> : <ShoppingBag size={16} />}
            <span>{added ? 'Both Added' : 'Add Both to Cart'}</span>
          </button>

          <button 
            type="button" 
            className="btn btn-primary"
            onClick={handleAutonomousBuyBundle}
          >
            <Zap size={16} />
            <span>Autonomous Buy Outfit (₹{totalPrice})</span>
          </button>
        </div>
      </div>
    </div>
  )
}
