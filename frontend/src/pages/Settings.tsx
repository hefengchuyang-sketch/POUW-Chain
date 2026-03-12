import { useState, useEffect } from 'react'
import { useTranslation } from '../i18n'
import { 
  Settings as SettingsIcon, 
  Globe, 
  Bell, 
  Shield,
  Palette, 
  Monitor, 
  Moon, 
  Sun, 
  Database, 
  Save,
  Check,
  Volume2,
  Clock,
  Zap,
  Eye
} from 'lucide-react'

// 设置类型
interface SettingsState {
  general: {
    language: string
    timezone: string
    currency: string
  }
  appearance: {
    theme: 'dark' | 'light' | 'system'
    compactMode: boolean
    animations: boolean
  }
  notifications: {
    taskUpdates: boolean
    orderAlerts: boolean
    securityWarnings: boolean
    marketAlerts: boolean
    sound: boolean
  }
  network: {
    rpcEndpoint: string
    autoConnect: boolean
  }
  privacy: {
    hideBalance: boolean
    transactionConfirm: boolean
    autoLock: string
  }
}

const defaultSettings: SettingsState = {
  general: {
    language: 'zh-CN',
    timezone: 'Asia/Shanghai',
    currency: 'USD',
  },
  appearance: {
    theme: 'dark',
    compactMode: false,
    animations: true,
  },
  notifications: {
    taskUpdates: true,
    orderAlerts: true,
    securityWarnings: true,
    marketAlerts: false,
    sound: true,
  },
  network: {
    rpcEndpoint: window.location.origin || 'http://localhost:8545',
    autoConnect: true,
  },
  privacy: {
    hideBalance: false,
    transactionConfirm: true,
    autoLock: '15',
  },
}

const languages = [
  { value: 'zh-CN', label: '简体中文' },
  { value: 'en-US', label: 'English' },
  { value: 'ja-JP', label: '日本語' },
  { value: 'ko-KR', label: '한국어' },
]

const timezones = [
  { value: 'Asia/Shanghai', labelKey: 'timezones.Asia/Shanghai' },
  { value: 'Asia/Tokyo', labelKey: 'timezones.Asia/Tokyo' },
  { value: 'America/New_York', labelKey: 'timezones.America/New_York' },
  { value: 'Europe/London', labelKey: 'timezones.Europe/London' },
]

const currencies = [
  { value: 'USD', labelKey: 'currencies.USD' },
  { value: 'CNY', labelKey: 'currencies.CNY' },
  { value: 'EUR', labelKey: 'currencies.EUR' },
  { value: 'JPY', labelKey: 'currencies.JPY' },
]

const sections = [
  { id: 'general', labelKey: 'settings.general', icon: Globe },
  { id: 'appearance', labelKey: 'settings.appearance', icon: Palette },
  { id: 'notifications', labelKey: 'settings.notifications', icon: Bell },
  { id: 'network', labelKey: 'settings.network', icon: Database },
  { id: 'privacy', labelKey: 'settings.privacy', icon: Shield },
]

// 应用主题到 document
function applyTheme(theme: 'dark' | 'light' | 'system') {
  const root = document.documentElement
  if (theme === 'system') {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    root.classList.toggle('dark', prefersDark)
    root.classList.toggle('light', !prefersDark)
  } else {
    root.classList.toggle('dark', theme === 'dark')
    root.classList.toggle('light', theme === 'light')
  }
}

