import { Outlet, NavLink, useLocation } from 'react-router-dom'
import { 
  LayoutDashboard, 
  Store, 
  ListTodo, 
  Wallet, 
  Receipt, 
  User, 
  HelpCircle,
  Menu,
  X,
  Bell,
  ChevronDown,
  Settings,
  LogOut,
  Key,
  Server,
  AlertTriangle,
  CheckCircle,
  ExternalLink,
  Vote,
  BarChart2,
  Users,
  Shield,
  Hammer,
  Database,
  PlayCircle,
  Rocket
} from 'lucide-react'
import { useState, useEffect } from 'react'
import { useAccountStore, useUIStore, useNotificationStore } from '../store'
import { statsApi } from '../api'
import { useTranslation } from '../i18n'
import clsx from 'clsx'

// Navigation items with i18n keys
const navItemDefs = [
  { path: '/', icon: LayoutDashboard, labelKey: 'nav.dashboard', descKey: 'nav.dashboardDesc' },
  { path: '/market', icon: Store, labelKey: 'nav.market', descKey: 'nav.marketDesc' },
  { path: '/tasks', icon: ListTodo, labelKey: 'nav.tasks', descKey: 'nav.tasksDesc' },
  { path: '/mining', icon: Hammer, labelKey: 'nav.mining', descKey: 'nav.miningDesc' },
  { path: '/provider', icon: Server, labelKey: 'nav.provider', descKey: 'nav.providerDesc' },
  { path: '/demo', icon: PlayCircle, labelKey: 'nav.demo', descKey: 'nav.demoDesc' },
  { path: '/showcase', icon: Rocket, labelKey: 'nav.showcase', descKey: 'nav.showcaseDesc' },
  { path: '/wallet', icon: Wallet, labelKey: 'nav.wallet', descKey: 'nav.walletDesc' },
  { path: '/explorer', icon: Database, labelKey: 'nav.explorer', descKey: 'nav.explorerDesc' },
  { path: '/orders', icon: Receipt, labelKey: 'nav.orders', descKey: 'nav.ordersDesc' },
  { path: '/miners', icon: Users, labelKey: 'nav.miners', descKey: 'nav.minersDesc' },
  { path: '/governance', icon: Vote, labelKey: 'nav.governance', descKey: 'nav.governanceDesc' },
  { path: '/statistics', icon: BarChart2, labelKey: 'nav.statistics', descKey: 'nav.statisticsDesc' },
  { path: '/privacy', icon: Shield, labelKey: 'nav.privacy', descKey: 'nav.privacyDesc' },
  { path: '/account', icon: User, labelKey: 'nav.account', descKey: 'nav.accountDesc' },
]

const bottomNavDefs = [
  { path: '/settings', icon: Settings, labelKey: 'nav.settings' },
  { path: '/help', icon: HelpCircle, labelKey: 'nav.help' },
]

interface SystemStatus {
  status: 'healthy' | 'degraded' | 'down'
  message: string
  blockHeight: number
  syncStatus: boolean
}

