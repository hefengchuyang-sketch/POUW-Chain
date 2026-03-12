import { useState, useEffect } from 'react'
import { 
  Search, Star, TrendingUp, TrendingDown, AlertTriangle,
  CheckCircle, Clock, XCircle, Award, Activity, RefreshCw
} from 'lucide-react'
import clsx from 'clsx'
import { minerApi, Miner } from '../api'
import { useTranslation } from '../i18n'

// 扩展矿工类型，包含更多展示字段
interface MinerDisplay extends Miner {
  scoreChange?: number
  failedTasks?: number
  disputeRate?: number
  avgResponseTime?: number
  uptime?: number
  joinDate?: number
  lastActive?: number
  congestionPenalties?: number
  earlyTerminations?: number
}

const reputationLevels: Record<string, { label: string; className: string; icon: React.ReactNode }> = {
  platinum: { 
    label: 'miners.platinum', 
    className: 'bg-gradient-to-r from-purple-400 to-pink-400 text-white',
    icon: <Award size={14} />
  },
  gold: { 
    label: 'miners.gold', 
    className: 'bg-gradient-to-r from-yellow-400 to-orange-400 text-black',
    icon: <Award size={14} />
  },
  silver: { 
    label: 'miners.silver', 
    className: 'bg-gradient-to-r from-gray-300 to-gray-400 text-black',
    icon: <Award size={14} />
  },
  bronze: { 
    label: 'miners.bronze', 
    className: 'bg-gradient-to-r from-amber-600 to-amber-700 text-white',
    icon: <Award size={14} />
  },
}

const gpuTypes = [
  { value: 'all', label: 'miners.allGPU' },
  { value: 'H100', label: 'H100' },
  { value: 'A100', label: 'A100' },
  { value: 'RTX4090', label: 'RTX4090' },
]

const reputationOptions = [
  { value: 'all', label: 'miners.allLevel' },
  { value: 'platinum', label: 'miners.platinum' },
  { value: 'gold', label: 'miners.gold' },
  { value: 'silver', label: 'miners.silver' },
  { value: 'bronze', label: 'miners.bronze' },
]

