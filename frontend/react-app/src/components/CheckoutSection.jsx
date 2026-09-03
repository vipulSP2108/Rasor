import React, { useState, useEffect, useRef } from 'react'
import { 
  CreditCard, Bot, Zap, ShieldAlert, Key, 
  AlertTriangle, ArrowRight, X, Sliders,
  RefreshCw, QrCode, PhoneCall, CheckCircle2,
  XCircle, ArrowDown, ExternalLink, ShieldCheck,
  Copy, Sparkles, Smartphone, Check, Clock, BellOff, Bell, RotateCcw
} from 'lucide-react'
import { 
  createOrder, createMandateOrder, captureS2S, 
  verifyPayment, syncShopify, createPaymentLink, 
  getPaymentLinkStatus, cancelPaymentLink, logFailover 
} from '../api/client'
import { useVoice } from '../hooks/useVoice'
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
    cart,
    config,
    updateConfig,
    userProfile
  } = useApp()
  
  const { speak } = useVoice()
  const [loading, setLoading] = useState(false)
  const [showInPlaceControls, setShowInPlaceControls] = useState(false)
  const [guardrailModal, setGuardrailModal] = useState(null)
  const curr = currency === 'INR' ? '₹' : '$'

  const effectiveEmail = customerEmail || config.customerEmail || userProfile?.email || 'vipulapatil21@gmail.com'
  const effectiveLimit = Number(tokenMaxLimit || 0)
  const autonomousCap = Number(config.maxCostHitl || 2000)

  // Only restore cascade state if an active, valid payment link session actually exists
  const hasActiveSession = () => {
    try {
      const raw = localStorage.getItem('rasor_active_plink')
      if (!raw) return false
      const parsed = JSON.parse(raw)
      return !!parsed?.plink_id
    } catch (e) {
      return false
    }
  }

  // Demo 3 Multi-Rail Failover States (persisted ONLY during active rescue sessions)
  const [cascadeStep, setCascadeStep] = useState(() => {
    if (!hasActiveSession()) return 0
    try {
      const saved = JSON.parse(localStorage.getItem('rasor_cascade_state'))
      return saved?.cascadeStep || 0
    } catch (e) { return 0 }
  })
  const [cascadeStatuses, setCascadeStatuses] = useState(() => {
    if (!hasActiveSession()) return { tier1: 'idle', tier2: 'idle', tier3: 'idle' }
    try {
      const saved = JSON.parse(localStorage.getItem('rasor_cascade_state'))
      return saved?.cascadeStatuses || {
        tier1: 'idle',
        tier2: 'idle',
        tier3: 'idle',
      }
    } catch (e) { return { tier1: 'idle', tier2: 'idle', tier3: 'idle' } }
  })
  const [activeOrderId, setActiveOrderId] = useState(null)
  const [activeKeyId, setActiveKeyId] = useState(null)
  const [activeAmountPaise, setActiveAmountPaise] = useState(null)
  const [pendingRail, setPendingRail] = useState(() => {
    if (!hasActiveSession()) return null
    try {
      const saved = JSON.parse(localStorage.getItem('rasor_cascade_state'))
      return saved?.pendingRail || null
    } catch (e) { return null }
  })
  const [copiedAssistCard, setCopiedAssistCard] = useState(false)
  const failedTierRef = useRef(null)

  // Auto-persist cascade state ONLY if a session is actively underway
  useEffect(() => {
    try {
      if (hasActiveSession() || pendingRail || cascadeStatuses.tier1 !== 'idle') {
        localStorage.setItem('rasor_cascade_state', JSON.stringify({
          cascadeStep,
          cascadeStatuses,
          pendingRail
        }))
      } else {
        localStorage.removeItem('rasor_cascade_state')
      }
    } catch (e) {}
  }, [cascadeStep, cascadeStatuses, pendingRail])

  const handleResetToDefault = (reason = 'cancelled') => {
    // 1. Reset Stepper & Cascade State
    setCascadeStep(0)
    setCascadeStatuses({ tier1: 'idle', tier2: 'idle', tier3: 'idle' })
    setPendingRail(null)
    setActiveOrderId(null)
    failedTierRef.current = null

    // 2. Reset Rescue Module State
    setPollingActive(false)
    setRemainingSeconds(0)
    setMobileRescueData(null)
    setIsRescueModuleActive(false)

    // 3. Clear LocalStorage caches
    try {
      localStorage.removeItem('rasor_cascade_state')
      localStorage.removeItem('rasor_active_plink')
      localStorage.setItem('rasor_rescue_module_active', 'false')
    } catch (e) {}

    if (reason === 'expired') {
      toast('⏳ Session expired. Reset to default checkout state.', { icon: '🔄', id: 'plink-exp' })
      speak('Payment link expired. Restored default checkout state.')
    } else if (reason === 'cancelled') {
      toast.success('🛑 Transaction cancelled. Reset to default checkout state.', { id: 'plink-cancel' })
      speak('Transaction cancelled. Restored default checkout state.')
    }
  }

  const handleResetCascade = () => {
    handleResetToDefault('reset')
    toast('Multi-rail cascade reset to initial state', { icon: '🔄' })
  }

  // Mobile WhatsApp / QR Rescue Module Active State (persisted)
  const [mobileRescueData, setMobileRescueData] = useState(null)
  const [isRescueModuleActive, setIsRescueModuleActive] = useState(() => {
    try {
      return localStorage.getItem('rasor_rescue_module_active') === 'true'
    } catch (e) {
      return false
    }
  })
  const [pollingActive, setPollingActive] = useState(false)
  const [remainingSeconds, setRemainingSeconds] = useState(900)

  // Auto-persist isRescueModuleActive
  useEffect(() => {
    try {
      localStorage.setItem('rasor_rescue_module_active', isRescueModuleActive ? 'true' : 'false')
    } catch (e) {}
  }, [isRescueModuleActive])

  // 1-second countdown ticker (decrements continuously without resetting)
  useEffect(() => {
    if (!mobileRescueData || !pollingActive) return
    const timer = setInterval(() => {
      setRemainingSeconds(prev => {
        if (prev <= 1) {
          clearInterval(timer)
          if (mobileRescueData?.plink_id) {
            cancelPaymentLink(mobileRescueData.plink_id).catch(() => {})
          }
          handleResetToDefault('expired')
          return 0
        }
        return prev - 1
      })
    }, 1000)
    return () => clearInterval(timer)
  }, [mobileRescueData?.plink_id, pollingActive, speak])

  const formatCountdown = (secs) => {
    const maxSecs = (config.paymentLinkExpiryMinutes || 15) * 60
    const clamped = Math.min(Math.max(0, secs), maxSecs)
    const m = Math.floor(clamped / 60)
    const s = clamped % 60
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  }

  // Explicit cancellation of mobile rescue link on Razorpay servers
  const handleCancelMobileRescue = async () => {
    if (mobileRescueData?.plink_id) {
      toast.loading('Cancelling payment link on Razorpay…', { id: 'plink-cancel' })
      try {
        await cancelPaymentLink(mobileRescueData.plink_id)
      } catch (err) {}
    }
    handleResetToDefault('cancelled')
  }

  // Hydrate active mobile rescue and query server for authoritative remaining seconds
  useEffect(() => {
    let isMounted = true
    const hydrateAndSyncWithServer = async () => {
      try {
        const raw = localStorage.getItem('rasor_active_plink')
        if (!raw) {
          // If there is no active link in storage, purge any stale cascade state immediately!
          handleResetToDefault('idle')
          return
        }
        const parsed = JSON.parse(raw)
        if (!parsed?.plink_id) {
          handleResetToDefault('idle')
          return
        }

        // Always query server for real-time authoritative status and seconds
        const { data } = await getPaymentLinkStatus(parsed.plink_id)
        if (!isMounted) return

        if (data.success && data.status === 'created' && data.remaining_seconds > 0) {
          setMobileRescueData(parsed.data)
          const maxSecs = (config.paymentLinkExpiryMinutes || 15) * 60
          setRemainingSeconds(Math.min(data.remaining_seconds, maxSecs))
          setPollingActive(true)
          const wasActive = localStorage.getItem('rasor_rescue_module_active') === 'true'
          if (wasActive) {
            setIsRescueModuleActive(true)
          }
        } else if (data.status === 'paid') {
          handleResetToDefault('paid')
          toast.success('🎉 Payment already captured on mobile!')
        } else {
          // Link expired, cancelled, or 0s remaining: Reset everything to default!
          handleResetToDefault('expired')
        }
      } catch (e) {
        console.error('[Hydration error]', e)
        handleResetToDefault('idle')
      }
    }
    hydrateAndSyncWithServer()
    return () => { isMounted = false }
  }, [])

  // Auto-cancel payment link if cart is emptied / cleared
  useEffect(() => {
    if ((mobileRescueData || isRescueModuleActive) && (!cartItemsPayload || cartItemsPayload.length === 0)) {
      handleCancelMobileRescue()
    }
  }, [cartItemsPayload, mobileRescueData, isRescueModuleActive])

  // Continuous polling and server-clock synchronization
  useEffect(() => {
    let interval = null
    if (pollingActive && mobileRescueData?.plink_id) {
      interval = setInterval(async () => {
        try {
          const { data } = await getPaymentLinkStatus(mobileRescueData.plink_id)
          if (data?.status === 'paid') {
            setPollingActive(false)
            clearInterval(interval)
            localStorage.removeItem('rasor_active_plink')
            toast.success('🎉 Mobile Payment Verified & Paid! Syncing to Shopify...', { duration: 6000 })
            speak('Mobile payment received successfully. Synchronizing order to Shopify.')
            
            // Sync to Shopify
            await syncShopify({
              cart_items: cartItemsPayload,
              currency,
              final_total: rawTotal,
              order_id: mobileRescueData.plink_id,
              email: effectiveEmail,
            })
            clearCart()
            onSuccess?.()
          } else if (data?.status === 'cancelled' || data?.status === 'expired') {
            setPollingActive(false)
            clearInterval(interval)
            localStorage.removeItem('rasor_active_plink')
            setMobileRescueData(null)
            toast.error('🛑 Payment link is cancelled or expired on server')
          } else if (data?.remaining_seconds !== undefined) {
            // Re-sync timer to exact authoritative server clock
            setRemainingSeconds(data.remaining_seconds)
          }
        } catch (err) {
          console.error('[Polling Error]', err)
        }
      }, 3000)
    }
    return () => {
      if (interval) clearInterval(interval)
    }
  }, [pollingActive, mobileRescueData?.plink_id, cartItemsPayload, currency, rawTotal, effectiveEmail, clearCart, onSuccess, speak])

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
        prefill: { 
          name: userProfile?.fullName || 'Rasor User', 
          email: effectiveEmail, 
          contact: userProfile?.phone || '9999999999' 
        },
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
              toast(`Payment verified, Shopify sync issue: ${syncData.error}`, { id: 'verify', icon: '⚠️' })
            }
          } catch (e) {
            toast.error('Sync error: ' + (e.response?.data?.detail || e.message), { id: 'verify' })
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

  // ── Demo 1: Mandate Authorization Flow ────────────────────
  const handleDemo1 = async () => {
    setLoading(true)
    try {
      const loaded = await loadRazorpayScript()
      if (!loaded) { toast.error('Could not load Razorpay'); return }

      const { data } = await createMandateOrder({
        cart_items: cartItemsPayload,
        currency,
        final_total: rawTotal,
        cart_id: `cart_mandate_${Date.now()}`,
      })

      if (!data.success) { toast.error('Order creation failed: ' + data.error); return }

      const cid = data.customer_id
      const orderId = data.order_id

      const rzp = new window.Razorpay({
        key: data.key_id,
        amount: data.amount,
        currency: data.currency,
        name: 'Rasor AP2 Mandate Flow',
        description: `Mandate Setup: Authorize up to ${curr}${rawTotal.toFixed(0)}`,
        order_id: orderId,
        customer_id: cid,
        prefill: { 
          name: userProfile?.fullName || 'Agentic User', 
          email: effectiveEmail, 
          contact: userProfile?.phone || '8806549952' 
        },
        theme: { color: '#6366f1' },
        handler: async (response) => {
          toast.loading('Verifying payment & saving mandate token…', { id: 'mandate-verify' })
          try {
            const { data: vd } = await verifyPayment({
              payment_id: response.razorpay_payment_id,
              order_id: orderId,
            })
            if (!vd.valid) {
              toast.error('Payment verification failed!', { id: 'mandate-verify' })
              return
            }

            const capturedToken = response.razorpay_token_id || `tok_${Math.random().toString(36).slice(2, 10)}`
            saveMandateToken(capturedToken, cid, rawTotal, effectiveEmail)

            const { data: syncData } = await syncShopify({
              cart_items: cartItemsPayload,
              currency,
              final_total: rawTotal,
              order_id: orderId,
              email: effectiveEmail,
            })

            toast.success(
              `🎉 Mandate Approved & Saved!\nToken: ${capturedToken}\nShopify Order: ${syncData.order_name || 'Created'}`,
              { id: 'mandate-verify', duration: 6000 }
            )
            clearCart()
            onSuccess?.()
          } catch (e) {
            toast.error('Verification error: ' + (e.response?.data?.detail || e.message), { id: 'mandate-verify' })
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

  // ── Demo 3: Autonomous Multi-Rail Failover Cascade ──────────────────────────
  const ensureOrderParams = async () => {
    if (activeOrderId && activeKeyId && activeAmountPaise) {
      return { orderId: activeOrderId, keyId: activeKeyId, amountPaise: activeAmountPaise }
    }
    const cid = cart?.cartId || cart?.shopifyCartId || `cart_cascade_${Date.now()}`
    const { data } = await createOrder({
      cart_items: cartItemsPayload,
      currency,
      final_total: rawTotal,
      cart_id: cid,
      customer_id: razorpayCustomerId,
      max_authorized_cap: autonomousCap
    })
    if (!data.success) {
      toast.error('Order creation failed: ' + data.error)
      throw new Error(data.error)
    }
    setActiveOrderId(data.order_id)
    setActiveKeyId(data.key_id)
    setActiveAmountPaise(data.amount)
    return { orderId: data.order_id, keyId: data.key_id, amountPaise: data.amount }
  }

  const handleStartCascade = async () => {
    runTier1()
  }

  const runTier1 = async () => {
    setLoading(true)
    try {
      const loaded = await loadRazorpayScript()
      if (!loaded) { toast.error('Could not load Razorpay'); return }
      const { orderId, keyId, amountPaise } = await ensureOrderParams()

      setCascadeStep(1)
      setCascadeStatuses(s => ({ ...s, tier1: 'attempting' }))
      setPendingRail(null)

      const bank = userProfile?.primaryBank || 'CNRB'
      const bankName = userProfile?.primaryBankLabel || 'Canara Bank'

      speak(`Initiating purchase through your primary rail, ${bankName}.`)
      toast(`Tier 1 Rail: ${bankName}...`, { icon: '🏛️' })

      const rzp = new window.Razorpay({
        key: keyId,
        amount: amountPaise,
        currency,
        name: 'Rasor Autonomous Commerce',
        description: `Tier 1: ${bankName} (${curr}${rawTotal.toFixed(0)})`,
        order_id: orderId,
        retry: { enabled: false },
        prefill: {
          name: userProfile?.fullName || 'Vipul Patil',
          email: effectiveEmail,
          contact: userProfile?.phone || '8806549952',
          method: 'netbanking',
          bank: bank
        },
        theme: { color: '#10b981' },
        handler: async (resp) => {
          failedTierRef.current = null
          setCascadeStatuses(s => ({ ...s, tier1: 'success' }))
          setPendingRail(null)
          handleCascadeSuccess(resp.razorpay_payment_id, orderId, `Tier 1 (${bankName})`)
        },
        modal: { 
          backdropclose: true,
          escape: true,
          confirm_close: false,
          ondismiss: () => {
            if (failedTierRef.current === 1) {
              failedTierRef.current = null
              toast('Tier 1 dismissed. Auto-advancing to Tier 2 (Bank of Baroda)...', { icon: '🔄' })
              setTimeout(() => {
                runTier2()
              }, 400)
            } else {
              setCascadeStatuses(s => s.tier1 === 'attempting' ? ({ ...s, tier1: 'idle' }) : s)
            }
          } 
        }
      })

      rzp.on('payment.failed', async (resp) => {
        setCascadeStatuses(s => ({ ...s, tier1: 'failed' }))
        setPendingRail(2)
        failedTierRef.current = 1
        const desc = resp.error?.description || 'Bank authorization declined'
        toast.error(`❌ Tier 1 (${bankName}) Declined: ${desc}`)

        // Log failover event to ledger
        await logFailover({
          cart_id: `cart_cascade_${orderId}`,
          order_id: orderId,
          failed_tier: 1,
          failed_instrument: `${bankName} (${bank})`,
          reason: desc,
          next_tier: 2,
          next_instrument: `${userProfile?.secondaryBankLabel || 'Bank of Baroda'} (${userProfile?.secondaryBank || 'BARB_R'})`
        })

        speak(`${bankName} was declined by the bank gateway. Close checkout or click Proceed to test Bank of Baroda.`)
      })

      rzp.open()
    } catch (e) {
      toast.error('Tier 1 error: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  const runTier2 = async () => {
    setLoading(true)
    try {
      const loaded = await loadRazorpayScript()
      if (!loaded) { toast.error('Could not load Razorpay'); return }
      const { orderId, keyId, amountPaise } = await ensureOrderParams()

      setCascadeStep(2)
      setCascadeStatuses(s => ({ ...s, tier2: 'attempting' }))
      setPendingRail(null)

      const bank = userProfile?.secondaryBank || 'BARB_R'
      const bankName = userProfile?.secondaryBankLabel || 'Bank of Baroda'

      speak(`Attempting failover through Tier 2, ${bankName}.`)
      toast(`Tier 2 Failover: ${bankName}...`, { icon: '🔄' })

      const rzp = new window.Razorpay({
        key: keyId,
        amount: amountPaise,
        currency,
        name: 'Rasor Autonomous Commerce',
        description: `Tier 2 Failover: ${bankName}`,
        order_id: orderId,
        retry: { enabled: false },
        prefill: {
          name: userProfile?.fullName || 'Vipul Patil',
          email: effectiveEmail,
          contact: userProfile?.phone || '8806549952',
          method: 'netbanking',
          bank: bank
        },
        theme: { color: '#f59e0b' },
        handler: async (resp) => {
          failedTierRef.current = null
          setCascadeStatuses(s => ({ ...s, tier2: 'success' }))
          setPendingRail(null)
          handleCascadeSuccess(resp.razorpay_payment_id, orderId, `Tier 2 (${bankName})`)
        },
        modal: { 
          backdropclose: true,
          escape: true,
          confirm_close: false,
          ondismiss: () => {
            if (failedTierRef.current === 2) {
              failedTierRef.current = null
              toast('Tier 2 dismissed. Auto-advancing to Tier 3 (Verified Card)...', { icon: '💳' })
              setTimeout(() => {
                runTier3()
              }, 400)
            } else {
              setCascadeStatuses(s => s.tier2 === 'attempting' ? ({ ...s, tier2: 'idle' }) : s)
            }
          } 
        }
      })

      rzp.on('payment.failed', async (resp) => {
        setCascadeStatuses(s => ({ ...s, tier2: 'failed' }))
        setPendingRail(3)
        failedTierRef.current = 2
        const desc = resp.error?.description || 'Bank authorization declined'
        toast.error(`❌ Tier 2 (${bankName}) Declined: ${desc}`)

        // Log failover
        await logFailover({
          cart_id: `cart_cascade_${orderId}`,
          order_id: orderId,
          failed_tier: 2,
          failed_instrument: `${bankName} (${bank})`,
          reason: desc,
          next_tier: 3,
          next_instrument: 'Verified Fallback Card (4012 •••• 0002)'
        })

        speak(`Bank of Baroda was also declined. Close checkout or click Proceed to test Verified Card.`)
      })

      rzp.open()
    } catch (e) {
      toast.error('Tier 2 error: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  const runTier3 = async () => {
    setLoading(true)
    try {
      const loaded = await loadRazorpayScript()
      if (!loaded) { toast.error('Could not load Razorpay'); return }
      const { orderId, keyId, amountPaise } = await ensureOrderParams()

      setCascadeStep(3)
      setCascadeStatuses(s => ({ ...s, tier3: 'attempting' }))
      setPendingRail(null)

      const card = userProfile?.fallbackCard || { last4: '0002' }
      speak(`Switching to final fallback card ending in ${card.last4}.`)
      toast(`Tier 3 Final Safeguard: Verified Card (${card.last4})...`, { icon: '💳' })

      const rzp = new window.Razorpay({
        key: keyId,
        amount: amountPaise,
        currency,
        name: 'Rasor Autonomous Commerce',
        description: `Tier 3 Final Safeguard: Verified Card`,
        order_id: orderId,
        retry: { enabled: false },
        prefill: {
          name: userProfile?.fullName || 'Vipul Patil',
          email: effectiveEmail,
          contact: userProfile?.phone || '8806549952',
          method: 'card'
        },
        theme: { color: '#8b5cf6' },
        handler: async (resp) => {
          failedTierRef.current = null
          setCascadeStatuses(s => ({ ...s, tier3: 'success' }))
          setPendingRail(null)
          handleCascadeSuccess(resp.razorpay_payment_id, orderId, 'Tier 3 (Verified Card)')
        },
        modal: { 
          backdropclose: true,
          escape: true,
          confirm_close: false,
          ondismiss: () => {
            if (failedTierRef.current === 3) {
              failedTierRef.current = null
              
              // 1. High-priority alert notification
              toast((t) => (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <strong style={{ color: '#fca5a5', display: 'flex', alignItems: 'center', gap: 6 }}>
                    📱 All 3 Payment Rails Declined!
                  </strong>
                  <span style={{ fontSize: '0.78rem', color: '#e2e8f0' }}>
                    Autonomous failover switched to Mobile Handset Rescue. Scan QR or tap WhatsApp to pay with an alternate bank/UPI.
                  </span>
                </div>
              ), { duration: 9000, icon: '🚨' })

              // 2. Audio Copilot notification
              speak('Attention: All three automated payment rails have declined. Emergency mobile rescue link is active below. Please complete payment using an alternate account or UPI.')

              // 3. Desktop browser notification if permitted
              if ('Notification' in window && Notification.permission === 'granted') {
                try {
                  new Notification('Rasor Autonomous Commerce Alert', {
                    body: 'All 3 payment rails declined. Mobile rescue link ready to complete checkout.',
                    icon: '/favicon.ico'
                  })
                } catch (e) {}
              }

              // 4. Activate Mobile Rescue Module
              setIsRescueModuleActive(true)
              try {
                localStorage.setItem('rasor_rescue_module_active', 'true')
              } catch (e) {}
              setTimeout(() => {
                const fullFailoverSummary = `${userProfile?.primaryBankLabel || 'Canara Bank'}, ${userProfile?.secondaryBankLabel || 'Bank of Baroda'}, Verified Card (•••• ${userProfile?.fallbackCard?.last4 || '1114'})`
                handleTriggerMobileRescue(fullFailoverSummary, true)
              }, 400)
            } else {
              setCascadeStatuses(s => s.tier3 === 'attempting' ? ({ ...s, tier3: 'idle' }) : s)
            }
          } 
        }
      })

      rzp.on('payment.failed', async (resp) => {
        setCascadeStatuses(s => ({ ...s, tier3: 'failed' }))
        setPendingRail(4)
        failedTierRef.current = 3
        const desc = resp.error?.description || 'Card declined'
        toast.error(`❌ Tier 3 Card Declined: ${desc}`)
        speak(`All local payment rails have declined. Auto-failover launching mobile rescue link.`)
      })

      rzp.open()
    } catch (e) {
      toast.error('Tier 3 error: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleCascadeSuccess = async (paymentId, orderId, railName) => {
    setLoading(true)
    toast.loading(`Verifying ${railName} capture...`, { id: 'cascade-verify' })
    try {
      const { data: vd } = await verifyPayment({ payment_id: paymentId, order_id: orderId })
      if (!vd.valid) {
        toast.error('Payment verification failed', { id: 'cascade-verify' })
        return
      }
      const { data: syncData } = await syncShopify({
        cart_items: cartItemsPayload,
        currency,
        final_total: rawTotal,
        order_id: orderId,
        payment_id: paymentId,
        email: effectiveEmail
      })
      if (syncData.success) {
        setCascadeStep(4)
        setPendingRail(null)

        // Log capture to ledger
        await logFailover({
          cart_id: `cart_cascade_${orderId}`,
          order_id: orderId,
          failed_tier: 0,
          failed_instrument: 'NONE',
          reason: `Recovered & Captured via ${railName}. Payment ID: ${paymentId}`,
          next_tier: 0,
          next_instrument: `Shopify Order: ${syncData.order_name}`
        }).catch(() => {})

        speak(`Order successfully recovered and verified on ${railName}. Synced to Shopify store.`)
        toast.success(`🎉 Order Recovered via ${railName}!\nShopify: ${syncData.order_name}\nRazorpay: ${paymentId}`, { id: 'cascade-verify', duration: 8000 })
        setIsRescueModuleActive(false)
        try {
          localStorage.removeItem('rasor_cascade_state')
          localStorage.setItem('rasor_rescue_module_active', 'false')
        } catch (e) {}
        clearCart()
        onSuccess?.()
      } else {
        toast(`Recovered via ${railName}, Shopify sync: ${syncData.error}`, { id: 'cascade-verify', icon: '⚠️' })
      }
    } catch (e) {
      toast.error('Verification error: ' + e.message, { id: 'cascade-verify' })
    } finally {
      setLoading(false)
    }
  }

  // ── Mobile WhatsApp / QR Rescue ───────────────────────────
  const handleTriggerMobileRescue = async (explicitSummary = null, forceRefresh = false) => {
    setIsRescueModuleActive(true)
    try {
      localStorage.setItem('rasor_rescue_module_active', 'true')
    } catch (e) {}

    // If an active session already exists, only reuse if not forcing a refresh and not adding a failover summary
    if (!forceRefresh && !explicitSummary && mobileRescueData?.plink_id && remainingSeconds > 0) {
      toast('Active mobile rescue session opened', { icon: '📱' })
      return
    }

    setLoading(true)
    try {
      // Cancel previous non-failover link if upgrading to failover rescue
      if (mobileRescueData?.plink_id) {
        cancelPaymentLink(mobileRescueData.plink_id).catch(() => {})
      }

      const cid = cart?.cartId || cart?.shopifyCartId || `cart_plink_${Date.now()}`

      // Build failed attempts summary from explicit argument or cascade state
      let failedSummary = explicitSummary
      if (!failedSummary) {
        const failedRails = []
        if (cascadeStatuses.tier1 === 'failed' || cascadeStep >= 1) failedRails.push(userProfile?.primaryBankLabel || 'Canara Bank')
        if (cascadeStatuses.tier2 === 'failed' || cascadeStep >= 2) failedRails.push(userProfile?.secondaryBankLabel || 'Bank of Baroda')
        if (cascadeStatuses.tier3 === 'failed' || cascadeStep >= 3 || failedTierRef.current === 3) failedRails.push(`Verified Card (•••• ${userProfile?.fallbackCard?.last4 || '1114'})`)
        if (failedRails.length > 0) failedSummary = failedRails.join(', ')
      }

      const { data } = await createPaymentLink({
        cart_items: cartItemsPayload,
        currency,
        final_total: rawTotal,
        cart_id: cid,
        customer_phone: userProfile?.phone || '8806549952',
        customer_email: effectiveEmail,
        customer_name: userProfile?.fullName || 'Vipul Patil',
        notify_sms: userProfile?.enableSmsNotification ?? true,
        notify_whatsapp: userProfile?.enableWhatsappRescue ?? true,
        expiry_minutes: config.paymentLinkExpiryMinutes || 15,
        failed_attempts_summary: failedSummary,
        buffer_minutes: config.paymentBufferMinutes ?? 1
      })

      if (!data.success) {
        toast.error('Failed to create payment link: ' + data.error)
        return
      }

      const rescuePayload = { ...data, failed_attempts_summary: failedSummary }
      setMobileRescueData(rescuePayload)
      const maxSecs = (config.paymentLinkExpiryMinutes || 15) * 60
      const durSecs = Math.min(data.duration_seconds || maxSecs, maxSecs)
      setRemainingSeconds(durSecs)
      setPollingActive(true)
      try {
        localStorage.setItem('rasor_active_plink', JSON.stringify({
          plink_id: data.plink_id,
          createdAt: Date.now(),
          duration_seconds: durSecs,
          data: rescuePayload
        }))
      } catch (e) {}
      toast.success('📱 Mobile Payment Link Generated! Polling for completion...', { duration: 5000 })
      if (failedSummary) {
        speak(`Automated attempts on ${failedSummary} declined. Please complete payment using an alternate account or UPI.`)
      } else {
        speak('Payment link generated. You can scan the QR code or click WhatsApp to complete on mobile.')
      }
    } catch (e) {
      toast.error('Mobile link error: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleCopyTestCard = () => {
    const cardNum = userProfile?.fallbackCard?.cardNumber || '4012000000000002'
    navigator.clipboard.writeText(cardNum)
    setCopiedAssistCard(true)
    toast.success('Test Card copied! Paste into Razorpay Card Number')
    setTimeout(() => setCopiedAssistCard(false), 2000)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* ── Standard Checkout ── */}
      <div className="checkout-section">
        <h3><CreditCard size={18} color="var(--accent-blue)" /> Standard Checkout</h3>
        <p className="text-sm text-muted">
          Normal, non-recurring Razorpay transaction. Supports UPI, Cards, Netbanking, and all test payment methods.
        </p>
        <button 
          className="btn btn-full" 
          style={{ background: 'linear-gradient(135deg, #3b82f6, #1d4ed8)', color: '#fff' }} 
          onClick={handleStandardCheckout} 
          disabled={loading}
        >
          {loading ? <span className="spinner" /> : <><CreditCard size={16} /> Pay {curr}{rawTotal.toFixed(0)} (Standard)</>}
        </button>
      </div>

      {/* ── Agentic Checkout ── */}
      <div className="checkout-section" style={{ border: '1px solid rgba(99,102,241,0.35)', background: 'rgba(15, 23, 42, 0.65)' }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 10 }}>
          <h3 style={{ margin: 0 }}>🔒 Agentic Checkout — AP2 Protocol</h3>
          <button 
            className="btn btn-ghost btn-xs"
            onClick={() => setShowInPlaceControls(!showInPlaceControls)}
            style={{ fontSize: '0.74rem', color: '#a5b4fc', display: 'flex', alignItems: 'center', gap: 4 }}
          >
            <Sliders size={12} /> {showInPlaceControls ? 'Hide Overrides' : 'In-Place Overrides'}
          </button>
        </div>

        {/* Demo mode radio tabs - Free and active switching */}
        <div className="radio-group" style={{ marginBottom: 14 }}>
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
          <button
            className={`radio-option ${demoMode === 'cascade_failover' ? 'selected' : ''}`}
            onClick={() => onDemoModeChange('cascade_failover')}
            style={{ fontWeight: 700 }}
          >
            Demo 3: Multi-Rail Failover
          </button>
        </div>

        {/* In-Place Mandate Overrides Accordion for Testing */}
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

        {/* ── Demo 1 UI ── */}
        {demoMode === 'human_present' && (
          <>
            <div className="mandate-banner">
              <strong>📝 Mandate Authorization for {effectiveEmail}</strong><br />
              Authorizes the agent to place this order up to <strong>{curr}{rawTotal.toFixed(0)}</strong>.
              Completing this payment on the secure page establishes and saves your recurring mandate token for future Demo 2 autonomous purchases.
            </div>
            <button className="btn btn-primary btn-full" onClick={handleDemo1} disabled={loading}>
              {loading ? <span className="spinner" /> : `✅ Approve Mandate & Pay ${curr}${rawTotal.toFixed(0)}`}
            </button>

            {/* Manual Mobile Handset Rescue Button in Demo 1 (Always Visible) */}
            <div style={{ textAlign: 'center', margin: '10px 0 4px 0', fontSize: '0.74rem', color: 'var(--text-muted)' }}>
              — or complete on mobile device —
            </div>

            <button
              type="button"
              className="btn btn-secondary btn-full btn-sm"
              onClick={handleTriggerMobileRescue}
              disabled={loading}
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}
            >
              <Smartphone size={14} /> Send Payment Link to Mobile / WhatsApp
            </button>
          </>
        )}

        {/* ── Demo 2 UI ── */}
        {demoMode === 'autonomous_s2s' && (
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

        {/* ── Demo 3 UI: Multi-Rail Failover Cascade ── */}
        {demoMode === 'cascade_failover' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ 
              background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.1), rgba(99, 102, 241, 0.1))', 
              border: '1px solid rgba(16, 185, 129, 0.3)',
              borderRadius: 8, padding: '12px 14px'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <span style={{ fontWeight: 700, fontSize: '0.84rem', color: '#6ee7b7' }}>
                  ⚡ Autonomous Multi-Rail Failover Cascade
                </span>
                <span className="badge badge-green" style={{ fontSize: '0.68rem' }}>AP2 Resilient</span>
              </div>
              <p style={{ fontSize: '0.76rem', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.4 }}>
                Tests real-world resilience: if <strong>{userProfile?.primaryBankLabel || 'Canara Bank'}</strong> declines at checkout, 
                the agent intercepts the failure, announces audio copilot guidance, and auto-failovers to <strong>{userProfile?.secondaryBankLabel || 'Bank of Baroda'}</strong>, 
                then to your <strong>Verified Card</strong>.
              </p>
            </div>

            {/* Live Visual Decision & Failover Stepper */}
            <div style={{ 
              background: 'rgba(0,0,0,0.3)', 
              border: '1px solid var(--border)', 
              borderRadius: 8, padding: '12px',
              display: 'flex', flexDirection: 'column', gap: 8 
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                  Autonomous Decision & Recovery Stepper:
                </div>
                {(cascadeStatuses.tier1 !== 'idle' || cascadeStatuses.tier2 !== 'idle' || cascadeStatuses.tier3 !== 'idle') && (
                  <button
                    type="button"
                    className="btn btn-ghost btn-xs"
                    onClick={handleResetCascade}
                    style={{ fontSize: '0.68rem', color: '#94a3b8', padding: '1px 6px', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                    title="Reset stepper to initial idle state"
                  >
                    <RotateCcw size={10} /> Reset Stepper
                  </button>
                )}
              </div>

              {/* Step 1: Canara Bank */}
              <div style={{ 
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '6px 10px', borderRadius: 6,
                background: cascadeStatuses.tier1 === 'attempting' ? 'rgba(16, 185, 129, 0.15)' : 
                            cascadeStatuses.tier1 === 'failed' ? 'rgba(239, 68, 68, 0.15)' : 
                            cascadeStatuses.tier1 === 'success' ? 'rgba(16, 185, 129, 0.25)' : 'rgba(255,255,255,0.03)',
                border: cascadeStatuses.tier1 === 'attempting' ? '1px solid #10b981' : 
                        cascadeStatuses.tier1 === 'failed' ? '1px solid #ef4444' : '1px solid transparent'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.78rem' }}>
                  <span style={{ 
                    width: 18, height: 18, borderRadius: 99, 
                    background: cascadeStatuses.tier1 === 'failed' ? '#ef4444' : '#10b981', 
                    color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 700 
                  }}>1</span>
                  <span><strong>Tier 1:</strong> {userProfile?.primaryBankLabel || 'Canara Bank'} ({userProfile?.primaryBank || 'CNRB'})</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  {cascadeStatuses.tier1 === 'idle' && <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Pending</span>}
                  {cascadeStatuses.tier1 === 'attempting' && <span style={{ fontSize: '0.7rem', color: '#10b981', fontWeight: 700 }}>● Attempting...</span>}
                  {cascadeStatuses.tier1 === 'failed' && <span style={{ fontSize: '0.7rem', color: '#ef4444', fontWeight: 700 }}>✖ Declined</span>}
                  {cascadeStatuses.tier1 === 'success' && <span style={{ fontSize: '0.7rem', color: '#10b981', fontWeight: 700 }}>✔ Captured</span>}
                  <button
                    type="button"
                    className="btn btn-ghost btn-xs"
                    onClick={runTier1}
                    disabled={loading}
                    style={{ padding: '2px 8px', fontSize: '0.68rem', color: '#6ee7b7', border: '1px solid rgba(16, 185, 129, 0.3)' }}
                    title="Test Tier 1 Canara Bank directly"
                  >
                    {cascadeStatuses.tier1 === 'failed' ? 'Retry' : 'Test'}
                  </button>
                </div>
              </div>

              {/* Step 2: Bank of Baroda */}
              <div style={{ 
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '6px 10px', borderRadius: 6,
                background: cascadeStatuses.tier2 === 'attempting' ? 'rgba(245, 158, 11, 0.15)' : 
                            cascadeStatuses.tier2 === 'failed' ? 'rgba(239, 68, 68, 0.15)' : 
                            cascadeStatuses.tier2 === 'success' ? 'rgba(16, 185, 129, 0.25)' : 'rgba(255,255,255,0.03)',
                border: cascadeStatuses.tier2 === 'attempting' ? '1px solid #f59e0b' : 
                        cascadeStatuses.tier2 === 'failed' ? '1px solid #ef4444' : '1px solid transparent'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.78rem' }}>
                  <span style={{ 
                    width: 18, height: 18, borderRadius: 99, 
                    background: cascadeStatuses.tier2 === 'failed' ? '#ef4444' : '#f59e0b', 
                    color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 700 
                  }}>2</span>
                  <span><strong>Tier 2:</strong> {userProfile?.secondaryBankLabel || 'Bank of Baroda'} ({userProfile?.secondaryBank || 'BARB_R'})</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  {cascadeStatuses.tier2 === 'idle' && <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Auto-Fallback</span>}
                  {cascadeStatuses.tier2 === 'attempting' && <span style={{ fontSize: '0.7rem', color: '#f59e0b', fontWeight: 700 }}>● Re-routing...</span>}
                  {cascadeStatuses.tier2 === 'failed' && <span style={{ fontSize: '0.7rem', color: '#ef4444', fontWeight: 700 }}>✖ Declined</span>}
                  {cascadeStatuses.tier2 === 'success' && <span style={{ fontSize: '0.7rem', color: '#10b981', fontWeight: 700 }}>✔ Captured</span>}
                  <button
                    type="button"
                    className="btn btn-ghost btn-xs"
                    onClick={runTier2}
                    disabled={loading}
                    style={{ padding: '2px 8px', fontSize: '0.68rem', color: '#fcd34d', border: '1px solid rgba(245, 158, 11, 0.3)' }}
                    title="Test Tier 2 Bank of Baroda directly"
                  >
                    {cascadeStatuses.tier2 === 'failed' ? 'Retry' : 'Test'}
                  </button>
                </div>
              </div>

              {/* Step 3: Verified Card */}
              <div style={{ 
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '6px 10px', borderRadius: 6,
                background: cascadeStatuses.tier3 === 'attempting' ? 'rgba(139, 92, 246, 0.15)' : 
                            cascadeStatuses.tier3 === 'failed' ? 'rgba(239, 68, 68, 0.15)' : 
                            cascadeStatuses.tier3 === 'success' ? 'rgba(16, 185, 129, 0.25)' : 'rgba(255,255,255,0.03)',
                border: cascadeStatuses.tier3 === 'attempting' ? '1px solid #8b5cf6' : 
                        cascadeStatuses.tier3 === 'failed' ? '1px solid #ef4444' : '1px solid transparent'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.78rem' }}>
                  <span style={{ 
                    width: 18, height: 18, borderRadius: 99, 
                    background: cascadeStatuses.tier3 === 'failed' ? '#ef4444' : '#8b5cf6', 
                    color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 700 
                  }}>3</span>
                  <span><strong>Tier 3:</strong> Verified Card (•••• {userProfile?.fallbackCard?.last4 || '0002'})</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  {cascadeStatuses.tier3 === 'idle' && <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Final Safeguard</span>}
                  {cascadeStatuses.tier3 === 'attempting' && <span style={{ fontSize: '0.7rem', color: '#8b5cf6', fontWeight: 700 }}>● Active Card</span>}
                  {cascadeStatuses.tier3 === 'failed' && <span style={{ fontSize: '0.7rem', color: '#ef4444', fontWeight: 700 }}>✖ Declined</span>}
                  {cascadeStatuses.tier3 === 'success' && <span style={{ fontSize: '0.7rem', color: '#10b981', fontWeight: 700 }}>✔ Captured</span>}
                  <button
                    type="button"
                    className="btn btn-ghost btn-xs"
                    onClick={runTier3}
                    disabled={loading}
                    style={{ padding: '2px 8px', fontSize: '0.68rem', color: '#c4b5fd', border: '1px solid rgba(139, 92, 246, 0.3)' }}
                    title="Test Tier 3 Verified Card directly"
                  >
                    {cascadeStatuses.tier3 === 'failed' ? 'Retry' : 'Test'}
                  </button>
                </div>
              </div>
            </div>

            {/* Contextual Failover Action Prompt */}
            {pendingRail === 2 && (
              <div style={{
                padding: '10px 12px', background: 'rgba(245, 158, 11, 0.12)', 
                border: '1px solid rgba(245, 158, 11, 0.4)', borderRadius: 8,
                display: 'flex', flexDirection: 'column', gap: 8
              }}>
                <div style={{ fontSize: '0.78rem', color: '#fcd34d', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <RefreshCw size={14} className="animate-spin" /> Tier 1 Declined. Ready to Failover to Tier 2:
                </div>
                <button 
                  className="btn btn-full" 
                  style={{ background: 'linear-gradient(135deg, #f59e0b, #d97706)', color: '#000', fontWeight: 700, fontSize: '0.82rem' }}
                  onClick={runTier2} 
                  disabled={loading}
                >
                  {loading ? <span className="spinner" /> : <>🔄 Proceed to Tier 2: {userProfile?.secondaryBankLabel || 'Bank of Baroda'} (BARB_R)</>}
                </button>
              </div>
            )}

            {pendingRail === 3 && (
              <div style={{
                padding: '10px 12px', background: 'rgba(139, 92, 246, 0.12)', 
                border: '1px solid rgba(139, 92, 246, 0.4)', borderRadius: 8,
                display: 'flex', flexDirection: 'column', gap: 8
              }}>
                <div style={{ fontSize: '0.78rem', color: '#c4b5fd', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <CreditCard size={14} /> Tier 2 Declined. Ready for Final Safeguard:
                </div>
                <button 
                  className="btn btn-full" 
                  style={{ background: 'linear-gradient(135deg, #8b5cf6, #6d28d9)', color: '#fff', fontWeight: 700, fontSize: '0.82rem' }}
                  onClick={runTier3} 
                  disabled={loading}
                >
                  {loading ? <span className="spinner" /> : <>💳 Proceed to Tier 3: Verified Card (•••• {userProfile?.fallbackCard?.last4 || '0002'})</>}
                </button>
              </div>
            )}

            {pendingRail === 4 && mobileRescueData && remainingSeconds > 0 && (
              <div style={{
                padding: '10px 12px', background: 'rgba(16, 185, 129, 0.12)', 
                border: '1px solid rgba(16, 185, 129, 0.4)', borderRadius: 8,
                display: 'flex', flexDirection: 'column', gap: 8
              }}>
                <div style={{ fontSize: '0.78rem', color: '#6ee7b7', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Smartphone size={14} /> All Local Rails Declined. Ready for Mobile Rescue:
                </div>
                <button 
                  className="btn btn-full" 
                  style={{ background: 'linear-gradient(135deg, #10b981, #059669)', color: '#fff', fontWeight: 700, fontSize: '0.82rem' }}
                  onClick={() => {
                    const fullSummary = `${userProfile?.primaryBankLabel || 'Canara Bank'}, ${userProfile?.secondaryBankLabel || 'Bank of Baroda'}, Verified Card (•••• ${userProfile?.fallbackCard?.last4 || '1114'})`
                    handleTriggerMobileRescue(fullSummary, true)
                  }} 
                  disabled={loading}
                >
                  {loading ? <span className="spinner" /> : <>📱 Launch Mobile Handset Rescue (WhatsApp / QR)</>}
                </button>
              </div>
            )}

            {/* 3rd Failure Critical Notice Banner - Only shown during active rescue */}
            {pendingRail === 4 && mobileRescueData && remainingSeconds > 0 && (
              <div className="animate-fade-in" style={{
                background: 'linear-gradient(135deg, rgba(239, 68, 68, 0.2), rgba(185, 28, 28, 0.08))',
                border: '1px solid rgba(239, 68, 68, 0.5)',
                borderRadius: 8,
                padding: '12px 14px',
                display: 'flex',
                flexDirection: 'column',
                gap: 6
              }}>
                <div style={{ color: '#fca5a5', fontWeight: 700, fontSize: '0.86rem', display: 'flex', alignItems: 'center', gap: 6 }}>
                  🚨 Multi-Rail Failover Exhausted (3/3 Rails Declined)
                </div>
                <div style={{ color: '#f1f5f9', fontSize: '0.78rem', lineHeight: 1.4 }}>
                  The agent attempted <strong>{userProfile?.primaryBankLabel || 'Canara Bank'}</strong>, <strong>{userProfile?.secondaryBankLabel || 'Bank of Baroda'}</strong>, and <strong>Verified Card (•••• {userProfile?.fallbackCard?.last4 || '0002'})</strong>. All 3 transactions were declined by their respective banking gateways.
                </div>
                <div style={{ color: '#6ee7b7', fontSize: '0.76rem', fontWeight: 600 }}>
                  👉 Autonomous failover has handed off to Mobile Rescue. Scan the QR code or tap WhatsApp below to pay using an alternate account or UPI.
                </div>
              </div>
            )}

            {/* Agent Test Card Quick-Assist Pill (Shown during cascade) */}
            <div style={{ 
              background: 'rgba(99, 102, 241, 0.1)', border: '1px dashed rgba(99, 102, 241, 0.35)', 
              borderRadius: 6, padding: '8px 10px', display: 'flex', alignItems: 'center', justifyContent: 'space-between'
            }}>
              <div style={{ fontSize: '0.74rem' }}>
                <span style={{ color: '#a5b4fc', fontWeight: 600 }}>Test Card Assist:</span>{' '}
                <code style={{ color: '#c7d2fe' }}>4012 0000 0000 0002</code> (12/28, CVV: 123)
              </div>
              <button
                type="button"
                className="btn btn-ghost btn-xs"
                onClick={handleCopyTestCard}
                style={{ padding: '2px 8px', fontSize: '0.7rem' }}
              >
                {copiedAssistCard ? <Check size={12} color="#10b981" /> : <Copy size={12} />}
                {copiedAssistCard ? 'Copied' : 'Copy'}
              </button>
            </div>

            {/* Launch Cascade Button (Starts at Tier 1) */}
            {!pendingRail && (
              <button 
                className="btn btn-full" 
                style={{ background: 'linear-gradient(135deg, #10b981, #6366f1)', color: '#fff', fontWeight: 700 }}
                onClick={handleStartCascade} 
                disabled={loading}
              >
                {loading ? <span className="spinner" /> : <><Zap size={16} /> Start Multi-Rail Cascade ({curr}{rawTotal.toFixed(0)})</>}
              </button>
            )}

            {/* Or Mobile Handset Rescue Button (Always Visible) */}
            <div style={{ textAlign: 'center', margin: '4px 0', fontSize: '0.74rem', color: 'var(--text-muted)' }}>
              — or test away-from-desktop rescue —
            </div>

            <button
              type="button"
              className="btn btn-secondary btn-full btn-sm"
              onClick={() => {
                const failedRails = []
                if (cascadeStatuses.tier1 === 'failed') failedRails.push(userProfile?.primaryBankLabel || 'Canara Bank')
                if (cascadeStatuses.tier2 === 'failed') failedRails.push(userProfile?.secondaryBankLabel || 'Bank of Baroda')
                if (cascadeStatuses.tier3 === 'failed') failedRails.push(`Verified Card (•••• ${userProfile?.fallbackCard?.last4 || '1114'})`)
                const s = failedRails.length > 0 ? failedRails.join(', ') : null
                handleTriggerMobileRescue(s, !!s)
              }}
              disabled={loading}
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}
            >
              <Smartphone size={14} /> Send Payment Link to Mobile / WhatsApp
            </button>
          </div>
        )}

        {/* ── Mobile WhatsApp / QR Rescue View Module (Persisted State) ── */}
        {isRescueModuleActive && mobileRescueData && remainingSeconds > 0 && (
          <div style={{ 
            marginTop: 14, padding: '14px', 
            background: 'linear-gradient(135deg, #1e1b4b, #0f172a)', 
            border: '1px solid rgba(16, 185, 129, 0.4)', borderRadius: 8 
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <span style={{ fontWeight: 700, fontSize: '0.84rem', color: '#6ee7b7', display: 'flex', alignItems: 'center', gap: 6 }}>
                <Smartphone size={16} /> Mobile Handset Rescue Active
              </span>
              <button 
                type="button"
                className="btn btn-ghost btn-xs"
                onClick={handleCancelMobileRescue} 
                style={{ 
                  background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.35)',
                  color: '#f87171', cursor: 'pointer', padding: '3px 8px', borderRadius: 4,
                  fontSize: '0.72rem', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 4
                }}
                title="Cancel and immediately expire this payment link on Razorpay"
              >
                <X size={13} /> Cancel & Expire Link
              </button>
            </div>

            {/* 15-Minute Live Countdown Timer */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              background: remainingSeconds > 60 ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.2)',
              border: `1px solid ${remainingSeconds > 60 ? 'rgba(16, 185, 129, 0.4)' : 'rgba(239, 68, 68, 0.5)'}`,
              borderRadius: 6, padding: '7px 12px', marginBottom: 10
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.76rem', color: remainingSeconds > 60 ? '#6ee7b7' : '#fca5a5' }}>
                <Clock size={14} className={remainingSeconds > 0 ? "animate-pulse" : ""} />
                <span><strong>Active Link Expiration ({Math.min(Math.floor(remainingSeconds / 60) || 15, config.paymentLinkExpiryMinutes || 15)}m Lock):</strong></span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{
                  fontFamily: 'monospace', fontWeight: 800, fontSize: '0.92rem',
                  color: remainingSeconds > 60 ? '#34d399' : '#f87171'
                }}>
                  {remainingSeconds > 0 ? formatCountdown(remainingSeconds) : '00:00 (EXPIRED)'}
                </div>
                {remainingSeconds > 0 && (
                  <button
                    type="button"
                    className="btn btn-ghost btn-xs"
                    onClick={handleCancelMobileRescue}
                    style={{ padding: '1px 6px', fontSize: '0.65rem', color: '#f87171', border: '1px solid rgba(239, 68, 68, 0.3)' }}
                    title="Force immediate expiry of link"
                  >
                    Expire Now
                  </button>
                )}
              </div>
            </div>

            {/* Customer Completion Deadline with Safety Buffer */}
            {mobileRescueData?.deadline_str && (
              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 6,
                background: 'rgba(245, 158, 11, 0.1)',
                border: '1px solid rgba(245, 158, 11, 0.3)',
                borderRadius: 6, padding: '6px 12px', marginBottom: 10,
                fontSize: '0.74rem', color: '#fef08a'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span>⏳</span>
                  <span><strong>Payment Deadline:</strong> Please complete before <strong>{mobileRescueData.deadline_str}</strong></span>
                </div>
                <span style={{ fontSize: '0.68rem', color: '#fcd34d', background: 'rgba(245, 158, 11, 0.2)', padding: '2px 6px', borderRadius: 4 }}>
                  {mobileRescueData.buffer_minutes ?? config.paymentBufferMinutes ?? 1}m Safety Buffer Applied
                </span>
              </div>
            )}

            {/* Anti-Spam Notification Status Pill */}
            <div style={{ 
              display: 'flex', alignItems: 'center', gap: 8, 
              fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: 10,
              padding: '4px 8px', background: 'rgba(255, 255, 255, 0.04)', borderRadius: 4
            }}>
              {userProfile?.enableSmsNotification !== false ? (
                <span style={{ color: '#34d399', display: 'flex', alignItems: 'center', gap: 4 }}>
                  <Check size={12} /> SMS dispatched to {userProfile?.phone || '+91 88065 49952'}
                </span>
              ) : (
                <span style={{ color: '#fbbf24', display: 'flex', alignItems: 'center', gap: 4 }}>
                  <BellOff size={12} /> SMS disabled in Profile Settings (Anti-Spam Mode)
                </span>
              )}
            </div>

            {/* Multi-Rail Failure Notice if previous rails failed */}
            {mobileRescueData?.failed_attempts_summary && (
              <div style={{
                background: 'rgba(239, 68, 68, 0.12)',
                border: '1px solid rgba(239, 68, 68, 0.35)',
                borderRadius: 6,
                padding: '8px 12px',
                marginBottom: 10,
                fontSize: '0.74rem',
                color: '#fca5a5',
                lineHeight: 1.4
              }}>
                <div style={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                  ⚠️ Primary Payment Rails Declined:
                </div>
                <div>
                  We attempted your checkout on <strong>{mobileRescueData.failed_attempts_summary}</strong>, but transactions were declined.
                  Please complete your order using a <strong>different bank account, UPI (GPay/PhonePe), or an alternate card</strong> via the rescue link below.
                </div>
              </div>
            )}

            <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
              {/* QR Code */}
              <div style={{ background: '#fff', padding: 6, borderRadius: 6, display: 'inline-block' }}>
                <img 
                  src={`https://api.qrserver.com/v1/create-qr-code/?size=120x120&data=${encodeURIComponent(mobileRescueData.short_url)}`} 
                  alt="Scan to pay on mobile" 
                  style={{ width: 100, height: 100, display: 'block' }}
                />
              </div>

              {/* WhatsApp Action & Polling Indicator */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, flex: 1 }}>
                <p style={{ margin: 0, fontSize: '0.76rem', color: '#cbd5e1', lineHeight: 1.4 }}>
                  Scan the QR code with your phone camera, or launch WhatsApp to complete payment{mobileRescueData?.deadline_str ? <> before <strong style={{ color: '#fde68a' }}>{mobileRescueData.deadline_str}</strong></> : ''}.
                </p>

                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {/* Native WhatsApp Application Protocol */}
                  <a
                    href={mobileRescueData.whatsapp_app_url || mobileRescueData.whatsapp_url}
                    className="btn btn-sm"
                    style={{ background: '#25D366', color: '#fff', fontWeight: 700, fontSize: '0.75rem', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                    title="Directly opens the WhatsApp application on desktop or phone"
                  >
                    📲 Open WhatsApp App
                  </a>

                  {/* WhatsApp Web Fallback */}
                  <a
                    href={mobileRescueData.whatsapp_web_url || mobileRescueData.whatsapp_url}
                    target="_blank"
                    rel="noreferrer"
                    className="btn btn-ghost btn-sm"
                    style={{ fontSize: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                    title="Opens in web.whatsapp.com browser tab"
                  >
                    🌐 Web WhatsApp
                  </a>

                  {/* Direct Link */}
                  <a
                    href={mobileRescueData.short_url}
                    target="_blank"
                    rel="noreferrer"
                    className="btn btn-ghost btn-sm"
                    style={{ fontSize: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                  >
                    <ExternalLink size={12} /> Direct Link
                  </a>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.72rem', color: remainingSeconds > 0 ? '#34d399' : '#f87171' }}>
                  <RefreshCw size={12} className={remainingSeconds > 0 && pollingActive ? "animate-spin" : ""} />
                  <span>
                    {remainingSeconds > 0 && pollingActive 
                      ? "Polling Razorpay every 3s — desktop auto-completes upon mobile capture"
                      : "Polling stopped (window closed)"}
                  </span>
                </div>
              </div>
            </div>
          </div>
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
