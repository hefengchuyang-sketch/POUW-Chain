import { useState, useEffect } from 'react'
import { 
  Cpu, 
  Star, 
  Clock, 
  ShoppingCart,
  AlertTriangle,
  CheckCircle,
  RefreshCw,
  Info,
  X
} from 'lucide-react'
import { useAccountStore, useNotificationStore } from '../store'
import { minerApi, orderbookApi } from '../api'
import { useTranslation } from '../i18n'

interface GpuSector {
  id: string
  name: string
  type: string
  pricePerHour: number  // MAIN per GPU per hour
  availableBlocks: number
  totalGpus: number
  avgRating: number
  features: string[]
  specs: {
    memory: string
    tflops: number
    cuda: number
  }
}

interface ComputeBlock {
  blockId: string
  sectorId: string
  gpuCount: number
  status: 'available' | 'busy' | 'maintenance'
  rating: number
  completedTasks: number
  slaScore: number
  environment: string[]
}

// GPU 规格信息
const GPU_SPECS: Record<string, { memory: string; tflops: number; cuda: number; features: string[]; price: number; displayName: string }> = {
  'H100': { memory: '80GB HBM3', tflops: 1979, cuda: 16896, features: ['NVLink', 'HBM3', 'FP8 Training'], price: 2.5, displayName: 'NVIDIA H100' },
  'A100': { memory: '80GB HBM2e', tflops: 312, cuda: 6912, features: ['Multi-Instance GPU', 'HBM2e', 'TF32'], price: 1.8, displayName: 'NVIDIA A100' },
  'RTX4090': { memory: '24GB GDDR6X', tflops: 82.6, cuda: 16384, features: ['Ada Lovelace', 'DLSS 3', 'AV1 Encode'], price: 0.8, displayName: 'GeForce RTX 4090' },
  'RTX4080': { memory: '16GB GDDR6X', tflops: 48.7, cuda: 9728, features: ['Ada Lovelace', 'DLSS 3'], price: 0.65, displayName: 'GeForce RTX 4080' },
  'RTX3090': { memory: '24GB GDDR6X', tflops: 35.6, cuda: 10496, features: ['Ampere', 'DLSS', 'Ray Tracing'], price: 0.5, displayName: 'GeForce RTX 3090' },
  'RTX3080': { memory: '12GB GDDR6X', tflops: 29.8, cuda: 8960, features: ['Ampere', 'DLSS'], price: 0.4, displayName: 'GeForce RTX 3080' },
  'CPU': { memory: 'CPU', tflops: 1, cuda: 0, features: ['CPU'], price: 0.1, displayName: 'CPU' },
}

// 从GPU名称解析规格
function parseGpuType(gpuName: string): { key: string; specs: typeof GPU_SPECS['H100'] } {
  const name = gpuName.toUpperCase()
  
  // 按优先级匹配
  if (name.includes('H100')) return { key: 'H100', specs: GPU_SPECS['H100'] }
  if (name.includes('A100')) return { key: 'A100', specs: GPU_SPECS['A100'] }
  if (name.includes('4090')) return { key: 'RTX4090', specs: GPU_SPECS['RTX4090'] }
  if (name.includes('4080')) return { key: 'RTX4080', specs: GPU_SPECS['RTX4080'] }
  if (name.includes('3090')) return { key: 'RTX3090', specs: GPU_SPECS['RTX3090'] }
  if (name.includes('3080')) return { key: 'RTX3080', specs: GPU_SPECS['RTX3080'] }
  if (name.includes('3070')) return { key: 'RTX3080', specs: { ...GPU_SPECS['RTX3080'], displayName: 'GeForce RTX 3070', price: 0.35 } }
  if (name.includes('CPU') || name === '通用GPU') return { key: 'CPU', specs: GPU_SPECS['CPU'] }
  
  // 默认：通用GPU
  return { 
    key: 'GPU', 
    specs: { memory: 'General', tflops: 20, cuda: 8000, features: ['General'], price: 0.3, displayName: gpuName || 'GPU' } 
  }
}

