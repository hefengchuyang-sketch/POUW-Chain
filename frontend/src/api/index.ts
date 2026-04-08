// API base configuration
const RPC_URL = '/rpc'  // Proxied to backend :8545 via Vite

// JSON-RPC 2.0 request ID counter
let rpcId = 1

// JSON-RPC 2.0 request function
async function rpcCall<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  
  // Attach identity header when wallet is connected (write operations require auth)
  const walletAddress = localStorage.getItem('wallet_address')
  if (walletAddress) {
    headers['X-Auth-User'] = walletAddress
  }
  
  const response = await fetch(RPC_URL, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      jsonrpc: '2.0',
      id: rpcId++,
      method,
      params,
    }),
  })
  
  if (!response.ok) {
    throw new Error(`RPC Error: ${response.status}`)
  }
  
  const result = await response.json()
  
  if (result.error) {
    throw new Error(`RPC Error ${result.error.code}: ${result.error.message}`)
  }
  
  return result.result
}

// ========== Wallet APIs ==========

export interface KeystoreFile {
  version: number
  id: string
  address: string
  crypto: {
    cipher: string
    ciphertext: string
    kdf: string
    kdfparams: {
      dklen: number
      salt: string
      c: number
      prf: string
    }
    checksum: string
  }
  created_at: number
  chain: string
}

export interface WalletCreateResult {
  success: boolean
  mnemonic?: string
  address?: string
  addresses?: Record<string, string>
  sectorAddresses?: Record<string, string>
  sectorBalances?: Record<string, number>
  keystore?: KeystoreFile  // Translated comment
  keystoreFilename?: string
  message: string
  error?: string
}

export interface WalletImportResult {
  success: boolean
  address?: string
  addresses?: Record<string, string>
  sectorAddresses?: Record<string, string>
  message: string
  error?: string
}

export interface WalletInfo {
  connected: boolean
  address: string
  addresses: Record<string, string>
  sectorAddresses?: Record<string, string>
  balance?: number
  mainBalance?: number
  sectorTotal?: number  // Translated comment
  sectorBalances?: Record<string, number>
  availableSectorBalances?: Record<string, number>  // Translated comment
  message?: string
}

export const walletApi = {
  create: async (password: string = ''): Promise<WalletCreateResult> => {
    try {
      return await rpcCall<WalletCreateResult>('wallet_create', { password })
    } catch (e) {
      const errMsg = String(e)
      return {
        success: false,
        message: errMsg.includes('fetch') || errMsg.includes('network') 
          ? 'Cannot connect to backend service. Please make sure the node is running.' 
          : `Wallet creation failed: ${errMsg}`,
        error: errMsg
      }
    }
  },
  import: async (mnemonic: string, password: string = ''): Promise<WalletImportResult> => {
    try {
      return await rpcCall<WalletImportResult>('wallet_import', { mnemonic, password })
    } catch (e) {
      return {
        success: false,
        message: 'Wallet import failed',
        error: String(e)
      }
    }
  },
  // Translated comment
  importKeystore: async (keystore: KeystoreFile | string, password: string): Promise<WalletImportResult> => {
    try {
      return await rpcCall<WalletImportResult>('wallet_importKeystore', { keystore, password })
    } catch (e) {
      return {
        success: false,
        message: 'Keystore import failed',
        error: String(e)
      }
    }
  },
  // Translated comment
  exportKeystore: async (password: string): Promise<{ success: boolean; keystore?: KeystoreFile; filename?: string; message: string }> => {
    try {
      return await rpcCall('wallet_exportKeystore', { password })
    } catch (e) {
      return {
        success: false,
        message: 'Export failed: ' + String(e),
      }
    }
  },
  getInfo: async (): Promise<WalletInfo> => {
    try {
      return await rpcCall<WalletInfo>('wallet_getInfo', {})
    } catch {
      return {
        connected: false,
        address: '',
        addresses: {},
      }
    }
  },
  unlock: async (password: string): Promise<{ success: boolean; message: string }> => {
    try {
      return await rpcCall<{ success: boolean; message: string }>('wallet_unlock', { password })
    } catch {
      return { success: false, message: 'Unlock failed' }
    }
  },
}

// ========== Transfer APIs ==========

export interface TransferResult {
  success: boolean
  txid?: string
  from?: string
  to?: string
  amount?: number
  sector?: string
  memo?: string
  timestamp?: number
  status?: string
  error?: string
  message: string
}

export const transferApi = {
  send: async (
    toAddress: string, 
    amount: number, 
    sector: string = 'MAIN',
    memo: string = ''
  ): Promise<TransferResult> => {
    try {
      return await rpcCall<TransferResult>('wallet_transfer', {
        toAddress,
        amount,
        sector,
        memo
      })
    } catch (e) {
      return {
        success: false,
        message: 'Transfer failed',
        error: String(e)
      }
    }
  }
}

// ========== Mining APIs ==========

export interface MiningStatus {
  isMining: boolean
  minerAddress: string
  hashRate: number
  blocksMined: number
  totalRewards: number
  sectorRewards?: Record<string, number>
  sector: string
  difficulty: number
  gpuName?: string
  miningMode: 'mine_only' | 'task_only' | 'mine_and_task'
  acceptingTasks: boolean
  p2pEnabled?: boolean
  p2pPort?: number
  demoMainBalance?: number
  acceptedOrders?: Array<{
    orderId: string
    status: string
    gpuType: string
    gpuCount: number
    durationHours: number
    program?: string
    taskId?: string
  }>
  runningPrograms?: Array<{
    taskId: string
    orderId?: string
    status: string
    progress: number
    program?: string
    runtime?: string
  }>
}

export interface MiningStartResult {
  success: boolean
  message: string
  minerAddress?: string
  sector?: string
  gpuName?: string
  miningMode?: string
  acceptingTasks?: boolean
  p2pEnabled?: boolean
  p2pPort?: number
  p2pPublicKey?: string
}

export interface MiningReward {
  coin: string
  amount: number
  timestamp: string
  blockHeight: number
}

export interface MiningRewardsResult {
  rewards: MiningReward[]
  totalAmount: number
  count: number
  minerAddress: string
}

export interface MinerScore {
  minerId: string
  objectiveScore: number
  feedbackScore: number
  priorityScore: number
  grade: 'S' | 'A' | 'B' | 'C' | 'D'
  metrics: {
    avgLatencyMs: number
    completionRate: number
    uptimeRate: number
    totalTasks: number
    blocksMined: number
  }
  feedback: {
    rating: number
    count: number
    totalTips: number
  }
  weights: {
    objectiveWeight: number
    feedbackWeight: number
  }
}

export const miningApi = {
  getStatus: async (address?: string): Promise<MiningStatus> => {
    try {
      return await rpcCall<MiningStatus>('mining_getStatus', address ? { address } : {})
    } catch {
      return {
        isMining: false,
        minerAddress: '',
        hashRate: 0,
        blocksMined: 0,
        totalRewards: 0,
        sectorRewards: {},
        sector: 'CPU',
        difficulty: 4,
        miningMode: 'mine_only',
        acceptingTasks: false,
        p2pEnabled: false,
        p2pPort: 0,
        demoMainBalance: 0,
        acceptedOrders: [],
        runningPrograms: [],
      }
    }
  },
  start: async (address?: string, mode?: string, p2pIp?: string, p2pPort?: number): Promise<MiningStartResult> => {
    try {
      return await rpcCall<MiningStartResult>('mining_start', { address, mode, p2pIp, p2pPort })
    } catch (e) {
      return { success: false, message: String(e) }
    }
  },
  stop: async (): Promise<{ success: boolean; message: string }> => {
    try {
      return await rpcCall<{ success: boolean; message: string }>('mining_stop', {})
    } catch (e) {
      return { success: false, message: String(e) }
    }
  },
  setMode: async (mode: string): Promise<{ success: boolean; mode: string; modeName: string; message: string }> => {
    try {
      return await rpcCall('mining_setMode', { mode })
    } catch (e) {
      return { success: false, mode: '', modeName: '', message: String(e) }
    }
  },
  getScore: async (minerId?: string): Promise<MinerScore> => {
    try {
      return await rpcCall<MinerScore>('mining_getScore', { miner_id: minerId })
    } catch {
      return {
        minerId: '',
        objectiveScore: 0.5,
        feedbackScore: 0.5,
        priorityScore: 0.5,
        grade: 'B',
        metrics: { avgLatencyMs: 0, completionRate: 0, uptimeRate: 0, totalTasks: 0, blocksMined: 0 },
        feedback: { rating: 0, count: 0, totalTips: 0 },
        weights: { objectiveWeight: 0.7, feedbackWeight: 0.3 },
      }
    }
  },
  getRewards: async (period?: string): Promise<MiningRewardsResult> => {
    try {
      return await rpcCall<MiningRewardsResult>('mining_getRewards', { period })
    } catch {
      return {
        rewards: [],
        totalAmount: 0,
        count: 0,
        minerAddress: '',
      }
    }
  },
}

