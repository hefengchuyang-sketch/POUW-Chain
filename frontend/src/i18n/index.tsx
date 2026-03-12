import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import zhCN from './zh-CN'
import enUS from './en-US'
import type { TranslationKeys } from './zh-CN'

const translations: Record<string, TranslationKeys> = {
  'zh-CN': zhCN,
  'en-US': enUS,
}

function getStoredLanguage(): string {
  try {
    const raw = localStorage.getItem('settings')
    if (raw) {
      const parsed = JSON.parse(raw)
      if (parsed?.general?.language && translations[parsed.general.language]) {
        return parsed.general.language
      }
    }
  } catch { /* ignore */ }
  return 'zh-CN'
}

// 嵌套取值
function getNestedValue(obj: Record<string, unknown>, path: string): string {
  const keys = path.split('.')
  let current: unknown = obj
  for (const key of keys) {
    if (current == null || typeof current !== 'object') return path
    current = (current as Record<string, unknown>)[key]
  }
  return typeof current === 'string' ? current : path
}

interface I18nContextType {
  language: string
  setLanguage: (lang: string) => void
  t: (key: string) => string
}

const I18nContext = createContext<I18nContextType>({
  language: 'zh-CN',
  setLanguage: () => {},
  t: (key) => key,
})

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState(getStoredLanguage)

  const setLanguage = useCallback((lang: string) => {
    if (!translations[lang]) return
    setLanguageState(lang)
  }, [])

  // 监听 settings 变化（Settings 页面保存时触发）
  useEffect(() => {
    const handler = () => setLanguageState(getStoredLanguage())
    window.addEventListener('settings-changed', handler)
    window.addEventListener('storage', handler)
    return () => {
      window.removeEventListener('settings-changed', handler)
      window.removeEventListener('storage', handler)
    }
  }, [])

  const t = useCallback((key: string): string => {
    const dict = translations[language] || zhCN
    const val = getNestedValue(dict as unknown as Record<string, unknown>, key)
    if (val !== key) return val
    // fallback to zh-CN
    if (language !== 'zh-CN') {
      return getNestedValue(zhCN as unknown as Record<string, unknown>, key)
    }
    return key
  }, [language])

  return (
    <I18nContext.Provider value={{ language, setLanguage, t }}>
      {children}
    </I18nContext.Provider>
  )
}

export function useTranslation() {
  return useContext(I18nContext)
}

export default I18nProvider
