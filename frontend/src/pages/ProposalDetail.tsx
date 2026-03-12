import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { 
  ArrowLeft, Clock, Users, ThumbsUp, ThumbsDown, 
  Minus, AlertTriangle, ExternalLink, Copy, Loader2
} from 'lucide-react'
import clsx from 'clsx'
import { governanceApi, type Proposal } from '../api'
import { useTranslation } from '../i18n'

interface ProposalVote {
  address: string
  vote: 'for' | 'against' | 'abstain'
  power: number
  timestamp: number
}

interface ProposalDetailData extends Proposal {
  detail?: string
  votes?: ProposalVote[]
}

// 空提案（加载失败时显示）
const emptyProposal: ProposalDetailData = {
  proposalId: '',
  title: '提案不存在',
  description: '未找到该提案',
  proposerId: '',
  category: 'parameter',
  status: 'draft',
  votesFor: 0,
  votesAgainst: 0,
  votesAbstain: 0,
  quorum: 1,
  threshold: 0.5,
  votingEndsAt: new Date().toISOString(),
  votingStartsAt: new Date().toISOString(),
  createdAt: new Date().toISOString(),
  detail: '',
  votes: [],
}

const typeLabels: Record<string, { label: string; className: string }> = {
  parameter: { label: 'proposalDetail.typeParameter', className: 'badge-info' },
  funding: { label: 'proposalDetail.typeFunding', className: 'badge-success' },
  protocol: { label: 'proposalDetail.typeProtocol', className: 'badge-warning' },
  emergency: { label: 'proposalDetail.typeEmergency', className: 'badge-error' },
}