// ========== Visual demo APIs ==========

export interface DemoOrderResult {
  orderId: string
  status: string
  buyerAddress?: string
  buyerBalanceAfter?: number
  totalPrice?: number
  freeOrder?: boolean
}

export interface DemoSubmitOrderParams {
  buyerAddress: string
  gpuType?: string
  gpuCount?: number
  durationHours?: number
  pricePerHour?: number
  freeOrder?: boolean
  program?: string
  image?: string
  inputDataRef?: string
  inputFilename?: string
}

export const demoApi = {
  createWallet: async (password: string) => walletApi.create(password),
  startMinerTaskMode: async (address: string) =>
    rpcCall<MiningStartResult>('mining_start', { address, mode: 'task_only' }),
  acceptOrder: async (orderId: string, minerAddress: string) =>
    rpcCall<{ 
      status: string
      taskId: string
      minerBalanceAfter?: number
      totalPrice?: number
      minerPayout?: number
      platformFee?: number
      treasuryFee?: number
    }>('compute_acceptOrder', {
      order_id: orderId,
      miner_address: minerAddress,
    }),
  getOrder: async (orderId: string) =>
    rpcCall<Record<string, unknown>>('compute_getOrder', { order_id: orderId }),
  getChainInfo: async () => rpcCall<Record<string, unknown>>('chain_getInfo', {}),
  submitOrderManual: async (params: DemoSubmitOrderParams) =>
    rpcCall<DemoOrderResult>('compute_submitOrder', {
      gpu_type: params.gpuType || 'RTX4090',
      gpu_count: params.gpuCount ?? 1,
      duration_hours: params.durationHours ?? 1,
      price_per_hour: params.freeOrder ? 0 : (params.pricePerHour ?? 1),
      free_order: params.freeOrder ?? false,
      buyer_address: params.buyerAddress,
      program: params.program || "print('manual demo task')",
      image: params.image,
      inputDataRef: params.inputDataRef,
      inputFilename: params.inputFilename,
    }),
  completeOrderManual: async (orderId: string, taskId: string, resultData: string) =>
    rpcCall<{ status: string; result: string }>('compute_completeOrder', {
      order_id: orderId,
      task_id: taskId,
      result_data: resultData,
    }),
}

// ========== Sector-coin exchange APIs ==========

export interface ExchangeRate {
  rate: number
  example: string
}

export interface ExchangeRatesResult {
  success: boolean
  rates: Record<string, ExchangeRate>
  message?: string
  error?: string
}

export interface ExchangeResult {
  success: boolean
  exchangeId?: string
  fromSector?: string
  fromAmount?: number
  toAmount?: number
  rate?: number
  status?: string
  witnesses?: string[]
  message: string
  error?: string
}

export interface ExchangeRecord {
  exchangeId: string
  fromSector: string
  fromAmount: number
  toAmount: number
  rate: number
  status: string
  createdAt: string
  witnesses: string[]
}

export interface ExchangeHistoryResult {
  success: boolean
  exchanges: ExchangeRecord[]
  total: number
  error?: string
}

export const exchangeApi = {
  // Translated comment
  getRates: async (): Promise<ExchangeRatesResult> => {
    try {
      return await rpcCall<ExchangeRatesResult>('sector_getExchangeRates', {})
    } catch (e) {
      return {
        success: false,
        rates: {},
        error: String(e)
      }
    }
  },
  
  // Translated comment
  requestExchange: async (sector: string, amount: number): Promise<ExchangeResult> => {
    try {
      return await rpcCall<ExchangeResult>('sector_requestExchange', { sector, amount })
    } catch (e) {
      return {
        success: false,
        message: 'Exchange request failed',
        error: String(e)
      }
    }
  },
  
  // Translated comment
  getHistory: async (limit: number = 20): Promise<ExchangeHistoryResult> => {
    try {
      return await rpcCall<ExchangeHistoryResult>('sector_getExchangeHistory', { limit })
    } catch (e) {
      return {
        success: false,
        exchanges: [],
        total: 0,
        error: String(e)
      }
    }
  },
  
  // Translated comment
  cancel: async (exchangeId: string): Promise<{ success: boolean; message: string }> => {
    try {
      return await rpcCall<{ success: boolean; message: string }>('sector_cancelExchange', { exchangeId })
    } catch (e) {
      return {
        success: false,
        message: String(e)
      }
    }
  }
}

// ========== Account APIs ==========

export interface Account {
  address: string
  balance: number
  mainBalance: number  // Translated comment
  sectorTotal: number  // Translated comment
  sectorAddresses?: Record<string, string>
  sectorBalances: Record<string, number>
  privacyLevel: 'transparent' | 'pseudonymous' | 'private'
  privacyRisk: 'low' | 'medium' | 'high'
  subAddresses: SubAddress[]
}

export interface SubAddress {
  address: string
  label: string
  balance: number
  usageCount: number
}

export interface Transaction {
  txId: string
  from: string
  to: string
  amount: number
  coin: string
  status: 'pending' | 'confirmed' | 'failed'
  timestamp: string
  blockHeight?: number
}

export const accountApi = {
  getAccount: async (address?: string): Promise<Account | null> => {
    try {
      const result = await rpcCall<{ 
        balance: number
        mainBalance: number
        sectorTotal: number
        sectorBalances: Record<string, number>
      }>('account_getBalance', { address })
      return {
        address: address || '',
        balance: result.balance,
        mainBalance: result.mainBalance || result.balance,
        sectorTotal: result.sectorTotal || 0,
        sectorBalances: result.sectorBalances || {},
        privacyLevel: 'pseudonymous',
        privacyRisk: 'low',
        subAddresses: [],
      }
    } catch {
      return null
    }
  },
  getTransactions: async (address?: string, limit = 20): Promise<{ transactions: Transaction[], total: number }> => {
    try {
      const result = await rpcCall<{ transactions: Transaction[], total: number }>(
        'account_getTransactions', { address, limit }
      )
      return result
    } catch {
      return { transactions: [], total: 0 }
    }
  },
  getSubAddresses: async (address?: string): Promise<SubAddress[]> => {
    try {
      return await rpcCall<SubAddress[]>('account_getSubAddresses', { address })
    } catch {
      return []
    }
  },
  createSubAddress: async (label: string): Promise<SubAddress | null> => {
    try {
      return await rpcCall<SubAddress>('account_createSubAddress', { label })
    } catch {
      return null
    }
  },
  exportWallet: async (password: string = ''): Promise<{ success: boolean; keystore?: KeystoreFile; filename?: string; message: string } | null> => {
    try {
      return await rpcCall<{ success: boolean; keystore?: KeystoreFile; filename?: string; message: string }>('wallet_exportKeystore', { password })
    } catch {
      return null
    }
  },
}

// ========== Dashboard APIs ==========

export interface DashboardStats {
  balance: number
  mainBalance: number  // Translated comment
  sectorTotal: number  // Translated comment
  balanceChange: number
  sectorBalances?: Record<string, number>
  activeTasks: number
  completedToday: number
  onlineMiners: number
  totalGpuPower: number
  networkUtilization: number
  blockHeight: number
  totalBlocksMined?: number
  minerAddress?: string
}

export interface RecentTask {
  id: string
  title: string
  status: 'pending' | 'running' | 'completed'
  progress: number
  gpu: string
}

export interface RecentProposal {
  id: string
  title: string
  status: 'voting' | 'passed' | 'rejected'
  votesFor: number
  votesAgainst: number
}

