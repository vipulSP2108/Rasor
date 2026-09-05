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

const MONK_TONES = [
  { tone: 1, hex: '#F6EDE4', label: 'MST 1 (Light)' },
  { tone: 2, hex: '#F3E7DB', label: 'MST 2' },
  { tone: 3, hex: '#F7EADC', label: 'MST 3' },
  { tone: 4, hex: '#EAD0B3', label: 'MST 4' },
  { tone: 5, hex: '#D7BD96', label: 'MST 5 (Medium)' },
  { tone: 6, hex: '#9E7A5A', label: 'MST 6' },
  { tone: 7, hex: '#7C563D', label: 'MST 7' },
  { tone: 8, hex: '#634433', label: 'MST 8' },
  { tone: 9, hex: '#4B3629', label: 'MST 9' },
  { tone: 10, hex: '#2F241E', label: 'MST 10 (Deep)' },
]

const inferUndertone = (jewelry, sun, vein) => {
  let warm = 0
  let cool = 0
  if (jewelry === 'gold') warm++
  if (jewelry === 'silver') cool++
  if (sun === 'tan') warm++
  if (sun === 'burn') cool++
  if (vein === 'green') warm++
  if (vein === 'blue') cool++
  if (warm === 0 && cool === 0) return null
  if (warm > cool) return 'warm'
  if (cool > warm) return 'cool'
  return 'neutral'
}

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
  const { userProfile, updateUserProfile, config, updateConfig } = useApp()
  const [form, setForm] = useState(() => ({
    ...userProfile,
    skinDepth: userProfile?.skinDepth !== undefined ? userProfile.skinDepth : null,
    undertone: userProfile?.undertone || null,
    quizJewelry: userProfile?.quizJewelry || null,
    quizSun: userProfile?.quizSun || null,
    quizVein: userProfile?.quizVein || null,
    email: userProfile?.email || config?.customerEmail || 'vipulapatil21@gmail.com',
    customerEmail: config?.customerEmail || userProfile?.email || 'vipulapatil21@gmail.com',
    userLocation: config?.userLocation || userProfile?.userLocation || 'Mumbai',
  }))
  const [copiedCard, setCopiedCard] = useState(false)

  const handleSave = (e) => {
    e.preventDefault()
    const emailVal = form.email || form.customerEmail || 'vipulapatil21@gmail.com'
    const locVal = form.userLocation || 'Mumbai'
    updateUserProfile({
      ...form,
      email: emailVal,
      customerEmail: emailVal,
      userLocation: locVal,
    })
    updateConfig({
      customerEmail: emailVal,
      userLocation: locVal,
    })
    toast.success('Profile preferences & customer details saved successfully!')
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

        {/* Section 1B: Personal Color Theory & Skin Undertone (Decision D-08) */}
        <div className="settings-section">
          <div className="settings-section-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Sparkles size={18} style={{ color: 'var(--accent-purple)' }} />
              <span>Personal Skin Tone Palette (Optional Soft Boost)</span>
            </div>
            <span style={{ fontSize: '0.75rem', color: 'var(--accent-purple)', fontWeight: 600 }}>
              Non-Compulsory • +0.0 to +0.15 Boost
            </span>
          </div>
          <div className="settings-section-body">
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              This optional profile gives a gentle positive affinity boost to upper garments closest to your face using the Monk Skin Tone scale and color harmony science. It never hides products or interferes with checkout.
            </p>

            {/* Monk Skin Tone Depth Slider / Swatches */}
            <div>
              <div className="settings-label" style={{ marginBottom: 10 }}>
                <strong>Monk Skin Tone Scale (MST Depth: {form.skinDepth ? `${form.skinDepth}/10` : 'None / Any'})</strong>
                <span>Select your skin depth from light (1) to deep (10), or Skip/Any:</span>
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                <button
                  type="button"
                  className={`monk-chip ${form.skinDepth === null ? 'selected' : ''}`}
                  style={{ 
                    width: 'auto', 
                    minWidth: 54, 
                    height: 34, 
                    padding: '0 10px', 
                    background: form.skinDepth === null ? 'rgba(99, 102, 241, 0.25)' : 'rgba(255, 255, 255, 0.05)',
                    border: form.skinDepth === null ? '2px solid var(--accent-purple)' : '1px solid var(--border)',
                    borderRadius: 8,
                    color: form.skinDepth === null ? '#fff' : 'var(--text-secondary)',
                    fontSize: '0.78rem',
                    fontWeight: 600,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 4
                  }}
                  title="Skip / None (No Depth Preference)"
                  onClick={() => setForm(f => ({ ...f, skinDepth: null }))}
                >
                  {form.skinDepth === null && <Check size={12} color="#fff" />}
                  <span>Any</span>
                </button>
                {MONK_TONES.map(m => (
                  <button
                    key={m.tone}
                    type="button"
                    className={`monk-chip ${form.skinDepth === m.tone ? 'selected' : ''}`}
                    style={{ background: m.hex, width: 34, height: 34 }}
                    title={m.label}
                    onClick={() => setForm(f => ({ ...f, skinDepth: m.tone }))}
                  >
                    {form.skinDepth === m.tone && <Check size={14} color={m.tone > 5 ? '#fff' : '#000'} />}
                  </button>
                ))}
              </div>
            </div>

            <div className="divider" style={{ margin: '14px 0' }} />

            {/* 3-Question Undertone Self-Report Quiz */}
            <div>
              <div className="settings-label" style={{ marginBottom: 12 }}>
                <strong>3-Question Undertone Self-Report Quiz</strong>
                <span>Tap your natural responses to automatically determine your undertone (or select Skip/Any):</span>
              </div>

              {/* Q1: Jewelry */}
              <div style={{ marginBottom: 12 }}>
                <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)', display: 'block', marginBottom: 6 }}>
                  1. Which metal looks best against your skin?
                </span>
                <div className="radio-group">
                  {[
                    { id: 'gold', label: 'Gold Jewelry (Warm)' },
                    { id: 'silver', label: 'Silver / White Gold (Cool)' },
                    { id: 'both', label: 'Both Look Equally Flattering (Neutral)' },
                    { id: 'any', label: 'Any / Skip (No Preference)' }
                  ].map(opt => (
                    <button
                      key={opt.id}
                      type="button"
                      className={`radio-option ${(form.quizJewelry === opt.id || (!form.quizJewelry && opt.id === 'any')) ? 'selected' : ''}`}
                      onClick={() => {
                        const newQ = { ...form, quizJewelry: opt.id === 'any' ? null : opt.id }
                        const newUt = inferUndertone(newQ.quizJewelry, newQ.quizSun, newQ.quizVein)
                        setForm(f => ({ ...f, quizJewelry: opt.id === 'any' ? null : opt.id, undertone: newUt }))
                      }}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Q2: Sun Response */}
              <div style={{ marginBottom: 12 }}>
                <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)', display: 'block', marginBottom: 6 }}>
                  2. How does your skin respond to direct sunlight?
                </span>
                <div className="radio-group">
                  {[
                    { id: 'tan', label: 'Tans easily, rarely burns (Warm)' },
                    { id: 'burn', label: 'Burns easily, rarely tans (Cool)' },
                    { id: 'mixed', label: 'Burns initially, then turns tan (Neutral)' },
                    { id: 'any', label: 'Any / Skip (No Preference)' }
                  ].map(opt => (
                    <button
                      key={opt.id}
                      type="button"
                      className={`radio-option ${(form.quizSun === opt.id || (!form.quizSun && opt.id === 'any')) ? 'selected' : ''}`}
                      onClick={() => {
                        const newQ = { ...form, quizSun: opt.id === 'any' ? null : opt.id }
                        const newUt = inferUndertone(newQ.quizJewelry, newQ.quizSun, newQ.quizVein)
                        setForm(f => ({ ...f, quizSun: opt.id === 'any' ? null : opt.id, undertone: newUt }))
                      }}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Q3: Wrist Veins */}
              <div style={{ marginBottom: 12 }}>
                <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)', display: 'block', marginBottom: 6 }}>
                  3. What color do the veins on your inner wrist appear?
                </span>
                <div className="radio-group">
                  {[
                    { id: 'green', label: 'Greenish / Olive (Warm)' },
                    { id: 'blue', label: 'Blueish / Purple (Cool)' },
                    { id: 'mixed', label: 'Blue-green or difficult to tell (Neutral)' },
                    { id: 'any', label: 'Any / Skip (Difficult to Tell)' }
                  ].map(opt => (
                    <button
                      key={opt.id}
                      type="button"
                      className={`radio-option ${(form.quizVein === opt.id || (!form.quizVein && opt.id === 'any')) ? 'selected' : ''}`}
                      onClick={() => {
                        const newQ = { ...form, quizVein: opt.id === 'any' ? null : opt.id }
                        const newUt = inferUndertone(newQ.quizJewelry, newQ.quizSun, newQ.quizVein)
                        setForm(f => ({ ...f, quizVein: opt.id === 'any' ? null : opt.id, undertone: newUt }))
                      }}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Inferred Undertone Badge */}
              <div style={{ 
                marginTop: 14, 
                padding: '10px 14px', 
                background: 'rgba(99, 102, 241, 0.1)', 
                border: '1px solid rgba(99, 102, 241, 0.3)', 
                borderRadius: 'var(--radius-sm)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between'
              }}>
                <div>
                  <strong style={{ color: '#fff', fontSize: '0.85rem' }}>Active Undertone Affinity:</strong>
                  <span style={{ display: 'block', fontSize: '0.76rem', color: 'var(--text-secondary)' }}>
                    {(!form.undertone || form.undertone === 'any') && 'Neutral / Any • Zero color bias applied (all colorways treated equally)'}
                    {form.undertone === 'warm' && 'Warm Undertone • Flattering tones: Olive Green, Mustard, Terracotta, Warm Beige'}
                    {form.undertone === 'cool' && 'Cool Undertone • Flattering tones: Cobalt Blue, Dark Navy, Burgundy, Crisp White'}
                    {form.undertone === 'neutral' && 'Neutral / Olive Undertone • Flattering tones: Charcoal, Heather Grey, Sand Beige, Muted Tones'}
                  </span>
                </div>
                <span style={{ 
                  background: (!form.undertone || form.undertone === 'any') ? 'rgba(255, 255, 255, 0.12)' : 'var(--accent-purple)', 
                  color: '#fff', 
                  padding: '4px 10px', 
                  borderRadius: 99, 
                  fontSize: '0.74rem', 
                  fontWeight: 700,
                  textTransform: 'uppercase'
                }}>
                  {form.undertone || 'ANY / NONE'}
                </span>
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

        {/* Section 3: Customer Details & Delivery Location */}
        <div className="settings-section">
          <div className="settings-section-header">
            <span style={{ fontSize: 18 }}>👤</span>
            <span>Customer Details & Delivery Location</span>
          </div>
          <div className="settings-section-body">
            <div className="settings-row">
              <div className="settings-label">
                <strong>Shopify Account Email</strong>
                <span>Orders will be synced under this account and used for AP2 Intent Mandates.</span>
              </div>
              <input
                type="email"
                className="input"
                style={{ width: 260 }}
                value={form.email || form.customerEmail || ''}
                onChange={e => setForm(f => ({ ...f, email: e.target.value, customerEmail: e.target.value }))}
                placeholder="vipulapatil21@gmail.com"
              />
            </div>

            <div className="settings-row">
              <div className="settings-label">
                <strong>Default Delivery Location</strong>
                <span>Used for delivery distance calculations & warehouse routing.</span>
              </div>
              <input
                type="text"
                className="input"
                style={{ width: 260 }}
                value={form.userLocation || ''}
                onChange={e => setForm(f => ({ ...f, userLocation: e.target.value }))}
                placeholder="e.g. 424001, Mumbai, Delhi"
              />
            </div>

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
