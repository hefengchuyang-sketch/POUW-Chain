import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from '../i18n'
import { 
  Receipt, 
  Clock, 
  CheckCircle, 
  XCircle,
  RefreshCw,
  Search,
  ChevronDown,
  ExternalLink,
  AlertTriangle,
  Cpu
} from 'lucide-react'
import { useAccountStore } from '../store'
import { orderApi, type OrderData } from '../api'

type OrderStatus = 'pending' | 'executing' | 'completed' | 'failed' | 'cancelled' | 'active'

interface Order {
  orderId: string
  taskId: string
  gpuType: string
  gpuCount: number
  duration: number  // 小时
  pricePerHour: number
  totalPrice: number
  status: OrderStatus
  createdAt: string
  completedAt?: string
  taxes: {
    burn: number      // 0.5%
    miner: number     // 0.3%
    foundation: number // 0.2%
  }
}

function OrderStatusBadge({ status }: { status: OrderStatus }) {
  const { t } = useTranslation()
  const config: Record<OrderStatus, { class: string; label: string; icon: React.ReactNode }> = {
    pending: { class: 'badge-warning', label: t('orders.pendingStatus'), icon: <Clock size={12} /> },
    executing: { class: 'badge-info', label: t('orders.executingStatus'), icon: <RefreshCw size={12} className="animate-spin" /> },
    active: { class: 'badge-info', label: t('orders.executingStatus'), icon: <RefreshCw size={12} /> },
    completed: { class: 'badge-success', label: t('orders.completedStatus'), icon: <CheckCircle size={12} /> },
    failed: { class: 'badge-error', label: t('orders.failedStatus'), icon: <XCircle size={12} /> },
    cancelled: { class: 'badge-neutral', label: t('orders.cancelledStatus'), icon: <XCircle size={12} /> },
  }
  const { class: cls, label, icon } = config[status] || config.pending
  return (
    <span className={`badge ${cls} gap-1`}>
      {icon}
      {label}
    </span>
  )
}