export default function Settings() {
  const { t } = useTranslation()
  const [settings, setSettings] = useState<SettingsState>(() => {
    try {
      const saved = localStorage.getItem('settings')
      return saved ? { ...defaultSettings, ...JSON.parse(saved) } : defaultSettings
    } catch {
      return defaultSettings
    }
  })
  const [activeSection, setActiveSection] = useState<string>('general')
  const [hasChanges, setHasChanges] = useState(false)
  const [saved, setSaved] = useState(false)

  // 主题初始化与监听系统偏好变化
  useEffect(() => {
    applyTheme(settings.appearance.theme)
    if (settings.appearance.theme === 'system') {
      const mq = window.matchMedia('(prefers-color-scheme: dark)')
      const handler = () => applyTheme('system')
      mq.addEventListener('change', handler)
      return () => mq.removeEventListener('change', handler)
    }
  }, [settings.appearance.theme])

  // 动画开关
  useEffect(() => {
    document.documentElement.classList.toggle('no-animations', !settings.appearance.animations)
  }, [settings.appearance.animations])

  // 紧凑模式
  useEffect(() => {
    document.documentElement.classList.toggle('compact', settings.appearance.compactMode)
  }, [settings.appearance.compactMode])

  const updateSettings = <K extends keyof SettingsState>(
    section: K,
    key: keyof SettingsState[K],
    value: SettingsState[K][keyof SettingsState[K]]
  ) => {
    setSettings(prev => ({
      ...prev,
      [section]: {
        ...prev[section],
        [key]: value,
      },
    }))
    setHasChanges(true)
    setSaved(false)
  }

  const handleSave = () => {
    // 保存设置到 localStorage
    localStorage.setItem('settings', JSON.stringify(settings))
    window.dispatchEvent(new Event('settings-changed'))
    setHasChanges(false)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const handleReset = () => {
    setSettings(defaultSettings)
    setHasChanges(true)
  }

  return (
    <div className="flex gap-6 h-full">
      {/* 左侧导航 */}
      <div className="w-56 shrink-0">
        <h1 className="text-xl font-bold text-console-text mb-4 flex items-center gap-2">
          <SettingsIcon size={20} />
          {t('settings.title')}
        </h1>
        <nav className="space-y-1">
          {sections.map(section => {
            const Icon = section.icon
            return (
              <button
                key={section.id}
                onClick={() => setActiveSection(section.id)}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-left transition-colors ${
                  activeSection === section.id
                    ? 'bg-console-accent/10 text-console-accent border-l-2 border-console-accent'
                    : 'text-console-text-muted hover:bg-console-surface hover:text-console-text'
                }`}
              >
                <Icon size={18} />
                {t(section.labelKey)}
              </button>
            )
          })}
        </nav>
      </div>

      {/* 右侧内容 */}
      <div className="flex-1 space-y-6">
        {/* 通用设置 */}
        {activeSection === 'general' && (
          <section className="card">
            <h2 className="text-lg font-semibold text-console-text mb-6 flex items-center gap-2">
              <Globe size={20} className="text-console-accent" />
              {t('settings.general')}
            </h2>
            
            <div className="space-y-6">
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-console-text mb-2">
                    {t('settings.language')}
                  </label>
                  <select
                    value={settings.general.language}
                    onChange={(e) => {
                      updateSettings('general', 'language', e.target.value)
                      // 语言立即生效：写入 localStorage 并通知 i18n
                      const current = JSON.parse(localStorage.getItem('settings') || '{}')
                      current.general = { ...current.general, language: e.target.value }
                      localStorage.setItem('settings', JSON.stringify(current))
                      window.dispatchEvent(new Event('settings-changed'))
                    }}
                    className="input"
                  >
                    {languages.map(lang => (
                      <option key={lang.value} value={lang.value}>{lang.label}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-console-text mb-2">
                    {t('settings.timezone')}
                  </label>
                  <select
                    value={settings.general.timezone}
                    onChange={(e) => updateSettings('general', 'timezone', e.target.value)}
                    className="input"
                  >
                    {timezones.map(tz => (
                      <option key={tz.value} value={tz.value}>{t(tz.labelKey)}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-console-text mb-2">
                  {t('settings.currency')}
                </label>
                <select
                  value={settings.general.currency}
                  onChange={(e) => updateSettings('general', 'currency', e.target.value)}
                  className="input w-64"
                >
                  {currencies.map(curr => (
                    <option key={curr.value} value={curr.value}>{t(curr.labelKey)}</option>
                  ))}
                </select>
              </div>
            </div>
          </section>
        )}

        {/* 外观设置 */}
        {activeSection === 'appearance' && (
          <section className="card">
            <h2 className="text-lg font-semibold text-console-text mb-6 flex items-center gap-2">
              <Palette size={20} className="text-console-accent" />
              {t('settings.appearance')}
            </h2>

            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-console-text mb-3">
                  {t('settings.theme')}
                </label>
                <div className="flex gap-3">
                  {[
                    { value: 'dark', label: t('settings.themeDark'), icon: Moon },
                    { value: 'light', label: t('settings.themeLight'), icon: Sun },
                    { value: 'system', label: t('settings.themeSystem'), icon: Monitor },
                  ].map(theme => {
                    const Icon = theme.icon
                    return (
                      <button
                        key={theme.value}
                        onClick={() => updateSettings('appearance', 'theme', theme.value as 'dark' | 'light' | 'system')}
                        className={`flex items-center gap-2 px-4 py-3 rounded-lg border transition-colors ${
                          settings.appearance.theme === theme.value
                            ? 'border-console-accent bg-console-accent/10 text-console-accent'
                            : 'border-console-border text-console-text-muted hover:border-console-text-muted'
                        }`}
                      >
                        <Icon size={18} />
                        {theme.label}
                      </button>
                    )
                  })}
                </div>
              </div>

              <SettingToggle
                icon={Zap}
                label={t('settings.compactMode')}
                description={t('settings.compactModeDesc')}
                checked={settings.appearance.compactMode}
                onChange={(checked) => updateSettings('appearance', 'compactMode', checked)}
              />

              <SettingToggle
                icon={Zap}
                label={t('settings.animations')}
                description={t('settings.animationsDesc')}
                checked={settings.appearance.animations}
                onChange={(checked) => updateSettings('appearance', 'animations', checked)}
              />
            </div>
          </section>
        )}

        {/* 通知设置 */}
        {activeSection === 'notifications' && (
          <section className="card">
            <h2 className="text-lg font-semibold text-console-text mb-6 flex items-center gap-2">
              <Bell size={20} className="text-console-accent" />
              {t('settings.notifications')}
            </h2>

            <div className="space-y-4">
              <SettingToggle
                icon={Bell}
                label={t('settings.taskUpdateNotify')}
                description={t('settings.taskUpdateNotifyDesc')}
                checked={settings.notifications.taskUpdates}
                onChange={(checked) => updateSettings('notifications', 'taskUpdates', checked)}
              />

              <SettingToggle
                icon={Bell}
                label={t('settings.orderAlerts')}
                description={t('settings.orderAlertsDesc')}
                checked={settings.notifications.orderAlerts}
                onChange={(checked) => updateSettings('notifications', 'orderAlerts', checked)}
              />

              <SettingToggle
                icon={Shield}
                label={t('settings.securityWarnings')}
                description={t('settings.securityWarningsDesc')}
                checked={settings.notifications.securityWarnings}
                onChange={(checked) => updateSettings('notifications', 'securityWarnings', checked)}
              />

              <SettingToggle
                icon={Bell}
                label={t('settings.marketAlerts')}
                description={t('settings.marketAlertsDesc')}
                checked={settings.notifications.marketAlerts}
                onChange={(checked) => updateSettings('notifications', 'marketAlerts', checked)}
              />

              <SettingToggle
                icon={Volume2}
                label={t('settings.soundNotify')}
                description={t('settings.soundNotifyDesc')}
                checked={settings.notifications.sound}
                onChange={(checked) => updateSettings('notifications', 'sound', checked)}
              />
            </div>
          </section>
        )}

        {/* 网络设置 */}
        {activeSection === 'network' && (
          <section className="card">
            <h2 className="text-lg font-semibold text-console-text mb-6 flex items-center gap-2">
              <Database size={20} className="text-console-accent" />
              {t('settings.network')}
            </h2>

            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-console-text mb-2">
                  {t('settings.rpcEndpoint')}
                </label>
                <input
                  type="text"
                  value={settings.network.rpcEndpoint}
                  onChange={(e) => updateSettings('network', 'rpcEndpoint', e.target.value)}
                  className="input"
                  placeholder={t('settings.rpcPlaceholder')}
                />
                <p className="text-xs text-console-text-muted mt-2">
                  {t('settings.rpcHint')}
                </p>
              </div>

              <SettingToggle
                icon={Database}
                label={t('settings.autoConnect')}
                description={t('settings.autoConnectDesc')}
                checked={settings.network.autoConnect}
                onChange={(checked) => updateSettings('network', 'autoConnect', checked)}
              />
            </div>
          </section>
        )}

        {/* 隐私设置 */}
        {activeSection === 'privacy' && (
          <section className="card">
            <h2 className="text-lg font-semibold text-console-text mb-6 flex items-center gap-2">
              <Shield size={20} className="text-console-accent" />
              {t('settings.privacy')}
            </h2>

            <div className="space-y-6">
              <SettingToggle
                icon={Eye}
                label={t('settings.hideBalance')}
                description={t('settings.hideBalanceDesc')}
                checked={settings.privacy.hideBalance}
                onChange={(checked) => updateSettings('privacy', 'hideBalance', checked)}
              />

              <SettingToggle
                icon={Shield}
                label={t('settings.txConfirm')}
                description={t('settings.txConfirmDesc')}
                checked={settings.privacy.transactionConfirm}
                onChange={(checked) => updateSettings('privacy', 'transactionConfirm', checked)}
              />

              <div>
                <label className="block text-sm font-medium text-console-text mb-2 flex items-center gap-2">
                  <Clock size={16} />
                  {t('settings.autoLockTime')}
                </label>
                <select
                  value={settings.privacy.autoLock}
                  onChange={(e) => updateSettings('privacy', 'autoLock', e.target.value)}
                  className="input w-48"
                >
                  <option value="5">{t('settings.min5')}</option>
                  <option value="15">{t('settings.min15')}</option>
                  <option value="30">{t('settings.min30')}</option>
                  <option value="60">{t('settings.hour1')}</option>
                  <option value="never">{t('settings.never')}</option>
                </select>
              </div>
            </div>
          </section>
        )}

        {/* 保存按钮 */}
        <div className="flex items-center justify-end gap-3 pt-4 border-t border-console-border">
          <button 
            onClick={handleReset}
            className="btn-secondary"
            disabled={!hasChanges}
          >
            {t('settings.resetDefault')}
          </button>
          <button 
            onClick={handleSave}
            className={`btn-primary flex items-center gap-2 ${saved ? 'bg-green-600' : ''}`}
            disabled={!hasChanges && !saved}
          >
            {saved ? (
              <>
                <Check size={16} />
                {t('common.saved')}
              </>
            ) : (
              <>
                <Save size={16} />
                {t('settings.saveSettings')}
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

// 设置开关组件
function SettingToggle({
  icon: Icon,
  label,
  description,
  checked,
  onChange,
}: {
  icon: React.ComponentType<{ size?: number | string; className?: string }>
  label: string
  description: string
  checked: boolean
  onChange: (checked: boolean) => void
}) {
  return (
    <div className="flex items-center justify-between p-4 bg-console-bg rounded-lg border border-console-border">
      <div className="flex items-center gap-3">
        <Icon size={20} className="text-console-text-muted" />
        <div>
          <div className="font-medium text-console-text">{label}</div>
          <div className="text-sm text-console-text-muted">{description}</div>
        </div>
      </div>
      <label className="relative inline-flex items-center cursor-pointer">
        <input 
          type="checkbox" 
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          className="sr-only peer" 
        />
        <div className="w-11 h-6 bg-console-border rounded-full peer peer-checked:bg-console-accent peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-0.5 after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all" />
      </label>
    </div>
  )
}
