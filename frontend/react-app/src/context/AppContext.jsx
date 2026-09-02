import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { getProductsByIds } from '../api/client'

const AppContext = createContext(null)

const DEFAULT_CONFIG = {
  customerEmail: 'vipulapatil21@gmail.com',
  mode: 'live',
  dataSource: 'shopify_storefront_live_api',
  primaryModel: 'gemini-3.5-flash',
  fallbackModel: 'llama-3.3-70b-versatile',
  maxResults: 21,
  enableDeepEnrichment: true,
  maxDeepFetches: 10,
  enableVqaScanner: true,
  vqaStrictFilter: true,
  truthHierarchy: true,
  enableOfferEngine: true,
  enableSemanticEngine: true,
  maxCostHitl: 800,
  maxBudget: 3000,
  currency: 'INR',
  userLocation: 'Mumbai',
  demoMode: 'human_present',
  voiceEnabled: true,
  voiceURI: null,
}

const INITIAL_CHAT_MESSAGES = [
  {
    role: 'assistant',
    content: "Welcome to **Rasor**! I'm your AI personal stylist. 🛍️ Tell me what you're looking for — I'll ask just a few smart questions or evaluate your skin tone to find the perfect match for you.",
    suggestedOptions: ['Show me men\'s t-shirts', 'Marvel fan merch', 'Skin tone 5', 'Something for the gym', 'Surprise me 🎲'],
    products: null,
  }
]

const INITIAL_SEARCH_STATE = {
  query: '',
  results: [],
  discardedProducts: [],
  evaluations: [],
  canonicalQuery: null,
  status: null,
}

// Helpers for safe storage persistence
const loadLocalJson = (key, fallback) => {
  try {
    const item = localStorage.getItem(key)
    return item ? JSON.parse(item) : fallback
  } catch (e) {
    return fallback
  }
}

const saveLocalJson = (key, val) => {
  try {
    localStorage.setItem(key, JSON.stringify(val))
  } catch (e) {}
}

const loadSessionJson = (key, fallback) => {
  try {
    const item = sessionStorage.getItem(key)
    return item ? JSON.parse(item) : fallback
  } catch (e) {
    return fallback
  }
}

const saveSessionJson = (key, val) => {
  try {
    sessionStorage.setItem(key, JSON.stringify(val))
  } catch (e) {}
}

