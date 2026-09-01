import React, { useState, useRef, useEffect } from 'react'
import { 
  Send, Trash2, Mic, MicOff, Volume2, Sparkles, User, Bot, 
  ChevronLeft, ChevronRight, RotateCcw, Flame, Palette, Shirt
} from 'lucide-react'
import { chatMessage, clearChat, searchProducts } from '../api/client'
import { useApp } from '../context/AppContext'
import { useVoice } from '../hooks/useVoice'
import ProductCard from './ProductCard'
import toast from 'react-hot-toast'

const SESSION_ID = 'rasor-stylist'

const INITIAL_MESSAGES = [
  {
    role: 'assistant',
    content: "Welcome to **Rasor**! I'm your AI personal stylist. 🛍️ Tell me what you're looking for — I'll ask just a few smart questions or evaluate your skin tone to find the perfect match for you.",
    suggestedOptions: ['Show me men\'s t-shirts', 'Marvel fan merch', 'Skin tone 5', 'Something for the gym', 'Surprise me 🎲'],
  }
]

export default function ChatInterface({ onAddToCart }) {
  const { config } = useApp()
  const [messages, setMessages] = useState(INITIAL_MESSAGES)
  const [input, setInput] = useState('')
  const [isThinking, setIsThinking] = useState(false)
  const [searchResults, setSearchResults] = useState(null)
  const [isSearching, setIsSearching] = useState(false)
  const [isAutoVoice, setIsAutoVoice] = useState(false)
  const [speakingIdx, setSpeakingIdx] = useState(null)
  const { isListening, transcript, startListening, stopListening, speak, stopSpeaking, resetTranscript } = useVoice()
  
  const endRef = useRef(null)
  const inputRef = useRef(null)
  const carouselRef = useRef(null)

  useEffect(() => { 
    endRef.current?.scrollIntoView({ behavior: 'smooth' }) 
  }, [messages, isThinking, searchResults])

  useEffect(() => {
    if (transcript) setInput(transcript)
  }, [transcript])

  useEffect(() => {
    // Auto-send when voice stops and we have input
    if (!isListening && input.trim() && transcript) {
      sendMessage(input)
      resetTranscript()
    }
  }, [isListening, transcript, input])

  const sendMessage = async (text) => {
    if (!text.trim() || isThinking) return
    const userText = text.trim()
    stopSpeaking()
    stopListening()
    setSpeakingIdx(null)
    setInput('')
    resetTranscript()
    setMessages(prev => [...prev, { role: 'user', content: userText }])
    setIsThinking(true)
    setSearchResults(null)

    try {
      const history = messages.map(m => ({ role: m.role, content: m.content }))
      const { data } = await chatMessage({
        message: userText,
        history,
        session_id: SESSION_ID,
        data_source: config.dataSource,
        primary_model: config.primaryModel,
        fallback_model: config.fallbackModel,
      })

      const assistantMsg = {
        role: 'assistant',
        content: data.message,
        suggestedOptions: data.suggested_options || [],
      }

      setMessages(prev => {
        const next = [...prev, assistantMsg]
        const targetIdx = next.length - 1
        // Auto-play voice if enabled
        if (config.voiceEnabled) {
          setSpeakingIdx(targetIdx)
          speak(data.message, config.voiceURI, () => {
            setSpeakingIdx(null)
            // Listening only begins strictly AFTER the AI finishes speaking
            if (isAutoVoice) {
              setTimeout(() => {
                startListening()
              }, 400)
            }
          })
        }
        return next
      })

      if (data.ready_for_search && data.updated_query) {
        setIsSearching(true)
        try {
          const { data: searchData } = await searchProducts({
            query: data.updated_query,
            data_source: config.dataSource,
            primary_model: config.primaryModel,
            fallback_model: config.fallbackModel,
            max_results: config.maxResults,
            enable_deep_enrichment: config.enableDeepEnrichment,
            max_deep_fetches: config.maxDeepFetches,
            enable_vqa_scanner: config.enableVqaScanner,
            vqa_strict_filter: config.vqaStrictFilter,
            truth_hierarchy: config.truthHierarchy,
            enable_semantic_engine: config.enableSemanticEngine,
            currency: config.currency,
          })
          const prods = searchData.products || []
          setSearchResults(prods)
          if (prods.length > 0) {
            setMessages(prev => [...prev, {
              role: 'assistant',
              content: `✨ Found **${prods.length}** curated picks matching your style! Browse them below:`,
            }])
          } else {
            setMessages(prev => [...prev, {
              role: 'assistant',
              content: "Hmm, I couldn't find products matching those exact criteria. Want to try a different description or fit?",
            }])
          }
        } catch (err) {
          toast.error('Search failed: ' + (err.response?.data?.detail || err.message))
        } finally {
          setIsSearching(false)
        }
      }
    } catch (err) {
      toast.error('Chat error: ' + (err.response?.data?.detail || err.message))
      setMessages(prev => [...prev, { role: 'assistant', content: "Sorry, I ran into an issue connecting to the AI. Could you try again?" }])
    } finally {
      setIsThinking(false)
    }
  }

  const handleChipClick = (opt) => sendMessage(opt)

  const handleClear = async () => {
    await clearChat(SESSION_ID).catch(() => {})
    setMessages(INITIAL_MESSAGES)
    setSearchResults(null)
    stopSpeaking()
    stopListening()
    setSpeakingIdx(null)
    setInput('')
    resetTranscript()
    toast.success('Conversation reset')
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { 
      e.preventDefault()
      sendMessage(input) 
    }
  }

  const handlePlayVoice = (text, idx) => {
    if (speakingIdx === idx) {
      stopSpeaking()
      setSpeakingIdx(null)
    } else {
      stopSpeaking()
      setSpeakingIdx(idx)
      speak(text, config.voiceURI, () => setSpeakingIdx(null))
    }
  }

  const scrollCarousel = (direction) => {
    if (carouselRef.current) {
      const shift = direction === 'left' ? -260 : 260
      carouselRef.current.scrollBy({ left: shift, behavior: 'smooth' })
    }
  }

  return (
    <div className="chat-container">
      {/* Sleek Chat Header */}
      <div className="chat-header-card">
        <div className="chat-header-left">
          <div className="chat-header-avatar">
            <Sparkles size={20} color="#fff" />
            <div className="chat-online-badge" title="AI Stylist Active" />
          </div>
          <div className="chat-header-info">
            <h3>
              AI Personal Stylist
              <span className="badge badge-purple" style={{ fontSize: '0.65rem', padding: '2px 8px' }}>Active</span>
            </h3>
            <p>Multi-turn fashion dialogue • Skin tone color theory & recommendations</p>
          </div>
        </div>
        <div className="chat-header-actions">
          <button 
            className="btn btn-ghost btn-sm" 
            onClick={handleClear} 
            title="Reset Conversation"
            style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.8rem' }}
          >
            <RotateCcw size={14} />
            <span>Reset</span>
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`chat-message ${msg.role} animate-slide-up`}>
            <div className={`chat-avatar ${msg.role}`}>
              {msg.role === 'assistant' ? <Bot size={18} /> : <User size={18} />}
            </div>
            <div style={{ maxWidth: '100%' }}>
              <div className={`chat-bubble ${msg.role}`}>
                <span dangerouslySetInnerHTML={{
                  __html: msg.content
                    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                    .replace(/\n/g, '<br/>')
                }} />

                {/* Speaker playback */}
                {msg.role === 'assistant' && (
                  <div className="chat-bubble-footer">
                    <button 
                      className="btn btn-ghost btn-sm" 
                      style={{ 
                        padding: '3px 8px', 
                        height: 'auto', 
                        fontSize: '0.75rem', 
                        color: speakingIdx === i ? '#818cf8' : 'var(--text-muted)',
                        background: speakingIdx === i ? 'rgba(99, 102, 241, 0.2)' : 'transparent',
                        border: speakingIdx === i ? '1px solid rgba(99, 102, 241, 0.4)' : '1px solid transparent',
                        borderRadius: 99,
                        transition: 'all 0.2s ease'
                      }} 
                      onClick={() => handlePlayVoice(msg.content, i)}
                      title={speakingIdx === i ? "Stop playback" : "Read aloud"}
                    >
                      <Volume2 size={13} className={speakingIdx === i ? 'pulsing' : ''} style={{ marginRight: 4 }} />
                      <span>{speakingIdx === i ? 'Playing…' : 'Listen'}</span>
                    </button>
                  </div>
                )}
              </div>

              {/* Quick Reply Chips */}
              {msg.suggestedOptions?.length > 0 && i === messages.length - 1 && (
                <div className="chat-chips">
                  {msg.suggestedOptions.map((opt, j) => (
                    <button key={j} className="chat-chip" onClick={() => handleChipClick(opt)}>
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
        {isThinking && (
          <div className="chat-message assistant animate-slide-up">
            <div className="chat-avatar assistant"><Bot size={18} /></div>
            <div className="typing-indicator">
              <div className="typing-dot" />
              <div className="typing-dot" />
              <div className="typing-dot" />
            </div>
          </div>
        )}

        {/* Searching Animation */}
        {isSearching && (
          <div className="loading-state" style={{ padding: '16px 0' }}>
            <div className="spinner" style={{ borderTopColor: 'var(--accent-green)' }} />
            <span className="text-sm text-muted">Searching & Ranking Catalog…</span>
          </div>
        )}

        {/* Product Carousel inside Chat */}
        {searchResults && searchResults.length > 0 && (
          <div className="product-carousel-wrapper animate-slide-up">
            <div className="product-carousel-header">
              <div className="product-carousel-title">
                <Shirt size={16} color="var(--accent-green)" />
                <span>Curated Recommendations ({searchResults.length} items)</span>
              </div>
              <div className="product-carousel-nav">
                <button className="product-carousel-btn" onClick={() => scrollCarousel('left')} title="Previous items">
                  <ChevronLeft size={16} />
                </button>
                <button className="product-carousel-btn" onClick={() => scrollCarousel('right')} title="Next items">
                  <ChevronRight size={16} />
                </button>
              </div>
            </div>
            <div className="product-carousel" ref={carouselRef}>
              {searchResults.map(p => (
                <ProductCard key={p.id} product={p} onAddToCart={onAddToCart} layout="carousel" />
              ))}
            </div>
          </div>
        )}

        <div ref={endRef} />
      </div>

      {/* Modern Glassmorphic Input Bar */}
      <div className="chat-input-bar-container">
        <div className="chat-input-glass-pill">
          <button 
            className="btn btn-ghost btn-icon" 
            onClick={handleClear} 
            title="Clear Chat"
            style={{ width: 32, height: 32, padding: 0, color: 'var(--text-muted)' }}
          >
            <Trash2 size={16} />
          </button>

          <textarea
            ref={inputRef}
            className="chat-input-field"
            value={input}
            onChange={e => { setInput(e.target.value); resetTranscript() }}
            onKeyDown={handleKeyDown}
            placeholder={isListening ? "🎙️ Listening to your voice..." : "Tell the stylist what you want (e.g. Skin tone 5, party wear)..."}
            rows={1}
            disabled={isThinking}
          />

          {/* Voice Mic Controls */}
          {config.voiceEnabled && (
            <div className="chat-voice-pill">
              <button 
                className={`chat-mic-btn ${isListening ? 'active' : ''}`} 
                onClick={isListening ? stopListening : startListening}
                title={isListening ? "Stop recording" : "Speak to AI"}
              >
                {isListening ? <MicOff size={16} /> : <Mic size={16} />}
              </button>
              <label style={{ display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer', paddingRight: 4 }}>
                <input 
                  type="checkbox" 
                  checked={isAutoVoice}
                  onChange={(e) => setIsAutoVoice(e.target.checked)}
                  style={{ accentColor: 'var(--accent-purple)' }}
                />
                Auto
              </label>
            </div>
          )}

          <button
            className="chat-send-pill-btn"
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || isThinking}
            title="Send Message (Enter)"
          >
            <Send size={16} />
          </button>
        </div>

        <div className="chat-input-hints">
          <span>💡 Press <strong>Enter</strong> to send, <strong>Shift+Enter</strong> for a new line</span>
          <span>Autonomous Stylist • Color Matching Engine • Web Speech API</span>
        </div>
      </div>
    </div>
  )
}
