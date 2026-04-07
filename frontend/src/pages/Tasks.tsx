import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { 
  Plus, 
  Search, 
  Clock, 
  Play, 
  CheckCircle, 
  XCircle,
  AlertTriangle,
  RefreshCw,
  ChevronDown,
  Upload,
  Code,
  Cpu,
  Lock,
  Shield,
  Loader2,
  Network,
  Layers,
  Package
} from 'lucide-react'
import { taskApi, encryptedTaskApi, fileTransferApi, Task } from '../api'
import type { FileUploadProgress } from '../api'
import { useAccountStore } from '../store'
import P2PTasks from '../components/P2PTasks'
import { useTranslation } from '../i18n'

type TaskStatus = 'pending' | 'assigned' | 'running' | 'completed' | 'disputed' | 'dispute' | 'cancelled' | 'failed'

function TaskStatusBadge({ status }: { status: TaskStatus }) {
  const { t } = useTranslation()
  const config: Record<TaskStatus, { class: string; label: string; icon: React.ReactNode }> = {
    pending: { class: 'badge-warning', label: t('status.waitingOrder'), icon: <Clock size={12} /> },
    assigned: { class: 'badge-info', label: t('status.assigned'), icon: <Cpu size={12} /> },
    running: { class: 'badge-info', label: t('status.executing'), icon: <Play size={12} /> },
    completed: { class: 'badge-success', label: t('status.completed'), icon: <CheckCircle size={12} /> },
    dispute: { class: 'badge-error', label: t('status.dispute'), icon: <AlertTriangle size={12} /> },
    disputed: { class: 'badge-error', label: t('status.dispute'), icon: <AlertTriangle size={12} /> },
    cancelled: { class: 'badge-neutral', label: t('status.cancelled'), icon: <XCircle size={12} /> },
    failed: { class: 'badge-error', label: t('status.failed'), icon: <XCircle size={12} /> },
  }
  const { class: cls, label, icon } = config[status] || { class: 'badge-neutral', label: status, icon: null }
  return (
    <span className={`badge ${cls} gap-1`}>
      {icon}
      {label}
    </span>
  )
}

