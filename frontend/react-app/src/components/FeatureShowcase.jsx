import React from 'react';
const FEATURES = [
  // ── Existing (Live) ──
  {
    icon: '🧠', color: 'purple',
    title: 'AI Stylist Agent',
    desc: 'Multi-turn conversational shopping assistant. Gathers gender, occasion, color, fit, design through smart question-coupling.',
    status: 'live',
    protocol: null,
  },
  {
    icon: '🔍', color: 'green',
    title: '5-Tier Progressive Search',
    desc: 'Structured → full-text → union → category-only → full dump fallback. Works across Shopify, Bewakoof, and scraped catalogs.',
    status: 'live',
    protocol: null,
  },
  {
    icon: '👁️', color: 'blue',
    title: 'VQA Vision Scanner',
    desc: 'Local Vision-Language Model scans product images for complex graphic constraints (e.g. "Batman in a heroic pose, NOT just a logo").',
    status: 'live',
    protocol: null,
  },
  {
    icon: '🎨', color: 'amber',
    title: 'Color Theory Engine',
    desc: 'Maps 1–10 skin tone rating to professional seasonal color palettes (Fair → Jewel tones, Warm → Mustard/Terracotta, Deep → Cobalt).',
    status: 'live',
    protocol: null,
  },
  {
    icon: '🎭', color: 'purple',
    title: 'Semantic Pop-Culture Engine',
    desc: 'Fandom Knowledge Graph expands queries: "Panther" → ["wakanda", "t\'challa", "vibranium"]. Matches products that don\'t contain the exact keyword.',
    status: 'live',
    protocol: null,
  },
  {
    icon: '🎁', color: 'green',
    title: 'Offer & Upsell Engine',
    desc: 'Evaluates cart against bulk deals and spend thresholds. Proactively suggests items to unlock rewards like "Buy 3 for ₹999".',
    status: 'live',
    protocol: null,
  },
  {
    icon: '⚖️', color: 'blue',
    title: 'AI Product Comparison',
    desc: 'Select 2–5 products. The LLM generates a structured feature matrix, pros/cons, and stylist recommendation tailored to your needs.',
    status: 'live',
    protocol: null,
  },
  {
    icon: '🛡️', color: 'amber',
    title: 'HITL Financial Guardrails',
    desc: 'Configurable HITL threshold (default ₹800) and hard budget ceiling (₹3,000). Agent pauses or refuses out-of-bounds transactions.',
    status: 'live',
    protocol: 'AP2',
  },
  {
    icon: '📝', color: 'purple',
    title: 'Mandate-Style Checkout (Demo 1)',
    desc: 'AP2-aligned: Intent → priced Cart → Payment Mandate. Human completes one secure payment; Razorpay token saved for future autonomy.',
    status: 'live',
    protocol: 'AP2',
  },
  {
    icon: '🤖', color: 'green',
    title: 'Autonomous S2S (Demo 2)',
    desc: 'Agent executes server-to-server capture using saved mandate token. Rail-agnostic design: same pattern as NPCI UAP once pilot opens.',
    status: 'live',
    protocol: 'UAP',
  },
  {
    icon: '📜', color: 'blue',
    title: 'Append-Only Audit Ledger',
    desc: 'Every money-touching action is logged in JSONL: mandate approvals, order IDs, Razorpay responses, Shopify sync results.',
    status: 'live',
    protocol: 'AP2',
  },
  {
    icon: '🏪', color: 'amber',
    title: 'Multi-Merchant Providers',
    desc: 'UniversalProductMapper + HandleRegistry: onboard new stores by mapping their JSON to canonical schema. Shopify, Bewakoof, Scraper all live.',
    status: 'live',
    protocol: 'ACP',
  },

  // ── Planned / Coming ──
  {
    icon: '🗣️', color: 'purple',
    title: 'Voice-First Input',
    desc: 'Web Speech API + Kokoro ONNX TTS. Dictate complex shopping requirements naturally. Foundation is built — activation pending.',
    status: 'planned',
    protocol: null,
  },
  {
    icon: '👗', color: 'green',
    title: '"Match My Outfit" Engine',
    desc: 'User inputs owned items; agent identifies complementary categories and color contrasts using color theory. (from Future Directions)',
    status: 'planned',
    protocol: null,
  },
  {
    icon: '🧶', color: 'blue',
    title: 'Multi-Item Bundle Coordinator',
    desc: 'Hierarchical query: buy a full outfit in one session. Dynamic budget allocation formula prevents any single item from dominating.',
    status: 'planned',
    protocol: null,
  },
  {
    icon: '✨', color: 'amber',
    title: 'Vibe/Aesthetic Search',
    desc: '"90s retro grunge" → Oversized, Washed, Maroon/Grey. Rule-based Vibe Tagging Mapper translates aesthetics into structured metadata.',
    status: 'planned',
    protocol: null,
  },
  {
    icon: '🔒', color: 'purple',
    title: 'TAP Agent Identity Layer',
    desc: 'Lightweight signed API key + request header on feed/checkout endpoints, gesturing at Visa Trusted Agent Protocol identity verification.',
    status: 'planned',
    protocol: 'TAP',
  },
  {
    icon: '📦', color: 'green',
    title: 'ACP-Style Product Feed',
    desc: 'Expose UniversalProductMapper canonical products as a structured /feed endpoint so external AI buyer agents can discover the catalog.',
    status: 'planned',
    protocol: 'ACP',
  },
]

const STATUS_LABELS = {
  live: '● Live',
  new: '✦ New',
  planned: '◌ Planned',
}

const PROTOCOL_LABELS = { AP2: 'AP2', UAP: 'UAP', ACP: 'ACP', TAP: 'TAP' }

export default function FeatureShowcase() {
  return (
    <div>
      <div className="hero-banner" style={{ marginBottom: 32 }}>
        <h1>What Rasor Has Built</h1>
        <p>
          A full-stack agentic commerce platform covering discovery, persuasion, guardrail-protected payment, and an append-only audit trail — aligned with AP2, UAP, ACP, and TAP protocols.
        </p>
        <div className="protocol-badges">
          <span className="protocol-badge ap2">AP2 — Agent Payments Protocol</span>
          <span className="protocol-badge uap">UAP — Unified AutoPay (NPCI)</span>
          <span className="protocol-badge acp">ACP — Agentic Commerce Protocol</span>
          <span className="protocol-badge tap">TAP — Trusted Agent Protocol</span>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 10, marginBottom: 24, flexWrap: 'wrap' }}>
        <span className="feature-status live">● 12 Live Features</span>
        <span className="feature-status planned">◌ 6 Planned Features</span>
      </div>

      <div className="feature-grid">
        {FEATURES.map((f, i) => (
          <div key={i} className="feature-card animate-slide-up" style={{ animationDelay: `${i * 30}ms` }}>
            <div className="flex items-center justify-between">
              <div className={`feature-icon ${f.color}`}>{f.icon}</div>
              <div style={{ display: 'flex', gap: 6 }}>
                {f.protocol && (
                  <span className={`protocol-badge ${f.protocol.toLowerCase()}`} style={{ fontSize: '0.65rem' }}>{f.protocol}</span>
                )}
                <span className={`feature-status ${f.status}`}>{STATUS_LABELS[f.status]}</span>
              </div>
            </div>
            <div className="feature-title">{f.title}</div>
            <div className="feature-desc">{f.desc}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
