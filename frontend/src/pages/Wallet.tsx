import { useState, useEffect } from 'react'
import { 
  Wallet as WalletIcon, 
  ArrowUpRight, 
  ArrowDownRight, 
  RefreshCw,
  Copy,
  Check,
  Star,
  Clock,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Send,
  X,
  Loader2,
  ArrowRightLeft
} from 'lucide-react'
import { useAccountStore } from '../store'
import { useTranslation } from '../i18n'
import { accountApi, Transaction, walletApi, transferApi, stakingApi, exchangeApi, type StakingRecord, type ExchangeRate } from '../api'

interface SectorBalance {
  coin: string
  symbol: string
  balance: number
  availableBalance: number  // 可转账余额（已成熟 UTXO）
  priceInMain: number
  change24h: number
}

interface StakeRecord {
  id: string
  taskId: string
  rating: number
  amount: number
  timestamp: string
  status: 'burned' | 'pending'
}

export default function Wallet() {
  const { account, isConnected, setAccount } = useAccountStore()
  const { t } = useTranslation()
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [sectorBalances, setSectorBalances] = useState<SectorBalance[]>([])
  const [stakeRecords, setStakeRecords] = useState<StakeRecord[]>([])
  const [stakingLoading, setStakingLoading] = useState(false)
  const [loading, setLoading] = useState(true)
  const [expandedSectors, setExpandedSectors] = useState(true)
  const [copied, setCopied] = useState(false)
  const [activeTab, setActiveTab] = useState<'balance' | 'transactions' | 'stakes'>('balance')
  
  // 转账相关状态
  const [showTransferModal, setShowTransferModal] = useState(false)
  const [transferTo, setTransferTo] = useState('')
  const [transferAmount, setTransferAmount] = useState('')
  const [transferSector, setTransferSector] = useState('MAIN')
  
  // 兑换相关状态
  const [showExchangeModal, setShowExchangeModal] = useState(false)
  const [exchangeRates, setExchangeRates] = useState<Record<string, ExchangeRate>>({})
  const [exchangeSector, setExchangeSector] = useState('')
  const [exchangeAmount, setExchangeAmount] = useState('')
  const [exchanging, setExchanging] = useState(false)
  const [exchangeResult, setExchangeResult] = useState<{success: boolean, message: string, toAmount?: number} | null>(null)
  const [transferMemo, setTransferMemo] = useState('')
  const [transferring, setTransferring] = useState(false)
  const [transferResult, setTransferResult] = useState<{success: boolean, message: string} | null>(null)

  // 获取当前选中币种的可转账余额
  const getAvailableBalance = () => {
    if (transferSector === 'MAIN') {
      return account?.mainBalance || 0
    }
    const sector = sectorBalances.find(s => s.symbol === transferSector)
    return sector?.availableBalance ?? sector?.balance ?? 0
  }

  // 执行转账
  const handleTransfer = async () => {
    if (!transferTo || !transferAmount) {
      setTransferResult({ success: false, message: '请填写完整转账信息' })
      return
    }
    
    const amount = parseFloat(transferAmount)
    if (isNaN(amount) || amount <= 0) {
      setTransferResult({ success: false, message: '请输入有效金额' })
      return
    }
    
    if (amount > getAvailableBalance()) {
      setTransferResult({ success: false, message: '余额不足' })
      return
    }
    
    setTransferring(true)
    setTransferResult(null)
    
    try {
      const result = await transferApi.send(transferTo, amount, transferSector, transferMemo)
      setTransferResult({ success: result.success, message: result.message })
      
      if (result.success) {
        // 刷新数据
        setTimeout(() => {
          fetchWalletData()
          setShowTransferModal(false)
          setTransferTo('')
          setTransferAmount('')
          setTransferMemo('')
          setTransferResult(null)
        }, 2000)
      }
    } catch (err) {
      setTransferResult({ success: false, message: '转账失败: ' + String(err) })
    } finally {
      setTransferring(false)
    }
  }

  // 获取兑换可得的MAIN数量
  const getExchangePreview = () => {
    const amount = parseFloat(exchangeAmount) || 0
    const rate = exchangeRates[exchangeSector]?.rate || 0.5
    return amount * rate
  }

  // 获取选中板块的可用余额
  const getExchangeAvailableBalance = () => {
    const sector = sectorBalances.find(s => s.symbol === exchangeSector)
    return sector?.availableBalance ?? sector?.balance ?? 0
  }

  // 执行兑换
  const handleExchange = async () => {
    if (!exchangeSector || !exchangeAmount) {
      setExchangeResult({ success: false, message: '请选择板块并输入金额' })
      return
    }
    
    const amount = parseFloat(exchangeAmount)
    if (isNaN(amount) || amount <= 0) {
      setExchangeResult({ success: false, message: '请输入有效金额' })
      return
    }
    
    if (amount > getExchangeAvailableBalance()) {
      setExchangeResult({ success: false, message: '板块币余额不足' })
      return
    }
    
    setExchanging(true)
    setExchangeResult(null)
    
    try {
      const result = await exchangeApi.requestExchange(exchangeSector, amount)
      setExchangeResult({ 
        success: result.success, 
        message: result.message,
        toAmount: result.toAmount
      })
      
      if (result.success) {
        // 刷新数据
        setTimeout(() => {
          fetchWalletData()
          setShowExchangeModal(false)
          setExchangeSector('')
          setExchangeAmount('')
          setExchangeResult(null)
        }, 2000)
      }
    } catch (err) {
      setExchangeResult({ success: false, message: '兑换失败: ' + String(err) })
    } finally {
      setExchanging(false)
    }
  }

  // 从后端获取实时数据
  const fetchWalletData = async () => {
    setLoading(true)
    try {
      // 获取钱包信息
      const walletInfo = await walletApi.getInfo()
      
      // 从 store 获取最新 account（避免闭包过期）
      const currentAccount = useAccountStore.getState().account
      if (walletInfo.connected && currentAccount) {
        setAccount({
          ...currentAccount,
          balance: walletInfo.mainBalance || walletInfo.balance || 0,
          mainBalance: walletInfo.mainBalance || walletInfo.balance || 0,
          sectorTotal: walletInfo.sectorTotal || 0,
          sectorBalances: walletInfo.sectorBalances || {},
          sectorAddresses: walletInfo.sectorAddresses || walletInfo.addresses || {}
        })
      }
      
      // 先获取兑换比例，然后用于板块币估值
      const ratesResult = await exchangeApi.getRates()
      let rates: Record<string, ExchangeRate> = {}
      if (ratesResult.success) {
        rates = ratesResult.rates
        setExchangeRates(rates)
      }
      
      // 构建板块余额数据（使用 API 汇率）
      const availableBalances = walletInfo.availableSectorBalances || {}
      const balances: SectorBalance[] = Object.entries(walletInfo.sectorBalances || {}).map(([symbol, balance]) => ({
        coin: `${symbol}_COIN`,
        symbol,
        balance: balance as number,
        availableBalance: (availableBalances[symbol] as number) ?? (balance as number),
        priceInMain: rates[symbol]?.rate ?? (symbol === 'H100' ? 2.5 : symbol === 'A100' ? 1.8 : symbol === 'RTX4090' ? 0.8 : 0.5),
        change24h: (rates[symbol] as { change24h?: number })?.change24h ?? 0
      }))
      setSectorBalances(balances)
      
      // 获取交易记录（使用最新地址）
      const currentAddress = useAccountStore.getState().account?.address
      const txResult = await accountApi.getTransactions(currentAddress, 20)
      setTransactions(txResult.transactions)
    } catch (err) {
      console.error('获取钱包数据失败:', err)
    } finally {
      setLoading(false)
    }
  }

  // 获取质押记录
  const fetchStakingRecords = async () => {
    setStakingLoading(true)
    try {
      const result = await stakingApi.getRecords()
      // 转换 API 数据格式
      const records: StakeRecord[] = result.records.map((r: StakingRecord) => ({
        id: r.id,
        taskId: r.taskId || `task_${r.id.slice(-6)}`,
        rating: r.rating || 5,
        amount: r.amount,
        timestamp: new Date(r.createdAt).toISOString(),
        status: r.status as 'burned' | 'pending'
      }))
      setStakeRecords(records)
    } catch (err) {
      console.error('获取质押记录失败:', err)
    } finally {
      setStakingLoading(false)
    }
  }

  useEffect(() => {
    if (isConnected) {
      fetchWalletData()
      fetchStakingRecords()
    } else {
      setLoading(false)
    }
  }, [isConnected])

  const handleCopy = () => {
    if (account?.address) {
      navigator.clipboard.writeText(account.address)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const totalMainValue = (account?.mainBalance || 0) + 
    sectorBalances.reduce((sum, s) => sum + s.balance * s.priceInMain, 0)

  if (!isConnected) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <WalletIcon size={48} className="text-console-text-muted mb-4" />
        <h2 className="text-xl font-medium text-console-text mb-2">{t('wallet.notConnected')}</h2>
        <p className="text-console-text-muted mb-6">{t('wallet.connectFirst')}</p>
        <a href="/connect" className="btn-primary">{t('header.connectWallet')}</a>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 钱包概览 */}
      <div className="wallet-balance">
        <div className="relative z-10">
          <div className="flex items-start justify-between mb-6">
            <div>
              <div className="text-sm text-console-text-muted mb-1">{t('wallet.totalAssetValue')}</div>
              <div className="text-3xl font-bold text-console-text">
                {totalMainValue.toFixed(4)} <span className="text-lg">MAIN</span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowTransferModal(true)}
                className="btn-primary py-1.5 px-4 text-sm flex items-center gap-2"
              >
                <Send size={14} />
                {t('wallet.transfer')}
              </button>
              <button
                onClick={handleCopy}
                className="btn-ghost py-1.5 px-3 text-sm flex items-center gap-2"
              >
                {copied ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
                {account?.address.slice(0, 10)}...{account?.address.slice(-6)}
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 bg-console-bg/50 rounded-lg border border-console-border">
              <div className="text-sm text-console-text-muted mb-1">MAIN 币余额</div>
              <div className="text-xl font-semibold text-console-text">
                {(account?.mainBalance || 0).toFixed(4)} MAIN
              </div>
              <div className="text-xs text-console-text-muted mt-1">
                {t('wallet.sectorCoinDesc')}
              </div>
            </div>
            <div className="p-4 bg-console-bg/50 rounded-lg border border-console-border">
              <div className="text-sm text-console-text-muted mb-1">{t('wallet.sectorCoinTotal')}</div>
              <div className="text-xl font-semibold text-console-text">
                {(account?.sectorTotal || sectorBalances.reduce((sum, s) => sum + s.balance, 0)).toFixed(4)} {t('common.coins')}
              </div>
              <div className="text-xs text-console-text-muted mt-1">
                {t('wallet.miningSectorCoinDesc')}
              </div>
            </div>
            <div className="p-4 bg-console-bg/50 rounded-lg border border-console-border">
              <div className="text-sm text-console-text-muted mb-1">{t('wallet.holdingSectors')}</div>
              <div className="text-xl font-semibold text-console-text">
                {sectorBalances.filter(s => s.balance > 0).length} 个
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 转账对话框 */}
      {showTransferModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="card w-full max-w-md mx-4">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-bold text-console-text">{t('wallet.transfer')}</h3>
              <button
                onClick={() => {
                  setShowTransferModal(false)
                  setTransferResult(null)
                }}
                className="text-console-text-muted hover:text-console-text"
              >
                <X size={20} />
              </button>
            </div>
            
            <div className="space-y-4">
              {/* 币种选择 */}
              <div>
                <label className="block text-sm text-console-text-muted mb-2">{t('wallet.selectCoin')}</label>
                <select
                  value={transferSector}
                  onChange={(e) => setTransferSector(e.target.value)}
                  className="w-full input"
                >
                  <option value="MAIN">MAIN ({t('wallet.balance')}{(account?.mainBalance || 0).toFixed(4)})</option>
                  {sectorBalances.filter(s => s.balance > 0).map(s => (
                    <option key={s.symbol} value={s.symbol}>
                      {s.symbol} ({t('wallet.balance')}{s.balance.toFixed(4)}{s.availableBalance < s.balance ? `, 可用:${s.availableBalance.toFixed(4)}` : ''})
                    </option>
                  ))}
                </select>
              </div>
              
              {/* 收款地址 */}
              <div>
                <label className="block text-sm text-console-text-muted mb-2">{t('wallet.recipientAddress')}</label>
                <input
                  type="text"
                  value={transferTo}
                  onChange={(e) => setTransferTo(e.target.value)}
                  placeholder={t('wallet.recipientPlaceholder')}
                  className="w-full input"
                />
              </div>
              
              {/* 转账金额 */}
              <div>
                <label className="block text-sm text-console-text-muted mb-2">
                  {t('wallet.transferAmount')}
                  <span className="float-right">
                    {t('wallet.available')}{getAvailableBalance().toFixed(4)} {transferSector}
                  </span>
                </label>
                {(() => {
                  const sector = sectorBalances.find(s => s.symbol === transferSector)
                  if (sector && sector.availableBalance < sector.balance) {
                    return (
                      <div className="text-xs text-yellow-400 mb-1 flex items-center gap-1">
                        <Clock size={12} />
                        {(sector.balance - sector.availableBalance).toFixed(4)} {transferSector} 待成熟（需等待更多区块确认）
                      </div>
                    )
                  }
                  return null
                })()}
                <div className="flex gap-2">
                  <input
                    type="number"
                    value={transferAmount}
                    onChange={(e) => setTransferAmount(e.target.value)}
                    placeholder="0.0000"
                    step="0.0001"
                    min="0"
                    max={getAvailableBalance()}
                    className="flex-1 input"
                  />
                  <button
                    onClick={() => setTransferAmount(getAvailableBalance().toString())}
                    className="btn-ghost px-3"
                  >
                    {t('wallet.allAmount')}
                  </button>
                </div>
              </div>
              
              {/* 备注 */}
              <div>
                <label className="block text-sm text-console-text-muted mb-2">{t('wallet.memo')}</label>
                <input
                  type="text"
                  value={transferMemo}
                  onChange={(e) => setTransferMemo(e.target.value)}
                  placeholder={t('wallet.memoPlaceholder')}
                  className="w-full input"
                />
              </div>
              
              {/* 结果提示 */}
              {transferResult && (
                <div className={`p-3 rounded-lg text-sm ${
                  transferResult.success 
                    ? 'bg-green-500/10 text-green-400 border border-green-500/20' 
                    : 'bg-red-500/10 text-red-400 border border-red-500/20'
                }`}>
                  {transferResult.message}
                </div>
              )}
              
              {/* 操作按钮 */}
              <div className="flex gap-3 pt-2">
                <button
                  onClick={() => {
                    setShowTransferModal(false)
                    setTransferResult(null)
                  }}
                  className="flex-1 btn-ghost"
                  disabled={transferring}
                >
                  {t('common.cancel')}
                </button>
                <button
                  onClick={handleTransfer}
                  className="flex-1 btn-primary flex items-center justify-center gap-2"
                  disabled={transferring || !transferTo || !transferAmount}
                >
                  {transferring ? (
                    <>
                      <RefreshCw size={16} className="animate-spin" />
                      {t('wallet.sending')}
                    </>
                  ) : (
                    <>
                      <Send size={16} />
                      {t('wallet.confirmTransfer')}
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 标签页 */}
      <div className="tabs">
        <button
          onClick={() => setActiveTab('balance')}
          className={`tab ${activeTab === 'balance' ? 'tab-active' : ''}`}
        >
          {t('wallet.assetDetail')}
        </button>
        <button
          onClick={() => setActiveTab('transactions')}
          className={`tab ${activeTab === 'transactions' ? 'tab-active' : ''}`}
        >
          {t('wallet.transactionHistory')}
        </button>
        <button
          onClick={() => setActiveTab('stakes')}
          className={`tab ${activeTab === 'stakes' ? 'tab-active' : ''}`}
        >
          {t('wallet.stakeAndReview')}
        </button>
      </div>

      {/* 资产明细 */}
      {activeTab === 'balance' && (
        <div className="space-y-4">
          {/* 主币 */}
          <div className="card">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-lg bg-console-accent/20 flex items-center justify-center">
                  <WalletIcon size={20} className="text-console-accent" />
                </div>
                <div>
                  <div className="font-medium text-console-text">MAIN</div>
                  <div className="text-sm text-console-text-muted">{t('wallet.mainCoin')}</div>
                </div>
              </div>
              <div className="text-right">
                <div className="font-semibold text-console-text">
                  {(account?.mainBalance || 0).toFixed(4)}
                </div>
                <div className="text-sm text-console-text-muted">≈ ${((account?.mainBalance || 0) * 10).toFixed(2)}</div>
              </div>
            </div>
          </div>

          {/* 板块币 */}
          <div className="card">
            <button
              onClick={() => setExpandedSectors(!expandedSectors)}
              className="w-full flex items-center justify-between"
            >
              <div className="flex items-center gap-2">
                <span className="font-medium text-console-text">{t('common.sectorCoin')}</span>
                <span className="text-sm text-console-text-muted">
                  ({sectorBalances.length} 种)
                </span>
              </div>
              {expandedSectors ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
            </button>

            {expandedSectors && (
              <div className="mt-4 space-y-3">
                {sectorBalances.length === 0 ? (
                  <div className="text-center py-4 text-console-text-muted text-sm">
                    暂无板块币
                  </div>
                ) : sectorBalances.map((sector) => (
                  <div 
                    key={sector.coin}
                    className="flex items-center justify-between p-3 bg-console-bg/50 rounded-lg"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-console-primary/20 flex items-center justify-center text-xs font-bold text-console-primary">
                        {sector.symbol.slice(0, 2)}
                      </div>
                      <div>
                        <div className="font-medium text-console-text">{sector.symbol}</div>
                        <div className="text-xs text-console-text-muted">1 = {sector.priceInMain} MAIN</div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-medium text-console-text">
                        {sector.balance > 0 ? sector.balance.toFixed(2) : '-'}
                      </div>
                      {sector.balance > 0 && (
                        <div className={`text-xs flex items-center justify-end gap-1 ${sector.change24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {sector.change24h >= 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
                          {Math.abs(sector.change24h)}%
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 兑换入口 */}
          <div 
            className="card card-hover cursor-pointer"
            onClick={() => {
              // 默认选中第一个有余额的板块
              const firstWithBalance = sectorBalances.find(s => s.balance > 0)
              if (firstWithBalance) {
                setExchangeSector(firstWithBalance.symbol)
              }
              setShowExchangeModal(true)
            }}
          >
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-lg bg-console-warning/10">
                <ArrowRightLeft size={24} className="text-console-warning" />
              </div>
              <div className="flex-1">
                <div className="font-medium text-console-text">兑换板块币 → MAIN</div>
                <div className="text-sm text-console-text-muted">
                  将板块币兑换为主币 MAIN（双见证机制）
                </div>
              </div>
              <ArrowUpRight className="text-console-text-muted" />
            </div>
          </div>
        </div>
      )}

      {/* 兑换对话框 */}
      {showExchangeModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="card w-full max-w-md mx-4">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-bold text-console-text">板块币 → MAIN 兑换</h3>
              <button
                onClick={() => {
                  setShowExchangeModal(false)
                  setExchangeResult(null)
                }}
                className="text-console-text-muted hover:text-console-text"
              >
                <X size={20} />
              </button>
            </div>
            
            {/* 兑换说明 */}
            <div className="mb-4 p-3 bg-console-warning/10 rounded-lg border border-console-warning/20">
              <div className="flex items-start gap-2 text-sm text-console-warning">
                <AlertTriangle size={16} className="shrink-0 mt-0.5" />
                <div>
                  <div className="font-medium">双见证兑换机制</div>
                  <div className="text-xs opacity-80 mt-1">
                    兑换需要至少 2 个板块验证见证后完成，板块币将被销毁并铸造等值 MAIN
                  </div>
                </div>
              </div>
            </div>
            
            <div className="space-y-4">
              {/* 选择板块币 */}
              <div>
                <label className="block text-sm text-console-text-muted mb-2">选择板块币</label>
                <select
                  value={exchangeSector}
                  onChange={(e) => setExchangeSector(e.target.value)}
                  className="w-full input"
                >
                  <option value="">请选择板块</option>
                  {sectorBalances.filter(s => s.balance > 0).map(s => (
                    <option key={s.symbol} value={s.symbol}>
                      {s.symbol}_COIN ({t('wallet.balance')}{s.balance.toFixed(4)}, 比例: 1:{exchangeRates[s.symbol]?.rate || 0.5})
                    </option>
                  ))}
                </select>
              </div>
              
              {/* 兑换金额 */}
              <div>
                <label className="block text-sm text-console-text-muted mb-2">
                  兑换数量
                  <span className="float-right">
                    {t('wallet.available')}{getExchangeAvailableBalance().toFixed(4)} {exchangeSector || '---'}
                  </span>
                </label>
                <div className="flex gap-2">
                  <input
                    type="number"
                    value={exchangeAmount}
                    onChange={(e) => setExchangeAmount(e.target.value)}
                    placeholder="0.0000"
                    step="0.0001"
                    min="0"
                    max={getExchangeAvailableBalance()}
                    className="flex-1 input"
                  />
                  <button
                    onClick={() => setExchangeAmount(getExchangeAvailableBalance().toString())}
                    className="btn-ghost px-3"
                    disabled={!exchangeSector}
                  >
                    {t('wallet.allAmount')}
                  </button>
                </div>
              </div>
              
              {/* 兑换预览 */}
              {exchangeSector && exchangeAmount && parseFloat(exchangeAmount) > 0 && (
                <div className="p-4 bg-console-bg/80 rounded-lg border border-console-border">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-console-text-muted">支出</span>
                    <span className="text-console-text font-medium">
                      {parseFloat(exchangeAmount).toFixed(4)} {exchangeSector}_COIN
                    </span>
                  </div>
                  <div className="flex items-center justify-center my-2">
                    <ArrowDownRight size={20} className="text-console-accent" />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-console-text-muted">获得</span>
                    <span className="text-green-400 font-bold text-lg">
                      {getExchangePreview().toFixed(4)} MAIN
                    </span>
                  </div>
                  <div className="text-center text-xs text-console-text-muted mt-2">
                    兑换比例: 1 {exchangeSector}_COIN = {exchangeRates[exchangeSector]?.rate || 0.5} MAIN
                  </div>
                </div>
              )}
              
              {/* 结果提示 */}
              {exchangeResult && (
                <div className={`p-3 rounded-lg text-sm ${
                  exchangeResult.success 
                    ? 'bg-green-500/10 text-green-400 border border-green-500/20' 
                    : 'bg-red-500/10 text-red-400 border border-red-500/20'
                }`}>
                  {exchangeResult.message}
                  {exchangeResult.success && exchangeResult.toAmount && (
                    <div className="mt-1 font-medium">
                      已获得: {exchangeResult.toAmount.toFixed(4)} MAIN
                    </div>
                  )}
                </div>
              )}
              
              {/* 操作按钮 */}
              <div className="flex gap-3 pt-2">
                <button
                  onClick={() => {
                    setShowExchangeModal(false)
                    setExchangeResult(null)
                  }}
                  className="flex-1 btn-ghost"
                  disabled={exchanging}
                >
                  {t('common.cancel')}
                </button>
                <button
                  onClick={handleExchange}
                  className="flex-1 btn-primary flex items-center justify-center gap-2"
                  disabled={exchanging || !exchangeSector || !exchangeAmount || parseFloat(exchangeAmount) <= 0}
                >
                  {exchanging ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      兑换中...
                    </>
                  ) : (
                    <>
                      <ArrowRightLeft size={16} />
                      确认兑换
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 交易流水 */}
      {activeTab === 'transactions' && (
        <div className="card">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <RefreshCw className="animate-spin text-console-accent" />
            </div>
          ) : transactions.length > 0 ? (
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>类型</th>
                    <th>金额</th>
                    <th>币种</th>
                    <th>状态</th>
                    <th>时间</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((tx) => (
                    <tr key={tx.txId}>
                      <td>
                        <div className="flex items-center gap-2">
                          {tx.to === account?.address ? (
                            <ArrowDownRight size={16} className="text-green-400" />
                          ) : (
                            <ArrowUpRight size={16} className="text-red-400" />
                          )}
                          <span>{tx.to === account?.address ? '收入' : '支出'}</span>
                        </div>
                      </td>
                      <td className={tx.to === account?.address ? 'text-green-400' : 'text-red-400'}>
                        {tx.to === account?.address ? '+' : '-'}{tx.amount}
                      </td>
                      <td>{tx.coin || 'MAIN'}</td>
                      <td>
                        <span className={`badge ${tx.status === 'confirmed' ? 'badge-success' : 'badge-warning'}`}>
                          {tx.status === 'confirmed' ? '已确认' : '待确认'}
                        </span>
                      </td>
                      <td className="text-console-text-muted text-sm">
                        {new Date(tx.timestamp).toLocaleString('zh-CN')}
                      </td>
                      <td>
                        <button className="text-console-accent hover:underline text-sm">
                          <ExternalLink size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center py-8 text-console-text-muted">
              <Clock size={32} className="mx-auto mb-2 opacity-50" />
              <p>暂无交易记录</p>
            </div>
          )}
        </div>
      )}

      {/* 质押与评价 */}
      {activeTab === 'stakes' && (
        <div className="space-y-4">
          {/* 说明 */}
          <div className="alert alert-info">
            <AlertTriangle size={18} className="shrink-0" />
            <div>
              <div className="font-medium">质押评价说明</div>
              <div className="text-sm opacity-80">
                任务完成后可进行质押评价，质押金额 = 算力费用 × 0.1%，质押金将直接销毁并影响评分权重
              </div>
            </div>
          </div>

          <div className="card">
            {stakingLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="animate-spin text-console-cyan" size={24} />
              </div>
            ) : stakeRecords.length > 0 ? (
              <div className="space-y-4">
                {stakeRecords.map((record) => (
                  <div 
                    key={record.id}
                    className="flex items-center justify-between p-4 bg-console-bg/50 rounded-lg"
                  >
                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-1">
                        {[...Array(5)].map((_, i) => (
                          <Star 
                            key={i} 
                            size={16} 
                            className={i < record.rating ? 'text-yellow-400 fill-yellow-400' : 'text-console-border'} 
                          />
                        ))}
                      </div>
                      <div>
                        <div className="text-sm font-medium text-console-text">
                          任务 {record.taskId}
                        </div>
                        <div className="text-xs text-console-text-muted">
                          {new Date(record.timestamp).toLocaleString('zh-CN')}
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-medium text-red-400">
                        -{record.amount} MAIN
                      </div>
                      <div className="text-xs text-console-text-muted">
                        {record.status === 'burned' ? '已销毁' : '待处理'}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-console-text-muted">
                <Star size={32} className="mx-auto mb-2 opacity-50" />
                <p>暂无质押评价记录</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
