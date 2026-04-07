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
        {/* Console home */}
        <Route index element={<Dashboard />} />
        
        {/* Compute market */}
        <Route path="market" element={<Market />} />
        
        {/* Task system */}
        <Route path="tasks" element={<Tasks />} />
        <Route path="tasks/:taskId" element={<TaskDetail />} />
        
        {/* Wallet */}
        <Route path="wallet" element={<Wallet />} />
        
        {/* Order center */}
        <Route path="orders" element={<Orders />} />
        
        {/* User center */}
        <Route path="account" element={<Account />} />
        
        {/* Governance */}
        <Route path="governance" element={<Governance />} />
        <Route path="governance/:proposalId" element={<ProposalDetail />} />
        
        {/* Statistics */}
        <Route path="statistics" element={<Statistics />} />
        
        {/* Explorer */}
        <Route path="explorer" element={<Explorer />} />

        {/* Visual demo */}
        <Route path="demo" element={<DemoFlow />} />

        {/* Project showcase */}
        <Route path="showcase" element={<ProjectShowcase />} />
        
        {/* Miners */}
        <Route path="miners" element={<Miners />} />
        
        {/* Mining */}
        <Route path="mining" element={<Mining />} />
        
        {/* Compute provider */}
        <Route path="provider" element={<Provider />} />
        
        {/* Privacy */}
        <Route path="privacy" element={<Privacy />} />
        
        {/* Settings */}
        <Route path="settings" element={<Settings />} />
        
        {/* Help */}
        <Route path="help" element={<Help />} />
      </Route>
      
      {/* Wallet connect page (standalone layout) */}
      <Route path="connect" element={<Connect />} />
    </Routes>
  )
}

export default App