export default function Orders() {
  const { t } = useTranslation()
  const { isConnected } = useAccountStore()
  const [orders, setOrders] = useState<Order[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [expandedOrder, setExpandedOrder] = useState<string | null>(null)

  const fetchOrders = async () => {
    setLoading(true)
    try {
      const result = await orderApi.getList(statusFilter === 'all' ? undefined : statusFilter)
      // 转换 API 数据格式
      const transformedOrders: Order[] = result.orders.map((o: OrderData) => ({
        orderId: o.id,
        taskId: `task_${o.id.slice(-8)}`,
        gpuType: o.gpuType,
        gpuCount: o.amount,
        duration: o.duration,
        pricePerHour: o.pricePerHour,
        totalPrice: o.totalPrice,
        status: o.status as OrderStatus,
        createdAt: new Date(o.createdAt).toISOString(),
        completedAt: o.completedAt ? new Date(o.completedAt).toISOString() : undefined,
        taxes: {
          burn: o.totalPrice * 0.005,
          miner: o.totalPrice * 0.003,
          foundation: o.totalPrice * 0.002,
        }
      }))
      setOrders(transformedOrders)
    } catch (error) {
      console.error('获取订单失败:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (isConnected) {
      fetchOrders()
    }
  }, [isConnected, statusFilter])

  const filteredOrders = orders.filter(order => {
    // 状态已由 API 过滤，此处仅处理搜索
    if (searchQuery && !order.orderId.includes(searchQuery) && !order.taskId.includes(searchQuery)) return false
    return true
  })

  const stats = {
    total: orders.length,
    pending: orders.filter(o => o.status === 'pending').length,
    executing: orders.filter(o => o.status === 'executing').length,
    completed: orders.filter(o => o.status === 'completed').length,
    totalSpent: orders.filter(o => o.status === 'completed').reduce((sum, o) => sum + o.totalPrice, 0),
    totalTaxes: orders.filter(o => o.status === 'completed').reduce((sum, o) => sum + o.taxes.burn + o.taxes.miner + o.taxes.foundation, 0),
  }

  if (!isConnected) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <Receipt size={48} className="text-console-text-muted mb-4" />
        <h2 className="text-xl font-medium text-console-text mb-2">{t('wallet.notConnected')}</h2>
        <p className="text-console-text-muted mb-6">{t('wallet.connectFirst')}</p>
        <a href="/connect" className="btn-primary">{t('header.connectWallet')}</a>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 统计卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="stat-card">
          <div className="stat-value">{stats.total}</div>
          <div className="stat-label">{t('orders.totalOrders')}</div>
        </div>
        <div className="stat-card">
          <div className="stat-value text-console-warning">{stats.pending + stats.executing}</div>
          <div className="stat-label">{t('orders.inProgress')}</div>
        </div>
        <div className="stat-card">
          <div className="stat-value text-console-primary">{stats.completed}</div>
          <div className="stat-label">{t('orders.completed')}</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.totalSpent.toFixed(2)}</div>
          <div className="stat-label">{t('orders.totalSpent')}</div>
        </div>
      </div>

      {/* 筛选 */}
      <div className="card">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-console-text-muted" />
            <input
              type="text"
              placeholder={t('orders.searchPlaceholder')}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input pl-9"
            />
          </div>
          <div className="flex gap-2">
            <div className="relative">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="input pr-8 appearance-none cursor-pointer"
              >
                <option value="all">{t('orders.allStatus')}</option>
                <option value="pending">{t('orders.pendingStatus')}</option>
                <option value="executing">{t('orders.executingStatus')}</option>
                <option value="completed">{t('orders.completedStatus')}</option>
                <option value="failed">{t('orders.failedStatus')}</option>
                <option value="cancelled">{t('orders.cancelledStatus')}</option>
              </select>
              <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-console-text-muted pointer-events-none" />
            </div>
          </div>
        </div>
      </div>

      {/* 订单列表 */}
      <div className="card p-0">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <RefreshCw className="animate-spin text-console-accent" size={24} />
          </div>
        ) : filteredOrders.length > 0 ? (
          <div className="divide-y divide-console-border">
            {filteredOrders.map((order) => (
              <div key={order.orderId}>
                {/* 订单头部 */}
                <div 
                  className="p-4 hover:bg-console-bg/50 cursor-pointer transition-colors"
                  onClick={() => setExpandedOrder(expandedOrder === order.orderId ? null : order.orderId)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded-lg bg-console-accent/10 flex items-center justify-center">
                        <Cpu size={20} className="text-console-accent" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-console-text">{order.gpuType}</span>
                          <span className="text-console-text-muted">× {order.gpuCount}</span>
                          <OrderStatusBadge status={order.status} />
                        </div>
                        <div className="text-sm text-console-text-muted mt-0.5">
                          {t('orders.order')} {order.orderId} · {new Date(order.createdAt).toLocaleString('zh-CN')}
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-semibold text-console-text">{order.totalPrice.toFixed(2)} MAIN</div>
                      <div className="text-sm text-console-text-muted">{order.duration} {t('common.hours')}</div>
                    </div>
                  </div>
                </div>

                {/* 订单详情 */}
                {expandedOrder === order.orderId && (
                  <div className="px-4 pb-4 bg-console-bg/30">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-4 bg-console-surface rounded-lg border border-console-border">
                      {/* 基本信息 */}
                      <div className="space-y-3">
                        <h4 className="text-sm font-medium text-console-text-muted">{t('orders.orderInfo')}</h4>
                        <div className="space-y-2 text-sm">
                          <div className="flex justify-between">
                            <span className="text-console-text-muted">{t('orders.orderId')}</span>
                            <span className="font-mono text-console-text">{order.orderId}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-console-text-muted">{t('orders.relatedTask')}</span>
                            <Link to={`/tasks/${order.taskId}`} className="text-console-accent hover:underline flex items-center gap-1">
                              {order.taskId}
                              <ExternalLink size={12} />
                            </Link>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-console-text-muted">{t('orders.gpuConfig')}</span>
                            <span className="text-console-text">{order.gpuType} × {order.gpuCount}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-console-text-muted">{t('orders.rentDuration')}</span>
                            <span className="text-console-text">{order.duration} {t('common.hours')}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-console-text-muted">{t('orders.unitPrice')}</span>
                            <span className="text-console-text">{order.pricePerHour} {t('orders.priceUnit')}</span>
                          </div>
                        </div>
                      </div>

                      {/* 费用明细 */}
                      <div className="space-y-3">
                        <h4 className="text-sm font-medium text-console-text-muted">{t('orders.feeBreakdown')}</h4>
                        <div className="space-y-2 text-sm">
                          <div className="flex justify-between">
                            <span className="text-console-text-muted">{t('orders.computeFee')}</span>
                            <span className="text-console-text">{order.totalPrice.toFixed(4)} MAIN</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-console-text-muted">{t('orders.burnTax')}</span>
                            <span className="text-red-400">-{order.taxes.burn.toFixed(4)} MAIN</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-console-text-muted">{t('orders.minerIncentive')}</span>
                            <span className="text-console-text-muted">-{order.taxes.miner.toFixed(4)} MAIN</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-console-text-muted">{t('orders.foundation')}</span>
                            <span className="text-console-text-muted">-{order.taxes.foundation.toFixed(4)} MAIN</span>
                          </div>
                          <div className="border-t border-console-border pt-2 flex justify-between font-medium">
                            <span className="text-console-text">{t('orders.totalPaid')}</span>
                            <span className="text-console-text">
                              {(order.totalPrice + order.taxes.burn + order.taxes.miner + order.taxes.foundation).toFixed(4)} MAIN
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-12 text-console-text-muted">
            <Receipt size={32} className="mx-auto mb-2 opacity-50" />
            <p>{t('orders.noOrders')}</p>
            <Link to="/market" className="text-console-accent hover:underline text-sm mt-2 inline-block">
              {t('orders.goToMarket')}
            </Link>
          </div>
        )}
      </div>

      {/* 税费说明 */}
      <div className="alert alert-info">
        <AlertTriangle size={18} className="shrink-0" />
        <div>
          <div className="font-medium">{t('orders.taxInfo')}</div>
          <div className="text-sm opacity-80">
            {t('orders.taxDesc')}
          </div>
        </div>
      </div>
    </div>
  )
}