export default function Tasks() {
  useAccountStore()
  const { t } = useTranslation()
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [activeTab, setActiveTab] = useState<'local' | 'p2p'>('local')
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    const fetchTasks = async () => {
      setLoading(true)
      try {
        const result = await taskApi.getTasks(
          statusFilter !== 'all' ? { status: statusFilter } : undefined
        )
        setTasks(result.tasks)
      } catch (err) {
        console.error(err)
      } finally {
        setLoading(false)
      }
    }
    fetchTasks()
  }, [statusFilter, refreshKey])

  const filteredTasks = tasks.filter(task => {
    if (searchQuery && !task.title.toLowerCase().includes(searchQuery.toLowerCase()) && 
        !task.taskId.includes(searchQuery)) {
      return false
    }
    return true
  })

  const stats = {
    total: tasks.length,
    running: tasks.filter(t => t.status === 'running' || t.status === 'assigned').length,
    completed: tasks.filter(t => t.status === 'completed').length,
    failed: tasks.filter((t) => {
      const s = String(t.status)
      return s === 'cancelled' || s === 'disputed' || s === 'dispute'
    }).length,
  }

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-console-text">{t('tasks.title')}</h1>
          <p className="text-console-text-muted mt-1">{t('tasks.subtitle')}</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="btn-primary flex items-center gap-2"
        >
          <Plus size={16} />
          {t('tasks.createTask')}
        </button>
      </div>

      {/* 任务类型切换标签 */}
      <div className="flex gap-2 border-b border-console-border pb-2">
        <button
          onClick={() => setActiveTab('local')}
          className={`flex items-center gap-2 px-4 py-2 rounded-t-lg transition-colors ${
            activeTab === 'local'
              ? 'bg-console-surface text-console-primary border-b-2 border-console-primary'
              : 'text-console-text-muted hover:text-console-text'
          }`}
        >
          <Layers size={16} />
          {t('tasks.localTasks')}
        </button>
        <button
          onClick={() => setActiveTab('p2p')}
          className={`flex items-center gap-2 px-4 py-2 rounded-t-lg transition-colors ${
            activeTab === 'p2p'
              ? 'bg-console-surface text-console-primary border-b-2 border-console-primary'
              : 'text-console-text-muted hover:text-console-text'
          }`}
        >
          <Network size={16} />
          {t('tasks.p2pTasks')}
        </button>
      </div>

      {/* P2P 任务视图 */}
      {activeTab === 'p2p' ? (
        <P2PTasks />
      ) : (
        <>
          {/* 统计卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="stat-card">
          <div className="stat-value">{stats.total}</div>
          <div className="stat-label">{t('tasks.totalTasks')}</div>
        </div>
        <div className="stat-card">
          <div className="stat-value text-console-accent">{stats.running}</div>
          <div className="stat-label">{t('tasks.inProgress')}</div>
        </div>
        <div className="stat-card">
          <div className="stat-value text-console-primary">{stats.completed}</div>
          <div className="stat-label">{t('tasks.completed')}</div>
        </div>
        <div className="stat-card">
          <div className="stat-value text-console-error">{stats.failed}</div>
          <div className="stat-label">{t('tasks.failedDispute')}</div>
        </div>
      </div>

      {/* 筛选栏 */}
      <div className="card">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-console-text-muted" />
            <input
              type="text"
              placeholder={t('tasks.searchPlaceholder')}
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
                <option value="all">{t('tasks.allStatus')}</option>
                <option value="pending">{t('status.waitingOrder')}</option>
                <option value="running">{t('status.executing')}</option>
                <option value="completed">{t('status.completed')}</option>
                <option value="failed">{t('status.failed')}</option>
                <option value="dispute">{t('status.dispute')}</option>
              </select>
              <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-console-text-muted pointer-events-none" />
            </div>
            <button
              onClick={() => { setStatusFilter('all'); setSearchQuery(''); }}
              className="btn-ghost"
            >
              <RefreshCw size={14} />
            </button>
          </div>
        </div>
      </div>

      {/* 任务列表 */}
      <div className="card p-0">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <RefreshCw className="animate-spin text-console-accent" size={24} />
          </div>
        ) : filteredTasks.length > 0 ? (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>{t('tasks.task')}</th>
                  <th>{t('common.type')}</th>
                  <th>GPU</th>
                  <th>{t('common.status')}</th>
                  <th>{t('common.progress')}</th>
                  <th>{t('tasks.createdAt')}</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filteredTasks.map((task) => (
                  <tr key={task.taskId}>
                    <td>
                      <div>
                        <div className="font-medium text-console-text">{task.title}</div>
                        <div className="text-xs text-console-text-muted font-mono">{task.taskId}</div>
                      </div>
                    </td>
                    <td>
                      <span className="badge badge-neutral">{task.taskType}</span>
                    </td>
                    <td>
                      <div className="text-sm">
                        <span className="text-console-text">{task.gpuType || 'N/A'}</span>
                        {task.gpuCount && (
                          <span className="text-console-text-muted"> × {task.gpuCount}</span>
                        )}
                      </div>
                    </td>
                    <td>
                      <TaskStatusBadge status={task.status as TaskStatus} />
                    </td>
                    <td>
                      <div className="flex items-center gap-2">
                        <div className="progress-bar w-20">
                          <div 
                            className={`h-full rounded-full transition-all ${
                              task.status === 'completed' ? 'bg-console-primary' : 'bg-console-accent'
                            }`}
                            style={{ width: `${task.progress || 0}%` }}
                          />
                        </div>
                        <span className="text-xs text-console-text-muted">{task.progress || 0}%</span>
                      </div>
                    </td>
                    <td className="text-sm text-console-text-muted">
                      {new Date(task.createdAt).toLocaleDateString('zh-CN')}
                    </td>
                    <td>
                      <Link 
                        to={`/tasks/${task.taskId}`}
                        className="btn-ghost py-1 px-3 text-sm"
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
          <div className="text-center py-12 text-console-text-muted">
            <Code size={32} className="mx-auto mb-2 opacity-50" />
            <p>{t('tasks.noTasks')}</p>
            <button 
              onClick={() => setShowCreateModal(true)}
              className="text-console-accent hover:underline text-sm mt-2"
            >
              {t('tasks.createFirstTask')}
            </button>
          </div>
        )}
      </div>
        </>
      )}

      {/* 创建任务弹窗 */}
      {showCreateModal && (
        <CreateTaskModal onClose={(refresh?: boolean) => {
          setShowCreateModal(false)
          if (refresh) {
            setRefreshKey(prev => prev + 1)
          }
        }} />
      )}
    </div>
  )
}

