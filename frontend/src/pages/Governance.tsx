import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { 
  Search, Plus, Vote, Clock, CheckCircle, XCircle, AlertTriangle,
  TrendingUp, Users, FileText, RefreshCw
} from 'lucide-react'
import clsx from 'clsx'
import { useTranslation } from '../i18n'
import { governanceApi, type Proposal } from '../api'

interface ProposalData {
  id: string
  title: string
  description: string
  proposer: string
  type: string
  status: string
  forVotes: number
  againstVotes: number
  abstainVotes: number
  totalVotes: number
  quorum: number
  endTime: number
  createdAt: number
}

const proposalTypes = [
  { value: 'all', label: 'governance.allTypes' },
  { value: 'parameter', label: 'governance.paramAdjust' },
  { value: 'feature', label: 'governance.featureProposal' },
  { value: 'governance', label: 'governance.govImprove' },
  { value: 'treasury', label: 'governance.financeProposal' },
  { value: 'emergency', label: 'governance.urgentProposal' },
]

const proposalStatuses = [
  { value: 'all', label: 'governance.allStatus' },
  { value: 'active', label: 'governance.voting' },
  { value: 'passed', label: 'governance.passed' },
  { value: 'rejected', label: 'governance.rejected' },
  { value: 'executed', label: 'governance.executed' },
]

const typeLabels: Record<string, { label: string; className: string }> = {
  parameter: { label: 'governance.paramAdjust', className: 'badge-info' },
  funding: { label: 'governance.fundProposal', className: 'badge-success' },
  protocol: { label: 'governance.protocolUpgrade', className: 'badge-warning' },
  emergency: { label: 'governance.urgentProposal', className: 'badge-error' },
}

const statusIcons: Record<string, { icon: React.ReactNode; className: string }> = {
  active: { icon: <Clock size={14} />, className: 'text-blue-400' },
  passed: { icon: <CheckCircle size={14} />, className: 'text-green-400' },
  rejected: { icon: <XCircle size={14} />, className: 'text-red-400' },
  executed: { icon: <CheckCircle size={14} />, className: 'text-purple-400' },
}

export default function Governance() {
  const [proposals, setProposals] = useState<ProposalData[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [showCreateModal, setShowCreateModal] = useState(false)
  const { t } = useTranslation()

  // 获取提案数据
  const fetchProposals = async () => {
    setLoading(true)
    try {
      const result = await governanceApi.getProposals()
      // 转换 API 返回的数据格式
      const formattedProposals: ProposalData[] = result.proposals.map((p: Proposal) => ({
        id: p.proposalId,
        title: p.title,
        description: p.description,
        proposer: p.proposerId || '0x...',
        type: p.category || 'feature',
        status: p.status === 'voting' ? 'active' : p.status,
        forVotes: p.votesFor || 0,
        againstVotes: p.votesAgainst || 0,
        abstainVotes: p.votesAbstain || 0,
        totalVotes: (p.votesFor || 0) + (p.votesAgainst || 0) + (p.votesAbstain || 0),
        quorum: p.quorum || 25000,
        endTime: new Date(p.votingEndsAt).getTime(),
        createdAt: new Date(p.createdAt).getTime(),
      }))
      setProposals(formattedProposals)
    } catch (err) {
      console.error('获取提案失败:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchProposals()
  }, [])

  const filteredProposals = proposals.filter(proposal => {
    const matchesSearch = proposal.title.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesType = typeFilter === 'all' || proposal.type === typeFilter
    const matchesStatus = statusFilter === 'all' || proposal.status === statusFilter
    return matchesSearch && matchesType && matchesStatus
  })

  const activeProposals = proposals.filter(p => p.status === 'active' || p.status === 'voting')
  const totalVotingPower = proposals.reduce((sum, p) => sum + p.totalVotes, 0)
  const passedCount = proposals.filter(p => p.status === 'passed' || p.status === 'executed').length
  const passRate = proposals.length > 0 ? Math.round((passedCount / proposals.length) * 100) : 0

  return (
    <div className="space-y-6">
      {/* 统计卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard icon={<Vote />} label={t('governance.activeProposals')} value={activeProposals.length.toString()} />
        <StatCard icon={<FileText />} label={t('governance.totalProposals')} value={proposals.length.toString()} />
        <StatCard icon={<Users />} label={t('governance.participated')} value={(totalVotingPower / 1000).toFixed(0) + 'K'} />
        <StatCard icon={<TrendingUp />} label={t('governance.passRate')} value={passRate + '%'} />
      </div>

      {/* 操作栏 */}
      <div className="card">
        <div className="flex flex-col md:flex-row gap-4 items-start md:items-center justify-between">
          <div className="flex flex-col md:flex-row gap-4 flex-1">
            {/* 搜索 */}
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-console-muted" size={18} />
              <input
                type="text"
                placeholder={t('governance.searchPlaceholder')}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="input pl-10"
              />
            </div>

            {/* 类型筛选 */}
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="input w-auto"
            >
              {proposalTypes.map(type => (
                <option key={type.value} value={type.value}>{t(type.label)}</option>
              ))}
            </select>

            {/* 状态筛选 */}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="input w-auto"
            >
              {proposalStatuses.map(status => (
                <option key={status.value} value={status.value}>{t(status.label)}</option>
              ))}
            </select>
          </div>

          <div className="flex gap-2">
            <button 
              onClick={fetchProposals}
              className="btn-ghost flex items-center gap-2"
              disabled={loading}
            >
              <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
              {t('common.refresh')}
            </button>
            <button 
              className="btn-primary flex items-center gap-2"
              onClick={() => setShowCreateModal(true)}
            >
              <Plus size={18} />
              {t('governance.createProposal')}
            </button>
          </div>
        </div>
      </div>

      {/* 提案列表 */}
      <div className="space-y-4">
        {loading ? (
          <div className="text-center py-8 text-console-muted">
            <RefreshCw className="animate-spin mx-auto mb-2" />
            {t('common.loading')}
          </div>
        ) : filteredProposals.length > 0 ? (
          filteredProposals.map(proposal => (
            <ProposalCard key={proposal.id} proposal={proposal} />
          ))
        ) : (
          <div className="text-center py-8 text-console-muted">
            {t('governance.noProposals')}
          </div>
        )}
      </div>

      {/* 创建提案弹窗 */}
      {showCreateModal && (
        <CreateProposalModal onClose={() => {
          setShowCreateModal(false)
          fetchProposals()
        }} />
      )}
    </div>
  )
}

// 统计卡片
function StatCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="card flex items-center gap-4">
      <div className="p-3 rounded-lg bg-console-hover text-console-accent">
        {icon}
      </div>
      <div>
        <p className="text-sm text-console-muted">{label}</p>
        <p className="text-xl font-bold text-console-text">{value}</p>
      </div>
    </div>
  )
}

