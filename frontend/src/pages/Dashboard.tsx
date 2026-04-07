import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { 
  Wallet, 
  Cpu, 
  Activity,
  Clock,
  AlertTriangle,
  RefreshCw,
  ArrowUpRight,
  ArrowDownRight,
  Play,
  TrendingUp,
  Server,
  Zap,
  ExternalLink,
  Hammer
} from 'lucide-react'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts'
import { dashboardApi, DashboardStats, RecentTask, statsApi, miningApi, MiningStatus } from '../api'
import { useAccountStore } from '../store'
import { useTranslation } from '../i18n'

interface StatCardProps {
  icon: React.ReactNode
  label: string
  value: string
  subtext?: string
  change?: { value: number; isUp: boolean }
  loading?: boolean
}

function StatCard({ icon, label, value, subtext, change, loading }: StatCardProps) {
  if (loading) {
    return (
      <div className="stat-card">
        <div className="flex items-start justify-between">
          <div className="p-2 rounded-lg bg-console-border/50">
            <div className="w-5 h-5 skeleton" />
          </div>
        </div>
        <div className="mt-4">
          <div className="h-8 w-24 skeleton mb-2" />
          <div className="h-4 w-32 skeleton" />
        </div>
      </div>
    )
  }

  return (
    <div className="stat-card">
      <div className="flex items-start justify-between">
        <div className="p-2 rounded-lg bg-console-accent/10 border border-console-accent/20">
          {icon}
        </div>
        {change && (
          <div className={change.isUp ? 'stat-change-up' : 'stat-change-down'}>
            {change.isUp ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
            {Math.abs(change.value)}%
          </div>
        )}
      </div>
      <div className="mt-4">
        <div className="stat-value">{value}</div>
        <div className="stat-label">{label}</div>
        {subtext && <div className="text-xs text-console-text-muted mt-1">{subtext}</div>}
      </div>
    </div>
  )
}

function TaskStatusBadge({ status }: { status: string }) {
  const config: Record<string, { class: string; labelKey: string }> = {
    pending: { class: 'badge-warning', labelKey: 'status.pending' },
    running: { class: 'badge-info', labelKey: 'status.running' },
    completed: { class: 'badge-success', labelKey: 'status.completed' },
    failed: { class: 'badge-error', labelKey: 'status.failed' },
    assigned: { class: 'badge-info', labelKey: 'status.assigned' },
  }
  const { t } = useTranslation()
  const { class: cls, labelKey } = config[status] || { class: 'badge-neutral', labelKey: status }
  return <span className={`badge ${cls}`}>{t(labelKey)}</span>
}

export default function Dashboard() {
  const { account, isConnected } = useAccountStore()
  const { t } = useTranslation()
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [recentTasks, setRecentTasks] = useState<RecentTask[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [networkStats, setNetworkStats] = useState<{ totalMiners: number; onlineMiners: number; totalGpuPower: number } | null>(null)
  const [miningStatus, setMiningStatus] = useState<MiningStatus | null>(null)

  const fetchData = async () => {
    setLoading(true)
    setError(null)
    try {
      const [statsData, tasksData, network, mining] = await Promise.all([
        dashboardApi.getStats(account?.address),
        dashboardApi.getRecentTasks(5),
        statsApi.getNetworkStats(),
        miningApi.getStatus(account?.address),
      ])
      setStats(statsData)
      setRecentTasks(tasksData)
      setNetworkStats(network)
      setMiningStatus(mining)
    } catch (err) {
      setError(t('dashboard.cannotConnect'))
      console.error('Dashboard fetch error:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [account?.address])

  // 算力利用率环图数据
  const utilizationData = [
    { name: t('dashboard.used'), value: stats?.networkUtilization || 0, color: '#238636' },
    { name: t('dashboard.idle'), value: 100 - (stats?.networkUtilization || 0), color: '#30363d' },
  ]

  // 资产占比数据 - 区分 MAIN 币和板块币
  const mainBalance = stats?.mainBalance || account?.mainBalance || 0
  const sectorTotal = stats?.sectorTotal || account?.sectorTotal || 0
  const assetData = [
    { name: 'MAIN', value: mainBalance, color: '#1f6feb' },
    { name: t('common.sectorCoin'), value: sectorTotal, color: '#238636' },
  ].filter(d => d.value > 0)

  return (
    <div className="space-y-6">
      {/* 欢迎区域 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-console-text">{t('dashboard.title')}</h1>
          <p className="text-console-text-muted mt-1">
            {isConnected ? t('dashboard.welcome') : t('dashboard.connectWalletHint')}
          </p>
        </div>
        <button
          onClick={fetchData}
          disabled={loading}
          className="btn-ghost flex items-center gap-2 text-sm"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          {t('common.refresh')}
        </button>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="alert alert-error">
          <AlertTriangle size={18} />
          <div className="flex-1">{error}</div>
          <button onClick={fetchData} className="btn-ghost py-1 px-3 text-sm">{t('common.retry')}</button>
        </div>
      )}

      {/* 系统公告 */}
      <div className="alert alert-info">
        <Activity size={18} className="shrink-0" />
        <div className="flex-1">
          <span className="font-medium">{t('dashboard.systemNotice')}</span>
          {t('dashboard.networkNormal')} #{stats?.blockHeight?.toLocaleString() || 0}
        </div>
        <a href="#" className="text-sm flex items-center gap-1 hover:underline">
          {t('common.viewMore')} <ExternalLink size={12} />
        </a>
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={<Wallet size={18} className="text-console-accent" />}
          label={t('dashboard.mainBalance')}
          value={`${(stats?.mainBalance || account?.mainBalance || 0).toFixed(4)} MAIN`}
          subtext={`${t('dashboard.sectorCoins')}: ${(stats?.sectorTotal || account?.sectorTotal || 0).toFixed(2)} ${t('common.coins')}`}
          loading={loading}
        />
        <StatCard
          icon={<Play size={18} className="text-green-400" />}
          label={t('dashboard.runningTasks')}
          value={(stats?.activeTasks || 0).toString()}
          subtext={`${t('dashboard.todayCompleted')} ${stats?.completedToday || 0} ${t('common.pieces')}`}
          loading={loading}
        />
        <StatCard
          icon={<Server size={18} className="text-console-warning" />}
          label={t('dashboard.onlineMiners')}
          value={(networkStats?.onlineMiners || stats?.onlineMiners || 0).toString()}
          subtext={`${t('common.total')} ${networkStats?.totalMiners || 0} ${t('common.pieces')}`}
          loading={loading}
        />
        <StatCard
          icon={<Zap size={18} className="text-purple-400" />}
          label={t('dashboard.networkHashrate')}
          value={`${((networkStats?.totalGpuPower || stats?.totalGpuPower || 0) / 1000).toFixed(1)} PFLOPS`}
          subtext={`${t('dashboard.utilization')} ${Math.round(stats?.networkUtilization || 0)}%`}
          loading={loading}
        />
      </div>

      {/* 图表区 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 算力利用率 */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-medium text-console-text">{t('dashboard.computeUtilization')}</h3>
            <span className="text-2xl font-bold text-console-primary">
              {Math.round(stats?.networkUtilization || 0)}%
            </span>
          </div>
          <div className="h-40">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={utilizationData}
                  cx="50%"
                  cy="50%"
                  innerRadius={45}
                  outerRadius={60}
                  paddingAngle={2}
                  dataKey="value"
                  startAngle={90}
                  endAngle={-270}
                >
                  {utilizationData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} stroke="none" />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="flex justify-center gap-6 mt-2 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-sm bg-console-primary" />
              <span className="text-console-text-muted">{t('dashboard.used')}</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-sm bg-console-border" />
              <span className="text-console-text-muted">{t('dashboard.idle')}</span>
            </div>
          </div>
        </div>

        {/* 资产分布 */}
        <div className="card">
          <h3 className="font-medium text-console-text mb-4">{t('dashboard.assetDistribution')}</h3>
          {assetData.length > 0 ? (
            <>
              <div className="h-40">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={assetData}
                      cx="50%"
                      cy="50%"
                      innerRadius={45}
                      outerRadius={60}
                      paddingAngle={2}
                      dataKey="value"
                    >
                      {assetData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} stroke="none" />
                      ))}
                    </Pie>
                    <Tooltip 
                      contentStyle={{ 
                        backgroundColor: '#161b22',
                        border: '1px solid #30363d',
                        borderRadius: '6px',
                        fontSize: '12px'
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="flex flex-wrap justify-center gap-4 mt-2 text-sm">
                {assetData.map((item) => (
                  <div key={item.name} className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: item.color }} />
                    <span className="text-console-text-muted">{item.name}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="h-40 flex items-center justify-center text-console-text-muted text-sm">
              {isConnected ? t('dashboard.noAssets') : t('dashboard.connectToViewAssets')}
            </div>
          )}
        </div>

        {/* 快捷操作 */}
        <div className="card">
          <h3 className="font-medium text-console-text mb-4">{t('dashboard.quickActions')}</h3>
          <div className="space-y-3">
            <Link
              to="/market"
              className="flex items-center gap-3 p-3 rounded-lg border border-console-border hover:border-console-accent/50 hover:bg-console-accent/5 transition-all"
            >
              <div className="p-2 rounded-lg bg-console-primary/10">
                <Cpu size={18} className="text-console-primary" />
              </div>
              <div className="flex-1">
                <div className="text-sm font-medium text-console-text">{t('dashboard.rentCompute')}</div>
                <div className="text-xs text-console-text-muted">{t('dashboard.rentComputeDesc')}</div>
              </div>
              <ArrowUpRight size={16} className="text-console-text-muted" />
            </Link>

            <Link
              to="/tasks"
              className="flex items-center gap-3 p-3 rounded-lg border border-console-border hover:border-console-accent/50 hover:bg-console-accent/5 transition-all"
            >
              <div className="p-2 rounded-lg bg-console-accent/10">
                <Play size={18} className="text-console-accent" />
              </div>
              <div className="flex-1">
                <div className="text-sm font-medium text-console-text">{t('dashboard.createTask')}</div>
                <div className="text-xs text-console-text-muted">{t('dashboard.createTaskDesc')}</div>
              </div>
              <ArrowUpRight size={16} className="text-console-text-muted" />
            </Link>

            <Link
              to="/wallet"
              className="flex items-center gap-3 p-3 rounded-lg border border-console-border hover:border-console-accent/50 hover:bg-console-accent/5 transition-all"
            >
              <div className="p-2 rounded-lg bg-console-warning/10">
                <TrendingUp size={18} className="text-console-warning" />
              </div>
              <div className="flex-1">
                <div className="text-sm font-medium text-console-text">{t('dashboard.exchangeSectorCoin')}</div>
                <div className="text-xs text-console-text-muted">{t('dashboard.exchangeDesc')}</div>
              </div>
              <ArrowUpRight size={16} className="text-console-text-muted" />
            </Link>

            <Link
              to="/mining"
              className="flex items-center gap-3 p-3 rounded-lg border border-console-border hover:border-console-accent/50 hover:bg-console-accent/5 transition-all"
            >
              <div className={`p-2 rounded-lg ${miningStatus?.isMining ? 'bg-green-500/20' : 'bg-console-border/50'}`}>
                <Hammer size={18} className={miningStatus?.isMining ? 'text-green-400' : 'text-console-text-muted'} />
              </div>
              <div className="flex-1">
                <div className="text-sm font-medium text-console-text">
                  {miningStatus?.isMining ? t('dashboard.miningActive') : t('dashboard.startMining')}
                </div>
                <div className="text-xs text-console-text-muted">
                  {miningStatus?.isMining 
                    ? `${t('dashboard.minedBlocks')} ${miningStatus.blocksMined} ${t('dashboard.blocks')}` 
                    : t('dashboard.startMiningDesc')}
                </div>
              </div>
              <ArrowUpRight size={16} className="text-console-text-muted" />
            </Link>
          </div>
        </div>
      </div>

      {/* 最近任务 */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-medium text-console-text">{t('dashboard.recentTasks')}</h3>
          <Link to="/tasks" className="text-sm text-console-accent hover:underline">
            {t('common.viewAll')}
          </Link>
        </div>

        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3].map(i => (
              <div key={i} className="flex items-center gap-4">
                <div className="h-10 w-10 skeleton rounded" />
                <div className="flex-1">
                  <div className="h-4 w-48 skeleton mb-2" />
                  <div className="h-3 w-32 skeleton" />
                </div>
              </div>
            ))}
          </div>
        ) : recentTasks.length > 0 ? (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>{t('dashboard.taskId')}</th>
                  <th>{t('dashboard.name')}</th>
                  <th>{t('dashboard.gpu')}</th>
                  <th>{t('common.status')}</th>
                  <th>{t('common.progress')}</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {recentTasks.map((task) => (
                  <tr key={task.id}>
                    <td className="font-mono text-xs text-console-text-muted">
                      {task.id.slice(0, 8)}...
                    </td>
                    <td className="font-medium">{task.title}</td>
                    <td className="text-console-text-muted">{task.gpu || 'N/A'}</td>
                    <td><TaskStatusBadge status={task.status} /></td>
                    <td>
                      <div className="flex items-center gap-2">
                        <div className="progress-bar w-20">
                          <div 
                            className="progress-fill" 
                            style={{ width: `${task.progress}%` }}
                          />
                        </div>
                        <span className="text-xs text-console-text-muted">{task.progress}%</span>
                      </div>
                    </td>
                    <td>
                      <Link 
                        to={`/tasks/${task.id}`}
                        className="text-console-accent hover:underline text-sm"
                      >
                        {t('common.details')}
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-8 text-console-text-muted">
            <Clock size={32} className="mx-auto mb-2 opacity-50" />
            <p>{t('dashboard.noTasks')}</p>
            <Link to="/tasks" className="text-console-accent hover:underline text-sm mt-2 inline-block">
              {t('dashboard.createFirstTask')}
            </Link>
          </div>
        )}
      </div>
    </div>
  )
}
