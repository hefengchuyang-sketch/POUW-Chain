import { useState, useEffect } from 'react'
import { 
  Shield, Eye, AlertTriangle, CheckCircle, Clock,
  Lock, RefreshCw, Info
} from 'lucide-react'
import clsx from 'clsx'
import { privacyApi, PrivacyStatus } from '../api'
import { useTranslation } from '../i18n'

// 隐私路线图阶段
const roadmapPhases = [
  {
    phase: 1,
    title: '地址隔离',
    status: 'completed',
    features: [
      '子地址系统',
      '交易分离',
      '基础隐私保护',
    ],
    description: '通过子地址系统实现交易隔离，降低地址关联风险。',
  },
  {
    phase: 2,
    title: '混币协议',
    status: 'current',
    features: [
      'CoinJoin 实现',
      '交易混淆',
      '金额隐藏',
    ],
    description: '集成混币协议，进一步打断交易链路，增强隐私性。',
  },
  {
    phase: 3,
    title: '零知识证明',
    status: 'planned',
    features: [
      'zk-SNARKs 验证',
      '完全匿名交易',
      '可选透明模式',
    ],
    description: '最终阶段，实现完全的交易隐私，同时保持可验证性。',
  },
]

const riskLabels: Record<string, { label: string; className: string; bgClassName: string }> = {
  low: { label: '低风险', className: 'text-green-400', bgClassName: 'bg-green-500' },
  medium: { label: '中风险', className: 'text-yellow-400', bgClassName: 'bg-yellow-500' },
  high: { label: '高风险', className: 'text-red-400', bgClassName: 'bg-red-500' },
}

