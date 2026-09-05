import React, { useState, useEffect } from 'react'
import { 
  Sparkles, ShoppingBag, Zap, Check, ArrowRight, RefreshCw, 
  Maximize2, X, ChevronDown, ChevronUp, ChevronLeft, ChevronRight, Tag, Info, AlertTriangle, 
  Sliders, Eye, Plus, CheckCircle2, ShieldCheck, RotateCcw
} from 'lucide-react'
import { useApp } from '../context/AppContext'
import toast from 'react-hot-toast'

export function getProductImageUrl(item, fallbackType = 'top') {
  if (!item) {
    return fallbackType === 'top'
      ? 'https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=800&q=80'
      : 'https://images.unsplash.com/photo-1542272604-780c96856592?auto=format&fit=crop&w=800&q=80'
  }

  const candidates = [
    item.image_url,
    item.images?.[0],
    item.specs?.image_url,
    item.specs?.display_image,
    item.specs?.images?.[0],
    item.thumb,
    item.image,
    item.source_url
  ]

  for (const c of candidates) {
    if (c && typeof c === 'string' && (c.startsWith('http') || c.startsWith('data:') || c.startsWith('/'))) {
      return c
    }
  }

  const cat = (item.category || item.specs?.subclass || item.title || '').toLowerCase()
  if (cat.includes('hoodie') || cat.includes('sweatshirt')) {
    return 'https://images.unsplash.com/photo-1556905055-8f358a7a47b2?auto=format&fit=crop&w=800&q=80'
  }
  if (cat.includes('jogger') || cat.includes('sweatpant') || cat.includes('cargo')) {
    return 'https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?auto=format&fit=crop&w=800&q=80'
  }
  if (cat.includes('jean') || cat.includes('denim')) {
    return 'https://images.unsplash.com/photo-1542272604-780c96856592?auto=format&fit=crop&w=800&q=80'
  }
  if (cat.includes('jacket')) {
    return 'https://images.unsplash.com/photo-1551028719-00167b16eac5?auto=format&fit=crop&w=800&q=80'
  }
  if (cat.includes('shoe') || cat.includes('sneaker') || cat.includes('slider') || cat.includes('footwear')) {
    return 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=800&q=80'
  }
  if (cat.includes('t-shirt') || cat.includes('tee') || cat.includes('shirt') || fallbackType === 'top') {
    return 'https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=800&q=80'
  }
  return 'https://images.unsplash.com/photo-1542272604-780c96856592?auto=format&fit=crop&w=800&q=80'
}

export default function InteractiveOutfitSuite({
  bundleData,
  mode = 'bundle',
  ownedItem = null,
  onAddToCart,
  onAutonomousCheckout,
  onFollowUp,
  onSelectAlternative,
  isStageModal = false
}) {
  const { addToCartLocal } = useApp()

  // ---------------------------------------------------------------------------
  // Low Budget Fallback State ($P_min)
  // ---------------------------------------------------------------------------
  if (mode === 'budget_too_low' || bundleData?.status === 'budget_too_low') {
    const altData = bundleData?.alternatives
    return (
      <div className={`interactive-suite-container low-budget-card animate-fade ${isStageModal ? 'stage-modal-mode' : ''}`}>
        <div className="suite-header-bar">
          <div className="suite-badge-pill warning">
            <AlertTriangle size={15} />
            <span>Budget Constraint Guidance</span>
          </div>
          <span className="suite-budget-req">
            Store Minimum: ₹{bundleData?.min_total_required || altData?.min_total || '998'}
          </span>
        </div>

        <p className="budget-alert-desc">
          Coordinating these requested categories strictly within <strong>₹{bundleData?.budget}</strong> falls below available inventory costs.
        </p>

        {altData?.options && (
          <div className="budget-alt-tray">
            <span className="budget-alt-heading">
              💡 Suggested Stylist Adjustments:
            </span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 10 }}>
              {altData.options.map((opt, idx) => {
                const cleanOpt = String(opt || '').replace(/categoryenum\./gi, '')
                return (
                  <button
                    key={idx}
                    type="button"
                    className="budget-option-pill"
                    onClick={() => {
                      if (onSelectAlternative) {
                        onSelectAlternative(cleanOpt, idx)
                      } else if (onFollowUp) {
                        onFollowUp(cleanOpt)
                      }
                    }}
                  >
                    <ArrowRight size={14} style={{ color: 'var(--accent-amber)', flexShrink: 0 }} />
                    <span>{cleanOpt}</span>
                  </button>
                )
              })}
            </div>
          </div>
        )}
      </div>
    )
  }

  // ---------------------------------------------------------------------------
  // Match My Outfit Mode (Item A Constant Anchor)
  // ---------------------------------------------------------------------------
  if (mode === 'match_my_outfit' || bundleData?.mode === 'match_my_outfit') {
    return <MatchMyOutfitView 
      bundleData={bundleData} 
      ownedItem={ownedItem} 
      onAddToCart={onAddToCart}
      onAutonomousCheckout={onAutonomousCheckout}
      onFollowUp={onFollowUp}
      isStageModal={isStageModal}
    />
  }

  // ---------------------------------------------------------------------------
  // Multi-Item Bundle Mode (Both Non-Constant with Combos & Swapping)
  // ---------------------------------------------------------------------------
  return <MultiBundleCoordinatorView 
    bundleData={bundleData}
    onAddToCart={onAddToCart}
    onAutonomousCheckout={onAutonomousCheckout}
    onFollowUp={onFollowUp}
    isStageModal={isStageModal}
  />
}

