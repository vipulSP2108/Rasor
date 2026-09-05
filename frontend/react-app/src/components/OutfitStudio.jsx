import React, { useState, useRef, useEffect } from 'react'
import { 
  Send, Trash2, Mic, MicOff, Volume2, VolumeX, Sparkles, User, Bot, 
  RotateCcw, RefreshCw, Plus, X, Layers, ShoppingBag,
  Columns, Layout, MessageSquare, ArrowUpRight, ArrowLeft, ChevronDown, ChevronUp
} from 'lucide-react'
import { coordinateBundle, matchOutfit, extractGarmentImage } from '../api/client'
import { useApp } from '../context/AppContext'
import { useVoice } from '../hooks/useVoice'
import InteractiveOutfitSuite, { getProductImageUrl } from './InteractiveOutfitSuite'
import toast from 'react-hot-toast'

const OWNED_STAPLES = {
  "Heavyweight Olive Green Hoodie": {
    category: "hoodie",
    color: "Olive Green",
    fit: "Oversized Fit",
    description: "Heavyweight Olive Green Fleece Hoodie",
    thumb: "https://images.unsplash.com/photo-1556905055-8f358a7a47b2?auto=format&fit=crop&w=800&q=80",
    image_url: "https://images.unsplash.com/photo-1556905055-8f358a7a47b2?auto=format&fit=crop&w=800&q=80"
  },
  "Crisp White Boxy Tee": {
    category: "t-shirt",
    color: "White",
    fit: "Boxy Fit",
    description: "Crisp White Heavyweight Boxy T-Shirt",
    thumb: "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=800&q=80",
    image_url: "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=800&q=80"
  },
  "Classic Jet Black Denim Jacket": {
    category: "jacket",
    color: "Black",
    fit: "Regular Fit",
    description: "Classic Jet Black Denim Jacket",
    thumb: "https://images.unsplash.com/photo-1551028719-00167b16eac5?auto=format&fit=crop&w=800&q=80",
    image_url: "https://images.unsplash.com/photo-1551028719-00167b16eac5?auto=format&fit=crop&w=800&q=80"
  },
  "Baggy Charcoal Sweatpants": {
    category: "joggers",
    color: "Charcoal",
    fit: "Baggy Fit",
    description: "Baggy Charcoal Fleece Sweatpant Joggers",
    thumb: "https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?auto=format&fit=crop&w=800&q=80",
    image_url: "https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?auto=format&fit=crop&w=800&q=80"
  }
}

