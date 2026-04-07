import { create } from 'zustand'
import type { Account } from '../api'

// ========== Account state ==========

interface AccountState {
  account: Account | null
  isConnected: boolean
  isLoading: boolean
  error: string | null
  
  setAccount: (account: Account | null) => void
  setConnected: (connected: boolean) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
}

// Restore connection state from localStorage
const savedAddress = localStorage.getItem('wallet_address')
const initialConnected = !!savedAddress
const initialAccount: Account | null = savedAddress
  ? { address: savedAddress, balance: 0, mainBalance: 0, sectorTotal: 0, sectorAddresses: {}, sectorBalances: {}, privacyLevel: 'pseudonymous', privacyRisk: 'low', subAddresses: [] }
  : null

export const useAccountStore = create<AccountState>((set) => ({
  account: initialAccount,
  isConnected: initialConnected,
  isLoading: false,
  error: null,
  
  setAccount: (account) => {
    // Persist wallet address for RPC authentication
    if (account?.address) {
      localStorage.setItem('wallet_address', account.address)
    } else {
      localStorage.removeItem('wallet_address')
    }
    set({ account })
  },
  setConnected: (isConnected) => {
    if (!isConnected) {
      localStorage.removeItem('wallet_address')
      localStorage.removeItem('pouw_wallet_mnemonic')
    }
    set({ isConnected })
  },
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
}))

// ========== Notification state ==========

interface Notification {
  id: string
  type: 'success' | 'error' | 'warning' | 'info'
  title: string
  message: string
  duration?: number
}

interface NotificationState {
  notifications: Notification[]
  
  addNotification: (notification: Omit<Notification, 'id'>) => void
  removeNotification: (id: string) => void
  clearAll: () => void
}

export const useNotificationStore = create<NotificationState>((set) => ({
  notifications: [],
  
  addNotification: (notification) => {
    const id = Date.now().toString()
    set((state) => ({
      notifications: [
        ...state.notifications,
        { ...notification, id }
      ]
    }))
    // Auto-clear notification (after 5 seconds)
    setTimeout(() => {
      set((state) => ({
        notifications: state.notifications.filter(n => n.id !== id)
      }))
    }, 5000)
  },
  removeNotification: (id) => set((state) => ({
    notifications: state.notifications.filter(n => n.id !== id)
  })),
  clearAll: () => set({ notifications: [] }),
}))

// ========== UI state ==========

interface UIState {
  sidebarOpen: boolean
  theme: 'dark' | 'light'
  
  toggleSidebar: () => void
  setTheme: (theme: UIState['theme']) => void
}

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  theme: 'dark',
  
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setTheme: (theme) => set({ theme }),
}))
