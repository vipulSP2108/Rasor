import React, { useState } from 'react'
import { User, Shield, CreditCard, Smartphone, Check, Sparkles, Copy, Sliders, ArrowRight } from 'lucide-react'
import { useApp } from '../context/AppContext'
import toast from 'react-hot-toast'

const SIZES = ['XS', 'S', 'M', 'L', 'XL', 'XXL', '3XL']
const FITS = ['Regular Fit', 'Oversized', 'Slim Fit', 'Any']
const BANKS = [
  { code: 'CNRB', name: 'Canara Bank' },
  { code: 'BARB_R', name: 'Bank of Baroda (Retail)' },
  { code: 'PUNB_R', name: 'Punjab National Bank' },
  { code: 'SBIN', name: 'State Bank of India' },
  { code: 'HDFC', name: 'HDFC Bank' },
  { code: 'ICIC', name: 'ICICI Bank' },
]

function Toggle({ checked, onChange }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <label className="toggle">
        <input type="checkbox" checked={!!checked} onChange={e => onChange(e.target.checked)} />
        <div className="toggle-track" />
      </label>
      <span style={{ 
        fontSize: '0.72rem', 
        fontWeight: 700, 
        padding: '2px 8px', 
        borderRadius: 4,
        letterSpacing: '0.04em',
        background: checked ? 'rgba(16, 185, 129, 0.2)' : 'rgba(255, 255, 255, 0.08)',
        color: checked ? '#34d399' : '#94a3b8',
        border: checked ? '1px solid rgba(16, 185, 129, 0.4)' : '1px solid rgba(255, 255, 255, 0.15)'
      }}>
        {checked ? 'ENABLED' : 'DISABLED'}
      </span>
    </div>
  )
}

