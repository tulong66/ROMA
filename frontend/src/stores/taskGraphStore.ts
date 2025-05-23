import { create } from 'zustand'
import { subscribeWithSelector } from 'zustand/middleware'
import type { TaskNode, APIResponse, HITLRequest, HITLResponse } from '@/types'

interface TaskGraphState {
  // Data
  nodes: Record<string, TaskNode>
  graphs: Record<string, any>
  overallProjectGoal?: string
  
  // UI State
  isConnected: boolean
  isLoading: boolean
  selectedNodeId?: string
  showContextFlow: boolean
  
  // HITL State
  currentHITLRequest?: HITLRequest
  isHITLModalOpen: boolean
  
  // Actions
  setData: (data: APIResponse) => void
  setConnectionStatus: (status: boolean) => void
  setLoading: (loading: boolean) => void
  selectNode: (nodeId?: string) => void
  toggleContextFlow: () => void
  
  // HITL Actions
  setHITLRequest: (request?: HITLRequest) => void
  respondToHITL: (response: HITLResponse) => void
  closeHITLModal: () => void
}

export const useTaskGraphStore = create<TaskGraphState>()(
  subscribeWithSelector((set, get) => ({
    // Initial state
    nodes: {},
    graphs: {},
    overallProjectGoal: undefined,
    isConnected: false,
    isLoading: false,
    selectedNodeId: undefined,
    showContextFlow: true,
    currentHITLRequest: undefined,
    isHITLModalOpen: false,
    
    // Actions
    setData: (data: APIResponse) => {
      console.log('📊 Store: Received data update:', data)
      console.log('📊 Nodes count:', Object.keys(data.all_nodes || {}).length)
      console.log('📊 Graphs count:', Object.keys(data.graphs || {}).length)
      
      const hasNewData = Object.keys(data.all_nodes || {}).length > 0
      
      set({
        nodes: data.all_nodes || {},
        graphs: data.graphs || {},
        overallProjectGoal: data.overall_project_goal,
        // Clear loading state when we receive data
        isLoading: hasNewData ? false : get().isLoading,
      })
      
      console.log('📊 Store updated, isLoading now:', hasNewData ? false : get().isLoading)
    },
    
    setConnectionStatus: (status: boolean) => {
      console.log('🔌 Store: Connection status changed:', status)
      set({ isConnected: status })
    },
    
    setLoading: (loading: boolean) => {
      console.log('⏳ Store: Loading state changed:', loading)
      set({ isLoading: loading })
    },
    
    selectNode: (nodeId?: string) => set({ selectedNodeId: nodeId }),
    
    toggleContextFlow: () => set((state) => ({ 
      showContextFlow: !state.showContextFlow 
    })),
    
    // HITL Actions
    setHITLRequest: (request?: HITLRequest) => set({
      currentHITLRequest: request,
      isHITLModalOpen: !!request,
    }),
    
    respondToHITL: (response: HITLResponse) => {
      const { currentHITLRequest } = get()
      if (currentHITLRequest) {
        console.log('HITL Response:', response)
      }
      set({
        currentHITLRequest: undefined,
        isHITLModalOpen: false,
      })
    },
    
    closeHITLModal: () => set({
      currentHITLRequest: undefined,
      isHITLModalOpen: false,
    }),
  }))
) 