export default function Privacy() {
  const { t } = useTranslation()
  const [privacyStatus, setPrivacyStatus] = useState<PrivacyStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'overview' | 'addresses' | 'roadmap' | 'settings'>('overview')
  const [showMixer, setShowMixer] = useState(false)
  const [rotating, setRotating] = useState(false)
  const [rotateMessage, setRotateMessage] = useState('')

  const fetchPrivacyStatus = async () => {
    setLoading(true)
    try {
      const status = await privacyApi.getStatus()
      setPrivacyStatus(status)
    } catch (err) {
      console.error('Failed to fetch privacy status:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchPrivacyStatus()
  }, [])

  const handleRotateAddress = async () => {
    setRotating(true)
    setRotateMessage('')
    try {
      const result = await privacyApi.rotateAddress()
      if (result?.newAddress) {
        setRotateMessage(`地址已轮换！新地址: ${result.newAddress}`)
        fetchPrivacyStatus()
      } else {
        setRotateMessage('地址轮换失败，请稍后重试')
      }
    } catch (err) {
      console.error('Failed to rotate address:', err)
      setRotateMessage('地址轮换失败: 网络错误')
    } finally {
      setRotating(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="animate-spin text-console-accent" size={48} />
      </div>
    )
  }

  const riskLevel = privacyStatus?.riskLevel || 'low'
  const riskScore = riskLevel === 'low' ? 85 : riskLevel === 'medium' ? 65 : 35
  const riskInfo = riskLabels[riskLevel] || riskLabels['low']
  
  // 构建推荐建议
  const recommendations = privacyStatus?.recommendations || [
    { id: 1, type: 'info', message: '隐私状态正常' }
  ]
  
  // 构建地址使用数据
  const mainAddressInfo = privacyStatus?.mainAddressInfo || {
    address: '未知',
    usageCount: 0,
    riskLevel: 'low',
    linkedAddresses: 0,
    lastUsed: Date.now()
  }
  
  const subAddresses = privacyStatus?.subAddresses || []

  return (
    <div className="space-y-6">
      {/* 地址轮换成功提示 */}
      {rotateMessage && (
        <div className="alert alert-success flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle size={18} />
            {rotateMessage}
          </div>
          <button onClick={() => setRotateMessage('')} className="text-green-400 hover:text-green-300">关闭</button>
        </div>
      )}
      {/* 隐私评分卡片 */}
      <div className="card bg-gradient-to-br from-console-accent/20 to-console-accent/5">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
          <div className="flex items-center gap-6">
            <div className="relative">
              <svg className="w-24 h-24 transform -rotate-90">
                <circle
                  className="text-console-border"
                  strokeWidth="8"
                  stroke="currentColor"
                  fill="transparent"
                  r="44"
                  cx="48"
                  cy="48"
                />
                <circle
                  className={riskInfo.className}
                  strokeWidth="8"
                  strokeDasharray={`${riskScore * 2.76} 276`}
                  strokeLinecap="round"
                  stroke="currentColor"
                  fill="transparent"
                  r="44"
                  cx="48"
                  cy="48"
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <Shield className={riskInfo.className} size={32} />
              </div>
            </div>
            <div>
              <h2 className="text-2xl font-bold text-console-text mb-1">{t('privacy.privacyScore')}</h2>
              <p className={clsx('text-3xl font-bold', riskInfo.className)}>
                {riskScore}
              </p>
              <p className="text-sm text-console-muted mt-1">
                {riskInfo.label} - {t('privacy.suggestion')}
              </p>
            </div>
          </div>

          <div className="flex gap-3">
            <button 
              onClick={() => setShowMixer(true)}
              className="btn-primary flex items-center gap-2"
            >
              <RefreshCw size={18} />
              {t('privacy.startMixing')}
            </button>
            <button 
              onClick={handleRotateAddress}
              disabled={rotating}
              className="btn-secondary flex items-center gap-2"
            >
              <RefreshCw size={18} className={rotating ? 'animate-spin' : ''} />
              {rotating ? t('privacy.rotating') : t('privacy.rotateAddress')}
            </button>
          </div>
        </div>
      </div>

      {/* 选项卡 */}
      <div className="flex gap-2 border-b border-console-border pb-2">
        {[
          { key: 'overview', label: t('privacy.riskOverview') },
          { key: 'addresses', label: t('privacy.addressAnalysis') },
          { key: 'roadmap', label: t('privacy.privacyRoadmap') },
          { key: 'settings', label: t('privacy.privacySettings') },
        ].map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key as typeof activeTab)}
            className={clsx(
              'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
              activeTab === tab.key
                ? 'bg-console-accent text-console-text'
                : 'text-console-muted hover:text-console-text hover:bg-console-hover'
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* 风险概览 */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          {/* 建议 */}
          <div className="card">
            <h3 className="text-lg font-semibold text-console-text mb-4">{t('privacy.privacyAdvice')}</h3>
            <div className="space-y-3">
              {recommendations.map(rec => (
                <div 
                  key={rec.id}
                  className={clsx(
                    'p-4 rounded-lg border flex items-start gap-3',
                    rec.type === 'warning' && 'bg-yellow-400/10 border-yellow-400/20',
                    rec.type === 'info' && 'bg-blue-400/10 border-blue-400/20',
                    rec.type === 'success' && 'bg-green-400/10 border-green-400/20',
                  )}
                >
                  {rec.type === 'warning' && <AlertTriangle className="text-yellow-400 flex-shrink-0" size={20} />}
                  {rec.type === 'info' && <Info className="text-blue-400 flex-shrink-0" size={20} />}
                  {rec.type === 'success' && <CheckCircle className="text-green-400 flex-shrink-0" size={20} />}
                  <p className={clsx(
                    rec.type === 'warning' && 'text-yellow-200',
                    rec.type === 'info' && 'text-blue-200',
                    rec.type === 'success' && 'text-green-200',
                  )}>
                    {rec.message}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* 风险指标 */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="card">
              <div className="flex items-center gap-3 mb-3">
                <div className="p-2 rounded-lg bg-red-500/20 text-red-400">
                  <AlertTriangle size={20} />
                </div>
                <span className="text-console-muted">{t('privacy.addressExposure')}</span>
              </div>
              <p className="text-2xl font-bold text-red-400">
                {mainAddressInfo.riskLevel === 'high' ? '高' : mainAddressInfo.riskLevel === 'medium' ? '中' : '低'}
              </p>
              <p className="text-sm text-console-muted mt-1">{t('privacy.mainAddressUsage')} {mainAddressInfo.usageCount} {t('common.times')}</p>
            </div>

            <div className="card">
              <div className="flex items-center gap-3 mb-3">
                <div className="p-2 rounded-lg bg-yellow-500/20 text-yellow-400">
                  <Eye size={20} />
                </div>
                <span className="text-console-muted">{t('privacy.linkedAddresses')}</span>
              </div>
              <p className="text-2xl font-bold text-yellow-400">{mainAddressInfo.linkedAddresses} 个</p>
              <p className="text-sm text-console-muted mt-1">{t('privacy.mayBeTracked')}</p>
            </div>

            <div className="card">
              <div className="flex items-center gap-3 mb-3">
                <div className="p-2 rounded-lg bg-green-500/20 text-green-400">
                  <Shield size={20} />
                </div>
                <span className="text-console-muted">{t('privacy.txPattern')}</span>
              </div>
              <p className="text-2xl font-bold text-green-400">{t('privacy.normal')}</p>
              <p className="text-sm text-console-muted mt-1">{t('privacy.noAnomaly')}</p>
            </div>
          </div>
        </div>
      )}

      {/* 地址分析 */}
      {activeTab === 'addresses' && (
        <div className="space-y-4">
          {/* 主地址 */}
          <div className="card">
            <h3 className="text-lg font-semibold text-console-text mb-4">{t('privacy.mainAddress')}</h3>
            <AddressRow 
              address={mainAddressInfo.address}
              usageCount={mainAddressInfo.usageCount}
              riskLevel={mainAddressInfo.riskLevel}
              linkedAddresses={mainAddressInfo.linkedAddresses}
              lastUsed={mainAddressInfo.lastUsed}
              isMain
            />
          </div>

          {/* 子地址 */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-console-text">{t('privacy.subAddress')}</h3>
              <button 
                onClick={handleRotateAddress}
                disabled={rotating}
                className="btn-secondary text-sm py-1.5"
              >
                {rotating ? t('privacy.creating') : t('privacy.createSubAddress')}
              </button>
            </div>
            <div className="space-y-3">
              {subAddresses.length === 0 ? (
                <p className="text-console-muted text-center py-4">{t('privacy.noSubAddress')}</p>
              ) : (
                subAddresses.map((sub, index) => (
                  <AddressRow
                    key={index}
                    address={sub.address}
                    usageCount={sub.usageCount || 0}
                    riskLevel={sub.riskLevel || 'low'}
                    lastUsed={sub.lastUsed || Date.now()}
                  />
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* 隐私路线图 */}
      {activeTab === 'roadmap' && (
        <div className="card">
          <h3 className="text-lg font-semibold text-console-text mb-6">{t('privacy.privacyRoadmapTitle')}</h3>
          <div className="relative">
            {/* 连接线 */}
            <div className="absolute left-8 top-8 bottom-8 w-0.5 bg-console-border" />
            
            <div className="space-y-8">
              {roadmapPhases.map((phase) => (
                <div key={phase.phase} className="relative flex gap-6">
                  {/* 节点 */}
                  <div className={clsx(
                    'w-16 h-16 rounded-full flex items-center justify-center flex-shrink-0 z-10',
                    phase.status === 'completed' && 'bg-green-500 text-console-text',
                    phase.status === 'current' && 'bg-console-accent text-console-text ring-4 ring-console-accent/30',
                    phase.status === 'planned' && 'bg-console-card text-console-muted',
                  )}>
                    {phase.status === 'completed' && <CheckCircle size={28} />}
                    {phase.status === 'current' && <Clock size={28} />}
                    {phase.status === 'planned' && <Lock size={28} />}
                  </div>

                  {/* 内容 */}
                  <div className={clsx(
                    'flex-1 p-4 rounded-lg',
                    phase.status === 'current' && 'bg-console-accent/10 border border-console-accent/30',
                    phase.status !== 'current' && 'bg-console-card',
                  )}>
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-xs text-console-muted">{t(`privacy.phase${phase.phase}`  as 'privacy.phase1')}</span>
                      <span className={clsx(
                        'badge text-xs',
                        phase.status === 'completed' && 'badge-success',
                        phase.status === 'current' && 'badge-info',
                        phase.status === 'planned' && 'bg-console-card text-console-muted',
                      )}>
                        {phase.status === 'completed' && t('privacy.phaseCompleted')}
                        {phase.status === 'current' && t('privacy.phaseInProgress')}
                        {phase.status === 'planned' && t('privacy.phasePlanned')}
                      </span>
                    </div>
                    <h4 className="text-lg font-semibold text-console-text mb-2">{phase.title}</h4>
                    <p className="text-console-muted text-sm mb-3">{phase.description}</p>
                    <div className="flex flex-wrap gap-2">
                      {phase.features.map((feature, fIndex) => (
                        <span 
                          key={fIndex}
                          className="px-2 py-1 rounded bg-console-card text-xs text-console-muted"
                        >
                          {feature}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 隐私设置 */}
      {activeTab === 'settings' && (
        <div className="space-y-4">
          <SettingCard
            icon={<RefreshCw />}
            title={t('privacy.autoMixing')}
            description={t('privacy.autoMixingDesc')}
            enabled={true}
          />
          <SettingCard
            icon={<Eye />}
            title={t('privacy.addressRotation')}
            description={t('privacy.addressRotationDesc')}
            enabled={true}
          />
          <SettingCard
            icon={<Shield />}
            title={t('privacy.txDelay')}
            description={t('privacy.txDelayDesc')}
            enabled={false}
          />
          <SettingCard
            icon={<AlertTriangle />}
            title={t('privacy.riskWarning')}
            description={t('privacy.riskWarningDesc')}
            enabled={true}
          />
        </div>
      )}

      {/* 混币弹窗 */}
      {showMixer && (
        <MixerModal onClose={() => setShowMixer(false)} />
      )}
    </div>
  )
}

// 地址行
function AddressRow({ 
  address, 
  usageCount, 
  riskLevel, 
  linkedAddresses,
  lastUsed,
  isMain 
}: { 
  address: string;
  usageCount: number;
  riskLevel: string;
  linkedAddresses?: number;
  lastUsed: number;
  isMain?: boolean;
}) {
  const { t } = useTranslation()
  return (
    <div className={clsx(
      'p-4 rounded-lg flex items-center justify-between',
      isMain ? 'bg-console-hover' : 'bg-console-card'
    )}>
      <div className="flex items-center gap-4">
        <div className={clsx(
          'w-10 h-10 rounded-lg flex items-center justify-center',
          riskLabels[riskLevel].className.replace('text-', 'bg-').replace('400', '400/20')
        )}>
          {riskLevel === 'low' && <CheckCircle size={20} className={riskLabels[riskLevel].className} />}
          {riskLevel === 'medium' && <AlertTriangle size={20} className={riskLabels[riskLevel].className} />}
          {riskLevel === 'high' && <AlertTriangle size={20} className={riskLabels[riskLevel].className} />}
        </div>
        <div>
          <p className="font-mono text-console-text">{address}</p>
          <p className="text-xs text-console-muted">
            {t('privacy.lastUsed')} {new Date(lastUsed).toLocaleString()}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-6">
        <div className="text-center">
          <p className="text-console-text font-semibold">{usageCount}</p>
          <p className="text-xs text-console-muted">{t('privacy.usageCount')}</p>
        </div>
        {linkedAddresses !== undefined && (
          <div className="text-center">
            <p className="text-console-text font-semibold">{linkedAddresses}</p>
            <p className="text-xs text-console-muted">{t('privacy.linkedAddresses')}</p>
          </div>
        )}
        <span className={clsx('badge', `badge-${riskLevel === 'low' ? 'success' : riskLevel === 'medium' ? 'warning' : 'error'}`)}>
          {riskLabels[riskLevel].label}
        </span>
      </div>
    </div>
  )
}

// 设置卡片
function SettingCard({ 
  icon, 
  title, 
  description, 
  enabled 
}: { 
  icon: React.ReactNode;
  title: string;
  description: string;
  enabled: boolean;
}) {
  const [isEnabled, setIsEnabled] = useState(enabled)

  return (
    <div className="card flex items-center justify-between">
      <div className="flex items-center gap-4">
        <div className="p-3 rounded-lg bg-console-hover text-console-accent">
          {icon}
        </div>
        <div>
          <h3 className="font-semibold text-console-text">{title}</h3>
          <p className="text-sm text-console-muted">{description}</p>
        </div>
      </div>
      <button
        onClick={() => setIsEnabled(!isEnabled)}
        className={clsx(
          'w-12 h-6 rounded-full transition-colors relative',
          isEnabled ? 'bg-console-accent' : 'bg-console-card'
        )}
      >
        <div className={clsx(
          'w-5 h-5 rounded-full bg-white absolute top-0.5 transition-transform',
          isEnabled ? 'translate-x-6' : 'translate-x-0.5'
        )} />
      </button>
    </div>
  )
}

// 混币弹窗
function MixerModal({ onClose }: { onClose: () => void }) {
  const [step, setStep] = useState(1)
  const [amount, setAmount] = useState('')
  const [coin, setCoin] = useState('MAIN')

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-console-bg border border-console-border rounded-xl p-6 w-full max-w-md">
        <h2 className="text-xl font-bold text-console-text mb-6">混币服务</h2>
        
        {step === 1 && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-console-muted mb-1">选择代币</label>
              <select
                value={coin}
                onChange={(e) => setCoin(e.target.value)}
                className="input"
              >
                <option value="MAIN">MAIN</option>
                <option value="H100">H100</option>
                <option value="A100">A100</option>
              </select>
            </div>

            <div>
              <label className="block text-sm text-console-muted mb-1">混币金额</label>
              <input
                type="number"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="input"
                placeholder="0.00"
              />
            </div>

            <div className="p-4 rounded-lg bg-console-card">
              <div className="flex justify-between text-sm mb-2">
                <span className="text-console-muted">混币费用</span>
                <span className="text-console-text">1%</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-console-muted">预计时间</span>
                <span className="text-console-text">~30 分钟</span>
              </div>
            </div>

            <div className="flex items-center gap-2 p-3 rounded-lg bg-yellow-400/10 border border-yellow-400/20">
              <AlertTriangle size={18} className="text-yellow-400" />
              <p className="text-sm text-yellow-200">
                混币后资金将分批发送到您的新子地址
              </p>
            </div>

            <div className="flex gap-3">
              <button onClick={onClose} className="btn-secondary flex-1">取消</button>
              <button 
                onClick={() => setStep(2)} 
                className="btn-primary flex-1"
                disabled={!amount}
              >
                下一步
              </button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <div className="text-center py-8">
              <RefreshCw size={48} className="text-console-accent mx-auto mb-4 animate-spin" />
              <p className="text-console-text font-semibold">混币进行中...</p>
              <p className="text-console-muted text-sm mt-2">请勿关闭此页面</p>
            </div>

            <div className="p-4 rounded-lg bg-console-card">
              <div className="flex justify-between text-sm mb-2">
                <span className="text-console-muted">混币金额</span>
                <span className="text-console-text">{amount} {coin}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-console-muted">当前阶段</span>
                <span className="text-console-accent">1/3 - 资金注入</span>
              </div>
            </div>

            <button onClick={onClose} className="btn-secondary w-full">后台运行</button>
          </div>
        )}
      </div>
    </div>
  )
}
