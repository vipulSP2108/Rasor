import { useState } from 'react'
import { X, ShoppingCart } from 'lucide-react'
import { createCart, addToCart } from '../api/client'
import { useApp } from '../context/AppContext'
import toast from 'react-hot-toast'

export default function AddToCartModal({ product, onConfirm, onClose, config }) {
  const { cart, setShopifyCart } = useApp()
  const [selectedSize, setSelectedSize] = useState(null)
  const [qty, setQty] = useState(1)
  const [loading, setLoading] = useState(false)

  const variantIds = product.specs?.variant_ids || {}
  const sizes = Object.keys(variantIds)
  const curr = config.currency === 'INR' ? '₹' : '$'
  const itemCost = product.price * qty
  const newCartTotal = cart.total + itemCost

  const hitlExceeded = newCartTotal > config.maxCostHitl
  const budgetExceeded = newCartTotal > config.maxBudget
  const [hitlApproved, setHitlApproved] = useState(false)

  const canAdd = !budgetExceeded && (!hitlExceeded || hitlApproved)

  const handleConfirm = async () => {
    if (!canAdd) return
    const size = selectedSize || sizes[0]
    const variantGid = variantIds[size]

    if (!variantGid) {
      onConfirm(product, qty)
      return
    }

    setLoading(true)
    try {
      let res
      if (cart.shopifyCartId) {
        const { data } = await addToCart({ cart_id: cart.shopifyCartId, variant_gid: variantGid, quantity: qty })
        res = data
      } else {
        const { data } = await createCart({ variant_gid: variantGid, quantity: qty })
        res = data
      }

      if (res.success) {
        setShopifyCart(res.cart_id, res.checkout_url, res.total_quantity, parseFloat(res.cost || 0))
        toast.success('Added to cart!')
      } else {
        toast.error('Cart error: ' + (res.errors || 'Unknown'))
      }
      onConfirm(product, qty)
    } catch (err) {
      toast.error('Cart error: ' + (err.response?.data?.detail || err.message))
      // Still add locally
      onConfirm(product, qty)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <div className="cart-overlay" onClick={onClose} style={{ zIndex: 300 }} />
      <div style={{
        position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
        zIndex: 301, background: 'var(--bg-surface)', border: '1px solid var(--border)',
        borderRadius: 'var(--radius-xl)', padding: 24, width: 'min(480px, 92vw)',
        boxShadow: 'var(--shadow-elevated)',
      }} className="animate-fade">
        {/* Header */}
        <div className="flex justify-between items-center" style={{ marginBottom: 20 }}>
          <h3 style={{ fontFamily: 'Outfit, sans-serif', fontWeight: 700 }}>Add to Cart</h3>
          <button className="btn btn-ghost btn-icon" onClick={onClose}><X size={18} /></button>
        </div>

        {/* Product */}
        <div className="flex gap-4" style={{ marginBottom: 20 }}>
          <img
            src={product.specs?.display_image || product.specs?.image_url || ''}
            alt={product.title}
            style={{ width: 80, height: 100, objectFit: 'cover', borderRadius: 8, border: '1px solid var(--border)' }}
          />
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600, fontSize: '0.9rem', lineHeight: 1.4, marginBottom: 6 }}>{product.title}</div>
            <div style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--accent-green)' }}>
              {curr}{product.price?.toFixed(0)}
            </div>
          </div>
        </div>

        {/* Size selection */}
        {sizes.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div className="text-sm" style={{ marginBottom: 8, fontWeight: 600 }}>Select Size</div>
            <div className="radio-group">
              {sizes.map(s => (
                <button
                  key={s}
                  className={`radio-option ${(selectedSize || sizes[0]) === s ? 'selected' : ''}`}
                  onClick={() => setSelectedSize(s)}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Qty */}
        <div style={{ marginBottom: 16 }}>
          <div className="text-sm" style={{ marginBottom: 8, fontWeight: 600 }}>Quantity</div>
          <div className="flex items-center gap-3">
            <button className="qty-btn" onClick={() => setQty(q => Math.max(1, q - 1))}>−</button>
            <span className="qty-display" style={{ fontSize: '1rem' }}>{qty}</span>
            <button className="qty-btn" onClick={() => setQty(q => Math.min(10, q + 1))}>+</button>
            <span className="text-sm text-muted" style={{ marginLeft: 8 }}>
              Subtotal: <strong style={{ color: 'var(--accent-green)' }}>{curr}{itemCost.toFixed(0)}</strong>
            </span>
          </div>
        </div>

        {/* Guardrail warnings */}
        {budgetExceeded && (
          <div className="alert alert-error" style={{ marginBottom: 12 }}>
            ⛔ Exceeds hard budget of {curr}{config.maxBudget.toLocaleString()}. Cannot proceed.
          </div>
        )}
        {!budgetExceeded && hitlExceeded && (
          <div style={{ marginBottom: 12 }}>
            <div className="alert alert-warning" style={{ marginBottom: 8 }}>
              ⚠️ <strong>HITL Approval Required</strong><br />
              New cart total ({curr}{newCartTotal.toFixed(0)}) exceeds auto-approval threshold of {curr}{config.maxCostHitl.toLocaleString()}.
            </div>
            <label className="flex items-center gap-2 text-sm" style={{ cursor: 'pointer' }}>
              <input type="checkbox" checked={hitlApproved} onChange={e => setHitlApproved(e.target.checked)} />
              I manually approve this high-value addition
            </label>
          </div>
        )}

        <button className="btn btn-primary btn-full" onClick={handleConfirm} disabled={!canAdd || loading}>
          {loading ? <span className="spinner" /> : <><ShoppingCart size={16} /> Confirm Add to Cart</>}
        </button>
      </div>
    </>
  )
}