export default function Market() {
  const { t } = useTranslation()
  const { isConnected } = useAccountStore()
  const { addNotification } = useNotificationStore()
  const [sectors, setSectors] = useState<GpuSector[]>([])
  const [blocks, setBlocks] = useState<ComputeBlock[]>([])
  const [selectedSector, setSelectedSector] = useState<GpuSector | null>(null)
  const [selectedBlock, setSelectedBlock] = useState<ComputeBlock | null>(null)
  const [loading, setLoading] = useState(true)
  const [showOrderPanel, setShowOrderPanel] = useState(false)
  const [ordering, setOrdering] = useState(false)
  const [freeOrder, setFreeOrder] = useState(false)
  
  // 订单参数
  const [orderDuration, setOrderDuration] = useState(1) // 小时
  
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      try {
        // 获取矿工列表作为算力提供者
        const minerResult = await minerApi.getMiners()
        const miners = minerResult.miners || []
        
        // 从矿工数据构建板块信息
        const sectorMap = new Map<string, GpuSector>()
        const blockList: ComputeBlock[] = []
        
        miners.forEach((miner) => {
          const gpuName = miner.gpuType || 'GPU'
          const { key: gpuKey, specs } = parseGpuType(gpuName)
          const sectorId = gpuKey.toLowerCase()
          
          // 更新或创建板块
          if (!sectorMap.has(sectorId)) {
            sectorMap.set(sectorId, {
              id: sectorId,
              name: specs.displayName,
              type: gpuKey,
              pricePerHour: specs.price,
              availableBlocks: 0,
              totalGpus: 0,
              avgRating: 0,
              features: specs.features,
              specs: { memory: specs.memory, tflops: specs.tflops, cuda: specs.cuda }
            })
          }
          
          const sector = sectorMap.get(sectorId)!
          sector.totalGpus += miner.gpuCount
          if (miner.status === 'online') {
            sector.availableBlocks += 1
          }
          // avgRating 累加求和，循环后再除以矿工数
          sector.avgRating += (miner.behaviorScore / 20)
          
          // 创建区块
          blockList.push({
            blockId: miner.minerId,
            sectorId: sectorId,
            gpuCount: miner.gpuCount,
            status: miner.status === 'online' ? 'available' : miner.status === 'busy' ? 'busy' : 'maintenance',
            rating: miner.behaviorScore / 20,
            completedTasks: miner.completedTasks,
            slaScore: miner.acceptanceRate,
            environment: ['PyTorch 2.0', 'CUDA 12.1', 'Python 3.11']
          })
        })
        
        // 计算真正的平均评分
        sectorMap.forEach(sector => {
          const minerCount = blockList.filter(b => b.sectorId === sector.id).length
          if (minerCount > 0) sector.avgRating = sector.avgRating / minerCount
        })
        
        setSectors(Array.from(sectorMap.values()))
        setBlocks(blockList)
      } catch (err) {
        console.error('获取市场数据失败:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  const handleSelectSector = (sector: GpuSector) => {
    setSelectedSector(sector)
    setSelectedBlock(null)
    setShowOrderPanel(false)
  }

  const handleSelectBlock = (block: ComputeBlock) => {
    setSelectedBlock(block)
    setShowOrderPanel(true)
  }

  const handlePlaceOrder = async () => {
    if (ordering) return
    if (!isConnected) {
      addNotification({
        type: 'warning',
        title: t('market.notConnected'),
        message: t('market.connectFirst')
      })
      return
    }
    
    if (!selectedBlock || !selectedSector) return
    
    const unitPrice = freeOrder ? 0 : selectedSector.pricePerHour
    const totalPrice = unitPrice * selectedBlock.gpuCount * orderDuration
    const taxAmount = totalPrice * 0.01
    
    setOrdering(true)
    try {
      // 通过订单簿提交买单
      const result = await orderbookApi.submitBid({
        gpuType: selectedSector.type,
        gpuCount: selectedBlock.gpuCount,
          maxPricePerHour: unitPrice,
        duration: orderDuration,
      })
      
      if (result) {
        addNotification({
          type: 'success',
          title: t('market.orderSubmitted'),
          message: t('market.orderSubmittedMsg').replace('{gpuCount}', String(selectedBlock.gpuCount)).replace('{gpuName}', selectedSector.name).replace('{duration}', String(orderDuration)).replace('{cost}', (totalPrice + taxAmount).toFixed(4))
        })
      } else {
        addNotification({
          type: 'error',
          title: t('market.orderFailed'),
          message: t('market.orderFailedMsg')
        })
      }
    } catch {
      addNotification({
        type: 'error',
        title: t('market.orderFailed'),
        message: t('market.networkError')
      })
    } finally {
      setOrdering(false)
    }
    
    setShowOrderPanel(false)
    setSelectedBlock(null)
  }

  const filteredBlocks = selectedSector 
    ? blocks.filter(b => b.sectorId === selectedSector.id)
    : []

  const calculatePrice = () => {
    if (!selectedSector || !selectedBlock) return { base: 0, tax: 0, total: 0 }
    const base = (freeOrder ? 0 : selectedSector.pricePerHour) * selectedBlock.gpuCount * orderDuration
    const tax = base * 0.01
    return { base, tax, total: base + tax }
  }

  const refreshData = async () => {
    setLoading(true)
    try {
      const minerResult = await minerApi.getMiners()
      const miners = minerResult.miners || []
      
      const sectorMap = new Map<string, GpuSector>()
      const blockList: ComputeBlock[] = []
      
      miners.forEach((miner) => {
        const gpuName = miner.gpuType || 'GPU'
        const { key: gpuKey, specs } = parseGpuType(gpuName)
        const sectorId = gpuKey.toLowerCase()
        
        if (!sectorMap.has(sectorId)) {
          sectorMap.set(sectorId, {
            id: sectorId,
            name: specs.displayName,
            type: gpuKey,
            pricePerHour: specs.price,
            availableBlocks: 0,
            totalGpus: 0,
            avgRating: 0,
            features: specs.features,
            specs: { memory: specs.memory, tflops: specs.tflops, cuda: specs.cuda }
          })
        }
        
        const sector = sectorMap.get(sectorId)!
        sector.totalGpus += miner.gpuCount
        if (miner.status === 'online') sector.availableBlocks += 1
        // avgRating 累加求和，循环后再除以矿工数
        sector.avgRating += (miner.behaviorScore / 20)
        
        blockList.push({
          blockId: miner.minerId,
          sectorId: sectorId,
          gpuCount: miner.gpuCount,
          status: miner.status === 'online' ? 'available' : miner.status === 'busy' ? 'busy' : 'maintenance',
          rating: miner.behaviorScore / 20,
          completedTasks: miner.completedTasks,
          slaScore: miner.acceptanceRate,
          environment: ['PyTorch 2.0', 'CUDA 12.1', 'Python 3.11']
        })
      })
      
      // 计算真正的平均评分
      sectorMap.forEach(sector => {
        const minerCount = blockList.filter(b => b.sectorId === sector.id).length
        if (minerCount > 0) sector.avgRating = sector.avgRating / minerCount
      })
      
      setSectors(Array.from(sectorMap.values()))
      setBlocks(blockList)
    } catch (err) {
      console.error('刷新失败:', err)
    } finally {
      setLoading(false)
    }
  }

  const prices = calculatePrice()

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-console-text">{t('market.title')}</h1>
          <p className="text-console-text-muted mt-1">{t('market.subtitle')}</p>
        </div>
        <button
          onClick={refreshData}
          className="btn-ghost flex items-center gap-2 text-sm"
        >
          <RefreshCw size={14} />
          {t('common.refresh')}
        </button>
      </div>

      {/* 板块选择 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {loading ? (
          [...Array(4)].map((_, i) => (
            <div key={i} className="card">
              <div className="h-6 w-32 skeleton mb-4" />
              <div className="h-8 w-24 skeleton mb-2" />
              <div className="h-4 w-full skeleton" />
            </div>
          ))
        ) : (
          sectors.map((sector) => (
            <div
              key={sector.id}
              onClick={() => handleSelectSector(sector)}
              className={`sector-card cursor-pointer ${selectedSector?.id === sector.id ? 'border-console-accent' : ''}`}
            >
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h3 className="font-semibold text-console-text">{sector.name}</h3>
                  <p className="text-xs text-console-text-muted">{sector.type}</p>
                </div>
                <div className="flex items-center gap-1 text-yellow-400">
                  <Star size={14} className="fill-current" />
                  <span className="text-sm">{sector.avgRating}</span>
                </div>
              </div>
              
              <div className="text-2xl font-bold text-console-accent mb-1">
                {sector.pricePerHour} <span className="text-sm font-normal text-console-text-muted">{t('market.priceUnit')}</span>
              </div>
              
              <div className="flex items-center gap-4 text-sm text-console-text-muted mb-3">
                <span className="flex items-center gap-1">
                  <Cpu size={14} />
                  {sector.availableBlocks} {t('market.blocksAvailable')}
                </span>
              </div>
              
              <div className="flex flex-wrap gap-1">
                {sector.features.slice(0, 2).map((f) => (
                  <span key={f} className="text-xs px-2 py-0.5 bg-console-bg rounded text-console-text-muted">
                    {f}
                  </span>
                ))}
              </div>
            </div>
          ))
        )}
      </div>

      {/* 区块列表 */}
      {selectedSector && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-semibold text-console-text">
                {selectedSector.name} {t('market.availableBlocks')}
              </h2>
              <span className="badge badge-info">
                {filteredBlocks.filter(b => b.status === 'available').length} {t('market.blocksAvailable')}
              </span>
            </div>
            <div className="text-sm text-console-text-muted">
              {t('market.specs')}{selectedSector.specs.memory} | {selectedSector.specs.tflops} {t('market.tflops')}
            </div>
          </div>

          <div className="alert alert-info mb-4">
            <Info size={16} className="shrink-0" />
            <span className="text-sm">
              {t('market.blockDesc')}
            </span>
          </div>

          {filteredBlocks.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredBlocks.map((block) => (
                <div
                  key={block.blockId}
                  onClick={() => block.status === 'available' && handleSelectBlock(block)}
                  className={`p-4 rounded-lg border transition-all ${
                    block.status === 'available'
                      ? 'border-console-border hover:border-console-accent cursor-pointer'
                      : 'border-console-border/50 opacity-50 cursor-not-allowed'
                  } ${selectedBlock?.blockId === block.blockId ? 'border-console-accent bg-console-accent/5' : 'bg-console-bg/50'}`}
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <div className={`status-dot ${block.status === 'available' ? 'status-dot-online' : 'status-dot-busy'}`} />
                      <span className="font-mono text-sm text-console-text-muted">{block.blockId}</span>
                    </div>
                    <div className="flex items-center gap-1 text-yellow-400">
                      <Star size={12} className="fill-current" />
                      <span className="text-xs">{block.rating}</span>
                    </div>
                  </div>
                  
                  <div className="text-lg font-semibold text-console-text mb-2">
                    {block.gpuCount}x GPU
                  </div>
                  
                  <div className="space-y-1 text-xs text-console-text-muted">
                    <div className="flex items-center gap-2">
                      <CheckCircle size={12} className="text-green-400" />
                      <span>SLA {block.slaScore}%</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Clock size={12} />
                      <span>{block.completedTasks} {t('market.completedTasksCount')}</span>
                    </div>
                  </div>
                  
                  <div className="mt-3 pt-3 border-t border-console-border">
                    <div className="text-xs text-console-text-muted mb-1">{t('market.execEnv')}</div>
                    <div className="flex flex-wrap gap-1">
                      {block.environment.slice(0, 2).map((env) => (
                        <span key={env} className="text-xs px-1.5 py-0.5 bg-console-surface rounded">
                          {env}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-console-text-muted">
              <Cpu size={32} className="mx-auto mb-2 opacity-50" />
              <p>{t('market.noBlocks')}</p>
            </div>
          )}
        </div>
      )}

      {/* 下单面板 */}
      {showOrderPanel && selectedSector && selectedBlock && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="modal max-w-md">
            <div className="modal-header flex items-center justify-between">
              <h3 className="text-lg font-semibold">{t('market.rentCompute')}</h3>
              <button onClick={() => setShowOrderPanel(false)} className="text-console-text-muted hover:text-console-text">
                <X size={20} />
              </button>
            </div>
            
            <div className="modal-body space-y-4">
              {/* 选中信息 */}
              <div className="p-4 bg-console-bg rounded-lg border border-console-border">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-console-text-muted">{t('market.gpuModel')}</span>
                  <span className="font-medium text-console-text">{selectedSector.name}</span>
                </div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-console-text-muted">{t('market.block')}</span>
                  <span className="font-mono text-console-text">{selectedBlock.blockId}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-console-text-muted">{t('market.gpuCount')}</span>
                  <span className="font-medium text-console-text">{selectedBlock.gpuCount}x</span>
                </div>
              </div>

              {/* 租用时长 */}
              <div>
                <label className="block text-sm font-medium text-console-text mb-2">
                  {t('market.rentDuration')}
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="range"
                    min="1"
                    max="24"
                    value={orderDuration}
                    onChange={(e) => setOrderDuration(Number(e.target.value))}
                    className="flex-1"
                  />
                  <div className="w-20 text-center">
                    <span className="text-lg font-bold text-console-text">{orderDuration}</span>
                    <span className="text-console-text-muted text-sm"> {t('common.hours')}</span>
                  </div>
                </div>
              </div>

              <label className="flex items-center justify-between p-3 bg-console-bg rounded-lg border border-console-border text-sm">
                <span className="text-console-text">Free Order (0 MAIN demo mode)</span>
                <input type="checkbox" checked={freeOrder} onChange={(e) => setFreeOrder(e.target.checked)} />
              </label>

              {/* 费用明细 */}
              <div className="p-4 bg-console-bg rounded-lg border border-console-border space-y-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-console-text-muted">{t('orders.computeFee')}</span>
                  <span className="text-console-text">{prices.base.toFixed(4)} MAIN</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-console-text-muted">{t('orders.taxInfo')} (1%)</span>
                  <span className="text-console-text">{prices.tax.toFixed(4)} MAIN</span>
                </div>
                <div className="flex items-center justify-between pt-2 border-t border-console-border font-medium">
                  <span className="text-console-text">{t('common.total')}</span>
                  <span className="text-lg text-console-accent">{prices.total.toFixed(4)} MAIN</span>
                </div>
              </div>

              {/* 提示 */}
              <div className="alert alert-warning text-xs">
                <AlertTriangle size={14} className="shrink-0" />
                <span>{t('market.orderLimitHint')}</span>
              </div>
            </div>

            <div className="modal-footer">
              <button onClick={() => setShowOrderPanel(false)} className="btn-secondary">
                {t('common.cancel')}
              </button>
              <button onClick={handlePlaceOrder} disabled={ordering} className="btn-primary flex items-center gap-2">
                <ShoppingCart size={16} />
                {ordering ? t('common.loading') : t('common.confirm')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
