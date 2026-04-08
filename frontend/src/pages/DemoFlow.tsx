import { useMemo, useState } from 'react'
import { ArrowRight, Cpu, FileCode2, PackageCheck, PlayCircle, ShoppingCart, Wallet } from 'lucide-react'
import { accountApi, demoApi, fileTransferApi, miningApi, taskApi } from '../api'

interface LogEntry {
  time: string
  action: string
  ok: boolean
  detail: string
}

type StepStatus = 'todo' | 'running' | 'done' | 'failed'

interface FlowStepState {
  status: StepStatus
  detail: string
}

const nowLabel = () => new Date().toLocaleTimeString()

export default function DemoFlow() {
  const initialIdentity = localStorage.getItem('wallet_address') || ''
  const [orderAddress, setOrderAddress] = useState('')
  const [minerAddress, setMinerAddress] = useState('')
  const [activeIdentity, setActiveIdentity] = useState(initialIdentity)
  const [orderId, setOrderId] = useState('')
  const [taskId, setTaskId] = useState('')
  const [busyAction, setBusyAction] = useState('')
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [rawData, setRawData] = useState<Record<string, unknown>>({})
  const [uiError, setUiError] = useState('')
  const [uiMessage, setUiMessage] = useState('')
  const [selectedFileName, setSelectedFileName] = useState('')
  const [uploadedFileRef, setUploadedFileRef] = useState('')
  const [uploadProgress, setUploadProgress] = useState({
    phase: '',
    percent: 0,
    uploadedBytes: 0,
    totalBytes: 0,
  })
  const [stats, setStats] = useState({
    acceptedOrders: 0,
    runningPrograms: 0,
    finalOrderStatus: '-',
    chainHeight: 0,
  })
  const [runtimeResult, setRuntimeResult] = useState('')
  const [runtimeResultLoading, setRuntimeResultLoading] = useState(false)
  const [runtimeResultError, setRuntimeResultError] = useState('')
  const [balances, setBalances] = useState({
    orderInitial: 0,
    orderCurrent: 0,
    minerInitial: 0,
    minerCurrent: 0,
    orderInited: false,
    minerInited: false,
  })
  const [lastOrderTotalPrice, setLastOrderTotalPrice] = useState(0)
  const [settlement, setSettlement] = useState({
    totalPrice: 0,
    buyerDebitTotal: 0,
    minerPayout: 0,
    platformFee: 0,
    treasuryFee: 0,
  })
  const [form, setForm] = useState({
    gpuType: 'RTX4090',
    gpuCount: 1,
    durationHours: 1,
    pricePerHour: 1,
    freeOrder: false,
    enableEncryption: false,
    dockerImage: 'python:3.11-slim',
    program: "x = 6 * 7\nresult = {'value': x, 'message': 'from user program'}",
    resultData: 'manual_visual_demo_result_ok',
  })
  const [flowState, setFlowState] = useState<Record<string, FlowStepState>>({
    buyer: { status: 'todo', detail: 'Create buyer account' },
    submit: { status: 'todo', detail: 'Submit compute order' },
    miner: { status: 'todo', detail: 'Create miner account' },
    start: { status: 'todo', detail: 'Start miner task mode' },
    encrypt: { status: 'todo', detail: 'Optional encryption before submit' },
    accept: { status: 'todo', detail: 'Accept order as miner' },
    complete: { status: 'todo', detail: 'Complete execution' },
    result: { status: 'todo', detail: 'Fetch result as buyer' },
  })

  const appendLog = (action: string, ok: boolean, detail: unknown) => {
    setLogs((prev) => [{ time: nowLabel(), action, ok, detail: String(detail) }, ...prev].slice(0, 80))
  }

  const setRaw = (key: string, value: unknown) => {
    setRawData((prev) => ({ ...prev, [key]: value }))
  }

  const setStep = (step: string, status: StepStatus, detail?: string) => {
    setFlowState((prev) => ({
      ...prev,
      [step]: {
        status,
        detail: detail || prev[step]?.detail || '',
      },
    }))
  }

  const useIdentity = (address: string, label: string) => {
    if (!address) {
      setUiError(`${label} address is empty`)
      return false
    }
    localStorage.setItem('wallet_address', address)
    setActiveIdentity(address)
    appendLog('Switch RPC identity', true, `${label}: ${address}`)
    return true
  }

  const syncBalanceForAddress = async (role: 'order' | 'miner', address: string) => {
    if (!address) return
    const account = await accountApi.getAccount(address)
    const main = Number(account?.mainBalance ?? account?.balance ?? 0)
    setBalances((prev) => {
      if (role === 'order') {
        return {
          ...prev,
          // Keep demo/market balance once it is available; chain balance is only initial fallback.
          orderCurrent: prev.orderInited ? prev.orderCurrent : main,
          orderInitial: prev.orderInited ? prev.orderInitial : main,
          orderInited: true,
        }
      }
      return {
        ...prev,
        // Keep demo/market balance once it is available; chain balance is only initial fallback.
        minerCurrent: prev.minerInited ? prev.minerCurrent : main,
        minerInitial: prev.minerInited ? prev.minerInitial : main,
        minerInited: true,
      }
    })
  }

  const syncBalances = async () => {
    await Promise.all([
      orderAddress ? syncBalanceForAddress('order', orderAddress) : Promise.resolve(),
      minerAddress ? syncBalanceForAddress('miner', minerAddress) : Promise.resolve(),
    ])
  }

  const applyDemoBalances = (payload: Record<string, unknown>) => {
    const buyerAfter = Number(payload.buyerBalanceAfter)
    const minerAfter = Number(payload.minerBalanceAfter)
    const totalPriceRaw = Number(payload.totalPrice)
    const totalPrice = Number.isFinite(totalPriceRaw) ? totalPriceRaw : lastOrderTotalPrice
    const buyerDebitRaw = Number(payload.buyerDebitTotal)
    const minerPayoutRaw = Number(payload.minerPayout)
    const platformFee = Number(payload.platformFee)
    const treasuryFee = Number(payload.treasuryFee)
    const buyerDebit = Number.isFinite(buyerDebitRaw) ? buyerDebitRaw : totalPrice
    const minerCredit = Number.isFinite(minerPayoutRaw) ? minerPayoutRaw : totalPrice

    setSettlement((prev) => ({
      totalPrice: Number.isFinite(totalPrice) ? totalPrice : prev.totalPrice,
      buyerDebitTotal: Number.isFinite(buyerDebit) ? buyerDebit : prev.buyerDebitTotal,
      minerPayout: Number.isFinite(minerCredit) ? minerCredit : prev.minerPayout,
      platformFee: Number.isFinite(platformFee) ? platformFee : prev.platformFee,
      treasuryFee: Number.isFinite(treasuryFee) ? treasuryFee : prev.treasuryFee,
    }))

    setBalances((prev) => ({
      ...prev,
      orderCurrent: Number.isFinite(buyerAfter) ? buyerAfter : prev.orderCurrent,
      orderInitial:
        Number.isFinite(buyerAfter) && Number.isFinite(buyerDebit)
          ? Math.max(0, buyerAfter + buyerDebit)
          : prev.orderInitial,
      orderInited: prev.orderInited || Number.isFinite(buyerAfter),
      minerCurrent: Number.isFinite(minerAfter) ? minerAfter : prev.minerCurrent,
      minerInitial:
        Number.isFinite(minerAfter) && Number.isFinite(minerCredit)
          ? Math.max(0, minerAfter - minerCredit)
          : prev.minerInitial,
      minerInited: prev.minerInited || Number.isFinite(minerAfter),
    }))
  }

  const callAction = async <T,>(actionName: string, fn: () => Promise<T>) => {
    setBusyAction(actionName)
    setUiError('')
    try {
      const result = await fn()
      appendLog(actionName, true, 'OK')
      return result
    } catch (e) {
      appendLog(actionName, false, e)
      throw e
    } finally {
      setBusyAction('')
    }
  }

  const fetchRuntimeResult = async (tid?: string) => {
    const targetTaskId = (tid || taskId || '').trim()
    if (!targetTaskId) {
      setRuntimeResult('')
      setRuntimeResultError('taskId 为空，无法获取运行结果')
      setStep('result', 'failed', 'Missing taskId')
      return
    }

    if (!orderAddress || activeIdentity !== orderAddress) {
      setRuntimeResult('')
      setRuntimeResultError('仅下单账户可查看结果：请先点击 Use Buyer')
      setStep('result', 'failed', 'Denied: switch to buyer first')
      return
    }

    setRuntimeResultLoading(true)
    setRuntimeResultError('')
    setStep('result', 'running', 'Fetching owner-only result...')
    try {
      const outputs = await taskApi.getTaskOutputs(targetTaskId)
      const resultFile = outputs.find((item) => item.name === 'result.json')
      if (!resultFile) {
        setRuntimeResult('')
        setRuntimeResultError('未找到 result.json，请先完成任务或检查任务输出权限')
        setStep('result', 'failed', 'result.json not found')
        return
      }

      if (resultFile.content && String(resultFile.content).trim()) {
        setRuntimeResult(resultFile.content)
      } else {
        setRuntimeResult(JSON.stringify(resultFile, null, 2))
      }
      appendLog('Fetch task result', true, `taskId=${targetTaskId}`)
      setStep('result', 'done', 'Result fetched by buyer')
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      setRuntimeResult('')
      setRuntimeResultError(msg)
      appendLog('Fetch task result', false, msg)
      setStep('result', 'failed', msg)
    } finally {
      setRuntimeResultLoading(false)
    }
  }

  const createOrderWallet = async () => {
    setStep('buyer', 'running', 'Creating buyer account...')
    const res = await callAction('Create order account', () => demoApi.createWallet('manual-order'))
    const addr = res.address || ''
    if (!addr) throw new Error('order account address missing')
    setOrderAddress(addr)
    useIdentity(addr, 'buyer')
    setRaw('orderWallet', res)
    appendLog('Create order account', true, addr)
    setStep('buyer', 'done', `Buyer ready: ${addr.slice(0, 14)}...`)
    await syncBalanceForAddress('order', addr)
  }

  const createMinerWallet = async () => {
    setStep('miner', 'running', 'Creating miner account...')
    const res = await callAction('Create miner account', () => demoApi.createWallet('manual-miner'))
    const addr = res.address || ''
    if (!addr) throw new Error('miner account address missing')
    setMinerAddress(addr)
    setRaw('minerWallet', res)
    appendLog('Create miner account', true, addr)
    setStep('miner', 'done', `Miner ready: ${addr.slice(0, 14)}...`)
    await syncBalanceForAddress('miner', addr)
  }

  const startMiner = async () => {
    if (!minerAddress) throw new Error('please create or input miner account first')
    setStep('start', 'running', 'Starting miner task mode...')
    const res = await callAction('Start miner task mode', () => demoApi.startMinerTaskMode(minerAddress))
    setRaw('miningStart', res)
    appendLog('Start miner task mode', true, res.message || 'started')
    setStep('start', 'done', 'Miner is accepting tasks')
  }

  const uploadDockerTaskFile = async (file: File) => {
    if (!file) return
    setSelectedFileName(file.name)
    const fileRef = await callAction('Upload docker task file', async () => {
      const ref = await fileTransferApi.chunkedUpload(file, (p) => setUploadProgress({
        phase: p.phase,
        percent: p.percent,
        uploadedBytes: p.uploadedBytes,
        totalBytes: p.totalBytes,
      }))
      if (!ref) {
        throw new Error('file upload failed')
      }
      return ref
    })

    setUploadedFileRef(fileRef)
    setUiMessage(`文件上传成功: ${file.name}`)
    setRaw('uploadedInputFile', {
      name: file.name,
      fileRef,
      size: file.size,
      type: file.type || 'application/octet-stream',
    })
    appendLog('Upload docker task file', true, `${file.name} -> ${fileRef}`)
  }

  const submitOrder = async () => {
    if (!orderAddress) throw new Error('please create or input order account first')
    setStep('submit', 'running', 'Submitting order...')
    if (form.enableEncryption) {
      setStep('encrypt', 'running', 'Encrypting program payload...')
      const preview = btoa(unescape(encodeURIComponent(form.program))).slice(0, 80)
      setRaw('encryption', {
        enabled: true,
        algorithm: 'base64-preview-for-demo-visualization',
        preview,
      })
      setStep('encrypt', 'done', 'Encryption visualization completed')
    } else {
      setStep('encrypt', 'todo', 'Encryption disabled')
    }
    useIdentity(orderAddress, 'buyer')
    const res = await callAction('Submit order', () => demoApi.submitOrderManual({
      buyerAddress: orderAddress,
      gpuType: form.gpuType,
      gpuCount: form.gpuCount,
      durationHours: form.durationHours,
      pricePerHour: form.pricePerHour,
      freeOrder: form.freeOrder,
      program: form.program,
      image: form.dockerImage,
      inputDataRef: uploadedFileRef || undefined,
      inputFilename: selectedFileName || undefined,
    }))
    setOrderId(res.orderId)
    setLastOrderTotalPrice(Number((res as { totalPrice?: number }).totalPrice || 0))
    setRaw('submitOrder', res)
    appendLog('Submit order', true, `orderId=${res.orderId}`)
    setStep('submit', 'done', `Order submitted: ${res.orderId}`)
    applyDemoBalances((res as unknown as Record<string, unknown>))
    await syncBalances()
  }

  const acceptOrder = async () => {
    if (!orderId || !minerAddress) throw new Error('need orderId and miner account')
    setStep('accept', 'running', 'Miner accepting order...')
    useIdentity(minerAddress, 'miner')
    const res = await callAction('Accept order', () => demoApi.acceptOrder(orderId, minerAddress))
    setTaskId(res.taskId)
    setRaw('acceptOrder', res)
    appendLog('Accept order', true, `taskId=${res.taskId}`)
    setStep('accept', 'done', `Accepted as task: ${res.taskId}`)
    applyDemoBalances((res as unknown as Record<string, unknown>))
    await syncBalances()
  }

  const refreshStatus = async () => {
    if (!minerAddress) throw new Error('need miner account')
    const miningStatus = await callAction('Refresh mining status', () => miningApi.getStatus(minerAddress))
    const acceptedCount = miningStatus.acceptedOrders?.length || 0
    const runningCount = miningStatus.runningPrograms?.length || 0
    setStats((prev) => ({ ...prev, acceptedOrders: acceptedCount, runningPrograms: runningCount }))
    setRaw('miningStatus', miningStatus)
    appendLog('Refresh mining status', true, `accepted=${acceptedCount}, running=${runningCount}`)
    if (typeof miningStatus.demoMainBalance === 'number') {
      setBalances((prev) => ({
        ...prev,
        minerCurrent: miningStatus.demoMainBalance || 0,
        minerInitial: prev.minerInited ? prev.minerInitial : (miningStatus.demoMainBalance || 0),
        minerInited: true,
      }))
    }
    await syncBalances()
  }

  const completeOrder = async () => {
    if (!orderId || !taskId) throw new Error('need orderId and taskId')
    setStep('complete', 'running', 'Completing execution...')
    const res = await callAction('Complete order', () => demoApi.completeOrderManual(orderId, taskId, form.resultData))
    setRaw('completeOrder', res)
    appendLog('Complete order', true, res.status)
    setStep('complete', 'done', 'Execution completed')
    await fetchRuntimeResult(taskId)
    await syncBalances()
  }

  const queryOrder = async () => {
    if (!orderId) throw new Error('need orderId')
    const orderInfo = await callAction('Query order', () => demoApi.getOrder(orderId))
    const chainInfo = await callAction('Query chain info', () => demoApi.getChainInfo())
    setStats((prev) => ({
      ...prev,
      finalOrderStatus: String(orderInfo.status || '-'),
      chainHeight: Number(chainInfo.height || 0),
    }))
    setRaw('orderInfo', orderInfo)
    setRaw('chainInfo', chainInfo)
    appendLog('Query order', true, `status=${String(orderInfo.status || '-')}`)
    applyDemoBalances(orderInfo)
    await fetchRuntimeResult(taskId)
    await syncBalances()
  }

  const clearAll = () => {
    setLogs([])
    setRawData({})
    setUiError('')
    setUiMessage('')
    setStats({ acceptedOrders: 0, runningPrograms: 0, finalOrderStatus: '-', chainHeight: 0 })
    setRuntimeResult('')
    setRuntimeResultError('')
    setRuntimeResultLoading(false)
    setOrderAddress('')
    setMinerAddress('')
    setActiveIdentity('')
    setOrderId('')
    setTaskId('')
    setSelectedFileName('')
    setUploadedFileRef('')
    setUploadProgress({ phase: '', percent: 0, uploadedBytes: 0, totalBytes: 0 })
    setSettlement({ totalPrice: 0, buyerDebitTotal: 0, minerPayout: 0, platformFee: 0, treasuryFee: 0 })
    setBalances({
      orderInitial: 0,
      orderCurrent: 0,
      minerInitial: 0,
      minerCurrent: 0,
      orderInited: false,
      minerInited: false,
    })
    setFlowState({
      buyer: { status: 'todo', detail: 'Create buyer account' },
      submit: { status: 'todo', detail: 'Submit compute order' },
      miner: { status: 'todo', detail: 'Create miner account' },
      start: { status: 'todo', detail: 'Start miner task mode' },
      encrypt: { status: 'todo', detail: 'Optional encryption before submit' },
      accept: { status: 'todo', detail: 'Accept order as miner' },
      complete: { status: 'todo', detail: 'Complete execution' },
      result: { status: 'todo', detail: 'Fetch result as buyer' },
    })
  }

  const disabled = useMemo(() => !!busyAction, [busyAction])
  const orderDelta = balances.orderCurrent - balances.orderInitial
  const minerDelta = balances.minerCurrent - balances.minerInitial
  const parsedRuntime = useMemo(() => {
    if (!runtimeResult) return null
    try {
      return JSON.parse(runtimeResult) as Record<string, unknown>
    } catch {
      return null
    }
  }, [runtimeResult])

  const parsedExecution = useMemo(() => {
    if (!parsedRuntime) return null
    const execution = parsedRuntime.execution
    if (!execution || typeof execution !== 'object') return null
    return execution as Record<string, unknown>
  }, [parsedRuntime])

  const displayResultData = useMemo(() => {
    if (!parsedRuntime) return ''
    const value = parsedRuntime.resultData
    if (value === undefined || value === null) return ''
    return typeof value === 'string' ? value : JSON.stringify(value, null, 2)
  }, [parsedRuntime])

  const displayExecutionOutput = useMemo(() => {
    if (!parsedExecution) return ''
    const value = parsedExecution.output
    if (value === undefined || value === null) return ''
    return typeof value === 'string' ? value : JSON.stringify(value, null, 2)
  }, [parsedExecution])

  return (
    <div className="space-y-6">
      {uiError ? (
        <div className="alert alert-error">{uiError}</div>
      ) : null}
      {uiMessage ? (
        <div className="alert alert-success">{uiMessage}</div>
      ) : null}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-console-text">Manual Dual-Account Demo</h1>
          <p className="text-console-text-muted mt-1">Create accounts, submit an order, accept it as miner, track status, and complete.</p>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
            <span className="text-console-text-muted">Current RPC identity:</span>
            <span className="font-mono px-2 py-1 rounded border border-console-border bg-console-bg text-console-text break-all">
              {activeIdentity || '-'}
            </span>
            <button className="btn-ghost py-1 px-2" onClick={() => useIdentity(orderAddress, 'buyer')} disabled={disabled || !orderAddress}>
              Use Buyer
            </button>
            <button className="btn-ghost py-1 px-2" onClick={() => useIdentity(minerAddress, 'miner')} disabled={disabled || !minerAddress}>
              Use Miner
            </button>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={clearAll} className="btn-secondary">Clear Panel</button>
          <span className="text-xs text-console-text-muted">{busyAction ? `Running: ${busyAction}` : 'Idle'}</span>
        </div>
      </div>

      <div className="card">
        <h2 className="font-semibold text-console-text mb-3">Visual Flow (Click-by-Click)</h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
          {[
            ['buyer', '1. Buyer Account'],
            ['submit', '2. Submit Order'],
            ['miner', '3. Miner Account'],
            ['start', '4. Start Accepting'],
            ['encrypt', '5. Encrypt (Optional)'],
            ['accept', '6. Accept Order'],
            ['complete', '7. Complete'],
            ['result', '8. Fetch Result (Buyer Only)'],
          ].map(([key, title]) => {
            const node = flowState[key]
            const color = node?.status === 'done'
              ? 'border-green-500/40 bg-green-500/10'
              : node?.status === 'running'
                ? 'border-blue-500/40 bg-blue-500/10'
                : node?.status === 'failed'
                  ? 'border-red-500/40 bg-red-500/10'
                  : 'border-console-border bg-console-bg'
            return (
              <div key={key} className={`rounded border p-2 ${color}`}>
                <div className="text-xs font-semibold text-console-text">{title}</div>
                <div className="text-[11px] text-console-text-muted mt-1">{node?.detail || '-'}</div>
              </div>
            )
          })}
        </div>
      </div>

      <div className="card">
        <h2 className="font-semibold text-console-text mb-3">Flow Board</h2>
        <div className="grid grid-cols-1 md:grid-cols-7 gap-3 items-center">
          <div className="rounded border border-console-border bg-console-bg px-3 py-3">
            <div className="text-console-text flex items-center gap-2 text-sm"><Wallet size={14} />Buyer Account</div>
            <input
              value={orderAddress}
              onChange={(e) => setOrderAddress(e.target.value.trim())}
              placeholder="MAIN_..."
              className="mt-2 input text-xs"
            />
            <button className="btn-secondary mt-2 w-full" onClick={createOrderWallet} disabled={disabled}>Create Account</button>
          </div>
          <div className="hidden md:flex justify-center text-console-text-muted"><ArrowRight size={16} /></div>
          <div className="rounded border border-console-border bg-console-bg px-3 py-3">
            <div className="text-console-text flex items-center gap-2 text-sm"><ShoppingCart size={14} />Submit Order</div>
            <input value={orderId} onChange={(e) => setOrderId(e.target.value.trim())} placeholder="order_xxx" className="mt-2 input text-xs" />
            <button className="btn-primary mt-2 w-full" onClick={submitOrder} disabled={disabled}>Submit</button>
          </div>
          <div className="hidden md:flex justify-center text-console-text-muted"><ArrowRight size={16} /></div>
          <div className="rounded border border-console-border bg-console-bg px-3 py-3">
            <div className="text-console-text flex items-center gap-2 text-sm"><Cpu size={14} />Miner Account</div>
            <input
              value={minerAddress}
              onChange={(e) => setMinerAddress(e.target.value.trim())}
              placeholder="MAIN_..."
              className="mt-2 input text-xs"
            />
            <div className="mt-2 grid grid-cols-2 gap-2">
              <button className="btn-secondary" onClick={createMinerWallet} disabled={disabled}>Create</button>
              <button className="btn-secondary" onClick={startMiner} disabled={disabled}>Start Accepting</button>
            </div>
          </div>
          <div className="hidden md:flex justify-center text-console-text-muted"><ArrowRight size={16} /></div>
          <div className="rounded border border-console-border bg-console-bg px-3 py-3">
            <div className="text-console-text flex items-center gap-2 text-sm"><PackageCheck size={14} />Accept / Complete</div>
            <input value={taskId} onChange={(e) => setTaskId(e.target.value.trim())} placeholder="task_xxx" className="mt-2 input text-xs" />
            <div className="mt-2 grid grid-cols-1 gap-2">
              <button className="btn-primary" onClick={acceptOrder} disabled={disabled}>Accept Order</button>
              <button className="btn-secondary" onClick={completeOrder} disabled={disabled}>Complete & Return</button>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card">
          <h2 className="font-semibold text-console-text mb-3">Order Params</h2>
          <div className="grid grid-cols-2 gap-2">
            <input className="input text-sm" value={form.gpuType} onChange={(e) => setForm((p) => ({ ...p, gpuType: e.target.value }))} placeholder="GPU Type" />
            <input className="input text-sm" type="number" value={form.gpuCount} onChange={(e) => setForm((p) => ({ ...p, gpuCount: Number(e.target.value || 1) }))} placeholder="GPU Count" />
            <input className="input text-sm" type="number" value={form.durationHours} onChange={(e) => setForm((p) => ({ ...p, durationHours: Number(e.target.value || 1) }))} placeholder="Duration (hours)" />
            <input className="input text-sm" type="number" step="0.1" value={form.pricePerHour} onChange={(e) => setForm((p) => ({ ...p, pricePerHour: Number(e.target.value || 0) }))} placeholder="Price / hour" />
          </div>
          <label className="flex items-center gap-2 text-sm text-console-text mt-3">
            <input type="checkbox" checked={form.freeOrder} onChange={(e) => setForm((p) => ({ ...p, freeOrder: e.target.checked }))} />
            Free order (price_per_hour=0)
          </label>
          <label className="flex items-center gap-2 text-sm text-console-text mt-2">
            <input type="checkbox" checked={form.enableEncryption} onChange={(e) => setForm((p) => ({ ...p, enableEncryption: e.target.checked }))} />
            Enable encryption visualization (optional)
          </label>
          <input className="input text-sm mt-3" value={form.dockerImage} onChange={(e) => setForm((p) => ({ ...p, dockerImage: e.target.value }))} placeholder="Docker image, e.g. python:3.11-slim" />
          <textarea className="input text-sm mt-3 min-h-[120px]" value={form.program} onChange={(e) => setForm((p) => ({ ...p, program: e.target.value }))} placeholder="Program content / startup code" />
          <div className="text-xs text-console-text-muted mt-2">
            Tip: set <code>result = ...</code> in your code to get accurate runtime feedback.
          </div>

          <div className="mt-3 rounded border border-console-border bg-console-bg p-3">
            <div className="text-sm text-console-text mb-2">Optional: Upload Docker task file</div>
            <input
              type="file"
              className="input text-sm"
              accept=".zip,.tar,.gz,.tgz,.py,.json,.yaml,.yml,.txt,.dockerfile,Dockerfile"
              onChange={async (e) => {
                const file = e.target.files?.[0]
                if (!file) return
                try {
                  await uploadDockerTaskFile(file)
                } catch (err) {
                  setUiError(String(err))
                  appendLog('Upload docker task file', false, err)
                } finally {
                  e.currentTarget.value = ''
                }
              }}
              disabled={disabled}
            />
            <div className="text-xs text-console-text-muted mt-2 break-all">
              File: {selectedFileName || '-'}
            </div>
            <div className="text-xs text-console-text-muted mt-1 break-all">
              fileRef: {uploadedFileRef || '-'}
            </div>
            <div className="text-xs text-console-text-muted mt-1">
              Upload: {uploadProgress.phase || '-'} {uploadProgress.percent}%
            </div>
            <div className="h-2 rounded-full bg-console-card border border-console-border overflow-hidden mt-2">
              <div className="h-full bg-console-primary transition-all duration-200" style={{ width: `${uploadProgress.percent}%` }} />
            </div>
          </div>
        </div>

        <div className="card">
          <h2 className="font-semibold text-console-text mb-3">Complete & Query</h2>
          <input className="input text-sm" value={form.resultData} onChange={(e) => setForm((p) => ({ ...p, resultData: e.target.value }))} placeholder="Result string to return on completion" />
          <div className="grid grid-cols-2 gap-2 mt-3">
            <button className="btn-secondary" onClick={refreshStatus} disabled={disabled}>Refresh Miner Status</button>
            <button className="btn-secondary" onClick={queryOrder} disabled={disabled}>Query Order / Chain</button>
            <button className="btn-secondary col-span-2" onClick={() => fetchRuntimeResult(taskId)} disabled={disabled || runtimeResultLoading}>
              {runtimeResultLoading ? 'Loading Result...' : 'Fetch Runtime Result (result.json)'}
            </button>
          </div>
          <div className="grid grid-cols-2 gap-3 mt-4">
            <div className="rounded border border-console-border px-3 py-2 bg-console-bg">
              <div className="text-xs text-console-text-muted">Accepted Orders</div>
              <div className="text-xl font-semibold text-console-text">{stats.acceptedOrders}</div>
            </div>
            <div className="rounded border border-console-border px-3 py-2 bg-console-bg">
              <div className="text-xs text-console-text-muted">Running Programs</div>
              <div className="text-xl font-semibold text-console-text">{stats.runningPrograms}</div>
            </div>
            <div className="rounded border border-console-border px-3 py-2 bg-console-bg">
              <div className="text-xs text-console-text-muted">Final Order Status</div>
              <div className="text-xl font-semibold text-console-text">{stats.finalOrderStatus}</div>
            </div>
            <div className="rounded border border-console-border px-3 py-2 bg-console-bg">
              <div className="text-xs text-console-text-muted">Chain Height</div>
              <div className="text-xl font-semibold text-console-text">{stats.chainHeight}</div>
            </div>
          </div>
          <div className="mt-3 rounded border border-console-border bg-console-bg p-3 text-xs text-console-text-muted space-y-1">
            <div>Order Total: {settlement.totalPrice.toFixed(4)} MAIN</div>
            <div>Buyer Debit: {settlement.buyerDebitTotal.toFixed(4)} MAIN</div>
            <div>Miner Payout: {settlement.minerPayout.toFixed(4)} MAIN</div>
            <div>Platform Fee: {settlement.platformFee.toFixed(4)} MAIN</div>
            <div>Treasury Fee: {settlement.treasuryFee.toFixed(4)} MAIN</div>
          </div>
          <div className="mt-3 rounded border border-console-border bg-console-bg p-3">
            <div className="text-xs text-console-text-muted mb-2">Runtime Result Feedback (Owner-only)</div>
            {runtimeResultError ? (
              <div className="text-xs text-red-400 break-all">{runtimeResultError}</div>
            ) : runtimeResult ? (
              <div className="space-y-3">
                {parsedRuntime ? (
                  <div className="grid grid-cols-1 gap-2 text-xs text-console-text">
                    <div className="rounded border border-console-border p-2 bg-console-card">
                      <div className="text-console-text-muted">Task</div>
                      <div className="font-mono break-all">{String(parsedRuntime.taskId || '-')}</div>
                    </div>
                    <div className="rounded border border-console-border p-2 bg-console-card">
                      <div className="text-console-text-muted">Result Data</div>
                      <pre className="overflow-auto max-h-[140px] whitespace-pre-wrap break-words">{displayResultData || '-'}</pre>
                    </div>
                    <div className="rounded border border-console-border p-2 bg-console-card">
                      <div className="text-console-text-muted">Execution Success</div>
                      <div>{parsedExecution ? String(Boolean(parsedExecution.success)) : '-'}</div>
                    </div>
                    <div className="rounded border border-console-border p-2 bg-console-card">
                      <div className="text-console-text-muted">Execution Mode</div>
                      <div>{parsedExecution ? String(parsedExecution.executionMode || '-') : '-'}</div>
                    </div>
                    <div className="rounded border border-console-border p-2 bg-console-card">
                      <div className="text-console-text-muted">Execution Output</div>
                      <pre className="overflow-auto max-h-[140px] whitespace-pre-wrap break-words">{displayExecutionOutput || '-'}</pre>
                    </div>
                  </div>
                ) : null}
                <div>
                  <div className="text-xs text-console-text-muted mb-1">Raw result.json</div>
                  <pre className="text-xs text-console-text overflow-auto max-h-[220px] whitespace-pre-wrap break-words">
{runtimeResult}
                  </pre>
                </div>
              </div>
            ) : (
              <div className="text-xs text-console-text-muted">No runtime result yet.</div>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card">
          <div className="text-sm text-console-text-muted mb-1 flex items-center gap-2"><Wallet size={14} />Order Account</div>
          <div className="font-mono text-sm text-console-text break-all">{orderAddress || '-'}</div>
          <div className="mt-2 text-sm text-console-text">Balance: {balances.orderCurrent.toFixed(4)} MAIN</div>
          <div className={`text-xs mt-1 ${orderDelta < 0 ? 'text-red-400' : orderDelta > 0 ? 'text-green-400' : 'text-console-text-muted'}`}>
            Change: {orderDelta >= 0 ? '+' : ''}{orderDelta.toFixed(4)} MAIN
          </div>
        </div>
        <div className="card">
          <div className="text-sm text-console-text-muted mb-1 flex items-center gap-2"><Cpu size={14} />Mining Account</div>
          <div className="font-mono text-sm text-console-text break-all">{minerAddress || '-'}</div>
          <div className="mt-2 text-sm text-console-text">Balance: {balances.minerCurrent.toFixed(4)} MAIN</div>
          <div className={`text-xs mt-1 ${minerDelta < 0 ? 'text-red-400' : minerDelta > 0 ? 'text-green-400' : 'text-console-text-muted'}`}>
            Change: {minerDelta >= 0 ? '+' : ''}{minerDelta.toFixed(4)} MAIN
          </div>
        </div>
      </div>

      <div className="card">
        <h2 className="font-semibold text-console-text mb-3 flex items-center gap-2"><PlayCircle size={16} />Operation Logs</h2>
        <div className="space-y-2 max-h-[300px] overflow-auto pr-1">
          {logs.length === 0 ? <div className="text-sm text-console-text-muted">No logs yet. Click an action above.</div> : null}
          {logs.map((log, idx) => (
            <div key={`${log.time}-${idx}`} className={`border rounded px-3 py-2 ${log.ok ? 'border-green-500/40 bg-green-500/10' : 'border-red-500/40 bg-red-500/10'}`}>
              <div className="flex items-center justify-between gap-2">
                <div className="text-sm text-console-text">{log.action}</div>
                <div className="text-xs text-console-text-muted">{log.time}</div>
              </div>
              <div className="text-xs text-console-text-muted mt-1 break-all">{log.detail}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <h2 className="font-semibold text-console-text mb-3 flex items-center gap-2"><FileCode2 size={16} />Live JSON</h2>
        <pre className="text-xs bg-console-bg border border-console-border rounded p-3 overflow-auto max-h-[420px] text-console-text">
{JSON.stringify(rawData, null, 2)}
        </pre>
      </div>
    </div>
  )
}
