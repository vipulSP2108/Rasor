import React from 'react'
import { Star, ShoppingCart, Scale, Check } from 'lucide-react'
import { useApp } from '../context/AppContext'
import toast from 'react-hot-toast'

export default function ProductCard({ product, onAddToCart, layout = 'grid' }) {
  const { cart, compareList, toggleCompare, config } = useApp()
  const inCart = !!cart.items[product.id]
  const inCompare = !!compareList[product.id]
  const curr = '₹'

  const imgUrl = product.specs?.display_image || product.specs?.image_url || 'https://via.placeholder.com/400x500/161e2e/6366f1?text=No+Image'

  const handleCompare = (e) => {
    e.stopPropagation()
    toggleCompare(product)
    if (inCompare) {
      toast.success(`Removed "${product.title?.slice(0, 22)}..." from Compare`)
    } else {
      if (Object.keys(compareList).length >= 5) {
        toast.error('Compare limit reached (max 5 items)')
      } else {
        toast.success(`Added "${product.title?.slice(0, 22)}..." to Compare`)
      }
    }
  }

  // 1. Match % calculation and dynamic coloring
  const rawScore = product.relevance_score ?? 0.7
  const matchPct = Math.min(100, Math.max(10, Math.round(rawScore * 100)))
  const badgeColor = matchPct >= 70 ? '#10b981' : (matchPct >= 40 ? '#f59e0b' : '#ef4444')

  // 2. HITL Approval Requirement check
  const hitlLimit = config.maxCostHitl || 800
  const requiresApproval = (product.price || 0) > hitlLimit

  // 3. Price & Ratings details
  const mrpVal = product.mrp || product.specs?.mrp_inr || product.specs?.mrp
  const reviewCount = product.review_count || product.specs?.review_count || 120
  const ratingVal = product.rating || 4.5

  // 4. Delivery timeline: ONLY show when fast delivery was explicitly requested or distance was computed
  const showDelivery = Boolean(
    product.is_fast_shipping_requested ||
    product.specs?.distance_km != null ||
    product.specs?.shipping_speed != null
  )
  const shippingDays = product.shipping_days || product.specs?.shipping_days || 3

  // 5. Source URL for View on entire card click
  const productUrl = product.source_url ||
    (product.specs?.handle ? `https://rasor-test-store-1.myshopify.com/products/${product.specs.handle}` :
      (product.specs?.url ? (product.specs.url.startsWith('http') ? product.specs.url : `https://www.bewakoof.com${product.specs.url}`) : 'https://rasor-test-store-1.myshopify.com'))

  const handleCardClick = () => {
    if (productUrl) {
      window.open(productUrl, '_blank', 'noopener,noreferrer')
    }
  }

  const verdictColor = {
    'STRONG_MATCH': 'var(--accent-green)',
    'PARTIAL_MATCH': 'var(--accent-amber)',
  }[product.verdict] || 'transparent'

  return (
    <div
      className={`product-card animate-slide-up ${inCompare ? 'in-compare-active' : ''}`}
      onClick={handleCardClick}
      title="Click anywhere on card to view product page ↗"
      style={{
        borderTopColor: verdictColor,
        borderTopWidth: 2,
        borderColor: inCompare ? 'rgba(99, 102, 241, 0.6)' : undefined,
        boxShadow: inCompare ? '0 0 16px rgba(99, 102, 241, 0.25)' : undefined,
        cursor: 'pointer',
      }}
    >
      <div className="product-card-image">
        <img src={imgUrl} alt={product.title} loading="lazy" />

        {/* Top-Left Badge: % Match or Best Match depending on Settings toggle */}
        {config.showMatchPercentage !== false ? (
          <div
            className="product-card-match-badge"
            style={{
              position: 'absolute',
              top: 10,
              left: 10,
              background: badgeColor,
              color: '#fff',
              padding: '4px 10px',
              borderRadius: 20,
              fontSize: '0.74rem',
              fontWeight: 700,
              zIndex: 3,
              boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
              display: 'flex',
              alignItems: 'center',
              gap: 4
            }}
          >
            🧠 {matchPct}% Match
          </div>
        ) : (
          (product.verdict === 'STRONG_MATCH' || matchPct >= 70) ? (
            <div className="product-card-badge" style={{ position: 'absolute', top: 10, left: 10 }}>
              ✦ Best Match
            </div>
          ) : (
            <div className="product-card-badge" style={{ position: 'absolute', top: 10, left: 10, background: 'var(--accent-amber)' }}>
              ⚡ Good Match
            </div>
          )
        )}

        {/* Top-Right: Hover Compare Action Button */}
        <div className={`product-card-actions ${inCompare ? 'active' : ''}`}>
          <button
            className={`product-card-action-btn ${inCompare ? 'active' : ''}`}
            onClick={handleCompare}
            title={inCompare ? "In Compare (Click to remove)" : "Add to compare"}
          >
            {inCompare ? <Check size={15} /> : <Scale size={14} />}
          </button>
        </div>

        {/* Bottom-Left Overlay: ⚠️ Requires Approval if price > HITL Limit */}
        {requiresApproval && (
          <div
            className="product-card-hitl-badge"
            style={{
              position: 'absolute',
              bottom: 10,
              left: 10,
              background: 'rgba(239, 68, 68, 0.95)',
              color: '#fff',
              padding: '4px 10px',
              borderRadius: 20,
              fontSize: '0.72rem',
              fontWeight: 700,
              zIndex: 3,
              boxShadow: '0 4px 10px rgba(0,0,0,0.4)',
              border: '1px solid rgba(255,255,255,0.25)',
              display: 'flex',
              alignItems: 'center',
              gap: 4
            }}
            title={`Order cost (${curr}${product.price}) exceeds autonomous approval limit of ${curr}${hitlLimit}`}
          >
            ⚠️ Requires Approval
          </div>
        )}
      </div>

      <div className="product-card-body">
        <div className="product-card-title" title={product.title}>{product.title}</div>

        {/* Price & Strikethrough MRP + Ratings Row */}
        <div className="product-card-meta">
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <span className="product-card-price">{curr}{product.price?.toFixed(0)}</span>
            {mrpVal && Number(mrpVal) > product.price && (
              <span style={{ textDecoration: 'line-through', color: '#94a3b8', fontSize: '0.85rem', fontWeight: 400 }}>
                {curr}{Number(mrpVal).toFixed(0)}
              </span>
            )}
          </div>

          <span className="product-card-rating">
            <Star size={12} className="star" fill="#fbbf24" color="#fbbf24" />
            <strong>{Number(ratingVal).toFixed(1)}</strong>
            <span style={{ opacity: 0.8 }}>({reviewCount})</span>
          </span>
        </div>

        {/* Delivery Timeline: Clean plain text right above Add to Cart, only when requested */}
        {showDelivery && (
          <div style={{
            fontSize: '0.78rem',
            fontWeight: 600,
            color: '#94a3b8',
            textAlign: 'center',
            marginTop: 2,
            marginBottom: 0
          }}>
            ⚡ Delivered in {shippingDays} {shippingDays === 1 ? 'Day' : 'Days'}
          </div>
        )}

        {/* Single Prominent Add to Cart Button */}
        {inCart ? (
          <div
            className="product-card-in-cart"
            onClick={(e) => e.stopPropagation()}
          >
            <Check size={14} style={{ display: 'inline', marginRight: 6 }} />
            In Cart ({cart.items[product.id]})
          </div>
        ) : (
          <button
            className="product-card-add-btn"
            onClick={(e) => {
              e.stopPropagation()
              onAddToCart(product)
            }}
          >
            <ShoppingCart size={15} /> Add to Cart
          </button>
        )}
      </div>
    </div>
  )
}