export const dashboardApi = {
  getStats: async (address?: string): Promise<DashboardStats> => {
    try {
      return await rpcCall<DashboardStats>('dashboard_getStats', address ? { address } : {})
    } catch {
      return {
        balance: 0,
        mainBalance: 0,
        sectorTotal: 0,
        balanceChange: 0,
        activeTasks: 0,
        completedToday: 0,
        onlineMiners: 0,
        totalGpuPower: 0,
        networkUtilization: 0,
        blockHeight: 0,
      }
    }
  },
  getRecentTasks: async (limit = 5): Promise<RecentTask[]> => {
    try {
      return await rpcCall<RecentTask[]>('dashboard_getRecentTasks', { limit })
    } catch {
      return []
    }
  },
  getRecentProposals: async (limit = 5): Promise<RecentProposal[]> => {
    try {
      return await rpcCall<RecentProposal[]>('dashboard_getRecentProposals', { limit })
    } catch {
      return []
    }
  },
  getBlockChart: async (): Promise<{ data: { name: string; value: number; color: string }[]; total: number }> => {
    try {
      return await rpcCall<{ data: { name: string; value: number; color: string }[]; total: number }>(
        'dashboard_getBlockChart', {}
      )
    } catch {
      return { data: [], total: 0 }
    }
  },
  getRewardTrend: async (): Promise<{ data: { time: string; rewards: number }[] }> => {
    try {
      return await rpcCall<{ data: { time: string; rewards: number }[] }>('dashboard_getRewardTrend', {})
    } catch {
      return { data: [] }
    }
  },
}

// ========== Task APIs ==========

export interface Task {
  taskId: string
  title: string
  description: string
  taskType: 'ai_training' | 'ai_inference' | 'rendering' | 'scientific' | 'other'
  status: 'pending' | 'assigned' | 'running' | 'completed' | 'disputed' | 'cancelled' | 'failed'
  priority: 'normal' | 'urgent'
  
  // Translated comment
  price: number
  coin: string
  
  // Translated comment
  gpuType: string
  gpuCount: number
  estimatedHours: number
  
  // SLA
  slaId: string
  slaMetrics?: {
    latency_ms: number
    throughput: number
    error_rate: number
    accuracy?: number
  }
  
  // Translated comment
  protocolVerdict?: 'executed' | 'consistent' | 'cheated' | 'timeout' | 'invalid'
  serviceVerdict?: 'met' | 'partial' | 'violated' | 'pending'
  applicationVerdict?: 'accepted' | 'disputed' | 'rejected' | 'auto_accepted'
  
  // Translated comment
  createdAt: string
  startedAt?: string
  completedAt?: string
  
  // Translated comment
  buyerId: string
  minerId?: string
  
  // Translated comment
  progress: number
  
  // Translated comment
  runningTime?: string
  gpuUtilization?: number
}

// Translated comment
export interface TaskFileNode {
  name: string
  type: 'file' | 'folder'
  children?: TaskFileNode[]
  content?: string
}

// Translated comment
export interface TaskLogEntry {
  timestamp: string
  type: 'stdout' | 'stderr' | 'system'
  message: string
}

// Translated comment
export interface TaskOutputFile {
  name: string
  size: string
  hash: string
  downloadUrl?: string
  content?: string
}

// Translated comment
export interface TaskRuntimeStatus {
  runningTime: string
  gpuUtilization: number
  memoryUsage?: number
  progress: number
}

export interface TaskCreateInput {
  title: string
  description: string
  taskType: Task['taskType']
  priority: Task['priority']
  gpuType: string
  gpuCount: number
  estimatedHours: number
  maxPrice: number
  slaId: string
  requirements?: string
}

export const taskApi = {
  getTasks: async (filters?: { status?: string, type?: string }): Promise<{ tasks: Task[], total: number }> => {
    try {
      return await rpcCall<{ tasks: Task[], total: number }>('task_getList', {
        status: filters?.status,
        task_type: filters?.type,
      })
    } catch {
      return { tasks: [], total: 0 }
    }
  },
  getTask: async (taskId: string): Promise<Task | null> => {
    try {
      return await rpcCall<Task>('task_getInfo', { task_id: taskId })
    } catch {
      return null
    }
  },
  createTask: async (input: TaskCreateInput): Promise<Task | null> => {
    try {
      return await rpcCall<Task>('task_create', {
        title: input.title,
        description: input.description,
        task_type: input.taskType,
        priority: input.priority,
        gpu_type: input.gpuType,
        gpu_count: input.gpuCount,
        estimated_hours: input.estimatedHours,
        max_price: input.maxPrice,
        requirements: input.requirements || '',
      })
    } catch {
      return null
    }
  },
  cancelTask: async (taskId: string): Promise<{ status: string } | null> => {
    try {
      return await rpcCall<{ status: string }>('task_cancel', { task_id: taskId })
    } catch {
      return null
    }
  },
  raiseDispute: async (taskId: string, reason: string): Promise<{ disputeId: string } | null> => {
    try {
      return await rpcCall<{ disputeId: string }>('task_raiseDispute', { task_id: taskId, reason })
    } catch {
      return null
    }
  },
  acceptResult: async (taskId: string, rating: number, comment?: string): Promise<{ success: boolean; message?: string }> => {
    try {
      await rpcCall<void>('task_acceptResult', { task_id: taskId, rating, comment })
      return { success: true }
    } catch (e) {
      return { success: false, message: String(e) }
    }
  },
    
  // Translated comment
  getTaskFiles: async (taskId: string): Promise<TaskFileNode[]> => {
    try {
      return await rpcCall<TaskFileNode[]>('task_getFiles', { task_id: taskId })
    } catch {
      return []
    }
  },
  
  // Translated comment
  getTaskLogs: async (taskId: string, since?: string): Promise<TaskLogEntry[]> => {
    try {
      return await rpcCall<TaskLogEntry[]>('task_getLogs', { task_id: taskId, since })
    } catch {
      return []
    }
  },
  
  // Translated comment
  getTaskOutputs: async (taskId: string): Promise<TaskOutputFile[]> => {
    return await rpcCall<TaskOutputFile[]>('task_getOutputs', { task_id: taskId })
  },
  
  // Translated comment
  getTaskRuntimeStatus: async (taskId: string): Promise<TaskRuntimeStatus | null> => {
    try {
      return await rpcCall<TaskRuntimeStatus>('task_getRuntimeStatus', { task_id: taskId })
    } catch {
      return null
    }
  },
}

// ========== Encrypted task APIs ==========

export interface EncryptedTaskCreateInput {
  title: string
  description: string
  codeData: string  // Translated comment
  inputData?: string  // Translated comment
  inputDataRef?: string  // Translated comment
  taskType: string
  estimatedHours: number
  budgetPerHour: number
  receivers?: string[]  // Translated comment
  userPublicKey?: string
  requirements?: string
  maxMemoryGb?: number  // Translated comment
  maxTimeoutHours?: number  // Translated comment
}

export interface EncryptedTaskResult {
  taskId: string
  title: string
  status: string
  chainLength: number
  estimatedBudget: number
  userPublicKey: string
  receivers: string[]
  createdAt: number
}

export interface EncryptedTaskStatus {
  taskId: string
  status: string
  progress: number
  currentNode?: string
  startedAt?: number
  completedAt?: number
}

export interface KeyPairResult {
  keyId: string
  publicKey: string
  privateKey: string
}

export const encryptedTaskApi = {
  // Translated comment
  generateKeypair: async (): Promise<KeyPairResult | null> => {
    try {
      return await rpcCall<KeyPairResult>('encryptedTask_generateKeypair', {})
    } catch {
      return null
    }
  },
  
  // Translated comment
  create: async (input: EncryptedTaskCreateInput): Promise<EncryptedTaskResult> => {
    return await rpcCall<EncryptedTaskResult>('encryptedTask_create', {
      title: input.title,
      description: input.description,
      codeData: input.codeData,
      inputData: input.inputData || '',
      inputDataRef: input.inputDataRef || '',
      taskType: input.taskType,
      estimatedHours: input.estimatedHours,
      budgetPerHour: input.budgetPerHour,
      receivers: input.receivers || [],
      userPublicKey: input.userPublicKey || '',
      requirements: input.requirements || '',
      maxMemoryGb: input.maxMemoryGb || 8,
      maxTimeoutHours: input.maxTimeoutHours || 0,
    })
  },
  
  // Translated comment
  submit: async (taskId: string, userPrivateKey?: string): Promise<{ submitted: boolean; status: string } | null> => {
    try {
      return await rpcCall<{ submitted: boolean; status: string }>('encryptedTask_submit', { 
        taskId,
        userPrivateKey: userPrivateKey || ''
      })
    } catch {
      return null
    }
  },
  
  // Translated comment
  getStatus: async (taskId: string): Promise<EncryptedTaskStatus | null> => {
    try {
      return await rpcCall<EncryptedTaskStatus>('encryptedTask_getStatus', { taskId })
    } catch {
      return null
    }
  },
  
  // Translated comment
  getResult: async (taskId: string, userPrivateKey?: string): Promise<{
    taskId: string
    status: string
    result?: string
    resultHash?: string
  } | null> => {
    try {
      return await rpcCall('encryptedTask_getResult', { 
        taskId, 
        userPrivateKey: userPrivateKey || '' 
      })
    } catch {
      return null
    }
  },
  
  // Translated comment
  getBillingReport: async (taskId: string): Promise<{
    taskId: string
    totalCost: number
    breakdown: { nodeId: string; cost: number; duration: number }[]
  } | null> => {
    try {
      return await rpcCall('encryptedTask_getBillingReport', { taskId })
    } catch {
      return null
    }
  },
  
  // Translated comment
  encodeToBase64: (data: string): string => {
    return btoa(unescape(encodeURIComponent(data)))
  },
  
  // Translated comment
  fileToBase64: (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => {
        const result = reader.result as string
        // Translated comment
        const base64 = result.split(',')[1] || result
        resolve(base64)
      }
      reader.onerror = reject
      reader.readAsDataURL(file)
    })
  }
}

