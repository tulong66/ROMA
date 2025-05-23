import { create } from 'zustand'
import { subscribeWithSelector } from 'zustand/middleware'
import type { TaskNode, APIResponse, HITLRequest, HITLResponse } from '@/types'

// Filtering interfaces
interface GraphFilters {
  statuses: string[]
  taskTypes: string[]
  nodeTypes: ('PLAN' | 'EXECUTE')[]
  layers: number[]
  agentNames: string[]
  searchTerm: string
  showOnlySelected: boolean
}

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
  
  // Filtering State
  filters: GraphFilters
  isFilterPanelOpen: boolean
  
  // HITL State
  currentHITLRequest?: HITLRequest
  isHITLModalOpen: boolean
  
  // Actions
  setData: (data: APIResponse) => void
  setConnectionStatus: (status: boolean) => void
  setLoading: (loading: boolean) => void
  selectNode: (nodeId?: string) => void
  toggleContextFlow: () => void
  
  // Filter Actions
  updateFilters: (filters: Partial<GraphFilters>) => void
  resetFilters: () => void
  toggleFilterPanel: () => void
  setSearchTerm: (term: string) => void
  
  // Quick Filter Actions
  showActiveNodes: () => void
  showProblematicNodes: () => void
  showCompletedNodes: () => void
  showCurrentLayer: () => void
  
  // Computed Properties
  getFilteredNodes: () => Record<string, TaskNode>
  getAvailableFilters: () => {
    statuses: string[]
    taskTypes: string[]
    nodeTypes: ('PLAN' | 'EXECUTE')[]
    layers: number[]
    agentNames: string[]
  }
  
  // HITL Actions
  setHITLRequest: (request?: HITLRequest) => void
  respondToHITL: (response: HITLResponse) => void
  closeHITLModal: () => void
}

const defaultFilters: GraphFilters = {
  statuses: [],
  taskTypes: [],
  nodeTypes: [],
  layers: [],
  agentNames: [],
  searchTerm: '',
  showOnlySelected: false
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
    
    // Filtering state
    filters: defaultFilters,
    isFilterPanelOpen: false,
    
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
    
    // Filter Actions
    updateFilters: (newFilters: Partial<GraphFilters>) => {
      set((state) => ({
        filters: { ...state.filters, ...newFilters }
      }))
    },
    
    resetFilters: () => {
      set({ filters: defaultFilters })
    },
    
    toggleFilterPanel: () => {
      set((state) => ({ isFilterPanelOpen: !state.isFilterPanelOpen }))
    },
    
    setSearchTerm: (term: string) => {
      set((state) => ({
        filters: { ...state.filters, searchTerm: term }
      }))
    },
    
    // Quick Filter Actions
    showActiveNodes: () => {
      set((state) => ({
        filters: { ...state.filters, statuses: ['RUNNING', 'READY'] }
      }))
    },
    
    showProblematicNodes: () => {
      set((state) => ({
        filters: { ...state.filters, statuses: ['FAILED', 'NEEDS_REPLAN'] }
      }))
    },
    
    showCompletedNodes: () => {
      set((state) => ({
        filters: { ...state.filters, statuses: ['DONE'] }
      }))
    },
    
    showCurrentLayer: () => {
      const { nodes, selectedNodeId } = get()
      if (selectedNodeId && nodes[selectedNodeId]) {
        const selectedLayer = nodes[selectedNodeId].layer
        set((state) => ({
          filters: { ...state.filters, layers: [selectedLayer] }
        }))
      }
    },
    
    // Computed Properties
    getFilteredNodes: () => {
      const { nodes, filters } = get()
      const { statuses, taskTypes, nodeTypes, layers, agentNames, searchTerm, showOnlySelected } = filters
      const { selectedNodeId } = get()
      
      return Object.fromEntries(
        Object.entries(nodes).filter(([id, node]) => {
          // Status filter
          if (statuses.length > 0 && !statuses.includes(node.status)) {
            return false
          }
          
          // Task type filter
          if (taskTypes.length > 0 && !taskTypes.includes(node.task_type)) {
            return false
          }
          
          // Node type filter
          if (nodeTypes.length > 0 && !nodeTypes.includes(node.node_type)) {
            return false
          }
          
          // Layer filter
          if (layers.length > 0 && !layers.includes(node.layer)) {
            return false
          }
          
          // Agent name filter
          if (agentNames.length > 0 && node.agent_name && !agentNames.includes(node.agent_name)) {
            return false
          }
          
          // Show only selected filter
          if (showOnlySelected && id !== selectedNodeId) {
            return false
          }
          
          // Search term filter
          if (searchTerm.trim()) {
            const term = searchTerm.toLowerCase()
            const searchableText = [
              node.goal,
              node.task_type,
              node.agent_name,
              node.output_summary,
              JSON.stringify(node.full_result)
            ].filter(Boolean).join(' ').toLowerCase()
            
            if (!searchableText.includes(term)) {
              return false
            }
          }
          
          return true
        })
      )
    },
    
    getAvailableFilters: () => {
      const { nodes } = get()
      const nodeValues = Object.values(nodes)
      
      return {
        statuses: [...new Set(nodeValues.map(n => n.status))].sort(),
        taskTypes: [...new Set(nodeValues.map(n => n.task_type))].sort(),
        nodeTypes: [...new Set(nodeValues.map(n => n.node_type))].sort() as ('PLAN' | 'EXECUTE')[],
        layers: [...new Set(nodeValues.map(n => n.layer))].sort((a, b) => a - b),
        agentNames: [...new Set(nodeValues.map(n => n.agent_name).filter(Boolean))].sort() as string[]
      }
    },
    
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