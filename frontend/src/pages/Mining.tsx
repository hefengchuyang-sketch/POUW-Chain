import { useState, useEffect } from 'react'
import { 
  Play, 
  Square, 
  RefreshCw, 
  Cpu, 
  Zap, 
  TrendingUp,
  Clock,
  Award,
  AlertTriangle,
  CheckCircle,
  Activity,
  Star,
  Hammer,
  ClipboardList,
  Layers,
  Timer,
  ThumbsUp,
  BarChart3,
  Shield,
  Globe,
  Wifi,
} from 'lucide-react'
import { XAxis, YAxis, Tooltip, ResponsiveContainer, AreaChart, Area, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar } from 'recharts'
import { miningApi, MiningStatus, MiningReward, MinerScore } from '../api'
import { useAccountStore } from '../store'
import { useTranslation } from '../i18n'

type MiningMode = 'mine_only' | 'task_only' | 'mine_and_task'

const MODE_CONFIG: Record<MiningMode, { label: string; labelEn: string; desc: string; descEn: string; icon: typeof Hammer; color: string; bgColor: string }> = {
  mine_only: {
    label: 'mining.mineOnly',
    labelEn: 'Mine Only',
    desc: 'mining.mineOnlyDesc',
    descEn: 'Focus on block mining, earn Sector Coins as rewards',
    icon: Hammer,
    color: 'text-amber-400',
    bgColor: 'bg-amber-500/10 border-amber-500/30',
  },
  task_only: {
    label: 'mining.tasksOnly',
    labelEn: 'Tasks Only',
    desc: 'mining.tasksOnlyDesc',
    descEn: 'Accept compute task orders only, earn task rewards',
    icon: ClipboardList,
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/10 border-blue-500/30',
  },
  mine_and_task: {
    label: 'mining.mineAndTasks',
    labelEn: 'Mine & Tasks',
    desc: 'mining.mineAndTasksDesc',
    descEn: 'Mine blocks and accept tasks simultaneously, maximize earnings',
    icon: Layers,
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/10 border-emerald-500/30',
  },
}

const GRADE_STYLE: Record<string, { color: string; bg: string; text: string; textEn: string }> = {
  S: { color: 'text-yellow-300', bg: 'bg-yellow-500/20 border-yellow-400/50', text: 'mining.gradeExceptional', textEn: 'Exceptional' },
  A: { color: 'text-green-400', bg: 'bg-green-500/20 border-green-400/50', text: 'mining.gradeExcellent', textEn: 'Excellent' },
  B: { color: 'text-blue-400', bg: 'bg-blue-500/20 border-blue-400/50', text: 'mining.gradeGood', textEn: 'Good' },
  C: { color: 'text-orange-400', bg: 'bg-orange-500/20 border-orange-400/50', text: 'mining.gradeAverage', textEn: 'Average' },
  D: { color: 'text-red-400', bg: 'bg-red-500/20 border-red-400/50', text: 'mining.gradeNeedsImprovement', textEn: 'Needs Improvement' },
}