// ========== Chunked file upload/download APIs ==========

const CHUNK_SIZE = 4 * 1024 * 1024 // 4MB chunks

export interface FileUploadProgress {
  phase: 'hashing' | 'uploading' | 'finalizing' | 'done'
  percent: number
  uploadedBytes: number
  totalBytes: number
}

export interface DownloadableTaskOutputFile {
  name: string
  fileSize: number
  sha256: string
}

export const fileTransferApi = {
  /**
   * Translated comment
   */
  chunkedUpload: async (
    file: File,
    onProgress?: (p: FileUploadProgress) => void,
  ): Promise<string | null> => {
    try {
      const totalSize = file.size
      const totalChunks = Math.ceil(totalSize / CHUNK_SIZE)

      // Translated comment
      onProgress?.({ phase: 'hashing', percent: 0, uploadedBytes: 0, totalBytes: totalSize })
      const sha256 = await computeSHA256(file)
      onProgress?.({ phase: 'hashing', percent: 100, uploadedBytes: 0, totalBytes: totalSize })

      // Translated comment
      const initResult = await rpcCall<{ uploadId: string; chunkSize: number }>('file_initUpload', {
        filename: file.name,
        totalSize,
        sha256Hash: sha256,
      })
      if (!initResult) throw new Error('Failed to initialize upload')
      const uploadId = initResult.uploadId

      // Translated comment
      onProgress?.({ phase: 'uploading', percent: 0, uploadedBytes: 0, totalBytes: totalSize })
      for (let i = 0; i < totalChunks; i++) {
        const start = i * CHUNK_SIZE
        const end = Math.min(start + CHUNK_SIZE, totalSize)
        const chunk = file.slice(start, end)
        const chunkBase64 = await blobToBase64(chunk)

        const chunkResult = await rpcCall<{ received: number }>('file_uploadChunk', {
          uploadId,
          chunkIndex: i,
          chunkData: chunkBase64,
        })
        if (!chunkResult) throw new Error(`Chunk upload failed: ${i}`)

        onProgress?.({
          phase: 'uploading',
          percent: Math.round(((i + 1) / totalChunks) * 100),
          uploadedBytes: end,
          totalBytes: totalSize,
        })
      }

      // Translated comment
      onProgress?.({ phase: 'finalizing', percent: 99, uploadedBytes: totalSize, totalBytes: totalSize })
      const finalResult = await rpcCall<{ fileRef?: string; fileId?: string; verified?: boolean }>('file_finalizeUpload', {
        uploadId,
      })
      if (!finalResult) throw new Error('File finalization failed')

      const resolvedFileRef = finalResult.fileRef || finalResult.fileId
      if (!resolvedFileRef) throw new Error('Missing file reference in finalize response')

      // verified 字段在部分后端版本中不存在；缺省时以 finalize 成功视为通过。
      if (typeof finalResult.verified === 'boolean' && !finalResult.verified) {
        throw new Error('File verification failed')
      }

      onProgress?.({ phase: 'done', percent: 100, uploadedBytes: totalSize, totalBytes: totalSize })
      return resolvedFileRef
    } catch (e) {
      console.error('Chunked upload failed:', e)
      return null
    }
  },

  /**
   * Translated comment
   */
  cancelUpload: async (uploadId: string): Promise<boolean> => {
    try {
      await rpcCall('file_cancelUpload', { uploadId })
      return true
    } catch {
      return false
    }
  },

  /**
   * Translated comment
   */
  getUploadProgress: async (uploadId: string) => {
    try {
      return await rpcCall<{
        uploadId: string
        receivedChunks: number
        chunkCount: number
        progress: number
        completed: boolean
        fileRef: string | null
      }>('file_getUploadProgress', { uploadId })
    } catch {
      return null
    }
  },

  /**
   * Translated comment
   */
  getTaskOutputs: async (taskId: string): Promise<DownloadableTaskOutputFile[]> => {
    try {
      const result = await rpcCall<{ files: DownloadableTaskOutputFile[] }>('file_getTaskOutputs', { taskId })
      return result?.files || []
    } catch {
      return []
    }
  },

  /**
   * Translated comment
   */
  downloadTaskOutput: async (
    taskId: string,
    filename: string,
    onProgress?: (percent: number) => void,
  ): Promise<Blob | null> => {
    try {
      // Translated comment
      const info = await rpcCall<{ size: number; totalChunks: number }>('file_downloadTaskOutput', {
        taskId,
        filename,
        chunkIndex: 0,
      })
      if (!info) return null

      const chunks: ArrayBuffer[] = []
      const totalChunks = info.totalChunks || 1

      for (let i = 0; i < totalChunks; i++) {
        const chunkResult = await rpcCall<{ chunkData: string; chunkIndex: number; totalChunks: number }>(
          'file_downloadTaskOutput',
          { taskId, filename, chunkIndex: i },
        )
        if (!chunkResult) throw new Error(`Chunk download failed: ${i}`)
        chunks.push(base64ToArrayBuffer(chunkResult.chunkData))
        onProgress?.(Math.round(((i + 1) / totalChunks) * 100))
      }

      return new Blob(chunks)
    } catch (e) {
      console.error('Failed to download output file:', e)
      return null
    }
  },
}

// Translated comment

async function computeSHA256(file: File): Promise<string> {
  const buffer = await file.arrayBuffer()
  const hash = await crypto.subtle.digest('SHA-256', buffer)
  return Array.from(new Uint8Array(hash))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = reader.result as string
      resolve(result.split(',')[1] || result)
    }
    reader.onerror = reject
    reader.readAsDataURL(blob)
  })
}

function base64ToArrayBuffer(b64: string): ArrayBuffer {
  const bin = atob(b64)
  const arr = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i)
  return arr.buffer
}

// ========== Compute market APIs ==========

export interface MarketOrder {
  orderId: string
  minerId: string
  minerName: string
  gpuType: string
  gpuCount: number
  pricePerHour: number
  coin: string
  available: boolean
  rating: number
  completedTasks: number
  slaGuarantee: string
}

export interface Quote {
  quoteId: string
  orderId: string
  price: number
  estimatedTime: number
  minerRating: number
}

export const marketApi = {
  getOrders: async (gpuType?: string): Promise<{ orders: MarketOrder[], total: number }> => {
    try {
      const market = await rpcCall<{ orders?: MarketOrder[] }>('compute_getMarket', { gpu_type: gpuType })
      const orders = market.orders || []
      return { orders, total: orders.length }
    } catch {
      return { orders: [], total: 0 }
    }
  },
  getQuotes: async (taskId: string): Promise<Quote[]> => {
    try {
      return await rpcCall<Quote[]>('market_getQuotes', { task_id: taskId })
    } catch {
      return []
    }
  },
  acceptQuote: async (quoteId: string): Promise<void> => {
    try {
      await rpcCall<void>('market_acceptQuote', { quote_id: quoteId })
    } catch {
      // ignore
    }
  },
  acceptOrder: async (orderId: string, taskId?: string): Promise<{ status: string } | null> => {
    try {
      return await rpcCall<{ status: string }>('compute_acceptOrder', { order_id: orderId, task_id: taskId })
    } catch {
      return null
    }
  },
  cancelOrder: async (orderId: string): Promise<{ status: string } | null> => {
    try {
      return await rpcCall<{ status: string }>('compute_cancelOrder', { order_id: orderId })
    } catch {
      return null
    }
  },
  getOrder: async (orderId: string) => {
    try {
      return await rpcCall<MarketOrder | null>('compute_getOrder', { order_id: orderId })
    } catch {
      return null
    }
  },
}

