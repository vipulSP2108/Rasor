import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { getProductsByIds, cancelPaymentLink } from '../api/client'

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
  enableVqaScanner: false,
  vqaStrictFilter: true,
  vqaLimit: 16,
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
  showMatchPercentage: true,
  paymentLinkExpiryMinutes: 15,
  paymentBufferMinutes: 1,
}

const DEFAULT_USER_PROFILE = {
  fullName: 'Vipul Patil',
  email: 'vipulapatil21@gmail.com',
  phone: '+918806549952',
  defaultSize: 'XL',
  preferredFit: 'Regular Fit',
  preferredColor: 'Any',
  primaryBank: 'CNRB',
  primaryBankLabel: 'Canara Bank',
  secondaryBank: 'BARB_R',
  secondaryBankLabel: 'Bank of Baroda',
  fallbackCard: {
    nickname: 'Test Visa Card',
    last4: '1007',
    cardNumber: '4100 2800 0000 1007',
    exp: '12/28',
    cvv: '123',
    holder: 'Vipul Patil'
  },
  enableSmsNotification: true,
  enableWhatsappRescue: true
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
  } catch (e) { }
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
  } catch (e) { }
}

// ── Lightweight Storage Pruning (95% memory reduction) ───────────────
export const trimProductForStorage = (p) => {
  if (!p || typeof p !== 'object') return p
  return {
    id: p.id,
    title: p.title,
    price: p.price,
    merchant: p.merchant || 'Rasor',
    rating: p.rating,
    category: p.category,
    specs: {
      display_image: p.specs?.display_image || p.specs?.image_url,
      image_url: p.specs?.image_url || p.specs?.display_image,
      variant_ids: p.specs?.variant_ids,
    }
  }
}

export const getStorageUsage = () => {
  let localBytes = 0
  let sessionBytes = 0
  const localKeys = {}
  const sessionKeys = {}

  try {
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i)
      const v = localStorage.getItem(k) || ''
      const size = (k.length + v.length) * 2
      localBytes += size
      localKeys[k] = (size / 1024).toFixed(1) + ' KB'
    }
  } catch (e) {}

  try {
    for (let i = 0; i < sessionStorage.length; i++) {
      const k = sessionStorage.key(i)
      const v = sessionStorage.getItem(k) || ''
      const size = (k.length + v.length) * 2
      sessionBytes += size
      sessionKeys[k] = (size / 1024).toFixed(1) + ' KB'
    }
  } catch (e) {}

  return {
    localKb: (localBytes / 1024).toFixed(1),
    sessionKb: (sessionBytes / 1024).toFixed(1),
    totalKb: ((localBytes + sessionBytes) / 1024).toFixed(1),
    localKeys,
    sessionKeys,
  }
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
    const commonColors = ['black', 'white', 'blue', 'green', 'red', 'yellow', 'taupe', 'brown', 'beige', 'olive', 'pink', 'purple', 'multicolor', 'grey', 'gray']
    for (const clr of commonColors) {
      if (new RegExp(`\\b${clr}\\b`).test(q)) {
        color = clr.charAt(0).toUpperCase() + clr.slice(1)
        break
      }
    }
  }

  // ⚡ Design
  let design = c.design || 'Any'
  if (design === 'Any') {
    if (/\b(graphic|printed|print|marvel|panther|anime)\b/.test(q)) design = 'Graphic Print'
    else if (/\b(solid|plain)\b/.test(q)) design = 'Solid'
    else if (/\b(checked|checks?|stripes?|striped)\b/.test(q)) design = 'Checked / Striped'
    else if (/\b(textured)\b/.test(q)) design = 'Textured'
  }

  // 🦸 Fandom
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

  // 🧵 Sleeve
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

  // 📐 Fit
  let fit = c.fit || 'Any'
  if (fit === 'Any') {
    if (/\b(oversized|baggy|loose)\b/.test(q)) fit = 'Oversized'
    else if (/\b(slim|fitted)\b/.test(q)) fit = 'Slim'
    else if (/\b(regular|classic)\b/.test(q)) fit = 'Regular'
  }

  // 💰 Budget
  const budgetCap = config.maxBudget ? `₹${config.maxBudget}` : 'No Cap'

  return {
    gender,
    category,
    fandom,
    occasion,
    color,
    design,
    size,
    fit,
    sleeve,
    budgetCap
  }
}

