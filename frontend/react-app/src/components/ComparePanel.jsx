import { useState } from 'react'
import { compareProducts } from '../api/client'
import { X } from 'lucide-react'
import { useApp } from '../context/AppContext'
import toast from 'react-hot-toast'

export default function ComparePanel() {
  const { compareList, clearCompare, toggleCompare } = useApp()
  const [comparison, setComparison] = useState(null)
  const [loading, setLoading] = useState(false)
  const products = Object.values(compareList)

  const runCompare = async () => {
    if (products.length < 2) return
    setLoading(true)
    try {
      const { data } = await compareProducts({ products })
      setComparison(data)
    } catch (err) {
      toast.error('Comparison failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  if (products.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">⚖️</div>
        <h3>No Products Selected</h3>
        <p>Use the compare button on any product card to add items here. Select 2–5 products.</p>
      </div>
    )
  }

  return (
    <div>
      <div className="page-title">⚖️ Compare Products</div>
      <p className="page-subtitle">{products.length} products selected</p>

      {/* Thumbnails */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 20 }}>
        {products.map(p => (
          <div key={p.id} style={{ position: 'relative' }}>
            <img
              src={p.specs?.display_image || p.specs?.image_url || ''}
              alt={p.title}
              style={{ width: 72, height: 88, objectFit: 'cover', borderRadius: 8, border: '1px solid var(--border)' }}
            />
            <button
              onClick={() => toggleCompare(p)}
              style={{
                position: 'absolute', top: -6, right: -6,
                background: 'var(--accent-red)', border: 'none', borderRadius: '50%',
                width: 20, height: 20, color: '#fff', cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}
            >
              <X size={11} />
            </button>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 10, marginBottom: 24 }}>
        <button className="btn btn-primary" onClick={runCompare} disabled={loading || products.length < 2}>
          {loading ? <span className="spinner" /> : '🤖 AI Compare'}
        </button>
        <button className="btn btn-ghost" onClick={() => { clearCompare(); setComparison(null) }}>
          Clear All
        </button>
      </div>

      {comparison && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Summary */}
          <div className="alert alert-info">
            💡 <span dangerouslySetInnerHTML={{ __html: comparison.quick_summary?.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') }} />
          </div>

          {/* Feature Matrix */}
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                <thead>
                  <tr style={{ background: 'var(--bg-elevated)' }}>
                    <th style={{ padding: '12px 16px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600 }}>Feature</th>
                    {products.map(p => (
                      <th key={p.id} style={{ padding: '12px 16px', textAlign: 'left', color: 'var(--text-primary)', fontWeight: 600 }}>
                        {p.title.slice(0, 25)}…
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {comparison.feature_matrix?.map((row, i) => (
                    <tr key={i} style={{ borderTop: '1px solid var(--border)' }}>
                      <td style={{ padding: '10px 16px', color: 'var(--text-secondary)', fontWeight: 500 }}>{row.feature_name}</td>
                      {products.map(p => (
                        <td key={p.id} style={{ padding: '10px 16px' }}>{row.product_values?.[p.title] || '—'}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Pros & Cons */}
          <div style={{ display: 'grid', gridTemplateColumns: `repeat(${products.length}, 1fr)`, gap: 14 }}>
            {products.map(p => {
              const pc = comparison.pros_and_cons?.find(x => x.product_title === p.title)
              return (
                <div key={p.id} className="card" style={{ padding: 16 }}>
                  <div style={{ fontWeight: 700, marginBottom: 10, fontSize: '0.85rem' }}>{p.title.slice(0, 30)}…</div>
                  {pc?.pros?.map((pro, j) => <div key={j} style={{ fontSize: '0.8rem', color: 'var(--accent-green)', marginBottom: 4 }}>✅ {pro}</div>)}
                  {pc?.cons?.map((con, j) => <div key={j} style={{ fontSize: '0.8rem', color: 'var(--accent-red)', marginBottom: 4 }}>❌ {con}</div>)}
                </div>
              )
            })}
          </div>

          {/* Recommendation */}
          {comparison.stylist_recommendation && (
            <div className="card" style={{ padding: 20 }}>
              <div style={{ fontWeight: 700, marginBottom: 12 }}>🎯 Stylist Recommendation</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 10 }}>
                {Object.entries(comparison.stylist_recommendation).map(([cat, rec]) => (
                  <div key={cat} className="alert alert-success">
                    <div><strong>{cat}</strong><br />{rec}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