// ========== Governance APIs ==========

export interface Proposal {
  proposalId: string
  title: string
  description: string
  category: 'parameter' | 'funding' | 'protocol' | 'emergency'
  status: 'draft' | 'voting' | 'passed' | 'rejected' | 'executed'
  
  // Translated comment
  votesFor: number
  votesAgainst: number
  votesAbstain: number
  quorum: number
  threshold: number
  
  // Translated comment
  createdAt: string
  votingStartsAt: string
  votingEndsAt: string
  
  // Translated comment
  proposerId: string
  
  // Translated comment
  fundingAmount?: number
  fundingRecipient?: string
}

export interface ProposalCreateInput {
  title: string
  description: string
  category: Proposal['category']
  fundingAmount?: number
  fundingRecipient?: string
}

export const governanceApi = {
  getProposals: async (status?: string): Promise<{ proposals: Proposal[], total: number }> => {
    try {
      const proposals = await rpcCall<Proposal[]>('governance_getProposals', { status })
      return { proposals, total: proposals.length }
    } catch {
      return { proposals: [], total: 0 }
    }
  },
  getProposal: async (proposalId: string): Promise<Proposal | null> => {
    try {
      return await rpcCall<Proposal>('governance_getProposal', { proposal_id: proposalId })
    } catch {
      return null
    }
  },
  createProposal: async (input: ProposalCreateInput): Promise<{ success: boolean; proposal?: Proposal; message: string }> => {
    try {
      const result = await rpcCall<{ success: boolean; proposal?: Proposal; message: string }>('governance_createProposal', { ...input })
      return result
    } catch (e) {
      return { success: false, message: String(e) }
    }
  },
  vote: async (proposalId: string, vote: 'for' | 'against' | 'abstain') =>
    rpcCall<{ status: string }>('governance_vote', { proposal_id: proposalId, vote }),
}

// ========== Miner APIs ==========

export interface Miner {
  minerId: string
  name: string
  address: string
  status: 'online' | 'offline' | 'busy'
  
  // Translated comment
  gpuType: string
  gpuCount: number
  
  // Translated comment
  behaviorScore: number
  acceptanceRate: number
  priceDiversity: number
  congestionHelp: number
  
  // Translated comment
  totalTasks: number
  completedTasks: number
  totalEarnings: number
  
  // Translated comment
  reputationLevel: 'bronze' | 'silver' | 'gold' | 'platinum'
  schedulingMultiplier: number
}

export const minerApi = {
  getMiners: async (sortBy?: string): Promise<{ miners: Miner[], total: number }> => {
    try {
      return await rpcCall<{ miners: Miner[], total: number }>('miner_getList', { sort_by: sortBy })
    } catch {
      return { miners: [], total: 0 }
    }
  },
  getMiner: async (minerId: string): Promise<Miner | null> => {
    try {
      return await rpcCall<Miner>('miner_getInfo', { miner_id: minerId })
    } catch {
      return null
    }
  },
  getMinerBehaviorReport: async (minerId: string): Promise<{ score: unknown, suggestions: string[] } | null> => {
    try {
      return await rpcCall<{ score: unknown, suggestions: string[] }>('miner_getBehaviorReport', { miner_id: minerId })
    } catch {
      return null
    }
  },
  register: async (params: {
    gpuType: string
    gpuCount: number
    pricePerHour: number
    description?: string
    sectors?: string[]
  }): Promise<{
    success: boolean
    minerId?: string
    address?: string
    profile?: Miner
    error?: string
    message: string
  }> => {
    try {
      return await rpcCall<{
        success: boolean
        minerId?: string
        address?: string
        profile?: Miner
        error?: string
        message: string
      }>('miner_register', params)
    } catch (e) {
      return {
        success: false,
        message: 'Registration failed',
        error: String(e)
      }
    }
  },
  updateProfile: async (params: {
    gpuType?: string
    gpuCount?: number
    pricePerHour?: number
    description?: string
    status?: 'online' | 'offline' | 'busy'
  }): Promise<{
    success: boolean
    profile?: Miner
    error?: string
    message: string
  }> => {
    try {
      return await rpcCall<{
        success: boolean
        profile?: Miner
        error?: string
        message: string
      }>('miner_updateProfile', params)
    } catch (e) {
      return {
        success: false,
        message: 'Update failed',
        error: String(e)
      }
    }
  },
}

// ========== Statistics APIs ==========

export interface BlockStats {
  taskBlocks: number
  idleBlocks: number
  validationBlocks: number
  totalRewards: number
  rewardsByType: Record<string, number>
}

export interface TaskStats {
  totalTasks: number
  completedTasks: number
  disputedTasks: number
  averagePrice: number
  tasksByType: Record<string, number>
}

export interface NetworkStats {
  totalMiners: number
  onlineMiners: number
  totalGpuPower: number
  blockHeight: number
  difficulty: number
}

export const statsApi = {
  getBlockStats: async (period: '24h' | '7d' | '30d'): Promise<BlockStats> => {
    try {
      return await rpcCall<BlockStats>('stats_getBlocks', { period })
    } catch {
      return {
        taskBlocks: 0,
        idleBlocks: 0,
        validationBlocks: 0,
        totalRewards: 0,
        rewardsByType: {},
      }
    }
  },
  getTaskStats: async (period: '24h' | '7d' | '30d'): Promise<TaskStats> => {
    try {
      return await rpcCall<TaskStats>('stats_getTasks', { period })
    } catch {
      return {
        totalTasks: 0,
        completedTasks: 0,
        disputedTasks: 0,
        averagePrice: 0,
        tasksByType: {},
      }
    }
  },
  getNetworkStats: async (): Promise<NetworkStats> => {
    try {
      return await rpcCall<NetworkStats>('stats_getNetwork', {})
    } catch {
      return {
        totalMiners: 0,
        onlineMiners: 0,
        totalGpuPower: 0,
        blockHeight: 0,
        difficulty: 0,
      }
    }
  },
  getChainInfo: async () => {
    try {
      return await rpcCall<{ height: number; syncing: boolean }>('chain_getInfo', {})
    } catch {
      return { height: 0, syncing: false }
    }
  },
}

// ========== Privacy APIs ==========

export interface AddressUsageInfo {
  address: string
  usageCount: number
  riskLevel: string
  linkedAddresses?: number
  lastUsed: number
}

export interface PrivacyStatus {
  currentLevel: 'transparent' | 'pseudonymous' | 'private'
  riskLevel: 'low' | 'medium' | 'high'
  addressUsageCount: number
  subAddressCount?: number
  suggestions: string[]
  roadmapPhase: string
  nextPhaseFeatures: string[]
  recommendations?: { id: number; type: string; message: string }[]
  mainAddressInfo?: AddressUsageInfo
  subAddresses?: AddressUsageInfo[]
}

export const privacyApi = {
  getStatus: async (): Promise<PrivacyStatus> => {
    try {
      return await rpcCall<PrivacyStatus>('privacy_getStatus', {})
    } catch {
      return {
        currentLevel: 'pseudonymous',
        riskLevel: 'low',
        addressUsageCount: 0,
        suggestions: [],
        roadmapPhase: 'Phase 1',
        nextPhaseFeatures: [],
      }
    }
  },
  rotateAddress: async (): Promise<{ newAddress: string, status: string } | null> => {
    try {
      return await rpcCall<{ newAddress: string, status: string }>('privacy_rotateAddress', {})
    } catch {
      return null
    }
  },
}

// ========== Order APIs ==========

export interface OrderData {
  id: string
  type: 'buy' | 'sell'
  status: 'pending' | 'active' | 'completed' | 'cancelled' | 'failed' | 'executing'
  gpuType: string
  amount: number
  pricePerHour: number
  totalPrice: number
  duration: number
  createdAt: number
  completedAt?: number
  buyer: string
  seller: string
}