const DEFAULT_CART = {
  cartId: 'cart_local_user',
  shopifyCartId: null,
  checkoutUrl: null,
  quantity: 0,
  total: 0,
  items: {},        // { productId: quantity }
  products: {},     // { productId: Product }
}

export function AppProvider({ children }) {
  const [config, setConfig] = useState(() => {
    const saved = loadLocalJson('rasor_config_state', null)
    if (saved) {
      const merged = { ...DEFAULT_CONFIG, ...saved }
      // Auto-migrate legacy 8 limit to 16
      if (saved.vqaLimit === 8 || !saved.vqaLimit) {
        merged.vqaLimit = 16
      }
      return merged
    }
    return DEFAULT_CONFIG
  })

  // Auto-persist config so demoMode and all settings stay preserved across refreshes
  useEffect(() => {
    saveLocalJson('rasor_config_state', config)
  }, [config])

  const [cart, setCart] = useState(() => {
    const loaded = loadLocalJson('rasor_cart_state', null)
    if (loaded && typeof loaded === 'object' && loaded.items && loaded.products) {
      return loaded
    }
    return { ...DEFAULT_CART, cartId: `cart_${Date.now()}` }
  })

  // Auto-persist cart to localStorage so refresh preserves all items and cartId
  useEffect(() => {
    saveLocalJson('rasor_cart_state', cart)
  }, [cart])
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
    } catch { }
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
        if (p && p.id) next[p.id] = trimProductForStorage(p)
      }
      // Cap in-memory cache to 40 items to avoid memory bloat
      const keys = Object.keys(next)
      if (keys.length > 40) {
        for (let i = 0; i < keys.length - 40; i++) {
          delete next[keys[i]]
        }
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
      const next = [record, ...filtered].slice(0, 25) // Keep latest 25 searches
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
      // Sanitize products inside messages before serializing to storage
      const trimmed = (next || []).map(m => {
        if (m.products && Array.isArray(m.products)) {
          return {
            ...m,
            products: m.products.map(trimProductForStorage)
          }
        }
        return m
      })
      saveSessionJson('rasor_chat_messages', trimmed)
      return next
    })
  }, [])

  const clearChatMessages = useCallback(() => {
    setChatMessagesState(INITIAL_CHAT_MESSAGES)
    saveSessionJson('rasor_chat_messages', INITIAL_CHAT_MESSAGES)
  }, [])

  // Persistent Outfit Studio State
  const [studioMessages, setStudioMessagesState] = useState(() =>
    loadSessionJson('rasor_studio_messages', [
      {
        id: 'msg-init',
        role: 'assistant',
        content: "Welcome to **Outfit Studio & Aesthetic Basketing**! 🎨\n\nI'm your conversational fashion coordinator. You can ask for complete multi-piece looks (e.g. *\"I want 2 uppers and 1 lower under 3k\"* or *\"Give me 2 shirts\"*), or tap the **+** button beside the chat box to upload an owned garment you'd like to match.\n\nWhat would you like to put together today?",
        suggestedOptions: [
          "I want 2 uppers and 1 lower under 3k",
          "Give me 2 shirts",
          "Olive hoodie and black joggers under 2500",
          "Vintage graphic tee + denim jeans"
        ],
        voiceEnabled: true
      }
    ])
  )
  const setStudioMessages = useCallback((updater) => {
    setStudioMessagesState(prev => {
      const next = typeof updater === 'function' ? updater(prev) : updater
      saveSessionJson('rasor_studio_messages', next)
      return next
    })
  }, [])

  const [studioMode, setStudioModeState] = useState(() => loadSessionJson('rasor_studio_mode', 'bundle'))
  const setStudioMode = useCallback((updater) => {
    setStudioModeState(prev => {
      const next = typeof updater === 'function' ? updater(prev) : updater
      saveSessionJson('rasor_studio_mode', next)
      return next
    })
  }, [])

  const [studioViewportMode, setStudioViewportModeState] = useState(() => loadSessionJson('rasor_studio_viewport', 'chat'))
  const setStudioViewportMode = useCallback((updater) => {
    setStudioViewportModeState(prev => {
      const next = typeof updater === 'function' ? updater(prev) : updater
      saveSessionJson('rasor_studio_viewport', next)
      return next
    })
  }, [])

  const [studioActiveStageBundle, setStudioActiveStageBundleState] = useState(() => loadSessionJson('rasor_studio_stage_bundle', null))
  const setStudioActiveStageBundle = useCallback((updater) => {
    setStudioActiveStageBundleState(prev => {
      const next = typeof updater === 'function' ? updater(prev) : updater
      saveSessionJson('rasor_studio_stage_bundle', next)
      return next
    })
  }, [])

  const [studioExpandedLooks, setStudioExpandedLooksState] = useState(() => loadSessionJson('rasor_studio_expanded', {}))
  const setStudioExpandedLooks = useCallback((updater) => {
    setStudioExpandedLooksState(prev => {
      const next = typeof updater === 'function' ? updater(prev) : updater
      saveSessionJson('rasor_studio_expanded', next)
      return next
    })
  }, [])


