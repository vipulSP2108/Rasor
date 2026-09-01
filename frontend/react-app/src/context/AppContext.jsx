import React from 'react';
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
