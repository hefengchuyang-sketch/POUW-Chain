import { useState, useEffect } from 'react'
import {
  Network,
  Cpu,
  CheckCircle,
  XCircle,
  Clock,
  RefreshCw,
  Play,
  Users,
  Activity,
  Layers,
  Server
} from 'lucide-react'
import { p2pTaskApi, P2PTask, P2PTaskStats, P2PMiner } from '../api'
import { useTranslation } from '../i18n'

type P2PTaskStatus = 'CREATED' | 'ENCRYPTING' | 'DISTRIBUTING' | 'COMPUTING' | 'COLLECTING' | 'VERIFYING' | 'COMPLETED' | 'FAILED'

function P2PStatusBadge({ status }: { status: P2PTaskStatus }) {
  const { t } = useTranslation()
  const config: Record<P2PTaskStatus, { class: string; label: string; icon: React.ReactNode }> = {
    CREATED: { class: 'badge-neutral', label: t('p2p.created'), icon: <Clock size={12} /> },
    ENCRYPTING: { class: 'badge-info', label: t('p2p.encrypting'), icon: <RefreshCw size={12} className="animate-spin" /> },
    DISTRIBUTING: { class: 'badge-info', label: t('p2p.distributing'), icon: <Network size={12} /> },
    COMPUTING: { class: 'badge-warning', label: t('p2p.computing'), icon: <Cpu size={12} /> },
    COLLECTING: { class: 'badge-info', label: t('p2p.collecting'), icon: <Layers size={12} /> },
    VERIFYING: { class: 'badge-accent', label: t('p2p.verifying'), icon: <Activity size={12} /> },
    COMPLETED: { class: 'badge-success', label: t('p2p.completed2'), icon: <CheckCircle size={12} /> },
    FAILED: { class: 'badge-error', label: t('p2p.failed'), icon: <XCircle size={12} /> },
  }
  const { class: cls, label, icon } = config[status] || { class: 'badge-neutral', label: status, icon: null }
  return (
    <span className={`badge ${cls} gap-1`}>
      {icon}
      {label}
    </span>
  )
}

function ProgressBar({ progress, className = '' }: { progress: number; className?: string }) {
  return (
    <div className={`w-full bg-console-surface rounded-full h-2 ${className}`}>
      <div
        className="bg-console-primary h-2 rounded-full transition-all duration-300"
        style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
      />
    </div>
  )
}

