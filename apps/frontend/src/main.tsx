import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import App from './App'
import { ErrorBoundary } from './components/ErrorBoundary'
import './styles/theme.css'
import './styles/personalization.css'

// Ilk-boya zemin kurali (index.html: `:not(.tema-hazir)`) artik devre disi:
// tema CSS'i yuklendi, zemin token'dan gelir → tek parlaklik dugmesi (dim)
// html zeminini de surer. applyTheme de ayni sinifi ekler (ayni sozlesme).
document.documentElement.classList.add('tema-hazir')

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ErrorBoundary>
  </StrictMode>,
)

// Sunucu tercihleri (tema/arka plan) artık App içinde, auth oturumu hazır olunca
// yüklenir — burada çağrıldığında token henüz yerleşmemişti (401 → konsol hatası).