export default function ProposalDetail() {
  const { t } = useTranslation()
  const { proposalId: id } = useParams()
  const [loading, setLoading] = useState(true)
  const [proposal, setProposal] = useState<ProposalDetailData>(emptyProposal)
  const [selectedVote, setSelectedVote] = useState<'for' | 'against' | 'abstain' | null>(null)
  const [showVoteModal, setShowVoteModal] = useState(false)

  // 从 API 获取提案详情
  useEffect(() => {
    const fetchProposal = async () => {
      if (!id) return
      setLoading(true)
      try {
        const data = await governanceApi.getProposal(id)
        if (data) {
          setProposal({
            ...data,
            detail: (data as ProposalDetailData).detail || data.description,
            votes: (data as ProposalDetailData).votes || [],
          })
        }
      } catch (err) {
        console.error('获取提案详情失败:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchProposal()
  }, [id])

  const rawTotalVotes = proposal.votesFor + proposal.votesAgainst + proposal.votesAbstain
  const totalVotes = rawTotalVotes
  const safeDivisor = rawTotalVotes || 1
  const forPercentage = (proposal.votesFor / safeDivisor * 100)
  const againstPercentage = (proposal.votesAgainst / safeDivisor * 100)
  const abstainPercentage = (proposal.votesAbstain / safeDivisor * 100)
  const quorumPercentage = Math.min(100, (rawTotalVotes / (proposal.quorum || 1) * 100))
  const isQuorumMet = rawTotalVotes >= proposal.quorum

  const endTime = new Date(proposal.votingEndsAt).getTime()
  const timeRemaining = Math.max(0, endTime - Date.now())
  const daysRemaining = Math.floor(timeRemaining / (24 * 60 * 60 * 1000))
  const hoursRemaining = Math.floor((timeRemaining % (24 * 60 * 60 * 1000)) / (60 * 60 * 1000))

  const handleVote = (vote: 'for' | 'against' | 'abstain') => {
    setSelectedVote(vote)
    setShowVoteModal(true)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-console-accent" />
        <span className="ml-3 text-console-muted">{t('common.loading')}</span>
      </div>
    )
  }

  if (!proposal.proposalId) {
    return (
      <div className="space-y-6">
        <Link to="/governance" className="inline-flex items-center gap-2 text-console-muted hover:text-console-text transition-colors">
          <ArrowLeft size={18} />
          {t('proposalDetail.backToList')}
        </Link>
        <div className="card text-center py-12">
          <AlertTriangle className="w-12 h-12 text-yellow-500 mx-auto mb-4" />
          <p className="text-console-muted">{t('proposalDetail.notFound')}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 返回链接 */}
      <Link to="/governance" className="inline-flex items-center gap-2 text-console-muted hover:text-console-text transition-colors">
        <ArrowLeft size={18} />
        {t('proposalDetail.backToList')}
      </Link>

      {/* 提案头部 */}
      <div className="card">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-2">
            <span className={clsx('badge', typeLabels[proposal.category]?.className || 'badge-info')}>
              {t(typeLabels[proposal.category]?.label || 'proposalDetail.typeParameter') || proposal.category}
            </span>
            <span className="flex items-center gap-1 text-blue-400">
              <Clock size={14} />
              <span className="text-sm">{proposal.status === 'voting' ? t('proposalDetail.voting') : proposal.status}</span>
            </span>
          </div>
          <span className="text-xs text-console-muted">{t('proposalDetail.id')}{id}</span>
        </div>

        <h1 className="text-2xl font-bold text-console-text mb-3">{proposal.title}</h1>
        <p className="text-console-muted mb-4">{proposal.description}</p>

        <div className="flex flex-wrap items-center gap-4 text-sm">
          <div className="flex items-center gap-2">
            <span className="text-console-muted">{t('proposalDetail.proposer')}</span>
            <button className="flex items-center gap-1 text-console-accent hover:underline">
              <span>{proposal.proposerId.slice(0, 10)}...{proposal.proposerId.slice(-8)}</span>
              <Copy size={12} />
            </button>
          </div>
          <div className="flex items-center gap-1 text-yellow-400">
            <Clock size={14} />
            {t('proposalDetail.remaining')} {daysRemaining}{t('proposalDetail.days')} {hoursRemaining}{t('proposalDetail.hours')}
          </div>
          <div className="flex items-center gap-1 text-console-muted">
            <Users size={14} />
            {proposal.votes?.length || 0} {t('proposalDetail.voters')}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧内容 */}
        <div className="lg:col-span-2 space-y-6">
          {/* 提案详情 */}
          <div className="card">
            <h2 className="text-lg font-semibold text-console-text mb-4">{t('proposalDetail.proposalDetails')}</h2>
            <div className="prose prose-invert prose-sm max-w-none">
              {/* 简单渲染 Markdown 内容 */}
              <div className="text-console-text whitespace-pre-wrap">
                {proposal.detail}
              </div>
            </div>
          </div>

          {/* 投票记录 */}
          <div className="card">
            <h2 className="text-lg font-semibold text-console-text mb-4">{t('proposalDetail.voteRecord')}</h2>
            <div className="space-y-3">
              {(proposal.votes || []).map((vote, index) => (
                <div key={index} className="flex items-center justify-between p-3 rounded-lg bg-console-card">
                  <div className="flex items-center gap-3">
                    <div className={clsx(
                      'w-8 h-8 rounded-full flex items-center justify-center',
                      vote.vote === 'for' && 'bg-green-500/20 text-green-400',
                      vote.vote === 'against' && 'bg-red-500/20 text-red-400',
                      vote.vote === 'abstain' && 'bg-gray-500/20 text-console-muted',
                    )}>
                      {vote.vote === 'for' && <ThumbsUp size={14} />}
                      {vote.vote === 'against' && <ThumbsDown size={14} />}
                      {vote.vote === 'abstain' && <Minus size={14} />}
                    </div>
                    <div>
                      <p className="text-console-text font-medium">{vote.address}</p>
                      <p className="text-xs text-console-muted">
                        {new Date(vote.timestamp).toLocaleString()}
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-console-text font-semibold">{vote.power.toLocaleString()}</p>
                    <p className="text-xs text-console-muted">{t('proposalDetail.votePower')}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* 右侧投票面板 */}
        <div className="space-y-6">
          {/* 投票进度 */}
          <div className="card">
            <h2 className="text-lg font-semibold text-console-text mb-4">{t('proposalDetail.voteResult')}</h2>

            {/* 赞成 */}
            <div className="mb-4">
              <div className="flex justify-between text-sm mb-1">
                <span className="flex items-center gap-1 text-green-400">
                  <ThumbsUp size={14} />
                  {t('proposalDetail.approve')}
                </span>
                <span className="text-console-text">{forPercentage.toFixed(1)}%</span>
              </div>
              <div className="h-3 rounded-full bg-console-hover overflow-hidden">
                <div 
                  className="bg-green-500 h-full rounded-full"
                  style={{ width: `${forPercentage}%` }}
                />
              </div>
              <p className="text-xs text-console-muted mt-1">{proposal.votesFor.toLocaleString()} {t('proposalDetail.votes')}</p>
            </div>

            {/* 反对 */}
            <div className="mb-4">
              <div className="flex justify-between text-sm mb-1">
                <span className="flex items-center gap-1 text-red-400">
                  <ThumbsDown size={14} />
                  {t('proposalDetail.reject')}
                </span>
                <span className="text-console-text">{againstPercentage.toFixed(1)}%</span>
              </div>
              <div className="h-3 rounded-full bg-console-hover overflow-hidden">
                <div 
                  className="bg-red-500 h-full rounded-full"
                  style={{ width: `${againstPercentage}%` }}
                />
              </div>
              <p className="text-xs text-console-muted mt-1">{proposal.votesAgainst.toLocaleString()} {t('proposalDetail.votes')}</p>
            </div>

            {/* 弃权 */}
            <div className="mb-6">
              <div className="flex justify-between text-sm mb-1">
                <span className="flex items-center gap-1 text-console-muted">
                  <Minus size={14} />
                  {t('proposalDetail.abstain')}
                </span>
                <span className="text-console-text">{abstainPercentage.toFixed(1)}%</span>
              </div>
              <div className="h-3 rounded-full bg-console-hover overflow-hidden">
                <div 
                  className="bg-gray-500 h-full rounded-full"
                  style={{ width: `${abstainPercentage}%` }}
                />
              </div>
              <p className="text-xs text-console-muted mt-1">{proposal.votesAbstain.toLocaleString()} {t('proposalDetail.votes')}</p>
            </div>

            {/* 法定人数 */}
            <div className="p-3 rounded-lg bg-console-card">
              <div className="flex justify-between text-sm mb-2">
                <span className="text-console-muted">{t('proposalDetail.quorumProgress')}</span>
                <span className={isQuorumMet ? 'text-green-400' : 'text-yellow-400'}>
                  {quorumPercentage.toFixed(1)}%
                </span>
              </div>
              <div className="h-2 rounded-full bg-console-hover overflow-hidden">
                <div 
                  className={clsx('h-full', isQuorumMet ? 'bg-green-500' : 'bg-yellow-500')}
                  style={{ width: `${quorumPercentage}%` }}
                />
              </div>
              <p className="text-xs text-console-muted mt-2">
                {totalVotes.toLocaleString()} / {proposal.quorum.toLocaleString()} 票
              </p>
            </div>
          </div>

          {/* 投票按钮 */}
          {proposal.status === 'voting' && (
            <div className="card">
              <h2 className="text-lg font-semibold text-console-text mb-4">{t('proposalDetail.vote')}</h2>
              <p className="text-sm text-console-muted mb-4">{t('proposalDetail.yourVotePower')}1,250</p>
              <div className="space-y-2">
                <button 
                  onClick={() => handleVote('for')}
                  className="w-full py-3 rounded-lg bg-green-500/10 border border-green-500/30 text-green-400 hover:bg-green-500/20 transition-colors flex items-center justify-center gap-2"
                >
                  <ThumbsUp size={18} />
                  {t('proposalDetail.approve')}
                </button>
                <button 
                  onClick={() => handleVote('against')}
                  className="w-full py-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 hover:bg-red-500/20 transition-colors flex items-center justify-center gap-2"
                >
                  <ThumbsDown size={18} />
                  {t('proposalDetail.reject')}
                </button>
                <button 
                  onClick={() => handleVote('abstain')}
                  className="w-full py-3 rounded-lg bg-gray-500/10 border border-gray-500/30 text-console-muted hover:bg-gray-500/20 transition-colors flex items-center justify-center gap-2"
                >
                  <Minus size={18} />
                  {t('proposalDetail.abstain')}
                </button>
              </div>
            </div>
          )}

          {/* 相关链接 */}
          <div className="card">
            <h2 className="text-lg font-semibold text-console-text mb-4">{t('proposalDetail.relatedLinks')}</h2>
            <div className="space-y-2">
              <a href="#" className="flex items-center gap-2 text-console-accent hover:underline text-sm">
                <ExternalLink size={14} />
                {t('proposalDetail.viewInExplorer')}
              </a>
              <a href="#" className="flex items-center gap-2 text-console-accent hover:underline text-sm">
                <ExternalLink size={14} />
                {t('proposalDetail.discussionForum')}
              </a>
            </div>
          </div>
        </div>
      </div>

      {/* 投票确认弹窗 */}
      {showVoteModal && selectedVote && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-console-bg border border-console-border rounded-xl p-6 w-full max-w-md">
            <h2 className="text-xl font-bold text-console-text mb-4">{t('proposalDetail.confirmVote')}</h2>
            
            <div className={clsx(
              'p-4 rounded-lg mb-4 flex items-center gap-3',
              selectedVote === 'for' && 'bg-green-500/10 border border-green-500/30',
              selectedVote === 'against' && 'bg-red-500/10 border border-red-500/30',
              selectedVote === 'abstain' && 'bg-gray-500/10 border border-gray-500/30',
            )}>
              <div className={clsx(
                'w-10 h-10 rounded-full flex items-center justify-center',
                selectedVote === 'for' && 'bg-green-500/20 text-green-400',
                selectedVote === 'against' && 'bg-red-500/20 text-red-400',
                selectedVote === 'abstain' && 'bg-gray-500/20 text-console-muted',
              )}>
                {selectedVote === 'for' && <ThumbsUp size={20} />}
                {selectedVote === 'against' && <ThumbsDown size={20} />}
                {selectedVote === 'abstain' && <Minus size={20} />}
              </div>
              <div>
                <p className="font-semibold text-console-text">
                  {selectedVote === 'for' && t('proposalDetail.approve')}
                  {selectedVote === 'against' && t('proposalDetail.reject')}
                  {selectedVote === 'abstain' && t('proposalDetail.abstain')}
                </p>
                <p className="text-sm text-console-muted">1,250 {t('proposalDetail.votePower')}</p>
              </div>
            </div>

            <div className="flex items-center gap-2 p-3 rounded-lg bg-yellow-400/10 border border-yellow-400/20 mb-6">
              <AlertTriangle size={18} className="text-yellow-400" />
              <p className="text-sm text-yellow-200">
                {t('proposalDetail.confirmVoteNote')}
              </p>
            </div>

            <div className="flex gap-3">
              <button 
                onClick={() => setShowVoteModal(false)} 
                className="btn-secondary flex-1"
              >
                {t('common.cancel')}
              </button>
              <button 
                onClick={async () => {
                  if (selectedVote && proposal.proposalId) {
                    try {
                      await governanceApi.vote(proposal.proposalId, selectedVote)
                      // 投票后刷新提案数据
                      if (id) {
                        const data = await governanceApi.getProposal(id)
                        if (data) {
                          setProposal({
                            ...data,
                            detail: (data as ProposalDetailData).detail || data.description,
                            votes: (data as ProposalDetailData).votes || [],
                          })
                        }
                      }
                    } catch (err) {
                      console.error('投票失败:', err)
                      alert(t('proposalDetail.voteFailed'))
                      return
                    }
                  }
                  setShowVoteModal(false)
                }} 
                className="btn-primary flex-1"
              >
                {t('proposalDetail.confirmVote')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
