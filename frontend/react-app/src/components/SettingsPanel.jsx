import React from 'react';
import { useState, useEffect } from 'react'
import { RefreshCw, Trash2 } from 'lucide-react'
import { getOrders, getLedger, clearLedger } from '../api/client'
import { useApp } from '../context/AppContext'
import { useVoice } from '../hooks/useVoice'
import toast from 'react-hot-toast'

// ── Toggle Component ──────────────────────────────────────────
function Toggle({ checked, onChange }) {
  return (
    <label className="toggle">
      <input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} />
      <div className="toggle-track" />
    </label>
  )
}

// ── Settings Row ──────────────────────────────────────────────
function Row({ label, hint, children }) {
  return (
    <div className="settings-row">
      <div className="settings-label">
        <strong>{label}</strong>
        {hint && <span>{hint}</span>}
      </div>
      <div>{children}</div>
    </div>
  )
}

// ── Section ───────────────────────────────────────────────────
function Section({ icon, title, children }) {
  return (
    <div className="settings-section">
      <div className="settings-section-header">{icon} {title}</div>
      <div className="settings-section-body">{children}</div>
    </div>
  )
}

export default function SettingsPanel() {
  const { config, updateConfig } = useApp()
  const { voices, speak } = useVoice()
  const curr = config.currency === 'INR' ? '₹' : '$'

  const [orders, setOrders] = useState([])
  const [loadingOrders, setLoadingOrders] = useState(false)
  const [ledger, setLedger] = useState([])
  const [loadingLedger, setLoadingLedger] = useState(false)

  const fetchOrders = async () => {
    setLoadingOrders(true)
    try {
      const { data } = await getOrders(5)
      setOrders(data.orders || [])
    } catch { toast.error('Failed to fetch orders') }
    finally { setLoadingOrders(false) }
  }

  const fetchLedger = async () => {
    setLoadingLedger(true)
    try {
      const { data } = await getLedger()
      setLedger(data.entries || [])
    } catch { toast.error('Failed to fetch ledger') }
    finally { setLoadingLedger(false) }
  }

  const handleClearLedger = async () => {
    await clearLedger().catch(() => toast.error('Failed to clear ledger'))
    setLedger([])
    toast.success('Ledger cleared')
  }

  useEffect(() => { fetchOrders(); fetchLedger() }, [])

  return (
    <div className="settings-panel">
      <div className="page-title">⚙️ Settings</div>
      <p className="page-subtitle">Configure the agent, guardrails, and data sources</p>

      {/* ── Customer ── */}
      <Section icon="👤" title="Customer Details">
        <Row label="Shopify Account Email" hint="Orders will appear under this account">
          <input
            className="input"
            value={config.customerEmail}
            onChange={e => updateConfig({ customerEmail: e.target.value })}
            style={{ minWidth: 260 }}
          />
        </Row>
        <Row label="User Location" hint="Used for delivery time estimates">
          <select className="select" value={config.userLocation} onChange={e => updateConfig({ userLocation: e.target.value })}>
            {['Not Set', 'Mumbai', 'Delhi', 'Bengaluru', 'New York', 'London'].map(l => <option key={l}>{l}</option>)}
          </select>
        </Row>
      </Section>

      {/* ── Data Source ── */}
      <Section icon="🗄️" title="Execution & Data Source">
        <Row label="Data Source" hint="Where products are fetched from">
          <select className="select" value={config.dataSource} onChange={e => updateConfig({ dataSource: e.target.value })}>
            <option value="shopify_storefront_live_api">Shopify Storefront API</option>
            <option value="bewakoof_live_api">Bewakoof.com (Live API)</option>
            <option value="google_shopping_scraper">Google Shopping (Scraper)</option>
            <option value="dev_mock">Dev Mock Data</option>
          </select>
        </Row>
        <Row label="Demo Mode" hint="AP2 human-present vs autonomous S2S">
          <div className="radio-group">
            <button className={`radio-option ${config.demoMode === 'human_present' ? 'selected' : ''}`} onClick={() => updateConfig({ demoMode: 'human_present' })}>
              Demo 1
            </button>
            <button className={`radio-option ${config.demoMode === 'autonomous_s2s' ? 'selected' : ''}`} onClick={() => updateConfig({ demoMode: 'autonomous_s2s' })}>
              Demo 2
            </button>
          </div>
        </Row>
      </Section>

      {/* ── Guardrails ── */}
      <Section icon="🛡️" title="Financial Guardrails">
        <Row label={`HITL Threshold (${curr})`} hint="Pause & require human approval above this amount">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 200 }}>
            <input type="range" className="range-input" min={100} max={5000} step={50}
              value={config.maxCostHitl} onChange={e => updateConfig({ maxCostHitl: +e.target.value })} />
            <span className="text-sm text-muted">{curr}{config.maxCostHitl.toLocaleString()}</span>
          </div>
        </Row>
        <Row label={`Hard Budget (${curr})`} hint="Strictly refuse any order above this total">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 200 }}>
            <input type="range" className="range-input" min={config.maxCostHitl} max={20000} step={100}
              value={config.maxBudget} onChange={e => updateConfig({ maxBudget: +e.target.value })} />
            <span className="text-sm text-muted">{curr}{config.maxBudget.toLocaleString()}</span>
          </div>
        </Row>
      </Section>

      {/* ── Voice & Speech ── */}
      <Section icon="🗣️" title="Voice & Speech">
        <Row label="Voice Mode" hint="Enable Speech-to-Text mic and auto-play TTS">
          <Toggle checked={config.voiceEnabled} onChange={v => updateConfig({ voiceEnabled: v })} />
        </Row>
        <Row label="Stylist Voice" hint="Select the voice for the AI Stylist">
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
      <Section icon="🔍" title="Search & Enrichment">
        <Row label="Max Results" hint="Products shown in carousel">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 200 }}>
            <input type="range" className="range-input" min={5} max={40}
              value={config.maxResults} onChange={e => updateConfig({ maxResults: +e.target.value })} />
            <span className="text-sm text-muted">{config.maxResults} products</span>
          </div>
        </Row>
        <Row label="Deep Product Enrichment" hint="Fetches single-product API for richer details">
          <Toggle checked={config.enableDeepEnrichment} onChange={v => updateConfig({ enableDeepEnrichment: v })} />
        </Row>
        <Row label="Max Deep Fetches" hint="API calls per search for enrichment">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 200 }}>
            <input type="range" className="range-input" min={1} max={20}
              value={config.maxDeepFetches} onChange={e => updateConfig({ maxDeepFetches: +e.target.value })} />
            <span className="text-sm text-muted">{config.maxDeepFetches} products</span>
          </div>
        </Row>
        <Row label="VQA Vision Scanner" hint="Uses AI vision to verify complex graphic descriptions">
          <Toggle checked={config.enableVqaScanner} onChange={v => updateConfig({ enableVqaScanner: v })} />
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
        <Row label="Offer Engine" hint="Evaluates cart against merchant promotions">
          <Toggle checked={config.enableOfferEngine} onChange={v => updateConfig({ enableOfferEngine: v })} />
        </Row>
      </Section>

      {/* ── LLM ── */}
      <Section icon="🧠" title="LLM Models">
        <Row label="Primary Model" hint="Used for intent normalization & product evaluation">
          <select className="select" value={config.primaryModel} onChange={e => updateConfig({ primaryModel: e.target.value })}>
            <option value="gemini-2.5-flash">Gemini 2.5 Flash</option>
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

      {/* ── Order History ── */}
      <Section icon="🛍️" title="Shopify Order History">
        <div className="flex justify-between items-center">
          <span className="text-sm text-muted">{orders.length} recent orders</span>
          <button className="btn btn-ghost btn-sm" onClick={fetchOrders} disabled={loadingOrders}>
            {loadingOrders ? <span className="spinner" /> : <><RefreshCw size={14} /> Refresh</>}
          </button>
        </div>
        {orders.length > 0 ? orders.map((o, i) => (
          <div key={i} className="order-card">
            <div className="flex justify-between items-center">
              <strong style={{ fontSize: '0.875rem' }}>{o.name || `Order #${i+1}`}</strong>
              <span className={`order-status ${o.financial_status === 'paid' ? 'paid' : 'pending'}`}>
                {o.financial_status || 'unknown'}
              </span>
            </div>
            <span className="text-xs text-muted">{o.created_at} · {o.total_price} {o.currency}</span>
            {o.line_items?.map((li, j) => (
              <div key={j} className="text-xs text-muted">– {li.quantity}× {li.title}</div>
            ))}
          </div>
        )) : <div className="text-sm text-muted">No orders found.</div>}
      </Section>

      {/* ── Audit Ledger ── */}
      <Section icon="📜" title="Audit Ledger (Track 01)">
        <div className="flex justify-between items-center">
          <span className="text-sm text-muted">{ledger.length} events logged</span>
          <div className="flex gap-2">
            <button className="btn btn-ghost btn-sm" onClick={fetchLedger} disabled={loadingLedger}>
              {loadingLedger ? <span className="spinner" /> : <><RefreshCw size={14} /> Refresh</>}
            </button>
            {ledger.length > 0 && (
              <button className="btn btn-danger btn-sm" onClick={handleClearLedger}>
                <Trash2 size={14} /> Clear
              </button>
            )}
          </div>
        </div>
        {ledger.length > 0 ? [...ledger].reverse().map((e, i) => (
          <div key={i} className="ledger-entry">
            <div className="ledger-event-type">{e.event_type}</div>
            <div className="ledger-timestamp">{e.timestamp}</div>
            <pre className="ledger-details">{JSON.stringify(e.details, null, 2)}</pre>
          </div>
        )) : <div className="text-sm text-muted">Ledger is empty.</div>}
      </Section>
    </div>
  )
}
