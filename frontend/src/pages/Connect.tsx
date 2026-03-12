import { useState, useMemo, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { 
  Server, 
  Key, 
  Shield, 
  AlertTriangle,
  Copy,
  Check,
  Eye,
  EyeOff,
  RefreshCw,
  ArrowRight,
  ArrowLeft,
  HardDrive,
  Smartphone,
  CheckCircle2,
  XCircle,
  Lock,
  Download,
  Upload,
  FileKey
} from 'lucide-react'
import { useAccountStore } from '../store'
import { walletApi, type KeystoreFile } from '../api'
import { useTranslation } from '../i18n'

type ConnectionMethod = 'generate' | 'import' | 'importKeystore' | 'hardware' | 'readonly'

// 验证阶段需要填写的助记词数量
const VERIFY_WORD_COUNT = 3

export default function Connect() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const { setAccount, setConnected } = useAccountStore()
  const [method, setMethod] = useState<ConnectionMethod>('generate')
  // step: 1=选择方式, 1.5=输入密码, 2=显示助记词, 3=验证助记词
  const [step, setStep] = useState(1)
  const [mnemonic, setMnemonic] = useState('')
  const [keystoreData, setKeystoreData] = useState<KeystoreFile | null>(null)
  const [keystoreFilename, setKeystoreFilename] = useState('')
  const [keystoreDownloaded, setKeystoreDownloaded] = useState(false)
  const [walletData, setWalletData] = useState<{
    address: string
    sectorAddresses: Record<string, string>
    sectorBalances: Record<string, number>
  } | null>(null)
  const [showMnemonic, setShowMnemonic] = useState(false)
  const [copied, setCopied] = useState(false)
  const [importMnemonic, setImportMnemonic] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  
  // 创建钱包密码
  const [createPassword, setCreatePassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showCreatePassword, setShowCreatePassword] = useState(false)
  
  // 密钥文件导入相关
  const [keystorePassword, setKeystorePassword] = useState('')
  const [selectedKeystoreFile, setSelectedKeystoreFile] = useState<File | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  
  // 验证助记词输入状态
  const [verifyInputs, setVerifyInputs] = useState<Record<number, string>>({})
  const [verifyError, setVerifyError] = useState('')
  
  // 随机选择需要验证的单词位置 (1-indexed) - 使用稳定的随机数
  const [verifyPositions, setVerifyPositions] = useState<number[]>([])
  
  // 密码强度检查
  const passwordStrength = useMemo(() => {
    if (!createPassword) return { level: 0, text: '', color: '' }
    let score = 0
    if (createPassword.length >= 8) score++
    if (createPassword.length >= 12) score++
    if (/[A-Z]/.test(createPassword)) score++
    if (/[a-z]/.test(createPassword)) score++
    if (/[0-9]/.test(createPassword)) score++
    if (/[^A-Za-z0-9]/.test(createPassword)) score++
    
    if (score <= 2) return { level: 1, text: '弱', color: 'text-red-400' }
    if (score <= 4) return { level: 2, text: '中', color: 'text-yellow-400' }
    return { level: 3, text: '强', color: 'text-green-400' }
  }, [createPassword])
  
  // 密码匹配检查
  const passwordsMatch = createPassword && confirmPassword && createPassword === confirmPassword
  const canProceedWithPassword = createPassword.length >= 8 && passwordsMatch
  
  // 生成验证位置
  const generateVerifyPositions = useCallback((wordCount: number) => {
    const positions: number[] = []
    while (positions.length < VERIFY_WORD_COUNT) {
      const pos = Math.floor(Math.random() * wordCount) + 1
      if (!positions.includes(pos)) {
        positions.push(pos)
      }
    }
    return positions.sort((a, b) => a - b)
  }, [])

  // 获取助记词数组
  const mnemonicWords = useMemo(() => {
    return mnemonic ? mnemonic.split(' ') : []
  }, [mnemonic])

  // 检查验证是否正确
  const verifyCorrect = useMemo(() => {
    if (verifyPositions.length === 0) return false
    return verifyPositions.every(pos => {
      const expectedWord = mnemonicWords[pos - 1]
      const inputWord = (verifyInputs[pos] || '').trim().toLowerCase()
      return inputWord === expectedWord?.toLowerCase()
    })
  }, [verifyPositions, mnemonicWords, verifyInputs])

  const handleGenerateNew = async () => {
    if (!canProceedWithPassword) {
      setError('请设置有效密码（至少8位，两次输入需一致）')
      return
    }
    
    setLoading(true)
    setError('')
    try {
      const result = await walletApi.create(createPassword)
      if (result.success && result.mnemonic) {
        setMnemonic(result.mnemonic)
        // 存储密钥文件
        if (result.keystore) {
          setKeystoreData(result.keystore)
          setKeystoreFilename(result.keystoreFilename || `keystore_${result.address?.slice(0, 12)}.json`)
        }
        setWalletData({
          address: result.address || '',
          sectorAddresses: result.sectorAddresses || result.addresses || {},
          sectorBalances: result.sectorBalances || {}
        })
        // 生成验证位置
        const wordCount = result.mnemonic.split(' ').length
        setVerifyPositions(generateVerifyPositions(wordCount))
        setVerifyInputs({})
        setKeystoreDownloaded(false)
        setStep(2)
      } else {
        // 显示更详细的错误信息
        const errorMsg = result.error || result.message || '创建钱包失败'
        if (errorMsg.includes('weak_password') || errorMsg.includes('密码')) {
          setError('密码强度不足，请使用至少8位字符')
        } else {
          setError(result.message || '创建钱包失败，请检查后端服务是否正常运行')
        }
      }
    } catch (e) {
      setError('无法连接到后端服务，请确保节点正在运行')
    } finally {
      setLoading(false)
    }
  }

  // 下载密钥文件
  const handleDownloadKeystore = () => {
    if (!keystoreData) return
    const blob = new Blob([JSON.stringify(keystoreData, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = keystoreFilename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    setKeystoreDownloaded(true)
  }

  // 选择密钥文件
  const handleKeystoreFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setSelectedKeystoreFile(file)
      setError('')
    }
  }

  // 从密钥文件导入
  const handleImportKeystore = async () => {
    if (!selectedKeystoreFile || !keystorePassword) {
      setError('请选择密钥文件并输入密码')
      return
    }
    
    setLoading(true)
    setError('')
    
    try {
      const fileContent = await selectedKeystoreFile.text()
      const keystore = JSON.parse(fileContent)
      
      const result = await walletApi.importKeystore(keystore, keystorePassword)
      if (result.success) {
        const walletInfo = await walletApi.getInfo()
        setAccount({
          address: walletInfo.address || '',
          balance: walletInfo.balance || 0,
          mainBalance: walletInfo.mainBalance || 0,
          sectorTotal: walletInfo.sectorTotal || 0,
          sectorAddresses: walletInfo.sectorAddresses || walletInfo.addresses || {},
          sectorBalances: walletInfo.sectorBalances || {},
          privacyLevel: 'pseudonymous',
          privacyRisk: 'low',
          subAddresses: []
        })
        setConnected(true)
        navigate('/')
      } else {
        setError(result.message || '密钥文件导入失败')
      }
    } catch (e) {
      if (e instanceof SyntaxError) {
        setError('密钥文件格式无效')
      } else {
        setError('导入失败: ' + String(e))
      }
    } finally {
      setLoading(false)
    }
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(mnemonic)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // 进入验证步骤
  const handleProceedToVerify = () => {
    setShowMnemonic(false)
    setVerifyError('')
    setStep(3)
  }

  // 验证助记词
  const handleVerifyMnemonic = () => {
    if (!verifyCorrect) {
      setVerifyError('验证失败，请确保输入正确的单词')
      return
    }
    // 验证通过，完成钱包创建
    handleFinalizeWallet()
  }

  // 最终创建钱包
  const handleFinalizeWallet = () => {
    if (!walletData) return
    
    // 安全: 助记词不存入 localStorage，仅在创建流程中展示一次
    // 用户应在创建时抄写备份
    setAccount({
      address: walletData.address,
      balance: 0,
      mainBalance: 0,
      sectorTotal: 0,
      sectorAddresses: walletData.sectorAddresses,
      sectorBalances: walletData.sectorBalances,
      privacyLevel: 'pseudonymous',
      privacyRisk: 'low',
      subAddresses: []
    })
    setConnected(true)
    navigate('/')
  }

  const handleImport = async () => {
    const words = importMnemonic.trim().split(/\s+/)
    if (words.length !== 12 && words.length !== 24) {
      setError('助记词必须是12个或24个单词')
      return
    }
    
    setLoading(true)
    setError('')
    try {
      const result = await walletApi.import(importMnemonic.trim(), createPassword)
      if (result.success) {
        // 安全: 导入模式下助记词已由用户自行持有，不存入浏览器
        const walletInfo = await walletApi.getInfo()
        setAccount({
          address: walletInfo.address || '',
          balance: walletInfo.balance || 0,
          mainBalance: walletInfo.mainBalance || 0,
          sectorTotal: walletInfo.sectorTotal || 0,
          sectorAddresses: walletInfo.sectorAddresses || walletInfo.addresses || {},
          sectorBalances: walletInfo.sectorBalances || {},
          privacyLevel: 'pseudonymous',
          privacyRisk: 'low',
          subAddresses: []
        })
        setConnected(true)
        navigate('/')
      } else {
        setError(result.message || '导入钱包失败')
      }
    } catch (e) {
      setError('无法连接到后端服务')
    } finally {
      setLoading(false)
    }
  }

  const handleReadonly = () => {
    navigate('/')
  }

  // 返回上一步
  const handleBack = () => {
    if (step === 3) {
      setStep(2)
      setVerifyError('')
    } else if (step === 2) {
      // 从显示助记词/输入助记词返回到密码设置步骤
      if (method === 'generate' || method === 'import') {
        setStep(1.5)
      } else {
        setStep(1)
      }
      setMnemonic('')
      setWalletData(null)
      setShowMnemonic(false)
      setKeystoreData(null)
      setKeystoreDownloaded(false)
      setSelectedKeystoreFile(null)
      setKeystorePassword('')
      setImportMnemonic('')
    } else if (step === 1.5) {
      // 从密码设置返回到选择方式
      setStep(1)
      setCreatePassword('')
      setConfirmPassword('')
    } else {
      setStep(1)
      setImportMnemonic('')
    }
    setError('')
  }

  // 更新验证输入
  const updateVerifyInput = (pos: number, value: string) => {
    setVerifyInputs(prev => ({ ...prev, [pos]: value }))
    setVerifyError('')
  }

  return (
    <div className="min-h-screen bg-console-bg flex">
      {/* 左侧装饰 */}
      <div className="hidden lg:flex lg:w-1/2 bg-console-surface border-r border-console-border flex-col justify-center items-center p-12">
        <div className="max-w-md text-center">
          <div className="w-20 h-20 rounded-xl bg-console-accent/20 border border-console-accent/50 flex items-center justify-center mx-auto mb-8">
            <Server size={40} className="text-console-accent" />
          </div>
          <h1 className="text-3xl font-bold text-console-text mb-4">
            {t('connect.title')}
          </h1>
          <p className="text-console-text-muted mb-8">
            {t('connect.subtitle')}
          </p>
          
          {/* 步骤指示器 */}
          {method === 'generate' && step >= 2 && (
            <div className="mb-8">
              <div className="flex items-center justify-center gap-2 mb-4">
                {[1, 2, 3].map((s) => (
                  <div key={s} className="flex items-center">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                      step > s + 1 ? 'bg-green-500 text-white' :
                      step === s + 1 ? 'bg-console-accent text-black' :
                      'bg-console-border text-console-text-muted'
                    }`}>
                      {step > s + 1 ? <Check size={16} /> : s}
                    </div>
                    {s < 3 && (
                      <div className={`w-12 h-0.5 ${step > s + 1 ? 'bg-green-500' : 'bg-console-border'}`} />
                    )}
                  </div>
                ))}
              </div>
              <div className="text-sm text-console-text-muted">
                {step === 2 && t('connect.step1')}
                {step === 3 && t('connect.step2')}
              </div>
            </div>
          )}
          
          <div className="space-y-4 text-left">
            <div className="flex items-start gap-3 p-4 bg-console-bg/50 rounded-lg border border-console-border">
              <Shield className="text-green-400 shrink-0 mt-0.5" size={20} />
              <div>
                <div className="text-sm font-medium text-console-text">{t('connect.bip39')}</div>
                <div className="text-xs text-console-text-muted">{t('connect.bip39Desc')}</div>
              </div>
            </div>
            <div className="flex items-start gap-3 p-4 bg-console-bg/50 rounded-lg border border-console-border">
              <Lock className="text-console-accent shrink-0 mt-0.5" size={20} />
              <div>
                <div className="text-sm font-medium text-console-text">{t('connect.localKey')}</div>
                <div className="text-xs text-console-text-muted">{t('connect.localKeyDesc')}</div>
              </div>
            </div>
            <div className="flex items-start gap-3 p-4 bg-console-bg/50 rounded-lg border border-console-border">
              <Key className="text-yellow-400 shrink-0 mt-0.5" size={20} />
              <div>
                <div className="text-sm font-medium text-console-text">{t('connect.decentralizedId')}</div>
                <div className="text-xs text-console-text-muted">{t('connect.decentralizedIdDesc')}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 右侧连接表单 */}
      <div className="flex-1 flex flex-col justify-center p-8 lg:p-12">
        <div className="max-w-md mx-auto w-full">
          {/* 移动端 Logo */}
          <div className="lg:hidden text-center mb-8">
            <div className="w-12 h-12 rounded-lg bg-console-accent/20 border border-console-accent/50 flex items-center justify-center mx-auto mb-4">
              <Server size={24} className="text-console-accent" />
            </div>
            <h1 className="text-xl font-bold text-console-text">{t('connect.title')}</h1>
          </div>

          {/* Step 1: 选择连接方式 */}
          {step === 1 && (
            <>
              <h2 className="text-2xl font-bold text-console-text mb-2">{t('connect.connectWallet')}</h2>
              <p className="text-console-text-muted mb-8">{t('connect.selectMethod')}</p>

              <div className="space-y-3">
                <button
                  onClick={() => { setMethod('generate'); setStep(1.5); }}
                  className="w-full card card-hover flex items-center gap-4 text-left"
                >
                  <div className="w-10 h-10 rounded-lg bg-console-primary/20 flex items-center justify-center shrink-0">
                    <Key className="text-console-primary" size={20} />
                  </div>
                  <div className="flex-1">
                    <div className="font-medium text-console-text">{t('connect.createWallet')}</div>
                    <div className="text-sm text-console-text-muted">{t('connect.createWalletDesc')}</div>
                  </div>
                  <ArrowRight className="text-console-text-muted" size={18} />
                </button>

                <button
                  onClick={() => { setMethod('import'); setStep(1.5); }}
                  className="w-full card card-hover flex items-center gap-4 text-left"
                >
                  <div className="w-10 h-10 rounded-lg bg-console-accent/20 flex items-center justify-center shrink-0">
                    <RefreshCw className="text-console-accent" size={20} />
                  </div>
                  <div className="flex-1">
                    <div className="font-medium text-console-text">{t('connect.useMnemonic')}</div>
                    <div className="text-sm text-console-text-muted">{t('connect.useMnemonicDesc')}</div>
                  </div>
                  <ArrowRight className="text-console-text-muted" size={18} />
                </button>

                <button
                  onClick={() => { setMethod('importKeystore'); setStep(2); }}
                  className="w-full card card-hover flex items-center gap-4 text-left"
                >
                  <div className="w-10 h-10 rounded-lg bg-green-500/20 flex items-center justify-center shrink-0">
                    <FileKey className="text-green-400" size={20} />
                  </div>
                  <div className="flex-1">
                    <div className="font-medium text-console-text">{t('connect.useKeystore')}</div>
                    <div className="text-sm text-console-text-muted">{t('connect.useKeystoreDesc')}</div>
                  </div>
                  <ArrowRight className="text-console-text-muted" size={18} />
                </button>

                <button
                  disabled
                  className="w-full card flex items-center gap-4 text-left opacity-50 cursor-not-allowed"
                >
                  <div className="w-10 h-10 rounded-lg bg-console-border/50 flex items-center justify-center shrink-0">
                    <HardDrive className="text-console-text-muted" size={20} />
                  </div>
                  <div className="flex-1">
                    <div className="font-medium text-console-text">{t('connect.hardwareWallet')}</div>
                    <div className="text-sm text-console-text-muted">{t('connect.hardwareWalletDesc')}</div>
                  </div>
                  <span className="text-xs text-console-text-muted">{t('connect.comingSoon')}</span>
                </button>

                <button
                  disabled
                  className="w-full card flex items-center gap-4 text-left opacity-50 cursor-not-allowed"
                >
                  <div className="w-10 h-10 rounded-lg bg-console-border/50 flex items-center justify-center shrink-0">
                    <Smartphone className="text-console-text-muted" size={20} />
                  </div>
                  <div className="flex-1">
                    <div className="font-medium text-console-text">浏览器钱包</div>
                    <div className="text-sm text-console-text-muted">即将支持 MetaMask 等</div>
                  </div>
                  <span className="text-xs text-console-text-muted">{t('connect.comingSoon')}</span>
                </button>

                {error && (
                  <div className="alert alert-error text-sm">
                    <AlertTriangle size={16} />
                    {error}
                  </div>
                )}

                <div className="pt-4 border-t border-console-border">
                  <button
                    onClick={handleReadonly}
                    className="w-full btn-ghost text-center"
                  >
                    跳过，仅浏览市场
                  </button>
                </div>
              </div>
            </>
          )}

          {/* Step 1.5: 设置钱包密码 */}
          {step === 1.5 && (method === 'generate' || method === 'import') && (
            <div className="space-y-6">
              <div>
                <h2 className="text-2xl font-bold text-console-text mb-2">设置钱包密码</h2>
                <p className="text-console-text-muted">密码用于加密您的钱包密钥文件</p>
              </div>

              <div className="alert alert-info">
                <Shield size={20} className="shrink-0" />
                <div>
                  <div className="font-medium">安全提示</div>
                  <ul className="text-sm opacity-80 mt-1 space-y-1">
                    <li>• 密码将用于加密 Keystore 文件</li>
                    <li>• 请使用强密码并妥善保管</li>
                    <li>• 忘记密码将无法使用密钥文件</li>
                  </ul>
                </div>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-console-text mb-2">
                    输入密码
                  </label>
                  <div className="relative">
                    <input
                      type={showCreatePassword ? 'text' : 'password'}
                      value={createPassword}
                      onChange={(e) => setCreatePassword(e.target.value)}
                      placeholder="请输入钱包密码（至少8位）"
                      className="input w-full pr-10"
                      autoFocus
                    />
                    <button
                      type="button"
                      onClick={() => setShowCreatePassword(!showCreatePassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-console-text-muted hover:text-console-text"
                    >
                      {showCreatePassword ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                  </div>
                  {createPassword && (
                    <div className="mt-2">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-1.5 bg-console-border rounded-full overflow-hidden">
                          <div 
                            className={`h-full transition-all ${
                              passwordStrength.level === 1 ? 'w-1/3 bg-red-500' :
                              passwordStrength.level === 2 ? 'w-2/3 bg-yellow-500' :
                              'w-full bg-green-500'
                            }`}
                          />
                        </div>
                        <span className={`text-xs ${passwordStrength.color}`}>
                          {passwordStrength.text}
                        </span>
                      </div>
                    </div>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-console-text mb-2">
                    确认密码
                  </label>
                  <input
                    type={showCreatePassword ? 'text' : 'password'}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="请再次输入密码"
                    className={`input w-full ${confirmPassword && !passwordsMatch ? 'border-red-500' : ''}`}
                  />
                  {confirmPassword && !passwordsMatch && (
                    <p className="text-red-400 text-sm mt-1">两次输入的密码不一致</p>
                  )}
                </div>
              </div>

              {error && (
                <div className="alert alert-error text-sm">
                  <AlertTriangle size={16} />
                  {error}
                </div>
              )}

              <div className="flex gap-3">
                <button
                  onClick={handleBack}
                  className="btn-secondary flex-1"
                >
                  <ArrowLeft size={18} />
                  返回
                </button>
                {method === 'generate' ? (
                <button
                  onClick={handleGenerateNew}
                  disabled={!canProceedWithPassword || loading}
                  className="btn-primary flex-1"
                >
                  {loading ? (
                    <>
                      <RefreshCw className="animate-spin" size={18} />
                      创建中...
                    </>
                  ) : (
                    <>
                      <Key size={18} />
                      创建钱包
                    </>
                  )}
                </button>
                ) : (
                <button
                  onClick={() => setStep(2)}
                  disabled={!canProceedWithPassword}
                  className="btn-primary flex-1"
                >
                  <ArrowRight size={18} />
                  下一步
                </button>
                )}
              </div>
            </div>
          )}

          {/* Step 2: 创建钱包 - 显示助记词 */}
          {step === 2 && method === 'generate' && (
            <div className="space-y-6">
              <div>
                <h2 className="text-2xl font-bold text-console-text mb-2">备份助记词</h2>
                <p className="text-console-text-muted">请将以下助记词按顺序抄写到安全的地方</p>
              </div>

              <div className="alert alert-warning">
                <AlertTriangle size={20} className="shrink-0" />
                <div>
                  <div className="font-medium">重要安全提示</div>
                  <ul className="text-sm opacity-80 mt-1 space-y-1">
                    <li>• 这是恢复钱包的唯一方式</li>
                    <li>• 请勿截图或保存在联网设备中</li>
                    <li>• 建议手写并保存在安全的物理位置</li>
                  </ul>
                </div>
              </div>

              {/* 下载密钥文件 */}
              {keystoreData && (
                <div className={`card ${keystoreDownloaded ? 'bg-green-500/10 border-green-500/30' : 'bg-console-accent/10 border-console-accent/30'}`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${keystoreDownloaded ? 'bg-green-500/20' : 'bg-console-accent/20'}`}>
                        {keystoreDownloaded ? <Check className="text-green-400" size={20} /> : <FileKey className="text-console-accent" size={20} />}
                      </div>
                      <div>
                        <div className="font-medium text-console-text">
                          {keystoreDownloaded ? '密钥文件已下载' : '下载加密密钥文件'}
                        </div>
                        <div className="text-sm text-console-text-muted">
                          {keystoreDownloaded ? '请妥善保管此文件' : '推荐：使用密钥文件+密码登录更安全'}
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={handleDownloadKeystore}
                      className={`btn ${keystoreDownloaded ? 'btn-ghost' : 'btn-primary'} flex items-center gap-2`}
                    >
                      <Download size={16} />
                      {keystoreDownloaded ? '再次下载' : '下载'}
                    </button>
                  </div>
                </div>
              )}

              <div className="card bg-console-bg">
                <div className="flex items-center justify-between mb-4">
                  <span className="text-sm font-medium text-console-text">
                    助记词 ({mnemonicWords.length} 个单词)
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setShowMnemonic(!showMnemonic)}
                      className="btn-ghost py-1 px-2 text-sm flex items-center gap-1"
                    >
                      {showMnemonic ? <EyeOff size={14} /> : <Eye size={14} />}
                      {showMnemonic ? '隐藏' : '显示'}
                    </button>
                    <button
                      onClick={handleCopy}
                      className="btn-ghost py-1 px-2 text-sm flex items-center gap-1"
                    >
                      {copied ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
                      {copied ? '已复制' : '复制'}
                    </button>
                  </div>
                </div>
                <div className={`grid grid-cols-3 gap-2 transition-all ${!showMnemonic ? 'blur-sm select-none' : ''}`}>
                  {mnemonicWords.map((word, i) => (
                    <div key={i} className="flex items-center gap-2 p-2 bg-console-surface rounded text-sm border border-console-border">
                      <span className="text-console-text-muted w-6 text-right">{i + 1}.</span>
                      <span className="text-console-text font-mono">{word}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4 text-sm">
                <div className="flex items-start gap-2">
                  <CheckCircle2 size={16} className="text-blue-400 shrink-0 mt-0.5" />
                  <div className="text-blue-300">
                    点击"我已备份"后，您需要验证部分助记词以确保您已正确保存。
                  </div>
                </div>
              </div>

              <div className="flex gap-3">
                <button
                  onClick={handleBack}
                  className="btn-secondary flex-1"
                >
                  返回
                </button>
                <button
                  onClick={handleProceedToVerify}
                  className="btn-primary flex-1"
                >
                  我已备份，下一步
                </button>
              </div>
            </div>
          )}

          {/* Step 3: 验证助记词 */}
          {step === 3 && method === 'generate' && (
            <div className="space-y-6">
              <div>
                <h2 className="text-2xl font-bold text-console-text mb-2">验证助记词</h2>
                <p className="text-console-text-muted">
                  请输入以下位置的助记词，以确认您已正确备份
                </p>
              </div>

              <div className="space-y-4">
                {verifyPositions.map((pos) => {
                  const inputValue = verifyInputs[pos] || ''
                  const isCorrect = inputValue.trim().toLowerCase() === mnemonicWords[pos - 1]?.toLowerCase()
                  const hasInput = inputValue.trim().length > 0
                  
                  return (
                    <div key={pos} className="space-y-2">
                      <label className="block text-sm font-medium text-console-text">
                        第 {pos} 个单词是什么？
                      </label>
                      <div className="relative">
                        <input
                          type="text"
                          value={inputValue}
                          onChange={(e) => updateVerifyInput(pos, e.target.value)}
                          placeholder={`请输入第 ${pos} 个单词`}
                          className={`input w-full pr-10 font-mono ${
                            hasInput ? (isCorrect ? 'border-green-500' : 'border-red-500') : ''
                          }`}
                          autoComplete="off"
                          spellCheck="false"
                        />
                        {hasInput && (
                          <div className="absolute right-3 top-1/2 -translate-y-1/2">
                            {isCorrect ? (
                              <CheckCircle2 size={18} className="text-green-500" />
                            ) : (
                              <XCircle size={18} className="text-red-500" />
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>

              {verifyError && (
                <div className="alert alert-error text-sm">
                  <AlertTriangle size={16} />
                  {verifyError}
                </div>
              )}

              <div className="flex gap-3">
                <button
                  onClick={handleBack}
                  className="btn-secondary flex-1"
                >
                  返回查看
                </button>
                <button
                  onClick={handleVerifyMnemonic}
                  disabled={!verifyCorrect}
                  className="btn-primary flex-1 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  验证并创建钱包
                </button>
              </div>

              <p className="text-xs text-console-text-muted text-center">
                忘记了？点击"返回查看"重新查看助记词
              </p>
            </div>
          )}

          {/* Step 2: 导入钱包 */}
          {step === 2 && method === 'import' && (
            <div className="space-y-6">
              <div>
                <h2 className="text-2xl font-bold text-console-text mb-2">导入钱包</h2>
                <p className="text-console-text-muted">输入您的 BIP39 助记词以恢复钱包</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-console-text mb-2">
                  助记词 (12 或 24 个单词)
                </label>
                <textarea
                  value={importMnemonic}
                  onChange={(e) => { setImportMnemonic(e.target.value); setError(''); }}
                  placeholder="请输入助记词，用空格分隔每个单词"
                  rows={4}
                  className="input font-mono w-full"
                  spellCheck="false"
                />
                <p className="text-xs text-console-text-muted mt-2">
                  支持标准 BIP39 助记词，与比特币、以太坊等主流钱包兼容
                </p>
              </div>

              {error && (
                <div className="alert alert-error text-sm">
                  <AlertTriangle size={16} />
                  {error}
                </div>
              )}

              <div className="flex gap-3">
                <button
                  onClick={handleBack}
                  className="btn-secondary flex-1"
                >
                  返回
                </button>
                <button
                  onClick={handleImport}
                  disabled={loading || !importMnemonic.trim()}
                  className="btn-primary flex-1 flex items-center justify-center gap-2 disabled:opacity-50"
                >
                  {loading ? (
                    <>
                      <RefreshCw size={16} className="animate-spin" />
                      导入中...
                    </>
                  ) : (
                    '导入钱包'
                  )}
                </button>
              </div>
            </div>
          )}

          {/* Step 2: 密钥文件导入 */}
          {step === 2 && method === 'importKeystore' && (
            <div className="space-y-6">
              <div>
                <h2 className="text-2xl font-bold text-console-text mb-2">导入密钥文件</h2>
                <p className="text-console-text-muted">选择您的加密密钥文件并输入密码</p>
              </div>

              <div className="space-y-4">
                {/* 文件选择 */}
                <div>
                  <label className="block text-sm font-medium text-console-text mb-2">
                    密钥文件 (Keystore JSON)
                  </label>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".json"
                    onChange={handleKeystoreFileSelect}
                    className="hidden"
                  />
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="w-full card card-hover flex items-center justify-center gap-3 py-8 border-dashed"
                  >
                    {selectedKeystoreFile ? (
                      <>
                        <FileKey className="text-green-400" size={24} />
                        <div className="text-left">
                          <div className="font-medium text-console-text">{selectedKeystoreFile.name}</div>
                          <div className="text-sm text-console-text-muted">
                            {(selectedKeystoreFile.size / 1024).toFixed(1)} KB - 点击更换
                          </div>
                        </div>
                      </>
                    ) : (
                      <>
                        <Upload className="text-console-text-muted" size={24} />
                        <div className="text-console-text-muted">点击选择密钥文件</div>
                      </>
                    )}
                  </button>
                </div>

                {/* 密码输入 */}
                <div>
                  <label className="block text-sm font-medium text-console-text mb-2">
                    密钥文件密码
                  </label>
                  <input
                    type="password"
                    value={keystorePassword}
                    onChange={(e) => { setKeystorePassword(e.target.value); setError(''); }}
                    placeholder="请输入创建密钥文件时设置的密码"
                    className="input w-full"
                  />
                </div>
              </div>

              {error && (
                <div className="alert alert-error text-sm">
                  <AlertTriangle size={16} />
                  {error}
                </div>
              )}

              <div className="flex gap-3">
                <button
                  onClick={handleBack}
                  className="btn-secondary flex-1"
                >
                  返回
                </button>
                <button
                  onClick={handleImportKeystore}
                  disabled={loading || !selectedKeystoreFile || !keystorePassword}
                  className="btn-primary flex-1 flex items-center justify-center gap-2 disabled:opacity-50"
                >
                  {loading ? (
                    <>
                      <RefreshCw size={16} className="animate-spin" />
                      导入中...
                    </>
                  ) : (
                    '导入钱包'
                  )}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