// Default 5-item fashion runner-up buffer (ensures immediate zero-latency demo availability)
const DEFAULT_CANDIDATE_BUFFER = [
  {
    id: "BWK-BEWA-597127-XL",
    title: "Men's Black NASA Typography Oversized Hoodies",
    price: 1999,
    merchant: "Bewakoof",
    specs: {
      display_image: "https://images.bewakoof.com/t640/men-s-black-nasa-typography-oversized-hoodies-597127-1763470928-1.jpg",
      image_url: "https://images.bewakoof.com/t640/men-s-black-nasa-typography-oversized-hoodies-597127-1763470928-1.jpg",
      variant_ids: { XL: "gid://shopify/ProductVariant/597127-XL" }
    }
  },
  {
    id: "BWK-BEWA-685340-XL",
    title: "Men's Jet Black Spiderman Typography Oversized T-shirt",
    price: 999,
    merchant: "Bewakoof",
    specs: {
      display_image: "https://images.bewakoof.com/t640/685340_2026-03-23t10-12-15_1.jpg",
      image_url: "https://images.bewakoof.com/t640/685340_2026-03-23t10-12-15_1.jpg",
      variant_ids: { XL: "gid://shopify/ProductVariant/685340-XL" }
    }
  },
  {
    id: "BWK-BEWA-556949-XL",
    title: "Men's Black I Need My Space NASA Typography Sweatshirt",
    price: 839,
    merchant: "Bewakoof",
    specs: {
      display_image: "https://images.bewakoof.com/t640/men-s-black-i-need-my-space-nasa-typography-sweatshirt-556949-1738310566-1.jpg",
      image_url: "https://images.bewakoof.com/t640/men-s-black-i-need-my-space-nasa-typography-sweatshirt-556949-1738310566-1.jpg",
      variant_ids: { XL: "gid://shopify/ProductVariant/556949-XL" }
    }
  },
  {
    id: "BWK-BEWA-664129-XL",
    title: "Men's Black NASA Typography Oversized Cargo Joggers",
    price: 1399,
    merchant: "Bewakoof",
    specs: {
      display_image: "https://images.bewakoof.com/t640/664129_2026-01-14t10-36-41_1.jpg",
      image_url: "https://images.bewakoof.com/t640/664129_2026-01-14t10-36-41_1.jpg",
      variant_ids: { XL: "gid://shopify/ProductVariant/664129-XL" }
    }
  },
  {
    id: "BWK-BEWA-664142-XL",
    title: "Men's Winter Moss Green NASA Typography Oversized Joggers",
    price: 1499,
    merchant: "Bewakoof",
    specs: {
      display_image: "https://images.bewakoof.com/t640/664142_2026-01-20t08-19-17_1.jpg",
      image_url: "https://images.bewakoof.com/t640/664142_2026-01-20t08-19-17_1.jpg",
      variant_ids: { XL: "gid://shopify/ProductVariant/664142-XL" }
    }
  }
]

  const [candidateBuffer, setCandidateBufferState] = useState(() => {
    const saved = loadSessionJson('rasor_candidate_buffer', null)
    return (Array.isArray(saved) && saved.length > 0) ? saved : DEFAULT_CANDIDATE_BUFFER
  })

  const setCandidateBuffer = useCallback((buffer) => {
    setCandidateBufferState(buffer)
    saveSessionJson('rasor_candidate_buffer', buffer)
  }, [])

  // Simulated OOS Failover Cascade State (Default: 0 — Direct Success)
  const [simulatedOosCount, setSimulatedOosCountState] = useState(0)
  const [simulatedOosRemaining, setSimulatedOosRemaining] = useState(0)

  const setSimulatedOosCount = useCallback((count) => {
    const num = Math.max(0, parseInt(count, 10) || 0)
    setSimulatedOosCountState(num)
    setSimulatedOosRemaining(num)
  }, [])

  // Simulated Post-Payment OOS Race Condition Collision & Instant Refund
  const [simulatePostPaymentOos, setSimulatePostPaymentOosState] = useState(() =>
    loadSessionJson('rasor_simulate_post_payment_oos', false)
  )
  const [postPaymentRefundData, setPostPaymentRefundData] = useState(null)

  const setSimulatePostPaymentOos = useCallback((val) => {
    const bool = !!val
    setSimulatePostPaymentOosState(bool)
    saveSessionJson('rasor_simulate_post_payment_oos', bool)
  }, [])

  const setSearchState = useCallback((patch) => {
    setSearchStateInternal(prev => {
      const next = typeof patch === 'function' ? patch(prev) : { ...prev, ...patch }
      // Prune heavy discardedProducts and strip full HTML/specs before writing to storage
      const sanitized = {
        query: next.query,
        results: (next.results || []).slice(0, 24).map(trimProductForStorage),
        discardedProducts: [], // Kept in memory only; pruned from storage
        evaluations: [],
        canonicalQuery: next.canonicalQuery,
        status: next.status,
      }
      saveSessionJson('rasor_search_state', sanitized)
      if (next.results && next.results.length > 1) {
        setCandidateBuffer(next.results.slice(1, 6))
      }
      return next
    })
  }, [setCandidateBuffer])

  const saveSearchSnapshot = useCallback((snapshot) => {
    if (!snapshot || !snapshot.query) return
    setSearchHistory(prev => {
      // Avoid duplicate consecutive searches
      const filtered = prev.filter(s => s.query.toLowerCase() !== snapshot.query.toLowerCase())
      const item = {
        id: Date.now(),
        query: snapshot.query,
        resultsCount: (snapshot.results || []).length,
        results: (snapshot.results || []).slice(0, 8).map(trimProductForStorage),
        canonicalQuery: snapshot.canonicalQuery,
        status: snapshot.status,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }
      const next = [item, ...filtered].slice(0, 4) // Keep latest 4 searches max
      saveSessionJson('rasor_search_history', next)
      return next
    })
  }, [])

  const clearStorageCaches = useCallback(() => {
    try {
      sessionStorage.removeItem('rasor_product_cache')
      sessionStorage.removeItem('rasor_search_state')
      sessionStorage.removeItem('rasor_search_history')
      sessionStorage.removeItem('rasor_candidate_buffer')
      sessionStorage.removeItem('rasor_chat_messages')
      sessionStorage.removeItem('rasor_studio_messages')
      sessionStorage.removeItem('rasor_studio_mode')
      sessionStorage.removeItem('rasor_studio_viewport')
      sessionStorage.removeItem('rasor_studio_stage_bundle')
      sessionStorage.removeItem('rasor_studio_expanded')
      localStorage.removeItem('rasor_persistent_history')
      localStorage.removeItem('rasor_compare_ids')
      setProductCache({})
      setSearchHistory([])
      setHistoryRecords([])
      setChatMessagesState(INITIAL_CHAT_MESSAGES)
      setSearchStateInternal(INITIAL_SEARCH_STATE)
      setStudioMessagesState([
        {
          id: 'msg-init',
          role: 'assistant',
          content: "Welcome to **Outfit Studio & Aesthetic Basketing**! 🎨\n\nI'm your conversational fashion coordinator. You can ask for complete multi-piece looks (e.g. *\"I want 2 uppers and 1 lower under 3k\"* or *\"Give me 2 shirts\"*), or tap the **+** button beside the chat box to upload an owned garment you'd like to match.\n\nWhat would you like to put together today?",
          suggestedOptions: [
            "I want 2 uppers and 1 lower under 3k",
            "Give me 2 shirts",
            "Olive hoodie and black joggers under 2500",
            "Vintage graphic tee + denim jeans"
          ],
          voiceEnabled: true
        }
      ])
      setStudioModeState('bundle')
      setStudioViewportModeState('chat')
      setStudioActiveStageBundleState(null)
      setStudioExpandedLooksState({})
    } catch (e) {}
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
        cartId: c.cartId || `cart_${Date.now()}`,
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
    // Invalidate payment link if cart contents change
    const activePlink = loadLocalJson('rasor_active_plink', null)
    if (activePlink?.plink_id) {
      cancelPaymentLink(activePlink.plink_id).catch(() => { })
      localStorage.removeItem('rasor_active_plink')
    }
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
    // Invalidate payment link if quantity changes
    const activePlink = loadLocalJson('rasor_active_plink', null)
    if (activePlink?.plink_id) {
      cancelPaymentLink(activePlink.plink_id).catch(() => { })
      localStorage.removeItem('rasor_active_plink')
    }
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
    // Immediately cancel and expire active payment link on Razorpay servers
    const activePlink = loadLocalJson('rasor_active_plink', null)
    if (activePlink?.plink_id) {
      cancelPaymentLink(activePlink.plink_id).catch(() => { })
      localStorage.removeItem('rasor_active_plink')
    }
    const fresh = { ...DEFAULT_CART, cartId: `cart_${Date.now()}` }
    setCart(fresh)
    saveLocalJson('rasor_cart_state', fresh)
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

  const [userProfile, setUserProfileState] = useState(() =>
    loadLocalJson('rasor_user_profile', DEFAULT_USER_PROFILE)
  )

  const updateUserProfile = useCallback((patch) => {
    setUserProfileState(prev => {
      const next = typeof patch === 'function' ? patch(prev) : { ...prev, ...patch }
      saveLocalJson('rasor_user_profile', next)
      return next
    })
  }, [])

  return (
    <AppContext.Provider value={{
      config, updateConfig,
      userProfile, updateUserProfile,
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
      candidateBuffer, setCandidateBuffer,
      simulatedOosCount, setSimulatedOosCount,
      simulatedOosRemaining, setSimulatedOosRemaining,
      simulatePostPaymentOos, setSimulatePostPaymentOos,
      postPaymentRefundData, setPostPaymentRefundData,
      clearStorageCaches,
      studioMessages, setStudioMessages,
      studioMode, setStudioMode,
      studioViewportMode, setStudioViewportMode,
      studioActiveStageBundle, setStudioActiveStageBundle,
      studioExpandedLooks, setStudioExpandedLooks,
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
