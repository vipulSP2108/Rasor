import React, { useState, useEffect } from 'react'
import ProductCard from './ProductCard'

export default function BatchedProductGrid({ 
  products = [], 
  onAddToCart, 
  layout = 'grid', // 'grid' | 'carousel' | 'history'
  batchSize = 4, 
  batchDelay = 130,
  innerRef
}) {
  const [renderedCount, setRenderedCount] = useState(() => Math.min(batchSize, products.length))

  useEffect(() => {
    // Reset to first batch whenever product list changes
    setRenderedCount(Math.min(batchSize, products.length))
    if (products.length <= batchSize) return

    let current = batchSize
    const timer = setInterval(() => {
      current += batchSize
      setRenderedCount(current)
      if (current >= products.length) {
        clearInterval(timer)
      }
    }, batchDelay)

    return () => clearInterval(timer)
  }, [products, batchSize, batchDelay])

  const visibleProducts = products.slice(0, renderedCount)
  const isProgressing = renderedCount < products.length

  const gridClass = layout === 'history' 
    ? 'history-product-grid' 
    : layout === 'carousel'
    ? 'product-carousel'
    : 'product-grid'

  return (
    <div>
      <div className={gridClass} ref={innerRef}>
        {visibleProducts.map((p, idx) => (
          <div 
            key={p.id || idx} 
            className="animate-slide-up"
            style={{ 
              animationDelay: `${(idx % batchSize) * 40}ms`,
              animationFillMode: 'both' 
            }}
          >
            <ProductCard product={p} onAddToCart={onAddToCart} layout={layout === 'carousel' ? 'carousel' : 'grid'} />
          </div>
        ))}
      </div>

      {isProgressing && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, padding: '10px 0', opacity: 0.75 }}>
          <span className="spinner spinner-sm" style={{ width: 14, height: 14 }} />
          <span className="text-xs text-muted">
            Loaded {visibleProducts.length} of {products.length} picks…
          </span>
        </div>
      )}
    </div>
  )
}