export default function P2PTasks() {
  const { t } = useTranslation()
  const [tasks, setTasks] = useState<P2PTask[]>([])
  const [stats, setStats] = useState<P2PTaskStats | null>(null)
  const [miners, setMiners] = useState<P2PMiner[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const fetchData = async () => {
    try {
      const [taskResult, statsResult, minerResult] = await Promise.all([
        p2pTaskApi.getList({ limit: 20 }),
        p2pTaskApi.getStats(),
        p2pTaskApi.getMiners()
      ])
      setTasks(taskResult.tasks || [])
      setStats(statsResult)
      setMiners(minerResult.miners || [])
    } catch (err) {
      console.error('Failed to fetch P2P data:', err)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    fetchData()
    // 每 10 秒自动刷新
    const interval = setInterval(fetchData, 10000)
    return () => clearInterval(interval)
  }, [])

  const handleRefresh = () => {
    setRefreshing(true)
    fetchData()
  }

  const handleDistribute = async (taskId: string) => {
    try {
      const result = await p2pTaskApi.distribute(taskId)
      if (result.success) {
        fetchData()
      }
    } catch (err) {
      console.error('P2P 任务分发失败:', err)
    }
  }

  const handleCancel = async (taskId: string) => {
    try {
      const result = await p2pTaskApi.cancel(taskId)
      if (result.success) {
        fetchData()
      }
    } catch (err) {
      console.error('P2P 任务取消失败:', err)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <RefreshCw className="animate-spin text-console-accent" size={24} />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* P2P 网络状态卡片 */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Network className="text-console-primary" size={20} />
            <h2 className="text-lg font-semibold text-console-text">{t('p2p.title')}</h2>
          </div>
          <button
            onClick={handleRefresh}
            className="btn-ghost"
            disabled={refreshing}
          >
            <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
          </button>
        </div>

        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="stat-card">
              <div className="flex items-center gap-2">
                <Users className="text-console-primary" size={16} />
                <span className="stat-value">{stats.p2pConnected}</span>
              </div>
              <div className="stat-label">{t('p2p.connectedNodes')}</div>
            </div>
            <div className="stat-card">
              <div className="flex items-center gap-2">
                <Server className="text-console-accent" size={16} />
                <span className="stat-value">{stats.distributor?.availableMiners || 0}</span>
              </div>
              <div className="stat-label">{t('p2p.availableMiners')}</div>
            </div>
            <div className="stat-card">
              <div className="flex items-center gap-2">
                <Layers className="text-console-warning" size={16} />
                <span className="stat-value">{stats.distributor?.totalTasks || 0}</span>
              </div>
              <div className="stat-label">{t('p2p.totalTasks')}</div>
            </div>
            <div className="stat-card">
              <div className="flex items-center gap-2">
                <CheckCircle className="text-console-success" size={16} />
                <span className="stat-value">{stats.distributor?.completedTasks || 0}</span>
              </div>
              <div className="stat-label">{t('p2p.completed')}</div>
            </div>
          </div>
        )}
      </div>

      {/* 可用矿工列表 */}
      {miners.length > 0 && (
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <Server className="text-console-accent" size={18} />
            <h3 className="font-semibold text-console-text">{t('p2p.availableMinerNodes')}</h3>
            <span className="badge badge-neutral">{miners.length}</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {miners.slice(0, 6).map((miner) => (
              <div key={miner.node_id} className="p-3 bg-console-surface rounded-lg">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-sm text-console-text">
                    {miner.node_id.substring(0, 12)}...
                  </span>
                  {miner.is_connected && (
                    <span className="w-2 h-2 bg-console-success rounded-full" />
                  )}
                </div>
                <div className="text-xs text-console-text-muted mt-1">
                  {miner.sector || 'MAIN'} • GPU: {miner.gpu_count || 1}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* P2P 任务列表 */}
      <div className="card p-0">
        <div className="p-4 border-b border-console-border">
          <div className="flex items-center gap-2">
            <Cpu className="text-console-primary" size={18} />
            <h3 className="font-semibold text-console-text">{t('p2p.p2pTasks')}</h3>
          </div>
        </div>

        {tasks.length > 0 ? (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>{t('p2p.task')}</th>
                  <th>{t('p2p.type')}</th>
                  <th>{t('p2p.status')}</th>
                  <th>{t('p2p.progress')}</th>
                  <th>{t('p2p.shards')}</th>
                  <th>{t('p2p.operation')}</th>
                </tr>
              </thead>
              <tbody>
                {tasks.map((task) => (
                  <tr key={task.taskId}>
                    <td>
                      <div>
                        <div className="font-medium text-console-text">{task.taskName}</div>
                        <div className="text-xs text-console-text-muted font-mono">{task.taskId}</div>
                      </div>
                    </td>
                    <td>
                      <span className="badge badge-neutral">{task.taskType}</span>
                    </td>
                    <td>
                      <P2PStatusBadge status={task.status as P2PTaskStatus} />
                    </td>
                    <td>
                      <div className="flex items-center gap-2 min-w-[120px]">
                        <ProgressBar progress={task.progress} className="flex-1" />
                        <span className="text-xs text-console-text-muted">
                          {task.progress.toFixed(1)}%
                        </span>
                      </div>
                    </td>
                    <td>
                      <span className="text-sm text-console-text">
                        {task.completedShards || 0}/{task.totalShards || 0}
                      </span>
                    </td>
                    <td>
                      <div className="flex gap-2">
                        {task.status === 'CREATED' && (
                          <button
                            onClick={() => handleDistribute(task.taskId)}
                            className="btn-ghost text-console-primary"
                            title="分发任务"
                          >
                            <Play size={14} />
                          </button>
                        )}
                        {!['COMPLETED', 'FAILED'].includes(task.status) && (
                          <button
                            onClick={() => handleCancel(task.taskId)}
                            className="btn-ghost text-console-error"
                            title="取消任务"
                          >
                            <XCircle size={14} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-12 text-console-text-muted">
            <Network size={48} className="mb-4 opacity-50" />
            <p>{t('p2p.noP2pTasks')}</p>
            <p className="text-sm mt-1">{t('p2p.createTaskHint')}</p>
          </div>
        )}
      </div>

      {/* 计算节点状态 */}
      {stats?.computeNode && (
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <Cpu className="text-console-accent" size={18} />
            <h3 className="font-semibold text-console-text">{t('p2p.localNode')}</h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <div className="text-2xl font-bold text-console-text">{stats.computeNode.currentTasks}</div>
              <div className="text-sm text-console-text-muted">{t('p2p.currentTask')}</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-console-primary">{stats.computeNode.completedTasks}</div>
              <div className="text-sm text-console-text-muted">{t('p2p.completed')}</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-console-accent">
                {stats.computeNode.totalComputeTime.toFixed(1)}s
              </div>
              <div className="text-sm text-console-text-muted">{t('p2p.totalComputeTime')}</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-console-warning">
                {stats.computeNode.averageComputeTime.toFixed(2)}s
              </div>
              <div className="text-sm text-console-text-muted">{t('p2p.avgTime')}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