export default function Layout() {
  const location = useLocation()
  const { sidebarOpen, toggleSidebar } = useUIStore()
  const { account, isConnected, setAccount, setConnected } = useAccountStore()
  const { notifications } = useNotificationStore()
  const { t } = useTranslation()
  const [showNotifications, setShowNotifications] = useState(false)
  const [showUserMenu, setShowUserMenu] = useState(false)
  const [systemStatus, setSystemStatus] = useState<SystemStatus>({
    status: 'healthy',
    message: '',
    blockHeight: 0,
    syncStatus: true
  })

  // 获取系统状态
  useEffect(() => {
    const checkStatus = async () => {
      try {
        const data = await statsApi.getChainInfo()
        if (data) {
          setSystemStatus({
            status: 'healthy',
            message: 'mainnetConnected',
            blockHeight: data.height || 0,
            syncStatus: !data.syncing
          })
        }
      } catch {
        setSystemStatus({
          status: 'down',
          message: '无法连接节点',
          blockHeight: 0,
          syncStatus: false
        })
      }
    }
    checkStatus()
    const interval = setInterval(checkStatus, 30000)
    return () => clearInterval(interval)
  }, [])

  const getStatusColor = () => {
    switch (systemStatus.status) {
      case 'healthy': return 'status-dot-online'
      case 'degraded': return 'status-dot-busy'
      case 'down': return 'status-dot-error'
    }
  }

  return (
    <div className="min-h-screen flex bg-console-bg">
      {/* 侧边栏 */}
      <aside 
        className={clsx(
          'fixed inset-y-0 left-0 z-50 w-64 bg-console-surface border-r border-console-border transform transition-transform duration-300 lg:relative lg:translate-x-0 flex flex-col',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {/* Logo */}
        <div className="h-14 flex items-center px-4 border-b border-console-border shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded bg-console-accent flex items-center justify-center">
              <Server size={18} className="text-white" />
            </div>
            <div>
              <span className="text-base font-semibold text-console-text">MainCoin</span>
              <span className="text-xs text-console-text-muted ml-1">Console</span>
            </div>
          </div>
          <button 
            onClick={toggleSidebar}
            className="ml-auto lg:hidden text-console-text-muted hover:text-console-text"
          >
            <X size={20} />
          </button>
        </div>

        {/* 主导航 */}
        <nav className="flex-1 py-4 overflow-y-auto">
          <div className="px-3 mb-2">
            <span className="text-xs font-medium text-console-text-muted uppercase tracking-wider">
              {t('nav.mainMenu')}
            </span>
          </div>
          {navItemDefs.map((item) => {
            const Icon = item.icon
            const isActive = location.pathname === item.path || 
              (item.path !== '/' && location.pathname.startsWith(item.path))
            
            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={clsx(
                  'flex items-center gap-3 px-4 py-2.5 mx-2 rounded-md transition-all duration-150',
                  isActive 
                    ? 'bg-console-accent/15 text-console-text border-l-2 border-console-accent ml-0 rounded-l-none' 
                    : 'text-console-text-muted hover:text-console-text hover:bg-console-border/30'
                )}
              >
                <Icon size={18} />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium">{t(item.labelKey)}</div>
                  {isActive && (
                    <div className="text-xs text-console-text-muted truncate">{t(item.descKey)}</div>
                  )}
                </div>
              </NavLink>
            )
          })}
        </nav>

        {/* 底部导航 */}
        <div className="py-2 border-t border-console-border">
          {bottomNavDefs.map((item) => {
            const Icon = item.icon
            return (
              <NavLink
                key={item.path}
                to={item.path}
                className="flex items-center gap-3 px-4 py-2 mx-2 text-sm text-console-text-muted hover:text-console-text hover:bg-console-border/30 rounded-md"
              >
                <Icon size={16} />
                <span>{t(item.labelKey)}</span>
              </NavLink>
            )
          })}
        </div>

        {/* 系统状态 */}
        <div className="p-4 border-t border-console-border shrink-0">
          <div className="flex items-center gap-3">
            <div className={clsx('status-dot', getStatusColor())} />
            <div className="flex-1 min-w-0">
              <div className="text-xs text-console-text truncate">{t('status.' + systemStatus.message)}</div>
              <div className="text-xs text-console-text-muted">
                {t('header.blockHeight')} #{systemStatus.blockHeight.toLocaleString()}
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* 主内容区 */}
      <div className="flex-1 flex flex-col min-h-screen min-w-0">
        {/* 顶部导航栏 */}
        <header className="h-14 bg-console-surface border-b border-console-border flex items-center justify-between px-4 sticky top-0 z-30 shrink-0">
          <div className="flex items-center gap-4">
            <button 
              onClick={toggleSidebar}
              className="lg:hidden text-console-text-muted hover:text-console-text"
            >
              <Menu size={20} />
            </button>

            {/* 面包屑 */}
            <div className="breadcrumb hidden sm:flex">
              <span>MainCoin</span>
              <span>/</span>
              <span className="text-console-text">
                {t(navItemDefs.find(item => 
                  item.path === location.pathname || 
                  (item.path !== '/' && location.pathname.startsWith(item.path))
                )?.labelKey || 'nav.dashboard')}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* 系统公告 */}
            {systemStatus.status !== 'healthy' && (
              <div className="hidden md:flex items-center gap-2 px-3 py-1 bg-console-warning/10 border border-console-warning/30 rounded text-xs text-console-warning">
                <AlertTriangle size={14} />
                <span>{t('status.maintenance')}</span>
              </div>
            )}

            {/* 通知按钮 */}
            <div className="relative">
              <button 
                onClick={() => setShowNotifications(!showNotifications)}
                className="relative p-2 text-console-text-muted hover:text-console-text hover:bg-console-border/30 rounded transition-colors"
              >
                <Bell size={18} />
                {notifications.length > 0 && (
                  <span className="absolute top-1 right-1 w-2 h-2 bg-console-error rounded-full" />
                )}
              </button>
              
              {showNotifications && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setShowNotifications(false)} />
                  <div className="dropdown right-0 top-full mt-2 w-80 z-50">
                    <div className="px-4 py-3 border-b border-console-border">
                      <h3 className="font-medium text-console-text">{t('header.notifications')}</h3>
                    </div>
                    <div className="max-h-64 overflow-y-auto">
                      {notifications.length === 0 ? (
                        <div className="px-4 py-8 text-center text-console-text-muted text-sm">
                          {t('header.noNotifications')}
                        </div>
                      ) : (
                        notifications.map(n => (
                          <div key={n.id} className="dropdown-item flex-col items-start gap-1">
                            <div className="flex items-center gap-2">
                              {n.type === 'success' && <CheckCircle size={14} className="text-green-400" />}
                              {n.type === 'error' && <AlertTriangle size={14} className="text-red-400" />}
                              <span className="font-medium text-sm">{n.title}</span>
                            </div>
                            <p className="text-xs text-console-text-muted">{n.message}</p>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </>
              )}
            </div>

            {/* 用户菜单 */}
            <div className="relative">
              <button 
                onClick={() => setShowUserMenu(!showUserMenu)}
                className="flex items-center gap-2 p-2 rounded hover:bg-console-border/30 transition-colors"
              >
                <div className="w-7 h-7 rounded bg-console-accent/20 border border-console-accent/50 flex items-center justify-center">
                  <User size={14} className="text-console-accent" />
                </div>
                {isConnected && account ? (
                  <span className="hidden sm:block text-sm text-console-text font-mono">
                    {account.address.slice(0, 6)}...{account.address.slice(-4)}
                  </span>
                ) : (
                  <span className="hidden sm:block text-sm text-console-text-muted">{t('header.notConnected')}</span>
                )}
                <ChevronDown size={14} className="text-console-text-muted" />
              </button>
              
              {showUserMenu && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setShowUserMenu(false)} />
                  <div className="dropdown right-0 top-full mt-2 z-50">
                    {isConnected ? (
                      <>
                        <div className="px-4 py-3 border-b border-console-border">
                          <div className="text-sm font-medium text-console-text">{t('header.connectedWallet')}</div>
                          <div className="text-xs text-console-text-muted font-mono mt-1">
                            {account?.address}
                          </div>
                        </div>
                        <NavLink to="/account" className="dropdown-item">
                          <User size={14} />
                          <span>{t('header.userCenter')}</span>
                        </NavLink>
                        <NavLink to="/wallet" className="dropdown-item">
                          <Key size={14} />
                          <span>{t('header.keyManagement')}</span>
                        </NavLink>
                        <NavLink to="/settings" className="dropdown-item">
                          <Settings size={14} />
                          <span>{t('header.settings')}</span>
                        </NavLink>
                        <div className="border-t border-console-border my-1" />
                        <button 
                          className="dropdown-item text-console-error w-full"
                          onClick={() => {
                            localStorage.removeItem('pouw_wallet_mnemonic')
                            localStorage.removeItem('pouw_connected')
                            localStorage.removeItem('wallet_address')
                            setAccount(null)
                            setConnected(false)
                            window.location.href = '/connect'
                          }}
                        >
                          <LogOut size={14} />
                          <span>{t('header.disconnect')}</span>
                        </button>
                      </>
                    ) : (
                      <>
                        <NavLink to="/connect" className="dropdown-item">
                          <Wallet size={14} />
                          <span>{t('header.connectWallet')}</span>
                        </NavLink>
                        <NavLink to="/" className="dropdown-item">
                          <ExternalLink size={14} />
                          <span>{t('header.readOnlyMode')}</span>
                        </NavLink>
                      </>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
        </header>

        {/* 页面内容 */}
        <main className="flex-1 p-6 overflow-auto">
          <Outlet />
        </main>

        {/* 页脚 */}
        <footer className="h-10 bg-console-surface border-t border-console-border flex items-center justify-between px-4 text-xs text-console-text-muted shrink-0">
          <div>{t('footer.slogan')}</div>
          <div className="flex items-center gap-4">
            <NavLink to="/help" className="hover:text-console-text">{t('footer.docs')}</NavLink>
            <NavLink to="/explorer" className="hover:text-console-text">{t('footer.explorer')}</NavLink>
            <NavLink to="/statistics" className="hover:text-console-text">{t('footer.status')}</NavLink>
          </div>
        </footer>
      </div>
    </div>
  )
}
