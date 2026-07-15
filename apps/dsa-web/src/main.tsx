import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { ThemeProvider } from './components/theme/ThemeProvider'
import { UiLanguageProvider } from './contexts/UiLanguageContext'
import { UiPreferencesProvider } from './contexts/UiPreferencesContext'
import { renderAfterI18nInitialization } from './i18n/bootstrap'

void renderAfterI18nInitialization(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <ThemeProvider>
        <UiLanguageProvider>
          <UiPreferencesProvider>
            <App />
          </UiPreferencesProvider>
        </UiLanguageProvider>
      </ThemeProvider>
    </StrictMode>,
  )
})
