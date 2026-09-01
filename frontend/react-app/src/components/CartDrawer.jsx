import { useState, useEffect } from 'react'
import { X, Minus, Plus, Trash2, ShoppingBag, ExternalLink } from 'lucide-react'
import { useApp } from '../context/AppContext'
import CheckoutSection from './CheckoutSection'
import toast from 'react-hot-toast'

export default function CartDrawer({ onClose }) {
  const { cart, removeFromCart, updateQty, clearCart, config } = useApp()
  const curr = '₹'

  const cartProducts = Object.entries(cart.items).map(([id, qty]) => ({
    ...cart.products[id],
    qty,
  })).filter(p => p.id)

  const rawTotal = cartProducts.reduce((s, p) => s + p.price * p.qty, 0)

  // Build cart_items for API
  const cartItemsPayload = cartProducts.map(p => ({
    product_id: p.id,
    title: p.title,
    merchant: p.merchant || 'Rasor',
    unit_price: p.price,
    quantity: p.qty,
  }))

  // Shopify permalink
  const permalink = cartProducts
    .map(p => {
      const vids = p.specs?.variant_ids || {}
      const first = Object.values(vids)[0] || ''
      const num = first.split('/').pop()
      return num ? `${num}:${p.qty}` : null
    })
    .filter(Boolean)
    .join(',')

  const shopifyUrl = permalink
    ? `https://rasor-test-store-1.myshopify.com/cart/${permalink}`
    : null

  if (cartProducts.length === 0) {
    return (
      <>
        <div className="cart-overlay" onClick={onClose} />
        <div className="cart-drawer animate-slide-right">
          <div className="cart-header">
            <h2>🛒 Your Cart</h2>
            <button className="btn btn-ghost btn-icon" onClick={onClose}><X size={18} /></button>
          </div>
          <div className="cart-body">
            <div className="empty-state">
              <div className="empty-state-icon">🛍️</div>
              <h3>Cart is empty</h3>
              <p>Search for products and add them to your cart.</p>
            </div>
          </div>
        </div>
      </>
    )
  }

  return (
    <>
      <div className="cart-overlay" onClick={onClose} />
      <div className="cart-drawer animate-slide-right">
        <div className="cart-header">
          <h2>🛒 Cart ({cart.quantity} items)</h2>
          <div className="flex gap-2">
            <button className="btn btn-danger btn-sm" onClick={() => { clearCart(); onClose() }}>
              <Trash2 size={14} /> Clear
            </button>
            <button className="btn btn-ghost btn-icon" onClick={onClose}><X size={18} /></button>
          </div>
        </div>

        <div className="cart-body">
          {/* Items */}
          {cartProducts.map(p => (
            <div key={p.id} className="cart-item">
              <div className="cart-item-image">
                <img src={p.specs?.display_image || p.specs?.image_url || 'https://via.placeholder.com/64x80/161e2e/6366f1'} alt={p.title} />
              </div>
              <div className="cart-item-details">
                <div className="cart-item-title">{p.title}</div>
                <div className="cart-item-price">{curr}{(p.price * p.qty).toFixed(0)}</div>
                <div className="cart-item-controls">
                  <button className="qty-btn" onClick={() => p.qty > 1 ? updateQty(p.id, p.qty - 1) : removeFromCart(p.id)}>
                    <Minus size={13} />
                  </button>
                  <span className="qty-display">{p.qty}</span>
                  <button className="qty-btn" onClick={() => updateQty(p.id, p.qty + 1)}>
                    <Plus size={13} />
                  </button>
                  <button className="btn btn-danger btn-icon btn-sm" style={{ marginLeft: 4 }} onClick={() => removeFromCart(p.id)}>
                    <X size={12} />
                  </button>
                </div>
              </div>
            </div>
          ))}

          <hr className="divider" />

          {/* Totals */}
          <div className="cart-total-row">
            <span className="cart-total-label">Raw Total</span>
            <span className="cart-total-value">{curr}{rawTotal.toFixed(0)}</span>
          </div>
          <div className="cart-total-row final">
            <span className="cart-total-label" style={{ fontWeight: 700, color: 'var(--text-primary)' }}>Estimated Total</span>
            <span className="cart-total-value green">{curr}{rawTotal.toFixed(0)}</span>
          </div>

          <hr className="divider" />

          {/* Native Shopify */}
          {shopifyUrl && (
            <div style={{ marginBottom: 16 }}>
              <div className="text-xs text-muted" style={{ marginBottom: 8 }}>
                💡 Checkout via native Shopify storefront (bypasses headless cart isolation)
              </div>
              <a
                href={shopifyUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-ghost btn-full"
                style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
              >
                <ShoppingBag size={16} /> Open in Shopify Storefront
                <ExternalLink size={13} />
              </a>
            </div>
          )}

          {/* Checkout Section */}
          <CheckoutSection
            cartItemsPayload={cartItemsPayload}
            rawTotal={rawTotal}
            currency={config.currency}
            customerEmail={config.customerEmail}
            demoMode={config.demoMode}
            onDemoModeChange={(m) => {}}
            onSuccess={onClose}
          />
        </div>
      </div>
    </>
  )
}
