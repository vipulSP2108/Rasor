import React, { useState } from 'react';
import { X, Minus, Plus, Trash2, ShoppingBag, ExternalLink, Sparkles, ShieldCheck, RefreshCw, Sliders, AlertTriangle, ShieldAlert, Volume2, VolumeX } from 'lucide-react'
import { useApp } from '../context/AppContext'
import { useVoice } from '../hooks/useVoice'
import CheckoutSection from './CheckoutSection'
import toast from 'react-hot-toast'

export default function CartDrawer({ onClose, autoStartCascade = false, onResetAutoStartCascade }) {
  const { 
    cart, removeFromCart, updateQty, clearCart, 
    config, updateConfig, candidateBuffer = [], 
    addToCartLocal, userProfile,
    simulatedOosCount = 0, setSimulatedOosCount,
    simulatedOosRemaining, setSimulatedOosRemaining,
    simulatePostPaymentOos = false, setSimulatePostPaymentOos
  } = useApp()
  const { speak, voiceChannels, setVoiceChannel } = useVoice()
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

          {/* OOS Pre-Fetched Buffer & Dual-Phase Resilience Safeguards Card */}
          {activeCandidateBuffer.length > 0 && cartProducts.length > 0 && (() => {
            const maxCached = activeCandidateBuffer.length
            const effectiveOosCount = Math.min(simulatedOosCount, maxCached)
            const previewCandidates = activeCandidateBuffer.slice(0, effectiveOosCount > 0 ? effectiveOosCount : 1)

            return (
              <div style={{
                background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.08), rgba(16, 185, 129, 0.05))',
                border: '1px solid rgba(99, 102, 241, 0.3)',
                borderRadius: 8, padding: '12px 14px', marginBottom: 14
              }}>
                {/* Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <span style={{ fontSize: '0.76rem', fontWeight: 700, color: '#a5b4fc', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Sparkles size={13} /> Pre-Fetched Runner-Up Buffer ({maxCached} cached)
                  </span>
                  <span className="badge badge-purple" style={{ fontSize: '0.66rem' }}>Zero-Latency Cache</span>
                </div>

                {/* ── Phase 1: Pre-Payment Inventory Check ── */}
                <div style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '7px 10px', background: 'rgba(0,0,0,0.3)', borderRadius: 6,
                  border: '1px solid rgba(255,255,255,0.08)', margin: '6px 0 4px 0'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <label style={{ fontSize: '0.74rem', fontWeight: 600, color: '#e2e8f0', display: 'flex', alignItems: 'center', gap: 6, margin: 0 }}>
                      <Sliders size={13} color="#a5b4fc" /> Pre-Payment OOS Swaps:
                    </label>
                    <button
                      type="button"
                      onClick={() => {
                        const next = !voiceChannels.inventoryOos
                        setVoiceChannel('inventoryOos', next)
                        toast(next ? 'Voice alerts enabled for OOS Swaps' : 'Voice alerts muted for OOS Swaps', { icon: next ? '🔊' : '🔇' })
                      }}
                      style={{
                        background: voiceChannels.inventoryOos ? 'rgba(74, 222, 128, 0.15)' : 'rgba(255, 255, 255, 0.05)',
                        border: voiceChannels.inventoryOos ? '1px solid rgba(74, 222, 128, 0.4)' : '1px solid rgba(255, 255, 255, 0.1)',
                        borderRadius: 4,
                        cursor: 'pointer',
                        padding: '2px 5px',
                        display: 'inline-flex',
                        alignItems: 'center',
                        color: voiceChannels.inventoryOos ? '#4ade80' : '#94a3b8'
                      }}
                      title={voiceChannels.inventoryOos ? "Voice active for OOS Swaps (click to mute)" : "Voice muted for OOS Swaps (click to enable)"}
                    >
                      {voiceChannels.inventoryOos ? <Volume2 size={11} /> : <VolumeX size={11} />}
                    </button>
                  </div>
                  <select
                    value={effectiveOosCount}
                    onChange={(e) => {
                      const val = Number(e.target.value)
                      setSimulatedOosCount(val)
                      if (val > 0) {
                        toast(`Pre-payment OOS set to ${val} swap(s). Injects qty: 0 at checkout.`, { icon: '⚙️' })
                      } else {
                        toast('Pre-payment OOS disabled (Direct checkout).', { icon: '✅' })
                      }
                    }}
                    style={{
                      background: '#1e1b4b',
                      color: '#c7d2fe',
                      border: '1px solid #6366f1',
                      borderRadius: 4,
                      padding: '3px 8px',
                      fontSize: '0.74rem',
                      fontWeight: 700,
                      cursor: 'pointer'
                    }}
                  >
                    <option value={0}>0 — Direct Success (0 Pre-Swaps)</option>
                    {Array.from({ length: maxCached }, (_, i) => i + 1).map(num => (
                      <option key={num} value={num}>
                        {num} — {num} Fallback{num > 1 ? 's' : ''} ({num} OOS Swap{num > 1 ? 's' : ''})
                      </option>
                    ))}
                  </select>
                </div>

                {/* Pre-Payment explanatory text (Clean block layout) */}
                <div style={{ fontSize: '0.71rem', color: '#94a3b8', lineHeight: 1.45, margin: '2px 0 8px 0' }}>
                  {effectiveOosCount === 0 ? (
                    <span>Direct checkout active. Set to 1–{maxCached} to test pre-payment zero-latency buffer substitution.</span>
                  ) : (
                    <div style={{ color: '#fbbf24', marginTop: 2 }}>
                      ⚡ Injects <code style={{ background: 'rgba(255,255,255,0.08)', padding: '1px 5px', borderRadius: 3, color: '#fde68a' }}>quantity: 0</code> for <strong>{effectiveOosCount} item(s)</strong> at checkout. Swaps from buffer with 0ms delay, then auto-cascades to Demo 3.
                    </div>
                  )}
                </div>

                {/* ── Phase 2: Post-Payment Collision (Instant Refund) ── */}
                <div style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '7px 10px', background: 'rgba(0,0,0,0.3)', borderRadius: 6,
                  border: simulatePostPaymentOos ? '1px solid rgba(239, 68, 68, 0.4)' : '1px solid rgba(255,255,255,0.08)',
                  margin: '6px 0 4px 0'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <label style={{ fontSize: '0.74rem', fontWeight: 600, color: '#e2e8f0', display: 'flex', alignItems: 'center', gap: 6, margin: 0 }}>
                      <ShieldAlert size={13} color={simulatePostPaymentOos ? '#f87171' : '#a5b4fc'} /> Post-Payment Collision:
                    </label>
                    <button
                      type="button"
                      onClick={() => {
                        const next = !voiceChannels.postRefund
                        setVoiceChannel('postRefund', next)
                        toast(next ? 'Voice alerts enabled for Post-Refund' : 'Voice alerts muted for Post-Refund', { icon: next ? '🔊' : '🔇' })
                      }}
                      style={{
                        background: voiceChannels.postRefund ? 'rgba(74, 222, 128, 0.15)' : 'rgba(255, 255, 255, 0.05)',
                        border: voiceChannels.postRefund ? '1px solid rgba(74, 222, 128, 0.4)' : '1px solid rgba(255, 255, 255, 0.1)',
                        borderRadius: 4,
                        cursor: 'pointer',
                        padding: '2px 5px',
                        display: 'inline-flex',
                        alignItems: 'center',
                        color: voiceChannels.postRefund ? '#4ade80' : '#94a3b8'
                      }}
                      title={voiceChannels.postRefund ? "Voice active for Post-Refund (click to mute)" : "Voice muted for Post-Refund (click to enable)"}
                    >
                      {voiceChannels.postRefund ? <Volume2 size={11} /> : <VolumeX size={11} />}
                    </button>
                  </div>
                  <button
                    type="button"
                    className="btn btn-xs"
                    style={{
                      padding: '3px 9px', fontSize: '0.7rem', fontWeight: 700,
                      background: simulatePostPaymentOos ? '#ef4444' : 'rgba(255,255,255,0.08)',
                      color: '#fff', border: simulatePostPaymentOos ? '1px solid #dc2626' : '1px solid rgba(255,255,255,0.2)'
                    }}
                    onClick={() => {
                      const next = !simulatePostPaymentOos
                      setSimulatePostPaymentOos(next)
                      if (next) {
                        toast('Post-Payment Collision Active! Payment will succeed, server will report sold out, and agent will issue instant 100% refund.', { icon: '🚨', duration: 4500 })
                      } else {
                        toast('Post-Payment Collision disabled. Normal order fulfillment active.', { icon: '✅' })
                      }
                    }}
                  >
                    {simulatePostPaymentOos ? 'ACTIVE (Simulate Refund)' : 'DISABLED'}
                  </button>
                </div>

                <div style={{ fontSize: '0.71rem', color: '#94a3b8', lineHeight: 1.45, margin: '2px 0 10px 0' }}>
                  {simulatePostPaymentOos ? (
                    <div style={{ color: '#f87171', marginTop: 2 }}>
                      🚨 <strong>Race Condition Mode:</strong> Payment captures successfully. Then server simulates <em>"Sold out during checkout"</em>. Agent halts fulfillment, issues <strong>100% Instant AP2 Refund</strong> via Razorpay, and presents runner-up re-order.
                    </div>
                  ) : (
                    <span>Toggle ON to test post-payment inventory collision and autonomous instant refund recovery.</span>
                  )}
                </div>

                {/* Pre-Fetched Runner-Up Item Preview(s) - Shows ALL selected candidates */}
                <div style={{ fontSize: '0.7rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 5 }}>
                  Runner-Up Queue ({previewCandidates.length} displayed of {maxCached} cached):
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: '220px', overflowY: 'auto' }}>
                  {previewCandidates.map((cand, idx) => (
                    <div key={cand.id || idx} style={{
                      display: 'flex', gap: 8, alignItems: 'center',
                      background: 'rgba(255,255,255,0.03)', padding: '6px 8px', borderRadius: 5,
                      border: '1px solid rgba(255,255,255,0.06)'
                    }}>
                      <img
                        src={cand?.specs?.display_image || cand?.specs?.image_url || 'https://via.placeholder.com/34'}
                        alt="Runner-up"
                        style={{ width: 34, height: 34, borderRadius: 4, objectFit: 'cover' }}
                      />
                      <div style={{ flex: 1, overflow: 'hidden' }}>
                        <div style={{ fontSize: '0.74rem', fontWeight: 600, whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>
                          {cand?.title}
                        </div>
                        <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
                          {curr}{cand?.price} · {cand?.merchant || 'Rasor'} (Size {userProfile?.defaultSize || 'XL'} Ready)
                        </div>
                      </div>
                      <span className="badge badge-purple" style={{ fontSize: '0.64rem', padding: '2px 6px', whiteSpace: 'nowrap' }}>
                        Fallback #{idx + 1}
                      </span>
                    </div>
                  ))}
                </div>

                {/* Action Button */}
                <div style={{ marginTop: 10 }}>
                  <button
                    type="button"
                    className="btn btn-sm btn-full"
                    style={{
                      background: (effectiveOosCount > 0 || simulatePostPaymentOos)
                        ? 'linear-gradient(135deg, rgba(99, 102, 241, 0.35), rgba(245, 158, 11, 0.35))' 
                        : 'rgba(99, 102, 241, 0.15)',
                      color: (effectiveOosCount > 0 || simulatePostPaymentOos) ? '#fde68a' : '#a5b4fc',
                      border: (effectiveOosCount > 0 || simulatePostPaymentOos) ? '1px solid #f59e0b' : '1px solid rgba(99,102,241,0.3)',
                      padding: '7px 10px', fontSize: '0.74rem', fontWeight: 700,
                      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6
                    }}
                    onClick={() => {
                      if (effectiveOosCount === 0 && !simulatePostPaymentOos) {
                        handleSubstituteItem(cartProducts[0], activeCandidateBuffer[0])
                      } else {
                        setSimulatedOosRemaining(effectiveOosCount)
                        updateConfig({ demoMode: 'cascade_failover' })
                        window.dispatchEvent(new CustomEvent('rasor:start-oos-cascade', { detail: { count: effectiveOosCount } }))
                      }
                    }}
                  >
                    {effectiveOosCount > 0 ? (
                      <>⚡ Run Pre-Check Cascade ({effectiveOosCount}x) {simulatePostPaymentOos ? '+ Post-Refund' : '→ Demo 3'}</>
                    ) : simulatePostPaymentOos ? (
                      <>⚡ Run Checkout + Post-Payment Collision Refund</>
                    ) : (
                      <><RefreshCw size={11} /> Test Instant Single Swap</>
                    )}
                  </button>
                </div>
              </div>
            )
          })()}

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