export default function ProfilePanel() {
  const { userProfile, updateUserProfile } = useApp()
  const [form, setForm] = useState(userProfile)
  const [copiedCard, setCopiedCard] = useState(false)

  const handleSave = (e) => {
    e.preventDefault()
    updateUserProfile(form)
    toast.success('Profile preferences saved successfully!')
  }

  const handleCopyCard = () => {
    navigator.clipboard.writeText(form.fallbackCard?.cardNumber || '4012000000000002')
    setCopiedCard(true)
    toast.success('Test Card copied to clipboard!')
    setTimeout(() => setCopiedCard(false), 2000)
  }

  return (
    <div className="settings-panel animate-fade" style={{ margin: '0 auto', maxWidth: 840 }}>
      <div style={{ marginBottom: 20 }}>
        <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <User size={28} style={{ color: 'var(--accent-purple)' }} />
          User Profile & Autonomous Commerce
        </h1>
        <p className="page-subtitle">
          Manage your personal apparel sizing defaults, contact handset, and prioritized payment rails for autonomous failover.
        </p>
      </div>

      <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        {/* Section 1: Apparel Sizing Defaults */}
        <div className="settings-section">
          <div className="settings-section-header">
            <Sliders size={18} />
            <span>Apparel Sizing & Stylist Defaults</span>
          </div>
          <div className="settings-section-body">
            <div>
              <div className="settings-label" style={{ marginBottom: 10 }}>
                <strong>Default Size (Sticky Selection)</strong>
                <span>Searches and "Add to Cart" modals will automatically default to this size.</span>
              </div>
              <div className="radio-group">
                {SIZES.map(s => (
                  <button
                    key={s}
                    type="button"
                    className={`radio-option ${form.defaultSize === s ? 'selected' : ''}`}
                    onClick={() => setForm(f => ({ ...f, defaultSize: s }))}
                    style={{ minWidth: 44, textAlign: 'center', fontWeight: 700 }}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            <div className="divider" style={{ margin: '8px 0' }} />

            <div>
              <div className="settings-label" style={{ marginBottom: 10 }}>
                <strong>Preferred Silhouette / Fit</strong>
                <span>Used by the AI Stylist when an item comes in multiple cuts.</span>
              </div>
              <div className="radio-group">
                {FITS.map(fit => (
                  <button
                    key={fit}
                    type="button"
                    className={`radio-option ${form.preferredFit === fit ? 'selected' : ''}`}
                    onClick={() => setForm(f => ({ ...f, preferredFit: fit }))}
                  >
                    {fit}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Section 2: Autonomous Payment Cascade (Demo 3) */}
        <div className="settings-section">
          <div className="settings-section-header" style={{ display: 'flex', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Shield size={18} style={{ color: 'var(--accent-green)' }} />
              <span>Autonomous Payment Cascade (Demo 3 Rails)</span>
            </div>
            <span style={{ fontSize: '0.75rem', color: 'var(--accent-green)', fontWeight: 600 }}>
              Multi-Rail AP2 Architecture
            </span>
          </div>
          <div className="settings-section-body">
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              Define your prioritized payment instruments. If the primary rail declines at bank authorization, 
              the autonomous agent automatically failovers down your hierarchy in sequence.
            </p>

            {/* Tier 1 */}
            <div className="settings-row" style={{ alignItems: 'center' }}>
              <div className="settings-label">
                <strong style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ 
                    background: 'var(--accent-green)', color: '#fff', 
                    borderRadius: 99, width: 20, height: 20, 
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 11 
                  }}>1</span>
                  Tier 1: Primary Rail (Netbanking)
                </strong>
                <span>The first instrument attempted during autonomous checkout.</span>
              </div>
              <select
                className="select"
                value={form.primaryBank}
                onChange={e => {
                  const b = BANKS.find(x => x.code === e.target.value)
                  setForm(f => ({ ...f, primaryBank: b.code, primaryBankLabel: b.name }))
                }}
              >
                {BANKS.map(b => (
                  <option key={b.code} value={b.code}>{b.name}</option>
                ))}
              </select>
            </div>

            {/* Tier 2 */}
            <div className="settings-row" style={{ alignItems: 'center' }}>
              <div className="settings-label">
                <strong style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ 
                    background: 'var(--accent-amber)', color: '#fff', 
                    borderRadius: 99, width: 20, height: 20, 
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 11 
                  }}>2</span>
                  Tier 2: Secondary Rail (Netbanking / Wallet)
                </strong>
                <span>Autonomous failover destination if Tier 1 is declined.</span>
              </div>
              <select
                className="select"
                value={form.secondaryBank}
                onChange={e => {
                  const b = BANKS.find(x => x.code === e.target.value)
                  setForm(f => ({ ...f, secondaryBank: b.code, secondaryBankLabel: b.name }))
                }}
              >
                {BANKS.map(b => (
                  <option key={b.code} value={b.code}>{b.name}</option>
                ))}
              </select>
            </div>

            {/* Tier 3 */}
            <div className="settings-row" style={{ alignItems: 'flex-start' }}>
              <div className="settings-label">
                <strong style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ 
                    background: 'var(--accent-purple)', color: '#fff', 
                    borderRadius: 99, width: 20, height: 20, 
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 11 
                  }}>3</span>
                  Tier 3: Final Fallback Rail (Saved / Test Card)
                </strong>
                <span>The final safeguard rail before triggering mobile link rescue.</span>
              </div>
              <div style={{
                background: 'var(--bg-base)', border: '1px solid var(--border)',
                borderRadius: 'var(--radius-md)', padding: '10px 14px', width: 260
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                  <span style={{ fontSize: '0.8rem', fontWeight: 700 }}>{form.fallbackCard?.nickname || 'Test Visa'}</span>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={handleCopyCard}
                    style={{ padding: '2px 6px', fontSize: '0.72rem' }}
                  >
                    {copiedCard ? <Check size={12} /> : <Copy size={12} />}
                    {copiedCard ? 'Copied' : 'Copy'}
                  </button>
                </div>
                <div style={{ fontFamily: 'monospace', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                  •••• •••• •••• {form.fallbackCard?.last4 || '0002'} ({form.fallbackCard?.exp || '12/28'})
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Section 3: Contact & Handset Information */}
        <div className="settings-section">
          <div className="settings-section-header">
            <Smartphone size={18} />
            <span>Contact & Handset Information</span>
          </div>
          <div className="settings-section-body">
            <div className="settings-row">
              <div className="settings-label">
                <strong>Full Name</strong>
                <span>Passed to Razorpay prefill and shipping manifests.</span>
              </div>
              <input
                type="text"
                className="input"
                style={{ width: 260 }}
                value={form.fullName || ''}
                onChange={e => setForm(f => ({ ...f, fullName: e.target.value }))}
              />
            </div>

            <div className="settings-row">
              <div className="settings-label">
                <strong>Handset Phone Number</strong>
                <span>Primary ID for Razorpay saved cards, UPI, and WhatsApp payment link rescue.</span>
              </div>
              <input
                type="text"
                className="input"
                style={{ width: 260 }}
                value={form.phone || ''}
                onChange={e => setForm(f => ({ ...f, phone: e.target.value }))}
                placeholder="+918806549952"
              />
            </div>

            <div className="settings-row">
              <div className="settings-label">
                <strong>Email Address</strong>
                <span>Used for Shopify receipt generation and AP2 Intent Mandates.</span>
              </div>
              <input
                type="email"
                className="input"
                style={{ width: 260 }}
                value={form.email || ''}
                onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                placeholder="vipulapatil21@gmail.com"
              />
            </div>
          </div>
        </div>

        {/* Section 4: Mobile Rescue & Notification Controls (Anti-Spam) */}
        <div className="settings-section">
          <div className="settings-section-header">
            <Smartphone size={18} style={{ color: 'var(--accent-blue)' }} />
            <span>Mobile Rescue & Notification Controls (Anti-Spam Testing)</span>
          </div>
          <div className="settings-section-body">
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              Control how the autonomous agent sends mobile fallback links. You can toggle off SMS to prevent phone spam during repeated testing.
            </p>

            {/* Toggle SMS */}
            <div className="settings-row" style={{ alignItems: 'center' }}>
              <div className="settings-label">
                <strong>Send Real SMS via Razorpay</strong>
                <span>
                  Dispatches carrier SMS to {form.phone || '+91 88065 49952'} containing the link. Turn OFF during testing to prevent SMS spam.
                </span>
              </div>
              <Toggle
                checked={form.enableSmsNotification ?? true}
                onChange={v => setForm(f => ({ ...f, enableSmsNotification: v }))}
              />
            </div>

            {/* Toggle WhatsApp */}
            <div className="settings-row" style={{ alignItems: 'center' }}>
              <div className="settings-label">
                <strong>Enable WhatsApp Mobile Rescue</strong>
                <span>
                  Generates 1-click WhatsApp app / web links for payment rescue away from desktop.
                </span>
              </div>
              <Toggle
                checked={form.enableWhatsappRescue ?? true}
                onChange={v => setForm(f => ({ ...f, enableWhatsappRescue: v }))}
              />
            </div>
          </div>
        </div>

        {/* Submit */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
          <button type="submit" className="btn btn-primary btn-lg">
            <Check size={18} />
            Save Profile Preferences
          </button>
        </div>
      </form>
    </div>
  )
}
