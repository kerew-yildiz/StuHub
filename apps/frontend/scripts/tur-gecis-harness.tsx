/**
 * Tur adım geçişi ölçüm sahnesi (yalnız ölçüm içindir; üretim paketine girmez).
 *
 * Neden var: ölçüm sürücüsü (tur-gecis-olcum.mjs) gerçek Dev sunucu olmadan,
 * dosya:// üzerinden koşar. Sahne, /takvim'deki rehberli turun (global tur,
 * 5 adım) anchor geometrisini taklit eder: sidebar 72px (üstte arama, altta
 * profil) + header sağ üstte üç ikon. Adımlar ve konumlandırma GERÇEK
 * TourOverlay'den gelir — sahnede yalnız anchor yerleşimi vardır.
 */
import { useState } from 'react'
import { createRoot } from 'react-dom/client'

import { TourOverlay } from '../src/tour/TourOverlay'

const SIDEBAR_GENISLIK = 72
const HEADER_YUKSEKLIK = 70

const ikonStil = { width: 40, height: 40, borderRadius: 10, border: '1px solid #333', background: '#1b1b1b', color: '#ddd' }

function Sahne() {
  return (
    <>
      <aside
        style={{
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          width: SIDEBAR_GENISLIK,
          borderRight: '1px solid #262626',
          background: '#111',
        }}
      >
        <button type="button" data-tour-id="global-search" style={{ ...ikonStil, width: 56, margin: 8 }}>
          Ara
        </button>
        <div style={{ position: 'absolute', bottom: 12, left: 8 }}>
          <button type="button" data-tour-id="profile-trigger" style={{ ...ikonStil, width: 56 }}>
            Hesap
          </button>
        </div>
      </aside>
      <header
        style={{
          position: 'fixed',
          left: SIDEBAR_GENISLIK,
          right: 0,
          top: 0,
          height: HEADER_YUKSEKLIK,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
          gap: 12,
          paddingRight: 24,
          borderBottom: '1px solid #262626',
          background: '#141414',
        }}
      >
        <button type="button" data-tour-id="help-button" style={ikonStil}>
          ?
        </button>
        <button type="button" data-tour-id="notification-button" style={ikonStil}>
          B
        </button>
        <button type="button" data-tour-id="browser-fullscreen-button" style={ikonStil}>
          F
        </button>
      </header>
      <section style={{ margin: `${HEADER_YUKSEKLIK + 24}px 24px 24px ${SIDEBAR_GENISLIK + 24}px` }}>
        <h1 style={{ fontSize: 22 }}>Ölçüm sahnesi — takvim rehberli tur geometrisi</h1>
        <p style={{ color: '#9a9a9a' }}>Bu sayfa yalnız ölçüm koşumu içindir; ürün ekranı değildir.</p>
      </section>
    </>
  )
}

function Olcum() {
  const [open, setOpen] = useState(true)
  return (
    <>
      <Sahne />
      <TourOverlay layer="global" open={open} onClose={() => setOpen(false)} />
    </>
  )
}

createRoot(document.getElementById('kok') as HTMLElement).render(<Olcum />)
