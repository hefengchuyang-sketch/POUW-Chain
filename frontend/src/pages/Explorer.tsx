import { useState, useEffect, useCallback } from 'react'
import {
  Search,
  Box,
  Clock,
  Hash,
  User,
  ArrowRight,
  ChevronRight,
  Coins,
  Activity,
  Layers,
  RefreshCw,
  ExternalLink,
  Copy,
  Check,
  TrendingUp,
  Database
} from 'lucide-react'
import { explorerApi, utxoApi, type Block, type TransactionInfo, type ChainInfo, type UTXOTraceItem } from '../api'
import { useTranslation } from '../i18n'

// 板块配置
const SECTORS = [
  { id: 'ALL', name: 'common.all', color: 'gray' },
  { id: 'H100', name: 'H100', color: 'purple' },
  { id: 'RTX4090', name: 'RTX 4090', color: 'green' },
  { id: 'RTX3080', name: 'RTX 3080', color: 'blue' },
  { id: 'CPU', name: 'CPU', color: 'orange' },
  { id: 'GENERAL', name: 'explorer.general', color: 'slate' },
]

// 格式化时间
const formatTime = (timestamp: number) => {
  const date = new Date(timestamp * 1000)
  return date.toLocaleString('zh-CN')
}

// 格式化相对时间
const formatRelativeTime = (timestamp: number) => {
  const now = Date.now() / 1000
  const diff = now - timestamp
  if (diff < 0) return '刚刚'
  if (diff < 60) return `${Math.floor(diff)}秒前`
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`
  return `${Math.floor(diff / 86400)}天前`
}

// 缩短哈希显示
const shortenHash = (hash: string, length: number = 8) => {
  if (!hash) return ''
  if (hash.length <= length * 2) return hash
  return `${hash.slice(0, length)}...${hash.slice(-length)}`
}

export default function Explorer() {
  const { t } = useTranslation()
  const [selectedSector, setSelectedSector] = useState('ALL')
  const [chainInfo, setChainInfo] = useState<ChainInfo | null>(null)
  const [blocks, setBlocks] = useState<Block[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedBlock, setSelectedBlock] = useState<Block | null>(null)
  const [selectedTx, setSelectedTx] = useState<TransactionInfo | null>(null)
  const [traceResult, setTraceResult] = useState<UTXOTraceItem[]>([])
  const [showTrace, setShowTrace] = useState(false)
  const [copied, setCopied] = useState('')
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [searchMessage, setSearchMessage] = useState('')

  // 加载数据
  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const sector = selectedSector === 'ALL' ? undefined : selectedSector
      const [info, blockList] = await Promise.all([
        explorerApi.getChainInfo(sector),
        explorerApi.getLatestBlocks(sector, 20)
      ])
      setChainInfo(info)
      setBlocks(blockList)
    } catch (e) {
      console.error('加载数据失败:', e)
    } finally {
      setLoading(false)
    }
  }, [selectedSector])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // 自动刷新
  useEffect(() => {
    if (!autoRefresh) return
    const interval = setInterval(fetchData, 10000)
    return () => clearInterval(interval)
  }, [autoRefresh, fetchData])

  // 搜索
  const handleSearch = async () => {
    if (!searchQuery.trim()) return
    
    setLoading(true)
    setSearchMessage('')
    try {
      const result = await explorerApi.search(searchQuery.trim())
      if (result.type === 'block') {
        setSelectedBlock(result.result as Block)
        setSelectedTx(null)
        setShowTrace(false)
        setSearchMessage(t('explorer.foundBlock'))
      } else if (result.type === 'transaction') {
        setSelectedTx(result.result as TransactionInfo)
        setSelectedBlock(null)
        setShowTrace(false)
        setSearchMessage(t('explorer.foundTransaction'))
      } else if (result.type === 'address') {
        setSearchMessage(`${t('explorer.addressBalance')}: ${(result.result as { balance: number }).balance}`)
      } else {
        setSearchMessage(t('explorer.noResults'))
      }
    } catch (e) {
      console.error('搜索失败:', e)
      setSearchMessage(t('explorer.searchFailed'))
    } finally {
      setLoading(false)
    }
  }

  // 查看区块详情
  const viewBlock = async (block: Block) => {
    setSelectedBlock(block)
    setSelectedTx(null)
    setShowTrace(false)
  }

  // 查看交易详情
  const viewTransaction = async (txId: string) => {
    setLoading(true)
    try {
      const tx = await explorerApi.getTransaction(txId)
      if (tx) {
        setSelectedTx(tx)
        setSelectedBlock(null)
        setShowTrace(false)
      }
    } catch (e) {
      console.error('获取交易失败:', e)
    } finally {
      setLoading(false)
    }
  }

  // 追溯交易来源
  const traceTransaction = async (txId: string) => {
    setLoading(true)
    try {
      const result = await utxoApi.trace(txId, 0)
      if (result.success) {
        setTraceResult(result.trace)
        setShowTrace(true)
      }
    } catch (e) {
      console.error('追溯失败:', e)
    } finally {
      setLoading(false)
    }
  }

  // 复制到剪贴板
  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text)
    setCopied(label)
    setTimeout(() => setCopied(''), 2000)
  }

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-console-text flex items-center gap-2">
            <Database className="w-7 h-7 text-console-accent" />
            {t('explorer.title')}
          </h1>
          <p className="text-console-muted mt-1">
            {t('explorer.subtitle')}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-console-muted">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded border-console-border"
            />
            {t('explorer.autoRefresh')}
          </label>
          <button
            onClick={fetchData}
            disabled={loading}
            className="btn-primary flex items-center gap-2"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            {t('common.refresh')}
          </button>
        </div>
      </div>

      {/* 搜索栏 */}
      <div className="console-card rounded-xl p-4">
        <div className="flex gap-3">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-console-muted" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder={t('explorer.searchPlaceholder')}
              className="input w-full pl-10"
            />
          </div>
          <button
            onClick={handleSearch}
            className="btn-primary px-6"
          >
            {t('common.search')}
          </button>
        </div>
        {searchMessage && (
          <p className="mt-2 text-sm text-console-muted">{searchMessage}</p>
        )}
      </div>

      {/* 板块选择 */}
      <div className="flex gap-2 overflow-x-auto pb-2">
        {SECTORS.map((sector) => (
          <button
            key={sector.id}
            onClick={() => {
              setSelectedSector(sector.id)
              setSelectedBlock(null)
              setSelectedTx(null)
              setShowTrace(false)
            }}
            className={`px-4 py-2 rounded-lg whitespace-nowrap transition-colors ${
              selectedSector === sector.id
                ? 'bg-console-accent text-white'
                : 'bg-console-card text-console-muted hover:bg-console-hover'
            }`}
          >
            {sector.id === 'GENERAL' || sector.id === 'ALL' ? t(sector.name) : sector.name}
          </button>
        ))}
      </div>

      {/* 链概览 */}
      {chainInfo && (
        <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-6 gap-4">
          <div className="console-card rounded-xl p-4">
            <div className="flex items-center gap-2 text-console-muted text-sm mb-1">
              <Layers className="w-4 h-4" />
              {t('explorer.blockHeight')}
            </div>
            <div className="text-2xl font-bold text-console-text">
              {chainInfo.height.toLocaleString()}
            </div>
          </div>
          <div className="console-card rounded-xl p-4">
            <div className="flex items-center gap-2 text-console-muted text-sm mb-1">
              <Activity className="w-4 h-4" />
              {t('explorer.totalTx')}
            </div>
            <div className="text-2xl font-bold text-console-text">
              {chainInfo.totalTransactions.toLocaleString()}
            </div>
          </div>
          <div className="console-card rounded-xl p-4">
            <div className="flex items-center gap-2 text-console-muted text-sm mb-1">
              <TrendingUp className="w-4 h-4" />
              {t('explorer.difficulty')}
            </div>
            <div className="text-2xl font-bold text-console-text">
              {chainInfo.difficulty}
            </div>
          </div>
          <div className="console-card rounded-xl p-4">
            <div className="flex items-center gap-2 text-console-muted text-sm mb-1">
              <Clock className="w-4 h-4" />
              {t('explorer.latestBlock')}
            </div>
            <div className="text-lg font-bold text-console-text">
              {chainInfo.lastBlockTime ? formatRelativeTime(chainInfo.lastBlockTime) : '-'}
            </div>
          </div>
          <div className="console-card rounded-xl p-4">
            <div className="flex items-center gap-2 text-console-muted text-sm mb-1">
              <Hash className="w-4 h-4" />
              Consensus Mode
            </div>
            <div className="text-lg font-bold text-console-text">
              {chainInfo.consensusMode || 'mixed'}
            </div>
          </div>
          <div className="console-card rounded-xl p-4">
            <div className="flex items-center gap-2 text-console-muted text-sm mb-1">
              <Coins className="w-4 h-4" />
              SBOX Ratio
            </div>
            <div className="text-lg font-bold text-console-text">
              {typeof chainInfo.consensusSboxRatio === 'number' ? `${(chainInfo.consensusSboxRatio * 100).toFixed(0)}%` : '-'}
            </div>
            <div className="text-xs text-console-muted mt-1">
              Selected: {chainInfo.consensusSelectedDistribution?.counts?.SBOX_POUW ?? 0} / {chainInfo.consensusSelectedDistribution?.window ?? 0}
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 区块列表 */}
        <div className="lg:col-span-1 console-card rounded-xl">
          <div className="p-4 border-b border-console-border">
            <h2 className="font-semibold text-console-text flex items-center gap-2">
              <Box className="w-5 h-5 text-console-accent" />
              {t('explorer.latestBlocks')}
            </h2>
          </div>
          <div className="divide-y divide-console-border max-h-[600px] overflow-y-auto">
            {blocks.length === 0 ? (
              <div className="p-8 text-center text-console-muted">
                {t('explorer.noBlockData')}
              </div>
            ) : (
              blocks.map((block) => (
                <div
                  key={`${block.sector}-${block.height}`}
                  onClick={() => viewBlock(block)}
                  className={`p-4 hover:bg-console-hover cursor-pointer transition-colors ${
                    selectedBlock?.height === block.height && selectedBlock?.sector === block.sector
                      ? 'bg-console-accent/10 border-l-4 border-console-accent'
                      : ''
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-lg font-semibold text-console-accent">
                        #{block.height}
                      </span>
                      <span className="px-2 py-0.5 text-xs rounded-full bg-console-hover text-console-muted">
                        {block.sector}
                      </span>
                    </div>
                    <span className="text-xs text-console-muted">
                      {formatRelativeTime(block.timestamp)}
                    </span>
                  </div>
                  <div className="text-sm text-console-muted space-y-1">
                    <div className="flex items-center gap-1">
                      <Hash className="w-3 h-3" />
                      <span className="font-mono">{shortenHash(block.hash)}</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <User className="w-3 h-3" />
                      <span className="font-mono">{shortenHash(block.miner, 6)}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span>{block.txCount} {t('explorer.transactions')}</span>
                      <span className="text-green-400">+{block.reward} {block.sector}</span>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* 详情面板 */}
        <div className="lg:col-span-2 space-y-4">
          {/* 区块详情 */}
          {selectedBlock && !selectedTx && !showTrace && (
            <div className="console-card rounded-xl">
              <div className="p-4 border-b border-console-border">
                <h2 className="font-semibold text-console-text flex items-center gap-2">
                  <Box className="w-5 h-5 text-green-400" />
                  {t('explorer.blockDetails')} #{selectedBlock.height}
                </h2>
              </div>
              <div className="p-4 space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="text-sm text-console-muted">{t('explorer.blockHash')}</div>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="font-mono text-sm break-all text-console-text">{selectedBlock.hash}</span>
                      <button
                        onClick={() => copyToClipboard(selectedBlock.hash, 'hash')}
                        className="p-1 hover:bg-console-hover rounded"
                      >
                        {copied === 'hash' ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4 text-console-muted" />}
                      </button>
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-console-muted">{t('explorer.prevBlockHash')}</div>
                    <div className="font-mono text-sm break-all mt-1 text-console-text">{selectedBlock.prevHash}</div>
                  </div>
                  <div>
                    <div className="text-sm text-console-muted">{t('explorer.time')}</div>
                    <div className="mt-1 text-console-text">{formatTime(selectedBlock.timestamp)}</div>
                  </div>
                  <div>
                    <div className="text-sm text-console-muted">{t('explorer.minerAddress')}</div>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="font-mono text-sm text-console-text">{shortenHash(selectedBlock.miner, 10)}</span>
                      <button
                        onClick={() => copyToClipboard(selectedBlock.miner, 'miner')}
                        className="p-1 hover:bg-console-hover rounded"
                      >
                        {copied === 'miner' ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4 text-console-muted" />}
                      </button>
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-console-muted">{t('explorer.sector')}</div>
                    <div className="mt-1">
                      <span className="badge-info">
                        {selectedBlock.sector}
                      </span>
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-console-muted">{t('explorer.blockReward')}</div>
                    <div className="mt-1 text-green-400 font-semibold">
                      +{selectedBlock.reward} {selectedBlock.sector}
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-console-muted">{t('explorer.consensusType')}</div>
                    <div className="mt-1">
                      <span className={`px-2 py-0.5 text-xs rounded font-semibold ${
                        selectedBlock.consensusType === 'SBOX_POUW'
                          ? 'bg-purple-500/20 text-purple-400'
                          : selectedBlock.consensusType === 'POUW'
                            ? 'bg-blue-500/20 text-blue-400'
                            : 'bg-gray-500/20 text-gray-400'
                      }`}>
                        {selectedBlock.consensusType === 'SBOX_POUW' ? 'S-Box PoUW' : selectedBlock.consensusType}
                      </span>
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-console-muted">{t('explorer.difficulty')}</div>
                    <div className="mt-1 text-console-text">{selectedBlock.difficulty}</div>
                  </div>
                  <div>
                    <div className="text-sm text-console-muted">{t('explorer.nonce')}</div>
                    <div className="mt-1 font-mono text-console-text">{selectedBlock.nonce}</div>
                  </div>
                </div>

                {/* S-Box PoUW 信息 */}
                {selectedBlock.sbox && (
                  <div className="border-t border-console-border pt-4 mt-4">
                    <h3 className="font-semibold text-console-text mb-3 flex items-center gap-2">
                      <span className="px-2 py-0.5 text-xs rounded bg-purple-500/20 text-purple-400">S-Box PoUW</span>
                      {t('explorer.sboxInfo')}
                    </h3>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                      <div>
                        <div className="text-sm text-console-muted">{t('explorer.sboxScore')}</div>
                        <div className="mt-1 text-purple-400 font-semibold">{selectedBlock.sbox.score}</div>
                      </div>
                      <div>
                        <div className="text-sm text-console-muted">{t('explorer.sboxNonlinearity')}</div>
                        <div className="mt-1 text-console-text">{selectedBlock.sbox.nonlinearity}</div>
                      </div>
                      <div>
                        <div className="text-sm text-console-muted">{t('explorer.sboxDiffUniformity')}</div>
                        <div className="mt-1 text-console-text">{selectedBlock.sbox.diffUniformity}</div>
                      </div>
                      <div>
                        <div className="text-sm text-console-muted">{t('explorer.sboxAvalanche')}</div>
                        <div className="mt-1 text-console-text">{selectedBlock.sbox.avalanche}</div>
                      </div>
                      <div>
                        <div className="text-sm text-console-muted">{t('explorer.sboxSector')}</div>
                        <div className="mt-1">
                          <span className="badge-info">{selectedBlock.sbox.selectedSector}</span>
                        </div>
                      </div>
                      <div>
                        <div className="text-sm text-console-muted">{t('explorer.sboxThreshold')}</div>
                        <div className="mt-1 text-console-text">{selectedBlock.sbox.scoreThreshold}</div>
                      </div>
                    </div>
                  </div>
                )}

                {/* 区块内交易 */}
                <div className="border-t border-console-border pt-4 mt-4">
                  <h3 className="font-semibold text-console-text mb-3">
                    {t('explorer.blockTx')} ({selectedBlock.txCount} {t('explorer.txCount')})
                  </h3>
                  {selectedBlock.transactions && selectedBlock.transactions.length > 0 ? (
                    <div className="space-y-2">
                      {selectedBlock.transactions.map((tx) => (
                        <div
                          key={tx.txId}
                          onClick={() => viewTransaction(tx.txId)}
                          className="p-3 bg-console-hover rounded-lg hover:bg-console-input cursor-pointer"
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className={`px-2 py-0.5 text-xs rounded ${
                                tx.txType === 'coinbase' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-blue-500/20 text-blue-400'
                              }`}>
                                {tx.txType}
                              </span>
                              <span className="font-mono text-sm text-console-text">{shortenHash(tx.txId)}</span>
                            </div>
                            <div className="text-sm font-semibold text-console-text">
                              {tx.amount} {tx.coinType}
                            </div>
                          </div>
                          <div className="mt-1 text-xs text-console-muted flex items-center gap-1">
                            <span>{shortenHash(tx.from, 6)}</span>
                            <ArrowRight className="w-3 h-3" />
                            <span>{shortenHash(tx.to, 6)}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-console-muted text-sm">
                      {t('explorer.loadFullBlockData')}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* 交易详情 */}
          {selectedTx && !showTrace && (
            <div className="console-card rounded-xl">
              <div className="p-4 border-b border-console-border flex items-center justify-between">
                <h2 className="font-semibold text-console-text flex items-center gap-2">
                  <Activity className="w-5 h-5 text-blue-400" />
                  {t('explorer.txDetails')}
                </h2>
                <button
                  onClick={() => traceTransaction(selectedTx.txId)}
                  className="btn-primary flex items-center gap-1 text-sm"
                >
                  <ExternalLink className="w-4 h-4" />
                  {t('explorer.traceFunds')}
                </button>
              </div>
              <div className="p-4 space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="col-span-2">
                    <div className="text-sm text-console-muted">{t('explorer.txId')}</div>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="font-mono text-sm break-all text-console-text">{selectedTx.txId}</span>
                      <button
                        onClick={() => copyToClipboard(selectedTx.txId, 'txid')}
                        className="p-1 hover:bg-console-hover rounded"
                      >
                        {copied === 'txid' ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4 text-console-muted" />}
                      </button>
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-console-muted">{t('common.type')}</div>
                    <div className="mt-1">
                      <span className={`px-2 py-1 rounded text-sm ${
                        selectedTx.txType === 'coinbase' 
                          ? 'bg-yellow-500/20 text-yellow-400'
                          : selectedTx.txType === 'transfer'
                          ? 'bg-blue-500/20 text-blue-400'
                          : 'bg-purple-500/20 text-purple-400'
                      }`}>
                        {selectedTx.txType}
                      </span>
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-console-muted">{t('common.status')}</div>
                    <div className="mt-1">
                      <span className={`px-2 py-1 rounded text-sm ${
                        selectedTx.status === 'confirmed' 
                          ? 'bg-green-500/20 text-green-400'
                          : 'bg-yellow-500/20 text-yellow-400'
                      }`}>
                        {selectedTx.status === 'confirmed' ? t('status.completed') : t('status.pending')}
                      </span>
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-console-muted">From</div>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="font-mono text-sm text-console-text">{selectedTx.from}</span>
                      {selectedTx.from !== 'coinbase' && (
                        <button
                          onClick={() => copyToClipboard(selectedTx.from, 'from')}
                          className="p-1 hover:bg-console-hover rounded"
                        >
                          {copied === 'from' ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4 text-console-muted" />}
                        </button>
                      )}
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-console-muted">To</div>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="font-mono text-sm text-console-text">{selectedTx.to}</span>
                      <button
                        onClick={() => copyToClipboard(selectedTx.to, 'to')}
                        className="p-1 hover:bg-console-hover rounded"
                      >
                        {copied === 'to' ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4 text-console-muted" />}
                      </button>
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-console-muted">{t('explorer.amount')}</div>
                    <div className="mt-1 text-lg font-semibold text-green-400">
                      {selectedTx.amount} {selectedTx.coinType}
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-console-muted">{t('explorer.fee')}</div>
                    <div className="mt-1 text-console-text">{selectedTx.fee} {selectedTx.coinType}</div>
                  </div>
                  <div>
                    <div className="text-sm text-console-muted">{t('explorer.blockHeight')}</div>
                    <div className="mt-1 text-console-text">#{selectedTx.blockHeight}</div>
                  </div>
                  <div>
                    <div className="text-sm text-console-muted">{t('explorer.time')}</div>
                    <div className="mt-1 text-console-text">{selectedTx.timestamp}</div>
                  </div>
                </div>

                {/* UTXO 输入输出 */}
                {selectedTx.inputs && selectedTx.inputs.length > 0 && (
                  <div className="border-t border-console-border pt-4">
                    <h3 className="font-semibold text-console-text mb-3">{t('explorer.inputUtxo')}</h3>
                    <div className="space-y-2">
                      {selectedTx.inputs.map((input, idx) => (
                        <div key={idx} className="p-2 bg-red-500/10 rounded text-sm">
                          <div className="font-mono text-xs text-console-muted">
                            {shortenHash(input.txId)}:{input.index}
                          </div>
                          <div className="text-red-400">-{input.amount}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {selectedTx.outputs && selectedTx.outputs.length > 0 && (
                  <div className="border-t border-console-border pt-4">
                    <h3 className="font-semibold text-console-text mb-3">{t('explorer.outputUtxo')}</h3>
                    <div className="space-y-2">
                      {selectedTx.outputs.map((output, idx) => (
                        <div key={idx} className="p-2 bg-green-500/10 rounded text-sm">
                          <div className="font-mono text-xs text-console-muted">
                            {t('explorer.output')} #{output.index} → {shortenHash(output.address, 10)}
                          </div>
                          <div className="text-green-400">+{output.amount}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* 资金追溯 */}
          {showTrace && traceResult.length > 0 && (
            <div className="console-card rounded-xl">
              <div className="p-4 border-b border-console-border flex items-center justify-between">
                <h2 className="font-semibold text-console-text flex items-center gap-2">
                  <Coins className="w-5 h-5 text-yellow-400" />
                  {t('explorer.fundTraceChain')} （{t('explorer.totalSteps')} {traceResult.length} {t('explorer.steps')}）
                </h2>
                <button
                  onClick={() => setShowTrace(false)}
                  className="text-sm text-console-muted hover:text-console-text"
                >
                  {t('explorer.backToTxDetails')}
                </button>
              </div>
              <div className="p-4">
                <div className="relative">
                  {/* 连接线 */}
                  <div className="absolute left-6 top-8 bottom-8 w-0.5 bg-gradient-to-b from-blue-500 via-indigo-500 to-yellow-500" />
                  
                  <div className="space-y-4">
                    {traceResult.map((item, idx) => (
                      <div key={idx} className="relative flex items-start gap-4">
                        {/* 节点 */}
                        <div className={`relative z-10 w-12 h-12 rounded-full flex items-center justify-center ${
                          item.txType === 'coinbase' 
                            ? 'bg-yellow-500 text-white'
                            : 'bg-blue-500 text-white'
                        }`}>
                          {item.txType === 'coinbase' ? (
                            <Coins className="w-6 h-6" />
                          ) : (
                            <ArrowRight className="w-6 h-6" />
                          )}
                        </div>
                        
                        {/* 内容 */}
                        <div className="flex-1 bg-console-hover rounded-lg p-4">
                          <div className="flex items-center justify-between mb-2">
                            <span className={`px-2 py-0.5 text-xs rounded ${
                              item.txType === 'coinbase' 
                                ? 'bg-yellow-500/20 text-yellow-400'
                                : 'bg-blue-500/20 text-blue-400'
                            }`}>
                              {item.txType === 'coinbase' ? t('explorer.miningRewardSource') : t('explorer.transfer')}
                            </span>
                            <span className="text-sm text-console-muted">
                              {t('explorer.blockPrefix')} #{item.blockHeight}
                            </span>
                          </div>
                          
                          <div className="text-lg font-semibold text-console-text mb-2">
                            {item.amount} {item.coinType}
                          </div>
                          
                          <div className="text-sm text-console-muted space-y-1">
                            <div className="flex items-center gap-1">
                              <span className="text-console-muted">From:</span>
                              <span className="font-mono">{shortenHash(item.from, 10)}</span>
                            </div>
                            <div className="flex items-center gap-1">
                              <span className="text-console-muted">To:</span>
                              <span className="font-mono">{shortenHash(item.to, 10)}</span>
                            </div>
                            <div className="text-xs text-console-muted">
                              {item.timestamp}
                            </div>
                          </div>
                          
                          <button
                            onClick={() => viewTransaction(item.txId)}
                            className="mt-2 text-sm text-console-accent hover:underline flex items-center gap-1"
                          >
                            {t('explorer.viewFullTx')} <ChevronRight className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                
                {/* 追溯结果总结 */}
                <div className="mt-6 p-4 bg-green-500/10 rounded-lg border border-green-500/30">
                  <div className="flex items-center gap-2 text-green-400">
                    <Check className="w-5 h-5" />
                    <span className="font-semibold">{t('explorer.fundSourceVerified')}</span>
                  </div>
                  <p className="mt-1 text-sm text-green-500">
                    {t('explorer.fundTraceDescription').replace('{blockHeight}', String(traceResult[traceResult.length - 1]?.blockHeight ?? '')).replace('{transfers}', String(traceResult.length - 1))}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* 空状态 */}
          {!selectedBlock && !selectedTx && !showTrace && (
            <div className="console-card rounded-xl p-12 text-center">
              <Database className="w-16 h-16 text-console-muted mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-console-text mb-2">
                {t('explorer.selectBlockToView')}
              </h3>
              <p className="text-console-muted">
                {t('explorer.selectBlockHint')}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
