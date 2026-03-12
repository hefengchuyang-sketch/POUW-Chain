import { useState, useEffect } from 'react'
import { 
  Cpu, 
  Server, 
  Zap, 
  CheckCircle, 
  AlertTriangle,
  RefreshCw,
  Play,
  Pause,
  DollarSign,
  Activity
} from 'lucide-react'
import { useAccountStore } from '../store'
import { minerApi, miningApi } from '../api'
import { useTranslation } from '../i18n'

interface ProviderProfile {
  minerId: string
  address: string
  gpuType: string
  gpuCount: number
  pricePerHour: number
  description: string
  sectors: string[]
  status: 'online' | 'offline' | 'busy'
  registeredAt: number
  behaviorScore: number
  totalTasks: number
  completedTasks: number
  totalEarnings: number
  acceptanceRate: number
  reputationLevel: string
}

const GPU_TYPES = [
  { value: 'H100', label: 'NVIDIA H100', power: 'provider.powerHigh' },
  { value: 'A100', label: 'NVIDIA A100', power: 'provider.powerHigh' },
  { value: 'RTX4090', label: 'NVIDIA RTX 4090', power: 'provider.powerHigh' },
  { value: 'RTX4080', label: 'NVIDIA RTX 4080', power: 'provider.powerMid' },
  { value: 'RTX3090', label: 'NVIDIA RTX 3090', power: 'provider.powerMid' },
  { value: 'RTX3080', label: 'NVIDIA RTX 3080', power: 'provider.powerMid' },
  { value: 'RTX3070', label: 'NVIDIA RTX 3070', power: 'provider.powerEntry' },
  { value: 'OTHER', label: 'provider.otherGpu', power: 'provider.powerGeneral' },
]

const SECTORS = [
  { value: 'GPU', label: 'provider.sectorGpuGeneral' },
  { value: 'H100', label: 'provider.sectorH100' },
  { value: 'A100', label: 'provider.sectorA100' },
  { value: 'RTX4090', label: 'provider.sectorRtx4090' },
]