export const orderApi = {
  getList: async (status?: string, limit = 20): Promise<{ orders: OrderData[], total: number }> => {
    try {
      return await rpcCall<{ orders: OrderData[], total: number }>('order_getList', { status, limit })
    } catch {
      return { orders: [], total: 0 }
    }
  },
  getDetail: async (orderId: string): Promise<OrderData | null> => {
    try {
      return await rpcCall<OrderData>('order_getDetail', { orderId })
    } catch {
      return null
    }
  },
}

// ========== Staking APIs ==========

export interface StakingRecord {
  id: string
  amount: number
  sector: string
  startTime: number
  endTime: number
  status: 'active' | 'completed' | 'pending' | 'burned'
  rewards: number
  apy?: number
  // Translated comment
  taskId?: string
  rating?: number
  createdAt: number
}

export const stakingApi = {
  getRecords: async (address?: string): Promise<{ records: StakingRecord[], totalStaked: number, totalRewards: number }> => {
    try {
      return await rpcCall<{ records: StakingRecord[], totalStaked: number, totalRewards: number }>('staking_getRecords', { address })
    } catch {
      return { records: [], totalStaked: 0, totalRewards: 0 }
    }
  },
  stake: async (amount: number, sector?: string, duration?: number): Promise<{ success: boolean, stakeId?: string, message?: string }> => {
    try {
      return await rpcCall<{ success: boolean, stakeId?: string, message?: string }>('staking_stake', { amount, sector, duration })
    } catch {
      return { success: false, message: 'Staking failed' }
    }
  },
  unstake: async (stakeId: string): Promise<{ success: boolean, message?: string }> => {
    try {
      return await rpcCall<{ success: boolean, message?: string }>('staking_unstake', { stakeId })
    } catch {
      return { success: false, message: 'Unstake failed' }
    }
  },
}

// ========== Blockchain APIs ==========

export interface SBoxInfo {
  score: number
  nonlinearity: number
  diffUniformity: number
  avalanche: number
  selectedSector: string
  allSectors: string[]
  scoreThreshold: number
}

export interface BlockInfo {
  height: number
  hash: string
  prevHash: string
  timestamp: number
  miner: string
  txCount: number
  size: number
  difficulty: number
  nonce: number
  consensusType: string
  reward: number
  sbox?: SBoxInfo
}

export const blockchainApi = {
  getHeight: async (): Promise<{ height: number, timestamp: number }> => {
    try {
      return await rpcCall<{ height: number, timestamp: number }>('blockchain_getHeight', {})
    } catch {
      return { height: 0, timestamp: Date.now() }
    }
  },
  getBlock: async (height?: number, hash?: string): Promise<BlockInfo | null> => {
    try {
      return await rpcCall<BlockInfo>('blockchain_getBlock', { height, hash })
    } catch {
      return null
    }
  },
  getLatestBlocks: async (limit = 10): Promise<{ blocks: BlockInfo[], total: number }> => {
    try {
      return await rpcCall<{ blocks: BlockInfo[], total: number }>('blockchain_getLatestBlocks', { limit })
    } catch {
      return { blocks: [], total: 0 }
    }
  },
}

// ========== Dynamic pricing APIs ==========

export interface GpuPricing {
  gpuType: string
  basePrice: number
  currentPrice: number
  demandMultiplier: number
  supplyLevel: 'low' | 'medium' | 'high'
  priceChange24h: number
}

export interface PriceForecast {
  hour: number
  predictedPrice: number
  confidence: number
}

export const pricingApi = {
  // Translated comment
  getBaseRates: async (): Promise<Record<string, number>> => {
    try {
      return await rpcCall<Record<string, number>>('pricing_getBaseRates', {})
    } catch {
      return {}
    }
  },
  // Translated comment
  getRealTimePrice: async (gpuType: string): Promise<GpuPricing | null> => {
    try {
      return await rpcCall<GpuPricing>('pricing_getRealTimePrice', { gpuType })
    } catch {
      return null
    }
  },
  // Translated comment
  calculatePrice: async (gpuType: string, hours: number, gpuCount: number = 1): Promise<{
    basePrice: number
    finalPrice: number
    breakdown: { item: string; amount: number }[]
  }> => {
    try {
      return await rpcCall('pricing_calculatePrice', { gpuType, hours, gpuCount })
    } catch {
      return { basePrice: 0, finalPrice: 0, breakdown: [] }
    }
  },
  // Translated comment
  getMarketState: async (): Promise<{
    totalSupply: number
    totalDemand: number
    utilizationRate: number
    byGpuType: Record<string, { supply: number; demand: number; utilization: number }>
  }> => {
    try {
      return await rpcCall('pricing_getMarketState', {})
    } catch {
      return { totalSupply: 0, totalDemand: 0, utilizationRate: 0, byGpuType: {} }
    }
  },
  // Translated comment
  getPriceForecast: async (gpuType: string, hours: number = 24): Promise<PriceForecast[]> => {
    try {
      return await rpcCall<PriceForecast[]>('pricing_getPriceForecast', { gpuType, hours })
    } catch {
      return []
    }
  },
  // Translated comment
  getTimeSlotSchedule: async (): Promise<{
    slots: { startHour: number; endHour: number; multiplier: number; label: string }[]
  }> => {
    try {
      return await rpcCall('pricing_getTimeSlotSchedule', {})
    } catch {
      return { slots: [] }
    }
  },
}

// Translated comment

export interface OrderBookEntry {
  orderId: string
  type: 'ask' | 'bid'
  gpuType: string
  pricePerHour: number
  gpuCount: number
  duration: number
  address: string
  timestamp: number
}

export interface OrderBookMatch {
  matchId: string
  askOrderId: string
  bidOrderId: string
  price: number
  gpuCount: number
  matchedAt: number
}

export const orderbookApi = {
  // Translated comment
  submitAsk: async (params: {
    gpuType: string
    gpuCount: number
    pricePerHour: number
    minDuration?: number
    maxDuration?: number
  }): Promise<{ orderId: string; status: string } | null> => {
    try {
      return await rpcCall('orderbook_submitAsk', params)
    } catch {
      return null
    }
  },
  // Translated comment
  submitBid: async (params: {
    gpuType: string
    gpuCount: number
    maxPricePerHour: number
    duration: number
    taskId?: string
  }): Promise<{ orderId: string; status: string; matched?: boolean } | null> => {
    try {
      return await rpcCall('orderbook_submitBid', params)
    } catch {
      return null
    }
  },
  // Translated comment
  cancelOrder: async (orderId: string): Promise<{ success: boolean; message: string }> => {
    try {
      return await rpcCall('orderbook_cancelOrder', { orderId })
    } catch {
      return { success: false, message: 'Cancel failed' }
    }
  },
  // Translated comment
  getOrderBook: async (gpuType?: string): Promise<{
    asks: OrderBookEntry[]
    bids: OrderBookEntry[]
    spread: number
    lastPrice: number
  }> => {
    try {
      return await rpcCall('orderbook_getOrderBook', { gpuType })
    } catch {
      return { asks: [], bids: [], spread: 0, lastPrice: 0 }
    }
  },
  // Translated comment
  getMarketPrice: async (gpuType: string): Promise<{
    bid: number
    ask: number
    last: number
    volume24h: number
  }> => {
    try {
      return await rpcCall('orderbook_getMarketPrice', { gpuType })
    } catch {
      return { bid: 0, ask: 0, last: 0, volume24h: 0 }
    }
  },
  // Translated comment
  getMyOrders: async (): Promise<{ orders: OrderBookEntry[]; total: number }> => {
    try {
      return await rpcCall('orderbook_getMyOrders', {})
    } catch {
      return { orders: [], total: 0 }
    }
  },
  // Translated comment
  getMatches: async (limit: number = 20): Promise<{ matches: OrderBookMatch[]; total: number }> => {
    try {
      return await rpcCall('orderbook_getMatches', { limit })
    } catch {
      return { matches: [], total: 0 }
    }
  },
}

// ========== Task queue APIs ==========

export interface QueuePosition {
  taskId: string
  position: number
  estimatedWaitTime: number
  priority: string
}

