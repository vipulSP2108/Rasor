import { Star, ShoppingCart, Scale, Check } from 'lucide-react'
import { useApp } from '../context/AppContext'

export default function ProductCard({ product, onAddToCart, layout = 'grid' }) {
  const { cart, compareList, toggleCompare } = useApp()
  const inCart = !!cart.items[product.id]
  const inCompare = !!compareList[product.id]
  const curr = '₹'

  const imgUrl = product.specs?.display_image || product.specs?.image_url || 'https://via.placeholder.com/400x500/161e2e/6366f1?text=No+Image'

  const handleCompare = (e) => {
    e.stopPropagation()
    toggleCompare(product)
  }

  const verdictColor = {
    'STRONG_MATCH': 'var(--accent-green)',
    'PARTIAL_MATCH': 'var(--accent-amber)',
  }[product.verdict] || 'transparent'

  return (
    <div
      className="product-card animate-slide-up"
      style={{ borderTopColor: verdictColor, borderTopWidth: 2 }}
    >
      <div className="product-card-image">
        <img src={imgUrl} alt={product.title} loading="lazy" />

        {product.verdict === 'STRONG_MATCH' && (
          <div className="product-card-badge">✦ Best Match</div>
        )}

        <div className="product-card-actions">
          <button
            className="product-card-action-btn"
            onClick={handleCompare}
            title={inCompare ? 'Remove from compare' : 'Add to compare'}
            style={{ 
              background: inCompare ? 'var(--accent-red)' : undefined, 
              color: inCompare ? '#fff' : undefined,
              borderColor: inCompare ? 'var(--accent-red)' : undefined 
            }}
          >
            {inCompare ? <Check size={14} /> : <Scale size={14} />}
          </button>
        </div>
      </div>

      <div className="product-card-body">
        <div className="product-card-title">{product.title}</div>
        <div className="product-card-meta">
          <span className="product-card-price">{curr}{product.price?.toFixed(0)}</span>
          <span className="product-card-rating">
            <Star size={12} className="star" fill="#fbbf24" color="#fbbf24" />
            {product.rating?.toFixed(1) || '—'}
          </span>
        </div>

        {inCart ? (
          <div className="product-card-in-cart">
            <ShoppingCart size={14} style={{ display: 'inline', marginRight: 6 }} />
            In Cart ({cart.items[product.id]})
          </div>
        ) : (
          <button
            className="product-card-add-btn"
            onClick={() => onAddToCart(product)}
          >
            <ShoppingCart size={15} /> Add to Cart
          </button>
        )}
      </div>
    </div>
  )
}