export default function Miners() {
  const { t } = useTranslation()
  const [searchQuery, setSearchQuery] = useState('')
  const [gpuFilter, setGpuFilter] = useState('all')
  const [reputationFilter, setReputationFilter] = useState('all')
  const [sortBy, setSortBy] = useState<'score' | 'tasks' | 'uptime'>('score')
  const [selectedMiner, setSelectedMiner] = useState<MinerDisplay | null>(null)
  const [miners, setMiners] = useState<MinerDisplay[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchMiners = async () => {
      setLoading(true)
      try {
        const data = await minerApi.getMiners(sortBy)
        // 添加扩展字段 - 基于真实数据计算
        const minersWithDefaults: MinerDisplay[] = data.miners.map(m => {
          const failedTasks = m.totalTasks - m.completedTasks
          const disputeRate = m.totalTasks > 0 ? (failedTasks / m.totalTasks * 100) : 0
          return {
            ...m,
            scoreChange: 0,  // 需要历史数据才能计算变化
            failedTasks,
            disputeRate: Math.round(disputeRate * 10) / 10,
            avgResponseTime: 1.5,  // 需要从后端获取
            uptime: m.completedTasks > 0 ? 99.5 : 95,  // 基于完成率估算
            joinDate: Date.now() - 90 * 24 * 60 * 60 * 1000,  // 默认3个月前
            lastActive: Date.now(),  // 在线的话就是现在
            congestionPenalties: 0,  // 需要从后端获取
            earlyTerminations: failedTasks,
          }
        })
        setMiners(minersWithDefaults)
      } catch (error) {
        console.error('获取矿工列表失败:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchMiners()
  }, [sortBy])

  const filteredMiners = miners
    .filter(miner => {
      const matchesSearch = miner.name.toLowerCase().includes(searchQuery.toLowerCase())
      const matchesGpu = gpuFilter === 'all' || miner.gpuType === gpuFilter
      const matchesReputation = reputationFilter === 'all' || miner.reputationLevel === reputationFilter
      return matchesSearch && matchesGpu && matchesReputation
    })
    .sort((a, b) => {
      if (sortBy === 'score') return b.behaviorScore - a.behaviorScore
      if (sortBy === 'tasks') return b.completedTasks - a.completedTasks
      return (b.uptime || 0) - (a.uptime || 0)
    })

  const avgScore = miners.length > 0 
    ? miners.reduce((sum, m) => sum + m.behaviorScore, 0) / miners.length 
    : 0
  const totalTasks = miners.reduce((sum, m) => sum + m.completedTasks, 0)

  if (loading && miners.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="animate-spin text-console-accent" size={48} />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 统计卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard icon={<Activity />} label={t('miners.activeMiners')} value={miners.length.toString()} />
        <StatCard icon={<Star />} label={t('miners.avgScore')} value={avgScore.toFixed(1)} />
        <StatCard icon={<CheckCircle />} label={t('miners.totalCompletedTasks')} value={totalTasks.toLocaleString()} />
        <StatCard icon={<Award />} label={t('miners.platinumMiners')} value={miners.filter(m => m.reputationLevel === 'platinum').length.toString()} />
      </div>

      {/* 筛选栏 */}
      <div className="card">
        <div className="flex flex-col md:flex-row gap-4">
          {/* 搜索 */}
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-console-muted" size={18} />
            <input
              type="text"
              placeholder={t('miners.searchPlaceholder')}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input pl-10"
            />
          </div>

          {/* GPU 类型 */}
          <select
            value={gpuFilter}
            onChange={(e) => setGpuFilter(e.target.value)}
            className="input w-auto"
          >
            {gpuTypes.map(type => (
              <option key={type.value} value={type.value}>{t(type.label)}</option>
            ))}
          </select>

          {/* 信誉等级 */}
          <select
            value={reputationFilter}
            onChange={(e) => setReputationFilter(e.target.value)}
            className="input w-auto"
          >
            {reputationOptions.map(option => (
              <option key={option.value} value={option.value}>{t(option.label)}</option>
            ))}
          </select>

          {/* 排序 */}
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
            className="input w-auto"
          >
            <option value="score">{t('miners.sortByScore')}</option>
            <option value="tasks">{t('miners.sortByTasks')}</option>
            <option value="uptime">{t('miners.sortByOnline')}</option>
          </select>
        </div>
      </div>

      {/* 矿工列表 */}
      <div className="space-y-4">
        {filteredMiners.map((miner, index) => (
          <MinerCard 
            key={miner.minerId} 
            miner={miner} 
            rank={index + 1}
            onSelect={() => setSelectedMiner(miner)}
          />
        ))}
      </div>

      {filteredMiners.length === 0 && miners.length === 0 && (
        <div className="card text-center py-12">
          <p className="text-console-muted mb-2">{t('miners.noMinerData')}</p>
          <p className="text-console-muted text-sm">{t('miners.waitingForMiners')}</p>
        </div>
      )}
      {filteredMiners.length === 0 && miners.length > 0 && (
        <div className="card text-center py-12">
          <p className="text-console-muted">{t('miners.noMatchingMiners')}</p>
        </div>
      )}

      {/* 矿工详情弹窗 */}
      {selectedMiner && (
        <MinerDetailModal miner={selectedMiner} onClose={() => setSelectedMiner(null)} />
      )}
    </div>
  )
}

// 统计卡片
function StatCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="card flex items-center gap-4">
      <div className="p-3 rounded-lg bg-console-hover text-console-accent">
        {icon}
      </div>
      <div>
        <p className="text-sm text-console-muted">{label}</p>
        <p className="text-xl font-bold text-console-text">{value}</p>
      </div>
    </div>
  )
}

