import { useState, useEffect } from 'react'
import { 
  Key, 
  Shield, 
  Smartphone,
  Download,
  Trash2,
  RefreshCw,
  Eye,
  EyeOff,
  Copy,
  Check,
  AlertTriangle,
  Lock,
  ChevronRight,
  Fingerprint,
  Monitor,
  Clock,
  Loader2
} from 'lucide-react'
import { walletApi, type WalletInfo } from '../api'
import { useTranslation } from '../i18n'

interface DeviceInfo {
  id: string
  name: string
  type: 'desktop' | 'mobile' | 'browser'
  lastActive: string
  isCurrent: boolean
  ip: string
}

export default function Account() {
  const { t } = useTranslation()
  const [showPrivateKey, setShowPrivateKey] = useState(false)
  const [copied, setCopied] = useState<string | null>(null)
  const [showExportModal, setShowExportModal] = useState(false)
  const [showRevokeModal, setShowRevokeModal] = useState(false)
  const [selectedDevice, setSelectedDevice] = useState<DeviceInfo | null>(null)
  const [walletInfo, setWalletInfo] = useState<WalletInfo | null>(null)
  const [loading, setLoading] = useState(true)

  // 设备列表（当前会话）
  const [devices] = useState<DeviceInfo[]>([
    { 
      id: '1', 
      name: `${navigator.platform} - ${navigator.userAgent.includes('Chrome') ? 'Chrome' : 'Browser'}`, 
      type: 'desktop', 
      lastActive: t('account.current'), 
      isCurrent: true, 
      ip: t('account.current') 
    },
  ])

  // 加载钱包信息
  useEffect(() => {
    const loadWalletInfo = async () => {
      setLoading(true)
      try {
        const info = await walletApi.getInfo()
        setWalletInfo(info)
      } catch (error) {
        console.error('加载钱包信息失败:', error)
      } finally {
        setLoading(false)
      }
    }
    loadWalletInfo()
  }, [])

  // 真实数据
  const publicKey = walletInfo?.address || ''

  const handleCopy = (text: string, type: string) => {
    navigator.clipboard.writeText(text)
    setCopied(type)
    setTimeout(() => setCopied(null), 2000)
  }

  const handleRevokeDevice = async () => {
    // 设备撤销 — 清除本地会话数据
    if (selectedDevice) {
      try {
        // 如果是当前设备，执行断开连接
        if (selectedDevice.isCurrent) {
          localStorage.removeItem('pouw_wallet_mnemonic') // 清除旧版本残留
          localStorage.removeItem('pouw_connected')
          localStorage.removeItem('wallet_address')
          window.location.href = '/connect'
          return
        }
      } catch (err) {
        console.error('设备撤销失败:', err)
      }
    }
    setShowRevokeModal(false)
    setSelectedDevice(null)
  }

  const getDeviceIcon = (type: string) => {
    switch (type) {
      case 'desktop': return <Monitor size={20} />
      case 'mobile': return <Smartphone size={20} />
      default: return <Monitor size={20} />
    }
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <h1 className="text-2xl font-bold text-console-text">{t('account.title')}</h1>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-console-accent" />
          <span className="ml-3 text-console-text-muted">{t('common.loading')}</span>
        </div>
      ) : (
      <>
      {/* 身份信息 */}
      <section className="card">
        <h2 className="text-lg font-semibold text-console-text mb-4 flex items-center gap-2">
          <Fingerprint size={20} className="text-console-accent" />
          {t('account.identityInfo')}
        </h2>
        
        <div className="space-y-4">
          {/* 公钥地址 */}
          <div className="p-4 bg-console-bg rounded-lg border border-console-border">
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm text-console-text-muted">{t('account.walletAddress')}</label>
              <button 
                onClick={() => handleCopy(publicKey, 'public')}
                className="btn-ghost p-1"
              >
                {copied === 'public' ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
              </button>
            </div>
            <div className="font-mono text-console-text break-all">{publicKey}</div>
          </div>

          {/* 板块地址列表 */}
          {walletInfo?.sectorAddresses && Object.keys(walletInfo.sectorAddresses).length > 0 && (
            <div className="p-4 bg-console-bg rounded-lg border border-console-border">
              <label className="text-sm text-console-text-muted mb-3 block">{t('account.sectorAddress')}</label>
              <div className="space-y-2">
                {Object.entries(walletInfo.sectorAddresses).map(([sector, addr]) => (
                  <div key={sector} className="flex items-center justify-between">
                    <span className="text-xs font-medium text-console-accent bg-console-accent/10 px-2 py-1 rounded">
                      {sector}
                    </span>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm text-console-text">{String(addr).slice(0, 20)}...</span>
                      <button 
                        onClick={() => handleCopy(String(addr), `sector-${sector}`)}
                        className="btn-ghost p-1"
                      >
                        {copied === `sector-${sector}` ? <Check size={12} className="text-green-400" /> : <Copy size={12} />}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 私钥 */}
          <div className="p-4 bg-console-bg rounded-lg border border-console-border">
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm text-console-text-muted flex items-center gap-2">
                <Key size={14} />
                {t('account.privateKey')}
                <span className="badge badge-error text-xs">{t('account.confidential')}</span>
              </label>
              <div className="flex items-center gap-1">
                <button 
                  onClick={() => setShowPrivateKey(!showPrivateKey)}
                  className="btn-ghost p-1"
                >
                  {showPrivateKey ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </div>
            <div className="font-mono text-console-text break-all">
              {showPrivateKey ? (
                <span className="text-console-text-muted italic text-sm">{t('account.exportKeyDesc')}</span>
              ) : t('account.confidential')}
            </div>
          </div>

          {/* 助记词 */}
          <div className="p-4 bg-console-bg rounded-lg border border-console-border">
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm text-console-text-muted flex items-center gap-2">
                {t('account.mnemonic')}
                <span className="badge badge-error text-xs">{t('account.confidential')}</span>
              </label>
            </div>
            <div className="text-console-text-muted text-sm">
              <p>{t('account.mnemonicNote')}</p>
              <p className="mt-1">{t('account.recoverNote')}</p>
            </div>
          </div>
        </div>

        {/* 警告 */}
        <div className="alert alert-warning mt-4">
          <AlertTriangle size={16} className="shrink-0" />
          <span className="text-sm">
            {t('account.securityWarning')}
          </span>
        </div>
      </section>

      {/* 密钥管理 */}
      <section className="card">
        <h2 className="text-lg font-semibold text-console-text mb-4 flex items-center gap-2">
          <Key size={20} className="text-console-accent" />
          {t('account.keyManagement')}
        </h2>
        
        <div className="space-y-3">
          <button 
            onClick={() => setShowExportModal(true)}
            className="w-full flex items-center justify-between p-4 bg-console-bg rounded-lg border border-console-border hover:border-console-accent transition-colors"
          >
            <div className="flex items-center gap-3">
              <Download size={20} className="text-console-accent" />
              <div className="text-left">
                <div className="font-medium text-console-text">{t('account.exportKey')}</div>
                <div className="text-sm text-console-text-muted">{t('account.exportKeyDesc')}</div>
              </div>
            </div>
            <ChevronRight size={18} className="text-console-text-muted" />
          </button>

          <button className="w-full flex items-center justify-between p-4 bg-console-bg rounded-lg border border-console-border hover:border-console-accent transition-colors">
            <div className="flex items-center gap-3">
              <RefreshCw size={20} className="text-console-warning" />
              <div className="text-left">
                <div className="font-medium text-console-text">{t('account.changeKeyPair')}</div>
                <div className="text-sm text-console-text-muted">{t('account.changeKeyPairDesc')}</div>
              </div>
            </div>
            <ChevronRight size={18} className="text-console-text-muted" />
          </button>
        </div>
      </section>

      {/* 设备管理 */}
      <section className="card">
        <h2 className="text-lg font-semibold text-console-text mb-4 flex items-center gap-2">
          <Smartphone size={20} className="text-console-accent" />
          {t('account.authorizedDevices')}
        </h2>

        <div className="space-y-2">
          {devices.map((device) => (
            <div 
              key={device.id}
              className="flex items-center justify-between p-4 bg-console-bg rounded-lg border border-console-border"
            >
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-console-surface text-console-accent">
                  {getDeviceIcon(device.type)}
                </div>
                <div>
                  <div className="font-medium text-console-text flex items-center gap-2">
                    {device.name}
                    {device.isCurrent && (
                      <span className="badge badge-success text-xs">{t('account.current')}</span>
                    )}
                  </div>
                  <div className="text-sm text-console-text-muted flex items-center gap-2">
                    <Clock size={12} />
                    {device.lastActive}
                    <span>·</span>
                    <span>{device.ip}</span>
                  </div>
                </div>
              </div>
              {!device.isCurrent && (
                <button 
                  onClick={() => {
                    setSelectedDevice(device)
                    setShowRevokeModal(true)
                  }}
                  className="btn-ghost text-red-400 hover:bg-red-500/10"
                >
                  <Trash2 size={16} />
                </button>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* 安全设置 */}
      <section className="card">
        <h2 className="text-lg font-semibold text-console-text mb-4 flex items-center gap-2">
          <Shield size={20} className="text-console-accent" />
          {t('account.securitySettings')}
        </h2>

        <div className="space-y-4">
          {/* 交易确认 */}
          <div className="flex items-center justify-between p-4 bg-console-bg rounded-lg border border-console-border">
            <div className="flex items-center gap-3">
              <Lock size={20} className="text-console-text-muted" />
              <div>
                <div className="font-medium text-console-text">{t('account.txConfirm')}</div>
                <div className="text-sm text-console-text-muted">{t('account.txConfirmDesc')}</div>
              </div>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" defaultChecked className="sr-only peer" />
              <div className="w-11 h-6 bg-console-border rounded-full peer peer-checked:bg-console-accent peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-0.5 after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all" />
            </label>
          </div>

          {/* 登录通知 */}
          <div className="flex items-center justify-between p-4 bg-console-bg rounded-lg border border-console-border">
            <div className="flex items-center gap-3">
              <Smartphone size={20} className="text-console-text-muted" />
              <div>
                <div className="font-medium text-console-text">{t('account.newDeviceNotify')}</div>
                <div className="text-sm text-console-text-muted">{t('account.newDeviceNotifyDesc')}</div>
              </div>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" defaultChecked className="sr-only peer" />
              <div className="w-11 h-6 bg-console-border rounded-full peer peer-checked:bg-console-accent peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-0.5 after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all" />
            </label>
          </div>

          {/* 自动锁定 */}
          <div className="flex items-center justify-between p-4 bg-console-bg rounded-lg border border-console-border">
            <div className="flex items-center gap-3">
              <Clock size={20} className="text-console-text-muted" />
              <div>
                <div className="font-medium text-console-text">{t('account.autoLock')}</div>
                <div className="text-sm text-console-text-muted">{t('account.autoLockDesc')}</div>
              </div>
            </div>
            <select className="input w-32 py-2">
              <option value="5">{t('account.min5')}</option>
              <option value="15">{t('account.min15')}</option>
              <option value="30">{t('account.min30')}</option>
              <option value="60">{t('account.hour1')}</option>
              <option value="never">{t('account.never')}</option>
            </select>
          </div>
        </div>
      </section>
      </>
      )}

      {/* 导出密钥弹窗 */}
      {showExportModal && (
        <ExportKeyModal onClose={() => setShowExportModal(false)} />
      )}

      {/* 撤销设备弹窗 */}
      {showRevokeModal && selectedDevice && (
        <div className="modal-overlay" onClick={() => setShowRevokeModal(false)}>
          <div className="modal max-w-md" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="text-lg font-semibold text-red-400">{t('account.revokeDevice')}</h3>
            </div>
            <div className="modal-body">
              <p className="text-console-text">
                {t('account.revokeConfirm')}
              </p>
              <div className="mt-4 p-4 bg-console-bg rounded-lg border border-console-border">
                <div className="font-medium text-console-text">{selectedDevice.name}</div>
                <div className="text-sm text-console-text-muted">
                  {t('account.lastActivity')} {selectedDevice.lastActive}
                </div>
              </div>
              <p className="mt-4 text-sm text-console-text-muted">
                {t('account.revokeNote')}
              </p>
            </div>
            <div className="modal-footer">
              <button onClick={() => setShowRevokeModal(false)} className="btn-secondary">
                {t('common.cancel')}
              </button>
              <button onClick={handleRevokeDevice} className="btn-danger">
                {t('account.confirmRevoke')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// 导出密钥弹窗
function ExportKeyModal({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation()
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [step, setStep] = useState<'password' | 'download'>('password')

  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState('')

  const handleExport = () => {
    if (password !== confirmPassword) {
      setExportError('密码不匹配')
      return
    }
    setExportError('')
    setStep('download')
  }

  const handleDownload = async () => {
    setExporting(true)
    setExportError('')
    try {
      const result = await walletApi.exportKeystore(password)
      if (result.success && result.keystore) {
        const blob = new Blob([JSON.stringify(result.keystore, null, 2)], { type: 'application/json' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = result.filename || 'keystore.json'
        a.click()
        URL.revokeObjectURL(url)
        onClose()
      } else {
        setExportError(result.message || '导出密钥文件失败')
      }
    } catch (err) {
      setExportError('导出失败: ' + String(err))
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal max-w-md" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="text-lg font-semibold">{t('account.exportKeyDialog')}</h3>
        </div>

        {step === 'password' ? (
          <>
            <div className="modal-body space-y-4">
              <p className="text-console-text-muted text-sm">
                {t('account.exportPasswordHint')}
              </p>

              <div>
                <label className="block text-sm font-medium text-console-text mb-2">
                  {t('account.encryptPassword')}
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input"
                  placeholder={t('account.enterPassword')}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-console-text mb-2">
                  {t('account.confirmPassword')}
                </label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="input"
                  placeholder={t('account.reenterPassword')}
                />
              </div>

              <div className="alert alert-warning">
                <AlertTriangle size={16} className="shrink-0" />
                <span className="text-sm">
                  {t('account.exportFileWarning')}
                </span>
              </div>

              {exportError && (
                <p className="text-red-400 text-sm">{exportError}</p>
              )}
            </div>

            <div className="modal-footer">
              <button onClick={onClose} className="btn-secondary">{t('common.cancel')}</button>
              <button 
                onClick={handleExport}
                disabled={!password || password !== confirmPassword}
                className="btn-primary disabled:opacity-50"
              >
                {t('account.nextStep')}
              </button>
            </div>
          </>
        ) : (
          <>
            <div className="modal-body space-y-4 text-center">
              <div className="w-16 h-16 rounded-full bg-green-500/10 flex items-center justify-center mx-auto">
                <Check size={32} className="text-green-400" />
              </div>
              <h4 className="text-lg font-medium text-console-text">{t('account.exportKeyDialog')}</h4>
              <p className="text-console-text-muted text-sm">
                {t('common.download')}
              </p>
              {exportError && (
                <p className="text-red-400 text-sm">{exportError}</p>
              )}
            </div>

            <div className="modal-footer justify-center">
              <button onClick={handleDownload} disabled={exporting} className="btn-primary flex items-center gap-2 disabled:opacity-50">
                <Download size={16} />
                {exporting ? t('common.loading') : t('common.download')}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
