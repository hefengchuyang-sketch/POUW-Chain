import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Tasks from './pages/Tasks'
import TaskDetail from './pages/TaskDetail'
import Market from './pages/Market'
import Wallet from './pages/Wallet'
import Orders from './pages/Orders'
import Account from './pages/Account'
import Connect from './pages/Connect'
import Help from './pages/Help'
import Settings from './pages/Settings'
import Governance from './pages/Governance'
import Statistics from './pages/Statistics'
import Miners from './pages/Miners'
import Privacy from './pages/Privacy'
import ProposalDetail from './pages/ProposalDetail'
import Mining from './pages/Mining'
import Provider from './pages/Provider'
import Explorer from './pages/Explorer'
import DemoFlow from './pages/DemoFlow'
import ProjectShowcase from './pages/ProjectShowcase'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        {/* 控制台首页 */}
        <Route index element={<Dashboard />} />
        
        {/* 算力市场 */}
        <Route path="market" element={<Market />} />
        
        {/* 任务系统 */}
        <Route path="tasks" element={<Tasks />} />
        <Route path="tasks/:taskId" element={<TaskDetail />} />
        
        {/* 钱包 */}
        <Route path="wallet" element={<Wallet />} />
        
        {/* 订单中心 */}
        <Route path="orders" element={<Orders />} />
        
        {/* 用户中心 */}
        <Route path="account" element={<Account />} />
        
        {/* 治理 */}
        <Route path="governance" element={<Governance />} />
        <Route path="governance/:proposalId" element={<ProposalDetail />} />
        
        {/* 统计 */}
        <Route path="statistics" element={<Statistics />} />
        
        {/* 区块浏览器 */}
        <Route path="explorer" element={<Explorer />} />

        {/* 可视化演示 */}
        <Route path="demo" element={<DemoFlow />} />

        {/* 项目介绍 */}
        <Route path="showcase" element={<ProjectShowcase />} />
        
        {/* 矿工 */}
        <Route path="miners" element={<Miners />} />
        
        {/* 挖矿 */}
        <Route path="mining" element={<Mining />} />
        
        {/* 算力提供者 */}
        <Route path="provider" element={<Provider />} />
        
        {/* 隐私 */}
        <Route path="privacy" element={<Privacy />} />
        
        {/* 设置 */}
        <Route path="settings" element={<Settings />} />
        
        {/* 帮助 */}
        <Route path="help" element={<Help />} />
      </Route>
      
      {/* 钱包连接页面（独立布局） */}
      <Route path="connect" element={<Connect />} />
    </Routes>
  )
}

export default App