export default function Mining() {
  const { t } = useTranslation()
  const { account, isConnected } = useAccountStore()
  const [status, setStatus] = useState<MiningStatus | null>(null)
  const [rewards, setRewards] = useState<MiningReward[]>([])
  const [score, setScore] = useState<MinerScore | null>(null)
  const [selectedMode, setSelectedMode] = useState<MiningMode>('mine_only')
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [p2pIp, setP2pIp] = useState('')
  const [p2pPort, setP2pPort] = useState('')

  const fetchData = async () => {
    setLoading(true)
    try {
      const [statusData, rewardsData, scoreData] = await Promise.all([
        miningApi.getStatus(),
        miningApi.getRewards(),
        miningApi.getScore(),
      ])
      setStatus(statusData)
      setRewards(rewardsData.rewards)
      setScore(scoreData)
      if (statusData.miningMode) {
        setSelectedMode(statusData.miningMode)
      }
      setError('')
    } catch {
      setError(t('mining.errorFetchStatus'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 10000)
    return () => clearInterval(interval)
  }, [])

  const handleStart = async () => {
    if (!isConnected || !account?.address) {
      setError(t('mining.errorConnectWallet'))
      return
    }
    setActionLoading(true)
    setError('')
    setMessage('')
    try {
      const result = await miningApi.start(
        account.address,
        selectedMode,
        (selectedMode !== 'mine_only' && p2pIp) ? p2pIp : undefined,
        (selectedMode !== 'mine_only' && p2pPort) ? parseInt(p2pPort) : undefined,
      )
      if (result.success) {
        setMessage(result.message || t('mining.started'))
        await fetchData()
      } else {
        setError(result.message || t('mining.startFailed'))
      }
    } catch {
      setError(t('mining.startFailed'))
    } finally {
      setActionLoading(false)
    }
  }

  const handleStop = async () => {
    setActionLoading(true)
    setError('')
    setMessage('')
    try {
      const result = await miningApi.stop()
      if (result.success) {
        setMessage(t('mining.stopped'))
        await fetchData()
      } else {
        setError(result.message || t('mining.stopFailed'))
      }
    } catch {
      setError(t('mining.stopFailed'))
    } finally {
      setActionLoading(false)
    }
  }

  const handleModeChange = async (mode: MiningMode) => {
    const previousMode = selectedMode
    setSelectedMode(mode)
    if (status?.isMining || status?.acceptingTasks) {
      try {
        const result = await miningApi.setMode(mode)
        if (result.success) {
          setMessage(result.message)
          await fetchData()
        } else {
          setSelectedMode(previousMode)
          setError(result.message || t('mining.switchModeFailed'))
        }
      } catch {
        setSelectedMode(previousMode)
        setError(t('mining.switchModeFailed'))
      }
    }
  }

  // 评分雷达图数据
  const radarData = score ? [
    { metric: `${t('mining.completionRate')} Completion`, value: (score.metrics.completionRate || 0) * 100, fullMark: 100 },
    { metric: `${t('mining.uptimeRate')} Uptime`, value: (score.metrics.uptimeRate || 0) * 100, fullMark: 100 },
    { metric: `${t('mining.latency')} Latency`, value: Math.max(0, 100 - (score.metrics.avgLatencyMs || 0) / 50), fullMark: 100 },
    { metric: `${t('mining.blocks')} Blocks`, value: Math.min(100, (score.metrics.blocksMined || 0) * 10), fullMark: 100 },
    { metric: `${t('mining.feedback')} Feedback`, value: (score.feedbackScore || 0.5) * 100, fullMark: 100 },
  ] : []

  const rewardChartData = rewards.slice(0, 20).reverse().map((r) => ({
    name: `#${r.blockHeight}`,
    amount: r.amount,
    time: new Date(r.timestamp).toLocaleTimeString()
  }))

  const gradeStyle = GRADE_STYLE[score?.grade || 'B']

  if (loading && !status) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="animate-spin text-console-accent" size={48} />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-console-text">{t('mining.title')} <span className="text-lg font-normal text-console-text-muted">Mining Control Center</span></h1>
          <p className="text-console-text-muted mt-1">{t('mining.subtitle')} · Select mode, manage tasks & view scores</p>
        </div>
        <button
          onClick={fetchData}
          disabled={loading}
          className="btn-ghost flex items-center gap-2"
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          {t('common.refresh')} Refresh
        </button>
      </div>

      {/* 错误/成功提示 */}
      {error && (
        <div className="alert alert-error">
          <AlertTriangle size={18} />
          {error}
        </div>
      )}
      {message && (
        <div className="alert alert-success">
          <CheckCircle size={18} />
          {message}
        </div>
      )}
      {!isConnected && (
        <div className="alert alert-warning">
          <AlertTriangle size={18} />
          <span>{t('mining.connectWalletFirst')} / Please connect wallet first to start mining</span>
        </div>
      )}

      {/* ==================== 挖矿模式选择 ==================== */}
      <div className="card">
        <h3 className="font-medium text-console-text mb-4 flex items-center gap-2">
          <Layers size={18} className="text-console-primary" />
          {t('mining.miningMode')} <span className="text-console-text-muted font-normal text-sm">Mining Mode</span>
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {(Object.entries(MODE_CONFIG) as [MiningMode, typeof MODE_CONFIG[MiningMode]][]).map(([mode, config]) => {
            const Icon = config.icon
            const isActive = selectedMode === mode
            const isRunning = status?.isMining || status?.acceptingTasks
            const isCurrentMode = status?.miningMode === mode && isRunning
            return (
              <button
                key={mode}
                onClick={() => handleModeChange(mode)}
                className={`relative p-5 rounded-xl border-2 text-left transition-all duration-200 ${
                  isActive
                    ? config.bgColor + ' ring-1 ring-offset-0'
                    : 'border-console-border bg-console-card hover:border-console-text-muted/30'
                }`}
              >
                {isCurrentMode && (
                  <span className="absolute top-3 right-3 flex h-2.5 w-2.5">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500"></span>
                  </span>
                )}
                <div className="flex items-center gap-3 mb-3">
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${isActive ? config.bgColor : 'bg-console-border'}`}>
                    <Icon size={20} className={isActive ? config.color : 'text-console-text-muted'} />
                  </div>
                  <div>
                    <div className={`font-semibold ${isActive ? config.color : 'text-console-text'}`}>
                      {t(config.label)}
                      <span className="text-xs font-normal text-console-text-muted ml-1">{config.labelEn}</span>
                    </div>
                  </div>
                </div>
                <p className="text-sm text-console-text-muted leading-relaxed">
                  {t(config.desc)}
                  <br />
                  <span className="text-xs opacity-70">{config.descEn}</span>
                </p>
                {isActive && (
                  <div className="mt-3 flex items-center gap-1 text-xs">
                    <CheckCircle size={12} className={config.color} />
                    <span className={config.color}>{t('mining.selected')} Selected</span>
                  </div>
                )}
              </button>
            )
          })}
        </div>
      </div>

      {/* ==================== P2P 直连配置（接单模式） ==================== */}
      {selectedMode !== 'mine_only' && (
        <div className="card border border-cyan-500/20">
          <h3 className="font-medium text-console-text mb-3 flex items-center gap-2">
            <Globe size={18} className="text-cyan-400" />
            {t('mining.p2pConfig')} <span className="text-console-text-muted font-normal text-sm">P2P Direct Connection</span>
          </h3>
          <p className="text-sm text-console-text-muted mb-4">
            {t('mining.p2pDescription')}
            <br />
            <span className="text-xs opacity-70">
              Enter your public IP so task creators can transfer data directly to you via encrypted P2P tunnel. Your IP is encrypted end-to-end.
            </span>
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-console-text-muted mb-1">
                {t('mining.publicIp')} <span className="text-xs">Public IP</span>
              </label>
              <input
                type="text"
                value={p2pIp}
                onChange={(e) => setP2pIp(e.target.value.replace(/[^0-9.]/g, ''))}
                placeholder={t('mining.ipPlaceholder')}
                className="w-full px-3 py-2 bg-console-bg border border-console-border rounded-lg text-console-text placeholder-console-text-muted/50 focus:border-cyan-500/50 focus:outline-none"
                disabled={status?.isMining || status?.acceptingTasks}
              />
              <p className="text-xs text-console-text-muted mt-1">{t('mining.ipEmptyHint')}</p>
            </div>
            <div>
              <label className="block text-sm text-console-text-muted mb-1">
                {t('mining.port')} <span className="text-xs">Port (optional)</span>
              </label>
              <input
                type="text"
                value={p2pPort}
                onChange={(e) => setP2pPort(e.target.value.replace(/[^0-9]/g, ''))}
                placeholder={t('mining.portAuto')}
                className="w-full px-3 py-2 bg-console-bg border border-console-border rounded-lg text-console-text placeholder-console-text-muted/50 focus:border-cyan-500/50 focus:outline-none"
                disabled={status?.isMining || status?.acceptingTasks}
              />
              <p className="text-xs text-console-text-muted mt-1">{t('mining.portHint')}</p>
            </div>
          </div>
          {/* P2P 运行状态 */}
          {(status?.isMining || status?.acceptingTasks) && (
            <div className="mt-4 p-3 rounded-lg bg-console-bg flex items-center gap-3">
              <Wifi size={18} className={status?.p2pEnabled ? 'text-green-400' : 'text-console-text-muted'} />
              <div>
                <span className={`text-sm font-medium ${status?.p2pEnabled ? 'text-green-400' : 'text-console-text-muted'}`}>
                  {status?.p2pEnabled
                    ? `${t('mining.p2pReady')} ${status.p2pPort}`
                    : t('mining.p2pNotEnabled')}
                </span>
                <span className="text-xs text-console-text-muted ml-2">
                  {status?.p2pEnabled ? 'Ready · Encrypted tunnel active' : 'Relay mode'}
                </span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ==================== 主控制区 ==================== */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左：启停控制 */}
        <div className="card lg:col-span-1">
          <h3 className="font-medium text-console-text mb-4">{t('mining.runStatus')} <span className="text-console-text-muted font-normal text-sm">Status</span></h3>
          <div className="text-center py-4">
            <div className={`w-24 h-24 mx-auto rounded-full flex items-center justify-center mb-4 transition-all ${
              (status?.isMining || status?.acceptingTasks)
                ? 'bg-green-500/20 border-2 border-green-500 shadow-lg shadow-green-500/20'
                : 'bg-console-border border-2 border-console-border'
            }`}>
              <Cpu size={40} className={(status?.isMining || status?.acceptingTasks) ? 'text-green-400' : 'text-console-text-muted'} />
            </div>
            
            <div className={`text-lg font-semibold mb-1 ${(status?.isMining || status?.acceptingTasks) ? 'text-green-400' : 'text-console-text-muted'}`}>
              {status?.isMining && status?.acceptingTasks
                ? `${t('mining.miningStatus')}+${t('mining.acceptingTasks')} Mining & Tasks`
                : status?.isMining
                ? `${t('mining.miningStatus')} Mining`
                : status?.acceptingTasks
                ? `${t('mining.acceptingTasks')} Accepting Tasks`
                : `${t('mining.stopped')} Stopped`}
            </div>

            <div className="text-xs text-console-text-muted mb-1">
              {t('mining.mode')} Mode: <span className={MODE_CONFIG[selectedMode].color}>{t(MODE_CONFIG[selectedMode].label)}</span>
            </div>

            {status?.gpuName && (
              <div className="text-xs text-console-text-muted mb-4">
                {t('mining.device')} Device: {status.gpuName} · {t('mining.sector')} Sector: {status.sector}
              </div>
            )}
            
            <div className="flex gap-3 justify-center mt-4">
              {(status?.isMining || status?.acceptingTasks) ? (
                <button
                  onClick={handleStop}
                  disabled={actionLoading}
                  className="btn-danger flex items-center gap-2 px-6"
                >
                  {actionLoading ? <RefreshCw size={16} className="animate-spin" /> : <Square size={16} />}
                  {t('mining.stop')} Stop
                </button>
              ) : (
                <button
                  onClick={handleStart}
                  disabled={actionLoading || !isConnected}
                  className="btn-primary flex items-center gap-2 px-6"
                >
                  {actionLoading ? <RefreshCw size={16} className="animate-spin" /> : <Play size={16} />}
                  {t('mining.start')} Start
                </button>
              )}
            </div>
          </div>
        </div>

        {/* 右：统计数据 */}
        <div className="card lg:col-span-2">
          <h3 className="font-medium text-console-text mb-4">{t('mining.runStats')} <span className="text-console-text-muted font-normal text-sm">Statistics</span></h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-4 bg-console-bg rounded-lg">
              <div className="flex items-center gap-2 text-console-text-muted mb-2">
                <Zap size={16} className="text-amber-400" />
                <span className="text-sm">{t('mining.hashrate')} Hashrate</span>
              </div>
              <div className="text-xl font-bold text-console-text">
                {status?.hashRate ? `${status.hashRate.toFixed(2)} H/s` : '0 H/s'}
              </div>
            </div>
            <div className="p-4 bg-console-bg rounded-lg">
              <div className="flex items-center gap-2 text-console-text-muted mb-2">
                <Award size={16} className="text-blue-400" />
                <span className="text-sm">{t('mining.minedBlocks')} Blocks</span>
              </div>
              <div className="text-xl font-bold text-console-text">
                {status?.blocksMined || 0}
              </div>
            </div>
            <div className="p-4 bg-console-bg rounded-lg">
              <div className="flex items-center gap-2 text-console-text-muted mb-2">
                <TrendingUp size={16} className="text-green-400" />
                <span className="text-sm">{t('mining.totalEarnings')} Total</span>
              </div>
              <div className="text-xl font-bold text-console-primary">
                {status?.totalRewards?.toFixed(4) || '0.0000'}
              </div>
              <div className="text-xs text-console-text-muted">{t('mining.sectorCoin')} Sector Coin</div>
            </div>
            <div className="p-4 bg-console-bg rounded-lg">
              <div className="flex items-center gap-2 text-console-text-muted mb-2">
                <Activity size={16} className="text-purple-400" />
                <span className="text-sm">{t('mining.difficulty')} Difficulty</span>
              </div>
              <div className="text-xl font-bold text-console-text">
                {status?.difficulty || 4}
              </div>
            </div>
          </div>

          {/* 任务统计（接单模式时显示） */}
          {(selectedMode === 'task_only' || selectedMode === 'mine_and_task') && score && (
            <div className="mt-4 grid grid-cols-3 gap-4">
              <div className="p-3 bg-console-bg rounded-lg flex items-center gap-3">
                <ClipboardList size={18} className="text-blue-400" />
                <div>
                  <div className="text-xs text-console-text-muted">{t('mining.completedTasks')} Tasks Done</div>
                  <div className="font-semibold text-console-text">{score.metrics.totalTasks}</div>
                </div>
              </div>
              <div className="p-3 bg-console-bg rounded-lg flex items-center gap-3">
                <Timer size={18} className="text-cyan-400" />
                <div>
                  <div className="text-xs text-console-text-muted">{t('mining.avgLatency')} Avg Latency</div>
                  <div className="font-semibold text-console-text">{score.metrics.avgLatencyMs.toFixed(0)} ms</div>
                </div>
              </div>
              <div className="p-3 bg-console-bg rounded-lg flex items-center gap-3">
                <ThumbsUp size={18} className="text-green-400" />
                <div>
                  <div className="text-xs text-console-text-muted">{t('mining.completionRate')} Completion</div>
                  <div className="font-semibold text-console-text">{((score.metrics.completionRate || 0) * 100).toFixed(1)}%</div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ==================== 矿工评分面板 ==================== */}
      <div className="card">
        <h3 className="font-medium text-console-text mb-4 flex items-center gap-2">
          <Star size={18} className="text-yellow-400" />
          {t('mining.minerScore')} <span className="text-console-text-muted font-normal text-sm">Miner Score</span>
        </h3>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 左：综合评级 */}
          <div className="flex flex-col items-center justify-center py-4">
            <div className={`w-28 h-28 rounded-2xl border-2 flex flex-col items-center justify-center mb-3 ${gradeStyle.bg}`}>
              <span className={`text-4xl font-black ${gradeStyle.color}`}>{score?.grade || 'B'}</span>
              <span className={`text-xs mt-1 ${gradeStyle.color}`}>{t(gradeStyle.text)} {gradeStyle.textEn}</span>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-console-text">
                {((score?.priorityScore || 0.5) * 100).toFixed(1)}
              </div>
              <div className="text-xs text-console-text-muted">{t('mining.priorityScore')} Priority Score</div>
            </div>
            <div className="mt-4 w-full space-y-2">
              <ScoreBar label={`${t('mining.objectiveMetrics')} Objective`} value={score?.objectiveScore || 0.5} weight={score?.weights.objectiveWeight || 0.7} color="blue" />
              <ScoreBar label={`${t('mining.userFeedback')} Feedback`} value={score?.feedbackScore || 0.5} weight={score?.weights.feedbackWeight || 0.3} color="green" />
            </div>
          </div>

          {/* 中：雷达图 */}
          <div className="flex items-center justify-center">
            {radarData.length > 0 ? (
              <ResponsiveContainer width="100%" height={240}>
                <RadarChart cx="50%" cy="50%" outerRadius="70%" data={radarData}>
                  <PolarGrid stroke="#30363d" />
                  <PolarAngleAxis 
                    dataKey="metric" 
                    tick={{ fill: '#8b949e', fontSize: 12 }}
                  />
                  <PolarRadiusAxis 
                    angle={90} 
                    domain={[0, 100]} 
                    tick={{ fill: '#8b949e', fontSize: 10 }}
                    tickCount={4}
                  />
                  <Radar
                    name={t('mining.score')}
                    dataKey="value"
                    stroke="#1f6feb"
                    fill="#1f6feb"
                    fillOpacity={0.25}
                    strokeWidth={2}
                  />
                </RadarChart>
              </ResponsiveContainer>
            ) : (
              <div className="text-console-text-muted text-center py-8">
                <BarChart3 size={32} className="mx-auto mb-2 opacity-50" />
                <p className="text-sm">{t('mining.scoresShownAfterMining')} Scores shown after mining starts</p>
              </div>
            )}
          </div>

          {/* 右：指标详情 */}
          <div className="space-y-3">
            <MetricRow
              icon={<Timer size={16} className="text-cyan-400" />}
              label={`${t('mining.latency')} Latency`}
              value={`${(score?.metrics.avgLatencyMs || 0).toFixed(0)} ms`}
              detail={score?.metrics.avgLatencyMs ? (score.metrics.avgLatencyMs <= 100 ? `${t('mining.gradeExcellent')} Excellent` : score.metrics.avgLatencyMs <= 1000 ? `${t('mining.gradeGood')} Good` : `${t('mining.needsImprove')} Improve`) : `${t('mining.noData')} No Data`}
              detailColor={score?.metrics.avgLatencyMs ? (score.metrics.avgLatencyMs <= 100 ? 'text-green-400' : score.metrics.avgLatencyMs <= 1000 ? 'text-blue-400' : 'text-orange-400') : 'text-console-text-muted'}
            />
            <MetricRow
              icon={<CheckCircle size={16} className="text-green-400" />}
              label={`${t('mining.completionRate')} Completion`}
              value={`${((score?.metrics.completionRate || 0) * 100).toFixed(1)}%`}
              detail={`${t('mining.totalPrefix')} ${score?.metrics.totalTasks || 0} ${t('mining.tasksSuffix')} tasks`}
              detailColor="text-console-text-muted"
            />
            <MetricRow
              icon={<Shield size={16} className="text-blue-400" />}
              label={`${t('mining.uptimeRate')} Uptime`}
              value={`${((score?.metrics.uptimeRate || 0) * 100).toFixed(1)}%`}
              detail={`${t('mining.stayOnline')} Stay online for higher score`}
              detailColor="text-console-text-muted"
            />
            <MetricRow
              icon={<Hammer size={16} className="text-amber-400" />}
              label={`${t('mining.blocksMined')} Blocks Mined`}
              value={`${score?.metrics.blocksMined || 0} ${t('mining.blocksUnit')} blocks`}
              detail={`${t('mining.miningRaisesScore')} Mining raises score`}
              detailColor="text-console-text-muted"
            />
            <MetricRow
              icon={<ThumbsUp size={16} className="text-purple-400" />}
              label={`${t('mining.userRating')} User Rating`}
              value={score?.feedback.count ? `${score.feedback.rating.toFixed(1)} / 5.0` : `${t('mining.na')} N/A`}
              detail={score?.feedback.count ? `${score.feedback.count} ${t('mining.reviews')} reviews · ${t('mining.tips')} Tips ${score.feedback.totalTips.toFixed(2)}` : `${t('mining.rateAfterTask')} Users rate after task completion`}
              detailColor="text-console-text-muted"
            />
          </div>
        </div>

        {/* 评分公式说明 */}
        <div className="mt-4 p-3 bg-console-bg rounded-lg">
          <div className="flex items-start gap-2">
            <BarChart3 size={14} className="text-console-text-muted mt-0.5 shrink-0" />
            <div className="text-xs text-console-text-muted leading-relaxed">
              <span className="text-console-text font-medium">{t('mining.scoringFormula')} Scoring Formula：</span>
              {' '}FinalScore = α × ObjectiveScore + β × FeedbackScore
              {' '}（α={score?.weights.objectiveWeight || 0.7}, β={score?.weights.feedbackWeight || 0.3}）
              <br />
              {t('mining.objectiveMetrics')} Objective = {t('mining.latency')} Latency(25%) + {t('mining.completionRate')} Completion(30%) + {t('mining.uptimeRate')} Uptime(25%) + {t('mining.blocks')} Blocks(20%).
              {t('mining.feedbackMinReviews')} (Feedback requires ≥5 reviews). {t('mining.higherScorePriority')} Higher score = higher task priority.
            </div>
          </div>
        </div>
      </div>

      {/* ==================== 收益趋势 ==================== */}
      <div className="card">
        <h3 className="font-medium text-console-text mb-4 flex items-center gap-2">
          <TrendingUp size={18} className="text-console-primary" />
          {t('mining.rewardTrend')} <span className="text-console-text-muted font-normal text-sm">Reward Trend</span>
        </h3>
        {rewardChartData.length > 0 ? (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={rewardChartData}>
                <defs>
                  <linearGradient id="colorAmount" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#1f6feb" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#1f6feb" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <XAxis 
                  dataKey="name" 
                  stroke="#8b949e"
                  tick={{ fill: '#8b949e', fontSize: 12 }}
                />
                <YAxis 
                  stroke="#8b949e"
                  tick={{ fill: '#8b949e', fontSize: 12 }}
                />
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: '#161b22', 
                    border: '1px solid #30363d',
                    borderRadius: '8px'
                  }}
                  labelStyle={{ color: '#c9d1d9' }}
                />
                <Area 
                  type="monotone" 
                  dataKey="amount" 
                  stroke="#1f6feb" 
                  fillOpacity={1}
                  fill="url(#colorAmount)"
                  name={`${t('mining.reward')} Reward`}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="h-48 flex items-center justify-center text-console-text-muted">
            <div className="text-center">
              <Clock size={32} className="mx-auto mb-2 opacity-50" />
              <p>{t('mining.noRewardRecords')} No reward records yet</p>
              <p className="text-sm">{t('mining.startMiningToSee')} Start mining to see reward trends</p>
            </div>
          </div>
        )}
      </div>

      {/* ==================== 最近奖励列表 ==================== */}
      <div className="card">
        <h3 className="font-medium text-console-text mb-4 flex items-center gap-2">
          <Award size={18} className="text-amber-400" />
          {t('mining.recentRewards')} <span className="text-console-text-muted font-normal text-sm">Recent Rewards</span>
        </h3>
        {rewards.length > 0 ? (
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {rewards.slice(0, 20).map((reward, i) => (
              <div 
                key={i}
                className="flex items-center justify-between p-3 bg-console-bg rounded-lg hover:bg-console-border/30 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-console-primary/20 flex items-center justify-center">
                    <Award size={14} className="text-console-primary" />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-console-text">
                      {t('mining.blocksUnit')} Block #{reward.blockHeight}
                    </div>
                    <div className="text-xs text-console-text-muted">
                      {new Date(reward.timestamp).toLocaleString()}
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-medium text-console-primary">
                    +{reward.amount.toFixed(4)}
                  </div>
                  <div className="text-xs text-console-text-muted">
                    {reward.coin}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-console-text-muted">
            <Award size={32} className="mx-auto mb-2 opacity-50" />
            <p>{t('mining.noRewardsYet')} No rewards yet</p>
          </div>
        )}
      </div>
    </div>
  )
}

/* ==================== 子组件 ==================== */

function ScoreBar({ label, value, weight, color }: { label: string; value: number; weight: number; color: string }) {
  const pct = Math.round(value * 100)
  const barColor = color === 'blue' ? 'bg-blue-500' : 'bg-green-500'
  return (
    <div>
      <div className="flex items-center justify-between text-xs mb-1">
        <span className="text-console-text-muted">{label} (×{weight})</span>
        <span className="text-console-text font-medium">{pct}</span>
      </div>
      <div className="h-2 bg-console-border rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-500 ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function MetricRow({ icon, label, value, detail, detailColor }: {
  icon: React.ReactNode
  label: string
  value: string
  detail: string
  detailColor: string
}) {
  return (
    <div className="flex items-center gap-3 p-3 bg-console-bg rounded-lg">
      <div className="shrink-0">{icon}</div>
      <div className="flex-1 min-w-0">
        <div className="text-sm text-console-text-muted">{label}</div>
        <div className="text-sm font-semibold text-console-text">{value}</div>
      </div>
      <div className={`text-xs ${detailColor} text-right shrink-0`}>{detail}</div>
    </div>
  )
}