// 创建任务弹窗
function CreateTaskModal({ onClose }: { onClose: (refresh?: boolean) => void }) {
  const { t } = useTranslation()
  const [step, setStep] = useState(1)
  const [submitting, setSubmitting] = useState(false)
  const [submitResult, setSubmitResult] = useState<{success: boolean, message: string, taskId?: string} | null>(null)
  const [validationError, setValidationError] = useState('')
  const [codeContent, setCodeContent] = useState('')
  const [inputContent, setInputContent] = useState('')
  const [requirementsContent, setRequirementsContent] = useState('')
  const [codeFile, setCodeFile] = useState<File | null>(null)
  const [dataFile, setDataFile] = useState<File | null>(null)
  const [dataUploadMethod, setDataUploadMethod] = useState<'text' | 'file'>('text')
  const [uploadProgress, setUploadProgress] = useState<FileUploadProgress | null>(null)
  const [maxMemoryGb, setMaxMemoryGb] = useState(8)
  const [maxTimeoutHours, setMaxTimeoutHours] = useState(0) // 0 = 使用 estimatedHours
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    taskType: 'ai_training',
    gpuType: 'H100',
    gpuCount: 4,
    estimatedHours: 4,
    budgetPerHour: 2.0,
    codeUploadMethod: 'upload', // upload | git | paste
    enableEncryption: false, // 演示默认关闭，避免加密预算/密钥门槛影响提交
    gitUrl: ''
  })

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setCodeFile(file)
    }
  }

  const handleDataFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const MAX_DATA_SIZE = 100 * 1024 * 1024 * 1024 // 100 GB（分块上传支持）
    if (file.size > MAX_DATA_SIZE) {
      setSubmitResult({ success: false, message: `${t('tasks.modal.dataFileTooLarge')}${(file.size / 1024 / 1024 / 1024).toFixed(1)}GB` })
      return
    }
    const DATA_EXTENSIONS = ['.csv', '.json', '.jsonl', '.txt', '.npy', '.npz', '.h5', '.hdf5',
      '.parquet', '.pt', '.pth', '.pkl', '.zip', '.tar', '.gz', '.tsv', '.xml', '.yaml', '.yml',
      '.onnx', '.safetensors', '.bin', '.arrow', '.feather', '.lz4', '.zst', '.bz2', '.xz',
      '.tif', '.tiff', '.png', '.jpg', '.jpeg', '.wav', '.mp3', '.mp4']
    const fileName = file.name.toLowerCase()
    const hasValidExt = DATA_EXTENSIONS.some(ext => fileName.endsWith(ext))
    if (!hasValidExt) {
      setSubmitResult({ success: false, message: `${t('tasks.modal.unsupportedDataFileType')}${DATA_EXTENSIONS.join(', ')}` })
      return
    }
    setDataFile(file)
  }

  const handleSubmit = async () => {
    setSubmitting(true)
    setSubmitResult(null)
    
    try {
      let codeData = ''
      
      // 准备代码数据（Base64 编码�?
      if (formData.codeUploadMethod === 'paste' && codeContent) {
        codeData = encryptedTaskApi.encodeToBase64(codeContent)
      } else if (formData.codeUploadMethod === 'upload' && codeFile) {
        // 文件类型和大小预检
        const MAX_FILE_SIZE = 50 * 1024 * 1024 // 50 MB
        if (codeFile.size > MAX_FILE_SIZE) {
          setSubmitResult({ success: false, message: `${t('tasks.modal.codeFileTooLarge')}${(codeFile.size / 1024 / 1024).toFixed(1)}MB` })
          setSubmitting(false)
          return
        }
        const ALLOWED_EXTENSIONS = ['.py', '.pyw', '.ipynb', '.txt', '.md', '.rst', '.json', '.jsonl', '.yaml', '.yml', '.toml', '.csv', '.tsv', '.xml', '.r', '.jl', '.zip', '.tar', '.gz', '.tgz', '.dockerfile', '.dockerignore']
        const fileName = codeFile.name.toLowerCase()
        const hasValidExt =
          ALLOWED_EXTENSIONS.some(ext => fileName.endsWith(ext)) ||
          fileName === 'dockerfile' ||
          fileName === 'docker-compose' ||
          fileName.startsWith('docker-compose.')
        if (!hasValidExt) {
          setSubmitResult({ success: false, message: `${t('tasks.modal.unsupportedFileType')}${ALLOWED_EXTENSIONS.join(', ')}` })
          setSubmitting(false)
          return
        }
        codeData = await encryptedTaskApi.fileToBase64(codeFile)
      }

      // 前端代码安全预检（快速检测常见恶意模�?�?粘贴和文件上传均检查）
      let codeToCheck = ''
      if (formData.codeUploadMethod === 'paste') {
        codeToCheck = codeContent
      } else if (formData.codeUploadMethod === 'upload' && codeFile) {
        // 对文本格式的代码文件也进行安全检�?
        const textExtensions = ['.py', '.pyw', '.txt', '.md', '.rst', '.json', '.jsonl', '.yaml', '.yml', '.toml', '.csv', '.tsv', '.xml', '.r', '.jl', '.ipynb', '.dockerfile', '.dockerignore']
        const fn = codeFile.name.toLowerCase()
        if (textExtensions.some(ext => fn.endsWith(ext)) || fn === 'dockerfile' || fn.startsWith('docker-compose.')) {
          try { codeToCheck = await codeFile.text() } catch { /* binary file, skip text check */ }
        }
      }
      if (codeToCheck) {
        const BLOCKED_PATTERNS = [
          { pattern: /\bos\.system\s*\(/, msg: t('tasks.modal.blocked.osSystem') },
          { pattern: /\bsubprocess\./, msg: t('tasks.modal.blocked.subprocess') },
          { pattern: /\bsocket\.socket\s*\(/, msg: t('tasks.modal.blocked.socket') },
          { pattern: /\bctypes\./, msg: t('tasks.modal.blocked.ctypes') },
          { pattern: /\b__import__\s*\(/, msg: t('tasks.modal.blocked.dynamicImport') },
          { pattern: /\bopen\s*\(\s*['"]\/(?:etc|proc|sys|dev)/, msg: t('tasks.modal.blocked.systemDir') },
          { pattern: /\beval\s*\(\s*compile/, msg: t('tasks.modal.blocked.evalCompile') },
        ]
        for (const { pattern, msg } of BLOCKED_PATTERNS) {
          if (pattern.test(codeToCheck)) {
            setSubmitResult({ success: false, message: `${t('tasks.modal.securityCheckFailed')}${msg}` })
            setSubmitting(false)
            return
          }
        }
      }
      
      // 准备输入数据
      let inputData = ''
      let inputDataRef = ''
      const CHUNKED_THRESHOLD = 50 * 1024 * 1024 // 50MB 以上使用分块上传
      
      if (dataUploadMethod === 'file' && dataFile) {
        if (dataFile.size > CHUNKED_THRESHOLD) {
          // 大文件：使用分块上传
          setSubmitResult({ success: false, message: t('tasks.modal.uploadingLargeFile') })
          const fileId = await fileTransferApi.chunkedUpload(dataFile, (p) => {
            setUploadProgress(p)
          })
          setUploadProgress(null)
          if (!fileId) {
            setSubmitResult({ success: false, message: t('tasks.modal.largeFileUploadFailed') })
            setSubmitting(false)
            return
          }
          inputDataRef = fileId
        } else {
          // 小文件：直接 Base64 编码
          inputData = await encryptedTaskApi.fileToBase64(dataFile)
        }
      } else if (dataUploadMethod === 'text' && inputContent) {
        inputData = encryptedTaskApi.encodeToBase64(inputContent)
      }

      if (formData.enableEncryption) {
        // 使用加密任务 API
        const result = await encryptedTaskApi.create({
          title: formData.title,
          description: formData.description,
          codeData: codeData,
          inputData: inputData,
          inputDataRef: inputDataRef,
          taskType: formData.taskType,
          estimatedHours: formData.estimatedHours,
          budgetPerHour: formData.budgetPerHour,
          requirements: requirementsContent || '',
          maxMemoryGb: maxMemoryGb,
          maxTimeoutHours: maxTimeoutHours || formData.estimatedHours,
        })

        setSubmitResult({
          success: true,
          message: `${t('tasks.modal.encryptedTaskCreated')}${result.taskId}`,
          taskId: result.taskId
        })

        // 自动提交任务
        const submitResult = await encryptedTaskApi.submit(result.taskId)
        if (!submitResult?.submitted) {
          setSubmitResult({
            success: false,
            message: `${t('tasks.modal.createEncryptedTaskFailed')}: 提交阶段失败`
          })
          setSubmitting(false)
          return
        }

        setTimeout(() => {
          onClose(true)
        }, 2000)
      } else {
        // 使用普通任�?API
        const result = await taskApi.createTask({
          title: formData.title,
          description: formData.description,
          taskType: formData.taskType as Task['taskType'],
          priority: 'normal',
          gpuType: formData.gpuType,
          gpuCount: formData.gpuCount,
          estimatedHours: formData.estimatedHours,
          maxPrice: formData.budgetPerHour * formData.estimatedHours,
          slaId: 'default',
          requirements: requirementsContent || '',
        })
        
        if (result) {
          setSubmitResult({
            success: true,
            message: `${t('tasks.modal.taskCreated')}${result.taskId}`,
            taskId: result.taskId
          })
          setTimeout(() => {
            onClose(true)
          }, 2000)
        } else {
          setSubmitResult({
            success: false,
            message: t('tasks.modal.createTaskFailed')
          })
        }
      }
    } catch (err) {
      setSubmitResult({
        success: false,
        message: `${t('tasks.modal.createFailed')}${String(err)}`
      })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={() => onClose()}>
      <div className="modal max-w-2xl" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="flex items-center gap-2">
            <h3 className="text-lg font-semibold">{t('tasks.modal.createNewTask')}</h3>
            {formData.enableEncryption && (
              <span className="flex items-center gap-1 text-xs px-2 py-0.5 bg-green-500/20 text-green-400 rounded">
                <Lock size={12} />
                {t('tasks.modal.e2eEncryption')}
              </span>
            )}
          </div>
        </div>

        <div className="modal-body">
          {/* 加密开�?*/}
          <div className="mb-4 p-3 rounded-lg bg-console-bg/50 border border-console-border">
            <label className="flex items-center justify-between cursor-pointer">
              <div className="flex items-center gap-3">
                <Shield size={20} className={formData.enableEncryption ? 'text-green-400' : 'text-console-text-muted'} />
                <div>
                  <div className="font-medium text-console-text">{t('tasks.modal.e2eEncryption')}</div>
                  <div className="text-xs text-console-text-muted">
                    {t('tasks.modal.encryptionDesc')}
                  </div>
                </div>
              </div>
              <div 
                className={`relative w-12 h-6 rounded-full transition-colors ${
                  formData.enableEncryption ? 'bg-green-500' : 'bg-console-border'
                }`}
                onClick={() => setFormData({ ...formData, enableEncryption: !formData.enableEncryption })}
              >
                <div 
                  className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                    formData.enableEncryption ? 'translate-x-7' : 'translate-x-1'
                  }`}
                />
              </div>
            </label>
          </div>

          {/* 步骤指示�?*/}
          <div className="flex items-center gap-4 mb-6">
            {[t('tasks.modal.basicInfo'), t('tasks.modal.resourceConfig'), t('tasks.modal.codeSubmit')].map((label, i) => (
              <div key={i} className="flex items-center gap-2">
                <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium ${
                  step > i + 1 ? 'bg-console-primary text-white' :
                  step === i + 1 ? 'bg-console-accent text-white' :
                  'bg-console-border text-console-text-muted'
                }`}>
                  {i + 1}
                </div>
                <span className={step === i + 1 ? 'text-console-text' : 'text-console-text-muted'}>
                  {label}
                </span>
                {i < 2 && <div className="w-8 h-px bg-console-border" />}
              </div>
            ))}
          </div>

          {/* 步骤1：基本信�?*/}
          {step === 1 && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-console-text mb-2">{t('tasks.modal.taskName')}</label>
                <input
                  type="text"
                  value={formData.title}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                  placeholder={t('tasks.modal.titlePlaceholder')}
                  className="input"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-console-text mb-2">{t('tasks.modal.taskDescription')}</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder={t('tasks.modal.descPlaceholder')}
                  rows={3}
                  className="input"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-console-text mb-2">{t('tasks.modal.taskType')}</label>
                <select
                  value={formData.taskType}
                  onChange={(e) => setFormData({ ...formData, taskType: e.target.value })}
                  className="input"
                >
                  <option value="ai_training">{t('tasks.modal.aiTraining')}</option>
                  <option value="ai_inference">{t('tasks.modal.aiInference')}</option>
                  <option value="rendering">{t('tasks.modal.rendering')}</option>
                  <option value="scientific">{t('tasks.modal.scientific')}</option>
                  <option value="other">{t('tasks.modal.other')}</option>
                </select>
              </div>
            </div>
          )}

          {/* 步骤2：资源配�?*/}
          {step === 2 && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-console-text mb-2">{t('tasks.modal.gpuType')}</label>
                <div className="grid grid-cols-2 gap-3">
                  {['H100', 'A100', 'RTX4090', 'RTX3090', 'RTX3080'].map((gpu) => (
                    <button
                      key={gpu}
                      onClick={() => setFormData({ ...formData, gpuType: gpu })}
                      className={`p-3 rounded-lg border text-left transition-all ${
                        formData.gpuType === gpu
                          ? 'border-console-accent bg-console-accent/10'
                          : 'border-console-border hover:border-console-accent/50'
                      }`}
                    >
                      <div className="font-medium text-console-text">{gpu}</div>
                      <div className="text-xs text-console-text-muted">
                        {gpu === 'H100' ? '80GB HBM3' :
                         gpu === 'A100' ? '80GB HBM2e' :
                         gpu === 'RTX3080' ? '10GB GDDR6X' :
                         '24GB GDDR6X'}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-console-text mb-2">{t('tasks.modal.gpuCount')}</label>
                  <select
                    value={formData.gpuCount}
                    onChange={(e) => setFormData({ ...formData, gpuCount: Number(e.target.value) })}
                    className="input"
                  >
                    {[1, 2, 4, 8].map((n) => (
                      <option key={n} value={n}>{n}x GPU</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-console-text mb-2">{t('tasks.modal.estimatedDuration')}</label>
                  <select
                    value={formData.estimatedHours}
                    onChange={(e) => setFormData({ ...formData, estimatedHours: Number(e.target.value) })}
                    className="input"
                  >
                    {[1, 2, 4, 8, 12, 24].map((h) => (
                      <option key={h} value={h}>{h} {t('tasks.modal.hours')}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* 资源配置（大模型/大数据支持） */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-console-text mb-2">{t('tasks.modal.maxMemory')}</label>
                  <input type="number" min="1" step="any" placeholder="����: 16" value={maxMemoryGb} onChange={(e) => setMaxMemoryGb(Number(e.target.value))} className="input w-full" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-console-text mb-2">{t('tasks.modal.maxExecutionTime')}</label>
                  <select
                    value={maxTimeoutHours}
                    onChange={(e) => setMaxTimeoutHours(Number(e.target.value))}
                    className="input"
                  >
                    <option value={0}>{t('tasks.modal.sameAsEstimated')}</option>
                    {[1, 2, 4, 8, 12, 24, 48, 72].map((h) => (
                      <option key={h} value={h}>{h} {t('tasks.modal.hours')}</option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
          )}

          {/* 步骤3：代码提�?*/}
          {step === 3 && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-console-text mb-2">{t('tasks.modal.codeSubmitMethod')}</label>
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { id: 'upload', icon: <Upload size={20} />, label: t('tasks.modal.uploadArchive') },
                    { id: 'git', icon: <Code size={20} />, label: t('tasks.modal.gitRepo') },
                    { id: 'paste', icon: <Code size={20} />, label: t('tasks.modal.onlinePaste') },
                  ].map((method) => (
                    <button
                      key={method.id}
                      onClick={() => setFormData({ ...formData, codeUploadMethod: method.id })}
                      className={`p-4 rounded-lg border flex flex-col items-center gap-2 transition-all ${
                        formData.codeUploadMethod === method.id
                          ? 'border-console-accent bg-console-accent/10'
                          : 'border-console-border hover:border-console-accent/50'
                      }`}
                    >
                      <div className="text-console-text">{method.icon}</div>
                      <div className="text-sm text-console-text">{method.label}</div>
                    </button>
                  ))}
                </div>
              </div>

              {formData.codeUploadMethod === 'upload' && (
                <div className="border-2 border-dashed border-console-border rounded-lg p-8 text-center">
                  <input
                    type="file"
                    accept=".zip,.tar,.gz,.tgz,.py,.ipynb,.json,.jsonl,.yaml,.yml,.txt,.md,.rst,.toml,.dockerfile,.dockerignore,Dockerfile,docker-compose.yml,docker-compose.yaml"
                    onChange={handleFileSelect}
                    className="hidden"
                    id="code-file-input"
                  />
                  <Upload size={32} className="mx-auto mb-2 text-console-text-muted" />
                  {codeFile ? (
                    <div className="text-console-accent">
                      <p className="font-medium">{codeFile.name}</p>
                      <p className="text-xs text-console-text-muted">
                        {(codeFile.size / 1024).toFixed(1)} KB
                      </p>
                    </div>
                  ) : (
                    <p className="text-console-text-muted">{t('tasks.modal.dragOrClickUpload')}</p>
                  )}
                  <label htmlFor="code-file-input" className="btn-secondary mt-4 cursor-pointer inline-block">
                    {codeFile ? t('tasks.modal.changeFile') : t('tasks.modal.selectFile')}
                  </label>
                </div>
              )}

              {formData.codeUploadMethod === 'git' && (
                <div>
                  <label className="block text-sm font-medium text-console-text mb-2">{t('tasks.modal.gitRepoAddress')}</label>
                  <input
                    type="text"
                    value={formData.gitUrl}
                    onChange={(e) => setFormData({ ...formData, gitUrl: e.target.value })}
                    placeholder="https://github.com/user/repo.git"
                    className="input"
                  />
                  <p className="text-xs text-console-text-muted mt-2">{t('tasks.modal.gitRepoHint')}</p>
                </div>
              )}

              {formData.codeUploadMethod === 'paste' && (
                <div>
                  <label className="block text-sm font-medium text-console-text mb-2">{t('tasks.modal.pythonCode')}</label>
                  <textarea
                    value={codeContent}
                    onChange={(e) => setCodeContent(e.target.value)}
                    placeholder={t('tasks.modal.codePlaceholder')}
                    className="input font-mono text-sm h-48"
                  />
                </div>
              )}

              {/* 输入数据 */}
              <div>
                <label className="block text-sm font-medium text-console-text mb-2">
                  {t('tasks.modal.inputData')} <span className="text-console-text-muted">{t('tasks.modal.inputDataHint')}</span>
                </label>
                <div className="flex gap-2 mb-2">
                  <button
                    type="button"
                    onClick={() => setDataUploadMethod('text')}
                    className={`px-3 py-1 text-xs rounded-md border transition-all ${
                      dataUploadMethod === 'text'
                        ? 'border-console-accent bg-console-accent/10 text-console-accent'
                        : 'border-console-border text-console-text-muted hover:border-console-accent/50'
                    }`}
                  >{t('tasks.modal.textInput')}</button>
                  <button
                    type="button"
                    onClick={() => setDataUploadMethod('file')}
                    className={`px-3 py-1 text-xs rounded-md border transition-all ${
                      dataUploadMethod === 'file'
                        ? 'border-console-accent bg-console-accent/10 text-console-accent'
                        : 'border-console-border text-console-text-muted hover:border-console-accent/50'
                    }`}
                  >{t('tasks.modal.fileUpload')}</button>
                </div>
                {dataUploadMethod === 'text' ? (
                  <textarea
                    value={inputContent}
                    onChange={(e) => setInputContent(e.target.value)}
                    placeholder={t('tasks.modal.inputDataPlaceholder')}
                    className="input font-mono text-sm h-24"
                  />
                ) : (
                  <div className="border-2 border-dashed border-console-border rounded-lg p-6 text-center">
                    <input
                      type="file"
                      accept=".csv,.json,.jsonl,.txt,.npy,.npz,.h5,.hdf5,.parquet,.pt,.pth,.pkl,.zip,.tar,.gz,.tsv,.xml,.yaml,.yml,.onnx,.safetensors,.bin,.arrow,.feather"
                      onChange={handleDataFileSelect}
                      className="hidden"
                      id="data-file-input"
                    />
                    <Upload size={24} className="mx-auto mb-2 text-console-text-muted" />
                    {dataFile ? (
                      <div className="text-console-accent">
                        <p className="font-medium">{dataFile.name}</p>
                        <p className="text-xs text-console-text-muted">
                          {dataFile.size > 1024 * 1024 * 1024
                            ? `${(dataFile.size / 1024 / 1024 / 1024).toFixed(2)} GB`
                            : dataFile.size > 1024 * 1024
                            ? `${(dataFile.size / 1024 / 1024).toFixed(1)} MB`
                            : `${(dataFile.size / 1024).toFixed(1)} KB`}
                          {dataFile.size > 50 * 1024 * 1024 && ` (${t('tasks.modal.willUseChunkedUpload')})`}
                        </p>
                      </div>
                    ) : (
                      <p className="text-console-text-muted text-sm">{t('tasks.modal.supportedDataFormats')}</p>
                    )}
                    <label htmlFor="data-file-input" className="btn-secondary mt-3 cursor-pointer inline-block text-sm">
                      {dataFile ? t('tasks.modal.changeFile') : t('tasks.modal.selectDataFile')}
                    </label>
                  </div>
                )}
              </div>

              {/* Python 依赖 */}
              <div>
                <label className="block text-sm font-medium text-console-text mb-2">
                  <span className="flex items-center gap-1">
                    <Package size={14} />
                    {t('tasks.modal.pythonDeps')} <span className="text-console-text-muted">{t('tasks.modal.pythonDepsHint')}</span>
                  </span>
                </label>
                <textarea
                  value={requirementsContent}
                  onChange={(e) => setRequirementsContent(e.target.value)}
                  placeholder={t('tasks.modal.requirementsPlaceholder')}
                  className="input font-mono text-sm h-28"
                />
                <p className="text-xs text-console-text-muted mt-1">
                  {t('tasks.modal.depsInstallHint')}
                </p>
              </div>

              {/* 加密状态提�?*/}
              {formData.enableEncryption && (
                <div className="bg-green-900/30 border border-green-700 rounded-lg p-3 flex items-center gap-2">
                  <Shield size={18} className="text-green-400" />
                  <span className="text-green-300 text-sm">
                    {t('tasks.modal.encryptionNote')}
                  </span>
                </div>
              )}

              {/* 大文件上传进�?*/}
              {uploadProgress && (
                <div className="rounded-lg p-3 bg-blue-900/30 border border-blue-700">
                  <p className="text-sm text-blue-300 mb-1">
                    {uploadProgress.phase === 'hashing' && t('tasks.modal.hashingFile')}
                    {uploadProgress.phase === 'uploading' && `${t('tasks.modal.uploadingFile')} ${uploadProgress.percent}%`}
                    {uploadProgress.phase === 'finalizing' && t('tasks.modal.verifyingFile')}
                    {uploadProgress.phase === 'done' && t('tasks.modal.uploadComplete')}
                  </p>
                  <div className="w-full bg-blue-900/50 rounded-full h-2">
                    <div
                      className="bg-blue-400 h-2 rounded-full transition-all"
                      style={{ width: `${uploadProgress.percent}%` }}
                    />
                  </div>
                  <p className="text-xs text-blue-400 mt-1">
                    {(uploadProgress.uploadedBytes / 1024 / 1024).toFixed(1)} / {(uploadProgress.totalBytes / 1024 / 1024).toFixed(1)} MB
                  </p>
                </div>
              )}

              {/* 提交结果反馈 */}
              {submitResult && (
                <div className={`rounded-lg p-3 ${
                  submitResult.success 
                    ? 'bg-green-900/30 border border-green-700 text-green-300' 
                    : 'bg-red-900/30 border border-red-700 text-red-300'
                }`}>
                  <p className="font-medium">{submitResult.success ? t('tasks.modal.submitSuccess') : t('tasks.modal.submitFailed')}</p>
                  <p className="text-sm mt-1">{submitResult.message}</p>
                  {submitResult.taskId && (
                    <p className="text-xs mt-1 text-console-text-muted">任务ID: {submitResult.taskId}</p>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="modal-footer">
          {validationError && (
            <div className="text-red-400 text-sm mr-auto flex items-center gap-1">
              <AlertTriangle size={14} />
              {validationError}
            </div>
          )}
          <button onClick={() => onClose()} className="btn-secondary" disabled={submitting}>{t('common.cancel')}</button>
          <div className="flex gap-2">
            {step > 1 && (
              <button onClick={() => setStep(step - 1)} className="btn-secondary" disabled={submitting}>{t('tasks.modal.prevStep')}</button>
            )}
            {step < 3 ? (
              <button
                onClick={() => {
                  if (step === 1 && !formData.title.trim()) {
                    setValidationError(t('tasks.modal.pleaseEnterTitle'))
                    return
                  }
                  setValidationError('')
                  setStep(step + 1)
                }}
                className="btn-primary"
              >{t('tasks.modal.nextStep')}</button>
            ) : (
              <button 
                onClick={handleSubmit} 
                className="btn-primary flex items-center gap-2"
                disabled={submitting}
              >
                {submitting ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    {formData.enableEncryption ? t('tasks.modal.encryptedSubmitting') : t('tasks.modal.submitting')}
                  </>
                ) : (
                  <>
                    {formData.enableEncryption && <Lock size={16} />}
                    {formData.enableEncryption ? t('tasks.modal.encryptedSubmit') : t('tasks.modal.submitTask')}
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