// 提案卡片
function ProposalCard({ proposal }: { proposal: ProposalData }) {
  const { t } = useTranslation()
  const forPercentage = proposal.totalVotes > 0 ? (proposal.forVotes / proposal.totalVotes * 100).toFixed(1) : '0.0'
  const againstPercentage = proposal.totalVotes > 0 ? (proposal.againstVotes / proposal.totalVotes * 100).toFixed(1) : '0.0'
  const quorumPercentage = proposal.quorum > 0 ? Math.min(100, (proposal.totalVotes / proposal.quorum * 100)) : 0
  const isQuorumMet = proposal.totalVotes >= proposal.quorum
  const timeRemaining = proposal.status === 'active' 
    ? Math.max(0, proposal.endTime - Date.now())
    : 0
  const daysRemaining = Math.floor(timeRemaining / (24 * 60 * 60 * 1000))
  const hoursRemaining = Math.floor((timeRemaining % (24 * 60 * 60 * 1000)) / (60 * 60 * 1000))

  return (
    <Link to={`/governance/${proposal.id}`} className="block">
      <div className="card card-hover">
        <div className="flex flex-col md:flex-row gap-4">
          {/* 左侧信息 */}
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <span className={clsx('badge', typeLabels[proposal.type]?.className || 'badge-info')}>
                {t(typeLabels[proposal.type]?.label || proposal.type)}
              </span>
              <span className={clsx('flex items-center gap-1', statusIcons[proposal.status]?.className || 'text-gray-400')}>
                {statusIcons[proposal.status]?.icon}
                <span className="text-sm">
                  {proposal.status === 'active' && t('governance.voting')}
                  {proposal.status === 'passed' && t('governance.passed')}
                  {proposal.status === 'rejected' && t('governance.rejected')}
                  {proposal.status === 'executed' && t('governance.executed')}
                </span>
              </span>
            </div>

            <h3 className="text-lg font-semibold text-console-text mb-2">{proposal.title}</h3>
            <p className="text-console-muted text-sm mb-3 line-clamp-2">{proposal.description}</p>

            <div className="flex items-center gap-4 text-sm text-console-muted">
              <span>{t('governance.proposer')}{proposal.proposer}</span>
              {proposal.status === 'active' && (
                <span className="flex items-center gap-1 text-yellow-400">
                  <Clock size={14} />
                  {t('governance.remaining')} {daysRemaining}{t('common.days')} {hoursRemaining}{t('common.hours')}
                </span>
              )}
            </div>
          </div>

          {/* 右侧投票进度 */}
          <div className="md:w-72 space-y-3">
            {/* 投票结果 */}
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-green-400">{t('governance.approve')} {forPercentage}%</span>
                <span className="text-red-400">{t('governance.reject')} {againstPercentage}%</span>
              </div>
              <div className="h-2 rounded-full bg-console-hover overflow-hidden flex">
                <div 
                  className="bg-green-500 h-full"
                  style={{ width: `${forPercentage}%` }}
                />
                <div 
                  className="bg-red-500 h-full"
                  style={{ width: `${againstPercentage}%` }}
                />
              </div>
            </div>

            {/* 法定人数 */}
            <div className="space-y-1">
              <div className="flex justify-between text-sm">
                <span className="text-console-muted">{t('governance.quorum')}</span>
                <span className={isQuorumMet ? 'text-green-400' : 'text-yellow-400'}>
                  {(proposal.totalVotes / 1000).toFixed(0)}K / {(proposal.quorum / 1000).toFixed(0)}K
                </span>
              </div>
              <div className="h-1.5 rounded-full bg-console-hover overflow-hidden">
                <div 
                  className={clsx('h-full', isQuorumMet ? 'bg-green-500' : 'bg-yellow-500')}
                  style={{ width: `${quorumPercentage}%` }}
                />
              </div>
            </div>

            {proposal.status === 'active' && (
              <button className="btn-primary w-full text-sm py-1.5">
                {t('governance.voteNow')}
              </button>
            )}
          </div>
        </div>
      </div>
    </Link>
  )
}

