import { useState } from 'react'
import { CreditCard, Bot, Zap } from 'lucide-react'
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

export default function CheckoutSection({ cartItemsPayload, rawTotal, currency, customerEmail, demoMode, onDemoModeChange, onSuccess }) {
  const { razorpayToken, setRazorpayToken, razorpayCustomerId, setRazorpayCustomerId, clearCart } = useApp()
  const [loading, setLoading] = useState(false)
  const curr = currency === 'INR' ? '₹' : '$'

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
        prefill: { name: 'Rasor User', email: customerEmail, contact: '9999999999' },
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
              email: customerEmail,
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
        prefill: { name: 'Agentic User', email: customerEmail, contact: '9999999999' },
        theme: { color: '#10b981' },
        handler: async (response) => {
          toast.loading('Verifying & syncing…', { id: 'demo1' })
          try {
            const { data: vd } = await verifyPayment({
              payment_id: response.razorpay_payment_id,
              order_id: data.order_id,
            })
            if (!vd.valid) { toast.error('Verification failed!', { id: 'demo1' }); return }

            // Simulate token save (TokenHQ/UAP not yet open-pilot)
            const mockToken = `tok_mock_${Math.random().toString(36).slice(2, 10)}`
            setRazorpayToken(mockToken)
            setRazorpayCustomerId(data.customer_id || `cust_${Date.now()}`)

            const { data: syncData } = await syncShopify({
              cart_items: cartItemsPayload,
              currency,
              final_total: rawTotal,
              order_id: data.order_id,
              email: customerEmail,
            })

            if (syncData.success) {
              toast.success(`✅ Mandate set! Order ${syncData.order_name} synced. Token saved for Demo 2.`, { id: 'demo1', duration: 6000 })
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

  // ── Demo 2: Autonomous S2S ────────────────────────────────
  const handleDemo2 = async () => {
    const tokenId = razorpayToken || 'token_s2s_mock_123'
    const customerId = razorpayCustomerId || 'cust_s2s_mock_456'

    if (!razorpayToken) {
      toast('No real token found. Using mock token for demo.', { icon: '⚠️' })
    }

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
        email: customerEmail,
      })

      if (syncData.success) {
        toast.success(`✅ S2S Capture! Shopify Order: ${syncData.order_name}`, { duration: 6000 })
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
      <div className="checkout-section" style={{ border: '1px solid rgba(99,102,241,0.3)' }}>
        <h3>🔒 Agentic Checkout — Track 01</h3>

        {/* Demo mode radio */}
        <div className="radio-group">
          <button
            className={`radio-option ${demoMode === 'human_present' ? 'selected' : ''}`}
            onClick={() => onDemoModeChange('human_present')}
          >Demo 1: Initial Purchase</button>
          <button
            className={`radio-option ${demoMode === 'autonomous_s2s' ? 'selected' : ''}`}
            onClick={() => onDemoModeChange('autonomous_s2s')}
          >Demo 2: Autonomous S2S</button>
        </div>

        {demoMode === 'human_present' ? (
          <>
            <div className="mandate-banner">
              <strong>📝 Mandate Authorization</strong><br />
              I explicitly authorize Rasor Agent to create an order for up to <strong>{curr}{rawTotal.toFixed(0)}</strong> on my behalf.
              I will complete the payment on the merchant's secure page, which establishes consent for future autonomous purchases (AP2 pattern).
            </div>
            <button className="btn btn-primary btn-full" onClick={handleDemo1} disabled={loading}>
              {loading ? <span className="spinner" /> : '✅ Approve Mandate & Pay'}
            </button>
          </>
        ) : (
          <>
            <div className="s2s-banner">
              <strong>🤖 Autonomous S2S Capture</strong><br />
              The agent executes this <strong>server-to-server</strong> using the saved token from your previous mandate, provided it is under your spend limit.
              <div className="s2s-note">
                <strong>Note on Implementation:</strong> Because NPCI's UAP (Unified AutoPay) and Razorpay's UPI Reserve Pay are still closed-pilot, we demonstrate the identical trust pattern (one-time consent, then bounded autonomous execution) by simulating the final S2S network call. The architecture is rail-agnostic; swapping the simulated mock for real UPI once that pilot opens is a configuration change, not a redesign.
              </div>
            </div>
            {razorpayToken && (
              <div className="alert alert-success" style={{ fontSize: '0.78rem' }}>
                🔐 Token Active: <code>{razorpayToken}</code>
              </div>
            )}
            <button className="btn btn-purple btn-full" onClick={handleDemo2} disabled={loading}>
              {loading ? <span className="spinner" /> : <><Bot size={16} /> Execute Autonomous Payment</>}
            </button>
          </>
        )}
      </div>
    </div>
  )
}
