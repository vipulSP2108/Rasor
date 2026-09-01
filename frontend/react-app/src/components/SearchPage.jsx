import { useState } from 'react'
import { Search, Sliders, Grid, List, ChevronDown, ChevronUp, Package, Trash2, ChevronLeft, ChevronRight } from 'lucide-react'
import { searchProducts } from '../api/client'
import { useApp } from '../context/AppContext'
import ProductCard from './ProductCard'
import toast from 'react-hot-toast'
import { useEffect } from 'react'

const QUICK_SEARCHES = [
  'Black oversized t-shirt',
  'Marvel graphic tee',
  'Gym dry-fit top',
  'Polo shirts for men',
  'Pastel hoodie women',
]

export default function SearchPage({ onAddToCart }) {
  const { config } = useApp()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [discardedProducts, setDiscardedProducts] = useState([])
  const [evaluations, setEvaluations] = useState([])
  const [canonicalQuery, setCanonicalQuery] = useState(null)
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(false)
  const [loadingStage, setLoadingStage] = useState(0)
  const [layout, setLayout] = useState('grid')
  const [currentPage, setCurrentPage] = useState(1)
  const [showEval, setShowEval] = useState(false)
  const [showDiscarded, setShowDiscarded] = useState(false)
  const pageSize = 12

  useEffect(() => {
    let interval
    if (loading) {
      setLoadingStage(0)
      interval = setInterval(() => {
        setLoadingStage(s => Math.min(s + 1, 2))
      }, 2500)
    }
    return () => clearInterval(interval)
  }, [loading])

  const stages = [
    "🤖 Stage 1: LLM Normalized Taxonomy...",
    "📡 Stage 2: Querying catalog...",
    "👁️ Stage 3: Exhaustive VQA Scanning..."
  ]

  const runSearch = async (q = query) => {
    if (!q.trim()) return
    setLoading(true)
    setResults([])
    setDiscardedProducts([])
    setEvaluations([])
    setCanonicalQuery(null)
    setStatus(null)
    setCurrentPage(1)

    try {
      const { data } = await searchProducts({
        query: q,
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
      setResults(data.products || [])
      setDiscardedProducts(data.discarded_products || [])
      setEvaluations(data.evaluations || [])
      setCanonicalQuery(data.canonical_query)
      setStatus(data.status)
      if (!data.products?.length) toast('No matching products found', { icon: '🔍' })
    } catch (err) {
      toast.error('Search failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      {/* Search Box */}
      <div className="card" style={{ padding: '20px', marginBottom: 24 }}>
        <div className="flex gap-3" style={{ marginBottom: 14 }}>
          <div style={{ position: 'relative', flex: 1 }}>
            <Search size={16} style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input
              className="input"
              style={{ paddingLeft: 40 }}
              placeholder="e.g. Solid black t-shirt for men, oversized fit"
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && runSearch()}
            />
          </div>
          <button className="btn btn-primary" onClick={() => runSearch()} disabled={loading || !query.trim()}>
            {loading ? <span className="spinner" /> : <><Search size={16} /> Search</>}
          </button>
        </div>

        {/* Quick chips */}
        <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
          {QUICK_SEARCHES.map(q => (
            <button
              key={q}
              className="chat-chip"
              onClick={() => { setQuery(q); runSearch(q) }}
            >{q}</button>
          ))}
        </div>
      </div>

      {/* Canonical Query Badge */}
      {canonicalQuery && (
        <div className="alert alert-info" style={{ marginBottom: 16 }}>
          <Sliders size={16} />
          <span>
            <strong>Normalized Intent:</strong>{' '}
            {[
              canonicalQuery.gender && `Gender: ${canonicalQuery.gender}`,
              canonicalQuery.category && `Category: ${canonicalQuery.category}`,
              canonicalQuery.color && `Color: ${canonicalQuery.color}`,
              canonicalQuery.fit && `Fit: ${canonicalQuery.fit}`,
              canonicalQuery.design && `Design: ${canonicalQuery.design}`,
            ].filter(Boolean).join(' · ')}
          </span>
        </div>
      )}

      {/* Results */}
      {loading ? (
        <div className="loading-state">
          <div className="spinner" />
          <p>{stages[loadingStage]}</p>
        </div>
      ) : results.length > 0 ? (
        <>
          <div className="flex items-center justify-between" style={{ marginBottom: 16 }}>
            <span className="text-sm text-muted">{status}</span>
            <div className="flex gap-2">
              <button className={`btn btn-icon btn-ghost ${layout === 'grid' ? 'active' : ''}`} onClick={() => setLayout('grid')}><Grid size={16} /></button>
              <button className={`btn btn-icon btn-ghost ${layout === 'carousel' ? 'active' : ''}`} onClick={() => setLayout('carousel')}><List size={16} /></button>
            </div>
          </div>

          {layout === 'carousel' ? (
            <div className="product-carousel">
              {results.slice((currentPage - 1) * pageSize, currentPage * pageSize).map(p => <ProductCard key={p.id} product={p} onAddToCart={onAddToCart} />)}
            </div>
          ) : (
            <div className="product-grid">
              {results.slice((currentPage - 1) * pageSize, currentPage * pageSize).map(p => <ProductCard key={p.id} product={p} onAddToCart={onAddToCart} />)}
            </div>
          )}

          {/* Pagination */}
          {results.length > pageSize && (
            <div className="flex items-center justify-center gap-4" style={{ marginTop: 24 }}>
              <button 
                className="btn btn-outline" 
                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                disabled={currentPage === 1}
              >
                <ChevronLeft size={16} /> Previous
              </button>
              <span className="text-sm text-muted">Page {currentPage} of {Math.ceil(results.length / pageSize)}</span>
              <button 
                className="btn btn-outline" 
                onClick={() => setCurrentPage(p => Math.min(Math.ceil(results.length / pageSize), p + 1))}
                disabled={currentPage === Math.ceil(results.length / pageSize)}
              >
                Next <ChevronRight size={16} />
              </button>
            </div>
          )}
        </>
      ) : status ? (
        <div className="empty-state">
          <div className="empty-state-icon">🔍</div>
          <h3>No Results</h3>
          <p>{status}</p>
        </div>
      ) : null}

      {/* Debug Accordions */}
      {!loading && canonicalQuery && (
        <div style={{ marginTop: 40, borderTop: '1px solid var(--border)', paddingTop: 20 }}>
          
          <button 
            className="flex items-center justify-between w-full" 
            style={{ padding: '12px', background: 'var(--surface)', borderRadius: 8, marginBottom: 12, border: '1px solid var(--border)', cursor: 'pointer' }}
            onClick={() => setShowEval(!showEval)}
          >
            <div className="flex items-center gap-2">
              <Search size={16} color="var(--accent-blue)" />
              <strong>Inspect Raw Canonical Query & Evaluations</strong>
            </div>
            {showEval ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
          {showEval && (
            <div className="card" style={{ padding: 16, marginBottom: 20, fontSize: '13px' }}>
              <h4 style={{ margin: '0 0 10px 0' }}>Canonical Query Object:</h4>
              <pre style={{ background: 'var(--bg)', padding: 12, borderRadius: 4, overflowX: 'auto' }}>
                {JSON.stringify(canonicalQuery, null, 2)}
              </pre>
              
              <h4 style={{ margin: '20px 0 10px 0' }}>LLM Evaluations ({evaluations.length}):</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {evaluations.map((e, i) => (
                  <div key={i} style={{ padding: 8, background: 'var(--bg)', borderRadius: 4, borderLeft: e.match_score >= 0.8 ? '3px solid var(--accent-green)' : (e.match_score >= 0.5 ? '3px solid var(--accent-orange)' : '3px solid var(--accent-red)') }}>
                    <strong>{e.product_id}</strong> (Score: {e.match_score})<br/>
                    <span className="text-muted">{e.reasoning}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <button 
            className="flex items-center justify-between w-full" 
            style={{ padding: '12px', background: 'var(--surface)', borderRadius: 8, marginBottom: 12, border: '1px solid var(--border)', cursor: 'pointer' }}
            onClick={() => setShowDiscarded(!showDiscarded)}
          >
            <div className="flex items-center gap-2">
              <Trash2 size={16} color="var(--accent-red)" />
              <strong>View Discarded / Low Relevance Candidates ({discardedProducts.length})</strong>
            </div>
            {showDiscarded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
          {showDiscarded && (
            <div className="product-grid" style={{ opacity: 0.6 }}>
              {discardedProducts.map(p => <ProductCard key={p.id} product={p} onAddToCart={onAddToCart} />)}
            </div>
          )}

        </div>
      )}
    </div>
  )
}