export const queueApi = {
  // Translated comment
  enqueue: async (taskId: string, priority: string = 'normal'): Promise<{
    position: number
    estimatedWaitTime: number
  }> => {
    try {
      return await rpcCall('queue_enqueue', { taskId, priority })
    } catch {
      return { position: -1, estimatedWaitTime: 0 }
    }
  },
  // Translated comment
  getPosition: async (taskId: string): Promise<QueuePosition | null> => {
    try {
      return await rpcCall<QueuePosition>('queue_getPosition', { taskId })
    } catch {
      return null
    }
  },
  // Translated comment
  getEstimatedWaitTime: async (gpuType: string, priority: string = 'normal'): Promise<{
    waitTime: number
    queueLength: number
  }> => {
    try {
      return await rpcCall('queue_getEstimatedWaitTime', { gpuType, priority })
    } catch {
      return { waitTime: 0, queueLength: 0 }
    }
  },
  // Translated comment
  getStats: async (): Promise<{
    totalQueued: number
    byGpuType: Record<string, number>
    byPriority: Record<string, number>
    avgWaitTime: number
  }> => {
    try {
      return await rpcCall('queue_getStats', {})
    } catch {
      return { totalQueued: 0, byGpuType: {}, byPriority: {}, avgWaitTime: 0 }
    }
  },
}

// ========== Market monitoring APIs ==========

export const marketMonitorApi = {
  // Translated comment
  getDashboard: async (): Promise<{
    totalOrders: number
    activeMiners: number
    totalGpuPower: number
    utilizationRate: number
    avgPrice: number
    priceChange24h: number
  }> => {
    try {
      return await rpcCall('market_getDashboard', {})
    } catch {
      return { totalOrders: 0, activeMiners: 0, totalGpuPower: 0, utilizationRate: 0, avgPrice: 0, priceChange24h: 0 }
    }
  },
  // Translated comment
  getSupplyDemandCurve: async (): Promise<{
    supplyPoints: { price: number; quantity: number }[]
    demandPoints: { price: number; quantity: number }[]
    equilibriumPrice: number
  }> => {
    try {
      return await rpcCall('market_getSupplyDemandCurve', {})
    } catch {
      return { supplyPoints: [], demandPoints: [], equilibriumPrice: 0 }
    }
  },
  // Translated comment
  getQueueStatus: async (): Promise<{
    pending: number
    running: number
    completed: number
    avgProcessingTime: number
  }> => {
    try {
      return await rpcCall('market_getQueueStatus', {})
    } catch {
      return { pending: 0, running: 0, completed: 0, avgProcessingTime: 0 }
    }
  },
}

// ========== Settlement APIs ==========

export interface SettlementRecord {
  settlementId: string
  taskId: string
  buyerAddress: string
  minerAddress: string
  totalAmount: number
  breakdown: { item: string; amount: number }[]
  status: 'pending' | 'completed' | 'disputed'
  createdAt: number
  completedAt?: number
}

export const settlementApi = {
  // Translated comment
  getRecord: async (taskId: string): Promise<SettlementRecord | null> => {
    try {
      return await rpcCall<SettlementRecord>('settlement_getRecord', { taskId })
    } catch {
      return null
    }
  },
  // Translated comment
  getDetailedBill: async (taskId: string): Promise<{
    taskId: string
    items: { name: string; quantity: number; unitPrice: number; total: number }[]
    subtotal: number
    fees: number
    total: number
  }> => {
    try {
      return await rpcCall('settlement_getDetailedBill', { taskId })
    } catch {
      return { taskId, items: [], subtotal: 0, fees: 0, total: 0 }
    }
  },
  // Translated comment
  getMinerEarnings: async (period?: string): Promise<{
    total: number
    breakdown: { date: string; amount: number; taskCount: number }[]
    pendingSettlement: number
  }> => {
    try {
      return await rpcCall('settlement_getMinerEarnings', { period })
    } catch {
      return { total: 0, breakdown: [], pendingSettlement: 0 }
    }
  },
}

// ========== Billing APIs ==========

export const billingApi = {
  // Translated comment
  calculateCost: async (params: {
    gpuType: string
    gpuCount: number
    hours: number
    memoryGB?: number
    storageGB?: number
  }): Promise<{
    gpuCost: number
    memoryCost: number
    storageCost: number
    networkCost: number
    totalCost: number
    currency: string
  }> => {
    try {
      return await rpcCall('billing_calculateCost', params)
    } catch {
      return { gpuCost: 0, memoryCost: 0, storageCost: 0, networkCost: 0, totalCost: 0, currency: 'MAIN' }
    }
  },
  // Translated comment
  getRates: async (): Promise<{
    gpu: Record<string, number>
    memory: number
    storage: number
    network: number
  }> => {
    try {
      return await rpcCall('billing_getRates', {})
    } catch {
      return { gpu: {}, memory: 0, storage: 0, network: 0 }
    }
  },
  // Translated comment
  estimateTask: async (taskId: string): Promise<{
    estimatedCost: number
    breakdown: { resource: string; cost: number }[]
    confidence: number
  }> => {
    try {
      return await rpcCall('billing_estimateTask', { taskId })
    } catch {
      return { estimatedCost: 0, breakdown: [], confidence: 0 }
    }
  },
}

// ========== UTXO APIs ==========

export interface UTXO {
  txId: string
  outputIndex: number
  amount: number
  coinType: string
  sourceType: 'coinbase' | 'transfer'
  blockHeight: number
  timestamp: string
}

export interface UTXOTraceItem {
  txId: string
  txType: 'coinbase' | 'transfer'
  amount: number
  coinType: string
  from: string
  to: string
  blockHeight: number
  timestamp: string
}

export interface UTXOTraceResult {
  success: boolean
  trace: UTXOTraceItem[]
  depth: number
  originType: string
  originTxId: string
  error?: string
}

export const utxoApi = {
  // Translated comment
  getUTXOs: async (address?: string): Promise<UTXO[]> => {
    try {
      return await rpcCall<UTXO[]>('account_getUTXOs', { address })
    } catch {
      return []
    }
  },
  
  // Translated comment
  trace: async (txId: string, outputIndex: number = 0): Promise<UTXOTraceResult> => {
    try {
      return await rpcCall<UTXOTraceResult>('account_traceUTXO', { txid: txId, output_index: outputIndex })
    } catch (e) {
      return {
        success: false,
        trace: [],
        depth: 0,
        originType: '',
        originTxId: '',
        error: String(e)
      }
    }
  }
}

// ========== Explorer APIs ==========

export interface Block {
  height: number
  hash: string
  prevHash: string
  timestamp: number
  miner: string
  sector: string
  txCount: number
  transactions?: TransactionInfo[]
  reward: number
  difficulty: number
  nonce: number
  size: number
  consensusType?: string
  sbox?: SBoxInfo
}

export interface TransactionInfo {
  txId: string
  txType: 'coinbase' | 'transfer' | 'exchange'
  from: string
  to: string
  amount: number
  coinType: string
  fee: number
  blockHeight: number
  timestamp: string
  status: 'confirmed' | 'pending'
  inputs?: { txId: string; index: number; amount: number }[]
  outputs?: { address: string; amount: number; index: number }[]
}

export interface ChainInfo {
  height: number
  sector: string
  totalBlocks: number
  totalTransactions: number
  difficulty: number
  lastBlockTime: number
  consensusMode?: 'mixed' | 'sbox_only' | 'pouw_only'
  consensusSboxRatio?: number
  consensusSelectedDistribution?: {
    window: number
    counts: { POUW: number; SBOX_POUW: number; POW: number }
    sbox_ratio: number
    pouw_ratio: number
    pow_ratio: number
  }
  consensusMinedDistribution?: {
    window: number
    counts: { POUW: number; SBOX_POUW: number; POW: number }
    sbox_ratio: number
    pouw_ratio: number
    pow_ratio: number
  }
  sboxMiningEnabled?: boolean
  currentSbox?: { score: number; sector: string; nonlinearity: number }
  sboxLibrarySize?: number
}