export default function OutfitStudio({ onAddToCart, onAutonomousCheckout, onNavigate }) {
  const { config, userProfile, 
    studioMessages: messages, setStudioMessages: setMessages,
    studioMode, setStudioMode,
    studioViewportMode: viewportMode, setStudioViewportMode: setViewportMode,
    studioActiveStageBundle: activeStageBundle, setStudioActiveStageBundle: setActiveStageBundle,
    studioExpandedLooks: expandedLooks, setStudioExpandedLooks: setExpandedLooks,
    addToCartLocal, clearCart
  } = useApp()

  // Voice mode auto tracking

  const [input, setInput] = useState('')
  const [isCoordinating, setIsCoordinating] = useState(false)
  const [speakingIdx, setSpeakingIdx] = useState(null)
  const [isAutoVoice, setIsAutoVoice] = useState(false)

  // Multi-Turn Onboarding State Machine
  const [pendingIntent, setPendingIntent] = useState(null)

  // Stage Canvas Modal Overlay State
  const [stageModalData, setStageModalData] = useState(null)

  // Escape key listener for Stage Modal
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && stageModalData) {
        setStageModalData(null)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [stageModalData])

  // Voice recognition & synthesis
  const { 
    isListening, transcript, startListening, stopListening, 
    speak, speakAsync, stopSpeaking, resetTranscript 
  } = useVoice()

  // Track index of latest message that contains a coordinated bundle
  const latestBundleMsgIdx = React.useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].bundleData) return i
    }
    return -1
  }, [messages])

  // Owned garment attachment
  const [attachment, setAttachment] = useState(null)
  const [isExtractingAttachment, setIsExtractingAttachment] = useState(false)

  const endRef = useRef(null)
  const inputRef = useRef(null)
  const fileInputRef = useRef(null)

  // Sync live voice transcript into input
  useEffect(() => {
    if (transcript) setInput(transcript)
  }, [transcript])

  // Auto-send when voice stops and has transcript
  useEffect(() => {
    const textToSend = input.trim() || transcript.trim()
    if (!isListening && textToSend && transcript) {
      handleSendMessage(textToSend)
      resetTranscript()
    }
  }, [isListening, transcript, input])

  // Auto-scroll
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isCoordinating])

  // Switch between 'bundle' and 'match' modes
  const handleSwitchMode = (newMode) => {
    if (newMode === studioMode) return
    setStudioMode(newMode)
    setAttachment(null)

    if (newMode === 'match') {
      const matchIntro = {
        id: 'msg-' + Date.now(),
        role: 'assistant',
        content: "🧷 **Match My Outfit Mode**: Tap the **`+`** button beside the chat box to upload a photo of your owned garment, or select an owned staple below. I'll evaluate CIELAB color harmony to find complementary matches!",
        suggestedOptions: [
          "Heavyweight Olive Green Hoodie",
          "Crisp White Boxy Tee",
          "Classic Jet Black Denim Jacket",
          "Baggy Charcoal Sweatpants"
        ],
        voiceEnabled: true
      }
      setMessages(prev => [...prev, matchIntro])
    } else {
      const bundleIntro = {
        id: 'msg-' + Date.now(),
        role: 'assistant',
        content: "✨ **Multi-Piece Looks Mode**: Tell or speak to me what complete outfit look you'd like to put together (e.g. *\"I want 2 uppers and 1 lower under 3k\"* or *\"Give me 2 shirts\"*). If metrics are missing, I'll ask you!",
        suggestedOptions: [
          "I want 2 uppers and 1 lower under 3k",
          "Give me 2 shirts",
          "Olive hoodie and black joggers under 2500",
          "Vintage graphic tee + denim jeans"
        ],
        voiceEnabled: true
      }
      setMessages(prev => [...prev, bundleIntro])
    }
  }

  // Handle file attachment (+)
  const handleAttachmentFile = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    const reader = new FileReader()
    reader.onload = async (event) => {
      const b64 = event.target.result
      setIsExtractingAttachment(true)
      const toastId = toast.loading('Extracting garment attributes with Vision AI…')

      try {
        const rawB64 = b64.split(',')[1] || b64
        const res = await extractGarmentImage({
          image_b64: rawB64,
          mime_type: file.type || 'image/jpeg'
        })
        const data = res.data
        const attObj = {
          thumb: b64,
          image_url: b64,
          category: data.category || 'hoodie',
          color: data.color || 'Olive Green',
          fit: data.fit || 'Regular Fit',
          description: data.visual_description || `${data.color} ${data.category}`
        }
        setAttachment(attObj)
        setStudioMode('match')
        if (!input.trim()) {
          setInput(`What matches with my ${attObj.color} ${attObj.category}?`)
        }
        toast.success(`Identified: ${attObj.color} ${attObj.category}`, { id: toastId })
      } catch (err) {
        console.error('Vision extraction error:', err)
        toast.dismiss(toastId)
        toast.error('Could not auto-extract garment. You can describe it in your chat prompt!')
      } finally {
        setIsExtractingAttachment(false)
      }
    }
    reader.readAsDataURL(file)
  }

  // Robust budget extractor handling commas (e.g. 1,500 -> 1500) and abbreviations (3k -> 3000)
  const extractBudgetFromText = (text) => {
    if (!text) return null
    const clean = text.replace(/,/g, '') // Strip commas
    const kMatch = clean.match(/\b(\d+(?:\.\d+)?)\s*k\b/i)
    if (kMatch) {
      return Math.round(parseFloat(kMatch[1]) * 1000)
    }
    const numMatch = clean.match(/(?:under|below|budget|within|max|<|<=|rs\.?|inr|₹)\s*(\d{3,5})/i) || clean.match(/\b(\d{3,5})\s*(?:rs|inr|rupees)?\b/i)
    if (numMatch) {
      const val = parseInt(numMatch[1], 10)
      if (val >= 300 && val <= 50000) return val
    }
    return null
  }

  // Check if query or look involves both upper and lower garments
  const checkHasUpperAndLower = (text) => {
    if (!text) return false
    const t = text.toLowerCase()
    const hasUpper = /\b(upper|top|shirt|t-shirt|tee|hoodie|jacket|sweatshirt|polo|overshirt)\b/i.test(t)
    const hasLower = /\b(lower|bottom|pant|pants|jogger|joggers|jean|jeans|trouser|trousers|short|shorts|sweatpant|sweatpants|cargo|cargos)\b/i.test(t)
    const isOutfit = /\b(outfit|look|combo|pair|set)\b/i.test(t)
    const isVagueTwoUppers = /\b(?:2|two)\s*(?:uppers?|tops?|shirts?)\b/i.test(t)
    if (isVagueTwoUppers) return false
    if (hasUpper && hasLower) return true
    if (isOutfit) return true
    if (t.includes('+') || t.includes(' and ')) {
      if (hasUpper || hasLower) return true
    }
    return false
  }

  // Parse upper and lower sizes independently from user response
  const parseUpperAndLowerSizes = (text) => {
    if (!text) return { upperSize: null, lowerSize: null }
    const t = text.toLowerCase()

    let upperSize = null
    let lowerSize = null

    // 1. Explicit upper size patterns (e.g., "upper: L", "upper L", "XL for upper", "XL for tshirt", "size xl for hoodie")
    const upperMatch = t.match(/(?:upper|top|t-shirt|tee|shirt|hoodie|jacket)\s*(?:is|size|:)?\s*([a-z0-9]+)/i) 
      || t.match(/([a-z0-9]+)\s*(?:for\s*(?:the\s*)?(?:upper|top|t-shirt|tee|shirt|hoodie|jacket))/i)
    
    if (upperMatch) {
      const val = upperMatch[1].toUpperCase()
      if (['XS', 'S', 'M', 'L', 'XL', '2XL', 'XXL', '3XL'].includes(val)) {
        upperSize = val
      }
    }

    // 2. Explicit lower size patterns (e.g., "lower: 32", "lower 32", "32 for lower", "32 waist", "size 32 for pants")
    const lowerMatch = t.match(/(?:lower|bottom|waist|pants?|joggers?|jeans?)\s*(?:is|size|:)?\s*([a-z0-9]+)/i)
      || t.match(/([a-z0-9]+)\s*(?:for\s*(?:the\s*)?(?:lower|bottom|waist|pants?|joggers?|jeans?))/i)
      || t.match(/\b([234]\d)\s*(?:waist|inch)?\b/i)

    if (lowerMatch) {
      const val = lowerMatch[1].toUpperCase()
      if (['28', '30', '32', '34', '36', '38', 'S', 'M', 'L', 'XL'].includes(val)) {
        lowerSize = val
      }
    }

    // 3. Combined chip pattern e.g. "Upper L • Lower 32" or "L and 32"
    const comboMatch = t.match(/\b(xs|s|m|l|xl|2xl|xxl|3xl)\b.*?\b(28|30|32|34|36|38)\b/i)
    if (comboMatch) {
      if (!upperSize) upperSize = comboMatch[1].toUpperCase()
      if (!lowerSize) lowerSize = comboMatch[2]
    }

    // 4. Reversed combined pattern e.g. "32 and L"
    const revComboMatch = t.match(/\b(28|30|32|34|36|38)\b.*?\b(xs|s|m|l|xl|2xl|xxl|3xl)\b/i)
    if (revComboMatch) {
      if (!lowerSize) lowerSize = revComboMatch[1]
      if (!upperSize) upperSize = revComboMatch[2].toUpperCase()
    }

    // 5. Standalone alpha size fallback (if not waist)
    if (!upperSize) {
      const standaloneAlpha = t.match(/\b(xs|s|m|l|xl|2xl|xxl|3xl)\b/i)
      if (standaloneAlpha && !t.includes('waist') && !t.includes('lower') && !t.includes('bottom') && !t.includes('pant') && !t.includes('jogger')) {
        upperSize = standaloneAlpha[1].toUpperCase()
      }
    }

    // 6. Standalone waist number fallback
    if (!lowerSize) {
      const standaloneWaist = t.match(/\b(28|30|32|34|36|38)\b/i)
      if (standaloneWaist) {
        lowerSize = standaloneWaist[1]
      }
    }

    return { upperSize, lowerSize }
  }

  // ── Dynamic Stylist Speech & Random Phrasing Helpers ──
  const pickRandom = (arr) => arr[Math.floor(Math.random() * arr.length)]

  const getBudgetPrompt = (isVagueTwoUppers) => {
    if (isVagueTwoUppers) {
      return pickRandom([
        "Great! To coordinate the best 2 uppers for you, what total budget would you like to stay under?",
        "Love the layered direction! What total budget should we work with for these two uppers?",
        "Awesome idea! What total price limit would you like me to keep both uppers under?"
      ])
    }
    return pickRandom([
      "Love it! What total budget would you like to stay under?",
      "Sounds stylish! Do you have a target budget in mind?",
      "Love the vision! What total budget are you aiming to stay under?",
      "I'm on it! What price limit would you like me to keep this under?",
      "Let's build something sharp! What total budget should we work with?"
    ])
  }

  const getTwoPieceSizePrompt = (budgetDesc) => {
    return pickRandom([
      `Sweet, keeping it ${budgetDesc}! What size do you prefer for your upper (e.g., M, L, XL) and what waist size for your lower (e.g., 30, 32, 34 waist)?`,
      `Locked in ${budgetDesc}! How would you like your upper sized (e.g. M, L, XL) and what waist size for the lower?`,
      `Got it, dialing in for ${budgetDesc}! Let me know your preferred upper size (M, L, XL) and lower waist size (e.g., 30, 32, 34).`,
      `Perfect, staying within ${budgetDesc}! What upper size and lower waist size feel best on you?`
    ])
  }

  const getSinglePieceSizePrompt = (budgetDesc) => {
    return pickRandom([
      `Sweet, keeping it ${budgetDesc}! What size and fit do you prefer for these?`,
      `Locked in ${budgetDesc}! What size and fit cut (e.g., Regular, Relaxed, Oversized) do you rock?`,
      `Got it, comfortably ${budgetDesc}! What size and fit profile should we aim for?`,
      `Love it, dialed in ${budgetDesc}! What's your go-to size and fit?`
    ])
  }

  const getLowerFollowupPrompt = (upperSize) => {
    return pickRandom([
      `Got it, ${upperSize} for your upper! And what waist size or fit do you prefer for your lower (e.g. 30, 32, 34 waist)?`,
      `Noted, ${upperSize} on top! What waist size or cut works best for your lower half?`,
      `Locked in ${upperSize} for the upper! And how should we size your lower (e.g. 30, 32, 34 waist)?`
    ])
  }

  const getUpperFollowupPrompt = (lowerSize) => {
    return pickRandom([
      `Got it, ${lowerSize} for your lower! And what size do you prefer for your upper (e.g., M, L, XL)?`,
      `Noted, ${lowerSize} on bottom! What upper size should I grab for you (e.g., S, M, L, XL)?`,
      `Locked in ${lowerSize} for the lower! What upper size fits you best?`
    ])
  }

  const getCoordinationSuccessPrompt = (targetBudget, topSizeSpec, bottomSizeSpec) => {
    if (topSizeSpec && bottomSizeSpec) {
      return pickRandom([
        `✨ Coordinated complete looks for you (Upper ${topSizeSpec}, Lower ${bottomSizeSpec}) within ₹${targetBudget}!`,
        `✨ Calibrated sharp coordinated looks for you (Upper ${topSizeSpec}, Lower ${bottomSizeSpec}) under ₹${targetBudget}!`,
        `✨ Here are stylist-approved looks (Upper ${topSizeSpec}, Lower ${bottomSizeSpec}) tailored under ₹${targetBudget}!`
      ])
    }
    return pickRandom([
      `✨ Coordinated complete looks for you within ₹${targetBudget}!`,
      `✨ Crafted balanced, stylist-approved looks within your ₹${targetBudget} budget!`,
      `✨ Here are high-harmony coordinated outfits tailored under ₹${targetBudget}!`,
      `✨ Curated your looks with color-science harmony under ₹${targetBudget}!`
    ])
  }

  // Send message
  const handleSendMessage = async (textToSend) => {
    const rawText = (textToSend || input).trim()
    if (!rawText && !attachment) return

    stopListening()
    const activeAttachment = attachment
    setAttachment(null)
    setInput('')
    resetTranscript()

    // Check if user selected one of our staple presets
    let currentOwned = activeAttachment
    if (OWNED_STAPLES[rawText]) {
      currentOwned = OWNED_STAPLES[rawText]
      setStudioMode('match')
    }

    const userMsg = {
      id: 'usr-' + Date.now(),
      role: 'user',
      content: rawText,
      attachment: currentOwned,
    }

    setMessages(prev => [...prev, userMsg])
    setIsCoordinating(true)

    const lowerText = rawText.toLowerCase()
    const extractedBudget = extractBudgetFromText(rawText)

    // ── 0. Conversational Autonomous Purchase Handler (e.g. "🛒 Buy Combo #1", "Buy Combo 1", "1-Click Buy") ──
    const isBuyIntent = /\b(buy|order|purchase|checkout|1-click|one-click)\b/i.test(lowerText)
    if (isBuyIntent) {
      setPendingIntent(null)
      setIsCoordinating(false)

      const latestLookMsg = [...messages].reverse().find(m => m.bundleData)
      if (!latestLookMsg) {
        setMessages(prev => [...prev, {
          id: 'asst-' + Date.now(),
          role: 'assistant',
          content: "There's no active outfit look to buy yet! Tell or speak to me what outfit you'd like to put together first.",
          suggestedOptions: [
            "I want 2 uppers and 1 lower under 3k",
            "Give me 2 shirts under 2000",
            "Olive hoodie and black joggers under 2500"
          ],
          voiceEnabled: true
        }])
        return
      }

      const bData = latestLookMsg.bundleData
      const comboMatch = rawText.match(/combo\s*#?\s*(\d+)/i) || rawText.match(/(?:look|option|outfit)\s*#?\s*(\d+)/i)
      const comboNum = comboMatch ? parseInt(comboMatch[1], 10) : 1

      // Compile combos list matching MultiBundleCoordinatorView
      const combosList = []
      if (bData.hero_bundle) {
        combosList.push(bData.hero_bundle)
      }
      if (bData.combos && Array.isArray(bData.combos)) {
        bData.combos.forEach(c => {
          if (c.bundle && !combosList.includes(c.bundle)) combosList.push(c.bundle)
        })
      }
      if (bData.candidate_bundles && Array.isArray(bData.candidate_bundles)) {
        bData.candidate_bundles.forEach(cb => {
          if (!combosList.includes(cb)) combosList.push(cb)
        })
      }
      if (combosList.length === 0) {
        combosList.push(bData)
      }

      const targetBundle = (comboNum > 0 && comboNum <= combosList.length)
        ? combosList[comboNum - 1]
        : (combosList[0] || bData.hero_bundle || bData)

      let targetItems = []
      if (bData.mode === 'match' || latestLookMsg.ownedItem) {
        const matchedProd = bData.top_recommendation?.product || bData.matched_results?.[0]?.product
        if (matchedProd) targetItems = [matchedProd]
      } else {
        targetItems = targetBundle.items || [targetBundle]
      }

      if (targetItems.length === 0) {
        toast.error('No items found in this outfit look to purchase.')
        return
      }

      const detectedSizeMatch = rawText.match(/\b(xs|s|m|l|xl|2xl|3xl|xxl|xxxl)\b/i)
      const detectedSize = detectedSizeMatch ? detectedSizeMatch[1].toUpperCase() : null

      // Clear existing cart and add all bundle pieces
      if (clearCart) clearCart()
      const addedTitles = []
      let grandTotal = 0

      targetItems.forEach((item, idx) => {
        if (!item) return
        let pieceSize = detectedSize || item.selectedSize
        if (!pieceSize) {
          if (idx === 0) pieceSize = bData.initialTopSize || userProfile?.defaultSize || 'L'
          else if (idx === 1) pieceSize = bData.initialBottomSize || '32'
          else pieceSize = userProfile?.defaultSize || 'L'
        }
        const piecePrice = item.price || 0
        grandTotal += piecePrice

        const vids = item.specs?.variant_ids || {}
        const variantId = vids[pieceSize] || Object.values(vids)[0] || `gid://shopify/ProductVariant/${item.id || idx}`

        const itemWithMeta = {
          ...item,
          selectedSize: pieceSize,
          cart_id: `cart_${Date.now()}_${idx}`,
          variant_gid: variantId
        }

        if (onAddToCart) {
          onAddToCart(itemWithMeta)
        } else if (addToCartLocal) {
          addToCartLocal(item, 1, {
            cart_id: `cart_${Date.now()}_${idx}`,
            variant_gid: variantId,
            size: pieceSize
          })
        }
        addedTitles.push(`"${item.title?.slice(0, 26) || item.category || 'Piece'}" (${pieceSize})`)
      })

      const buySpeech = `Added Combo ${comboNum} to your cart. Initiating autonomous Multi-Rail Failover checkout now.`
      toast.success(`🛒 Auto-Added Combo #${comboNum} to Cart (Total: ₹${grandTotal})!`, { duration: 5000, icon: '⚡' })

      const buyMsg = {
        id: 'asst-' + Date.now(),
        role: 'assistant',
        content: `🛒 **Initiating Autonomous 1-Click Checkout for Combo #${comboNum}**!\n\n• **Items Added:** ${addedTitles.join(' + ')}\n• **Total Price:** ₹${grandTotal} (within budget cap)\n\nTransferring to **Autonomous Multi-Rail Failover Checkout** now... ⚡`,
        voiceEnabled: true
      }
      setMessages(prev => [...prev, buyMsg])

      if (config.voiceEnabled) {
        speakAsync(buySpeech, { category: 'aiChat', voiceURI: config.voiceURI }).catch(() => {})
      }

      setTimeout(() => {
        onAutonomousCheckout?.({ mode: 'cascade_failover', autoStart: true })
      }, 500)
      return
    }

    // ── 0.1 Next Best Combo Quick Switch Handler (e.g. "🔄 Next Best Combo") ──
    if (/\b(next\s*best\s*combo|next\s*combo|swap\s*both)\b/i.test(lowerText)) {
      setPendingIntent(null)
      setIsCoordinating(false)
      const latestLook = [...messages].reverse().find(m => m.bundleData)
      if (latestLook) {
        setStageModalData({
          bundleData: latestLook.bundleData,
          ownedItem: latestLook.ownedItem,
          title: 'Next Best Combo'
        })
        setMessages(prev => [...prev, {
          id: 'asst-' + Date.now(),
          role: 'assistant',
          content: "⚡ Switched to **Stage Canvas Modal** for exploring next best combinations! Use the **Next Best Combo** / **Prev Combo** buttons to flip through pairs within your budget.",
          suggestedOptions: ["🛒 Buy Combo #1", "🔄 Swap Lower", "🔄 Swap Upper"],
          voiceEnabled: true
        }])
      }
      return
    }

    // ── 0.15 Alternative Guidance Action Handlers (e.g. from Low-Budget Guidance Chips) ──
    const adjustBudgetMatch = rawText.match(/adjust budget to\s*₹?\s*(\d+)/i)
    if (adjustBudgetMatch) {
      setPendingIntent(null)
      const newBudget = parseInt(adjustBudgetMatch[1], 10)
      const lastLook = [...messages].reverse().find(m => m.bundleData)
      let outfitQuery = lastLook?.bundleData?.query || activeStageBundle?.title || 'shirt and joggers'
      outfitQuery = outfitQuery.replace(/categoryenum\./gi, '')
      const outfitMatch = rawText.match(/for the complete\s+(.+?)\s+outfit/i)
      if (outfitMatch) {
        outfitQuery = outfitMatch[1].replace(/&/g, 'and').replace(/categoryenum\./gi, '').trim()
      }
      return coordinateAndDisplayLook(outfitQuery, newBudget, lastLook?.bundleData?.initialTopSize || 'L', lastLook?.bundleData?.initialBottomSize || '32')
    }

    const indivMatch = rawText.match(/get a top-tier\s+(?:categoryenum\.)?([a-z\s-]+)\s+individually/i)
    if (indivMatch) {
      setPendingIntent(null)
      const cat = indivMatch[1].replace(/categoryenum\./gi, '').trim()
      const b = extractedBudget || 1500
      return coordinateAndDisplayLook(`${cat}`, b, userProfile?.defaultSize || 'L', null)
    }

    const lighterMatch = rawText.match(/switch to a lighter combo.*under\s*₹?\s*(\d+)/i)
    if (lighterMatch) {
      setPendingIntent(null)
      const b = parseInt(lighterMatch[1], 10) || extractedBudget || 1500
      return coordinateAndDisplayLook('t-shirt and shorts', b, 'L', '32')
    }

    // ── 0.16 Conversational Continuations (e.g. "continue", "proceed", "yes", "ok") ──
    const isAffirmativeOrContinue = /^(continue|proceed|next|ok|okay|yes|yeah|sure|go ahead|ready|looks good)\b/i.test(lowerText.trim())
    if (isAffirmativeOrContinue && !pendingIntent) {
      const lastLook = [...messages].reverse().find(m => m.bundleData)
      if (lastLook) {
        setIsCoordinating(false)
        const affirmMsg = {
          id: 'asst-' + Date.now(),
          role: 'assistant',
          content: pickRandom([
            "You're all set! You can tap **🛒 Buy Combo #1** to checkout immediately, use **🔄 Next Best Combo** to view alternatives, or let me know if you'd like to swap any piece.",
            "Ready whenever you are! Tap **🛒 Buy Combo #1** for 1-click checkout, or ask me to adjust colors, sizes, or budget.",
            "Everything is styled and ready! You can check out with **🛒 Buy Combo #1** or explore the pieces on stage above."
          ]),
          suggestedOptions: [
            "🛒 Buy Combo #1",
            "🔄 Next Best Combo",
            "🔄 Swap Upper",
            "🔄 Swap Lower"
          ],
          voiceEnabled: true
        }
        setMessages(prev => [...prev, affirmMsg])
        if (affirmMsg.voiceEnabled && config.voiceEnabled) {
          setSpeakingIdx(messages.length + 1)
          speakAsync(affirmMsg.content.replace(/\*\*/g, '').replace(/[🛒🔄]/g, ''), { category: 'aiChat', voiceURI: config.voiceURI }).then(() => {
            setSpeakingIdx(null)
            if (isAutoVoice) setTimeout(() => startListening(), 400)
          })
        } else if (isAutoVoice) {
          setTimeout(() => startListening(), 400)
        }
        return
      }
    }

    // ── 0.2 Conversational Refinement of Existing Look (e.g. "Swap Lower with Joggers", "Keep total under ₹2000") ──
    const latestLookMsg = [...messages].reverse().find(m => m.bundleData)
    const isTweakOrRefine = latestLookMsg && (
      lowerText.includes('swap') ||
      lowerText.includes('contrast') ||
      lowerText.includes('instead') ||
      lowerText.includes('keep total') ||
      lowerText.includes('tweak') ||
      lowerText.includes('change') ||
      lowerText.includes('adjust') ||
      lowerText.startsWith('try ')
    )

    if (isTweakOrRefine) {
      setPendingIntent(null)
      const baseLookData = latestLookMsg.bundleData
      const prevQuery = baseLookData.query || activeStageBundle?.title || 'complete outfit'
      let targetBudget = extractedBudget || baseLookData.budget || 2500

      let replyLead = `Taking your **₹${targetBudget}** budget from before`
      let synthesizedQuery = prevQuery

      // Intelligent garment swap synthesis
      const items = baseLookData.hero_bundle?.items || []
      const upperCategory = items[0]?.category || 'shirt'
      const lowerCategory = items[1]?.category || 'pants'

      if (lowerText.includes('swap lower') || lowerText.includes('swap bottom') || lowerText.includes('jogger')) {
        let replacementLower = 'joggers'
        if (lowerText.includes('jean') || lowerText.includes('denim')) replacementLower = 'denim jeans'
        else if (lowerText.includes('cargo')) replacementLower = 'cargo pants'
        else if (lowerText.includes('short')) replacementLower = 'shorts'

        synthesizedQuery = `${upperCategory} and ${replacementLower}`
        replyLead = `Got it! Taking your **₹${targetBudget}** budget from before, swapping in **${replacementLower}** for your look ✨`
      } else if (lowerText.includes('swap upper') || lowerText.includes('swap top') || lowerText.includes('hoodie')) {
        let replacementUpper = 'oversized hoodie'
        if (lowerText.includes('jacket')) replacementUpper = 'jacket'
        else if (lowerText.includes('tee') || lowerText.includes('t-shirt')) replacementUpper = 'graphic t-shirt'
        else if (lowerText.includes('shirt')) replacementUpper = 'casual shirt'

        synthesizedQuery = `${replacementUpper} and ${lowerCategory}`
        replyLead = `Got it! Taking your **₹${targetBudget}** budget from before, trying an **${replacementUpper}** for your look ✨`
      } else if (lowerText.includes('contrast')) {
        synthesizedQuery = `${prevQuery} high contrast`
        replyLead = `Taking your **₹${targetBudget}** budget from before, coordinating higher contrast styles ✨`
      } else if (lowerText.includes('keep total') || lowerText.includes('under') || extractedBudget) {
        synthesizedQuery = prevQuery
        replyLead = `Got it! Adjusted your budget cap to **₹${targetBudget}** from before. Here are the top looks ✨`
      }

      try {
        const res = await coordinateBundle({
          query: synthesizedQuery,
          budget: targetBudget,
          gender: userProfile?.gender || 'men',
          user_skin_depth: userProfile?.skinDepth || null,
          user_undertone: userProfile?.undertone || null,
          data_source: config.dataSource || 'dev'
        })

        const data = res.data
        if (baseLookData.initialTopSize) data.initialTopSize = baseLookData.initialTopSize
        if (baseLookData.initialBottomSize) data.initialBottomSize = baseLookData.initialBottomSize

        let replyContent = `${replyLead}`
        if (data.status === 'budget_too_low') {
          replyContent = data.alternatives?.message || `With your budget of ₹${targetBudget}, coordinating these pieces exceeds catalog floor prices. Here are stylist recommendations:`
        }

        const bundleMsg = {
          id: 'asst-' + Date.now(),
          role: 'assistant',
          content: replyContent,
          bundleData: data,
          suggestedOptions: data.status === 'budget_too_low' 
            ? (data.alternatives?.options || [
                `Adjust budget to ₹${data.min_total_required || 2000}`,
                "Show Best Value Options",
                "Switch to T-Shirt + Joggers"
              ]).map(o => String(o).replace(/categoryenum\./gi, ''))
            : [
                "🛒 Buy Combo #1",
                "🔄 Next Best Combo",
                "🔄 Swap Upper",
                "🔄 Swap Lower"
              ],
          voiceEnabled: true
        }
        setMessages(prev => [...prev, bundleMsg])
        setExpandedLooks({ [bundleMsg.id]: true })

        setActiveStageBundle({
          bundleData: data,
          ownedItem: null,
          title: synthesizedQuery
        })

        if (bundleMsg.voiceEnabled && config.voiceEnabled) {
          setSpeakingIdx(messages.length + 1)
          const cleanSpeech = replyContent.replace(/\*\*/g, '').replace(/[✨🎨💡🛒🔄]/g, '')
          speakAsync(cleanSpeech, { category: 'aiChat', voiceURI: config.voiceURI }).then(() => {
            setSpeakingIdx(null)
            if (isAutoVoice) setTimeout(() => startListening(), 400)
          })
        } else if (isAutoVoice) {
          setTimeout(() => startListening(), 400)
        }
      } catch (err) {
        console.error('Refine coordinate error:', err)
        toast.error('Could not refine outfit look.')
      } finally {
        setIsCoordinating(false)
      }
      return
    }

    // Helper to coordinate look with individual upper & lower size specs and budget
    const coordinateAndDisplayLook = async (baseQuery, targetBudget, topSizeSpec, bottomSizeSpec) => {
      setIsCoordinating(true)
      let cleanQuery = String(baseQuery || 'complete outfit').replace(/categoryenum\./gi, '').trim()
      let synthesizedQuery = cleanQuery
      if (topSizeSpec && bottomSizeSpec) {
        synthesizedQuery += ` upper size ${topSizeSpec} lower size ${bottomSizeSpec}`
      } else if (topSizeSpec) {
        synthesizedQuery += ` size ${topSizeSpec}`
      }

      try {
        const res = await coordinateBundle({
          query: synthesizedQuery,
          budget: targetBudget,
          gender: userProfile?.gender || 'men',
          user_skin_depth: userProfile?.skinDepth || null,
          user_undertone: userProfile?.undertone || null,
          data_source: config.dataSource || 'dev'
        })

        const data = res.data
        if (topSizeSpec) data.initialTopSize = topSizeSpec
        if (bottomSizeSpec) data.initialBottomSize = bottomSizeSpec

        let replyContent = getCoordinationSuccessPrompt(targetBudget, topSizeSpec, bottomSizeSpec)

        if (data.status === 'budget_too_low') {
          replyContent = data.alternatives?.message || `💡 With your budget of ₹${targetBudget}, coordinating these pieces exceeds catalog floor prices. Here are proactive stylist recommendations:`
        }

        const bundleMsg = {
          id: 'asst-' + Date.now(),
          role: 'assistant',
          content: replyContent,
          bundleData: data,
          suggestedOptions: data.status === 'budget_too_low' 
            ? (data.alternatives?.options || [
                `Adjust budget to ₹${data.min_total_required || 2000}`,
                "Show Best Value Options",
                "Switch to T-Shirt + Joggers"
              ]).map(o => String(o).replace(/categoryenum\./gi, ''))
            : [
                "🛒 Buy Combo #1",
                "🔄 Next Best Combo",
                "🔄 Swap Upper",
                "🔄 Swap Lower"
              ],
          voiceEnabled: true
        }

        setMessages(prev => [...prev, bundleMsg])
        // Auto-collapse older looks, keep new look expanded!
        setExpandedLooks({ [bundleMsg.id]: true })

        setActiveStageBundle({
          bundleData: data,
          ownedItem: null,
          title: synthesizedQuery
        })

        if (bundleMsg.voiceEnabled && config.voiceEnabled) {
          setSpeakingIdx(messages.length + 1)
          const cleanSpeech = replyContent.replace(/\*\*/g, '').replace(/[✨🎨💡🛒🔄]/g, '')
          speakAsync(cleanSpeech, { category: 'aiChat', voiceURI: config.voiceURI }).then(() => {
            setSpeakingIdx(null)
            if (isAutoVoice) setTimeout(() => startListening(), 400)
          })
        } else if (isAutoVoice) {
          setTimeout(() => startListening(), 400)
        }
      } catch (err) {
        console.error('Bundle coordinate error:', err)
        const errorMsg = {
          id: 'asst-' + Date.now(),
          role: 'assistant',
          content: "I had trouble coordinating that exact combination. Could you specify the items or target budget? (e.g. *'vintage graphic tee and indigo denim jeans under 2500'* or *'give me 2 shirts under 1500'*).",
          suggestedOptions: [
            "I want 2 uppers and 1 lower under 3k",
            "Give me 2 shirts under 1500",
            "Olive hoodie and joggers under 2500"
          ],
          voiceEnabled: true
        }
        setMessages(prev => [...prev, errorMsg])
      } finally {
        setIsCoordinating(false)
      }
    }

    // ── 1. Check Active Multi-Turn Clarification State Machine ──
    if (pendingIntent) {
      const isUpperAndLower = pendingIntent.isUpperAndLower || checkHasUpperAndLower(pendingIntent.baseQuery)

      if (pendingIntent.step === 'awaiting_budget') {
        const isNoLimit = /\b(no\s*limit|no\s*cap|any|unlimited|skip)\b/i.test(lowerText)
        const budgetVal = extractedBudget || (isNoLimit ? 5000 : null)

        if (budgetVal !== null) {
          setIsCoordinating(false)
          const budgetDesc = isNoLimit ? 'No Budget Cap' : `Under ₹${budgetVal}`

          if (isUpperAndLower) {
            const { upperSize, lowerSize } = parseUpperAndLowerSizes(rawText)
            if (upperSize && !lowerSize) {
              setPendingIntent({
                ...pendingIntent,
                budget: budgetVal,
                upperSize,
                step: 'awaiting_lower_size'
              })
              const clarifyMsg = {
                id: 'asst-' + Date.now(),
                role: 'assistant',
                content: getLowerFollowupPrompt(upperSize),
                suggestedOptions: ["30 Waist", "32 Waist", "34 Waist", "Any Lower Size"],
                voiceEnabled: true
              }
              setMessages(prev => [...prev, clarifyMsg])
              if (clarifyMsg.voiceEnabled && config.voiceEnabled) {
                setSpeakingIdx(messages.length + 1)
                speakAsync(clarifyMsg.content, { category: 'aiChat', voiceURI: config.voiceURI }).then(() => {
                  setSpeakingIdx(null)
                  if (isAutoVoice) setTimeout(() => startListening(), 400)
                })
              } else if (isAutoVoice) {
                setTimeout(() => startListening(), 400)
              }
              return
            } else if (lowerSize && !upperSize) {
              setPendingIntent({
                ...pendingIntent,
                budget: budgetVal,
                lowerSize,
                step: 'awaiting_upper_size'
              })
              const clarifyMsg = {
                id: 'asst-' + Date.now(),
                role: 'assistant',
                content: getUpperFollowupPrompt(lowerSize),
                suggestedOptions: ["Size M", "Size L", "Size XL", "Any Upper Size"],
                voiceEnabled: true
              }
              setMessages(prev => [...prev, clarifyMsg])
              if (clarifyMsg.voiceEnabled && config.voiceEnabled) {
                setSpeakingIdx(messages.length + 1)
                speakAsync(clarifyMsg.content, { category: 'aiChat', voiceURI: config.voiceURI }).then(() => {
                  setSpeakingIdx(null)
                  if (isAutoVoice) setTimeout(() => startListening(), 400)
                })
              } else if (isAutoVoice) {
                setTimeout(() => startListening(), 400)
              }
              return
            } else if (upperSize && lowerSize) {
              setPendingIntent(null)
              return coordinateAndDisplayLook(pendingIntent.baseQuery, budgetVal, upperSize, lowerSize)
            } else {
              setPendingIntent({
                ...pendingIntent,
                budget: budgetVal,
                step: 'awaiting_specs'
              })
              const clarifyMsg = {
                id: 'asst-' + Date.now(),
                role: 'assistant',
                content: getTwoPieceSizePrompt(budgetDesc),
                suggestedOptions: [
                  "Upper L • Lower 32",
                  "Upper M • Lower 30",
                  "Upper XL • Lower 34",
                  "Any Size & Fit"
                ],
                voiceEnabled: true
              }
              setMessages(prev => [...prev, clarifyMsg])
              if (clarifyMsg.voiceEnabled && config.voiceEnabled) {
                setSpeakingIdx(messages.length + 1)
                speakAsync(clarifyMsg.content, { category: 'aiChat', voiceURI: config.voiceURI }).then(() => {
                  setSpeakingIdx(null)
                  if (isAutoVoice) setTimeout(() => startListening(), 400)
                })
              } else if (isAutoVoice) {
                setTimeout(() => startListening(), 400)
              }
              return
            }
          } else {
            setPendingIntent({
              ...pendingIntent,
              budget: budgetVal,
              step: 'awaiting_specs'
            })
            const clarifyMsg = {
              id: 'asst-' + Date.now(),
              role: 'assistant',
              content: getSinglePieceSizePrompt(budgetDesc),
              suggestedOptions: [
                "Size L • Oversized",
                "Size M • Regular Fit",
                "Size XL • Relaxed",
                "Any Size & Fit"
              ],
              voiceEnabled: true
            }
            setMessages(prev => [...prev, clarifyMsg])
            if (clarifyMsg.voiceEnabled && config.voiceEnabled) {
              setSpeakingIdx(messages.length + 1)
              speakAsync(clarifyMsg.content, { category: 'aiChat', voiceURI: config.voiceURI }).then(() => {
                setSpeakingIdx(null)
                if (isAutoVoice) setTimeout(() => startListening(), 400)
              })
            } else if (isAutoVoice) {
              setTimeout(() => startListening(), 400)
            }
            return
          }
        }
      } else if (pendingIntent.step === 'awaiting_specs') {
        const isAny = /\b(any|skip|whatever|fine|default)\b/i.test(lowerText)
        const finalBudget = pendingIntent.budget || 3000

        if (isUpperAndLower) {
          const { upperSize, lowerSize } = parseUpperAndLowerSizes(rawText)

          // If user specifically provided upper size only (e.g. "I want xl for tshirt", "XL", "XL for upper")
          if (upperSize && !lowerSize && !isAny) {
            setIsCoordinating(false)
            setPendingIntent({
              ...pendingIntent,
              upperSize,
              step: 'awaiting_lower_size'
            })
            const clarifyMsg = {
              id: 'asst-' + Date.now(),
              role: 'assistant',
              content: getLowerFollowupPrompt(upperSize),
              suggestedOptions: [
                "30 Waist",
                "32 Waist",
                "34 Waist",
                "Any Lower Size"
              ],
              voiceEnabled: true
            }
            setMessages(prev => [...prev, clarifyMsg])
            if (clarifyMsg.voiceEnabled && config.voiceEnabled) {
              setSpeakingIdx(messages.length + 1)
              speakAsync(clarifyMsg.content, { category: 'aiChat', voiceURI: config.voiceURI }).then(() => {
                setSpeakingIdx(null)
                if (isAutoVoice) setTimeout(() => startListening(), 400)
              })
            } else if (isAutoVoice) {
              setTimeout(() => startListening(), 400)
            }
            return
          }

          // If user specifically provided lower size only (e.g. "32 waist", "32")
          if (lowerSize && !upperSize && !isAny) {
            setIsCoordinating(false)
            setPendingIntent({
              ...pendingIntent,
              lowerSize,
              step: 'awaiting_upper_size'
            })
            const clarifyMsg = {
              id: 'asst-' + Date.now(),
              role: 'assistant',
              content: getUpperFollowupPrompt(lowerSize),
              suggestedOptions: [
                "Size M",
                "Size L",
                "Size XL",
                "Any Upper Size"
              ],
              voiceEnabled: true
            }
            setMessages(prev => [...prev, clarifyMsg])
            if (clarifyMsg.voiceEnabled && config.voiceEnabled) {
              setSpeakingIdx(messages.length + 1)
              speakAsync(clarifyMsg.content, { category: 'aiChat', voiceURI: config.voiceURI }).then(() => {
                setSpeakingIdx(null)
                if (isAutoVoice) setTimeout(() => startListening(), 400)
              })
            } else if (isAutoVoice) {
              setTimeout(() => startListening(), 400)
            }
            return
          }

          const finalUpper = upperSize || userProfile?.defaultSize || 'L'
          const finalLower = lowerSize || '32'
          setPendingIntent(null)
          return coordinateAndDisplayLook(pendingIntent.baseQuery, finalBudget, finalUpper, finalLower)
        } else {
          const szMatch = rawText.match(/\b(xs|s|m|l|xl|xxl|2xl|3xl)\b/i)
          const chosenSize = szMatch ? szMatch[1].toUpperCase() : (userProfile?.defaultSize || 'L')
          setPendingIntent(null)
          return coordinateAndDisplayLook(pendingIntent.baseQuery, finalBudget, chosenSize, null)
        }
      } else if (pendingIntent.step === 'awaiting_lower_size') {
        const { lowerSize } = parseUpperAndLowerSizes(rawText)
        const finalLower = lowerSize || (rawText.match(/\b(28|30|32|34|36|38)\b/)?.[1]) || '32'
        const finalUpper = pendingIntent.upperSize || 'L'
        const finalBudget = pendingIntent.budget || 3000
        setPendingIntent(null)
        return coordinateAndDisplayLook(pendingIntent.baseQuery, finalBudget, finalUpper, finalLower)
      } else if (pendingIntent.step === 'awaiting_upper_size') {
        const { upperSize } = parseUpperAndLowerSizes(rawText)
        const finalUpper = upperSize || (rawText.match(/\b(xs|s|m|l|xl|2xl|xxl|3xl)\b/i)?.[1]?.toUpperCase()) || 'L'
        const finalLower = pendingIntent.lowerSize || '32'
        const finalBudget = pendingIntent.budget || 3000
        setPendingIntent(null)
        return coordinateAndDisplayLook(pendingIntent.baseQuery, finalBudget, finalUpper, finalLower)
      }
    }

    // ── 2. Check Match My Outfit Mode / Active Owned Garment ──
    const activeAnchor = currentOwned || messages.find(m => m.attachment)?.attachment
    if (activeAnchor && (studioMode === 'match' || lowerText.includes('match') || lowerText.includes('pair') || Boolean(activeAttachment))) {
      try {
        let targetCat = 'joggers'
        if (lowerText.includes('jean') || lowerText.includes('denim')) targetCat = 'jeans'
        else if (lowerText.includes('hoodie')) targetCat = 'hoodie'
        else if (lowerText.includes('shirt') || lowerText.includes('tee')) targetCat = 't-shirt'
        else if (lowerText.includes('shoe') || lowerText.includes('slider') || lowerText.includes('footwear')) targetCat = 'footwear'

        const res = await matchOutfit({
          owned_item: {
            category: activeAnchor.category,
            color: activeAnchor.color,
            fit: activeAnchor.fit,
            description: activeAnchor.description,
            image_url: activeAnchor.thumb || activeAnchor.image_url
          },
          target_category: targetCat,
          budget: extractedBudget || 2500,
          gender: userProfile?.gender || 'men',
          user_skin_depth: userProfile?.skinDepth || null,
          user_undertone: userProfile?.undertone || null,
          data_source: config.dataSource || 'dev'
        })

        const matchMsg = {
          id: 'asst-' + Date.now(),
          role: 'assistant',
          content: `✨ Found complementary catalog pieces that aesthetically harmonize with your **${activeAnchor.description || activeAnchor.color + ' ' + activeAnchor.category}** using CIELAB color theory!`,
          bundleData: res.data,
          ownedItem: activeAnchor,
          suggestedOptions: [
            "Show Denim Jeans matches",
            "Show Joggers matches",
            "Under ₹1,500",
            "I want 2 uppers and 1 lower under 3k"
          ],
          voiceEnabled: true
        }
        setMessages(prev => [...prev, matchMsg])

        setActiveStageBundle({
          bundleData: res.data,
          ownedItem: activeAnchor,
          title: `Matched: ${activeAnchor.color || ''} ${activeAnchor.category || ''}`
        })

        if (matchMsg.voiceEnabled && config.voiceEnabled) {
          setSpeakingIdx(messages.length + 1)
          speakAsync(matchMsg.content, { category: 'aiChat', voiceURI: config.voiceURI }).then(() => {
            setSpeakingIdx(null)
            if (isAutoVoice) setTimeout(() => startListening(), 400)
          })
        } else if (isAutoVoice) {
          setTimeout(() => startListening(), 400)
        }
      } catch (err) {
        console.error('Outfit match error:', err)
        toast.error('Failed to coordinate match for your garment.')
      } finally {
        setIsCoordinating(false)
      }
      return
    }

    // ── 3. Missing Metric Detection & Multi-Turn Clarification ──
    const hasAnyBudget = extractedBudget !== null || /\b(no\s*limits?|no\s*cap|any\s*budget)\b/i.test(lowerText)
    const isUpperAndLower = checkHasUpperAndLower(rawText)
    const { upperSize: extractedUpper, lowerSize: extractedLower } = parseUpperAndLowerSizes(rawText)
    const isVagueTwoUppers = /\b(?:2|two)\s*(?:uppers?|tops?)\b/i.test(lowerText)

    // Step 1: If budget is missing: ask budget (sweet and on the point)
    if (!hasAnyBudget) {
      setIsCoordinating(false)
      setPendingIntent({
        baseQuery: rawText,
        budget: null,
        isUpperAndLower,
        upperSize: extractedUpper,
        lowerSize: extractedLower,
        step: 'awaiting_budget'
      })

      let clarifyContent = getBudgetPrompt(isVagueTwoUppers)
      let opts = ["Under ₹1,500", "Under ₹2,000", "Under ₹3,000", "No Budget Cap"]

      if (isVagueTwoUppers) {
        opts = [
          "Layered: Hoodie + T-shirt under 2500",
          "Jacket + T-shirt under 3000",
          "Two Casual Shirts under 2000",
          "No Budget Cap"
        ]
      }

      const clarifyMsg = {
        id: 'asst-' + Date.now(),
        role: 'assistant',
        content: clarifyContent,
        suggestedOptions: opts,
        voiceEnabled: true
      }
      setMessages(prev => [...prev, clarifyMsg])

      if (clarifyMsg.voiceEnabled && config.voiceEnabled) {
        setSpeakingIdx(messages.length + 1)
        speakAsync(clarifyMsg.content, { category: 'aiChat', voiceURI: config.voiceURI }).then(() => {
          setSpeakingIdx(null)
          if (isAutoVoice) setTimeout(() => startListening(), 400)
        })
      } else if (isAutoVoice) {
        setTimeout(() => startListening(), 400)
      }
      return
    }

    // Step 2: If budget is present:
    const targetBudget = extractedBudget || 3000

    if (isUpperAndLower) {
      if (extractedUpper && !extractedLower) {
        setIsCoordinating(false)
        setPendingIntent({
          baseQuery: rawText,
          budget: targetBudget,
          isUpperAndLower: true,
          upperSize: extractedUpper,
          step: 'awaiting_lower_size'
        })
        const clarifyMsg = {
          id: 'asst-' + Date.now(),
          role: 'assistant',
          content: getLowerFollowupPrompt(extractedUpper),
          suggestedOptions: ["30 Waist", "32 Waist", "34 Waist", "Any Lower Size"],
          voiceEnabled: true
        }
        setMessages(prev => [...prev, clarifyMsg])
        if (clarifyMsg.voiceEnabled && config.voiceEnabled) {
          setSpeakingIdx(messages.length + 1)
          speakAsync(clarifyMsg.content, { category: 'aiChat', voiceURI: config.voiceURI }).then(() => {
            setSpeakingIdx(null)
            if (isAutoVoice) setTimeout(() => startListening(), 400)
          })
        } else if (isAutoVoice) {
          setTimeout(() => startListening(), 400)
        }
        return
      }

      if (extractedLower && !extractedUpper) {
        setIsCoordinating(false)
        setPendingIntent({
          baseQuery: rawText,
          budget: targetBudget,
          isUpperAndLower: true,
          lowerSize: extractedLower,
          step: 'awaiting_upper_size'
        })
        const clarifyMsg = {
          id: 'asst-' + Date.now(),
          role: 'assistant',
          content: getUpperFollowupPrompt(extractedLower),
          suggestedOptions: ["Size M", "Size L", "Size XL", "Any Upper Size"],
          voiceEnabled: true
        }
        setMessages(prev => [...prev, clarifyMsg])
        if (clarifyMsg.voiceEnabled && config.voiceEnabled) {
          setSpeakingIdx(messages.length + 1)
          speakAsync(clarifyMsg.content, { category: 'aiChat', voiceURI: config.voiceURI }).then(() => {
            setSpeakingIdx(null)
            if (isAutoVoice) setTimeout(() => startListening(), 400)
          })
        } else if (isAutoVoice) {
          setTimeout(() => startListening(), 400)
        }
        return
      }

      if (!extractedUpper && !extractedLower && !/\b(any|skip|just\s*show)\b/i.test(lowerText)) {
        setIsCoordinating(false)
        setPendingIntent({
          baseQuery: rawText,
          budget: targetBudget,
          isUpperAndLower: true,
          step: 'awaiting_specs'
        })
        const clarifyMsg = {
          id: 'asst-' + Date.now(),
          role: 'assistant',
          content: getTwoPieceSizePrompt(`under ₹${targetBudget}`),
          suggestedOptions: [
            "Upper L • Lower 32",
            "Upper M • Lower 30",
            "Upper XL • Lower 34",
            "Any Size & Fit"
          ],
          voiceEnabled: true
        }
        setMessages(prev => [...prev, clarifyMsg])
        if (clarifyMsg.voiceEnabled && config.voiceEnabled) {
          setSpeakingIdx(messages.length + 1)
          speakAsync(clarifyMsg.content, { category: 'aiChat', voiceURI: config.voiceURI }).then(() => {
            setSpeakingIdx(null)
            if (isAutoVoice) setTimeout(() => startListening(), 400)
          })
        } else if (isAutoVoice) {
          setTimeout(() => startListening(), 400)
        }
        return
      }

      return coordinateAndDisplayLook(rawText, targetBudget, extractedUpper || 'L', extractedLower || '32')
    } else {
      const hasSize = /\b(xs|s|m|l|xl|xxl|3xl|2xl)\b/i.test(lowerText)
      const hasFitOrColor = /\b(oversized|baggy|slim|regular|classic|black|white|navy|olive|green|blue|beige)\b/i.test(lowerText)
      if (!hasSize && !hasFitOrColor && !/\b(any|skip|just\s*show)\b/i.test(lowerText)) {
        setIsCoordinating(false)
        setPendingIntent({
          baseQuery: rawText,
          budget: targetBudget,
          isUpperAndLower: false,
          step: 'awaiting_specs'
        })
        const clarifyMsg = {
          id: 'asst-' + Date.now(),
          role: 'assistant',
          content: getSinglePieceSizePrompt(`under ₹${targetBudget}`),
          suggestedOptions: [
            "Size L • Oversized",
            "Size M • Regular Fit",
            "Size XL • Relaxed",
            "Any Size & Fit"
          ],
          voiceEnabled: true
        }
        setMessages(prev => [...prev, clarifyMsg])
        if (clarifyMsg.voiceEnabled && config.voiceEnabled) {
          setSpeakingIdx(messages.length + 1)
          speakAsync(clarifyMsg.content, { category: 'aiChat', voiceURI: config.voiceURI }).then(() => {
            setSpeakingIdx(null)
            if (isAutoVoice) setTimeout(() => startListening(), 400)
          })
        } else if (isAutoVoice) {
          setTimeout(() => startListening(), 400)
        }
        return
      }

      return coordinateAndDisplayLook(rawText, targetBudget, extractedUpper || 'L', null)
    }
  }

  const handleReset = () => {
    setMessages([
      {
        id: 'msg-init-' + Date.now(),
        role: 'assistant',
        content: "Conversation reset! What outfit look would you like to put together today? You can ask for multi-piece looks or attach an owned piece via **+**.",
        suggestedOptions: [
          "I want 2 uppers and 1 lower under 3k",
          "Give me 2 shirts",
          "Olive hoodie and joggers under 2500",
          "Vintage graphic tee + jeans"
        ],
        voiceEnabled: true
      }
    ])
    setPendingIntent(null)
    setStageModalData(null)
    setAttachment(null)
    setActiveStageBundle(null)
    setExpandedLooks({})
    setInput('')
    toast.success('Studio reset')
  }

  const handleToggleVoice = (idx) => {
    const msg = messages[idx]
    if (speakingIdx === idx) {
      stopSpeaking()
      setSpeakingIdx(null)
    } else {
      setSpeakingIdx(idx)
      const cleanText = (msg.content || '').replace(/\*\*/g, '').replace(/[#🎨✨🛍️💡🧷]/g, '')
      speak(cleanText, () => setSpeakingIdx(null))
    }
  }

  // Toggle accordion expand/collapse for looks (supports both latest and historical)
  const toggleLook = (msgId, defaultExpanded = false) => {
    setExpandedLooks(prev => {
      const current = prev[msgId] !== undefined ? prev[msgId] : defaultExpanded
      return {
        ...prev,
        [msgId]: !current
      }
    })
  }

  const isLookExpanded = (msgId, defaultExpanded = false) => {
    if (expandedLooks[msgId] !== undefined) {
      return expandedLooks[msgId]
    }
    return defaultExpanded
  }

  // Project any look to Stage Canvas
  const handleProjectToStage = (bundleData, ownedItem, title) => {
    setActiveStageBundle({
      bundleData,
      ownedItem,
      title: title || 'Coordinated Look'
    })
    if (viewportMode === 'chat') {
      setViewportMode('split')
    }
    toast.success(`✨ Projected look to Stage Canvas!`, { icon: '◫' })
  }

  // Render Header Bar with Viewport Mode Switcher
  const renderHeader = () => (
    <div className="chat-header-card">
      <div className="chat-header-left">
        <div className="chat-header-avatar">
          <Sparkles size={20} color="#fff" />
          <div className="chat-online-badge" title="AI Outfit Coordinator Active" />
        </div>
        <div className="chat-header-info">
          <h3>
            AI Outfit Studio
            <span className="badge badge-purple" style={{ fontSize: '0.65rem', padding: '2px 8px' }}>Active</span>
          </h3>
          <p>Conversational Multi-Piece Styling • Color Theory & Harmonic Basketing</p>
        </div>
      </div>

      <div className="chat-header-actions">
        {/* Studio Mode Switcher: Multi-Piece vs Match My Outfit */}
        <div className="studio-mode-pills" style={{ display: 'flex', gap: 4, background: 'rgba(0,0,0,0.35)', padding: 3, borderRadius: 99, border: '1px solid rgba(255,255,255,0.1)' }}>
          <button
            type="button"
            className={`btn btn-sm ${studioMode === 'bundle' ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => handleSwitchMode('bundle')}
            style={{ padding: '4px 12px', fontSize: '0.75rem', borderRadius: 99, height: 'auto' }}
          >
            <Sparkles size={12} style={{ marginRight: 4 }} />
            Multi-Piece Looks
          </button>
          <button
            type="button"
            className={`btn btn-sm ${studioMode === 'match' ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => handleSwitchMode('match')}
            style={{ padding: '4px 12px', fontSize: '0.75rem', borderRadius: 99, height: 'auto' }}
          >
            <Layers size={12} style={{ marginRight: 4 }} />
            Match My Outfit
          </button>
        </div>

        <button 
          className="btn btn-ghost btn-sm" 
          onClick={handleReset} 
          title="Reset Studio"
          style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.8rem' }}
        >
          <RotateCcw size={14} />
          <span>Reset</span>
        </button>
      </div>
    </div>
  )

  // Render Chat Messages stream
  const renderChatMessages = () => (
    <div className="chat-messages">
      {messages.map((msg, i) => (
        <div key={msg.id || i} className={`chat-message ${msg.role} animate-slide-up`}>
          <div className={`chat-avatar ${msg.role}`}>
            {msg.role === 'assistant' ? <Bot size={18} /> : <User size={18} />}
          </div>

          <div style={{ maxWidth: msg.bundleData ? '100%' : '84%', width: msg.bundleData ? '100%' : 'auto' }}>
            <div className={`chat-bubble ${msg.role}`}>
              <span dangerouslySetInnerHTML={{
                __html: (msg.content || '')
                  .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                  .replace(/\n/g, '<br/>')
              }} />

              {/* User Attached Garment Anchor */}
              {msg.attachment && (
                <div className="chat-msg-attachment-badge" style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 10, background: 'rgba(0,0,0,0.25)', padding: '6px 10px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.1)' }}>
                  {msg.attachment.thumb && <img src={msg.attachment.thumb} alt="Garment" style={{ width: 42, height: 42, borderRadius: 4, objectFit: 'cover' }} />}
                  <div style={{ fontSize: '0.78rem' }}>
                    <strong style={{ color: '#a5b4fc', display: 'block' }}>Outfit Anchor Attached:</strong>
                    <span>{msg.attachment.description || `${msg.attachment.color || ''} ${msg.attachment.category || ''}`}</span>
                  </div>
                </div>
              )}

              {/* Per-Message Voice Toggle for Assistant */}
              {msg.role === 'assistant' && (
                <div className="chat-bubble-footer" style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 6 }}>
                  <button 
                    className="btn btn-ghost btn-sm voice-text-toggle" 
                    style={{ 
                      padding: '3px 9px', 
                      height: 'auto', 
                      fontSize: '0.72rem', 
                      fontWeight: 600,
                      color: (speakingIdx === i) ? '#4ade80' : '#a5b4fc',
                      background: 'rgba(99, 102, 241, 0.18)',
                      border: '1px solid rgba(99, 102, 241, 0.45)',
                      borderRadius: 99,
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 5,
                      cursor: 'pointer'
                    }} 
                    onClick={() => handleToggleVoice(i)}
                    title="Read aloud"
                  >
                    {speakingIdx === i ? (
                      <>
                        <Volume2 size={13} color="#4ade80" />
                        <span>Speaking…</span>
                      </>
                    ) : (
                      <>
                        <Volume2 size={13} color="#818cf8" />
                        <span>Voice: ON</span>
                      </>
                    )}
                  </button>
                </div>
              )}
            </div>

            {/* Coordinated Interactive Outfit Suite */}
            {msg.bundleData && (
              <div style={{ marginTop: 12 }}>
                {i === latestBundleMsgIdx ? (
                  /* Latest Look: Expanded with header banner & shortcut to Stage */
                  <div className="latest-look-container">
                    <div className="latest-look-toolbar">
                      <span className="latest-look-badge">
                        <Sparkles size={13} />
                        <span>Latest Coordinated Look</span>
                      </span>
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        {viewportMode === 'chat' && (
                          <>
                            <button 
                              type="button"
                              className="btn-project-to-stage-chip"
                              onClick={() => handleProjectToStage(msg.bundleData, msg.ownedItem, msg.content?.slice(0, 35))}
                              title="Open this look in Split Stage view"
                            >
                              <Columns size={13} />
                              <span>◫ Split Stage</span>
                            </button>
                            <button 
                              type="button"
                              className="btn-project-to-stage-chip"
                              onClick={() => {
                                setStageModalData({
                                  bundleData: msg.bundleData,
                                  ownedItem: msg.ownedItem,
                                  title: msg.content?.slice(0, 35) || 'Latest Coordinated Look'
                                })
                              }}
                              title="Open this look in dedicated Stage Canvas Modal"
                            >
                              <Layout size={13} />
                              <span>🖼️ Stage Canvas</span>
                            </button>
                          </>
                        )}
                        <button
                          type="button"
                          className="btn-accordion-arrow"
                          onClick={() => toggleLook(msg.id, true)}
                          title={isLookExpanded(msg.id, true) ? "Collapse look" : "Expand look"}
                        >
                          {isLookExpanded(msg.id, true) ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                        </button>
                      </div>
                    </div>
                    {viewportMode === 'split' ? (
                      <div className="historical-look-card animate-fade" style={{ marginTop: 8 }}>
                        <div className="historical-look-bar" style={{ background: 'var(--bg-elevated)', border: '1px dashed var(--accent-purple)', cursor: 'default' }}>
                          <div className="historical-look-left">
                            <div className="historical-look-icon"><Layout size={14} color="var(--accent-purple)" /></div>
                            <div className="historical-look-meta">
                              <strong>Viewing in Split Stage</strong>
                              <span className="historical-look-sub">Look is projected to the visual canvas ➔</span>
                            </div>
                          </div>
                          <button
                            type="button"
                            className="btn-project-stage-pill"
                            onClick={() => setStageModalData({
                              bundleData: msg.bundleData,
                              ownedItem: msg.ownedItem,
                              title: msg.content?.slice(0, 35) || 'Latest Coordinated Look'
                            })}
                            title="Open in Stage Canvas Modal"
                          >
                            <Layout size={13} />
                            <span>Modal</span>
                          </button>
                        </div>
                      </div>
                    ) : !isLookExpanded(msg.id, true) ? (
                      <div 
                        className="historical-look-card animate-fade" 
                        style={{ marginTop: 8 }}
                        onClick={() => toggleLook(msg.id, true)}
                      >
                        <div className="historical-look-bar" style={{ cursor: 'pointer' }}>
                          <div className="historical-look-left">
                            {msg.bundleData.hero_bundle?.items?.length >= 2 ? (
                              <div style={{ display: 'flex', alignItems: 'center', marginRight: 4 }}>
                                {msg.bundleData.hero_bundle.items.slice(0, 2).map((item, itmIdx) => (
                                  <img
                                    key={itmIdx}
                                    src={getProductImageUrl(item, itmIdx === 0 ? 'top' : 'bottom')}
                                    alt={item.title}
                                    style={{
                                      width: 32,
                                      height: 32,
                                      borderRadius: 6,
                                      objectFit: 'cover',
                                      border: '1.5px solid rgba(255,255,255,0.2)',
                                      marginLeft: itmIdx > 0 ? -10 : 0,
                                      boxShadow: '0 2px 4px rgba(0,0,0,0.35)'
                                    }}
                                    onError={(e) => { e.target.style.display = 'none' }}
                                  />
                                ))}
                              </div>
                            ) : (
                              <div className="historical-look-icon"><Sparkles size={14} color="var(--accent-purple)" /></div>
                            )}
                            <div className="historical-look-meta">
                              <strong>Latest Coordinated Look • ₹{msg.bundleData.hero_bundle?.total_price || msg.bundleData.budget || '—'}</strong>
                              <span className="historical-look-sub">
                                {msg.bundleData.hero_bundle?.items?.[0]?.title?.slice(0, 24) || 'Upper'} + {msg.bundleData.hero_bundle?.items?.[1]?.title?.slice(0, 24) || 'Lower'} — <em>Tap to expand look</em>
                              </span>
                            </div>
                          </div>
                          <ChevronDown size={16} />
                        </div>
                      </div>
                    ) : (
                      <InteractiveOutfitSuite 
                        bundleData={msg.bundleData}
                        mode={msg.bundleData.mode || 'bundle'}
                        ownedItem={msg.ownedItem}
                        onAddToCart={onAddToCart}
                        onAutonomousCheckout={onAutonomousCheckout}
                        onFollowUp={(followUpText) => handleSendMessage(followUpText)}
                        onSelectAlternative={(altText) => handleSendMessage(altText)}
                      />
                    )}
                  </div>
                ) : (
                  /* Historical Look: Sleek Accordion Pill */
                  <div className="historical-look-card animate-fade">
                    <div 
                      className="historical-look-bar"
                      onClick={() => toggleLook(msg.id)}
                    >
                      <div className="historical-look-left">
                        {msg.bundleData.hero_bundle?.items?.length >= 2 ? (
                          <div style={{ display: 'flex', alignItems: 'center', marginRight: 4 }}>
                            {msg.bundleData.hero_bundle.items.slice(0, 2).map((item, itmIdx) => (
                              <img
                                key={itmIdx}
                                src={getProductImageUrl(item, itmIdx === 0 ? 'top' : 'bottom')}
                                alt={item.title}
                                style={{
                                  width: 30,
                                  height: 30,
                                  borderRadius: 6,
                                  objectFit: 'cover',
                                  border: '1.5px solid rgba(255,255,255,0.2)',
                                  marginLeft: itmIdx > 0 ? -10 : 0,
                                  boxShadow: '0 2px 4px rgba(0,0,0,0.35)'
                                }}
                                onError={(e) => { e.target.style.display = 'none' }}
                              />
                            ))}
                          </div>
                        ) : (
                          <div className="historical-look-icon">
                            <Sparkles size={14} color="var(--accent-purple)" />
                          </div>
                        )}
                        <div className="historical-look-meta">
                          <strong>{msg.ownedItem ? `Matched Look (${msg.ownedItem.color || ''} ${msg.ownedItem.category || ''})` : `Coordinated Look #${i} • ₹${msg.bundleData.hero_bundle?.total_price || msg.bundleData.budget || '—'}`}</strong>
                          <span className="historical-look-sub">
                            {msg.bundleData.hero_bundle?.items?.[0]?.title?.slice(0, 22) || 'Piece 1'} + {msg.bundleData.hero_bundle?.items?.[1]?.title?.slice(0, 22) || 'Piece 2'} ({Math.round((msg.bundleData.hero_bundle?.style_score || 0.85) * 100)}% Harmony)
                          </span>
                        </div>
                      </div>

                      <div className="historical-look-actions" onClick={e => e.stopPropagation()}>
                        <button
                          type="button"
                          className="btn-project-stage-pill"
                          onClick={() => setStageModalData({
                            bundleData: msg.bundleData,
                            ownedItem: msg.ownedItem,
                            title: msg.content?.slice(0, 35) || `Coordinated Look #${i}`
                          })}
                          title="Open this historical look in Stage Canvas Modal"
                        >
                          <Layout size={13} />
                          <span>Stage Canvas</span>
                        </button>

                        <button
                          type="button"
                          className="btn-project-stage-pill"
                          onClick={() => handleProjectToStage(msg.bundleData, msg.ownedItem, msg.content?.slice(0, 35))}
                          title="Project this historical look onto Split Stage"
                        >
                          <Columns size={13} />
                          <span>Split</span>
                        </button>

                        <button
                          type="button"
                          className="btn-accordion-arrow"
                          onClick={() => toggleLook(msg.id)}
                          title={isLookExpanded(msg.id, false) ? "Collapse look" : "Expand look"}
                        >
                          {isLookExpanded(msg.id, false) ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                        </button>
                      </div>
                    </div>

                    {isLookExpanded(msg.id, false) && (
                      <div className="historical-look-body animate-slide-down">
                        <InteractiveOutfitSuite 
                          bundleData={msg.bundleData}
                          mode={msg.bundleData.mode || 'bundle'}
                          ownedItem={msg.ownedItem}
                          onAddToCart={onAddToCart}
                          onAutonomousCheckout={onAutonomousCheckout}
                          onFollowUp={(followUpText) => handleSendMessage(followUpText)}
                          onSelectAlternative={(altText) => handleSendMessage(altText)}
                        />
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Quick Reply Option Chips */}
            {msg.suggestedOptions?.length > 0 && i === messages.length - 1 && (
              <div className="chat-chips animate-slide-up" style={{ marginTop: 10 }}>
                {msg.suggestedOptions.map((opt, j) => (
                  <button 
                    key={j} 
                    className="chat-chip" 
                    onClick={() => handleSendMessage(opt)}
                    disabled={isCoordinating}
                  >
                    <Sparkles size={12} style={{ opacity: 0.7 }} />
                    <span>{opt}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      ))}

      {/* AI Thinking Animation */}
      {isCoordinating && (
        <div className="chat-message assistant animate-slide-up">
          <div className="chat-avatar assistant"><Bot size={18} /></div>
          <div className="typing-indicator">
            <div className="typing-dot" />
            <div className="typing-dot" />
            <div className="typing-dot" />
          </div>
        </div>
      )}

      <div ref={endRef} />
    </div>
  )

  // Render Input Bar with Auto-Voice Toggle
  const renderInputBar = () => (
    <div className="chat-input-bar-container">
      {/* Voice Listening Banner */}
      {isListening && (
        <div className="chat-voice-active-banner animate-slide-up" style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 14px',
          background: 'rgba(99, 102, 241, 0.18)',
          border: '1px solid var(--accent-purple)',
          borderRadius: 'var(--radius-md)',
          marginBottom: 8,
          color: '#fff',
          fontSize: '0.85rem'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div className="pulse-indicator" style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--accent-red)' }} />
            <span>{transcript ? `"${transcript}"` : "Listening to your voice... Speak your outfit request!"}</span>
          </div>
          <button 
            type="button" 
            className="btn btn-sm btn-primary"
            onClick={() => {
              stopListening()
              if (transcript.trim()) {
                handleSendMessage(transcript.trim())
              }
            }}
            style={{ padding: '4px 10px', fontSize: '0.78rem' }}
          >
            Send Voice
          </button>
        </div>
      )}

      {/* Attachment preview banner */}
      {attachment && (
        <div className="chat-attachment-preview animate-slide-up">
          <img src={attachment.thumb} alt="Preview" className="attachment-thumb" />
          <div className="attachment-text">
            <strong>Outfit Anchor Attached:</strong> {attachment.description || `${attachment.color} ${attachment.category}`}
          </div>
          <button type="button" className="attachment-remove-btn" onClick={() => setAttachment(null)} title="Remove attachment">
            <X size={16} />
          </button>
        </div>
      )}

      <div className="chat-input-glass-pill">
        {/* + Attachment Button */}
        <input 
          type="file" 
          accept="image/*" 
          ref={fileInputRef} 
          onChange={handleAttachmentFile} 
          style={{ display: 'none' }} 
        />
        <button 
          className="chat-attach-btn" 
          onClick={() => fileInputRef.current?.click()} 
          title="Attach owned outfit photo (+)"
          type="button"
          disabled={isExtractingAttachment || isCoordinating}
        >
          {isExtractingAttachment ? <RefreshCw size={16} className="animate-spin" /> : <Plus size={18} />}
        </button>

        <button 
          className="btn btn-ghost btn-icon" 
          onClick={handleReset} 
          title="Reset Studio"
          style={{ width: 32, height: 32, padding: 0, color: 'var(--text-muted)' }}
        >
          <Trash2 size={16} />
        </button>

        <textarea
          ref={inputRef}
          className="chat-input-field"
          value={input}
          onChange={e => { setInput(e.target.value); resetTranscript() }}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              handleSendMessage()
            }
          }}
          placeholder={isListening ? "🎙️ Listening to your voice..." : (studioMode === 'match' ? "Describe or speak pairing request (or upload photo with +)..." : "Type or speak outfit look (e.g. 2 uppers and 1 lower under 3k, 2 shirts)...")}
          rows={1}
          disabled={isCoordinating}
        />

        {/* Voice Mic & Auto-Voice Controls */}
        <div className="chat-voice-pill">
          <button 
            className={`chat-mic-btn ${isListening ? 'active' : ''}`} 
            onClick={isListening ? stopListening : startListening}
            title={isListening ? "Stop listening" : "Speak your outfit prompt (Voice Input)"}
            type="button"
          >
            {isListening ? <MicOff size={16} /> : <Mic size={16} />}
          </button>
          <button 
            type="button"
            className={`chat-auto-voice-btn ${isAutoVoice ? 'active' : ''}`}
            onClick={() => {
              const next = !isAutoVoice
              setIsAutoVoice(next)
              if (next && !isListening) {
                startListening()
              }
            }}
            title={isAutoVoice ? "Auto-Voice: ON (Continuous hands-free conversation)" : "Auto-Voice: OFF (Click for hands-free mode)"}
          >
            <span className={`auto-voice-dot ${isAutoVoice ? 'active' : ''}`} />
            <span>Auto</span>
          </button>
        </div>

        <button
          className="chat-send-pill-btn"
          onClick={() => handleSendMessage()}
          disabled={(!input.trim() && !attachment) || isCoordinating}
          title="Send Message (Enter)"
        >
          <Send size={16} />
        </button>
      </div>

      <div className="chat-input-hints">
        <span>💡 Press <strong>Enter</strong> to send, <strong>Shift+Enter</strong> for a new line</span>
        <span>Perceptual Color Science • Dynamic Budget Allocation • Vision AI</span>
      </div>
    </div>
  )

  // Render Visual Stage Canvas Content
  const renderStageContent = () => {
    const bundleToRender = activeStageBundle?.bundleData || (latestBundleMsgIdx !== -1 ? messages[latestBundleMsgIdx]?.bundleData : null)
    const ownedToRender = activeStageBundle?.ownedItem || (latestBundleMsgIdx !== -1 ? messages[latestBundleMsgIdx]?.ownedItem : null)

    if (!bundleToRender) {
      return (
        <div className="empty-stage-placeholder animate-fade">
          <div className="empty-stage-icon">
            <Sparkles size={32} color="var(--accent-purple)" />
          </div>
          <h3>Visual Outfit Stage Canvas</h3>
          <p>
            Ready to explore aesthetic combinations! Type or speak what you'd like to put together, or select a style prompt below to project it onto this stage.
          </p>
          <div className="empty-stage-suggestions">
            {[
              "I want 2 uppers and 1 lower under 3k",
              "Give me 2 shirts",
              "Olive hoodie and black joggers under 2500",
              "Vintage graphic tee + denim jeans"
            ].map((s, idx) => (
              <button
                key={idx}
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => handleSendMessage(s)}
                disabled={isCoordinating}
              >
                <Sparkles size={12} />
                <span>{s}</span>
              </button>
            ))}
          </div>
        </div>
      )
    }

    return (
      <div className="stage-canvas-inner animate-fade">
        <InteractiveOutfitSuite 
          bundleData={bundleToRender}
          mode={bundleToRender.mode || 'bundle'}
          ownedItem={ownedToRender}
          onAddToCart={onAddToCart}
          onAutonomousCheckout={onAutonomousCheckout}
          onFollowUp={(followUpText) => handleSendMessage(followUpText)}
          onSelectAlternative={(altText) => handleSendMessage(altText)}
        />
      </div>
    )
  }

  // Render Stage Canvas Modal Overlay
  const renderStageModal = () => {
    if (!stageModalData) return null

    const { bundleData, ownedItem, title } = stageModalData

    return (
      <div 
        className="stage-canvas-modal-overlay animate-fade"
        onClick={(e) => {
          if (e.target === e.currentTarget) setStageModalData(null)
        }}
      >
        <div className="stage-canvas-modal-dialog animate-scale-up" role="dialog" aria-modal="true">
          <div className="stage-modal-header">
            <div className="stage-modal-header-left">
              <div className="stage-modal-icon-badge">
                <Sparkles size={18} color="var(--accent-purple)" />
              </div>
              <div>
                <h3 className="stage-modal-title">
                  {title || 'Visual Outfit Stage Canvas'}
                </h3>
                <span className="stage-modal-subtitle">
                  Inspect pieces, swap top/bottom garments, explore alternatives, or autonomous checkout
                </span>
              </div>
            </div>

            <div className="stage-modal-header-actions">
              <span className="stage-modal-esc-hint">Press <strong>Esc</strong> to close</span>
              <button
                type="button"
                className="stage-modal-close-btn"
                onClick={() => setStageModalData(null)}
                title="Close Stage Canvas Modal"
                aria-label="Close"
              >
                <X size={18} />
              </button>
            </div>
          </div>

          <div className="stage-modal-body">
            <InteractiveOutfitSuite
              isStageModal={true}
              bundleData={bundleData}
              mode={bundleData?.mode || 'bundle'}
              ownedItem={ownedItem}
              onAddToCart={onAddToCart}
              onAutonomousCheckout={onAutonomousCheckout}
              onFollowUp={(followUpText) => {
                setStageModalData(null)
                handleSendMessage(followUpText)
              }}
              onSelectAlternative={(altText) => {
                setStageModalData(null)
                handleSendMessage(altText)
              }}
            />
          </div>
        </div>
      </div>
    )
  }

  // ── Layout by Viewport Mode ──

  // Mode 2: Split Stage (Side-by-side Dual-Pane)
  if (viewportMode === 'split') {
    return (
      <div className="outfit-studio-wrapper animate-fade">
        {renderHeader()}
        <div className="outfit-split-layout">
          {/* Left: Chat Stream Pane */}
          <div className="outfit-split-chat-pane">
            {renderChatMessages()}
            {renderInputBar()}
          </div>

          {/* Right: Visual Outfit Stage Pane */}
          <div className="outfit-split-stage-pane">
            <div className="stage-pane-header">
              <div className="stage-pane-title-group">
                <Sparkles size={16} color="var(--accent-purple)" />
                <h4>{activeStageBundle?.title || 'Visual Outfit Stage'}</h4>
              </div>
              <div className="stage-pane-actions">
                <button
                  type="button"
                  className="stage-nav-back-btn"
                  onClick={() => setViewportMode('stage')}
                  title="Expand to Fullscreen Stage Canvas"
                >
                  <Layout size={13} />
                  <span>Full Stage Canvas</span>
                </button>
                <button
                  type="button"
                  className="stage-nav-back-btn"
                  onClick={() => setViewportMode('chat')}
                  title="Return to Chat Focus mode"
                >
                  <MessageSquare size={13} />
                  <span>Chat Focus</span>
                </button>
              </div>
            </div>
            {renderStageContent()}
          </div>
        </div>
        {renderStageModal()}
      </div>
    )
  }

  // Mode 3: Stage Canvas (Full-width dedicated visual outfit inspection)
  if (viewportMode === 'stage') {
    return (
      <div className="outfit-studio-wrapper animate-fade">
        {renderHeader()}
        <div className="outfit-stage-canvas-fullscreen">
          <div className="stage-canvas-toolbar">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <button
                type="button"
                className="stage-nav-back-btn"
                onClick={() => setViewportMode('chat')}
                title="Return to Chat Focus mode"
              >
                <ArrowLeft size={14} />
                <span>Back to Chat</span>
              </button>
              <button
                type="button"
                className="stage-nav-back-btn"
                onClick={() => setViewportMode('split')}
                title="Switch to Side-by-side Split Stage"
              >
                <Columns size={14} />
                <span>Split Stage</span>
              </button>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Sparkles size={16} color="var(--accent-purple)" />
              <h3 style={{ margin: 0, fontSize: '1.05rem', color: '#fff' }}>
                {activeStageBundle?.title || 'Visual Outfit Stage Canvas'}
              </h3>
            </div>

            <div style={{ width: 140, display: 'flex', justifyContent: 'flex-end' }}>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={handleReset}
                title="Reset Studio"
                style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: '0.8rem' }}
              >
                <RotateCcw size={14} />
                <span>Reset</span>
              </button>
            </div>
          </div>
          {renderStageContent()}
        </div>
        {renderStageModal()}
      </div>
    )
  }

  // Mode 1 (Default): Chat Focus (Single-column conversational stream)
  return (
    <div className="chat-container animate-fade">
      {renderHeader()}
      {renderChatMessages()}
      {renderInputBar()}
      {renderStageModal()}
    </div>
  )
}