// 创建提案弹窗
function CreateProposalModal({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation()
  const [formData, setFormData] = useState({
    title: '',
    type: 'parameter',
    description: '',
    detail: '',
  })

  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setSubmitError('')
    try {
      const result = await governanceApi.createProposal({
        title: formData.title,
        description: formData.description || formData.detail,
        category: formData.type as 'parameter' | 'funding' | 'protocol' | 'emergency',
      })
      if (result.success) {
        onClose()
      } else {
        setSubmitError(result.message || t('governance.submitFailed'))
      }
    } catch (err) {
      setSubmitError(t('governance.submitFailed') + ': ' + String(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-console-bg border border-console-border rounded-xl p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <h2 className="text-xl font-bold text-console-text mb-6">{t('governance.createNewProposal')}</h2>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-console-muted mb-1">{t('governance.proposalTitle')}</label>
            <input
              type="text"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              className="input"
              placeholder={t('governance.proposalTitleHint')}
              required
            />
          </div>

          <div>
            <label className="block text-sm text-console-muted mb-1">{t('governance.proposalType')}</label>
            <select
              value={formData.type}
              onChange={(e) => setFormData({ ...formData, type: e.target.value })}
              className="input"
            >
              <option value="parameter">{t('governance.paramAdjust')}</option>
              <option value="funding">{t('governance.fundProposal')}</option>
              <option value="protocol">{t('governance.protocolUpgrade')}</option>
              <option value="emergency">{t('governance.urgentProposal')}</option>
            </select>
          </div>

          <div>
            <label className="block text-sm text-console-muted mb-1">{t('governance.proposalSummary')}</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              className="input min-h-24"
              placeholder={t('governance.proposalSummaryHint')}
              required
            />
          </div>

          <div>
            <label className="block text-sm text-console-muted mb-1">{t('governance.proposalDetail')}</label>
            <textarea
              value={formData.detail}
              onChange={(e) => setFormData({ ...formData, detail: e.target.value })}
              className="input min-h-48"
              placeholder={t('governance.proposalDetailHint')}
              required
            />
          </div>

          <div className="flex items-center gap-2 p-3 rounded-lg bg-yellow-400/10 border border-yellow-400/20">
            <AlertTriangle size={18} className="text-yellow-400" />
            <p className="text-sm text-yellow-200">
              {t('governance.bondNote')}
            </p>
          </div>

          {submitError && (
            <div className="flex items-center gap-2 p-3 rounded-lg bg-red-400/10 border border-red-400/20">
              <AlertTriangle size={18} className="text-red-400" />
              <p className="text-sm text-red-200">{submitError}</p>
            </div>
          )}

          <div className="flex gap-3">
            <button type="button" onClick={onClose} className="btn-secondary flex-1">
              {t('common.cancel')}
            </button>
            <button type="submit" disabled={submitting} className="btn-primary flex-1">
              {submitting ? t('governance.submitting') : t('governance.submitProposal')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