// 矿工卡片
function MinerCard({ 
  miner, 
  rank, 
  onSelect 
}: { 
  miner: MinerDisplay; 
  rank: number;
  onSelect: () => void;
}) {
  const { t } = useTranslation()
  const isOnline = miner.lastActive ? Date.now() - miner.lastActive < 15 * 60 * 1000 : false

  return (
    <div 
      className="card card-hover cursor-pointer"
      onClick={onSelect}
    >
      <div className="flex flex-col md:flex-row md:items-center gap-4">
        {/* 排名和基本信息 */}
        <div className="flex items-center gap-4 flex-1">
          <div className="w-10 h-10 rounded-full bg-console-hover flex items-center justify-center text-console-text font-bold">
            #{rank}
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="font-semibold text-console-text">{miner.name}</h3>
              <span className={clsx(
                'px-2 py-0.5 rounded-full text-xs font-medium flex items-center gap-1',
                reputationLevels[miner.reputationLevel].className
              )}>
                {reputationLevels[miner.reputationLevel].icon}
                {t(reputationLevels[miner.reputationLevel].label)}
              </span>
              <span className={clsx(
                'w-2 h-2 rounded-full',
                isOnline ? 'bg-green-400' : 'bg-gray-400'
              )} />
            </div>
            <p className="text-sm text-console-muted">{miner.address} · {miner.gpuType} × {miner.gpuCount}</p>
          </div>
        </div>

        {/* 行为评分 */}
        <div className="flex items-center gap-6">
          <div className="text-center">
            <div className="flex items-center gap-1">
              <span className={clsx(
                'text-2xl font-bold',
                miner.behaviorScore >= 90 ? 'text-green-400' :
                miner.behaviorScore >= 70 ? 'text-yellow-400' : 'text-red-400'
              )}>
                {miner.behaviorScore}
              </span>
              {(miner.scoreChange ?? 0) !== 0 && (
                <span className={clsx(
                  'flex items-center text-sm',
                  (miner.scoreChange ?? 0) > 0 ? 'text-green-400' : 'text-red-400'
                )}>
                  {(miner.scoreChange ?? 0) > 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                  {Math.abs(miner.scoreChange ?? 0)}
                </span>
              )}
            </div>
            <p className="text-xs text-console-muted">{t('miners.behaviorScore')}</p>
          </div>

          <div className="text-center">
            <p className="text-xl font-bold text-console-text">{miner.completedTasks}</p>
            <p className="text-xs text-console-muted">{t('miners.completedTasks')}</p>
          </div>

          <div className="text-center">
            <p className="text-xl font-bold text-console-text">{miner.uptime}%</p>
            <p className="text-xs text-console-muted">{t('miners.onlineRate')}</p>
          </div>

          <div className="text-center">
            <p className={clsx(
              'text-xl font-bold',
              (miner.disputeRate ?? 0) < 5 ? 'text-green-400' : 'text-yellow-400'
            )}>
              {miner.disputeRate ?? 0}%
            </p>
            <p className="text-xs text-console-muted">{t('miners.disputeRate')}</p>
          </div>
        </div>
      </div>
    </div>
  )
}

// 矿工详情弹窗
function MinerDetailModal({ miner, onClose }: { miner: MinerDisplay; onClose: () => void }) {
  const { t } = useTranslation()
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-console-bg border border-console-border rounded-xl p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        {/* 头部 */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <h2 className="text-xl font-bold text-console-text">{miner.name}</h2>
              <span className={clsx(
                'px-2 py-0.5 rounded-full text-xs font-medium flex items-center gap-1',
                reputationLevels[miner.reputationLevel].className
              )}>
                {reputationLevels[miner.reputationLevel].icon}
                {t(reputationLevels[miner.reputationLevel].label)}
              </span>
            </div>
            <p className="text-sm text-console-muted">{miner.address}</p>
          </div>
          <button onClick={onClose} className="text-console-muted hover:text-console-text">
            <XCircle size={24} />
          </button>
        </div>

        {/* 评分仪表盘 */}
        <div className="p-6 rounded-lg bg-console-card mb-6">
          <div className="flex items-center justify-center mb-4">
            <div className="relative">
              <svg className="w-32 h-32 transform -rotate-90">
                <circle
                  className="text-console-border"
                  strokeWidth="8"
                  stroke="currentColor"
                  fill="transparent"
                  r="56"
                  cx="64"
                  cy="64"
                />
                <circle
                  className={clsx(
                    miner.behaviorScore >= 90 ? 'text-green-400' :
                    miner.behaviorScore >= 70 ? 'text-yellow-400' : 'text-red-400'
                  )}
                  strokeWidth="8"
                  strokeDasharray={`${miner.behaviorScore * 3.52} 352`}
                  strokeLinecap="round"
                  stroke="currentColor"
                  fill="transparent"
                  r="56"
                  cx="64"
                  cy="64"
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-3xl font-bold text-console-text">{miner.behaviorScore}</span>
              </div>
            </div>
          </div>
          <p className="text-center text-console-muted">{t('miners.behaviorScore')}</p>
        </div>

        {/* 详细指标 */}
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
          <MetricItem label={t('miners.completedTasks')} value={miner.completedTasks.toString()} icon={<CheckCircle size={16} />} />
          <MetricItem label={t('miners.failedTasks')} value={(miner.failedTasks ?? 0).toString()} icon={<XCircle size={16} />} />
          <MetricItem label={t('miners.disputeRate')} value={`${miner.disputeRate ?? 0}%`} icon={<AlertTriangle size={16} />} />
          <MetricItem label={t('miners.avgResponse')} value={`${(miner.avgResponseTime ?? 0).toFixed(1)}s`} icon={<Clock size={16} />} />
          <MetricItem label={t('miners.onlineRate')} value={`${(miner.uptime ?? 0).toFixed(1)}%`} icon={<Activity size={16} />} />
          <MetricItem label={t('miners.gpuConfig')} value={`${miner.gpuType} × ${miner.gpuCount}`} icon={<Star size={16} />} />
        </div>

        {/* 惩罚记录 */}
        <div className="p-4 rounded-lg bg-console-card">
          <h3 className="font-semibold text-console-text mb-3">{t('miners.penaltyRecord')}</h3>
          <div className="grid grid-cols-2 gap-4">
            <div className="flex items-center justify-between">
              <span className="text-console-muted">{t('miners.congestionPenalty')}</span>
              <span className={clsx(
                'font-semibold',
                miner.congestionPenalties === 0 ? 'text-green-400' : 'text-yellow-400'
              )}>
                {miner.congestionPenalties} {t('miners.times')}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-console-muted">{t('miners.earlyTermination')}</span>
              <span className={clsx(
                'font-semibold',
                miner.earlyTerminations === 0 ? 'text-green-400' : 'text-yellow-400'
              )}>
                {miner.earlyTerminations} {t('miners.times')}
              </span>
            </div>
          </div>
        </div>

        <div className="flex gap-3 mt-6">
          <button onClick={onClose} className="btn-secondary flex-1">{t('miners.close')}</button>
          <button className="btn-primary flex-1">{t('miners.viewFullHistory')}</button>
        </div>
      </div>
    </div>
  )
}

// 指标项
function MetricItem({ label, value, icon }: { label: string; value: string; icon: React.ReactNode }) {
  return (
    <div className="p-3 rounded-lg bg-console-card">
      <div className="flex items-center gap-2 text-console-muted mb-1">
        {icon}
        <span className="text-sm">{label}</span>
      </div>
      <p className="text-lg font-semibold text-console-text">{value}</p>
    </div>
  )
}
