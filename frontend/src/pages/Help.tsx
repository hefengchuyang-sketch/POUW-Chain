import { Link } from 'react-router-dom'
import { 
  HelpCircle, 
  Book, 
  MessageCircle, 
  ChevronRight,
  Server,
  Cpu,
  Wallet,
  Shield,
  Zap,
  Code
} from 'lucide-react'
import { useTranslation } from '../i18n'

export default function Help() {
  const { t } = useTranslation()

  const faqItems = [
    { question: t('help.faqHowToStart'), answer: t('help.faqHowToStartAnswer') },
    { question: t('help.faqSectorCoin'), answer: t('help.faqSectorCoinAnswer') },
    { question: t('help.faqCodeSecurity'), answer: t('help.faqCodeSecurityAnswer') },
    { question: t('help.faqEvaluate'), answer: t('help.faqEvaluateAnswer') },
    { question: t('help.faqFuse'), answer: t('help.faqFuseAnswer') },
    { question: t('help.faqTax'), answer: t('help.faqTaxAnswer') },
  ]

  const guideItems = [
    {
      icon: <Wallet className="text-console-accent" size={24} />,
      title: t('help.walletGuide'),
      description: t('help.walletGuideDesc'),
      link: '/connect'
    },
    {
      icon: <Cpu className="text-console-primary" size={24} />,
      title: t('help.marketGuide'),
      description: t('help.marketGuideDesc'),
      link: '/market'
    },
    {
      icon: <Code className="text-purple-400" size={24} />,
      title: t('help.taskGuide'),
      description: t('help.taskGuideDesc'),
      link: '/tasks'
    },
    {
      icon: <Shield className="text-console-warning" size={24} />,
      title: t('help.securityGuide'),
      description: t('help.securityGuideDesc'),
      link: '/privacy'
    },
  ]

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* 标题 */}
      <div className="text-center">
        <h1 className="text-2xl font-bold text-console-text">{t('help.title')}</h1>
        <p className="text-console-text-muted mt-2">
          {t('help.subtitle')}
        </p>
      </div>

      {/* 快速入门 */}
      <div className="card">
        <h2 className="text-lg font-semibold text-console-text mb-4 flex items-center gap-2">
          <Zap size={20} className="text-console-warning" />
          {t('help.quickStart')}
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {guideItems.map((item, index) => (
            <Link
              key={index}
              to={item.link}
              className="flex items-start gap-4 p-4 rounded-lg border border-console-border hover:border-console-accent/50 hover:bg-console-accent/5 transition-all"
            >
              <div className="p-2 rounded-lg bg-console-bg">
                {item.icon}
              </div>
              <div className="flex-1">
                <div className="font-medium text-console-text">{item.title}</div>
                <div className="text-sm text-console-text-muted mt-1">{item.description}</div>
              </div>
              <ChevronRight size={18} className="text-console-text-muted mt-1" />
            </Link>
          ))}
        </div>
      </div>

      {/* 常见问题 */}
      <div className="card">
        <h2 className="text-lg font-semibold text-console-text mb-4 flex items-center gap-2">
          <HelpCircle size={20} className="text-console-accent" />
          {t('help.faq')}
        </h2>
        <div className="divide-y divide-console-border">
          {faqItems.map((item, index) => (
            <details key={index} className="group">
              <summary className="flex items-center justify-between py-4 cursor-pointer list-none">
                <span className="font-medium text-console-text">{item.question}</span>
                <ChevronRight size={18} className="text-console-text-muted transition-transform group-open:rotate-90" />
              </summary>
              <div className="pb-4 text-console-text-muted text-sm">
                {item.answer}
              </div>
            </details>
          ))}
        </div>
      </div>

      {/* 资源链接 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Link
          to="/explorer"
          className="card card-hover flex items-center gap-4"
        >
          <div className="p-3 rounded-lg bg-console-accent/10">
            <Book size={24} className="text-console-accent" />
          </div>
          <div className="flex-1">
            <div className="font-medium text-console-text">{t('help.explorerLink')}</div>
            <div className="text-sm text-console-text-muted">{t('help.explorerLinkDesc')}</div>
          </div>
          <ChevronRight size={16} className="text-console-text-muted" />
        </Link>

        <Link
          to="/governance"
          className="card card-hover flex items-center gap-4"
        >
          <div className="p-3 rounded-lg bg-console-primary/10">
            <MessageCircle size={24} className="text-console-primary" />
          </div>
          <div className="flex-1">
            <div className="font-medium text-console-text">{t('help.governanceLink')}</div>
            <div className="text-sm text-console-text-muted">{t('help.governanceLinkDesc')}</div>
          </div>
          <ChevronRight size={16} className="text-console-text-muted" />
        </Link>

        <Link
          to="/statistics"
          className="card card-hover flex items-center gap-4"
        >
          <div className="p-3 rounded-lg bg-console-warning/10">
            <Server size={24} className="text-console-warning" />
          </div>
          <div className="flex-1">
            <div className="font-medium text-console-text">{t('help.statsLink')}</div>
            <div className="text-sm text-console-text-muted">{t('help.statsLinkDesc')}</div>
          </div>
          <ChevronRight size={16} className="text-console-text-muted" />
        </Link>
      </div>

      {/* 联系我们 */}
      <div className="text-center py-6 text-console-text-muted text-sm">
        <p>{t('help.notFound')}</p>
        <Link to="/settings" className="text-console-accent hover:underline">
          {t('help.goToSettings')}
        </Link>
      </div>
    </div>
  )
}
