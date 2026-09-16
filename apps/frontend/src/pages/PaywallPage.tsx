import { Check } from 'lucide-react'
import { Link } from 'react-router-dom'

const plans = [
  { name: 'FREE', price: '₺0', features: ['Temel ders yönetimi', 'Not ve quiz akışları'], current: true },
  { name: 'PLUS', price: 'Yakında', features: ['Daha yüksek AI üretim kapasitesi', 'Öncelikli çalışma akışları'], yakinda: true },
  { name: 'PRO', price: 'Yakında', features: ['En yüksek AI kapasitesi', 'Gelişmiş çalışma araçları', 'Öncelikli özellik erişimi'], yakinda: true },
]

export function PaywallPage() {
  return (
    <section className="page-shell">
      <header className="page-header"><div><h1 className="page-title">Planını seç</h1><p className="page-subtitle">StuHub çalışma akışını ihtiyacına göre genişlet.</p></div><Link to="/" className="glass-panel-subtle glass-interactive rounded-control px-4 py-2 text-sm text-stuhub-text-secondary">Geri</Link></header>
      <div className="pricing-grid">
        {plans.map((plan) => (
          <article key={plan.name} className={`glass-panel plan-card ${plan.name === 'PLUS' ? 'plan-card--plus' : ''} ${plan.name === 'PRO' ? 'plan-card--pro' : ''}`}>
            <div><p className="eyebrow">{plan.name}</p><h2>{plan.price}</h2><div className="plan-features">{plan.features.map((f) => <p key={f}><Check size={15} aria-hidden="true" />{f}</p>)}</div></div>
            {/* K3: hazır olmayan plan tıklanabilir görünmesin — devre dışı + "Yakında" etiketi (gerçek checkout Aşama 2). */}
            <button type="button" className="glass-panel-subtle glass-interactive rounded-control px-4 py-2 text-sm" disabled={plan.current || plan.yakinda} aria-disabled={plan.current || plan.yakinda} title={plan.yakinda ? 'Bu plan henüz açılmadı' : undefined}>{plan.current ? 'Mevcut plan' : plan.yakinda ? 'Yakında' : `${plan.name}'a geç`}</button>
          </article>
        ))}
      </div>
    </section>
  )
}
