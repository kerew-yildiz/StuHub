import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import App from './App'
import { ErrorBoundary } from './components/ErrorBoundary'
import { applyBackgroundFromSettings } from './lib/personalization'
import './styles/theme.css'
import './styles/personalization.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ErrorBoundary>
  </StrictMode>,
)

// Kayitli arkaplani uygula — acilisi bloklamaz (fire-and-forget).
void applyBackgroundFromSettings()
