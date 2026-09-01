import { ShoppingCart, X, Scale } from 'lucide-react'
import { useApp } from '../context/AppContext'

export default function Topbar({ onOpenCart, onNavigate }) {
  const { cart, compareList } = useApp()

  return (
    <header className="topbar">
      <div className="topbar-left">
        <div className="topbar-status">
          <span className="status-dot" />
          <span>Rasor Agent Live</span>
        </div>
      </div>

      <div className="topbar-right">
        {/* Compare button */}
        {Object.keys(compareList).length >= 2 && (
          <button className="btn btn-ghost btn-sm" onClick={() => onNavigate('compare')}>
            <Scale size={15} />
            Compare ({Object.keys(compareList).length})
          </button>
        )}

        {/* Cart */}
        <div className="cart-btn-wrapper">
          <button className="btn btn-secondary btn-sm" onClick={onOpenCart}>
            <ShoppingCart size={16} />
            Cart
          </button>
          {cart.quantity > 0 && (
            <span className="cart-badge">{cart.quantity}</span>
          )}
        </div>
      </div>
    </header>
  )
}
