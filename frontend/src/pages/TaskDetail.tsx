import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { 
  ChevronLeft,
  Play,
  Square,
  RefreshCw,
  Download,
  Folder,
  File,
  FileCode,
  Terminal,
  Cpu,
  Clock,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Copy,
  Check,
  ChevronRight,
  ChevronDown,
  Star,
  MemoryStick,
  FolderOpen
} from 'lucide-react'
import { taskApi, stakingApi, fileTransferApi, Task, TaskFileNode, TaskLogEntry, TaskOutputFile, TaskRuntimeStatus } from '../api'
import { useTranslation } from '../i18n'

export default function TaskDetail() {
  const { t } = useTranslation()
  const { taskId } = useParams<{ taskId: string }>()
  const [task, setTask] = useState<Task | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedFile, setSelectedFile] = useState<TaskFileNode | null>(null)
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set())
  const [activeTab, setActiveTab] = useState<'code' | 'logs' | 'output'>('code')
  const [copiedHash, setCopiedHash] = useState<string | null>(null)
  const [showRatingModal, setShowRatingModal] = useState(false)
  const logContainerRef = useRef<HTMLDivElement>(null)
  
  // 动态数据状态
  const [fileTree, setFileTree] = useState<TaskFileNode[]>([])
  const [logs, setLogs] = useState<TaskLogEntry[]>([])
  const [outputFiles, setOutputFiles] = useState<TaskOutputFile[]>([])
  const [runtimeStatus, setRuntimeStatus] = useState<TaskRuntimeStatus | null>(null)
  const [filesLoading, setFilesLoading] = useState(false)
  const [logsLoading, setLogsLoading] = useState(false)
  const [outputsLoading, setOutputsLoading] = useState(false)
  const [outputsError, setOutputsError] = useState<string>('')

  // 获取任务基本信息
  const fetchTask = useCallback(async () => {
    if (!taskId) return
    setLoading(true)
    try {
      const data = await taskApi.getTask(taskId)
      setTask(data)
    } catch (err) {
      console.error('获取任务信息失败:', err)
    } finally {
      setLoading(false)
    }
  }, [taskId])

  // 获取任务文件
  const fetchFiles = useCallback(async () => {
    if (!taskId) return
    setFilesLoading(true)
    try {
      const files = await taskApi.getTaskFiles(taskId)
      setFileTree(files)

      // 自动选择第一个文件，避免代码面板空白
      const pickFirstFile = (nodes: TaskFileNode[]): TaskFileNode | null => {
        for (const n of nodes) {
          if (n.type === 'file') return n
          if (n.type === 'folder' && n.children?.length) {
            const child = pickFirstFile(n.children)
            if (child) return child
          }
        }
        return null
      }
      setSelectedFile(pickFirstFile(files))

      // 自动展开第一层文件夹
      const folders = files.filter(f => f.type === 'folder').map(f => f.name)
      setExpandedFolders(new Set(folders))
    } catch (err) {
      console.error('获取任务文件失败:', err)
    } finally {
      setFilesLoading(false)
    }
  }, [taskId])

  // 获取任务日志
  const fetchLogs = useCallback(async () => {
    if (!taskId) return
    setLogsLoading(true)
    try {
      const logData = await taskApi.getTaskLogs(taskId)
      setLogs(logData)
    } catch (err) {
      console.error('获取任务日志失败:', err)
    } finally {
      setLogsLoading(false)
    }
  }, [taskId])

  // 获取输出文件
  const fetchOutputs = useCallback(async () => {
    if (!taskId) return
    setOutputsLoading(true)
    setOutputsError('')
    try {
      const outputs = await taskApi.getTaskOutputs(taskId)
      setOutputFiles(outputs)
    } catch (err) {
      console.error('获取输出文件失败:', err)
      const msg = err instanceof Error ? err.message : '获取输出失败'
      setOutputsError(msg)
      setOutputFiles([])
    } finally {
      setOutputsLoading(false)
    }
  }, [taskId])

  // 获取运行状态
  const fetchRuntimeStatus = useCallback(async () => {
    if (!taskId) return
    try {
      const status = await taskApi.getTaskRuntimeStatus(taskId)
      setRuntimeStatus(status)
    } catch (err) {
      console.error('获取运行状态失败:', err)
    }
  }, [taskId])

  // 初始加载
  useEffect(() => {
    fetchTask()
  }, [fetchTask])

  // 根据任务状态加载相关数据
  useEffect(() => {
    if (!task) return
    
    // 加载文件
    fetchFiles()
    
    // 根据状态加载日志和输出
    if (task.status === 'running' || task.status === 'completed' || task.status === 'failed') {
      fetchLogs()
    }
    
    if (task.status === 'completed') {
      fetchOutputs()
    }
  }, [task, fetchFiles, fetchLogs, fetchOutputs])

  // 运行中时定期刷新状态和日志
  useEffect(() => {
    if (task?.status === 'running') {
      // 立即获取一次
      fetchRuntimeStatus()
      fetchLogs()
      
      // 定期刷新
      const statusInterval = setInterval(fetchRuntimeStatus, 3000)
      const logsInterval = setInterval(fetchLogs, 5000)
      
      return () => {
        clearInterval(statusInterval)
        clearInterval(logsInterval)
      }
    }
  }, [task?.status, fetchRuntimeStatus, fetchLogs])

  // 自动滚动日志
  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight
    }
  }, [logs])

  const toggleFolder = (path: string) => {
    setExpandedFolders(prev => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  }

  const handleCopyHash = (hash: string) => {
    navigator.clipboard.writeText(hash)
    setCopiedHash(hash)
    setTimeout(() => setCopiedHash(null), 2000)
  }

  const triggerBlobDownload = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename || 'output.bin'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const handleDownloadOutput = async (file: TaskOutputFile) => {
    if (file.downloadUrl) {
      const a = document.createElement('a')
      a.href = file.downloadUrl
      a.target = '_blank'
      a.rel = 'noopener noreferrer'
      a.download = file.name || 'output.bin'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      return
    }

    if (typeof file.content === 'string' && file.content.length > 0) {
      const blob = new Blob([file.content], { type: 'application/json;charset=utf-8' })
      triggerBlobDownload(blob, file.name || 'output.json')
      return
    }

    if (taskId && file.name) {
      const blob = await fileTransferApi.downloadTaskOutput(taskId, file.name)
      if (blob) {
        triggerBlobDownload(blob, file.name)
        return
      }
    }

    alert('该输出文件暂不支持下载')
  }

  const renderFileTree = (nodes: TaskFileNode[], path = '') => {
    return nodes.map((node) => {
      const fullPath = path ? `${path}/${node.name}` : node.name
      const isExpanded = expandedFolders.has(fullPath)
      const isSelected = selectedFile?.name === node.name

      if (node.type === 'folder') {
        return (
          <div key={fullPath}>
            <div
              onClick={() => toggleFolder(fullPath)}
              className="file-tree-item"
            >
              {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              <Folder size={14} className="text-console-warning" />
              <span className="text-console-text">{node.name}</span>
            </div>
            {isExpanded && node.children && (
              <div className="ml-4">
                {renderFileTree(node.children, fullPath)}
              </div>
            )}
          </div>
        )
      }

      return (
        <div
          key={fullPath}
          onClick={() => setSelectedFile(node)}
          className={`file-tree-item ml-4 ${isSelected ? 'file-tree-item-active' : ''}`}
        >
          <FileCode size={14} className="text-console-accent" />
          <span>{node.name}</span>
        </div>
      )
    })
  }

  const getStatusInfo = () => {
    const statusMap: Record<string, { class: string; label: string; icon: React.ReactNode }> = {
      pending: { class: 'text-yellow-400', label: t('taskDetail.waitingOrder'), icon: <Clock size={18} /> },
      assigned: { class: 'text-blue-400', label: t('taskDetail.envInit'), icon: <Cpu size={18} /> },
      running: { class: 'text-blue-400', label: t('taskDetail.executing'), icon: <Play size={18} /> },
      completed: { class: 'text-green-400', label: t('taskDetail.completed'), icon: <CheckCircle size={18} /> },
      failed: { class: 'text-red-400', label: t('taskDetail.taskFailed'), icon: <XCircle size={18} /> },
      disputed: { class: 'text-red-400', label: t('taskDetail.dispute'), icon: <AlertTriangle size={18} /> },
    }
    return statusMap[task?.status || 'pending'] || statusMap.pending
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="animate-spin text-console-accent" size={32} />
      </div>
    )
  }

  const statusInfo = getStatusInfo()

  return (
    <div className="space-y-4 h-full flex flex-col">
      {/* 顶部导航 */}
      <div className="flex items-center justify-between shrink-0">
        <div className="flex items-center gap-4">
          <Link to="/tasks" className="btn-ghost p-2">
            <ChevronLeft size={18} />
          </Link>
          <div>
            <h1 className="text-xl font-bold text-console-text">{task?.title || t('taskDetail.title')}</h1>
            <div className="flex items-center gap-3 mt-1">
              <span className="font-mono text-sm text-console-text-muted">{taskId}</span>
              <span className={`flex items-center gap-1 text-sm ${statusInfo.class}`}>
                {statusInfo.icon}
                {statusInfo.label}
              </span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {task?.status === 'running' && (
            <>
              <button
                onClick={async () => {
                  if (taskId && confirm('确定要取消此任务吗？取消后将停止执行并退还剩余预算。')) {
                    try {
                      await taskApi.cancelTask(taskId)
                      fetchTask()
                    } catch (err) {
                      console.error('停止任务失败:', err)
                    }
                  }
                }}
                className="btn-danger flex items-center gap-2"
              >
                <Square size={14} />
                {t('taskDetail.cancelTask')}
              </button>
            </>
          )}
          {task?.status === 'completed' && (
            <button 
              onClick={() => setShowRatingModal(true)}
              className="btn-primary flex items-center gap-2"
            >
              <Star size={14} />
              {t('taskDetail.evaluate')}
            </button>
          )}
        </div>
      </div>

      {/* 资源监控条 */}
      <div className="card py-3 shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <Cpu size={16} className="text-console-text-muted" />
              <span className="text-sm text-console-text">{task?.gpuType || '--'} × {task?.gpuCount || '--'}</span>
            </div>
            {task?.status === 'running' && runtimeStatus ? (
              <>
                <div className="flex items-center gap-2">
                  <MemoryStick size={16} className="text-console-text-muted" />
                  <span className="text-sm text-console-text">{t('taskDetail.gpuUsage')} {runtimeStatus.gpuUtilization}%</span>
                  <div className="progress-bar w-24">
                    <div className="progress-fill-accent" style={{ width: `${runtimeStatus.gpuUtilization}%` }} />
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Clock size={16} className="text-console-text-muted" />
                  <span className="text-sm text-console-text">{t('taskDetail.runtime')} {runtimeStatus.runningTime}</span>
                </div>
              </>
            ) : task?.status === 'pending' ? (
              <span className="text-sm text-console-text-muted">{t('taskDetail.waitingAssign')}</span>
            ) : task?.status === 'completed' ? (
              <span className="text-sm text-green-400">{t('taskDetail.taskCompleted')}</span>
            ) : task?.status === 'failed' ? (
              <span className="text-sm text-red-400">{t('taskDetail.taskFailed')}</span>
            ) : null}
          </div>
          <div className="text-sm text-console-text-muted">
                        {t('taskDetail.progressLabel')} {runtimeStatus?.progress ?? task?.progress ?? 0}%
          </div>
        </div>
      </div>

      {/* VSCode 风格编辑器 */}
      <div className="editor-container flex-1 flex flex-col min-h-0">
        {/* 标签栏 */}
        <div className="editor-tabs shrink-0">
          <button
            onClick={() => setActiveTab('code')}
            className={`editor-tab ${activeTab === 'code' ? 'editor-tab-active' : ''}`}
          >
            <FileCode size={14} />
            {t('taskDetail.code')}
          </button>
          <button
            onClick={() => setActiveTab('logs')}
            className={`editor-tab ${activeTab === 'logs' ? 'editor-tab-active' : ''}`}
          >
            <Terminal size={14} />
            {t('taskDetail.executionLog')}
            {task?.status === 'running' && (
              <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            )}
          </button>
          <button
            onClick={() => setActiveTab('output')}
            className={`editor-tab ${activeTab === 'output' ? 'editor-tab-active' : ''}`}
          >
            <Download size={14} />
            {t('taskDetail.outputResult')}
          </button>
        </div>

        {/* 内容区 */}
        <div className="flex flex-1 min-h-0">
          {/* 代码视图 */}
          {activeTab === 'code' && (
            <>
              {/* 文件树 */}
              <div className="editor-sidebar shrink-0 overflow-y-auto">
                <div className="p-2 text-xs font-medium text-console-text-muted uppercase tracking-wider">
                  {t('taskDetail.files')}
                </div>
                <div className="file-tree p-2">
                  {filesLoading ? (
                    <div className="flex items-center justify-center py-4">
                      <RefreshCw size={16} className="animate-spin text-console-accent" />
                    </div>
                  ) : fileTree.length > 0 ? (
                    renderFileTree(fileTree)
                  ) : (
                    <div className="text-xs text-console-text-muted text-center py-4">
                      <FolderOpen size={20} className="mx-auto mb-2 opacity-50" />
                      暂无文件
                    </div>
                  )}
                </div>
              </div>
              
              {/* 代码预览 */}
              <div className="editor-main bg-console-bg p-4 overflow-auto">
                {selectedFile ? (
                  <pre className="text-sm font-mono text-console-text whitespace-pre-wrap">
                    <code>{selectedFile.content}</code>
                  </pre>
                ) : (
                  <div className="flex items-center justify-center h-full text-console-text-muted">
                    {fileTree.length > 0 ? '选择文件查看内容' : '该任务没有代码文件'}
                  </div>
                )}
              </div>
            </>
          )}

          {/* 日志视图 */}
          {activeTab === 'logs' && (
            <div className="flex-1 flex flex-col bg-black">
              <div className="terminal-header px-4 py-2 shrink-0">
                <div className="terminal-dot bg-red-500" />
                <div className="terminal-dot bg-yellow-500" />
                <div className="terminal-dot bg-green-500" />
                <span className="ml-4 text-xs text-console-text-muted">Terminal - {task?.gpuType || '--'}</span>
              </div>
              <div 
                ref={logContainerRef}
                className="flex-1 overflow-y-auto p-4 font-mono text-sm"
              >
                {logsLoading && logs.length === 0 ? (
                  <div className="flex items-center justify-center h-full">
                    <RefreshCw size={20} className="animate-spin text-console-accent" />
                  </div>
                ) : logs.length > 0 ? (
                  logs.map((log, i) => (
                    <div key={i} className={`log-line ${log.type === 'stderr' ? 'log-stderr' : 'log-stdout'}`}>
                      <span className="log-timestamp">[{log.timestamp}]</span>
                      {log.type === 'stderr' && <span className="text-red-400">[ERROR] </span>}
                      {log.type === 'system' && <span className="text-blue-400">[SYSTEM] </span>}
                      {log.message}
                    </div>
                  ))
                ) : task?.status === 'pending' ? (
                  <div className="flex flex-col items-center justify-center h-full text-console-text-muted">
                    <Clock size={24} className="mb-2 opacity-50" />
                    <p>{t('taskDetail.notStarted')}</p>
                    <p className="text-xs mt-1">{t('taskDetail.waitingMiner')}</p>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center h-full text-console-text-muted">
                    <Terminal size={24} className="mb-2 opacity-50" />
                    <p>{t('taskDetail.noLogs')}</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* 输出结果 */}
          {activeTab === 'output' && (
            <div className="flex-1 p-6 overflow-auto">
              {outputsLoading ? (
                <div className="flex items-center justify-center h-full">
                  <RefreshCw size={24} className="animate-spin text-console-accent" />
                </div>
              ) : task?.status === 'completed' ? (
                outputsError ? (
                  <div className="flex flex-col items-center justify-center h-full text-console-text-muted">
                    <AlertTriangle size={24} className="mb-2 text-yellow-400" />
                    <p>无法查看输出结果</p>
                    <p className="text-xs mt-1">{outputsError}</p>
                  </div>
                ) : (
                outputFiles.length > 0 ? (
                  <div className="space-y-4">
                    <h3 className="font-medium text-console-text">{t('taskDetail.outputFiles')}</h3>
                    <div className="space-y-2">
                      {outputFiles.map((file) => (
                        <div 
                          key={file.name}
                          className="flex items-center justify-between p-4 bg-console-surface rounded-lg border border-console-border"
                        >
                          <div className="flex items-center gap-3">
                            <File size={20} className="text-console-accent" />
                            <div>
                              <div className="font-medium text-console-text">{file.name}</div>
                              <div className="text-xs text-console-text-muted">
                                {file.size} · {t('taskDetail.hash')} {file.hash}
                              </div>
                              {file.name === 'result.json' && file.content && (
                                <pre className="mt-2 max-w-[640px] overflow-auto rounded bg-console-bg p-3 text-xs text-console-text-muted border border-console-border">
{file.content}
                                </pre>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <button 
                              onClick={() => handleCopyHash(file.hash)}
                              className="btn-ghost py-1 px-2"
                            >
                              {copiedHash === file.hash ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
                            </button>
                            <button 
                              className="btn-secondary py-1 px-3 flex items-center gap-1"
                              onClick={() => handleDownloadOutput(file)}
                            >
                              <Download size={14} />
                              下载
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center h-full text-console-text-muted">
                    <File size={32} className="mb-2 opacity-50" />
                    <p>{t('taskDetail.completedNoOutput')}</p>
                  </div>
                )
                )
              ) : (
                <div className="flex flex-col items-center justify-center h-full text-console-text-muted">
                  <Clock size={32} className="mb-2 opacity-50" />
                  <p>{t('taskDetail.viewOutputAfter')}</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 评价弹窗 */}
      {showRatingModal && (
        <RatingModal onClose={() => setShowRatingModal(false)} taskId={taskId || ''} />
      )}
    </div>
  )
}

// 评价弹窗
function RatingModal({ onClose, taskId }: { onClose: () => void; taskId: string }) {
  const [rating, setRating] = useState(5)
  const [stakeAmount, setStakeAmount] = useState(0.5)
  const [confirmed, setConfirmed] = useState(false)

  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState('')

  const handleSubmit = async () => {
    setSubmitting(true)
    setSubmitError('')
    try {
      if (stakeAmount > 0) {
        const stakeResult = await stakingApi.stake(stakeAmount, 'MAIN')
        if (!stakeResult.success) {
          setSubmitError(stakeResult.message || '质押失败')
          setSubmitting(false)
          return
        }
      }
      const acceptRes = await taskApi.acceptResult(taskId, rating)
      if (!acceptRes.success) {
        setSubmitError(acceptRes.message || '评价提交失败')
        setSubmitting(false)
        return
      }
      setSubmitting(false)
      onClose()
    } catch (err) {
      setSubmitError('评价提交失败: ' + String(err))
      setSubmitting(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal max-w-md" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="text-lg font-semibold">评价任务执行</h3>
        </div>

        <div className="modal-body space-y-4">
          {/* 评分 */}
          <div>
            <label className="block text-sm font-medium text-console-text mb-2">评分</label>
            <div className="flex items-center gap-2">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  onClick={() => setRating(star)}
                  className="p-1"
                >
                  <Star
                    size={28}
                    className={star <= rating ? 'text-yellow-400 fill-yellow-400' : 'text-console-border'}
                  />
                </button>
              ))}
              <span className="ml-2 text-console-text">{rating} 星</span>
            </div>
          </div>

          {/* 质押金额 */}
          <div>
            <label className="block text-sm font-medium text-console-text mb-2">
              质押金额 (可选)
            </label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                value={stakeAmount}
                onChange={(e) => setStakeAmount(Number(e.target.value))}
                min="0"
                step="0.1"
                className="input"
              />
              <span className="text-console-text-muted">MAIN</span>
            </div>
            <p className="text-xs text-console-text-muted mt-2">
              质押金将被销毁，质押越多评分权重越高
            </p>
          </div>

          {/* 警告 */}
          <div className="alert alert-warning">
            <AlertTriangle size={16} className="shrink-0" />
            <span className="text-sm">质押金一旦提交将被永久销毁，不可退还</span>
          </div>

          {/* 错误提示 */}
          {submitError && (
            <div className="alert alert-error text-sm">
              <AlertTriangle size={16} className="shrink-0" />
              {submitError}
            </div>
          )}

          {/* 确认 */}
          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
              className="mt-1"
            />
            <span className="text-sm text-console-text">
              我已了解质押金将被销毁，确认提交评价
            </span>
          </label>
        </div>

        <div className="modal-footer">
          <button onClick={onClose} className="btn-secondary">取消</button>
          <button 
            onClick={handleSubmit}
            disabled={!confirmed || submitting}
            className="btn-primary disabled:opacity-50"
          >
            {submitting ? '提交中...' : '提交评价'}
          </button>
        </div>
      </div>
    </div>
  )
}
