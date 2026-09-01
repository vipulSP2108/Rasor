import { createContext, useContext, useState, useCallback } from 'react'

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
  const [compareList, setCompareList] = useState({})   // { productId: Product }
  const [razorpayToken, setRazorpayToken] = useState(null)
  const [razorpayCustomerId, setRazorpayCustomerId] = useState(null)

  const updateConfig = useCallback((patch) => setConfig(c => ({ ...c, ...patch })), [])

  const addToCartLocal = useCallback((product, qty = 1) => {
    setCart(c => {
      const prevQty = c.items[product.id] || 0
      return {
        ...c,
        quantity: c.quantity + qty,
        total: c.total + product.price * qty,
        items: { ...c.items, [product.id]: prevQty + qty },
        products: { ...c.products, [product.id]: product },
      }
    })
  }, [])

  const removeFromCart = useCallback((productId) => {
    setCart(c => {
      const qty = c.items[productId] || 0
      const price = c.products[productId]?.price || 0
      const newItems = { ...c.items }
      const newProducts = { ...c.products }
      delete newItems[productId]
      delete newProducts[productId]
      return {
        ...c,
        quantity: Math.max(0, c.quantity - qty),
        total: Math.max(0, c.total - price * qty),
        items: newItems,
        products: newProducts,
      }
    })
  }, [])

  const updateQty = useCallback((productId, newQty) => {
    setCart(c => {
      const oldQty = c.items[productId] || 0
      const price = c.products[productId]?.price || 0
      const diff = newQty - oldQty
      return {
        ...c,
        quantity: c.quantity + diff,
        total: c.total + price * diff,
        items: { ...c.items, [productId]: newQty },
      }
    })
  }, [])

  const clearCart = useCallback(() => {
    setCart({ shopifyCartId: null, checkoutUrl: null, quantity: 0, total: 0, items: {}, products: {} })
  }, [])

  const setShopifyCart = useCallback((cartId, checkoutUrl, totalQty, totalCost) => {
    setCart(c => ({ ...c, shopifyCartId: cartId, checkoutUrl, quantity: totalQty, total: totalCost }))
  }, [])

  const toggleCompare = useCallback((product) => {
    setCompareList(prev => {
      if (prev[product.id]) {
        const next = { ...prev }; delete next[product.id]; return next
      }
      if (Object.keys(prev).length >= 5) return prev
      return { ...prev, [product.id]: product }
    })
  }, [])
  const clearCompare = useCallback(() => setCompareList({}), [])

  return (
    <AppContext.Provider value={{
      config, updateConfig,
      cart, addToCartLocal, removeFromCart, updateQty, clearCart, setShopifyCart,
      compareList, toggleCompare, clearCompare,
      razorpayToken, setRazorpayToken,
      razorpayCustomerId, setRazorpayCustomerId,
    }}>
      {children}
    </AppContext.Provider>
  )
}

export const useApp = () => {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be inside AppProvider')
  return ctx
}
