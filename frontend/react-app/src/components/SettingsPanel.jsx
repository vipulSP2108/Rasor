import React from 'react'
import { useState, useEffect } from 'react'
import { Key, ShieldCheck, PlusCircle, CheckCircle2, AlertCircle, Trash2 } from 'lucide-react'
import { useApp } from '../context/AppContext'
import { useVoice } from '../hooks/useVoice'
import { bulkCancelPaymentLinks, cleanStaleRescueLinks } from '../api/client'
import toast from 'react-hot-toast'

// ── High-Contrast Visible Toggle Component ──────────────────────────
function Toggle({ checked, onChange, label }) {
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

// ── Settings Row ──────────────────────────────────────────────
function Row({ label, hint, children }) {
  return (
    <div className="settings-row" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 0', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
      <div className="settings-label" style={{ maxWidth: '60%' }}>
        <strong style={{ display: 'block', fontSize: '0.88rem', color: '#f1f5f9', marginBottom: 2 }}>{label}</strong>
        {hint && <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', lineHeight: 1.3, display: 'block' }}>{hint}</span>}
      </div>
      <div>{children}</div>
    </div>
  )
}

// ── Section ───────────────────────────────────────────────────
function Section({ icon, title, children }) {
  return (
    <div className="settings-section card" style={{ marginBottom: 20, padding: 20 }}>
      <div className="settings-section-header" style={{ fontSize: '1rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14, color: '#e0e7ff', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: 10 }}>
        {icon} {title}
      </div>
      <div className="settings-section-body">{children}</div>
    </div>
  )
}

export default function SettingsPanel() {
  const {
    config,
    updateConfig,
    razorpayToken,
    razorpayCustomerId,
    tokenMaxLimit,
    setRazorpayCustomerId,
    updateMandateTokenId,
    updateMandateLimit,
    saveMandateToken,
    clearMandateToken,
    userProfile,
    updateUserProfile
  } = useApp()

  const { voices, speak } = useVoice()
  const curr = config.currency === 'INR' ? '₹' : '$'
  const [isDeletingLinks, setIsDeletingLinks] = useState(false)

  const handleDeletePaymentLinks = async () => {
    setIsDeletingLinks(true)
    toast.loading('Scanning Razorpay links & cleaning rescue cache…', { id: 'bulk-cancel' })
    try {
      // Step 1: Cancel any still-active Razorpay payment links
      const { data: cancelData } = await bulkCancelPaymentLinks()
      // Step 2: Always clean stale local rescue dummy entries (plink_test_*)
      const { data: cleanData } = await cleanStaleRescueLinks().catch(() => ({ data: { removed_count: 0 } }))
      const staleRemoved = cleanData?.removed_count ?? 0

      if (cancelData.success) {
        localStorage.removeItem('rasor_active_plink')
        localStorage.removeItem('rasor_rescue_module_active')
        localStorage.removeItem('rasor_cascade_state')
        toast.success(
          `🧹 Cleanup Complete: Cancelled ${cancelData.cancelled_count} Razorpay link(s) · Removed ${staleRemoved} stale rescue cache entries (Scanned: ${cancelData.total_scanned})`,
          { id: 'bulk-cancel', duration: 6000 }
        )
      } else {
        toast.error('Cleanup failed: ' + cancelData.error, { id: 'bulk-cancel' })
      }
    } catch (e) {
      toast.error('Failed to cancel payment links: ' + (e.response?.data?.detail || e.message), { id: 'bulk-cancel' })
    } finally {
      setIsDeletingLinks(false)
    }
  }



  return (
    <div className="settings-panel animate-fade-in" style={{ maxWidth: 880, margin: '0 auto' }}>
      <div className="page-title" style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: 4 }}>⚙️ System Settings & Mandates</div>
      <p className="page-subtitle" style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: 24 }}>
        Configure AP2 autonomous execution, mandate token limits, guardrails, and data sources
      </p>

      {/* ── Razorpay Mandate Token Section ── */}
      <Section icon={<Key size={18} color="#fbbf24" />} title="Razorpay Recurring Mandate Token (Demo 2)">
        <div style={{ padding: '12px 16px', background: 'rgba(99, 102, 241, 0.08)', borderRadius: 8, border: '1px solid rgba(99, 102, 241, 0.25)', marginBottom: 16 }}>
          <div className="flex items-center justify-between" style={{ flexWrap: 'wrap', gap: 10 }}>
            <div>
              <div style={{ fontSize: '0.82rem', fontWeight: 600, color: '#e0e7ff', marginBottom: 2 }}>
                Mandate Status: {razorpayToken ? <span style={{ color: '#34d399' }}>🟢 Active & Ready for Demo 2</span> : <span style={{ color: '#f87171' }}>🔴 No Token Saved (Demo 1 Required)</span>}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                Demo 2 server-to-server payments use this token. It is automatically saved when completing a purchase in Demo 1.
              </div>
            </div>
            <div className="flex gap-2">
              <button
                className="btn btn-secondary btn-xs"
                onClick={() => {
                  const testTok = `tok_test_${Math.random().toString(36).slice(2, 9)}`
                  const testCust = `cust_test_${Math.random().toString(36).slice(2, 6)}`
                  saveMandateToken(testTok, testCust, 800)
                  toast.success('Generated Test Token (Authorized up to ₹800)')
                }}
                style={{ fontSize: '0.72rem' }}
              >
                + Generate Test Token (₹800)
              </button>
              {razorpayToken && (
                <button
                  className="btn btn-ghost btn-xs"
                  onClick={() => {
                    clearMandateToken()
                    toast('Mandate token cleared', { icon: '🗑️' })
                  }}
                  style={{ color: '#fca5a5', fontSize: '0.72rem' }}
                >
                  Clear Token
                </button>
              )}
            </div>
          </div>
        </div>

        <Row label="Active Mandate Token ID" hint="Stored token used for autonomous S2S payment capture">
          <input
            className="input"
            value={razorpayToken || ''}
            placeholder="No token (Run Demo 1 first)"
            onChange={e => updateMandateTokenId(e.target.value)}
            style={{ minWidth: 260, fontSize: '0.8rem', fontFamily: 'monospace' }}
          />
        </Row>

        <Row label="Customer ID" hint="Associated Razorpay Customer record">
          <input
            className="input"
            value={razorpayCustomerId || ''}
            placeholder="e.g. cust_12345"
            onChange={e => setRazorpayCustomerId(e.target.value)}
            style={{ minWidth: 260, fontSize: '0.8rem', fontFamily: 'monospace' }}
          />
        </Row>

        <Row label={`Token Authorized Limit (${curr})`} hint="Transactions above this amount will reject Demo 2 and require Demo 1">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <input
              type="number"
              className="input"
              value={tokenMaxLimit || 0}
              onChange={e => updateMandateLimit(Number(e.target.value))}
              style={{ width: 140, fontSize: '0.85rem' }}
            />
            {/* <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              (Tracks max purchase authorized in Demo 1)
            </span> */}
          </div>
        </Row>
      </Section>

      {/* ── Financial Guardrails ── */}
      <Section icon={<ShieldCheck size={18} color="var(--accent-green)" />} title="Financial Guardrails & Safety Caps">
        <Row label={`Demo 2 Autonomous Hard Cap (${curr})`} hint="Absolute ceiling for Demo 2 autonomous checkout (e.g. ₹2,000)">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 220 }}>
            <input type="range" className="range-input" min={100} max={10000} step={100}
              value={config.maxCostHitl} onChange={e => updateConfig({ maxCostHitl: +e.target.value })} />
            <div className="flex justify-between text-xs text-muted">
              <span>Current Cap: <strong>{curr}{config.maxCostHitl?.toLocaleString()}</strong></span>
              <span>Max: {curr}10,000</span>
            </div>
          </div>
        </Row>
        <Row label={`Global Maximum Budget (${curr})`} hint="Strict upper limit for the entire shopping cart">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 220 }}>
            <input type="range" className="range-input" min={config.maxCostHitl || 500} max={30000} step={200}
              value={config.maxBudget} onChange={e => updateConfig({ maxBudget: +e.target.value })} />
            <div className="flex justify-between text-xs text-muted">
              <span>Budget Cap: <strong>{curr}{config.maxBudget?.toLocaleString()}</strong></span>
              <span>Max: {curr}30,000</span>
            </div>
          </div>
        </Row>
        <Row label="Cart Mandate & Payment Link Expiry (Minutes)" hint="Active duration before AP2 price freeze and mobile rescue links expire (Razorpay API requires min 15 minutes)">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <input
              type="number"
              className="input"
              style={{ width: 90, textAlign: 'center' }}
              min={15}
              max={120}
              value={config.paymentLinkExpiryMinutes || 15}
              onChange={e => updateConfig({ paymentLinkExpiryMinutes: Math.max(15, Number(e.target.value)) })}
            />
            <span className="text-sm text-muted">minutes (min: 15)</span>
          </div>
        </Row>
        <Row
          label="Customer Payment Deadline Safety Buffer (Minutes)"
          hint="Buffer subtracted from link expiry so the customer is asked to complete payment earlier (e.g., 15m expiry - 1m buffer tells customer to complete by 14m before the exact deadline, preventing last-second network lapses)"
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <input
              type="number"
              className="input"
              style={{ width: 90, textAlign: 'center' }}
              min={0}
              max={10}
              value={config.paymentBufferMinutes ?? 1}
              onChange={e => updateConfig({ paymentBufferMinutes: Math.max(0, Math.min(10, Number(e.target.value))) })}
            />
            <span className="text-sm text-muted">minute buffer (0-10 mins)</span>
          </div>
        </Row>
      </Section>

      {/* ── Mobile Rescue & Anti-Spam Controls ── */}
      <Section icon="📱" title="Mobile Rescue & Anti-Spam Notification Controls">
        <Row
          label="Send Real SMS via Razorpay"
          hint="Dispatches carrier SMS with payment link to handset. Turn OFF during testing to prevent SMS spam."
        >
          <Toggle
            checked={userProfile?.enableSmsNotification ?? true}
            onChange={v => updateUserProfile({ enableSmsNotification: v })}
          />
        </Row>
        <Row
          label="Enable WhatsApp Deep-Link Rescue"
          hint="Generates 1-click WhatsApp app / web links for payment rescue away from desktop."
        >
          <Toggle
            checked={userProfile?.enableWhatsappRescue ?? true}
            onChange={v => updateUserProfile({ enableWhatsappRescue: v })}
          />
        </Row>
      </Section>

      {/* ── Delete Payment Links (Razorpay Test Mode Cleanup) ── */}
      <Section icon={<Trash2 size={18} color="#f87171" />} title="Payment Links Quota & Cleanup">
        <div style={{ padding: '14px 16px', background: 'rgba(239, 68, 68, 0.08)', borderRadius: 8, border: '1px solid rgba(239, 68, 68, 0.25)', marginBottom: 6 }}>
          <div style={{ fontSize: '0.86rem', fontWeight: 700, color: '#fca5a5', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
            <Trash2 size={15} /> Razorpay Test Mode Ceiling (30 Links — Cumulative)
          </div>
          <p style={{ fontSize: '0.78rem', color: '#cbd5e1', lineHeight: 1.5, margin: '6px 0 10px 0' }}>
            <strong>Why you see "limit of 30 reached":</strong> Razorpay counts all-time created payment links in test mode — cancelled, expired, and paid links all count. <em>Cancelling them does NOT restore quota.</em> The 30-link ceiling is permanent per test account.
          </p>
          <p style={{ fontSize: '0.78rem', color: '#6ee7b7', lineHeight: 1.5, margin: '0 0 10px 0' }}>
            ⚡ <strong>Already handled automatically:</strong> When the 30-link ceiling is hit, Rasor switches to <strong>Razorpay Orders API</strong> (no 30-link limit). Your QR code and WhatsApp rescue checkout opens a live <code style={{ background: 'rgba(255,255,255,0.08)', padding: '1px 4px', borderRadius: 3 }}>/pay/&#123;order_id&#125;</code> checkout page — fully functional with no restrictions.
          </p>
          <p style={{ fontSize: '0.78rem', color: '#fbbf24', lineHeight: 1.5, margin: '0 0 14px 0' }}>
            🧹 <strong>Use the button below</strong> to: (1) cancel any still-active Razorpay links and (2) remove stale local rescue cache entries that show "no longer active".
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <button
              type="button"
              className="btn btn-sm"
              style={{ background: '#ef4444', color: '#fff', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: 6, border: 'none', padding: '8px 16px', borderRadius: 6, cursor: 'pointer' }}
              disabled={isDeletingLinks}
              onClick={handleDeletePaymentLinks}
            >
              {isDeletingLinks ? <span className="spinner" /> : <Trash2 size={14} />}
              {isDeletingLinks ? 'Cleaning Up...' : 'Bulk-Cancel Active Links & Clean Rescue Cache'}
            </button>
            <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
              Cancels active Razorpay links &amp; purges stale local rescue dummy records.
            </span>
          </div>
        </div>
      </Section>

      {/* ── Customer Details ── */}
      <Section icon="👤" title="Customer Details & Delivery Location">
        <Row label="Shopify Account Email" hint="Orders will be synced under this account">
          <input
            className="input"
            value={config.customerEmail}
            onChange={e => updateConfig({ customerEmail: e.target.value })}
            style={{ minWidth: 260 }}
          />
        </Row>
        <Row label="Default Delivery Location" hint="Used for delivery distance calculations & warehouse routing">
          <input
            className="input"
            value={config.userLocation || ''}
            placeholder="e.g. 424001, Mumbai, Delhi"
            onChange={e => updateConfig({ userLocation: e.target.value })}
            style={{ minWidth: 260 }}
          />
        </Row>
      </Section>

      {/* ── Execution & Data Source ── */}
      <Section icon="🗄️" title="Execution Mode & Data Source">
        <Row label="Data Source" hint="Catalog provider for product search">
          <select className="select" value={config.dataSource} onChange={e => updateConfig({ dataSource: e.target.value })}>
            <option value="shopify_storefront_live_api">Shopify Storefront API</option>
            <option value="bewakoof_live_api">Bewakoof.com (Live API)</option>
            <option value="google_shopping_scraper">Google Shopping (Scraper)</option>
            <option value="dev_mock">Dev Mock Data</option>
          </select>
        </Row>
        {/* <Row label="Demo Mode" hint="Select checkout flow (Demo 1: Human Present vs Demo 2: Autonomous S2S)">
          <div className="radio-group">
            <button className={`radio-option ${config.demoMode === 'human_present' ? 'selected' : ''}`} onClick={() => updateConfig({ demoMode: 'human_present' })}>
              Demo 1 (Human Present)
            </button>
            <button
              className={`radio-option ${config.demoMode === 'autonomous_s2s' ? 'selected' : ''}`}
              onClick={() => updateConfig({ demoMode: 'autonomous_s2s' })}
            >
              Demo 2 (Autonomous S2S)
            </button>
          </div>
        </Row> */}
      </Section>

      {/* ── Voice & Speech ── */}
      <Section icon="🗣️" title="Voice & Speech Settings">
        <Row label="Voice Mode" hint="Enable Speech-to-Text mic input and auto-play TTS speech">
          <Toggle checked={config.voiceEnabled} onChange={v => updateConfig({ voiceEnabled: v })} />
        </Row>
        <Row label="Stylist Voice" hint="Select preferred synthetic voice">
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <select className="select" style={{ maxWidth: 220 }}
              value={config.voiceURI || ''}
              onChange={e => updateConfig({ voiceURI: e.target.value })}
            >
              <option value="">System Default</option>
              {voices.map(v => (
                <option key={v.voiceURI} value={v.voiceURI}>
                  {v.name} ({v.lang})
                </option>
              ))}
            </select>
            <button className="btn btn-ghost btn-sm" onClick={() => speak('Hello! This is how I sound.', config.voiceURI)}>
              Test Voice
            </button>
          </div>
        </Row>
      </Section>

      {/* ── Search & Enrichment ── */}
      <Section icon="🔍" title="Search & Multi-Tier AI Filtering">
        <Row label="Max Results" hint="Maximum number of products displayed in results">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 200 }}>
            <input type="range" className="range-input" min={5} max={40}
              value={config.maxResults} onChange={e => updateConfig({ maxResults: +e.target.value })} />
            <span className="text-sm text-muted">{config.maxResults} products</span>
          </div>
        </Row>
        <Row label="Deep Product Enrichment" hint="Enriches candidates with live /v2/product/{pid} metadata">
          <Toggle checked={config.enableDeepEnrichment} onChange={v => updateConfig({ enableDeepEnrichment: v })} />
        </Row>
        <Row label="Max Deep Fetches" hint="Maximum API calls per search for deep enrichment">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 200 }}>
            <input type="range" className="range-input" min={1} max={20}
              value={config.maxDeepFetches} onChange={e => updateConfig({ maxDeepFetches: +e.target.value })} />
            <span className="text-sm text-muted">{config.maxDeepFetches} products</span>
          </div>
        </Row>
        <Row
          label="Always Run VQA Scanner"
          hint={config.enableVqaScanner
            ? "ON: Multimodal VQA Vision scans candidates on EVERY query"
            : "OFF (Smart Auto): VQA only runs when visual intent (graphics, print, character) is asked"}
        >
          <Toggle checked={config.enableVqaScanner} onChange={v => updateConfig({ enableVqaScanner: v })} />
        </Row>
        <Row label="VQA Scan Limit" hint="Max products sent to VQA vision — higher = more accurate but slower & costlier">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 200 }}>
            <input type="range" className="range-input" min={1} max={20}
              value={config.vqaLimit ?? 8} onChange={e => updateConfig({ vqaLimit: +e.target.value })} />
            <span className="text-sm text-muted">{config.vqaLimit ?? 8} products scanned by Vision</span>
          </div>
        </Row>
        <Row label="Strict VQA Filtering" hint="Only scan products that pass text constraints first">
          <Toggle checked={config.vqaStrictFilter} onChange={v => updateConfig({ vqaStrictFilter: v })} />
        </Row>
        <Row label="Truth Hierarchy" hint="Prioritize product title over contradicting backend specs">
          <Toggle checked={config.truthHierarchy} onChange={v => updateConfig({ truthHierarchy: v })} />
        </Row>
        <Row label="Semantic Pop-Culture Engine" hint="Expands fandom queries (e.g. 'Panther' → Wakanda, T'Challa)">
          <Toggle checked={config.enableSemanticEngine} onChange={v => updateConfig({ enableSemanticEngine: v })} />
        </Row>
        <Row label="Show AI Match Percentage" hint="Display exact AI model accuracy (e.g. 🧠 95% Match) on product cards vs categorical badge (✦ Best Match)">
          <Toggle checked={config.showMatchPercentage ?? true} onChange={v => updateConfig({ showMatchPercentage: v })} />
        </Row>
        <Row label="Offer Engine" hint="Evaluates cart against merchant discounts & promos">
          <Toggle checked={config.enableOfferEngine} onChange={v => updateConfig({ enableOfferEngine: v })} />
        </Row>
      </Section>

      {/* ── LLM Models ── */}
      <Section icon="🧠" title="LLM Models">
        <Row label="Primary Model" hint="Used for intent normalization & product evaluation">
          <select className="select" value={config.primaryModel} onChange={e => updateConfig({ primaryModel: e.target.value })}>
            <option value="gemini-3.5-flash">Gemini 3.5 Flash (Recommended)</option>
            <option value="gemini-3.1-flash-lite">Gemini 3.1 Flash Lite</option>
            <option value="gemini-flash-latest">Gemini Flash Latest</option>
          </select>
        </Row>
        <Row label="Fallback Model" hint="Used when primary model fails or hits rate limits">
          <select className="select" value={config.fallbackModel} onChange={e => updateConfig({ fallbackModel: e.target.value })}>
            <option value="llama-3.3-70b-versatile">Llama 3.3 70B</option>
            <option value="openai/gpt-oss-20b">OpenAI GPT-OSS 20B</option>
            <option value="qwen/qwen3.6-27b">Qwen 3.6 27B</option>
          </select>
        </Row>
      </Section>

      {/* ── Link to Dedicated Orders & Ledger Page ── */}
      {/* <div style={{ marginTop: 24, padding: '16px 20px', background: 'rgba(59, 130, 246, 0.08)', borderRadius: 10, border: '1px solid rgba(59, 130, 246, 0.25)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: '0.92rem', color: '#e0e7ff', display: 'flex', alignItems: 'center', gap: 6 }}>
            📦 Looking for Shopify Orders or Audit Ledger?
          </div>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: 2 }}>
            Verified Shopify orders with 1-click reordering, safeguard refunds, and the reverse-sorted AP2 audit trail have moved to <strong>Orders & Ledger</strong> in the main navigation.
          </div>
        </div>
      </div> */}
    </div>
  )
}
