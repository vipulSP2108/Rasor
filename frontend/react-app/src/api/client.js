import axios from 'axios'

const api = axios.create({ baseURL: '' })

export const searchProducts = (data) => api.post('/api/search', data)
export const chatMessage = (data) => api.post('/api/chat', data)
export const clearChat = (sessionId) => api.delete(`/api/chat/${sessionId}`)
export const compareProducts = (data) => api.post('/api/compare', data)
export const createCart = (data) => api.post('/api/cart/create', data)
export const addToCart = (data) => api.post('/api/cart/add', data)
export const createOrder = (data) => api.post('/api/checkout/order', data)
export const createMandateOrder = (data) => api.post('/api/checkout/mandate-order', data)
export const captureS2S = (data) => api.post('/api/checkout/s2s', data)
export const verifyPayment = (data) => api.post('/api/checkout/verify', data)
export const syncShopify = (data) => api.post('/api/shopify/sync', data)
export const getOrders = (limit = 5) => api.get(`/api/shopify/orders?limit=${limit}`)
export const getLedger = () => api.get('/api/ledger')
export const clearLedger = () => api.delete('/api/ledger')
export const getRazorpayKey = () => api.get('/api/razorpay-key')