export default function Provider() {
  const { t } = useTranslation()
  const { account, isConnected } = useAccountStore()
  const [loading, setLoading] = useState(true)
  const [isRegistered, setIsRegistered] = useState(false)
  const [profile, setProfile] = useState<ProviderProfile | null>(null)
  const [miningStatus, setMiningStatus] = useState<{
    isMining: boolean
    hashRate: number
    blocksMined: number
    totalRewards: number
    sector: string
    sectorRewards: Record<string, number>
    gpuName: string
  }>({ isMining: false, hashRate: 0, blocksMined: 0, totalRewards: 0, sector: 'CPU', sectorRewards: {}, gpuName: '' })
  
  // 注册表单
  const [showRegisterForm, setShowRegisterForm] = useState(false)
  const [gpuType, setGpuType] = useState('RTX4090')
  const [gpuCount, setGpuCount] = useState(1)
  const [pricePerHour, setPricePerHour] = useState(1.0)
  const [description, setDescription] = useState('')
  const [selectedSectors, setSelectedSectors] = useState<string[]>(['GPU'])
  
  const [registering, setRegistering] = useState(false)
  const [registerResult, setRegisterResult] = useState<{success: boolean, message: string} | null>(null)
  const [miningAction, setMiningAction] = useState(false)

  // 获取矿工状态
  const fetchProviderStatus = async () => {
    setLoading(true)
    try {
      // 获取挖矿状态
      const status = await miningApi.getStatus()
      setMiningStatus({
        isMining: status.isMining,
        hashRate: status.hashRate,
        blocksMined: status.blocksMined,
        totalRewards: status.totalRewards,
        sector: status.sector || 'CPU',
        sectorRewards: status.sectorRewards || {},
        gpuName: status.gpuName || '',
      })
      
      // 检查是否已注册为矿工 (通过获取矿工列表检查)
      const minerList = await minerApi.getMiners()
      const myMiner = minerList.miners.find(m => 
        m.address === account?.address || 
        (m as any).isLocal
      )
      
      if (myMiner) {
        setIsRegistered(true)
        setProfile({
          minerId: myMiner.minerId,
          address: myMiner.address,
          gpuType: myMiner.gpuType,
          gpuCount: myMiner.gpuCount,
          pricePerHour: 0,
          description: '',
          sectors: [],
          status: myMiner.status,
          registeredAt: 0,
          behaviorScore: myMiner.behaviorScore,
          totalTasks: myMiner.totalTasks,
          completedTasks: myMiner.completedTasks,
          totalEarnings: myMiner.totalEarnings,
          acceptanceRate: myMiner.acceptanceRate,
          reputationLevel: myMiner.reputationLevel || 'bronze',
        })
      }
    } catch (err) {
      console.error('获取矿工状态失败:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (isConnected) {
      fetchProviderStatus()
    } else {
      setLoading(false)
    }
  }, [isConnected])

  // 注册为算力提供者
  const handleRegister = async () => {
    setRegistering(true)
    setRegisterResult(null)
    
    try {
      const result = await minerApi.register({
        gpuType,
        gpuCount,
        pricePerHour,
        description,
        sectors: selectedSectors,
      })
      
      setRegisterResult({ success: result.success, message: result.message })
      
      if (result.success) {
        setIsRegistered(true)
        setShowRegisterForm(false)
        fetchProviderStatus()
      }
    } catch (err) {
      setRegisterResult({ success: false, message: t('provider.registerFailed') + ': ' + String(err) })
    } finally {
      setRegistering(false)
    }
  }

  // 开始/停止挖矿
  const handleToggleMining = async () => {
    setMiningAction(true)
    try {
      if (miningStatus.isMining) {
        const result = await miningApi.stop()
        if (result.success) {
          setMiningStatus(prev => ({ ...prev, isMining: false }))
        }
      } else {
        const result = await miningApi.start(account?.address)
        if (result.success) {
          setMiningStatus(prev => ({ ...prev, isMining: true }))
        }
      }
    } catch (err) {
      console.error('挖矿操作失败:', err)
    } finally {
      setMiningAction(false)
      // 刷新状态
      setTimeout(fetchProviderStatus, 1000)
    }
  }

  // 切换板块选择
  const toggleSector = (sector: string) => {
    if (selectedSectors.includes(sector)) {
      setSelectedSectors(selectedSectors.filter(s => s !== sector))
    } else {
      setSelectedSectors([...selectedSectors, sector])
    }
  }

  if (!isConnected) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <Server size={48} className="text-console-text-muted mb-4" />
        <h2 className="text-xl font-medium text-console-text mb-2">{t('provider.title')}</h2>
        <p className="text-console-text-muted mb-6">{t('provider.subtitle')}</p>
        <a href="/connect" className="btn-primary">{t('provider.becomeProvider')}</a>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <RefreshCw size={32} className="animate-spin text-console-accent" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-console-text">{t('provider.title')}</h1>
          <p className="text-console-text-muted">
            {t('provider.subtitle')}
          </p>
        </div>
        <button
          onClick={fetchProviderStatus}
          className="btn-ghost flex items-center gap-2"
        >
          <RefreshCw size={16} />
          {t('common.refresh')}
        </button>
      </div>

      {/* 未注册 - 显示注册入口 */}
      {!isRegistered && !showRegisterForm && (
        <div className="card text-center py-12">
          <Server size={64} className="mx-auto text-console-accent mb-6 opacity-60" />
          <h2 className="text-xl font-bold text-console-text mb-3">{t('provider.becomeProvider')}</h2>
          <p className="text-console-text-muted mb-6 max-w-md mx-auto">
            {t('provider.becomeProviderDesc')}
          </p>
          <div className="flex flex-wrap gap-4 justify-center mb-8">
            <div className="flex items-center gap-2 text-sm text-console-text-muted">
              <CheckCircle size={16} className="text-green-400" />
              {t('provider.noStaking')}
            </div>
            <div className="flex items-center gap-2 text-sm text-console-text-muted">
              <CheckCircle size={16} className="text-green-400" />
              {t('provider.anytimeOnOff')}
            </div>
            <div className="flex items-center gap-2 text-sm text-console-text-muted">
              <CheckCircle size={16} className="text-green-400" />
              {t('provider.realtimeSettlement')}
            </div>
          </div>
          <button
            onClick={() => setShowRegisterForm(true)}
            className="btn-primary px-8 py-3 text-lg"
          >
            <Zap size={20} className="mr-2" />
            {t('provider.registerNow')}
          </button>
        </div>
      )}

      {/* 注册表单 */}
      {showRegisterForm && !isRegistered && (
        <div className="card">
          <h3 className="text-lg font-bold text-console-text mb-6">{t('provider.registerProvider')}</h3>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* GPU 类型 */}
            <div>
              <label className="block text-sm text-console-text-muted mb-2">{t('provider.gpuType')}</label>
              <select
                value={gpuType}
                onChange={(e) => setGpuType(e.target.value)}
                className="w-full input"
              >
                {GPU_TYPES.map(gpu => (
                  <option key={gpu.value} value={gpu.value}>
                    {gpu.value === 'OTHER' ? t(gpu.label) : gpu.label} ({t(gpu.power)})
                  </option>
                ))}
              </select>
            </div>
            
            {/* GPU 数量 */}
            <div>
              <label className="block text-sm text-console-text-muted mb-2">{t('provider.gpuCount')}</label>
              <input
                type="number"
                value={gpuCount}
                onChange={(e) => setGpuCount(parseInt(e.target.value) || 1)}
                min={1}
                max={128}
                className="w-full input"
              />
            </div>
            
            {/* 报价 */}
            <div>
              <label className="block text-sm text-console-text-muted mb-2">
                {t('provider.hourlyRate')}
              </label>
              <input
                type="number"
                value={pricePerHour}
                onChange={(e) => setPricePerHour(parseFloat(e.target.value) || 0.1)}
                step={0.1}
                min={0.1}
                className="w-full input"
              />
            </div>
            
            {/* 支持的板块 */}
            <div>
              <label className="block text-sm text-console-text-muted mb-2">{t('provider.supportedSectors')}</label>
              <div className="flex flex-wrap gap-2">
                {SECTORS.map(sector => (
                  <button
                    key={sector.value}
                    onClick={() => toggleSector(sector.value)}
                    className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                      selectedSectors.includes(sector.value)
                        ? 'bg-console-accent text-console-bg border-console-accent'
                        : 'bg-transparent text-console-text-muted border-console-border hover:border-console-accent'
                    }`}
                  >
                    {t(sector.label)}
                  </button>
                ))}
              </div>
            </div>
            
            {/* 描述 */}
            <div className="md:col-span-2">
              <label className="block text-sm text-console-text-muted mb-2">{t('provider.description')}</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder={t('provider.descPlaceholder')}
                rows={3}
                className="w-full input"
              />
            </div>
          </div>
          
          {/* 结果提示 */}
          {registerResult && (
            <div className={`mt-4 p-3 rounded-lg text-sm ${
              registerResult.success 
                ? 'bg-green-500/10 text-green-400 border border-green-500/20' 
                : 'bg-red-500/10 text-red-400 border border-red-500/20'
            }`}>
              {registerResult.message}
            </div>
          )}
          
          {/* 操作按钮 */}
          <div className="flex gap-3 mt-6">
            <button
              onClick={() => setShowRegisterForm(false)}
              className="btn-ghost"
              disabled={registering}
            >
              {t('common.cancel')}
            </button>
            <button
              onClick={handleRegister}
              className="btn-primary flex items-center gap-2"
              disabled={registering || selectedSectors.length === 0}
            >
              {registering ? (
                <>
                  <RefreshCw size={16} className="animate-spin" />
                  {t('provider.registering')}
                </>
              ) : (
                <>
                  <CheckCircle size={16} />
                  {t('provider.confirmRegister')}
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* 已注册 - 显示仪表盘 */}
      {isRegistered && (
        <>
          {/* 状态概览 */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="card">
              <div className="flex items-center gap-3 mb-2">
                <div className={`w-3 h-3 rounded-full ${miningStatus.isMining ? 'bg-green-400 animate-pulse' : 'bg-gray-400'}`} />
                <span className="text-sm text-console-text-muted">{t('common.status')}</span>
              </div>
              <div className="text-xl font-bold text-console-text">
                {miningStatus.isMining ? t('provider.running') : t('provider.stopped')}
              </div>
            </div>
            
            <div className="card">
              <div className="flex items-center gap-3 mb-2">
                <Activity size={16} className="text-console-accent" />
                <span className="text-sm text-console-text-muted">{t('provider.hashrate')}</span>
              </div>
              <div className="text-xl font-bold text-console-text">
                {miningStatus.hashRate.toFixed(2)} <span className="text-sm">H/s</span>
              </div>
            </div>
            
            <div className="card">
              <div className="flex items-center gap-3 mb-2">
                <Cpu size={16} className="text-console-primary" />
                <span className="text-sm text-console-text-muted">{t('provider.completedTasks')}</span>
              </div>
              <div className="text-xl font-bold text-console-text">
                {miningStatus.blocksMined}
              </div>
            </div>
            
            <div className="card">
              <div className="flex items-center gap-3 mb-2">
                <DollarSign size={16} className="text-console-warning" />
                <span className="text-sm text-console-text-muted">{t('provider.sectorCoinEarnings')}</span>
              </div>
              <div className="text-xl font-bold text-console-text">
                {miningStatus.totalRewards.toFixed(4)} <span className="text-sm">{miningStatus.sector}_COIN</span>
              </div>
              {/* 各板块奖励明细 */}
              {Object.keys(miningStatus.sectorRewards).length > 0 && (
                <div className="mt-2 text-xs text-console-text-muted">
                  {Object.entries(miningStatus.sectorRewards).map(([sector, amount]) => (
                    <div key={sector}>{sector}: {amount.toFixed(2)}</div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* 控制面板 */}
          <div className="card">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-lg font-bold text-console-text">{t('provider.miningControl')}</h3>
                {miningStatus.isMining && (
                  <div className="text-sm text-console-text-muted mt-1">
                    {t('provider.currentSector')}<span className="text-console-accent">{miningStatus.sector}</span>
                    {miningStatus.gpuName && <span className="ml-2">({miningStatus.gpuName})</span>}
                  </div>
                )}
              </div>
              <button
                onClick={handleToggleMining}
                disabled={miningAction}
                className={`px-6 py-2.5 rounded-lg font-medium flex items-center gap-2 transition-colors ${
                  miningStatus.isMining
                    ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30 border border-red-500/30'
                    : 'bg-green-500/20 text-green-400 hover:bg-green-500/30 border border-green-500/30'
                }`}
              >
                {miningAction ? (
                  <RefreshCw size={18} className="animate-spin" />
                ) : miningStatus.isMining ? (
                  <Pause size={18} />
                ) : (
                  <Play size={18} />
                )}
                {miningStatus.isMining ? t('provider.stopMining') : t('provider.startMining')}
              </button>
            </div>
            
            {/* 设备信息 */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 bg-console-bg/50 rounded-lg border border-console-border">
                <div className="text-sm text-console-text-muted mb-1">{t('provider.gpuType')}</div>
                <div className="font-medium text-console-text">{profile?.gpuType || gpuType}</div>
              </div>
              <div className="p-4 bg-console-bg/50 rounded-lg border border-console-border">
                <div className="text-sm text-console-text-muted mb-1">{t('provider.gpuCount')}</div>
                <div className="font-medium text-console-text">{profile?.gpuCount || gpuCount}</div>
              </div>
              <div className="p-4 bg-console-bg/50 rounded-lg border border-console-border">
                <div className="text-sm text-console-text-muted mb-1">{t('provider.reputationLevel')}</div>
                <div className="font-medium text-console-text capitalize">
                  {profile?.reputationLevel || 'bronze'}
                </div>
              </div>
            </div>
          </div>

          {/* 提示 */}
          <div className="alert alert-info">
            <AlertTriangle size={18} className="shrink-0" />
            <div>
              <div className="font-medium">{t('provider.miningInstructions')}</div>
              <div className="text-sm opacity-80">
                {t('provider.miningInstructionsDetail')}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
