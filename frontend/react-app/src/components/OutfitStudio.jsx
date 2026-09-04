import React, { useState, useRef, useEffect } from 'react'
import { 
  Send, Trash2, Mic, MicOff, Volume2, VolumeX, Sparkles, User, Bot, 
  RotateCcw, RefreshCw, Plus, X, Layers, ShoppingBag
} from 'lucide-react'
import { coordinateBundle, matchOutfit, extractGarmentImage } from '../api/client'
import { useApp } from '../context/AppContext'
import { useVoice } from '../hooks/useVoice'
import InteractiveOutfitSuite from './InteractiveOutfitSuite'
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
  const { config, userProfile } = useApp()
  const [studioMode, setStudioMode] = useState('bundle') // 'bundle' | 'match'
  
  const [messages, setMessages] = useState([
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

  const [input, setInput] = useState('')
  const [isCoordinating, setIsCoordinating] = useState(false)
  const [speakingIdx, setSpeakingIdx] = useState(null)

  // Voice recognition & synthesis
  const { 
    isListening, transcript, startListening, stopListening, 
    speak, stopSpeaking, resetTranscript 
  } = useVoice()

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
    if (!isListening && input.trim() && transcript) {
      handleSendMessage(input)
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

    // Context analysis across history
    const allUserTexts = [...messages.filter(m => m.role === 'user').map(m => m.content), rawText].join(' ')
    const extractedBudget = extractBudgetFromText(rawText) || extractBudgetFromText(allUserTexts)
    const lowerText = rawText.toLowerCase()

    // 1. Missing Metric Guard: "I want 2 uppers" or "give me 2 shirts" without budget
    const isVagueTwoUppers = /\b(?:2|two)\s*(?:uppers?|tops?)\b/i.test(rawText)
    const isVagueShirts = /\b(?:2|two)\s*(?:shirts?|tees?)\b/i.test(rawText)
    const hasAnyBudget = extractedBudget !== null

    if ((isVagueTwoUppers || isVagueShirts) && !hasAnyBudget) {
      setIsCoordinating(false)
      const clarifyMsg = {
        id: 'asst-' + Date.now(),
        role: 'assistant',
        content: isVagueTwoUppers
          ? "Great! To coordinate the best **2 uppers** for you:\n\n1. What **total budget** would you like to stay under?\n2. Would you prefer **2 distinct styles** (such as a hoodie or jacket layered over a t-shirt) or two shirts?"
          : "I'd love to coordinate **2 shirts** for you! What is your target total budget to stay under for both pieces?",
        suggestedOptions: isVagueTwoUppers
          ? [
              "Layered: Hoodie + T-shirt under 2500",
              "Jacket + T-shirt under 3000",
              "Two Casual Shirts under 2000",
              "Under ₹3,000 (Best Value)"
            ]
          : [
              "Under ₹1,500",
              "Under ₹2,500",
              "Under ₹3,500",
              "No Budget Cap"
            ],
        voiceEnabled: true
      }
      setMessages(prev => [...prev, clarifyMsg])
      return
    }

    // 2. Synthesize Multi-Turn Query if user is answering a budget/style question
    const prevUserGarment = [...messages.filter(m => m.role === 'user').map(m => m.content)]
      .reverse()
      .find(t => /\b(shirts?|uppers?|lowers?|hoodies?|joggers?|jeans?|t-?shirts?|tees?|pants?)\b/i.test(t)) || ''

    let effectiveQuery = rawText
    if (hasAnyBudget && prevUserGarment && !/\b(shirts?|uppers?|lowers?|hoodies?|joggers?|jeans?)\b/i.test(rawText)) {
      effectiveQuery = `${prevUserGarment} under ${extractedBudget}`
    }

    // 3. Case A: Match My Outfit (If an owned anchor is active or selected)
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
      } catch (err) {
        console.error('Outfit match error:', err)
        toast.error('Failed to coordinate match for your garment.')
      } finally {
        setIsCoordinating(false)
      }
      return
    }

    // 4. Case B: Free-Form Multi-Piece Bundle Coordination
    try {
      const targetBudget = extractedBudget || 3000
      const res = await coordinateBundle({
        query: effectiveQuery,
        budget: targetBudget,
        gender: userProfile?.gender || 'men',
        user_skin_depth: userProfile?.skinDepth || null,
        user_undertone: userProfile?.undertone || null,
        data_source: config.dataSource || 'dev'
      })

      const data = res.data
      let replyContent = `✨ Coordinated complete outfit looks for **"${effectiveQuery}"** within ₹${targetBudget}!`
      if (data.status === 'budget_too_low') {
        replyContent = `💡 With your budget of ₹${targetBudget}, coordinating these pieces exceeds catalog floor prices. Here are proactive stylist recommendations:`
      }

      const bundleMsg = {
        id: 'asst-' + Date.now(),
        role: 'assistant',
        content: replyContent,
        bundleData: data,
        suggestedOptions: data.status === 'budget_too_low' 
          ? [
              `Adjust budget to ₹${data.min_total_required || 2000}`,
              "Show Best Value Options",
              "Switch to T-Shirt + Joggers"
            ]
          : [
              "🛒 Buy Combo #1",
              "🔄 Swap Upper",
              "🔄 Swap Lower",
              "Under ₹2,000",
              "Show Oversized Looks"
            ],
        voiceEnabled: true
      }
      setMessages(prev => [...prev, bundleMsg])
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
    setAttachment(null)
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

  return (
    <div className="chat-container animate-fade">
      {/* Sleek Chat Header Card (Identical to AI Personal Stylist) */}
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

        {/* Mode Switcher Pills & Reset */}
        <div className="chat-header-actions">
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
            title="Reset Conversation"
            style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.8rem' }}
          >
            <RotateCcw size={14} />
            <span>Reset</span>
          </button>
        </div>
      </div>

      {/* Messages Thread */}
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
                <div style={{ marginTop: 14 }}>
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

      {/* Modern Glassmorphic Input Bar (Identical to ChatInterface) */}
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

          {/* Voice Mic Controls */}
          <div className="chat-voice-pill">
            <button 
              className={`chat-mic-btn ${isListening ? 'active' : ''}`} 
              onClick={isListening ? stopListening : startListening}
              title={isListening ? "Stop listening" : "Speak your outfit prompt (Voice Input)"}
              type="button"
            >
              {isListening ? <MicOff size={16} /> : <Mic size={16} />}
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
    </div>
  )
}