// =============================================================================
// SUB-VIEW 1: Multi-Item Bundle Coordinator (Combos, Swapping, Size, Inspection)
// =============================================================================
function MultiBundleCoordinatorView({ bundleData, onAddToCart, onAutonomousCheckout, onFollowUp, isStageModal = false }) {
  const { addToCartLocal } = useApp()

  // Build combos array from server or fallbacks
  const combos = React.useMemo(() => {
    if (bundleData?.combos && bundleData.combos.length > 0) {
      return bundleData.combos
    }
    const list = []
    if (bundleData?.hero_bundle) {
      list.push({
        id: 'combo-1',
        name: 'Combo 1: Hero Coordinated',
        badge: 'Top Stylist Match',
        tagline: 'Optimal Aesthetic Harmony',
        bundle: bundleData.hero_bundle
      })
    }
    if (bundleData?.alternative_bundle && bundleData.alternative_bundle !== bundleData.hero_bundle) {
      list.push({
        id: 'combo-2',
        name: 'Combo 2: High Contrast',
        badge: 'Streetwear Alternative',
        tagline: 'Distinct Silhouette & Tone',
        bundle: bundleData.alternative_bundle
      })
    }
    if (bundleData?.value_bundle && bundleData.value_bundle !== bundleData.hero_bundle && bundleData.value_bundle !== bundleData.alternative_bundle) {
      list.push({
        id: 'combo-3',
        name: 'Combo 3: Best Value',
        badge: 'Budget Maximizer',
        tagline: `Save ₹${Math.round(bundleData.value_bundle.budget_savings || 0)} under budget`,
        bundle: bundleData.value_bundle
      })
    }
    return list
  }, [bundleData])

  const currentBudget = bundleData?.budget || 0

  // Pre-compiled list of all candidate bundles from server ranking filtered strictly by budget
  const allBundles = React.useMemo(() => {
    let list = []
    if (bundleData?.all_bundles && bundleData.all_bundles.length > 0) {
      list = bundleData.all_bundles
    } else {
      combos.forEach(c => {
        if (c.bundle) list.push(c.bundle)
      })
      if (list.length === 0 && bundleData?.hero_bundle) {
        list = [bundleData.hero_bundle]
      }
    }

    // Strict Budget Gate (D-08): All bundles must satisfy total_price <= budget
    if (currentBudget > 0) {
      const budgetPassing = list.filter(b => {
        const p = (b.items || []).reduce((sum, it) => sum + (it.price || 0), 0)
        return p <= currentBudget
      })
      if (budgetPassing.length > 0) return budgetPassing
    }
    return list
  }, [bundleData, combos, currentBudget])

  // Combo History cache for previous / next combo navigation
  const [comboHistory, setComboHistory] = useState(() => {
    const initial = combos[0]?.bundle || allBundles[0] || bundleData?.hero_bundle || bundleData
    return initial ? [initial] : []
  })
  const [historyIndex, setHistoryIndex] = useState(0)
  const [selectedComboIdx, setSelectedComboIdx] = useState(0)

  const activeBundle = comboHistory[historyIndex] || combos[selectedComboIdx]?.bundle || allBundles[0] || bundleData?.hero_bundle || bundleData

  const initialTop = activeBundle?.items?.[0] || null
  const initialBottom = activeBundle?.items?.[1] || null
  const initialPiece3 = activeBundle?.items?.[2] || null

  // Active items currently in the visual slot (can be customized via swap)
  const [activeTop, setActiveTop] = useState(initialTop)
  const [activeBottom, setActiveBottom] = useState(initialBottom)
  const [activePiece3, setActivePiece3] = useState(initialPiece3)

  // Size selections
  const [topSize, setTopSize] = useState(bundleData?.initialTopSize || 'M')
  const [bottomSize, setBottomSize] = useState(bundleData?.initialBottomSize || '32')

  const isBottomGarment = (item) => {
    if (!item) return true
    const cat = String(item.category || item.title || item.name || '').toLowerCase()
    const upperWords = ['shirt', 't-shirt', 'tshirt', 'tee', 'hoodie', 'jacket', 'overshirt', 'sweatshirt', 'polo', 'vest', 'outerwear', 'top']
    const lowerWords = ['pant', 'pants', 'jogger', 'joggers', 'jean', 'jeans', 'trouser', 'trousers', 'short', 'shorts', 'cargo', 'skirt', 'lower', 'bottom']
    if (lowerWords.some(w => cat.includes(w))) return true
    if (upperWords.some(w => cat.includes(w))) return false
    return true
  }

  const isSecondPieceBottom = isBottomGarment(activeBottom)
  const piece2Sizes = isSecondPieceBottom ? ['28', '30', '32', '34', '36'] : ['S', 'M', 'L', 'XL', '2XL']
  const effectivePiece2Size = (!isSecondPieceBottom && /^\d+$/.test(bottomSize)) ? (topSize || 'L') : bottomSize

  const isThirdPieceBottom = isBottomGarment(activePiece3)
  const piece3Sizes = isThirdPieceBottom ? ['28', '30', '32', '34', '36'] : ['S', 'M', 'L', 'XL', '2XL']
  const [piece3Size, setPiece3Size] = useState(() => {
    if (activePiece3) {
      return isBottomGarment(activePiece3) ? (bundleData?.initialBottomSize || '32') : (bundleData?.initialTopSize || 'L')
    }
    return bundleData?.initialBottomSize || '32'
  })
  const effectivePiece3Size = (!isThirdPieceBottom && /^\d+$/.test(piece3Size)) ? (topSize || 'L') : piece3Size

  // Swapping shelf drawers ('top' | 'bottom' | null)
  const [openShelf, setOpenShelf] = useState(null)

  // Expand/collapse states for pieces
  const [topPieceExpanded, setTopPieceExpanded] = useState(true)
  const [bottomPieceExpanded, setBottomPieceExpanded] = useState(true)
  const [piece3Expanded, setPiece3Expanded] = useState(true)

  // Lightbox inspection modal
  const [inspectItem, setInspectItem] = useState(null)

  // Success animation states
  const [addedComplete, setAddedComplete] = useState(false)
  const [addedPieceKey, setAddedPieceKey] = useState(null)
  const [showSubScores, setShowSubScores] = useState(false)

  // Re-sync when bundleData changes completely
  useEffect(() => {
    const initBundle = combos[0]?.bundle || allBundles[0] || bundleData?.hero_bundle || bundleData
    if (initBundle?.items?.length >= 2) {
      setComboHistory([initBundle])
      setHistoryIndex(0)
      setActiveTop(initBundle.items[0])
      setActiveBottom(initBundle.items[1])
      setActivePiece3(initBundle.items[2] || null)
      setSelectedComboIdx(0)
      setOpenShelf(null)
    }
    if (bundleData?.initialTopSize) setTopSize(bundleData.initialTopSize)
    if (bundleData?.initialBottomSize) {
      setBottomSize(bundleData.initialBottomSize)
      setPiece3Size(bundleData.initialBottomSize)
    }
  }, [bundleData])

  // Combo tab selection
  const handleSelectComboTab = (idx) => {
    setSelectedComboIdx(idx)
    const targetBundle = combos[idx]?.bundle
    if (targetBundle && targetBundle.items?.length >= 2) {
      const cur = comboHistory[historyIndex]
      const curTopId = cur?.items?.[0]?.id
      const curBottomId = cur?.items?.[1]?.id
      const curPiece3Id = cur?.items?.[2]?.id
      const tgtTopId = targetBundle.items[0]?.id
      const tgtBottomId = targetBundle.items[1]?.id
      const tgtPiece3Id = targetBundle.items[2]?.id

      if (curTopId !== tgtTopId || curBottomId !== tgtBottomId || curPiece3Id !== tgtPiece3Id) {
        const newHist = [...comboHistory.slice(0, historyIndex + 1), targetBundle]
        setComboHistory(newHist)
        setHistoryIndex(newHist.length - 1)
      }
      setActiveTop(targetBundle.items[0])
      setActiveBottom(targetBundle.items[1])
      setActivePiece3(targetBundle.items[2] || null)
      setOpenShelf(null)
    }
  }

  // Auto-Swap Both to Next Best ranking combination strictly respecting budget
  const handleNextBestCombo = () => {
    // 1. If user previously went back, navigate forward in cached history
    if (historyIndex < comboHistory.length - 1) {
      const nextBundle = comboHistory[historyIndex + 1]
      setHistoryIndex(prev => prev + 1)
      if (nextBundle?.items?.length >= 2) {
        setActiveTop(nextBundle.items[0])
        setActiveBottom(nextBundle.items[1])
        setActivePiece3(nextBundle.items[2] || null)
      }
      toast.success(`⚡ Restored Next Cached Combo (#${historyIndex + 2})`, { icon: '🔄' })
      return
    }

    // 2. Look for next unused bundle from allBundles that is within budget
    const visitedSignatures = new Set(
      comboHistory.map(b => (b.items || []).map(it => it?.id || '').join('__'))
    )

    let nextCandidate = null
    for (const b of allBundles) {
      const bPrice = (b.items || []).reduce((sum, it) => sum + (it.price || 0), 0)
      if (currentBudget > 0 && bPrice > currentBudget) continue // Strict Budget Gate
      const sig = (b.items || []).map(it => it?.id || '').join('__')
      if (!visitedSignatures.has(sig)) {
        nextCandidate = b
        break
      }
    }

    // 3. If all pre-compiled bundles in allBundles are visited, permute shelves under budget
    const topShelves = bundleData?.shelves?.tops || []
    const bottomShelves = bundleData?.shelves?.bottoms || []

    if (!nextCandidate && topShelves.length > 0 && bottomShelves.length > 0) {
      for (const t of topShelves) {
        for (const b of bottomShelves) {
          if (t.id !== b.id) {
            const pairPrice = (t.price || 0) + (b.price || 0)
            if (currentBudget > 0 && pairPrice > currentBudget) continue // Strict Budget Gate: skip over-budget pair

            const sig = `${t.id}__${b.id}`
            if (!visitedSignatures.has(sig)) {
              nextCandidate = {
                items: [t, b],
                total_price: pairPrice,
                budget_savings: Math.max(0, currentBudget - pairPrice),
                style_score: 0.86,
                pairing_type: 'curated_mix',
                sub_scores: activeBundle?.sub_scores || {},
                rationale: `Harmonious aesthetic pairing of ${t.title} and ${b.title}.`
              }
              break
            }
          }
        }
        if (nextCandidate) break
      }
    }

    // 4. Wrap around gracefully if all budget-compliant combos have been shown
    if (!nextCandidate) {
      const firstValid = allBundles.find(b => {
        const p = (b.items || []).reduce((sum, it) => sum + (it.price || 0), 0)
        return currentBudget === 0 || p <= currentBudget
      }) || allBundles[0] || activeBundle

      nextCandidate = firstValid
      toast(`Explored all combos within ₹${currentBudget || 'budget'} — restarted from Top Stylist Pick`, { icon: '🔁' })
    }

    if (nextCandidate && nextCandidate.items?.length >= 2) {
      const newHist = [...comboHistory, nextCandidate]
      setComboHistory(newHist)
      setHistoryIndex(newHist.length - 1)
      setActiveTop(nextCandidate.items[0])
      setActiveBottom(nextCandidate.items[1])
      setActivePiece3(nextCandidate.items[2] || null)
      setOpenShelf(null)
      const p = (nextCandidate.items || []).reduce((sum, it) => sum + (it.price || 0), 0)
      toast.success(`⚡ Auto-Swapped to Next Best Combo (#${newHist.length}) • ₹${p}`, { icon: '⚡' })
    }
  }

  // Navigate to Previous Combo from memory cache
  const handlePreviousCombo = () => {
    if (historyIndex > 0) {
      const prevBundle = comboHistory[historyIndex - 1]
      setHistoryIndex(prev => prev - 1)
      if (prevBundle?.items?.length >= 2) {
        setActiveTop(prevBundle.items[0])
        setActiveBottom(prevBundle.items[1])
        setActivePiece3(prevBundle.items[2] || null)
      }
      setOpenShelf(null)
      toast(`◀ Returned to Previous Combo (#${historyIndex}) from cache`, { icon: '⏪' })
    }
  }

  if (!activeTop || !activeBottom) {
    if (bundleData?.status === 'insufficient_categories' || bundleData?.status === 'no_products_found') {
      return (
        <div className={`interactive-suite-container animate-fade ${isStageModal ? 'stage-modal-mode' : ''}`} style={{ padding: '16px 20px', background: 'rgba(30, 41, 59, 0.6)', borderRadius: 'var(--radius-md)', border: '1px solid rgba(255,255,255,0.08)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--accent-purple)', fontWeight: 600 }}>
            <Sparkles size={16} />
            <span>Multi-Piece Coordination Guidance</span>
          </div>
          <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', marginTop: 8, lineHeight: 1.5 }}>
            To assemble coordinated combinations, please specify target pieces and budget (e.g. <em>"2 shirts under 2000"</em>, <em>"2 uppers and 1 lower under 3k"</em>, or <em>"hoodie and joggers"</em>).
          </p>
        </div>
      )
    }
    return null
  }

  // Dynamic calculations
  const currentPrice = (activeTop?.price || 0) + (activeBottom?.price || 0) + (activePiece3?.price || 0)
  const currentSavings = currentBudget > currentPrice ? Math.round(currentBudget - currentPrice) : 0
  const isOverBudget = currentBudget > 0 && currentPrice > currentBudget
  const styleScorePercent = Math.round((activeBundle?.style_score || 0.88) * 100)

  // Top and bottom candidate shelves for swapping
  const topShelves = bundleData?.shelves?.tops || []
  const bottomShelves = bundleData?.shelves?.bottoms || []

  // Add complete outfit to cart
  const handleAddCompleteOutfit = () => {
    const topItemWithMeta = { ...activeTop, selectedSize: topSize }
    const bottomItemWithMeta = { ...activeBottom, selectedSize: effectivePiece2Size }
    const piece3ItemWithMeta = activePiece3 ? { ...activePiece3, selectedSize: effectivePiece3Size } : null

    if (onAddToCart) {
      onAddToCart(topItemWithMeta)
      onAddToCart(bottomItemWithMeta)
      if (piece3ItemWithMeta) onAddToCart(piece3ItemWithMeta)
    } else {
      addToCartLocal(topItemWithMeta, 1)
      addToCartLocal(bottomItemWithMeta, 1)
      if (piece3ItemWithMeta) addToCartLocal(piece3ItemWithMeta, 1)
    }
    setAddedComplete(true)
    toast.success(`🎉 Added Complete Outfit (${activePiece3 ? '3 Pieces' : '2 Pieces'}) to Cart! • Total: ₹${currentPrice}`)
    setTimeout(() => setAddedComplete(false), 2400)
  }

  // Add individual piece
  const handleAddPiece = (piece, size, key) => {
    const itemWithMeta = { ...piece, selectedSize: size }
    if (onAddToCart) {
      onAddToCart(itemWithMeta)
    } else {
      addToCartLocal(itemWithMeta, 1)
    }
    setAddedPieceKey(key)
    toast.success(`Added ${piece.title} (Size: ${size}) to Cart!`)
    setTimeout(() => setAddedPieceKey(null), 2000)
  }

  // 1-Click Fast Buy
  const handleAutonomousBuy = () => {
    const topItemWithMeta = { ...activeTop, selectedSize: topSize }
    const bottomItemWithMeta = { ...activeBottom, selectedSize: effectivePiece2Size }
    addToCartLocal(topItemWithMeta, 1)
    addToCartLocal(bottomItemWithMeta, 1)
    if (activePiece3) {
      addToCartLocal({ ...activePiece3, selectedSize: effectivePiece3Size }, 1)
    }
    if (onAutonomousCheckout) {
      onAutonomousCheckout({ mode: 'cascade_failover', autoStart: true })
    } else {
      toast.success('Initiating 1-Click Autonomous Checkout...')
    }
  }

  return (
    <div className={`interactive-suite-container animate-fade ${isStageModal ? 'stage-modal-mode' : ''}`}>
      {/* ── 1. Suite Header & Combination Selector Tabs ── */}
      <div className="suite-header-bar">
        <div className="suite-badge-pill hero">
          <Sparkles size={15} />
          <span>AI Stylist Coordinated Looks</span>
        </div>

        <div className="suite-price-savings-cluster">
          {currentBudget > 0 && (
            <span className={`suite-budget-status-pill ${isOverBudget ? 'over' : 'under'}`}>
              {isOverBudget ? (
                `⚠ Over Budget (+₹${currentPrice - currentBudget})`
              ) : (
                `✓ ₹${currentSavings} under ₹${currentBudget} cap`
              )}
            </span>
          )}
          {currentSavings > 0 && !isOverBudget && (
            <span className="suite-savings-tag">
              Save ₹{currentSavings}
            </span>
          )}
          <div className="suite-cohesion-meter">
            <span className="meter-val">{styleScorePercent}%</span>
            <span className="meter-lbl">Harmony</span>
          </div>
        </div>
      </div>

      {/* Combination Tabs (Horizontal Pills) & Auto-Swap Controls */}
      <div className="suite-combos-tabs-bar">
        {combos.length > 1 && (
          <div className="suite-combos-tabs-row horizontal-pills">
            {combos.map((combo, idx) => {
              const comboScore = combo.bundle?.style_score ? Math.round(combo.bundle.style_score * 100) : null
              const comboPrice = (combo.bundle?.items || []).reduce((sum, it) => sum + (it.price || 0), 0)
              const isComboOver = currentBudget > 0 && comboPrice > currentBudget

              return (
                <button
                  key={combo.id || idx}
                  type="button"
                  className={`suite-combo-pill-btn ${selectedComboIdx === idx ? 'active' : ''} ${isComboOver ? 'over-budget' : ''}`}
                  onClick={() => handleSelectComboTab(idx)}
                  title={`${combo.name}: ${combo.tagline || combo.badge} (₹${comboPrice})`}
                >
                  <span className="combo-pill-num">#{idx + 1}</span>
                  <span className="combo-pill-name">{combo.name?.replace(/^Combo \d+:\s*/, '') || `Look ${idx + 1}`}</span>
                  {comboPrice > 0 && <span className="combo-pill-price">₹{comboPrice}</span>}
                  {comboScore && <span className="combo-pill-score">{comboScore}%</span>}
                </button>
              )
            })}
          </div>
        )}

        {/* Auto-Swap Both & Prev/Next Combo Controls */}
        <div className="suite-combo-nav-actions">
          <button 
            type="button" 
            className="combo-nav-btn prev"
            disabled={historyIndex <= 0}
            onClick={handlePreviousCombo}
            title={historyIndex > 0 ? `Return to previous combo (#${historyIndex}) from cache` : "No previous combo in history"}
          >
            <ChevronLeft size={14} />
            <span>Prev Combo</span>
          </button>
          
          <button 
            type="button" 
            className="combo-nav-btn next-best"
            onClick={handleNextBestCombo}
            title="Auto-swap both pieces to next best aesthetic combination"
          >
            <Zap size={14} style={{ color: '#fbbf24' }} />
            <span>Next Best Combo</span>
            <ChevronRight size={14} />
          </button>
        </div>
      </div>

      {/* ── 2. Side-by-Side Coordinated Pieces Display with Expand/Collapse ── */}
      <div className="suite-pieces-header-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: '12px 0 6px 0', padding: '0 2px' }}>
        <span style={{ fontSize: '0.74rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          Coordinated Pieces {(!topPieceExpanded || !bottomPieceExpanded) ? '• Compact View' : '• Expanded'}
        </span>
        <button
          type="button"
          className="btn-toggle-pieces-view"
          onClick={() => {
            const nextState = !(topPieceExpanded && bottomPieceExpanded && (!activePiece3 || piece3Expanded))
            setTopPieceExpanded(nextState)
            setBottomPieceExpanded(nextState)
            if (activePiece3) setPiece3Expanded(nextState)
          }}
          style={{
            background: 'rgba(255,255,255,0.04)',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 99,
            padding: '3px 10px',
            fontSize: '0.72rem',
            fontWeight: 600,
            color: '#a5b4fc',
            cursor: 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 5
          }}
        >
          {topPieceExpanded && bottomPieceExpanded && (!activePiece3 || piece3Expanded) ? (
            <>
              <ChevronUp size={13} />
              <span>Collapse Items</span>
            </>
          ) : (
            <>
              <ChevronDown size={13} />
              <span>Expand Items</span>
            </>
          )}
        </button>
      </div>

      <div className={`suite-pieces-split-layout ${activePiece3 ? 'three-pieces' : ''}`}>
        {/* Piece #1: Upper (Collapsible) */}
        {!topPieceExpanded ? (
          <div 
            className="suite-piece-card top-card collapsed animate-fade" 
            onClick={() => setTopPieceExpanded(true)}
            title="Click to expand upper garment"
          >
            <div className="piece-collapsed-row">
              <img 
                src={getProductImageUrl(activeTop, 'top')} 
                alt={activeTop.title || 'Upper'} 
                className="piece-collapsed-thumb" 
                onError={(e) => {
                  e.target.onerror = null
                  e.target.src = 'https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=800&q=80'
                }}
              />
              <div className="piece-collapsed-meta">
                <span className="piece-type-badge top" style={{ fontSize: '0.66rem', padding: '1px 6px', width: 'fit-content' }}>
                  {activeTop.category ? `Piece #1 • ${activeTop.category.toUpperCase()}` : 'Piece #1 • Upper'}
                </span>
                <strong className="piece-collapsed-title" title={activeTop.title}>{activeTop.title || activeTop.name}</strong>
                <div className="piece-collapsed-sub">
                  <span className="current-price">₹{activeTop.price}</span>
                  <span className="size-badge-pill">Size: {topSize}</span>
                </div>
              </div>
              <div className="piece-collapsed-actions" onClick={e => e.stopPropagation()}>
                <button
                  type="button"
                  className={`btn-piece-add-mini ${addedPieceKey === 'top' ? 'added' : ''}`}
                  onClick={() => handleAddPiece(activeTop, topSize, 'top')}
                  title={`Add top only (₹${activeTop.price})`}
                >
                  {addedPieceKey === 'top' ? <Check size={13} /> : <Plus size={13} />}
                  <span>₹{activeTop.price}</span>
                </button>
                <button
                  type="button"
                  className="piece-accordion-toggle"
                  onClick={() => setTopPieceExpanded(true)}
                  title="Expand piece details"
                >
                  <ChevronDown size={16} />
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="suite-piece-card top-card animate-fade">
            <div className="piece-card-header">
              <span className="piece-type-badge top">
                {activeTop.category ? `Piece #1 • ${activeTop.category.toUpperCase()}` : 'Piece #1 • Upper'}
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <button 
                  type="button" 
                  className="piece-inspect-btn"
                  onClick={() => setInspectItem(activeTop)}
                  title="Inspect Upper Garment Details"
                >
                  <Eye size={13} />
                  <span>Details</span>
                </button>
                <button
                  type="button"
                  className="piece-accordion-toggle"
                  onClick={() => setTopPieceExpanded(false)}
                  title="Collapse upper garment"
                >
                  <ChevronUp size={15} />
                </button>
              </div>
            </div>

            <div className={`piece-image-wrap ${isStageModal ? 'large-modal-wrap' : ''}`} onClick={() => setInspectItem(activeTop)}>
              <img 
                src={getProductImageUrl(activeTop, 'top')} 
                alt={activeTop.title || activeTop.name || 'Upper Garment'} 
                className="piece-photo" 
                onError={(e) => {
                  e.target.onerror = null
                  e.target.src = 'https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=800&q=80'
                }}
              />
              <div className="image-zoom-overlay">
                <Maximize2 size={16} />
              </div>
            </div>

            <div className="piece-details-body">
              <h4 className="piece-item-title" title={activeTop.title}>
                {activeTop.title || activeTop.name}
              </h4>
              
              <div className="piece-pricing-row">
                <span className="current-price">₹{activeTop.price}</span>
                {activeTop.mrp && Number(activeTop.mrp) > activeTop.price && (
                  <span className="mrp-price">₹{activeTop.mrp}</span>
                )}
                {activeTop.rating && (
                  <span className="rating-pill">★ {activeTop.rating}</span>
                )}
              </div>

              {/* Size Selector */}
              <div className="piece-size-selector-row">
                <span className="size-label">Size:</span>
                <div className="size-pills-wrap">
                  {['S', 'M', 'L', 'XL', '2XL'].map(sz => (
                    <button
                      key={sz}
                      type="button"
                      className={`size-pill ${topSize === sz ? 'selected' : ''}`}
                      onClick={() => setTopSize(sz)}
                    >
                      {sz}
                    </button>
                  ))}
                </div>
              </div>

              {/* Piece Actions */}
              <div className="piece-card-actions">
                <button
                  type="button"
                  className={`btn-piece-add ${addedPieceKey === 'top' ? 'added' : ''}`}
                  onClick={() => handleAddPiece(activeTop, topSize, 'top')}
                >
                  {addedPieceKey === 'top' ? <Check size={14} /> : <Plus size={14} />}
                  <span>{addedPieceKey === 'top' ? 'Added Top' : `Add Top Only (₹${activeTop.price})`}</span>
                </button>

                {topShelves.length > 1 && (
                  <button
                    type="button"
                    className={`btn-piece-swap ${openShelf === 'top' ? 'active' : ''}`}
                    onClick={() => setOpenShelf(openShelf === 'top' ? null : 'top')}
                    title="Browse alternative matching tops"
                  >
                    <RefreshCw size={13} />
                    <span>{openShelf === 'top' ? 'Close Shelf' : 'Swap Upper'}</span>
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Cohesion & Color Science Connector */}
        <div className="suite-center-connector">
          <div className="connector-vertical-line" />
          <div className="connector-harmony-badge">
            <Sparkles size={16} />
            <span className="connector-score">{styleScorePercent}% Match</span>
            <span className="connector-vibe">
              {activeBundle?.pairing_type ? activeBundle.pairing_type.replace('_', ' ') : 'Coordinated'}
            </span>
          </div>
          <div className="connector-vertical-line" />
        </div>

        {/* Piece #2: Garment (Collapsible - Lower or Upper) */}
        {!bottomPieceExpanded ? (
          <div 
            className="suite-piece-card bottom-card collapsed animate-fade" 
            onClick={() => setBottomPieceExpanded(true)}
            title={`Click to expand ${isSecondPieceBottom ? 'lower garment' : 'second piece'}`}
          >
            <div className="piece-collapsed-row">
              <img 
                src={getProductImageUrl(activeBottom, 'bottom')} 
                alt={activeBottom.title || (isSecondPieceBottom ? 'Lower' : 'Piece #2')} 
                className="piece-collapsed-thumb" 
                onError={(e) => {
                  e.target.onerror = null
                  e.target.src = isSecondPieceBottom 
                    ? 'https://images.unsplash.com/photo-1542272604-780c96856592?auto=format&fit=crop&w=800&q=80'
                    : 'https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=800&q=80'
                }}
              />
              <div className="piece-collapsed-meta">
                <span className="piece-type-badge bottom" style={{ fontSize: '0.66rem', padding: '1px 6px', width: 'fit-content' }}>
                  {activeBottom.category ? `Piece #2 • ${activeBottom.category.toUpperCase()}` : (isSecondPieceBottom ? 'Piece #2 • Lower' : 'Piece #2 • Upper')}
                </span>
                <strong className="piece-collapsed-title" title={activeBottom.title}>{activeBottom.title || activeBottom.name}</strong>
                <div className="piece-collapsed-sub">
                  <span className="current-price">₹{activeBottom.price}</span>
                  <span className="size-badge-pill">{isSecondPieceBottom ? 'Waist' : 'Size'}: {effectivePiece2Size}</span>
                </div>
              </div>
              <div className="piece-collapsed-actions" onClick={e => e.stopPropagation()}>
                <button
                  type="button"
                  className={`btn-piece-add-mini ${addedPieceKey === 'bottom' ? 'added' : ''}`}
                  onClick={() => handleAddPiece(activeBottom, effectivePiece2Size, 'bottom')}
                  title={`Add ${isSecondPieceBottom ? 'lower only' : 'piece #2 only'} (₹${activeBottom.price})`}
                >
                  {addedPieceKey === 'bottom' ? <Check size={13} /> : <Plus size={13} />}
                  <span>₹{activeBottom.price}</span>
                </button>
                <button
                  type="button"
                  className="piece-accordion-toggle"
                  onClick={() => setBottomPieceExpanded(true)}
                  title="Expand piece details"
                >
                  <ChevronDown size={16} />
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="suite-piece-card bottom-card animate-fade">
            <div className="piece-card-header">
              <span className="piece-type-badge bottom">
                {activeBottom.category ? `Piece #2 • ${activeBottom.category.toUpperCase()}` : (isSecondPieceBottom ? 'Piece #2 • Lower' : 'Piece #2 • Upper')}
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <button 
                  type="button" 
                  className="piece-inspect-btn"
                  onClick={() => setInspectItem(activeBottom)}
                  title={`Inspect ${activeBottom.category || (isSecondPieceBottom ? 'Lower Garment' : 'Piece #2')} Details`}
                >
                  <Eye size={13} />
                  <span>Details</span>
                </button>
                <button
                  type="button"
                  className="piece-accordion-toggle"
                  onClick={() => setBottomPieceExpanded(false)}
                  title={`Collapse ${isSecondPieceBottom ? 'lower garment' : 'piece #2'}`}
                >
                  <ChevronUp size={15} />
                </button>
              </div>
            </div>

            <div className="piece-image-wrap" onClick={() => setInspectItem(activeBottom)}>
              <img 
                src={getProductImageUrl(activeBottom, 'bottom')} 
                alt={activeBottom.title || activeBottom.name || (isSecondPieceBottom ? 'Lower Garment' : 'Piece #2')} 
                className="piece-photo" 
                onError={(e) => {
                  e.target.onerror = null
                  e.target.src = isSecondPieceBottom 
                    ? 'https://images.unsplash.com/photo-1542272604-780c96856592?auto=format&fit=crop&w=800&q=80'
                    : 'https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=800&q=80'
                }}
              />
              <div className="image-zoom-overlay">
                <Maximize2 size={16} />
              </div>
            </div>

            <div className="piece-details-body">
              <h4 className="piece-item-title" title={activeBottom.title}>
                {activeBottom.title || activeBottom.name}
              </h4>
              
              <div className="piece-pricing-row">
                <span className="current-price">₹{activeBottom.price}</span>
                {activeBottom.mrp && Number(activeBottom.mrp) > activeBottom.price && (
                  <span className="mrp-price">₹{activeBottom.mrp}</span>
                )}
                {activeBottom.rating && (
                  <span className="rating-pill">★ {activeBottom.rating}</span>
                )}
              </div>

              {/* Size Selector */}
              <div className="piece-size-selector-row">
                <span className="size-label">{isSecondPieceBottom ? 'Waist:' : 'Size:'}</span>
                <div className="size-pills-wrap">
                  {piece2Sizes.map(sz => (
                    <button
                      key={sz}
                      type="button"
                      className={`size-pill ${effectivePiece2Size === sz ? 'selected' : ''}`}
                      onClick={() => setBottomSize(sz)}
                    >
                      {sz}
                    </button>
                  ))}
                </div>
              </div>

              {/* Piece Actions */}
              <div className="piece-card-actions">
                <button
                  type="button"
                  className={`btn-piece-add ${addedPieceKey === 'bottom' ? 'added' : ''}`}
                  onClick={() => handleAddPiece(activeBottom, effectivePiece2Size, 'bottom')}
                >
                  {addedPieceKey === 'bottom' ? <Check size={14} /> : <Plus size={14} />}
                  <span>
                    {addedPieceKey === 'bottom' 
                      ? (isSecondPieceBottom ? 'Added Lower' : 'Added Piece #2') 
                      : (isSecondPieceBottom 
                          ? `Add Lower Only (₹${activeBottom.price})` 
                          : (activeBottom.category 
                              ? `Add ${activeBottom.category.charAt(0).toUpperCase() + activeBottom.category.slice(1)} Only (₹${activeBottom.price})` 
                              : `Add Piece #2 Only (₹${activeBottom.price})`))}
                  </span>
                </button>

                {bottomShelves.length > 1 && (
                  <button
                    type="button"
                    className={`btn-piece-swap ${openShelf === 'bottom' ? 'active' : ''}`}
                    onClick={() => setOpenShelf(openShelf === 'bottom' ? null : 'bottom')}
                    title={`Browse alternative matching ${isSecondPieceBottom ? 'bottoms' : 'pieces'}`}
                  >
                    <RefreshCw size={13} />
                    <span>{openShelf === 'bottom' ? 'Close Shelf' : (isSecondPieceBottom ? 'Swap Lower' : 'Swap Garment')}</span>
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Connector 2 (if 3 pieces) */}
        {activePiece3 && (
          <div className="suite-center-connector">
            <div className="connector-vertical-line" />
            <div className="connector-harmony-badge">
              <Sparkles size={16} />
              <span className="connector-score">Ensemble</span>
              <span className="connector-vibe">
                3-Piece Look
              </span>
            </div>
            <div className="connector-vertical-line" />
          </div>
        )}

        {/* Piece #3: Additional Garment (Collapsible) */}
        {activePiece3 && (!piece3Expanded ? (
          <div 
            className="suite-piece-card bottom-card collapsed animate-fade" 
            onClick={() => setPiece3Expanded(true)}
            title={`Click to expand ${isThirdPieceBottom ? 'lower garment' : 'third piece'}`}
          >
            <div className="piece-collapsed-row">
              <img 
                src={getProductImageUrl(activePiece3, isThirdPieceBottom ? 'bottom' : 'top')} 
                alt={activePiece3.title || 'Piece #3'} 
                className="piece-collapsed-thumb" 
                onError={(e) => {
                  e.target.onerror = null
                  e.target.src = isThirdPieceBottom 
                    ? 'https://images.unsplash.com/photo-1542272604-780c96856592?auto=format&fit=crop&w=800&q=80'
                    : 'https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=800&q=80'
                }}
              />
              <div className="piece-collapsed-meta">
                <span className="piece-type-badge bottom" style={{ fontSize: '0.66rem', padding: '1px 6px', width: 'fit-content' }}>
                  {activePiece3.category ? `Piece #3 • ${activePiece3.category.toUpperCase()}` : (isThirdPieceBottom ? 'Piece #3 • Lower' : 'Piece #3 • Upper')}
                </span>
                <strong className="piece-collapsed-title" title={activePiece3.title}>{activePiece3.title || activePiece3.name}</strong>
                <div className="piece-collapsed-sub">
                  <span className="current-price">₹{activePiece3.price}</span>
                  <span className="size-badge-pill">{isThirdPieceBottom ? 'Waist' : 'Size'}: {effectivePiece3Size}</span>
                </div>
              </div>
              <div className="piece-collapsed-actions" onClick={e => e.stopPropagation()}>
                <button
                  type="button"
                  className={`btn-piece-add-mini ${addedPieceKey === 'piece3' ? 'added' : ''}`}
                  onClick={() => handleAddPiece(activePiece3, effectivePiece3Size, 'piece3')}
                  title={`Add piece #3 only (₹${activePiece3.price})`}
                >
                  {addedPieceKey === 'piece3' ? <Check size={13} /> : <Plus size={13} />}
                  <span>₹{activePiece3.price}</span>
                </button>
                <button
                  type="button"
                  className="piece-accordion-toggle"
                  onClick={() => setPiece3Expanded(true)}
                  title="Expand piece details"
                >
                  <ChevronDown size={16} />
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="suite-piece-card bottom-card animate-fade">
            <div className="piece-card-header">
              <span className="piece-type-badge bottom">
                {activePiece3.category ? `Piece #3 • ${activePiece3.category.toUpperCase()}` : (isThirdPieceBottom ? 'Piece #3 • Lower' : 'Piece #3 • Upper')}
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <button 
                  type="button" 
                  className="piece-inspect-btn"
                  onClick={() => setInspectItem(activePiece3)}
                  title="Inspect Piece #3 Details"
                >
                  <Eye size={13} />
                  <span>Details</span>
                </button>
                <button
                  type="button"
                  className="piece-accordion-toggle"
                  onClick={() => setPiece3Expanded(false)}
                  title="Collapse piece #3"
                >
                  <ChevronUp size={15} />
                </button>
              </div>
            </div>

            <div className="piece-image-wrap" onClick={() => setInspectItem(activePiece3)}>
              <img 
                src={getProductImageUrl(activePiece3, isThirdPieceBottom ? 'bottom' : 'top')} 
                alt={activePiece3.title || activePiece3.name || 'Piece #3'} 
                className="piece-photo" 
                onError={(e) => {
                  e.target.onerror = null
                  e.target.src = isThirdPieceBottom 
                    ? 'https://images.unsplash.com/photo-1542272604-780c96856592?auto=format&fit=crop&w=800&q=80'
                    : 'https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=800&q=80'
                }}
              />
              <div className="image-zoom-overlay">
                <Maximize2 size={16} />
              </div>
            </div>

            <div className="piece-details-body">
              <h4 className="piece-item-title" title={activePiece3.title}>
                {activePiece3.title || activePiece3.name}
              </h4>
              
              <div className="piece-pricing-row">
                <span className="current-price">₹{activePiece3.price}</span>
                {activePiece3.mrp && Number(activePiece3.mrp) > activePiece3.price && (
                  <span className="mrp-price">₹{activePiece3.mrp}</span>
                )}
                {activePiece3.rating && (
                  <span className="rating-pill">★ {activePiece3.rating}</span>
                )}
              </div>

              {/* Size Selector */}
              <div className="piece-size-selector-row">
                <span className="size-label">{isThirdPieceBottom ? 'Waist:' : 'Size:'}</span>
                <div className="size-pills-wrap">
                  {piece3Sizes.map(sz => (
                    <button
                      key={sz}
                      type="button"
                      className={`size-pill ${effectivePiece3Size === sz ? 'selected' : ''}`}
                      onClick={() => setPiece3Size(sz)}
                    >
                      {sz}
                    </button>
                  ))}
                </div>
              </div>

              {/* Piece Actions */}
              <div className="piece-card-actions">
                <button
                  type="button"
                  className={`btn-piece-add ${addedPieceKey === 'piece3' ? 'added' : ''}`}
                  onClick={() => handleAddPiece(activePiece3, effectivePiece3Size, 'piece3')}
                >
                  {addedPieceKey === 'piece3' ? <Check size={14} /> : <Plus size={14} />}
                  <span>{addedPieceKey === 'piece3' ? 'Added Piece #3' : `Add Piece #3 Only (₹${activePiece3.price})`}</span>
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* ── 3. Interactive Swapping Tray (Opens inline when user clicks Swap Upper/Lower) ── */}
      {openShelf && (
        <div className="suite-shelf-drawer animate-slide-down">
          <div className="shelf-drawer-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <RefreshCw size={15} style={{ color: 'var(--accent-purple)' }} />
              <strong>
                {openShelf === 'top' 
                  ? 'Select Alternative Upper Garment:' 
                  : (isSecondPieceBottom 
                      ? 'Select Alternative Lower Garment:' 
                      : 'Select Alternative Second Garment:')}
              </strong>
            </div>
            <button 
              type="button" 
              className="shelf-drawer-close"
              onClick={() => setOpenShelf(null)}
            >
              <X size={16} />
            </button>
          </div>

          <div className="shelf-candidates-scroll">
            {(() => {
              const rawCandidates = (openShelf === 'top' ? topShelves : bottomShelves)
              const otherPiece = openShelf === 'top' ? activeBottom : activeTop

              // Sort: within-budget items appear first, then ascending price
              const sorted = [...rawCandidates].sort((a, b) => {
                const totalA = (a.price || 0) + (otherPiece?.price || 0)
                const totalB = (b.price || 0) + (otherPiece?.price || 0)
                const overA = currentBudget > 0 && totalA > currentBudget ? 1 : 0
                const overB = currentBudget > 0 && totalB > currentBudget ? 1 : 0
                if (overA !== overB) return overA - overB
                return (a.price || 0) - (b.price || 0)
              })

              return sorted.map((cand, idx) => {
                const isCurrent = (openShelf === 'top' ? activeTop.id : activeBottom.id) === cand.id
                const otherPrice = (otherPiece?.price || 0)
                const projectedPairTotal = (cand.price || 0) + otherPrice
                const isOverBudgetCandidate = currentBudget > 0 && projectedPairTotal > currentBudget

                return (
                  <div 
                    key={cand.id || idx} 
                    className={`shelf-candidate-card ${isCurrent ? 'current-active' : ''} ${isOverBudgetCandidate ? 'over-budget' : ''}`}
                    onClick={() => {
                      if (openShelf === 'top') {
                        setActiveTop(cand)
                        const customBundle = {
                          items: [cand, activeBottom],
                          total_price: projectedPairTotal,
                          budget_savings: Math.max(0, currentBudget - projectedPairTotal),
                          style_score: Math.max(0.78, (activeBundle?.style_score || 0.86) - 0.02),
                          pairing_type: 'custom_upper_swap',
                          sub_scores: activeBundle?.sub_scores || {},
                          rationale: `Customized styling combination with ${cand.title}.`
                        }
                        const newHist = [...comboHistory.slice(0, historyIndex + 1), customBundle]
                        setComboHistory(newHist)
                        setHistoryIndex(newHist.length - 1)
                        if (isOverBudgetCandidate) {
                          toast(`Swapped upper to ${cand.title} (⚠ Exceeds budget by ₹${projectedPairTotal - currentBudget})`, { icon: '⚠️' })
                        } else {
                          toast.success(`Swapped upper to: ${cand.title}`)
                        }
                      } else {
                        setActiveBottom(cand)
                        const customBundle = {
                          items: [activeTop, cand],
                          total_price: projectedPairTotal,
                          budget_savings: Math.max(0, currentBudget - projectedPairTotal),
                          style_score: Math.max(0.78, (activeBundle?.style_score || 0.86) - 0.02),
                          pairing_type: 'custom_lower_swap',
                          sub_scores: activeBundle?.sub_scores || {},
                          rationale: `Customized styling combination with ${cand.title}.`
                        }
                        const newHist = [...comboHistory.slice(0, historyIndex + 1), customBundle]
                        setComboHistory(newHist)
                        setHistoryIndex(newHist.length - 1)
                        if (isOverBudgetCandidate) {
                          toast(`Swapped lower to ${cand.title} (⚠ Exceeds budget by ₹${projectedPairTotal - currentBudget})`, { icon: '⚠️' })
                        } else {
                          toast.success(`Swapped lower to: ${cand.title}`)
                        }
                      }
                      setOpenShelf(null)
                    }}
                  >
                    <div className="cand-thumb-wrap">
                      <img 
                        src={getProductImageUrl(cand, openShelf === 'top' ? 'top' : 'bottom')} 
                        alt={cand.title} 
                        className="cand-thumb" 
                        onError={(e) => {
                          e.target.onerror = null
                          e.target.src = openShelf === 'top'
                            ? 'https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=800&q=80'
                            : 'https://images.unsplash.com/photo-1542272604-780c96856592?auto=format&fit=crop&w=800&q=80'
                        }}
                      />
                      {isCurrent && <span className="cand-active-tag">In Outfit</span>}
                      {isOverBudgetCandidate && (
                        <span className="cand-over-budget-tag">
                          ⚠ +₹{projectedPairTotal - currentBudget} Over
                        </span>
                      )}
                    </div>
                    <div className="cand-info">
                      <span className="cand-title" title={cand.title}>{cand.title}</span>
                      <div className="cand-price-row">
                        <strong>₹{cand.price}</strong>
                        {cand.rating && <span className="cand-rating">★ {cand.rating}</span>}
                      </div>
                      <span className={`cand-pair-cost-note ${isOverBudgetCandidate ? 'over' : 'under'}`}>
                        Look: ₹{projectedPairTotal} {isOverBudgetCandidate ? `(Exceeds limit)` : `(Within limit)`}
                      </span>
                    </div>
                  </div>
                )
              })
            })()}
          </div>
        </div>
      )}

      {/* ── 4. Stylist Rationale & Color Theory Sub-Scores ── */}
      <div className="suite-rationale-box">
        <div className="rationale-header-row">
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <Sparkles size={14} style={{ color: 'var(--accent-purple)' }} />
            <strong style={{ fontSize: '0.84rem' }}>Stylist Insight:</strong>
          </div>
          {activeBundle?.sub_scores && (
            <button
              type="button"
              className="btn-text-accordion"
              onClick={() => setShowSubScores(v => !v)}
            >
              {showSubScores ? 'Hide Color Science ▲' : 'View Color Science Details ▼'}
            </button>
          )}
        </div>

        <p className="suite-rationale-text">
          {activeBundle?.rationale || "Harmonious tonal balance between upper and lower pieces with zero style collisions."}
        </p>

        {showSubScores && activeBundle?.sub_scores && (
          <div className="suite-subscores-grid animate-fade">
            <div className="subscore-metric">
              <span className="metric-label">Hue Harmony (LCh):</span>
              <span className="metric-value">{Math.round((activeBundle.sub_scores.hue_harmony || 0) * 100)}%</span>
            </div>
            <div className="subscore-metric">
              <span className="metric-label">Value Contrast:</span>
              <span className="metric-value">{Math.round((activeBundle.sub_scores.value_contrast || 0) * 100)}%</span>
            </div>
            <div className="subscore-metric">
              <span className="metric-label">Chroma Affinity:</span>
              <span className="metric-value">{Math.round((activeBundle.sub_scores.chroma_comp || 0) * 100)}%</span>
            </div>
            <div className="subscore-metric">
              <span className="metric-label">Neutral Balance:</span>
              <span className="metric-value">{Math.round((activeBundle.sub_scores.neutral_bonus || 0) * 100)}%</span>
            </div>
          </div>
        )}
      </div>

      {/* ── 5. Main Action Bar (Non-Forceful, Empowering) ── */}
      <div className="suite-footer-action-bar">
        <div className="suite-total-cluster">
          <span className="suite-total-label">Complete Outfit Total:</span>
          <div className="suite-total-numbers">
            <span className="suite-total-val">₹{currentPrice}</span>
            <span className="suite-pieces-count">({activePiece3 ? '3 Pieces Coordinated' : 'Upper + Lower'})</span>
          </div>
        </div>

        <div className="suite-actions-group">
          <button
            type="button"
            className="btn btn-primary btn-lg suite-add-all-btn"
            onClick={handleAddCompleteOutfit}
          >
            {addedComplete ? <CheckCircle2 size={18} /> : <ShoppingBag size={18} />}
            <span>{addedComplete ? 'Outfit in Cart!' : `Add Complete Outfit (₹${currentPrice})`}</span>
          </button>

          <button
            type="button"
            className="btn btn-outline suite-fastbuy-btn"
            onClick={handleAutonomousBuy}
            title="Convenient autonomous 1-click checkout"
          >
            <Zap size={16} />
            <span>1-Click Buy</span>
          </button>
        </div>
      </div>

      {/* ── 6. Conversational Refinement Quick Chips ── */}
      <div className="suite-refinement-chips-bar">
        <span className="refine-hint">💬 Ask Stylist to Tweak:</span>
        <div className="refine-chips-list">
          {[
            "🔄 Swap Lower with Joggers",
            "🎨 Show higher contrast styles",
            "💰 Keep total under ₹2000",
            "👕 Try oversized hoodie instead"
          ].map((chipPrompt, idx) => (
            <button
              key={idx}
              type="button"
              className="suite-refine-chip"
              onClick={() => onFollowUp && onFollowUp(chipPrompt)}
            >
              <span>{chipPrompt}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Lightbox Modal */}
      {inspectItem && (
        <ProductInspectionModal item={inspectItem} onClose={() => setInspectItem(null)} />
      )}
    </div>
  )
}

// =============================================================================
// SUB-VIEW 2: Match My Outfit Mode (Owned Anchor + Catalog Match)
// =============================================================================
function MatchMyOutfitView({ bundleData, ownedItem, onAddToCart, onAutonomousCheckout, onFollowUp, isStageModal = false }) {
  const { addToCartLocal } = useApp()
  const constant = ownedItem || bundleData?.constant_item
  const matchedResults = bundleData?.matched_results || []
  const [selectedMatchIdx, setSelectedMatchIdx] = useState(0)

  const activeMatch = matchedResults[selectedMatchIdx] || bundleData?.top_recommendation
  const product = activeMatch?.product

  const [size, setSize] = useState('32')
  const [inspectItem, setInspectItem] = useState(null)
  const [added, setAdded] = useState(false)
  const [showSubScores, setShowSubScores] = useState(false)

  if (!product) return null

  const matchPercent = Math.round((activeMatch?.style_score || 0.88) * 100)

  const handleAddMatch = () => {
    const itemWithMeta = { ...product, selectedSize: size }
    if (onAddToCart) {
      onAddToCart(itemWithMeta)
    } else {
      addToCartLocal(itemWithMeta, 1)
    }
    setAdded(true)
    toast.success(`Added ${product.title} (Size: ${size}) to Cart!`)
    setTimeout(() => setAdded(false), 2200)
  }

  const handleBuyMatch = () => {
    const itemWithMeta = { ...product, selectedSize: size }
    addToCartLocal(itemWithMeta, 1)
    if (onAutonomousCheckout) {
      onAutonomousCheckout({ mode: 'cascade_failover', autoStart: true })
    }
  }

  return (
    <div className={`interactive-suite-container animate-fade ${isStageModal ? 'stage-modal-mode' : ''}`}>
      {/* Header */}
      <div className="suite-header-bar">
        <div className="suite-badge-pill hero">
          <Sparkles size={15} />
          <span>Match My Outfit • Recommended Pairings</span>
        </div>

        <div className="suite-price-savings-cluster">
          <div className="suite-cohesion-meter">
            <span className="meter-val">{matchPercent}%</span>
            <span className="meter-lbl">Harmony</span>
          </div>
        </div>
      </div>

      {/* Matched Candidate Tabs if multiple matches exist */}
      {matchedResults.length > 1 && (
        <div className="suite-combos-tabs-bar">
          <div className="suite-combos-tabs-row horizontal-pills">
            {matchedResults.slice(0, 5).map((m, idx) => (
              <button
                key={idx}
                type="button"
                className={`suite-combo-pill-btn ${selectedMatchIdx === idx ? 'active' : ''}`}
                onClick={() => setSelectedMatchIdx(idx)}
                title={`${m.product?.title} (₹${m.product?.price})`}
              >
                <span className="combo-pill-num">#{idx + 1}</span>
                <span className="combo-pill-name">{m.product?.title?.slice(0, 18) || `Match ${idx + 1}`}…</span>
                <span className="combo-pill-price">₹{m.product?.price}</span>
              </button>
            ))}
          </div>

          <div className="suite-combo-nav-actions">
            <button 
              type="button" 
              className="combo-nav-btn prev"
              disabled={selectedMatchIdx <= 0}
              onClick={() => {
                if (selectedMatchIdx > 0) {
                  setSelectedMatchIdx(prev => prev - 1)
                  toast(`◀ Previous Match (#${selectedMatchIdx})`, { icon: '⏪' })
                }
              }}
              title="Return to previous match"
            >
              <ChevronLeft size={14} />
              <span>Prev Match</span>
            </button>
            
            <button 
              type="button" 
              className="combo-nav-btn next-best"
              disabled={selectedMatchIdx >= matchedResults.length - 1}
              onClick={() => {
                if (selectedMatchIdx < matchedResults.length - 1) {
                  setSelectedMatchIdx(prev => prev + 1)
                  toast.success(`⚡ Next Best Match (#${selectedMatchIdx + 2})`, { icon: '⚡' })
                }
              }}
              title="Next best ranked match"
            >
              <Zap size={14} style={{ color: '#fbbf24' }} />
              <span>Next Match</span>
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      )}

      {/* Side-by-Side: Owned Constant + Catalog Match */}
      <div className="suite-pieces-split-layout">
        {/* Anchor: Owned Garment */}
        <div className="suite-piece-card constant-card">
          <div className="piece-card-header">
            <span className="piece-type-badge anchor">
              <Sparkles size={12} style={{ display: 'inline', marginRight: 4 }} />
              Anchor • You Own This
            </span>
          </div>

          <div className={`piece-image-wrap ${isStageModal ? 'large-modal-wrap' : ''}`}>
            <img 
              src={getProductImageUrl(constant, 'top')} 
              alt="Owned Garment" 
              className="piece-photo" 
              onError={(e) => {
                e.target.onerror = null
                e.target.src = 'https://images.unsplash.com/photo-1556905055-8f358a7a47b2?auto=format&fit=crop&w=800&q=80'
              }}
            />
          </div>

          <div className="piece-details-body">
            <h4 className="piece-item-title">
              {constant?.description || constant?.name || `${constant?.color || ''} ${constant?.category || 'Owned Garment'}`}
            </h4>
            <div className="piece-meta-row" style={{ display: 'flex', gap: 6, marginTop: 8 }}>
              <span className="piece-tag">{constant?.category || 'Garment'}</span>
              <span className="piece-tag color">{constant?.color}</span>
              <span className="piece-tag">{constant?.fit}</span>
            </div>
          </div>
        </div>

        {/* Center Harmony Connector */}
        <div className="suite-center-connector">
          <div className="connector-vertical-line" />
          <div className="connector-harmony-badge">
            <Sparkles size={16} />
            <span className="connector-score">{matchPercent}% Match</span>
            <span className="connector-vibe">Color Science</span>
          </div>
          <div className="connector-vertical-line" />
        </div>

        {/* Catalog Match Piece */}
        <div className="suite-piece-card target-card">
          <div className="piece-card-header">
            <span className="piece-type-badge match">Catalog Recommendation</span>
            <button 
              type="button" 
              className="piece-inspect-btn"
              onClick={() => setInspectItem(product)}
              title="Inspect Garment Details"
            >
              <Eye size={13} />
              <span>Details</span>
            </button>
          </div>

          <div className={`piece-image-wrap ${isStageModal ? 'large-modal-wrap' : ''}`} onClick={() => setInspectItem(product)}>
            <img 
              src={getProductImageUrl(product, 'bottom')} 
              alt={product.title || product.name || 'Catalog Piece'} 
              className="piece-photo" 
              onError={(e) => {
                e.target.onerror = null
                e.target.src = 'https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?auto=format&fit=crop&w=800&q=80'
              }}
            />
            <div className="image-zoom-overlay">
              <Maximize2 size={16} />
            </div>
          </div>

          <div className="piece-details-body">
            <h4 className="piece-item-title" title={product.title}>
              {product.title || product.name}
            </h4>

            <div className="piece-pricing-row">
              <span className="current-price">₹{product.price}</span>
              {product.rating && (
                <span className="rating-pill">★ {product.rating}</span>
              )}
            </div>

            {/* Size Selector */}
            <div className="piece-size-selector-row">
              <span className="size-label">Size:</span>
              <div className="size-pills-wrap">
                {['28', '30', '32', '34', '36'].map(sz => (
                  <button
                    key={sz}
                    type="button"
                    className={`size-pill ${size === sz ? 'selected' : ''}`}
                    onClick={() => setSize(sz)}
                  >
                    {sz}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Rationale Box */}
      <div className="suite-rationale-box">
        <div className="rationale-header-row">
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <Sparkles size={14} style={{ color: 'var(--accent-purple)' }} />
            <strong style={{ fontSize: '0.84rem' }}>Stylist Insight:</strong>
          </div>
          {activeMatch?.sub_scores && (
            <button
              type="button"
              className="btn-text-accordion"
              onClick={() => setShowSubScores(v => !v)}
            >
              {showSubScores ? 'Hide Science ▲' : 'View Science Details ▼'}
            </button>
          )}
        </div>

        <p className="suite-rationale-text">
          {activeMatch?.rationale || "Complementary color harmony calibrated to flatter your owned piece effortlessly."}
        </p>

        {showSubScores && activeMatch?.sub_scores && (
          <div className="suite-subscores-grid animate-fade">
            <div className="subscore-metric">
              <span className="metric-label">Hue Harmony:</span>
              <span className="metric-value">{Math.round((activeMatch.sub_scores.hue_harmony || 0) * 100)}%</span>
            </div>
            <div className="subscore-metric">
              <span className="metric-label">Value Contrast:</span>
              <span className="metric-value">{Math.round((activeMatch.sub_scores.value_contrast || 0) * 100)}%</span>
            </div>
            <div className="subscore-metric">
              <span className="metric-label">Chroma Affinity:</span>
              <span className="metric-value">{Math.round((activeMatch.sub_scores.chroma_comp || 0) * 100)}%</span>
            </div>
            <div className="subscore-metric">
              <span className="metric-label">Neutral Balance:</span>
              <span className="metric-value">{Math.round((activeMatch.sub_scores.neutral_bonus || 0) * 100)}%</span>
            </div>
          </div>
        )}
      </div>

      {/* Footer Action Bar */}
      <div className="suite-footer-action-bar">
        <div className="suite-total-cluster">
          <span className="suite-total-label">Matching Item Price:</span>
          <div className="suite-total-numbers">
            <span className="suite-total-val">₹{product.price}</span>
          </div>
        </div>

        <div className="suite-actions-group">
          <button
            type="button"
            className="btn btn-primary btn-lg suite-add-all-btn"
            onClick={handleAddMatch}
          >
            {added ? <CheckCircle2 size={18} /> : <ShoppingBag size={18} />}
            <span>{added ? 'Added to Cart!' : `Add Match to Cart (₹${product.price})`}</span>
          </button>

          <button
            type="button"
            className="btn btn-outline suite-fastbuy-btn"
            onClick={handleBuyMatch}
          >
            <Zap size={16} />
            <span>1-Click Buy</span>
          </button>
        </div>
      </div>

      {/* Lightbox Modal */}
      {inspectItem && (
        <ProductInspectionModal item={inspectItem} onClose={() => setInspectItem(null)} />
      )}
    </div>
  )
}

// =============================================================================
// SUB-COMPONENT: Product Inspection Lightbox Modal
// =============================================================================
function ProductInspectionModal({ item, onClose }) {
  if (!item) return null

  return (
    <div className="modal-backdrop animate-fade" onClick={onClose}>
      <div className="modal-content product-inspection-modal animate-scale-up" onClick={e => e.stopPropagation()}>
        <button type="button" className="modal-close-btn" onClick={onClose}>
          <X size={18} />
        </button>

        <div className="inspection-grid">
          <div className="inspection-photo-col">
            <img 
              src={getProductImageUrl(item, 'top')} 
              alt={item.title || item.name} 
              className="inspection-large-img" 
              onError={(e) => {
                e.target.onerror = null
                e.target.src = 'https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=800&q=80'
              }}
            />
          </div>

          <div className="inspection-info-col">
            <span className="inspection-merchant-tag">{item.merchant || 'Bewakoof Official'}</span>
            <h3 className="inspection-title">{item.title || item.name}</h3>

            <div className="inspection-price-row">
              <span className="inspect-price">₹{item.price}</span>
              {item.mrp && Number(item.mrp) > item.price && (
                <span className="inspect-mrp">₹{item.mrp}</span>
              )}
              {item.rating && (
                <span className="rating-pill">★ {item.rating} ({item.review_count || 120} reviews)</span>
              )}
            </div>

            <div className="inspection-specs-list">
              <div className="spec-row">
                <span className="spec-key">Category:</span>
                <span className="spec-val">{item.category || 'Apparel'}</span>
              </div>
              {item.specs?.fit && (
                <div className="spec-row">
                  <span className="spec-key">Fit:</span>
                  <span className="spec-val">{item.specs.fit}</span>
                </div>
              )}
              {item.specs?.fabric && (
                <div className="spec-row">
                  <span className="spec-key">Fabric:</span>
                  <span className="spec-val">{item.specs.fabric}</span>
                </div>
              )}
              {item.specs?.color && (
                <div className="spec-row">
                  <span className="spec-key">Color:</span>
                  <span className="spec-val">{item.specs.color}</span>
                </div>
              )}
              <div className="spec-row">
                <span className="spec-key">Delivery:</span>
                <span className="spec-val">{item.shipping_speed || '🚚 Standard (2-3 Days)'}</span>
              </div>
            </div>

            <div style={{ marginTop: 24 }}>
              <button 
                type="button" 
                className="btn btn-primary" 
                style={{ width: '100%', justifyContent: 'center' }}
                onClick={onClose}
              >
                Back to Outfit Suite
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