export const explorerApi = {
  // Translated comment
  getChainInfo: async (sector?: string): Promise<ChainInfo> => {
    try {
      return await rpcCall<ChainInfo>('chain_getInfo', { sector })
    } catch {
      return { height: 0, sector: 'GENERAL', totalBlocks: 0, totalTransactions: 0, difficulty: 4, lastBlockTime: 0 }
    }
  },
  
  // Translated comment
  getHeight: async (sector?: string): Promise<number> => {
    try {
      const result = await rpcCall<{ height: number }>('chain_getHeight', { sector })
      return result.height
    } catch {
      return 0
    }
  },
  
  // Translated comment
  getLatestBlocks: async (sector?: string, limit: number = 20): Promise<Block[]> => {
    try {
      const result = await rpcCall<{ blocks: Block[] }>('block_getLatest', { sector, limit })
      return result.blocks || []
    } catch {
      return []
    }
  },
  
  // Translated comment
  getBlockByHeight: async (height: number, sector?: string): Promise<Block | null> => {
    try {
      return await rpcCall<Block>('block_getByHeight', { height, sector })
    } catch {
      return null
    }
  },
  
  // Translated comment
  getBlockByHash: async (hash: string): Promise<Block | null> => {
    try {
      return await rpcCall<Block>('block_getByHash', { hash })
    } catch {
      return null
    }
  },
  
  // Translated comment
  getTransaction: async (txId: string): Promise<TransactionInfo | null> => {
    try {
      return await rpcCall<TransactionInfo>('tx_get', { txid: txId })
    } catch {
      return null
    }
  },
  
  // Translated comment
  search: async (query: string): Promise<{
    type: 'address' | 'transaction' | 'block' | 'unknown'
    result: unknown
  }> => {
    try {
      // Translated comment
      const tx = await rpcCall<TransactionInfo | null>('tx_get', { txid: query })
      if (tx) {
        return { type: 'transaction', result: tx }
      }
    } catch {
      // ignore
    }
    
    try {
      // Translated comment
      const block = await rpcCall<Block | null>('block_getByHash', { hash: query })
      if (block) {
        return { type: 'block', result: block }
      }
    } catch {
      // ignore
    }
    
    // Translated comment
    if (query.startsWith('MC_') || query.length === 42) {
      const balance = await rpcCall<{ balance: number }>('account_getBalance', { address: query })
      if (balance) {
        return { type: 'address', result: { address: query, ...balance } }
      }
    }
    
    return { type: 'unknown', result: null }
  }
}

// ========== P2P distributed task APIs ==========

export interface P2PTask {
  taskId: string
  taskName: string
  taskType: string
  status: string
  progress: number
  totalShards: number
  completedShards: number
  createdAt: number
  startedAt?: number
  completedAt?: number
  shards?: Array<{
    shardId: string
    status: string
    assignedMiner: string
    retryCount: number
  }>
}

export interface P2PTaskCreateParams {
  taskName: string
  taskType?: string
  taskData?: string
  config?: Record<string, unknown>
  gpuCount?: number
  redundancy?: number
  shardCount?: number
  creatorId?: string
}

export interface P2PTaskStats {
  distributor: {
    nodeId: string
    role: string
    totalTasks: number
    completedTasks: number
    failedTasks: number
    pendingShards: number
    availableMiners: number
    p2pConnected: number
  }
  computeNode: {
    nodeId: string
    currentTasks: number
    completedTasks: number
    totalComputeTime: number
    averageComputeTime: number
  }
  p2pConnected: number
}

export interface P2PMiner {
  node_id: string
  address?: string
  sector?: string
  gpu_count?: number
  gpu_memory_gb?: number
  is_connected?: boolean
  registered_at?: number
}

export const p2pTaskApi = {
  // Translated comment
  create: async (params: P2PTaskCreateParams): Promise<{
    success: boolean
    taskId?: string
    taskName?: string
    taskType?: string
    status?: string
    shardCount?: number
    createdAt?: number
    error?: string
  }> => {
    try {
      return await rpcCall('p2pTask_create', { ...params })
    } catch (error) {
      return { success: false, error: String(error) }
    }
  },

  // Translated comment
  distribute: async (taskId: string): Promise<{
    success: boolean
    taskId?: string
    status?: string
    distributedShards?: number
    availableMiners?: number
    distributedAt?: number
    error?: string
  }> => {
    try {
      return await rpcCall('p2pTask_distribute', { taskId })
    } catch (error) {
      return { success: false, error: String(error) }
    }
  },

  // Translated comment
  getStatus: async (taskId: string): Promise<P2PTask | null> => {
    try {
      const result = await rpcCall<P2PTask>('p2pTask_getStatus', { taskId })
      if ('error' in result) return null
      return result
    } catch {
      return null
    }
  },

  // Translated comment
  getList: async (params?: {
    status?: string
    limit?: number
    offset?: number
  }): Promise<{ tasks: P2PTask[], total: number }> => {
    try {
      return await rpcCall('p2pTask_getList', params || {})
    } catch {
      return { tasks: [], total: 0 }
    }
  },

  // Translated comment
  getStats: async (): Promise<P2PTaskStats | null> => {
    try {
      return await rpcCall<P2PTaskStats>('p2pTask_getStats', {})
    } catch {
      return null
    }
  },

  // Translated comment
  cancel: async (taskId: string): Promise<{
    success: boolean
    taskId?: string
    status?: string
    cancelledAt?: number
    error?: string
  }> => {
    try {
      return await rpcCall('p2pTask_cancel', { taskId })
    } catch (error) {
      return { success: false, error: String(error) }
    }
  },

  // Translated comment
  registerMiner: async (params: {
    minerId: string
    address?: string
    sector?: string
    gpuCount?: number
    gpuMemoryGb?: number
  }): Promise<{
    success: boolean
    minerId?: string
    registeredAt?: number
    totalMiners?: number
    error?: string
  }> => {
    try {
      return await rpcCall('p2pTask_registerMiner', params)
    } catch (error) {
      return { success: false, error: String(error) }
    }
  },

  // Translated comment
  getMiners: async (): Promise<{ miners: P2PMiner[], total: number }> => {
    try {
      return await rpcCall('p2pTask_getMiners', {})
    } catch {
      return { miners: [], total: 0 }
    }
  },

  // Translated comment
  getResult: async (taskId: string): Promise<{
    taskId: string
    status: string
    ready: boolean
    progress?: number
    result?: Record<string, unknown>
    resultHash?: string
    completedAt?: number
    error?: string
  }> => {
    try {
      return await rpcCall('p2pTask_getResult', { taskId })
    } catch (error) {
      return { taskId, status: 'unknown', ready: false, error: String(error) }
    }
  }
}

// ========== P2P encrypted direct-transfer APIs ==========
// Translated comment
// Translated comment

export interface P2PTunnelTicket {
  ticketId: string
  sessionId: string
  taskId: string
  userEncryptedEndpoint: string
  minerEncryptedUserId: string
  sessionToken: string
  createdAt: number
  expiresAt: number
  transferMode: 'p2p' | 'relay'
  relayEndpoint: string
}

export const p2pTunnelApi = {
  /**
   * Translated comment
   */
  registerEndpoint: async (ip: string, port: number, publicKey: string): Promise<{
    success: boolean
    minerId?: string
    p2pReady?: boolean
    message?: string
  }> => {
    try {
      return await rpcCall('p2pTunnel_registerEndpoint', { ip, port, publicKey })
    } catch (error) {
      return { success: false, message: String(error) }
    }
  },

  /**
   * Translated comment
   */
  startServer: async (host?: string, port?: number): Promise<{
    success: boolean
    port?: number
    publicKey?: string
    message?: string
  }> => {
    try {
      return await rpcCall('p2pTunnel_startServer', { host: host || '0.0.0.0', port: port || 0 })
    } catch (error) {
      return { success: false, message: String(error) }
    }
  },

  /**
   * Translated comment
   * Translated comment
   */
  requestTicket: async (taskId: string, userPublicKey: string): Promise<{
    success: boolean
    transferMode?: 'p2p' | 'relay'
    ticket?: P2PTunnelTicket
    message?: string
  }> => {
    try {
      return await rpcCall('p2pTunnel_requestTicket', { taskId, userPublicKey })
    } catch (error) {
      return { success: false, message: String(error) }
    }
  },

  /**
   * Translated comment
   */
  getStatus: async (params: { sessionId?: string; taskId?: string }): Promise<{
    sessionId?: string
    taskId?: string
    transferMode?: string
    expired?: boolean
    createdAt?: number
    expiresAt?: number
    error?: string
  }> => {
    try {
      return await rpcCall('p2pTunnel_getStatus', params)
    } catch {
      return { error: 'failed' }
    }
  },

  /**
   * Translated comment
   */
  getMinerInfo: async (minerId?: string): Promise<{
    minerId: string
    p2pReady: boolean
    publicKey: string
    message: string
  }> => {
    try {
      return await rpcCall('p2pTunnel_getMinerP2PInfo', { minerId: minerId || '' })
    } catch {
      return { minerId: '', p2pReady: false, publicKey: '', message: 'unavailable' }
    }
  },
}

