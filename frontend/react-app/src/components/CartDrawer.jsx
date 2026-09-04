import React, { useState } from 'react';
import { X, Minus, Plus, Trash2, ShoppingBag, ExternalLink, Sparkles, ShieldCheck, RefreshCw } from 'lucide-react'
import { useApp } from '../context/AppContext'
import { useVoice } from '../hooks/useVoice'
import CheckoutSection from './CheckoutSection'
import toast from 'react-hot-toast'

export default function CartDrawer({ onClose, autoStartCascade = false, onResetAutoStartCascade }) {
  const { 
    cart, removeFromCart, updateQty, clearCart, 
    config, updateConfig, candidateBuffer = [], 
    addToCartLocal, userProfile 
  } = useApp()
  const { speak } = useVoice()
  const curr = '₹'

  const activeCandidateBuffer = candidateBuffer.filter(cand => !cart.items[cand.id])

  const handleSubstituteItem = (oldItem, newItem) => {
    if (!oldItem || !newItem) return
    removeFromCart(oldItem.id)
    addToCartLocal(newItem, 1)
    speak(`Item out of stock. Swapped with runner-up from local buffer with zero network latency.`)
    toast.success(`Substituted "${oldItem.title.slice(0, 15)}..." with "${newItem.title.slice(0, 15)}..." from buffer!`, { icon: '🔄' })
  }

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

          {/* AP2 Trust Shield */}
          <div style={{
            background: 'rgba(16, 185, 129, 0.08)',
            border: '1px solid rgba(16, 185, 129, 0.25)',
            borderRadius: 6, padding: '8px 10px',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            marginBottom: 12, fontSize: '0.74rem'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#6ee7b7' }}>
              <ShieldCheck size={16} />
              <span><strong>AP2 Bounded Mandate</strong> (Cap: {curr}{config.maxCostHitl || 2000})</span>
            </div>
            <span style={{ fontFamily: 'monospace', color: 'var(--text-muted)', fontSize: '0.7rem' }}>
              #sha256-verified
            </span>
          </div>

          {/* OOS Pre-Fetched Buffer Candidate Card */}
          {activeCandidateBuffer.length > 0 && cartProducts.length > 0 && (
            <div style={{
              background: 'rgba(99, 102, 241, 0.08)',
              border: '1px solid rgba(99, 102, 241, 0.25)',
              borderRadius: 8, padding: '10px 12px', marginBottom: 14
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                <span style={{ fontSize: '0.74rem', fontWeight: 700, color: '#a5b4fc', display: 'flex', alignItems: 'center', gap: 4 }}>
                  <Sparkles size={12} /> Pre-Fetched Runner-Up Buffer ({activeCandidateBuffer.length} cached)
                </span>
                <span className="badge badge-purple" style={{ fontSize: '0.66rem' }}>Zero-Latency</span>
              </div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 6 }}>
                <img
                  src={activeCandidateBuffer[0]?.specs?.display_image || activeCandidateBuffer[0]?.specs?.image_url || 'https://via.placeholder.com/40'}
                  alt="Runner-up"
                  style={{ width: 36, height: 36, borderRadius: 4, objectFit: 'cover' }}
                />
                <div style={{ flex: 1, overflow: 'hidden' }}>
                  <div style={{ fontSize: '0.75rem', fontWeight: 600, whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>
                    {activeCandidateBuffer[0]?.title}
                  </div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                    {curr}{activeCandidateBuffer[0]?.price} (Size {userProfile?.defaultSize || 'XL'} Ready)
                  </div>
                </div>
                <button
                  className="btn btn-sm"
                  style={{ background: 'rgba(99, 102, 241, 0.15)', color: '#a5b4fc', border: '1px solid rgba(99,102,241,0.3)', padding: '4px 8px', fontSize: '0.7rem', whiteSpace: 'nowrap' }}
                  onClick={() => handleSubstituteItem(cartProducts[0], activeCandidateBuffer[0])}
                  title="Simulate Out-Of-Stock on Item #1 and substitute with pre-fetched buffer"
                >
                  <RefreshCw size={11} /> Test OOS Swap
                </button>
              </div>
            </div>
          )}

          {/* Checkout Section */}
          <CheckoutSection
            cartItemsPayload={cartItemsPayload}
            rawTotal={rawTotal}
            currency={config.currency}
            customerEmail={config.customerEmail}
            demoMode={config.demoMode}
            onDemoModeChange={(m) => updateConfig({ demoMode: m })}
            onSuccess={onClose}
            autoStartCascade={autoStartCascade}
            onResetAutoStartCascade={onResetAutoStartCascade}
          />
        </div>
      </div>
    </>
  )
}
