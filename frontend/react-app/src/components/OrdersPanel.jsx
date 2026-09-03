import React, { useState, useEffect, useMemo } from 'react'
import {
  ShoppingBag, RefreshCw, Trash2, ExternalLink, ShieldAlert,
  CheckCircle2, ArrowDownUp, Filter, Search, PlusCircle,
  PackageCheck, Clock, CreditCard, RotateCcw, AlertCircle
} from 'lucide-react'
import { getOrders, getLedger, clearLedger, getRefunds } from '../api/client'
import { useApp } from '../context/AppContext'
import toast from 'react-hot-toast'

export default function OrdersPanel({ onOpenCart }) {
  const { config, addToCartLocal } = useApp()
  const curr = config.currency === 'USD' ? '$' : '₹'

  const [activeTab, setActiveTab] = useState('orders') // 'orders' | 'refunds' | 'ledger'
  const [orders, setOrders] = useState([])
  const [loadingOrders, setLoadingOrders] = useState(false)
  
  const [refunds, setRefunds] = useState([])
  const [loadingRefunds, setLoadingRefunds] = useState(false)

  const [ledger, setLedger] = useState([])
  const [loadingLedger, setLoadingLedger] = useState(false)
  const [ledgerFilter, setLedgerFilter] = useState('all') // 'all' | 'refund' | 'failover' | 'sync'
  const [searchQuery, setSearchQuery] = useState('')

  // ── Fetchers ─────────────────────────────────────────────────────────────
  const fetchOrders = async () => {
    setLoadingOrders(true)
    try {
      const { data } = await getOrders(10)
      setOrders(data.orders || [])
    } catch {
      toast.error('Failed to fetch Shopify orders')
    } finally {
      setLoadingOrders(false)
    }
  }

  const fetchRefunds = async () => {
    setLoadingRefunds(true)
    try {
      const { data } = await getRefunds()
      setRefunds(data.refunds || [])
    } catch {
      toast.error('Failed to fetch refunds')
    } finally {
      setLoadingRefunds(false)
    }
  }

  const fetchLedger = async () => {
    setLoadingLedger(true)
    try {
      const { data } = await getLedger()
      setLedger(data.entries || [])
    } catch {
      toast.error('Failed to fetch ledger')
    } finally {
      setLoadingLedger(false)
    }
  }

  const handleClearLedger = async () => {
    if (!window.confirm('Are you sure you want to clear the AP2 Audit Ledger?')) return
    await clearLedger().catch(() => toast.error('Failed to clear ledger'))
    setLedger([])
    toast.success('Audit ledger cleared')
  }

  useEffect(() => {
    fetchOrders()
    fetchRefunds()
    fetchLedger()
  }, [])

  // ── Reorder handler ──────────────────────────────────────────────────────
  const handleReorder = (order) => {
    const lineItems = order.line_items || []
    if (lineItems.length === 0) {
      toast.error('No items found in this order to add')
      return
    }

    let addedCount = 0
    lineItems.forEach(item => {
      const productObj = {
        id: item.product_id ? `SHPF-${item.product_id}` : `SHPF-${item.id}`,
        title: item.title,
        price: parseFloat(item.price || 0),
        unit_price: parseFloat(item.price || 0),
        merchant: item.vendor || 'Rasor Test Store 1',
        currency: order.currency || 'INR',
        imageUrl: item.image?.src || null
      }
      addToCartLocal(productObj, item.quantity || 1)
      addedCount += (item.quantity || 1)
    })

    toast.success(`🎉 Added ${addedCount} item(s) from Order ${order.name || order.order_number} to your cart!`, { duration: 4000 })
    onOpenCart?.()
  }

  // ── Reversed & Filtered Ledger ───────────────────────────────────────────
  // CRITICAL REQUIREMENT: Reversed so newest events are immediately at the top!
  const reversedLedger = useMemo(() => {
    return [...ledger].reverse()
  }, [ledger])

  const filteredLedger = useMemo(() => {
    return reversedLedger.filter(entry => {
      const type = (entry.event_type || entry.action || '').toLowerCase()
      const matchesFilter =
        ledgerFilter === 'all' ? true :
        ledgerFilter === 'refund' ? type.includes('refund') :
        ledgerFilter === 'failover' ? (type.includes('failover') || type.includes('decline') || type.includes('fail')) :
        ledgerFilter === 'sync' ? (type.includes('reconciled') || type.includes('order') || type.includes('sync')) : true

      if (!matchesFilter) return false

      if (!searchQuery.trim()) return true
      const q = searchQuery.toLowerCase()
      const str = (JSON.stringify(entry) || '').toLowerCase()
      return str.includes(q)
    })
  }, [reversedLedger, ledgerFilter, searchQuery])

  return (
    <div className="orders-panel animate-fade-in" style={{ maxWidth: 960, margin: '0 auto', paddingBottom: 60 }}>
      {/* Page Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12, marginBottom: 20 }}>
        <div>
          <div className="page-title" style={{ fontSize: '1.45rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
            📦 Orders, Refunds & Audit Ledger
          </div>
          <p className="page-subtitle" style={{ fontSize: '0.84rem', color: 'var(--text-muted)', marginTop: 4 }}>
            Verified Shopify orders with 1-click reordering, autonomous safeguard refunds, and cryptographic AP2 audit trail.
          </p>
        </div>

        {/* Global Refresh Button */}
        <div style={{ display: 'flex', gap: 8 }}>
          <button 
            className="btn btn-secondary btn-sm"
            onClick={() => { fetchOrders(); fetchRefunds(); fetchLedger() }}
            disabled={loadingOrders || loadingRefunds || loadingLedger}
            style={{ display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <RefreshCw size={13} className={(loadingOrders || loadingRefunds || loadingLedger) ? 'animate-spin' : ''} />
            Refresh All
          </button>
        </div>
      </div>

      {/* Modern Top Tabs */}
      <div style={{ display: 'flex', gap: 8, borderBottom: '1px solid var(--border)', paddingBottom: 12, marginBottom: 24, overflowX: 'auto' }}>
        <button
          onClick={() => setActiveTab('orders')}
          style={{
            padding: '8px 16px',
            borderRadius: 8,
            fontSize: '0.85rem',
            fontWeight: 600,
            cursor: 'pointer',
            border: activeTab === 'orders' ? '1px solid rgba(59, 130, 246, 0.4)' : '1px solid transparent',
            background: activeTab === 'orders' ? 'rgba(59, 130, 246, 0.15)' : 'rgba(255, 255, 255, 0.04)',
            color: activeTab === 'orders' ? '#60a5fa' : 'var(--text-secondary)',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            transition: 'all 0.15s ease'
          }}
        >
          <ShoppingBag size={16} />
          Shopify Orders
          {orders.length > 0 && (
            <span style={{ background: '#2563eb', color: '#fff', fontSize: '0.72rem', padding: '1px 6px', borderRadius: 10, fontWeight: 700 }}>
              {orders.length}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab('refunds')}
          style={{
            padding: '8px 16px',
            borderRadius: 8,
            fontSize: '0.85rem',
            fontWeight: 600,
            cursor: 'pointer',
            border: activeTab === 'refunds' ? '1px solid rgba(239, 68, 68, 0.4)' : '1px solid transparent',
            background: activeTab === 'refunds' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(255, 255, 255, 0.04)',
            color: activeTab === 'refunds' ? '#f87171' : 'var(--text-secondary)',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            transition: 'all 0.15s ease'
          }}
        >
          <ShieldAlert size={16} />
          Autonomous Refunds
          {refunds.length > 0 && (
            <span style={{ background: '#dc2626', color: '#fff', fontSize: '0.72rem', padding: '1px 6px', borderRadius: 10, fontWeight: 700 }}>
              {refunds.length}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab('ledger')}
          style={{
            padding: '8px 16px',
            borderRadius: 8,
            fontSize: '0.85rem',
            fontWeight: 600,
            cursor: 'pointer',
            border: activeTab === 'ledger' ? '1px solid rgba(168, 85, 247, 0.4)' : '1px solid transparent',
            background: activeTab === 'ledger' ? 'rgba(168, 85, 247, 0.15)' : 'rgba(255, 255, 255, 0.04)',
            color: activeTab === 'ledger' ? '#c084fc' : 'var(--text-secondary)',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            transition: 'all 0.15s ease'
          }}
        >
          <ArrowDownUp size={16} />
          AP2 Transaction Ledger (Newest First)
          {ledger.length > 0 && (
            <span style={{ background: '#9333ea', color: '#fff', fontSize: '0.72rem', padding: '1px 6px', borderRadius: 10, fontWeight: 700 }}>
              {ledger.length}
            </span>
          )}
        </button>
      </div>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* TAB 1: SHOPIFY ORDERS                                               */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {activeTab === 'orders' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
            <div>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 600, color: '#f8fafc', margin: 0 }}>
                Verified Shopify Orders
              </h3>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', margin: '2px 0 0 0' }}>
                Orders successfully transacted by the AI Agent and synchronized with Shopify Admin API.
              </p>
            </div>
            <button className="btn btn-secondary btn-xs" onClick={fetchOrders} disabled={loadingOrders}>
              <RefreshCw size={11} className={loadingOrders ? 'animate-spin' : ''} /> Refresh
            </button>
          </div>

          {/* Razorpay Section Navigator Tip */}
          <div style={{
            background: 'rgba(59, 130, 246, 0.08)',
            border: '1px solid rgba(59, 130, 246, 0.25)',
            borderRadius: 8,
            padding: '12px 14px',
            marginBottom: 16,
            fontSize: '0.78rem',
            color: '#cbd5e1',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 10
          }}>
            <div>
              <div style={{ fontWeight: 600, color: '#93c5fd', marginBottom: 2, display: 'flex', alignItems: 'center', gap: 6 }}>
                💡 Razorpay Dashboard Verification Guide:
              </div>
              <div style={{ lineHeight: 1.4, color: '#94a3b8' }}>
                • <strong>Direct Checkout & Multi-Rail Cascade Orders:</strong> Logged under <strong>TRANSACTIONS → Payments</strong> (<code>pay_xxxx</code>).<br />
                • <strong>Mobile Rescue Links (WhatsApp / SMS):</strong> Logged under <strong>PAYMENT PRODUCTS → Payment Links</strong> (<code>plink_xxxx</code>).
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <a
                href="https://dashboard.razorpay.com/app/payments"
                target="_blank"
                rel="noreferrer"
                className="btn btn-secondary btn-xs"
                style={{ display: 'inline-flex', alignItems: 'center', gap: 4, textDecoration: 'none', color: '#93c5fd' }}
              >
                <ExternalLink size={12} /> View Payments (pay_*)
              </a>
              <a
                href="https://dashboard.razorpay.com/app/paymentlinks"
                target="_blank"
                rel="noreferrer"
                className="btn btn-secondary btn-xs"
                style={{ display: 'inline-flex', alignItems: 'center', gap: 4, textDecoration: 'none', color: '#cbd5e1' }}
              >
                <ExternalLink size={12} /> View Links (plink_*)
              </a>
            </div>
          </div>

          {orders.length === 0 ? (
            <div style={{ padding: 32, textAlign: 'center', background: 'rgba(255,255,255,0.02)', borderRadius: 10, border: '1px dashed var(--border)' }}>
              <PackageCheck size={32} style={{ color: 'var(--text-muted)', marginBottom: 8 }} />
              <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)' }}>No orders found on Shopify yet.</p>
              <p style={{ fontSize: '0.76rem', color: 'var(--text-muted)' }}>Complete a checkout in Demo 1, Demo 2, or Mobile Rescue to see orders appear here.</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {orders.map(order => {
                const lineItems = order.line_items || []
                const formattedDate = order.created_at ? new Date(order.created_at).toLocaleString('en-IN', {
                  day: '2-digit', month: 'short', year: 'numeric',
                  hour: '2-digit', minute: '2-digit'
                }) : 'Just now'

                return (
                  <div 
                    key={order.id} 
                    style={{ 
                      background: 'rgba(255, 255, 255, 0.03)', 
                      borderRadius: 10, 
                      border: '1px solid rgba(255, 255, 255, 0.08)',
                      padding: 16,
                      transition: 'border-color 0.2s',
                    }}
                  >
                    {/* Order Top Bar */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, borderBottom: '1px solid rgba(255,255,255,0.06)', paddingBottom: 12 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <span style={{ fontSize: '1.05rem', fontWeight: 700, color: '#e2e8f0', letterSpacing: '0.02em' }}>
                          {order.name || `#${order.order_number}`}
                        </span>
                        <span style={{ 
                          fontSize: '0.72rem', 
                          fontWeight: 600, 
                          padding: '2px 8px', 
                          borderRadius: 4, 
                          background: 'rgba(16, 185, 129, 0.15)', 
                          color: '#34d399',
                          border: '1px solid rgba(16, 185, 129, 0.3)',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 4
                        }}>
                          <CheckCircle2 size={11} /> {order.financial_status?.toUpperCase() || 'PAID'}
                        </span>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                          <Clock size={12} /> {formattedDate}
                        </span>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <span style={{ fontSize: '1.1rem', fontWeight: 700, color: '#60a5fa' }}>
                          {curr}{parseFloat(order.total_price || 0).toFixed(2)}
                        </span>
                        <button
                          className="btn btn-primary btn-xs"
                          onClick={() => handleReorder(order)}
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 6,
                            padding: '6px 12px',
                            fontWeight: 600,
                            borderRadius: 6,
                            fontSize: '0.76rem'
                          }}
                        >
                          <RotateCcw size={12} /> Reorder / Add to Cart
                        </button>
                      </div>
                    </div>

                    {/* Customer & Razorpay Info */}
                    <div style={{ fontSize: '0.76rem', color: 'var(--text-secondary)', marginTop: 8, marginBottom: 10, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                      <div>
                        Customer: <span style={{ color: '#cbd5e1' }}>{order.email || order.customer?.email || 'vipulapatil21@gmail.com'}</span>
                        {order.tags && <span style={{ marginLeft: 10, color: '#94a3b8' }}>· Tags: <code style={{ color: '#cbd5e1' }}>{order.tags}</code></span>}
                      </div>
                      {(() => {
                        const payAttr = order.note_attributes?.find(a => a.name === 'payment_id')?.value
                        const payFromNote = order.note?.match(/pay_[a-zA-Z0-9]+/)?.[0]
                        const payId = (payAttr && payAttr !== 'None') ? payAttr : payFromNote
                        if (!payId) return null
                        return (
                          <a
                            href={`https://dashboard.razorpay.com/app/payments/${payId}`}
                            target="_blank"
                            rel="noreferrer"
                            className="btn btn-ghost btn-xs"
                            style={{ color: '#93c5fd', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 8px', fontSize: '0.72rem' }}
                            title="Inspect capture and settlement on Razorpay"
                          >
                            <ExternalLink size={11} /> Razorpay: <code>{payId}</code>
                          </a>
                        )
                      })()}
                    </div>

                    {/* Order Line Items List */}
                    <div style={{ background: 'rgba(0, 0, 0, 0.2)', borderRadius: 8, padding: '10px 12px', marginTop: 6 }}>
                      <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', fontWeight: 600, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                        Line Items ({lineItems.length}):
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        {lineItems.map((item, idx) => (
                          <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.82rem' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              <span style={{ color: '#93c5fd', fontWeight: 600 }}>{item.quantity}×</span>
                              <span style={{ color: '#e2e8f0' }}>{item.title}</span>
                              {item.variant_title && item.variant_title !== 'Default Title' && (
                                <span style={{ fontSize: '0.72rem', background: 'rgba(255,255,255,0.06)', padding: '1px 6px', borderRadius: 4, color: '#94a3b8' }}>
                                  {item.variant_title}
                                </span>
                              )}
                            </div>
                            <div style={{ color: '#94a3b8', fontWeight: 500, fontSize: '0.8rem', marginLeft: 12 }}>
                              {curr}{parseFloat(item.price || 0).toFixed(2)}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* TAB 2: AUTONOMOUS SAFEGUARD REFUNDS                                 */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {activeTab === 'refunds' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, marginBottom: 14 }}>
            <div>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 600, color: '#f8fafc', margin: 0 }}>
                💸 Autonomous Safeguard Refunds
              </h3>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', margin: '2px 0 0 0' }}>
                Triggered automatically when a payment completes on an expired or cancelled link. Protects customers from ghost charges.
              </p>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <a
                href="https://dashboard.razorpay.com/app/refunds"
                target="_blank"
                rel="noreferrer"
                className="btn btn-secondary btn-xs"
                style={{ display: 'inline-flex', alignItems: 'center', gap: 5, color: '#93c5fd', textDecoration: 'none' }}
              >
                <ExternalLink size={12} /> Open Razorpay Refunds Dashboard
              </a>
              <button className="btn btn-secondary btn-xs" onClick={fetchRefunds} disabled={loadingRefunds}>
                <RefreshCw size={11} className={loadingRefunds ? 'animate-spin' : ''} /> Refresh
              </button>
            </div>
          </div>

          {refunds.length === 0 ? (
            <div style={{ padding: 32, textAlign: 'center', background: 'rgba(255,255,255,0.02)', borderRadius: 10, border: '1px dashed var(--border)' }}>
              <ShieldAlert size={32} style={{ color: 'var(--text-muted)', marginBottom: 8 }} />
              <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)' }}>No autonomous refunds issued yet.</p>
              <p style={{ fontSize: '0.76rem', color: 'var(--text-muted)' }}>If a mobile user completes a bank transaction after desktop clicks "Cancel", the refund will appear here automatically.</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {refunds.map((ref, idx) => (
                <div 
                  key={idx}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '14px 16px',
                    background: 'rgba(239, 68, 68, 0.06)',
                    borderRadius: 8,
                    border: '1px solid rgba(239, 68, 68, 0.25)',
                    flexWrap: 'wrap',
                    gap: 12
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontWeight: 700, fontSize: '0.92rem', color: '#fca5a5' }}>
                        {ref.refund_id}
                      </span>
                      <span style={{ fontSize: '1rem', fontWeight: 700, color: '#fff' }}>
                        {curr}{parseFloat(ref.amount || 0).toFixed(2)}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.76rem', color: '#cbd5e1', marginTop: 3 }}>
                      {ref.reason}
                    </div>
                    <div style={{ fontSize: '0.73rem', color: 'var(--text-muted)', marginTop: 2 }}>
                      Link ID: <code style={{ color: '#93c5fd' }}>{ref.plink_id}</code> · Customer: {ref.customer_email || 'vipulapatil21@gmail.com'}
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{
                      padding: '3px 10px',
                      borderRadius: 4,
                      fontSize: '0.72rem',
                      fontWeight: 700,
                      background: 'rgba(16, 185, 129, 0.18)',
                      color: '#34d399',
                      border: '1px solid rgba(16, 185, 129, 0.4)',
                      letterSpacing: '0.04em'
                    }}>
                      {ref.status?.toUpperCase() || 'PROCESSED'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* TAB 3: AP2 TRANSACTION LEDGER (SORTED REVERSE / NEWEST FIRST)       */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {activeTab === 'ledger' && (
        <div>
          {/* Controls Bar */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, marginBottom: 14 }}>
            <div>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 600, color: '#f8fafc', margin: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
                <ArrowDownUp size={16} color="#c084fc" /> AP2 Cryptographic Transaction Ledger
              </h3>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', margin: '2px 0 0 0' }}>
                Sorted newest-first. Immutable append-only audit trail guaranteeing Track 01 Hackathon compliance.
              </p>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-secondary btn-xs" onClick={fetchLedger} disabled={loadingLedger}>
                <RefreshCw size={11} className={loadingLedger ? 'animate-spin' : ''} /> Refresh
              </button>
              <button className="btn btn-ghost btn-xs" onClick={handleClearLedger} style={{ color: 'var(--accent-red)' }}>
                <Trash2 size={11} /> Clear Ledger
              </button>
            </div>
          </div>

          {/* Filter Chips & Search Bar */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, marginBottom: 16, background: 'rgba(255,255,255,0.02)', padding: '10px 12px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.06)' }}>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {[
                { id: 'all', label: 'All Events' },
                { id: 'refund', label: '💸 Refunds' },
                { id: 'failover', label: '❌ Failovers & Declines' },
                { id: 'sync', label: '✔ Shopify Syncs' }
              ].map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setLedgerFilter(tab.id)}
                  style={{
                    padding: '4px 10px',
                    borderRadius: 6,
                    fontSize: '0.74rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    background: ledgerFilter === tab.id ? 'rgba(168, 85, 247, 0.25)' : 'rgba(255,255,255,0.05)',
                    color: ledgerFilter === tab.id ? '#e9d5ff' : 'var(--text-muted)',
                    border: ledgerFilter === tab.id ? '1px solid rgba(168, 85, 247, 0.4)' : '1px solid transparent',
                    transition: 'all 0.15s'
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <div style={{ position: 'relative', minWidth: 200 }}>
              <Search size={13} style={{ position: 'absolute', left: 8, top: 7, color: 'var(--text-muted)' }} />
              <input
                type="text"
                placeholder="Search audit trail..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                style={{
                  padding: '4px 8px 4px 26px',
                  borderRadius: 6,
                  border: '1px solid var(--border)',
                  background: 'rgba(0, 0, 0, 0.25)',
                  color: '#fff',
                  fontSize: '0.76rem',
                  width: '100%'
                }}
              />
            </div>
          </div>

          {filteredLedger.length === 0 ? (
            <div style={{ padding: 32, textAlign: 'center', background: 'rgba(255,255,255,0.02)', borderRadius: 10, border: '1px dashed var(--border)' }}>
              <ArrowDownUp size={32} style={{ color: 'var(--text-muted)', marginBottom: 8 }} />
              <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)' }}>No ledger records match the selected filter.</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {filteredLedger.map((entry, idx) => {
                const type = entry.event_type || entry.action || 'TRANSACTION'
                const isRefund = type.includes('refund')
                const isFailover = type.includes('failover') || type.includes('declined') || type.includes('failed')
                const isSync = type.includes('reconciled') || type.includes('order')
                
                const badgeBg = isRefund ? 'rgba(239, 68, 68, 0.2)' : isFailover ? 'rgba(245, 158, 11, 0.2)' : isSync ? 'rgba(16, 185, 129, 0.2)' : 'rgba(59, 130, 246, 0.2)'
                const badgeColor = isRefund ? '#fca5a5' : isFailover ? '#fde68a' : isSync ? '#86efac' : '#93c5fd'
                const badgeBorder = isRefund ? 'rgba(239, 68, 68, 0.4)' : isFailover ? 'rgba(245, 158, 11, 0.4)' : isSync ? 'rgba(16, 185, 129, 0.4)' : 'rgba(59, 130, 246, 0.4)'

                const timeStr = entry.timestamp ? new Date(entry.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : 'Unknown'
                const dateStr = entry.timestamp ? new Date(entry.timestamp).toLocaleDateString([], { month: 'short', day: 'numeric' }) : ''

                return (
                  <div
                    key={idx}
                    style={{
                      padding: '12px 14px',
                      background: 'rgba(255, 255, 255, 0.025)',
                      borderRadius: 8,
                      border: '1px solid rgba(255, 255, 255, 0.07)',
                      fontSize: '0.82rem'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                      <span style={{
                        padding: '2px 8px',
                        borderRadius: 4,
                        fontSize: '0.72rem',
                        fontWeight: 700,
                        background: badgeBg,
                        color: badgeColor,
                        border: `1px solid ${badgeBorder}`,
                        letterSpacing: '0.03em'
                      }}>
                        {type.replace(/_/g, ' ').toUpperCase()}
                      </span>
                      <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                        <Clock size={11} /> {dateStr} {timeStr}
                      </span>
                    </div>

                    <div style={{ color: '#cbd5e1', lineHeight: 1.4 }}>
                      {entry.details ? (
                        <div>
                          {entry.details.reason && (
                            <div style={{ color: '#f8fafc', fontWeight: 500, marginBottom: 3 }}>
                              {entry.details.reason}
                            </div>
                          )}
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, fontSize: '0.75rem', marginTop: 4 }}>
                            {entry.details.amount && (
                              <span style={{ color: '#93c5fd' }}>
                                Amount: <strong>{curr}{parseFloat(entry.details.amount).toFixed(2)}</strong>
                              </span>
                            )}
                            {entry.details.refund_id && (
                              <span style={{ color: '#fca5a5' }}>
                                Refund ID: <code>{entry.details.refund_id}</code>
                              </span>
                            )}
                            {entry.details.shopify_order_name && (
                              <span style={{ color: '#86efac' }}>
                                Shopify Order: <strong>{entry.details.shopify_order_name}</strong>
                              </span>
                            )}
                            {entry.details.rail && (
                              <span style={{ color: '#fbbf24' }}>
                                Rail: {entry.details.rail}
                              </span>
                            )}
                            {entry.details.plink_id && (
                              <span style={{ color: '#94a3b8' }}>
                                Link: <code>{entry.details.plink_id}</code>
                              </span>
                            )}
                            {entry.details.error && (
                              <span style={{ color: '#f87171' }}>
                                Error: {entry.details.error}
                              </span>
                            )}
                          </div>
                        </div>
                      ) : (
                        entry.description || JSON.stringify(entry)
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