export function extractQueryMetadata(queryStr = '', canonical = {}, config = {}) {
  const q = (queryStr || '').toLowerCase()
  const c = canonical || {}
  
  // 👤 Gender
  let gender = c.gender || 'All'
  if (gender === 'All') {
    if (/\b(men|man|male|boys?|gentlemen)\b/.test(q)) gender = 'Men'
    else if (/\b(women|woman|female|girls?|ladies)\b/.test(q)) gender = 'Women'
  }

  // 🏷️ Category
  let category = c.category || 'Any'
  if (category === 'Any') {
    if (/\b(t-?shirt|tee)\b/.test(q)) category = 'T-Shirt'
    else if (/\b(hoodie|sweatshirt)\b/.test(q)) category = 'Hoodie'
    else if (/\b(shirt)\b/.test(q)) category = 'Shirt'
    else if (/\b(jacket|coat)\b/.test(q)) category = 'Jacket'
    else if (/\b(polo)\b/.test(q)) category = 'Polo'
    else if (/\b(pants|jeans|joggers|trousers)\b/.test(q)) category = 'Pants'
  }

  // 🎉 Occasion
  let occasion = 'Any'
  if (/\b(gym|workout|athletic|sports?|running)\b/.test(q)) occasion = 'Gym'
  else if (/\b(party|club|festive|wedding)\b/.test(q)) occasion = 'Party'
  else if (/\b(casual|daily|lounge|home)\b/.test(q)) occasion = 'Casual'
  else if (/\b(work|formal|office)\b/.test(q)) occasion = 'Work'

  // 🎨 Color
  let color = c.color || 'Any'
  if (color === 'Any') {
    const colors = ['black', 'white', 'blue', 'green', 'red', 'yellow', 'taupe', 'brown', 'beige', 'olive', 'pink', 'purple', 'multicolor', 'grey', 'gray']
    for (const clr of colors) {
      if (new RegExp(`\\b${clr}\\b`).test(q)) {
        color = clr.charAt(0).toUpperCase() + clr.slice(1)
        break
      }
    }
  }

  // 🎨 Design Pattern
  let design = c.design || 'Any'
  if (design === 'Any') {
    if (/\b(graphic|printed|print|marvel|panther|anime)\b/.test(q)) design = 'Graphic Print'
    else if (/\b(solid|plain)\b/.test(q)) design = 'Solid'
    else if (/\b(checked|checks?|stripes?|striped)\b/.test(q)) design = 'Checked / Striped'
    else if (/\b(textured)\b/.test(q)) design = 'Textured'
  }

  // Theme / Fandom / Character
  let fandom = c.fandom || null
  if (!fandom) {
    if (/\b(iron man|ironman)\b/.test(q)) fandom = 'Marvel (Iron Man)'
    else if (/\b(black panther|wakanda|t'?challa)\b/.test(q)) fandom = 'Marvel (Black Panther)'
    else if (/\b(spider-?man|spiderman|venom)\b/.test(q)) fandom = 'Marvel (Spider-Man)'
    else if (/\b(captain america|avengers|thor|deadpool|hulk|loki|groot|wolverine|marvel)\b/.test(q)) fandom = 'Marvel'
    else if (/\b(batman|dark knight|superman|joker|gotham|flash|dc)\b/.test(q)) fandom = 'DC Universe'
    else if (/\b(naruto|dragon ball|dbz|anime|manga|itachi)\b/.test(q)) fandom = 'Anime'
    else if (/\b(harry potter|hogwarts|gryffindor)\b/.test(q)) fandom = 'Harry Potter'
    else if (/\b(mickey|disney|donald duck)\b/.test(q)) fandom = 'Disney'
  }

  // Sleeve
  let sleeve = c.sleeve || 'Any'
  if (sleeve === 'Any') {
    if (/\b(half sleeve|short sleeve)\b/.test(q)) sleeve = 'Half Sleeve'
    else if (/\b(full sleeve|long sleeve)\b/.test(q)) sleeve = 'Full Sleeve'
    else if (/\b(sleeveless|vest|tank)\b/.test(q)) sleeve = 'Sleeveless'
  }

  // 📏 Size
  let size = 'Any'
  const sizeMatch = q.match(/\b(3xl|2xl|xxl|xl|xs|s|m|l)\b/i)
  if (sizeMatch) size = sizeMatch[1].toUpperCase()

  // 👕 Fit
  let fit = c.fit || 'Any'
  if (fit === 'Any') {
    if (/\b(oversized|baggy|loose)\b/.test(q)) fit = 'Oversized'
    else if (/\b(slim|fitted)\b/.test(q)) fit = 'Slim'
    else if (/\b(regular|classic)\b/.test(q)) fit = 'Regular'
  }

  // 💰 Budget Cap
  const budgetCap = config.maxBudget ? `₹${config.maxBudget}` : 'No Cap'

  return { gender, category, fandom, occasion, color, design, size, fit, sleeve, budgetCap }
}

export function AppProvider({ children }) {
  const [config, setConfig] = useState(DEFAULT_CONFIG)
  const [cart, setCart] = useState({
    shopifyCartId: null,
    checkoutUrl: null,
    quantity: 0,
    total: 0,
    items: {},        // { productId: qty }
    products: {},     // { productId: Product }
  })
  const [compareList, setCompareListState] = useState({})
  const getDeterministicCustomerId = (email) => {
    if (!email) return 'cust_vipulapatil21'
    const clean = email.toLowerCase().replace(/[^a-z0-9]/g, '')
    return `cust_${clean.slice(0, 16)}`
  }

  // Multi-account mandate token store: { [email]: { token, customerId, maxLimit } }
  const [mandatesByEmail, setMandatesByEmail] = useState(() => 
    loadLocalJson('rasor_mandates_by_email', {
      'vipulapatil21@gmail.com': {
        token: loadLocalJson('rasor_rzp_token', null),
        customerId: 'cust_vipulapatil21',
        maxLimit: loadLocalJson('rasor_rzp_token_max_limit', 800)
      }
    })
  )

  const activeEmail = config.customerEmail || 'vipulapatil21@gmail.com'
  const emailMandate = mandatesByEmail[activeEmail] || {}

  const [razorpayToken, setRazorpayToken] = useState(() => 
    emailMandate.token || loadLocalJson('rasor_rzp_token', null)
  )
  const [razorpayCustomerId, setRazorpayCustomerId] = useState(() => 
    emailMandate.customerId || getDeterministicCustomerId(activeEmail)
  )
  const [tokenMaxLimit, setTokenMaxLimit] = useState(() => 
    emailMandate.maxLimit || loadLocalJson('rasor_rzp_token_max_limit', 800)
  )

  // Re-sync token and customer ID whenever customerEmail changes
  useEffect(() => {
    const email = config.customerEmail || 'vipulapatil21@gmail.com'
    const stored = mandatesByEmail[email]
    const derivedCustId = stored?.customerId || getDeterministicCustomerId(email)
    
    setRazorpayCustomerId(derivedCustId)
    setRazorpayToken(stored?.token || null)
    setTokenMaxLimit(stored?.maxLimit || null)
  }, [config.customerEmail, mandatesByEmail])

  const saveMandateToken = useCallback((tokenId, customerId, amount, emailOverride) => {
    if (!tokenId) return
    const email = emailOverride || config.customerEmail || 'vipulapatil21@gmail.com'
    const custId = customerId || getDeterministicCustomerId(email)
    
    setMandatesByEmail(prev => {
      const existing = prev[email] || {}
      const newMax = amount ? Math.max(Number(existing.maxLimit || 0), Number(amount)) : (existing.maxLimit || 800)
      const updated = {
        ...prev,
        [email]: {
          token: tokenId,
          customerId: custId,
          maxLimit: newMax,
          updatedAt: new Date().toISOString()
        }
      }
      saveLocalJson('rasor_mandates_by_email', updated)
      return updated
    })

    setRazorpayToken(tokenId)
    setRazorpayCustomerId(custId)
    saveLocalJson('rasor_rzp_token', tokenId)
    saveLocalJson('rasor_rzp_customer_id', custId)

    if (amount) {
      setTokenMaxLimit(prev => {
        const newMax = Math.max(Number(prev || 0), Number(amount))
        saveLocalJson('rasor_rzp_token_max_limit', newMax)
        return newMax
      })
    }
  }, [config.customerEmail])

  const updateMandateLimit = useCallback((limit, emailOverride) => {
    const num = Number(limit) || 0
    const email = emailOverride || config.customerEmail || 'vipulapatil21@gmail.com'
    
    setMandatesByEmail(prev => {
      const existing = prev[email] || {}
      const updated = {
        ...prev,
        [email]: {
          ...existing,
          maxLimit: num
        }
      }
      saveLocalJson('rasor_mandates_by_email', updated)
      return updated
    })

    setTokenMaxLimit(num)
    saveLocalJson('rasor_rzp_token_max_limit', num)
  }, [config.customerEmail])

  const updateMandateTokenId = useCallback((token, emailOverride) => {
    const email = emailOverride || config.customerEmail || 'vipulapatil21@gmail.com'
    
    setMandatesByEmail(prev => {
      const existing = prev[email] || {}
      const updated = {
        ...prev,
        [email]: {
          ...existing,
          token: token || null
        }
      }
      saveLocalJson('rasor_mandates_by_email', updated)
      return updated
    })

    setRazorpayToken(token || null)
    if (token) {
      saveLocalJson('rasor_rzp_token', token)
    } else {
      localStorage.removeItem('rasor_rzp_token')
    }
  }, [config.customerEmail])

  const clearMandateToken = useCallback((emailOverride) => {
    const email = emailOverride || config.customerEmail || 'vipulapatil21@gmail.com'
    
    setMandatesByEmail(prev => {
      const next = { ...prev }
      delete next[email]
      saveLocalJson('rasor_mandates_by_email', next)
      return next
    })

    setRazorpayToken(null)
    setTokenMaxLimit(null)
    try {
      localStorage.removeItem('rasor_rzp_token')
      localStorage.removeItem('rasor_rzp_token_max_limit')
    } catch {}
  }, [config.customerEmail])

  // In-memory / session product cache by ID
  const [productCache, setProductCache] = useState(() => 
    loadSessionJson('rasor_product_cache', {})
  )

  const cacheProducts = useCallback((prods = []) => {
    if (!prods || !prods.length) return
    setProductCache(prev => {
      const next = { ...prev }
      for (const p of prods) {
        if (p && p.id) next[p.id] = p
      }
      saveSessionJson('rasor_product_cache', next)
      return next
    })
  }, [])

  // Auto-hydrate compare products on startup / reload from lightweight stored IDs
  useEffect(() => {
    const ids = loadLocalJson('rasor_compare_ids', [])
    if (!ids || !ids.length) return

    getProductsByIds({ ids })
      .then(({ data }) => {
        const prods = data.products || []
        if (prods.length > 0) {
          cacheProducts(prods)
          const map = {}
          for (const p of prods) {
            if (p && p.id) map[p.id] = p
          }
          setCompareListState(map)
        }
      })
      .catch(err => console.error('[AppContext] Failed to hydrate compare list on load:', err))
  }, [cacheProducts])

  // Persistent Chat & Search State
  const [chatMessages, setChatMessagesState] = useState(() => 
    loadSessionJson('rasor_chat_messages', INITIAL_CHAT_MESSAGES)
  )
  const [searchState, setSearchStateInternal] = useState(() => 
    loadSessionJson('rasor_search_state', INITIAL_SEARCH_STATE)
  )
  const [searchHistory, setSearchHistory] = useState(() => 
    loadSessionJson('rasor_search_history', [])
  )

  // Global Lightweight History Records (localStorage)
  const [historyRecords, setHistoryRecords] = useState(() => 
    loadLocalJson('rasor_persistent_history', [])
  )

  const addHistoryRecord = useCallback((entry) => {
    if (!entry || !entry.query) return
    setHistoryRecords(prev => {
      const filtered = prev.filter(h => h.query.toLowerCase() !== entry.query.toLowerCase())
      const record = {
        id: `hist_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`,
        timestamp: new Date().toISOString(),
        formattedDate: new Date().toLocaleString([], { 
          month: 'short', day: 'numeric', year: 'numeric', 
          hour: '2-digit', minute: '2-digit' 
        }),
        source: entry.source || 'chat', // 'chat' | 'search'
        query: entry.query,
        productIds: entry.productIds || (entry.products || []).map(p => p.id),
        itemCount: (entry.productIds || entry.products || []).length,
        metadata: entry.metadata || extractQueryMetadata(entry.query, entry.canonicalQuery, config),
        sampleThumbnails: (entry.products || [])
          .slice(0, 3)
          .map(p => p.specs?.display_image || p.specs?.image_url)
          .filter(Boolean),
      }
      const next = [record, ...filtered].slice(0, 40) // Keep latest 40 searches
      saveLocalJson('rasor_persistent_history', next)
      return next
    })
    if (entry.products && entry.products.length) {
      cacheProducts(entry.products)
    }
  }, [config, cacheProducts])

  const deleteHistoryRecord = useCallback((recordId) => {
    setHistoryRecords(prev => {
      const next = prev.filter(h => h.id !== recordId)
      saveLocalJson('rasor_persistent_history', next)
      return next
    })
  }, [])

  const clearHistoryRecords = useCallback(() => {
    setHistoryRecords([])
    saveLocalJson('rasor_persistent_history', [])
  }, [])

  const setChatMessages = useCallback((updater) => {
    setChatMessagesState(prev => {
      const next = typeof updater === 'function' ? updater(prev) : updater
      saveSessionJson('rasor_chat_messages', next)
      return next
    })
  }, [])

  const clearChatMessages = useCallback(() => {
    setChatMessagesState(INITIAL_CHAT_MESSAGES)
    saveSessionJson('rasor_chat_messages', INITIAL_CHAT_MESSAGES)
  }, [])

  const setSearchState = useCallback((patch) => {
    setSearchStateInternal(prev => {
      const next = typeof patch === 'function' ? patch(prev) : { ...prev, ...patch }
      saveSessionJson('rasor_search_state', next)
      return next
    })
  }, [])

  const saveSearchSnapshot = useCallback((snapshot) => {
    if (!snapshot || !snapshot.query) return
    setSearchHistory(prev => {
      // Avoid duplicate consecutive searches
      const filtered = prev.filter(s => s.query.toLowerCase() !== snapshot.query.toLowerCase())
      const item = {
        id: Date.now(),
        query: snapshot.query,
        resultsCount: (snapshot.results || []).length,
        results: snapshot.results || [],
        discardedProducts: snapshot.discardedProducts || [],
        evaluations: snapshot.evaluations || [],
        canonicalQuery: snapshot.canonicalQuery,
        status: snapshot.status,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }
      const next = [item, ...filtered].slice(0, 8)
      saveSessionJson('rasor_search_history', next)
      return next
    })
  }, [])

  const restoreSearchSnapshot = useCallback((snapshotId) => {
    setSearchHistory(prev => {
      const found = prev.find(s => s.id === snapshotId)
      if (found) {
        setSearchStateInternal({
          query: found.query,
          results: found.results,
          discardedProducts: found.discardedProducts,
          evaluations: found.evaluations,
          canonicalQuery: found.canonicalQuery,
          status: found.status,
        })
        saveSessionJson('rasor_search_state', found)
      }
      return prev
    })
  }, [])

  const clearSearchHistory = useCallback(() => {
    setSearchHistory([])
    saveSessionJson('rasor_search_history', [])
  }, [])

  const updateConfig = useCallback((patch) => setConfig(c => ({ ...c, ...patch })), [])

  const addToCartLocal = useCallback((product, qty = 1, shopifyData = null) => {
    setCart(c => {
      const prevQty = c.items[product.id] || 0
      const newItems = { ...c.items, [product.id]: prevQty + qty }
      const newProducts = { ...c.products, [product.id]: product }
      
      const newQty = Object.values(newItems).reduce((sum, q) => sum + q, 0)
      const newTotal = Object.entries(newItems).reduce((sum, [id, q]) => sum + ((newProducts[id]?.price || 0) * q), 0)

      return {
        ...c,
        shopifyCartId: shopifyData?.cart_id || c.shopifyCartId,
        checkoutUrl: shopifyData?.checkout_url || c.checkoutUrl,
        quantity: newQty,
        total: newTotal,
        items: newItems,
        products: newProducts,
      }
    })
  }, [])

  const removeFromCart = useCallback((productId) => {
    setCart(c => {
      const newItems = { ...c.items }
      const newProducts = { ...c.products }
      delete newItems[productId]
      delete newProducts[productId]
      const newQty = Object.values(newItems).reduce((sum, q) => sum + q, 0)
      const newTotal = Object.entries(newItems).reduce((sum, [id, q]) => sum + ((newProducts[id]?.price || 0) * q), 0)
      return {
        ...c,
        quantity: newQty,
        total: newTotal,
        items: newItems,
        products: newProducts,
      }
    })
  }, [])

  const updateQty = useCallback((productId, newQty) => {
    setCart(c => {
      if (newQty <= 0) {
        const newItems = { ...c.items }
        const newProducts = { ...c.products }
        delete newItems[productId]
        delete newProducts[productId]
        const q = Object.values(newItems).reduce((sum, val) => sum + val, 0)
        const t = Object.entries(newItems).reduce((sum, [id, val]) => sum + ((newProducts[id]?.price || 0) * val), 0)
        return { ...c, quantity: q, total: t, items: newItems, products: newProducts }
      }
      const newItems = { ...c.items, [productId]: newQty }
      const q = Object.values(newItems).reduce((sum, val) => sum + val, 0)
      const t = Object.entries(newItems).reduce((sum, [id, val]) => sum + ((c.products[id]?.price || 0) * val), 0)
      return {
        ...c,
        quantity: q,
        total: t,
        items: newItems,
      }
    })
  }, [])

  const clearCart = useCallback(() => {
    setCart({ shopifyCartId: null, checkoutUrl: null, quantity: 0, total: 0, items: {}, products: {} })
  }, [])

  const setShopifyCart = useCallback((cartId, checkoutUrl) => {
    setCart(c => ({ ...c, shopifyCartId: cartId, checkoutUrl }))
  }, [])

  const toggleCompare = useCallback((product) => {
    setCompareListState(prev => {
      let next
      if (prev[product.id]) {
        next = { ...prev }
        delete next[product.id]
      } else {
        if (Object.keys(prev).length >= 5) return prev
        next = { ...prev, [product.id]: product }
      }
      // Store ONLY the array of string IDs in localStorage
      saveLocalJson('rasor_compare_ids', Object.keys(next))
      return next
    })
  }, [])

  const updateCompareProducts = useCallback((updatedProducts = []) => {
    if (!updatedProducts || !updatedProducts.length) return
    setCompareListState(prev => {
      const next = { ...prev }
      for (const p of updatedProducts) {
        if (p && p.id && next[p.id]) {
          next[p.id] = { ...next[p.id], ...p }
        }
      }
      saveLocalJson('rasor_compare_ids', Object.keys(next))
      return next
    })
  }, [])

  const clearCompare = useCallback(() => {
    setCompareListState({})
    saveLocalJson('rasor_compare_ids', [])
  }, [])

  return (
    <AppContext.Provider value={{
      config, updateConfig,
      cart, addToCartLocal, removeFromCart, updateQty, clearCart, setShopifyCart,
      compareList, toggleCompare, updateCompareProducts, clearCompare,
      chatMessages, setChatMessages, clearChatMessages,
      searchState, setSearchState,
      searchHistory, saveSearchSnapshot, restoreSearchSnapshot, clearSearchHistory,
      historyRecords, addHistoryRecord, deleteHistoryRecord, clearHistoryRecords,
      productCache, cacheProducts,
      razorpayToken, setRazorpayToken,
      razorpayCustomerId, setRazorpayCustomerId,
      tokenMaxLimit, setTokenMaxLimit,
      saveMandateToken, clearMandateToken,
      updateMandateLimit, updateMandateTokenId,
    }}>
      {children}
    </AppContext.Provider>
  )
}

export function useApp() {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used within AppProvider')
  return ctx
}
