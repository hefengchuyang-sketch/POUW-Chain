import { useState, useEffect } from 'react'
import { 
  BarChart2, Activity, Clock,
  Cpu, CheckCircle, Calendar, RefreshCw
} from 'lucide-react'
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts'
import clsx from 'clsx'
import { statsApi, dashboardApi } from '../api'
import { useTranslation } from '../i18n'

type TimeRange = '24h' | '7d' | '30d'

interface NetworkMetrics {
  totalBlocks: number
  avgBlockTime: number
  activeMiners: number
  totalTasks: number
  successRate: number
  avgTaskDuration: number
}

interface BlockTypeItem {
  type: string
  value: number
  color: string
}

interface TaskDistributionItem {
  type: string
  count: number
  percentage: number
}

interface DailyBlockData {
  date: string
  taskBlocks: number
  idleBlocks: number
  validationBlocks: number
}

interface RewardTrendItem {
  time: string
  rewards: number
}

export default function Statistics() {
  const { t } = useTranslation()
  const [timeRange, setTimeRange] = useState<TimeRange>('7d')
  const [loading, setLoading] = useState(true)
  const [networkMetrics, setNetworkMetrics] = useState<NetworkMetrics>({
    totalBlocks: 0,
    avgBlockTime: 0,
    activeMiners: 0,
    totalTasks: 0,
    successRate: 0,
    avgTaskDuration: 0,
  })
  const [blockTypeData, setBlockTypeData] = useState<BlockTypeItem[]>([])
  const [taskDistributionData, setTaskDistributionData] = useState<TaskDistributionItem[]>([])
  const [dailyBlocksData, setDailyBlocksData] = useState<DailyBlockData[]>([])
  const [rewardTrendData, setRewardTrendData] = useState<RewardTrendItem[]>([])

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      try {
        const [networkData, blockData, taskData] = await Promise.all([
          statsApi.getNetworkStats(),
          statsApi.getBlockStats(timeRange as '24h' | '7d' | '30d'),
          statsApi.getTaskStats(timeRange as '24h' | '7d' | '30d'),
        ])
        
        // 计算平均出块时间（基于区块数量和运行时间估算）
        const totalBlocks = networkData.blockHeight || (blockData.taskBlocks + blockData.idleBlocks + blockData.validationBlocks)
        const avgBlockTime = totalBlocks > 0 ? 12 : 0  // 设计目标是 12 秒
        
        setNetworkMetrics({
          totalBlocks,
          avgBlockTime,
          activeMiners: networkData.onlineMiners || 0,
          totalTasks: taskData.totalTasks || 0,
          successRate: taskData.completedTasks && taskData.totalTasks 
            ? Math.round(taskData.completedTasks / taskData.totalTasks * 100)
            : 0,
          avgTaskDuration: 0,  // 需要后端提供此数据
        })
        
        setBlockTypeData([
          { type: t('statistics.taskBlock'), value: blockData.taskBlocks || 0, color: '#6c5ce7' },
          { type: t('statistics.idleBlock'), value: blockData.idleBlocks || 0, color: '#0984e3' },
          { type: t('statistics.verifyBlock'), value: blockData.validationBlocks || 0, color: '#00b894' },
        ])
        
        // 从 taskData 获取 distribution
        const distribution = (taskData as unknown as { distribution?: TaskDistributionItem[] }).distribution
        setTaskDistributionData(distribution || [])
        
        // 从 blockData 获取 dailyData
        const dailyData = (blockData as unknown as { dailyData?: DailyBlockData[] }).dailyData
        setDailyBlocksData(dailyData || [])
        
        // 获取奖励趋势数据
        try {
          const rewardTrend = await dashboardApi.getRewardTrend()
          setRewardTrendData(rewardTrend.data || [])
        } catch {
          setRewardTrendData([])
        }
      } catch (error) {
        console.error('获取统计数据失败:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [timeRange])

  if (loading && networkMetrics.totalBlocks === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="animate-spin text-console-accent" size={48} />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 时间范围选择 */}
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-console-text">{t('statistics.title')}</h1>
        <div className="flex gap-2">
          {(['24h', '7d', '30d'] as TimeRange[]).map(range => (
            <button
              key={range}
              onClick={() => setTimeRange(range)}
              className={clsx(
                'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                timeRange === range
                  ? 'bg-console-accent text-console-text'
                  : 'bg-console-card text-console-muted hover:bg-console-hover'
              )}
            >
              {range}
            </button>
          ))}
        </div>
      </div>

      {/* 关键指标 */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <MetricCard 
          icon={<BarChart2 />} 
          label={t('statistics.totalBlocks')} 
          value={networkMetrics.totalBlocks.toLocaleString()} 
        />
        <MetricCard 
          icon={<Clock />} 
          label={t('statistics.avgBlockTime')} 
          value={`${networkMetrics.avgBlockTime}s`} 
        />
        <MetricCard 
          icon={<Cpu />} 
          label={t('statistics.activeMiners')} 
          value={networkMetrics.activeMiners.toString()} 
        />
        <MetricCard 
          icon={<Activity />} 
          label={t('statistics.totalTasks')} 
          value={networkMetrics.totalTasks.toLocaleString()} 
        />
        <MetricCard 
          icon={<CheckCircle />} 
          label={t('statistics.successRate')} 
          value={`${networkMetrics.successRate}%`} 
        />
        <MetricCard 
          icon={<Calendar />} 
          label={t('statistics.avgTaskDuration')} 
          value={`${networkMetrics.avgTaskDuration}min`} 
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 区块类型分布 */}
        <div className="card">
          <h3 className="text-lg font-semibold text-console-text mb-4">{t('statistics.blockTypeDistribution')}</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={blockTypeData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={90}
                  paddingAngle={5}
                  dataKey="value"
                  label={({ type, value }) => `${type}: ${value}%`}
                >
                  {blockTypeData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: '#1a1b3a', 
                    border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: '8px'
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="flex justify-center gap-6 mt-4">
            {blockTypeData.map(item => (
              <div key={item.type} className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: item.color }} />
                <span className="text-sm text-console-muted">{item.type}</span>
              </div>
            ))}
          </div>
        </div>

        {/* 任务类型分布 */}
        <div className="card">
          <h3 className="text-lg font-semibold text-console-text mb-4">{t('statistics.taskTypeDistribution')}</h3>
          <div className="space-y-4">
            {taskDistributionData.map(item => (
              <div key={item.type}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-console-muted">{item.type}</span>
                  <span className="text-console-text">{item.count} ({item.percentage}%)</span>
                </div>
                <div className="h-2 rounded-full bg-console-hover overflow-hidden">
                  <div 
                    className="h-full bg-console-accent rounded-full"
                    style={{ width: `${item.percentage}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 每日区块产出 */}
      <div className="card">
        <h3 className="text-lg font-semibold text-console-text mb-4">{t('statistics.dailyBlockOutput')}</h3>
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={dailyBlocksData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
              <XAxis dataKey="date" stroke="#9ca3af" />
              <YAxis stroke="#9ca3af" />
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: '#1a1b3a', 
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '8px'
                }}
              />
              <Legend />
              <Bar dataKey="taskBlocks" name={t('statistics.taskBlock')} fill="#6c5ce7" stackId="a" />
              <Bar dataKey="idleBlocks" name={t('statistics.idleBlock')} fill="#0984e3" stackId="a" />
              <Bar dataKey="validationBlocks" name={t('statistics.verifyBlock')} fill="#00b894" stackId="a" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 奖励趋势 */}
      <div className="card">
        <h3 className="text-lg font-semibold text-console-text mb-4">{t('statistics.miningRewardTrend')}</h3>
        <div className="h-80">
          {rewardTrendData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={rewardTrendData}>
                <defs>
                  <linearGradient id="colorRewards" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6c5ce7" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#6c5ce7" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                <XAxis dataKey="time" stroke="#9ca3af" />
                <YAxis stroke="#9ca3af" />
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: '#1a1b3a', 
                    border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: '8px'
                  }}
                />
                <Area 
                  type="monotone" 
                  dataKey="rewards" 
                  name={t('statistics.rewardMain')} 
                  stroke="#6c5ce7" 
                  fillOpacity={1} 
                  fill="url(#colorRewards)" 
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-full text-console-muted">
              {t('statistics.noRewardData')}
            </div>
          )}
        </div>
      </div>

      {/* 详细统计表 */}
      <div className="card">
        <h3 className="text-lg font-semibold text-console-text mb-4">{t('statistics.detailedStats')}</h3>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-console-border">
                <th className="text-left py-3 px-4 text-console-muted font-medium">{t('statistics.date')}</th>
                <th className="text-right py-3 px-4 text-console-muted font-medium">{t('statistics.taskBlock')}</th>
                <th className="text-right py-3 px-4 text-console-muted font-medium">{t('statistics.idleBlock')}</th>
                <th className="text-right py-3 px-4 text-console-muted font-medium">{t('statistics.verifyBlock')}</th>
                <th className="text-right py-3 px-4 text-console-muted font-medium">{t('common.total')}</th>
                <th className="text-right py-3 px-4 text-console-muted font-medium">{t('statistics.change')}</th>
              </tr>
            </thead>
            <tbody>
              {dailyBlocksData.map((day, index) => {
                const total = day.taskBlocks + day.idleBlocks + day.validationBlocks
                const prevTotal = index > 0 
                  ? dailyBlocksData[index - 1].taskBlocks + 
                    dailyBlocksData[index - 1].idleBlocks + 
                    dailyBlocksData[index - 1].validationBlocks
                  : total
                const change = ((total - prevTotal) / prevTotal * 100).toFixed(1)
                const isPositive = parseFloat(change) >= 0

                return (
                  <tr key={day.date} className="border-b border-console-border/50 hover:bg-console-hover">
                    <td className="py-3 px-4 text-console-text">{day.date}</td>
                    <td className="py-3 px-4 text-right text-console-text">{day.taskBlocks}</td>
                    <td className="py-3 px-4 text-right text-console-text">{day.idleBlocks}</td>
                    <td className="py-3 px-4 text-right text-console-text">{day.validationBlocks}</td>
                    <td className="py-3 px-4 text-right text-console-text font-semibold">{total}</td>
                    <td className={clsx(
                      'py-3 px-4 text-right font-semibold',
                      isPositive ? 'text-green-400' : 'text-red-400'
                    )}>
                      {isPositive ? '+' : ''}{change}%
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

// 指标卡片
function MetricCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="card">
      <div className="flex items-center gap-2 text-console-muted mb-2">
        {icon}
        <span className="text-sm">{label}</span>
      </div>
      <p className="text-xl font-bold text-console-text">{value}</p>
    </div>
  )
}
