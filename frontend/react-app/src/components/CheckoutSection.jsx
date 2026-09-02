import React, { useState } from 'react'
import { 
  CreditCard, Bot, Zap, ShieldAlert, Key, 
  AlertTriangle, ArrowRight, X, Sliders
} from 'lucide-react'
import { createOrder, createMandateOrder, captureS2S, verifyPayment, syncShopify } from '../api/client'
import { useApp } from '../context/AppContext'
import toast from 'react-hot-toast'

function loadRazorpayScript() {
  return new Promise((resolve) => {
    if (document.querySelector('script[src*="checkout.razorpay"]')) {
      resolve(true); return
    }
    const script = document.createElement('script')
    script.src = 'https://checkout.razorpay.com/v1/checkout.js'
    script.onload = () => resolve(true)
    script.onerror = () => resolve(false)
    document.body.appendChild(script)
  })
}

export default function CheckoutSection({ 
  cartItemsPayload, 
  rawTotal, 
  currency, 
  customerEmail, 
  demoMode, 
  onDemoModeChange, 
  onSuccess 
}) {
  const { 
    razorpayToken, 
    razorpayCustomerId, 
    tokenMaxLimit, 
    saveMandateToken, 
    updateMandateLimit,
    clearMandateToken,
    clearCart, 
    config,
    updateConfig
  } = useApp()
  
  const [loading, setLoading] = useState(false)
  const [showInPlaceControls, setShowInPlaceControls] = useState(false)
  const [guardrailModal, setGuardrailModal] = useState(null)
  const curr = currency === 'INR' ? '₹' : '$'

  const effectiveEmail = customerEmail || config.customerEmail || 'vipulapatil21@gmail.com'
  const effectiveLimit = Number(tokenMaxLimit || 0)
  const autonomousCap = Number(config.maxCostHitl || 2000)

  // ── Standard Checkout ─────────────────────────────────────
  const handleStandardCheckout = async () => {
    setLoading(true)
    try {
      const loaded = await loadRazorpayScript()
      if (!loaded) { toast.error('Could not load Razorpay'); return }

      const { data } = await createOrder({
        cart_items: cartItemsPayload,
        currency,
        final_total: rawTotal,
        cart_id: `cart_std_${Date.now()}`,
      })

      if (!data.success) { toast.error('Order creation failed: ' + data.error); return }

      const rzp = new window.Razorpay({
        key: data.key_id,
        amount: data.amount,
        currency: data.currency,
        name: 'Rasor Commerce',
        description: 'Standard One-Off Purchase',
        order_id: data.order_id,
        prefill: { name: 'Rasor User', email: effectiveEmail, contact: '9999999999' },
        theme: { color: '#3b82f6' },
        handler: async (response) => {
          toast.loading('Verifying payment…', { id: 'verify' })
          try {
            const { data: vd } = await verifyPayment({
              payment_id: response.razorpay_payment_id,
              order_id: data.order_id,
            })
            if (!vd.valid) {
              toast.error('Payment verification failed!', { id: 'verify' })
              return
            }
            // Sync to Shopify
            const { data: syncData } = await syncShopify({
              cart_items: cartItemsPayload,
              currency,
              final_total: rawTotal,
              order_id: data.order_id,
              email: effectiveEmail,
            })
            if (syncData.success) {
              toast.success(`✅ Order ${syncData.order_name} synced to Shopify!`, { id: 'verify', duration: 5000 })
              clearCart()
              onSuccess?.()
            } else {
              toast.error('Shopify sync failed: ' + syncData.error, { id: 'verify' })
            }
          } catch (err) {
            toast.error('Verification error: ' + err.message, { id: 'verify' })
          }
        },
        modal: {
          ondismiss: () => toast('Checkout closed without payment', { icon: '💡' })
        }
      })
      rzp.on('payment.failed', (resp) => {
        toast.error('Payment failed: ' + resp.error.description)
      })
      rzp.open()
    } catch (err) {
      toast.error('Error: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  // ── Demo 1: Mandate (Human Present) ──────────────────────
  const handleDemo1 = async () => {
    setLoading(true)
    try {
      const loaded = await loadRazorpayScript()
      if (!loaded) { toast.error('Could not load Razorpay'); return }

      const { data } = await createMandateOrder({
        cart_items: cartItemsPayload,
        currency,
        final_total: rawTotal,
        cart_id: `cart_d1_${Date.now()}`,
      })

      if (!data.success) { toast.error('Order creation failed: ' + data.error); return }

      const rzp = new window.Razorpay({
        key: data.key_id,
        amount: data.amount,
        currency: data.currency,
        name: 'Rasor Agentic Commerce',
        description: 'Initial Setup Purchase (AP2 Mandate Flow)',
        order_id: data.order_id,
        prefill: { name: 'Agentic User', email: effectiveEmail, contact: '9999999999' },
        theme: { color: '#10b981' },
        handler: async (response) => {
          toast.loading('Verifying & establishing mandate…', { id: 'demo1' })
          try {
            const { data: vd } = await verifyPayment({
              payment_id: response.razorpay_payment_id,
              order_id: data.order_id,
            })
            if (!vd.valid) { toast.error('Verification failed!', { id: 'demo1' }); return }

            // Save recurring token & set/update mandate max limit for this customer email
            const tokenGen = `tok_mandate_${Math.random().toString(36).slice(2, 10)}`
            saveMandateToken(tokenGen, razorpayCustomerId, rawTotal, effectiveEmail)

            const { data: syncData } = await syncShopify({
              cart_items: cartItemsPayload,
              currency,
              final_total: rawTotal,
              order_id: data.order_id,
              email: effectiveEmail,
            })

            if (syncData.success) {
              toast.success(`✅ Mandate Established for ${effectiveEmail}! Synced Order ${syncData.order_name}. Authorized up to ${curr}${rawTotal.toFixed(0)} for Demo 2.`, { id: 'demo1', duration: 6000 })
              clearCart()
              onSuccess?.()
            } else {
              toast.error('Shopify sync failed: ' + syncData.error, { id: 'demo1' })
            }
          } catch (err) {
            toast.error('Error: ' + err.message, { id: 'demo1' })
          }
        },
        modal: { ondismiss: () => toast('Checkout closed', { icon: '💡' }) }
      })
      rzp.on('payment.failed', (resp) => {
        toast.error('Payment failed: ' + resp.error.description)
      })
      rzp.open()
    } catch (err) {
      toast.error('Error: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  // ── Demo 2: Autonomous S2S Execution & Constraint Validation ────────────────
  const handleDemo2 = async () => {
    // 1. Constraint: Token existence check
    if (!razorpayToken) {
      setGuardrailModal({
        type: 'NO_TOKEN',
        title: '🔑 Mandate Token Required',
        message: `No active mandate token found for ${effectiveEmail}.\n\nTo use Demo 2 (Autonomous S2S), you must complete an authenticated purchase in Demo 1 (Human Present) first to establish and save your recurring mandate token.`,
        actionText: 'Switch to Demo 1 & Pay',
        onAction: () => {
          setGuardrailModal(null)
          onDemoModeChange('human_present')
        }
      })
      return
    }

    // 2. Constraint: Token authorized limit check
    if (effectiveLimit > 0 && rawTotal > effectiveLimit) {
      setGuardrailModal({
        type: 'TOKEN_LIMIT_EXCEEDED',
        title: '🚫 Mandate Token Limit Exceeded',
        message: `Your saved mandate token for ${effectiveEmail} is authorized for purchases up to ${curr}${effectiveLimit.toLocaleString()}, but this order total is ${curr}${rawTotal.toFixed(0)}.\n\nTransactions exceeding your mandate limit require you to complete the purchase in Demo 1 (Human Present) to authorize this higher limit.`,
        actionText: `Switch to Demo 1 & Authorize ${curr}${rawTotal.toFixed(0)}`,
        onAction: () => {
          setGuardrailModal(null)
          onDemoModeChange('human_present')
        }
      })
      return
    }

    // 3. Constraint: Autonomous safety hard cap from settings
    if (rawTotal > autonomousCap) {
      setGuardrailModal({
        type: 'AUTONOMOUS_HARD_CAP',
        title: '🛡️ Autonomous Safety Hard Cap Triggered',
        message: `This order total (${curr}${rawTotal.toFixed(0)}) exceeds your Demo 2 autonomous safety hard cap (${curr}${autonomousCap.toLocaleString()}).\n\nPer AP2 financial guardrails, autonomous server-to-server payments cannot execute above this safety threshold without human confirmation.`,
        actionText: 'Proceed via Demo 1 (Human Present)',
        onAction: () => {
          setGuardrailModal(null)
          onDemoModeChange('human_present')
        }
      })
      return
    }

    // All constraints passed -> Execute S2S Capture
    const tokenId = razorpayToken
    const customerId = razorpayCustomerId || 'cust_s2s_user'

    setLoading(true)
    try {
      const { data } = await captureS2S({
        cart_items: cartItemsPayload,
        currency,
        final_total: rawTotal,
        token_id: tokenId,
        customer_id: customerId,
        cart_id: `cart_s2s_${Date.now()}`,
      })

      if (!data.success) { toast.error('S2S capture failed: ' + data.error); return }

      const { data: syncData } = await syncShopify({
        cart_items: cartItemsPayload,
        currency,
        final_total: rawTotal,
        order_id: data.payment_id,
        email: effectiveEmail,
      })

      if (syncData.success) {
        toast.success(`✅ S2S Capture Authorized! Shopify Order: ${syncData.order_name}`, { duration: 6000 })
        clearCart()
        onSuccess?.()
      } else {
        toast(`S2S succeeded, Shopify sync issue: ${syncData.error}`, { icon: '⚠️' })
      }
    } catch (err) {
      toast.error('Error: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* ── Standard Checkout ── */}
      <div className="checkout-section">
        <h3><CreditCard size={18} color="var(--accent-blue)" /> Standard Checkout</h3>
        <p className="text-sm text-muted">
          Normal, non-recurring Razorpay transaction. Supports UPI, Cards, Netbanking, and all test payment methods.
        </p>
        <button className="btn btn-full" style={{ background: 'linear-gradient(135deg, #3b82f6, #1d4ed8)', color: '#fff' }} onClick={handleStandardCheckout} disabled={loading}>
          {loading ? <span className="spinner" /> : <><CreditCard size={16} /> Pay {curr}{rawTotal.toFixed(0)} (Standard)</>}
        </button>
      </div>

      {/* ── Agentic Checkout ── */}
      <div className="checkout-section" style={{ border: '1px solid rgba(99,102,241,0.35)', background: 'rgba(15, 23, 42, 0.65)' }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 10 }}>
          <h3 style={{ margin: 0 }}>🔒 Agentic Checkout — AP2 Mandate Flow</h3>
          <button 
            className="btn btn-ghost btn-xs"
            onClick={() => setShowInPlaceControls(!showInPlaceControls)}
            style={{ fontSize: '0.74rem', color: '#a5b4fc', display: 'flex', alignItems: 'center', gap: 4 }}
          >
            <Sliders size={12} /> {showInPlaceControls ? 'Hide Overrides' : 'In-Place Overrides'}
          </button>
        </div>

        {/* Demo mode radio tabs - Free and active switching */}
        <div className="radio-group" style={{ marginBottom: 12 }}>
          <button
            className={`radio-option ${demoMode === 'human_present' ? 'selected' : ''}`}
            onClick={() => onDemoModeChange('human_present')}
          >
            Demo 1: Initial Purchase
          </button>
          <button
            className={`radio-option ${demoMode === 'autonomous_s2s' ? 'selected' : ''}`}
            onClick={() => onDemoModeChange('autonomous_s2s')}
          >
            Demo 2: Autonomous S2S
          </button>
        </div>

        {/* Optional In-Place Mandate Overrides Accordion for Testing */}
        {showInPlaceControls && (
          <div style={{ 
            padding: '12px 14px', 
            background: 'rgba(99, 102, 241, 0.08)', 
            border: '1px solid rgba(99, 102, 241, 0.25)', 
            borderRadius: 8, 
            marginBottom: 12,
            fontSize: '0.78rem'
          }}>
            <div style={{ fontWeight: 700, color: '#e0e7ff', marginBottom: 6 }}>
              🛠️ In-Place Mandate Controls ({effectiveEmail}):
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 }}>
              <div>
                <span className="text-muted" style={{ display: 'block', fontSize: '0.7rem' }}>Customer ID:</span>
                <code style={{ fontSize: '0.72rem', color: '#93c5fd' }}>{razorpayCustomerId}</code>
              </div>
              <div>
                <span className="text-muted" style={{ display: 'block', fontSize: '0.7rem' }}>Token ID:</span>
                <code style={{ fontSize: '0.72rem', color: razorpayToken ? '#34d399' : '#f87171' }}>
                  {razorpayToken || 'None'}
                </code>
              </div>
            </div>

            <div className="flex items-center justify-between" style={{ flexWrap: 'wrap', gap: 8 }}>
              <div className="flex items-center gap-2">
                <span>Authorized Limit:</span>
                <input 
                  type="number" 
                  value={tokenMaxLimit || 0}
                  onChange={e => updateMandateLimit(Number(e.target.value), effectiveEmail)}
                  style={{ width: 80, padding: '3px 6px', fontSize: '0.75rem', background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.2)', borderRadius: 4, color: '#fff' }}
                />
              </div>

              <div className="flex gap-2">
                <button 
                  className="btn btn-secondary btn-xs"
                  onClick={() => {
                    const testTok = `tok_test_${Math.random().toString(36).slice(2, 9)}`
                    saveMandateToken(testTok, razorpayCustomerId, Math.max(rawTotal, 800), effectiveEmail)
                    toast.success(`Set test token authorized up to ${curr}${Math.max(rawTotal, 800)}!`)
                  }}
                  style={{ fontSize: '0.7rem', padding: '3px 8px' }}
                >
                  + Set Test Token
                </button>
                {razorpayToken && (
                  <button 
                    className="btn btn-ghost btn-xs"
                    onClick={() => { clearMandateToken(effectiveEmail); toast('Token cleared', { icon: '🗑️' }) }}
                    style={{ color: '#fca5a5', fontSize: '0.7rem' }}
                  >
                    Clear
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {demoMode === 'human_present' ? (
          <>
            <div className="mandate-banner">
              <strong>📝 Mandate Authorization for {effectiveEmail}</strong><br />
              Authorizes the agent to place this order up to <strong>{curr}{rawTotal.toFixed(0)}</strong>.
              Completing this payment on the secure page establishes and saves your recurring mandate token for future Demo 2 autonomous purchases.
            </div>
            <button className="btn btn-primary btn-full" onClick={handleDemo1} disabled={loading}>
              {loading ? <span className="spinner" /> : `✅ Approve Mandate & Pay ${curr}${rawTotal.toFixed(0)}`}
            </button>
          </>
        ) : (
          <>
            <div className="s2s-banner">
              <strong>🤖 Autonomous S2S Capture ({effectiveEmail})</strong><br />
              Executes <strong>server-to-server</strong> using your saved mandate token (Token Limit: <strong>{curr}{tokenMaxLimit || 0}</strong>, Autonomous Cap: <strong>{curr}{autonomousCap}</strong>).
            </div>

            {razorpayToken ? (
              <div className="alert alert-success" style={{ fontSize: '0.76rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
                <div>
                  🔐 <strong>Token Active:</strong> <code style={{ fontSize: '0.72rem' }}>{razorpayToken}</code>
                </div>
                <span className="badge badge-green" style={{ fontSize: '0.68rem' }}>
                  Max Limit: {curr}{tokenMaxLimit || rawTotal.toFixed(0)}
                </span>
              </div>
            ) : (
              <div className="alert alert-warning" style={{ fontSize: '0.76rem', marginBottom: 12 }}>
                ⚠️ <strong>Note:</strong> No mandate token currently saved for {effectiveEmail}. Clicking execute will prompt to set up Demo 1.
              </div>
            )}

            <button className="btn btn-purple btn-full" onClick={handleDemo2} disabled={loading}>
              {loading ? <span className="spinner" /> : <><Bot size={16} /> Execute Autonomous Payment ({curr}{rawTotal.toFixed(0)})</>}
            </button>
          </>
        )}
      </div>

      {/* ── Guardrail Modal Popup with 1-Click Action ── */}
      {guardrailModal && (
        <div style={{
          position: 'fixed', inset: 0,
          background: 'rgba(0, 0, 0, 0.75)',
          backdropFilter: 'blur(6px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 9999, padding: 20
        }}>
          <div className="card animate-fade-in" style={{
            maxWidth: 480, width: '100%',
            padding: '24px',
            background: 'linear-gradient(135deg, #1e1b4b, #0f172a)',
            border: '1px solid rgba(99, 102, 241, 0.4)',
            boxShadow: '0 20px 40px rgba(0, 0, 0, 0.6)'
          }}>
            <div className="flex items-center justify-between" style={{ marginBottom: 14 }}>
              <div className="flex items-center gap-2">
                {guardrailModal.type === 'NO_TOKEN' && <Key size={22} color="#fbbf24" />}
                {guardrailModal.type === 'TOKEN_LIMIT_EXCEEDED' && <ShieldAlert size={22} color="#f87171" />}
                {guardrailModal.type === 'AUTONOMOUS_HARD_CAP' && <AlertTriangle size={22} color="#f87171" />}
                <h3 style={{ fontSize: '1.1rem', fontWeight: 700, margin: 0, color: '#fff' }}>
                  {guardrailModal.title}
                </h3>
              </div>
              <button 
                onClick={() => setGuardrailModal(null)}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
              >
                <X size={18} />
              </button>
            </div>

            <p style={{ fontSize: '0.84rem', color: '#cbd5e1', lineHeight: 1.5, whiteSpace: 'pre-line', marginBottom: 20 }}>
              {guardrailModal.message}
            </p>

            <div className="flex items-center justify-end gap-3">
              <button 
                className="btn btn-ghost btn-sm"
                onClick={() => setGuardrailModal(null)}
              >
                Cancel
              </button>
              <button 
                className="btn btn-primary btn-sm"
                onClick={guardrailModal.onAction}
                style={{ display: 'flex', alignItems: 'center', gap: 6 }}
              >
                {guardrailModal.actionText} <ArrowRight size={14} />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
