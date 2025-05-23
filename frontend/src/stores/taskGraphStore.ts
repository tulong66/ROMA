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
  
  // Context Flow State
  contextFlowMode: 'none' | 'dataFlow' | 'executionPath' | 'subtree'
  focusNodeId?: string
  
  // Multi-Selection State
  selectedNodeIds: Set<string>
  isMultiSelectMode: boolean
  comparisonView: 'cards' | 'table' | 'timeline' | 'metrics'
  isComparisonPanelOpen: boolean
  
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
  showActiveNodes: () => void
  showProblematicNodes: () => void
  showCompletedNodes: () => void
  showCurrentLayer: () => void
  
  // Context Flow Actions
  setContextFlowMode: (mode: 'none' | 'dataFlow' | 'executionPath' | 'subtree') => void
  setFocusNode: (nodeId?: string) => void
  zoomToSubtree: (nodeId: string) => void
  
  // Multi-Selection Actions
  toggleNodeSelection: (nodeId: string, isMultiSelect?: boolean) => void
  selectAllNodes: () => void
  selectFilteredNodes: () => void
  clearSelection: () => void
  invertSelection: () => void
  setMultiSelectMode: (enabled: boolean) => void
  setComparisonView: (view: 'cards' | 'table' | 'timeline' | 'metrics') => void
  toggleComparisonPanel: () => void
  
  // Computed Properties
  getFilteredNodes: () => Record<string, TaskNode>
  getAvailableFilters: () => {
    statuses: string[]
    taskTypes: string[]
    nodeTypes: ('PLAN' | 'EXECUTE')[]
    layers: number[]
    agentNames: string[]
  }
  getSelectedNodes: () => TaskNode[]
  getSelectionStats: () => {
    total: number
    byStatus: Record<string, number>
    byTaskType: Record<string, number>
    byLayer: Record<number, number>
    avgExecutionTime: number
    successRate: number
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
    
    // Context Flow state
    contextFlowMode: 'none',
    focusNodeId: undefined,
    
    // Multi-Selection state
    selectedNodeIds: new Set<string>(),
    isMultiSelectMode: false,
    comparisonView: 'cards',
    isComparisonPanelOpen: false,
    
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
    
    // Context Flow Actions
    setContextFlowMode: (mode) => {
      set({ contextFlowMode: mode })
      // Auto-set focus to selected node when switching to a highlighting mode
      if (mode !== 'none' && !get().focusNodeId && get().selectedNodeId) {
        set({ focusNodeId: get().selectedNodeId })
      }
    },
    
    setFocusNode: (nodeId) => set({ focusNodeId: nodeId }),
    
    zoomToSubtree: (nodeId) => {
      console.log('Zooming to subtree:', nodeId)
      set({ focusNodeId: nodeId, contextFlowMode: 'subtree' })
    },
    
    // Multi-Selection Actions
    toggleNodeSelection: (nodeId: string, isMultiSelect = false) => {
      set((state) => {
        const newSelectedIds = new Set(state.selectedNodeIds)
        
        if (isMultiSelect) {
          // Multi-select mode: toggle the clicked node
          if (newSelectedIds.has(nodeId)) {
            newSelectedIds.delete(nodeId)
          } else {
            newSelectedIds.add(nodeId)
          }
          
          return {
            selectedNodeIds: newSelectedIds,
            selectedNodeId: newSelectedIds.size === 1 ? Array.from(newSelectedIds)[0] : undefined,
            isMultiSelectMode: newSelectedIds.size > 1
          }
        } else {
          // Single select mode: replace selection
          const wasSelected = newSelectedIds.has(nodeId)
          newSelectedIds.clear()
          
          if (!wasSelected) {
            newSelectedIds.add(nodeId)
          }
          
          return {
            selectedNodeIds: newSelectedIds,
            selectedNodeId: newSelectedIds.size === 1 ? nodeId : undefined,
            isMultiSelectMode: false
          }
        }
      })
    },
    
    selectAllNodes: () => {
      const filteredNodes = get().getFilteredNodes()
      const allNodeIds = new Set(Object.keys(filteredNodes))
      
      set({
        selectedNodeIds: allNodeIds,
        selectedNodeId: undefined,
        isMultiSelectMode: allNodeIds.size > 1
      })
    },
    
    selectFilteredNodes: () => {
      const filteredNodes = get().getFilteredNodes()
      const filteredNodeIds = new Set(Object.keys(filteredNodes))
      
      set({
        selectedNodeIds: filteredNodeIds,
        selectedNodeId: undefined,
        isMultiSelectMode: filteredNodeIds.size > 1
      })
    },
    
    clearSelection: () => {
      set({
        selectedNodeIds: new Set(),
        selectedNodeId: undefined,
        isMultiSelectMode: false,
        isComparisonPanelOpen: false
      })
    },
    
    invertSelection: () => {
      const { selectedNodeIds, getFilteredNodes } = get()
      const filteredNodes = getFilteredNodes()
      const allNodeIds = new Set(Object.keys(filteredNodes))
      const newSelection = new Set<string>()
      
      allNodeIds.forEach(id => {
        if (!selectedNodeIds.has(id)) {
          newSelection.add(id)
        }
      })
      
      set({
        selectedNodeIds: newSelection,
        selectedNodeId: newSelection.size === 1 ? Array.from(newSelection)[0] : undefined,
        isMultiSelectMode: newSelection.size > 1
      })
    },
    
    setMultiSelectMode: (enabled: boolean) => {
      if (!enabled) {
        // When disabling multi-select, keep only the first selected node
        const { selectedNodeIds } = get()
        const firstSelected = Array.from(selectedNodeIds)[0]
        
        set({
          selectedNodeIds: firstSelected ? new Set([firstSelected]) : new Set(),
          selectedNodeId: firstSelected,
          isMultiSelectMode: false
        })
      } else {
        set({ isMultiSelectMode: enabled })
      }
    },
    
    setComparisonView: (view) => set({ comparisonView: view }),
    
    toggleComparisonPanel: () => {
      set((state) => ({ isComparisonPanelOpen: !state.isComparisonPanelOpen }))
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
    
    getSelectedNodes: () => {
      const { nodes, selectedNodeIds } = get()
      return Array.from(selectedNodeIds).map(id => nodes[id]).filter(Boolean)
    },
    
    getSelectionStats: () => {
      const selectedNodes = get().getSelectedNodes()
      
      const stats = {
        total: selectedNodes.length,
        byStatus: {} as Record<string, number>,
        byTaskType: {} as Record<string, number>,
        byLayer: {} as Record<number, number>,
        avgExecutionTime: 0,
        successRate: 0
      }
      
      if (selectedNodes.length === 0) return stats
      
      // Calculate statistics
      let totalExecutionTime = 0
      let nodesWithExecutionTime = 0
      let successCount = 0
      
      selectedNodes.forEach(node => {
        // Status counts
        stats.byStatus[node.status] = (stats.byStatus[node.status] || 0) + 1
        
        // Task type counts
        stats.byTaskType[node.task_type] = (stats.byTaskType[node.task_type] || 0) + 1
        
        // Layer counts
        stats.byLayer[node.layer] = (stats.byLayer[node.layer] || 0) + 1
        
        // Execution time calculation
        if (node.timestamp_created && node.timestamp_completed) {
          const created = new Date(node.timestamp_created).getTime()
          const completed = new Date(node.timestamp_completed).getTime()
          totalExecutionTime += completed - created
          nodesWithExecutionTime++
        }
        
        // Success rate
        if (node.status === 'DONE') {
          successCount++
        }
      })
      
      stats.avgExecutionTime = nodesWithExecutionTime > 0 ? totalExecutionTime / nodesWithExecutionTime : 0
      stats.successRate = selectedNodes.length > 0 ? (successCount / selectedNodes.length) * 100 : 0
      
      return stats
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