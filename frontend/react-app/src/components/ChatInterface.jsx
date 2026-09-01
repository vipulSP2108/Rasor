import { useState, useRef, useEffect } from 'react'
import { Send, Trash2, Mic, MicOff, Volume2 } from 'lucide-react'
import { chatMessage, clearChat, searchProducts } from '../api/client'
import { useApp } from '../context/AppContext'
import { useVoice } from '../hooks/useVoice'
import ProductCard from './ProductCard'
import toast from 'react-hot-toast'

const SESSION_ID = 'rasor-stylist'

const INITIAL_MESSAGES = [
  {
    role: 'assistant',
    content: "Welcome to **Rasor**! I'm your AI personal stylist. 🛍️ Tell me what you're looking for — I'll ask just a few smart questions to find the perfect match for you.",
    suggestedOptions: ['Show me men\'s t-shirts', 'Marvel fan merch', 'Something for the gym', 'Surprise me 🎲'],
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
  const { isListening, transcript, startListening, stopListening, speak, stopSpeaking, resetTranscript } = useVoice()
  const endRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, isThinking])

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
    setInput('')
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
      setMessages(prev => [...prev, assistantMsg])

      // Auto-play voice if enabled
      if (config.voiceEnabled) {
        speak(data.message, config.voiceURI, () => {
          if (isAutoVoice) {
            startListening()
          }
        })
      }

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
          setSearchResults(searchData.products || [])
          if (searchData.products?.length > 0) {
            setMessages(prev => [...prev, {
              role: 'assistant',
              content: `✨ Found **${searchData.products.length}** perfect matches for you! Here are your top picks:`,
            }])
          } else {
            setMessages(prev => [...prev, {
              role: 'assistant',
              content: "Hmm, I couldn't find products matching those exact criteria. Want to try a different description?",
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
      setMessages(prev => [...prev, { role: 'assistant', content: "Sorry, I ran into an issue. Could you try again?" }])
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
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(input) }
  }

  return (
    <div className="chat-container">
      {/* Messages */}
      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`chat-message ${msg.role}`}>
            <div className={`chat-avatar ${msg.role}`}>
              {msg.role === 'assistant' ? '🤖' : '👤'}
            </div>
            <div>
              <div className={`chat-bubble ${msg.role}`}>
                <span dangerouslySetInnerHTML={{
                  __html: msg.content
                    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                    .replace(/\n/g, '<br/>')
                }} />
              </div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 4 }}>
                {msg.role === 'assistant' && (
                  <button className="btn btn-ghost btn-sm" style={{ padding: 4, height: 'auto', color: 'var(--text-muted)' }} onClick={() => speak(msg.content, config.voiceURI)}>
                    <Volume2 size={14} />
                  </button>
                )}
                {msg.suggestedOptions?.length > 0 && i === messages.length - 1 && (
                  <div className="chat-chips">
                    {msg.suggestedOptions.map((opt, j) => (
                      <button key={j} className="chat-chip" onClick={() => handleChipClick(opt)}>
                        {opt}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}

        {isThinking && (
          <div className="chat-message assistant">
            <div className="chat-avatar assistant">🤖</div>
            <div className="typing-indicator">
              <div className="typing-dot" />
              <div className="typing-dot" />
              <div className="typing-dot" />
            </div>
          </div>
        )}

        {isSearching && (
          <div className="loading-state" style={{ padding: '20px 0' }}>
            <div className="spinner" style={{ borderTopColor: 'var(--accent-green)' }} />
            <span className="text-sm text-muted">Searching catalog…</span>
          </div>
        )}

        {searchResults && searchResults.length > 0 && (
          <div className="animate-slide-up" style={{ paddingTop: 8 }}>
            <div className="product-carousel">
              {searchResults.map(p => (
                <ProductCard key={p.id} product={p} onAddToCart={onAddToCart} layout="carousel" />
              ))}
            </div>
          </div>
        )}

        <div ref={endRef} />
      </div>

      {/* Input area */}
      <div className="chat-input-area">
        <button className="btn btn-ghost btn-icon" onClick={handleClear} title="Clear chat">
          <Trash2 size={16} />
        </button>
        <textarea
          ref={inputRef}
          className="chat-input"
          style={{ minHeight: '60px' }}
          value={input}
          onChange={e => { setInput(e.target.value); resetTranscript() }}
          onKeyDown={handleKeyDown}
          placeholder={isListening ? "Listening..." : "Tell me what you're looking for…"}
          rows={3}
          disabled={isThinking}
        />
        {config.voiceEnabled && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, background: 'var(--surface)', padding: '4px', borderRadius: '100px', border: '1px solid var(--border)' }}>
            <button 
              className={`btn btn-icon ${isListening ? 'pulsing' : 'btn-ghost'}`} 
              onClick={isListening ? stopListening : startListening}
              style={{ color: isListening ? 'var(--accent-red)' : 'var(--text-muted)' }}
              title="Toggle Mic"
            >
              {isListening ? <MicOff size={18} /> : <Mic size={18} />}
            </button>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.75rem', color: 'var(--text-muted)', cursor: 'pointer', paddingRight: 8 }}>
              <input 
                type="checkbox" 
                checked={isAutoVoice}
                onChange={(e) => setIsAutoVoice(e.target.checked)}
              />
              Auto
            </label>
          </div>
        )}
        <button
          className="chat-send-btn"
          onClick={() => sendMessage(input)}
          disabled={!input.trim() || isThinking}
        >
          <Send size={18} />
        </button>
      </div>
    </div>
  )
}
