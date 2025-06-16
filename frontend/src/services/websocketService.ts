import { io, Socket } from 'socket.io-client'
import { useTaskGraphStore } from '@/stores/taskGraphStore'
import type { APIResponse, HITLRequest, HITLResponse } from '@/types'
import { useProjectStore } from '@/stores/projectStore'

class WebSocketService {
  private socket: Socket | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 10
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private isConnecting = false
  private lastUpdateTime = 0
  private updateCount = 0
  private connectionStableTimer: ReturnType<typeof setTimeout> | null = null
  private hasEverConnected = false
  private lastConnectionAttempt = 0

  connect() {
    if (this.isConnecting || this.isConnected()) {
      console.log('⚠️ Already connecting or connected')
      return
    }

    if (this.socket && !this.socket.connected && Date.now() - this.lastConnectionAttempt < 1000) {
      console.log('⚠️ Too soon to reconnect, waiting...')
      return
    }

    this.lastConnectionAttempt = Date.now()
    this.isConnecting = true
    console.log('🔌 Attempting to connect to WebSocket at http://localhost:5000')
    
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }

    this.socket = io('http://localhost:5000', {
      transports: ['polling'],
      timeout: 20000,
      forceNew: true,
      reconnection: false,
      upgrade: true,
      rememberUpgrade: true
    })

    this.setupEventListeners()
  }

  private setupEventListeners() {
    if (!this.socket) return

    this.socket.removeAllListeners()

    this.socket.on('connect', () => {
      console.log('✅ WebSocket connected successfully')
      this.isConnecting = false
      useTaskGraphStore.getState().setConnectionStatus(true)
      this.reconnectAttempts = 0
      
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer)
        this.reconnectTimer = null
      }

      this.connectionStableTimer = setTimeout(() => {
        console.log('🔒 WebSocket connection stabilized')
      }, 10000)
    })

    this.socket.on('disconnect', (reason) => {
      console.log('❌ WebSocket disconnected:', reason)
      this.isConnecting = false
      useTaskGraphStore.getState().setConnectionStatus(false)
      
      if (this.connectionStableTimer) {
        clearTimeout(this.connectionStableTimer)
        this.connectionStableTimer = null
      }
      
      if (reason === 'io server disconnect' || 
          reason === 'transport close' || 
          reason === 'transport error' ||
          reason === 'ping timeout') {
        console.log('🔄 Server disconnected, attempting reconnection...')
        this.handleReconnect()
      }
    })

    this.socket.on('connect_error', (error) => {
      console.error('❌ WebSocket connection error:', error)
      this.isConnecting = false
      useTaskGraphStore.getState().setConnectionStatus(false)
      this.handleReconnect()
    })

    // FIXED: Enhanced project-aware task graph updates with aggressive debugging
    this.socket.on('task_graph_update', (data: APIResponse & { project_id?: string, current_project?: any }) => {
      const now = Date.now()
      this.updateCount++
      
      console.log(`🚨🚨🚨 [UPDATE ${this.updateCount}] WEBSOCKET RECEIVED PROJECT-AWARE UPDATE`)
      console.log('📊 Raw data keys:', Object.keys(data))
      console.log('📊 Project ID from data:', data.project_id)
      console.log('📊 Current project from data:', data.current_project?.id)
      console.log('📊 Nodes in data:', Object.keys(data.all_nodes || {}).length)
      console.log('📊 First few node IDs:', Object.keys(data.all_nodes || {}).slice(0, 3))
      
      this.lastUpdateTime = now
      
      try {
        const taskGraphStore = useTaskGraphStore.getState()
        const projectStore = useProjectStore.getState()
        
        // AGGRESSIVE DEBUGGING: Log current store state
        console.log('🏪 BEFORE UPDATE - Store state:', {
          taskGraphCurrentProject: taskGraphStore.currentProjectId,
          projectStoreCurrentProject: projectStore.currentProjectId,
          taskGraphNodeCount: Object.keys(taskGraphStore.nodes).length,
          projectDataKeys: Object.keys(taskGraphStore.projectData)
        })
        
        // Determine the project ID with multiple fallbacks
        const projectId = data.project_id || 
                         data.current_project?.id || 
                         projectStore.currentProjectId ||
                         taskGraphStore.currentProjectId
        
        console.log('🎯 DETERMINED PROJECT ID:', projectId)
        
        if (projectId) {
          console.log('🏪 Storing project-specific data for:', projectId)
          
          // CRITICAL FIX: Always store project data first
          taskGraphStore.setProjectData(projectId, data)
          
          // CRITICAL FIX: Only update display if this matches BOTH store's current project
          const isCurrentInTaskGraph = projectId === taskGraphStore.currentProjectId
          const isCurrentInProjectStore = projectId === projectStore.currentProjectId
          
          console.log('🔍 PROJECT MATCHING CHECK:', {
            projectId,
            taskGraphCurrent: taskGraphStore.currentProjectId,
            projectStoreCurrent: projectStore.currentProjectId,
            isCurrentInTaskGraph,
            isCurrentInProjectStore,
            shouldUpdateDisplay: isCurrentInTaskGraph && isCurrentInProjectStore
          })
          
          if (isCurrentInTaskGraph && isCurrentInProjectStore) {
            console.log('🔄 Updating display for current project:', projectId)
            taskGraphStore.setData(data)
            
            // AGGRESSIVE DEBUGGING: Verify the update worked
            setTimeout(() => {
              const afterState = useTaskGraphStore.getState()
              console.log('✅ AFTER DISPLAY UPDATE:', {
                nodeCount: Object.keys(afterState.nodes).length,
                firstNodeId: Object.keys(afterState.nodes)[0],
                overallGoal: afterState.overallProjectGoal?.substring(0, 50)
              })
            }, 100)
          } else {
            console.log('📦 Stored data for non-current project:', projectId, 
                       '(taskGraph current:', taskGraphStore.currentProjectId, 
                       ', projectStore current:', projectStore.currentProjectId, ')')
          }
          
          // CRITICAL FIX: Auto-save project data for persistence
          this.autoSaveProjectData(projectId, data)
          
        } else {
          console.warn('⚠️ No project ID found, using legacy setData (this may cause project mixing!)')
          taskGraphStore.setData(data)
        }
        
        // AGGRESSIVE DEBUGGING: Log final state
        const finalState = useTaskGraphStore.getState()
        console.log('🏪 AFTER UPDATE - Final store state:', {
          taskGraphCurrentProject: finalState.currentProjectId,
          taskGraphNodeCount: Object.keys(finalState.nodes).length,
          projectDataKeys: Object.keys(finalState.projectData),
          projectDataSizes: Object.fromEntries(
            Object.entries(finalState.projectData).map(([id, data]) => 
              [id, Object.keys(data.nodes).length]
            )
          )
        })
        
        console.log('✅ Project-aware update completed')
      } catch (error) {
        console.error('❌ ERROR in project-aware WebSocket handler:', error)
        console.error('Stack trace:', error.stack)
      }
    })

    this.socket.on('hitl_request', (request: HITLRequest) => {
      console.log('🤔 WebSocket: Received HITL request:', {
        timestamp: new Date().toISOString(),
        requestId: request.request_id,
        checkpoint: request.checkpoint_name,
        nodeId: request.node_id,
        fullRequest: request
      })
      
      try {
        // AGGRESSIVE DEBUGGING: Validate request structure
        const validationErrors = []
        if (!request.request_id) validationErrors.push('missing request_id')
        if (!request.checkpoint_name) validationErrors.push('missing checkpoint_name')
        if (!request.node_id) validationErrors.push('missing node_id')
        
        if (validationErrors.length > 0) {
          console.error('❌ Invalid HITL request structure:', {
            errors: validationErrors,
            request
          })
          return
        }

        console.log('✅ HITL request validation passed')
        
        // Add to HITL logs
        console.log('📝 Adding HITL log entry')
        useTaskGraphStore.getState().addHITLLog({
          checkpoint_name: request.checkpoint_name,
          context_message: request.context_message,
          node_id: request.node_id,
          current_attempt: request.current_attempt,
          timestamp: request.timestamp || new Date().toISOString(),
          request_id: request.request_id
        })
        
        // AGGRESSIVE DEBUGGING: Check store state before setting
        const storeBefore = useTaskGraphStore.getState()
        console.log('🏪 Store state BEFORE setting HITL request:', {
          hitlRequest: storeBefore.hitlRequest,
          currentHITLRequest: storeBefore.currentHITLRequest,
          isHITLModalOpen: storeBefore.isHITLModalOpen
        })
        
        // Set the HITL request in the store - this should open the modal
        console.log('📤 Setting HITL request in store')
        useTaskGraphStore.getState().setHITLRequest(request)
        
        // AGGRESSIVE DEBUGGING: Verify it was set and check multiple times
        const verifyStoreUpdate = () => {
          const storeAfter = useTaskGraphStore.getState()
          console.log('✅ Store state AFTER setting HITL request:', {
            timestamp: new Date().toISOString(),
            hitlRequest: storeAfter.hitlRequest,
            currentHITLRequest: storeAfter.currentHITLRequest,
            isHITLModalOpen: storeAfter.isHITLModalOpen,
            hasRequest: !!storeAfter.hitlRequest,
            requestIdMatch: storeAfter.hitlRequest?.request_id === request.request_id
          })
          
          // Check if the modal should be visible
          if (!storeAfter.hitlRequest) {
            console.error('🚨 CRITICAL: HITL request was not set in store!')
          } else if (storeAfter.hitlRequest.request_id !== request.request_id) {
            console.error('🚨 CRITICAL: HITL request ID mismatch!')
          } else {
            console.log('✅ HITL request successfully set in store')
          }
        }
        
        // Verify immediately and after a delay
        verifyStoreUpdate()
        setTimeout(verifyStoreUpdate, 100)
        setTimeout(verifyStoreUpdate, 500)
        
      } catch (error) {
        console.error('❌ Error processing HITL request:', error)
        console.error('Stack trace:', error.stack)
      }
    })

    // AGGRESSIVE DEBUGGING: Add test event handler
    this.socket.on('hitl_test', (data) => {
      console.log('🧪 Received HITL test event:', data)
      
      // Trigger a test HITL request
      const testRequest = {
        request_id: 'test-' + Date.now(),
        checkpoint_name: 'TestCheckpoint',
        context_message: 'This is a test HITL request',
        data_for_review: { test: true },
        node_id: 'test-node',
        current_attempt: 1,
        timestamp: new Date().toISOString()
      }
      
      console.log('🧪 Triggering test HITL request:', testRequest)
      useTaskGraphStore.getState().setHITLRequest(testRequest)
    })

    this.socket.on('project_started', (data) => {
      console.log('🚀 Project started confirmation:', data)
      useTaskGraphStore.getState().setLoading(false)
    })

    this.socket.on('error', (error) => {
      console.error('❌ Socket error:', error)
      useTaskGraphStore.getState().setLoading(false)
    })

    // AGGRESSIVE DEBUGGING: Log ALL WebSocket events
    this.socket.onAny((eventName, ...args) => {
      console.log(`🔊 WebSocket event received: "${eventName}"`, {
        timestamp: new Date().toISOString(),
        args: args.length > 0 ? args : 'no args'
      })
    })

    // UPDATED: Enhanced project switching events with project-specific handling
    this.socket.on('project_switched', (data) => {
      console.log('🔄 Project switched:', data)
      
      const taskGraphStore = useTaskGraphStore.getState()
      const projectStore = useProjectStore.getState()
      
      // Update current project in both stores
      if (data.project_id) {
        taskGraphStore.setCurrentProject(data.project_id)
        projectStore.setCurrentProject(data.project_id)
      }
      
      // Update task graph with new project data
      if (data.project_data) {
        if (data.project_id) {
          // Store project-specific data
          taskGraphStore.setProjectData(data.project_id, data.project_data)
          // Switch to the project (this will update display)
          taskGraphStore.switchToProject(data.project_id)
        } else {
          // Fallback to legacy behavior
          taskGraphStore.setData(data.project_data)
        }
      }
    })

    this.socket.on('project_switch_success', (data) => {
      console.log('✅ Project switch successful:', data)
      
      const taskGraphStore = useTaskGraphStore.getState()
      
      // Update task graph with new project data
      if (data.project_data && data.project_id) {
        taskGraphStore.setProjectData(data.project_id, data.project_data)
        taskGraphStore.switchToProject(data.project_id)
      } else if (data.project_data) {
        taskGraphStore.setData(data.project_data)
      }
    })

    this.socket.on('project_switch_error', (data) => {
      console.error('❌ Project switch error:', data)
      // Could emit a toast notification here
    })

    this.socket.on('project_restored', (data: any) => {
      console.log('🔄 Project state restored:', data)
      console.log('🚨 RESTORE DEBUG - Data keys:', Object.keys(data))
      console.log('🚨 RESTORE DEBUG - Node count:', Object.keys(data.all_nodes || {}).length)
      console.log('🚨 RESTORE DEBUG - Has root graph:', !!data.root_graph_id)
      console.log('🚨 RESTORE DEBUG - Overall goal:', data.overall_project_goal?.substring(0, 100))
      
      // Log details about nodes
      if (data.all_nodes) {
        const nodeEntries = Object.entries(data.all_nodes)
        console.log('🚨 RESTORE DEBUG - First few nodes:')
        nodeEntries.slice(0, 3).forEach(([nodeId, nodeData]: [string, any]) => {
          console.log(`  - ${nodeId}: status=${nodeData.status}, layer=${nodeData.layer}, has_full_result=${!!nodeData.full_result}`)
          
          // Special logging for root node
          if (nodeData.layer === 0 && !nodeData.parent_node_id) {
            console.log('🚨 RESTORE DEBUG - ROOT NODE FOUND:', {
              task_id: nodeData.task_id,
              status: nodeData.status,
              has_full_result: !!nodeData.full_result,
              has_execution_details: !!nodeData.execution_details,
              full_result_preview: nodeData.full_result?.substring(0, 200)
            })
          }
        })
      }
      
      try {
        const projectId = data.project_id
        if (projectId) {
          console.log('🔄 Restoring project data for:', projectId)
          
          // FIXED: Access stores directly instead of using this.getStores()
          const taskGraphStore = useTaskGraphStore.getState()
          
          // Store the restored data
          taskGraphStore.setProjectData(projectId, data)
          
          // If this is the current project, also update display
          if (projectId === taskGraphStore.currentProjectId) {
            console.log('🔄 Updating display with restored data')
            taskGraphStore.setData(data)
            
            // VERIFICATION: Check if the data was properly restored
            setTimeout(() => {
              const currentState = useTaskGraphStore.getState()
              const nodeCount = Object.keys(currentState.nodes).length
              const rootNode = Object.values(currentState.nodes).find(
                (node: any) => node.layer === 0 && !node.parent_node_id
              )
              
              console.log('✅ RESTORE VERIFICATION:', {
                nodeCount,
                hasRootNode: !!rootNode,
                rootNodeStatus: rootNode?.status,
                rootNodeHasFullResult: !!(rootNode as any)?.full_result
              })
              
              if (rootNode && (rootNode as any).full_result) {
                console.log('✅ ROOT NODE FULL RESULT RESTORED SUCCESSFULLY')
              } else {
                console.error('❌ ROOT NODE FULL RESULT NOT RESTORED')
                
                // CRITICAL: If no results found, suggest re-execution
                console.warn('🚨 SUGGESTION: Project appears to have no execution results. Consider re-running the project.')
              }
            }, 100)
          }
          
          console.log('✅ Restored and switched to current project:', projectId)
        }
      } catch (error) {
        console.error('❌ Error handling project restoration:', error)
      }
    })

    this.socket.on('project_restore_error', (data) => {
      console.error('❌ Project restore error:', data)
    })

    // CRITICAL FIX: Enhanced connection handler with state recovery
    this.socket.on('connect', () => {
      console.log('🔌 Connected to WebSocket')
      useTaskGraphStore.getState().setConnectionStatus(true)
      
      // Clear connection stable timer
      if (this.connectionStableTimer) {
        clearTimeout(this.connectionStableTimer)
      }
      
      // CRITICAL FIX: Aggressive state recovery after connection
      this.connectionStableTimer = setTimeout(() => {
        const taskGraphStore = useTaskGraphStore.getState()
        const projectStore = useProjectStore.getState()
        const currentProjectId = projectStore.currentProjectId || taskGraphStore.currentProjectId
        
        console.log('🔄 CONNECTION RECOVERY - Current project:', currentProjectId)
        
        if (currentProjectId) {
          console.log('🔄 Requesting project state restoration for:', currentProjectId)
          
          // First, try to restore from localStorage
          try {
            const backupData = localStorage.getItem(`project_${currentProjectId}_backup`)
            if (backupData) {
              const parsedData = JSON.parse(backupData)
              console.log('🔄 Restored from localStorage backup during reconnection')
              taskGraphStore.setProjectData(currentProjectId, parsedData)
              taskGraphStore.switchToProject(currentProjectId)
            }
          } catch (error) {
            console.warn('Failed to restore from localStorage during reconnection:', error)
          }
          
          // Then request from server
          this.requestProjectRestore(currentProjectId)
        } else {
          console.log('📋 Requesting initial state (no current project)')
          this.socket?.emit('request_initial_state')
        }
      }, 1000)
    })
  }

  private handleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('❌ Max reconnection attempts reached')
      return
    }

    this.reconnectAttempts++
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000)
    
    console.log(`🔄 Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`)
    
    this.reconnectTimer = setTimeout(() => {
      this.connect()
    }, delay)
  }

  isConnected(): boolean {
    return this.socket?.connected || false
  }

  sendHITLResponse(response: HITLResponse) {
    if (this.socket && this.isConnected()) {
      console.log('📤 Sending HITL response:', response)
      this.socket.emit('hitl_response', response)
    } else {
      console.error('❌ Cannot send HITL response: not connected')
    }
  }

  async checkSystemReadiness(): Promise<boolean> {
    return new Promise((resolve) => {
      if (!this.socket || !this.isConnected()) {
        resolve(false)
        return
      }

      const timeout = setTimeout(() => {
        resolve(false)
      }, 5000)

      this.socket.emit('check_readiness', {}, (response: any) => {
        clearTimeout(timeout)
        resolve(response?.ready === true)
      })
    })
  }

  startProject(projectGoal: string, maxSteps: number = 250) {
    if (this.socket && this.isConnected()) {
      console.log('🚀 Starting project via WebSocket:', { projectGoal, maxSteps })
      useTaskGraphStore.getState().setLoading(true)
      
      this.socket.emit('start_project', {
        goal: projectGoal,
        max_steps: maxSteps
      })
    } else {
      console.error('❌ Cannot start project: WebSocket not connected')
      useTaskGraphStore.getState().setLoading(false)
    }
  }

  disconnect() {
    console.log('🔌 Disconnecting WebSocket')
    
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    
    if (this.connectionStableTimer) {
      clearTimeout(this.connectionStableTimer)
      this.connectionStableTimer = null
    }
    
    if (this.socket) {
      this.socket.disconnect()
      this.socket = null
    }
    
    useTaskGraphStore.getState().setConnectionStatus(false)
    this.isConnecting = false
    this.reconnectAttempts = 0
  }

  getConnectionInfo() {
    return {
      connected: this.isConnected(),
      reconnectAttempts: this.reconnectAttempts,
      lastUpdateTime: this.lastUpdateTime,
      updateCount: this.updateCount,
      hasEverConnected: this.hasEverConnected
    }
  }

  simulateBackendUpdate() {
    console.log('🧪 Simulating backend update...')
    
    const mockData = {
      all_nodes: {
        'mock-node-1': {
          task_id: 'mock-node-1',
          goal: 'Mock task 1',
          status: 'DONE',
          task_type: 'SEARCH',
          node_type: 'EXECUTE',
          layer: 0,
          timestamp_created: new Date().toISOString(),
          timestamp_completed: new Date().toISOString(),
          result: 'Mock result 1'
        },
        'mock-node-2': {
          task_id: 'mock-node-2',
          goal: 'Mock task 2',
          status: 'RUNNING',
          task_type: 'WRITE',
          node_type: 'EXECUTE',
          layer: 1,
          timestamp_created: new Date().toISOString(),
          result: 'Mock result 2'
        }
      },
      graphs: {},
      overall_project_goal: 'Mock project goal'
    }
    
    useTaskGraphStore.getState().setData(mockData)
    console.log('✅ Mock data applied to store')
  }

  // NEW: Simulate project-aware backend update
  simulateProjectUpdate(projectId: string) {
    console.log('🧪 Simulating project-specific backend update for:', projectId)
    
    const mockData = {
      all_nodes: {
        [`${projectId}-node-1`]: {
          task_id: `${projectId}-node-1`,
          goal: `Task 1 for ${projectId}`,
          status: 'DONE',
          task_type: 'SEARCH',
          node_type: 'EXECUTE',
          layer: 0,
          timestamp_created: new Date().toISOString(),
          timestamp_completed: new Date().toISOString(),
          result: `Result 1 for ${projectId}`
        },
        [`${projectId}-node-2`]: {
          task_id: `${projectId}-node-2`,
          goal: `Task 2 for ${projectId}`,
          status: 'RUNNING',
          task_type: 'WRITE',
          node_type: 'EXECUTE',
          layer: 1,
          timestamp_created: new Date().toISOString(),
          result: `Result 2 for ${projectId}`
        }
      },
      graphs: {},
      overall_project_goal: `Goal for ${projectId}`,
      project_id: projectId
    }
    
    // Simulate the project-aware update
    const taskGraphStore = useTaskGraphStore.getState()
    taskGraphStore.setProjectData(projectId, mockData)
    
    // If this is the current project, also update display
    if (projectId === taskGraphStore.currentProjectId) {
      taskGraphStore.setData(mockData)
    }
    
    console.log('✅ Project-specific mock data applied to store')
  }

  triggerTestHITL() {
    console.log('🧪 Triggering test HITL...')
    
    const testRequest = {
      request_id: 'manual-test-' + Date.now(),
      checkpoint_name: 'ManualTestCheckpoint',
      context_message: 'This is a manually triggered test HITL request',
      data_for_review: { 
        test: true, 
        source: 'manual',
        timestamp: new Date().toISOString()
      },
      node_id: 'manual-test-node',
      current_attempt: 1,
      timestamp: new Date().toISOString()
    }
    
    console.log('🧪 Triggering manual test HITL request:', testRequest)
    useTaskGraphStore.getState().setHITLRequest(testRequest)
  }

  // UPDATED: Project-aware switching
  switchProject(projectId: string) {
    if (this.socket && this.isConnected()) {
      console.log('🔄 Switching project via WebSocket:', projectId)
      this.socket.emit('switch_project', { project_id: projectId })
    } else {
      console.error('❌ Cannot switch project: WebSocket not connected')
    }
  }

  requestProjectRestore(projectId: string) {
    if (this.socket && this.isConnected()) {
      console.log('🔄 Requesting project restoration:', projectId)
      this.socket.emit('request_project_restore', { project_id: projectId })
    } else {
      console.warn('Cannot request project restore: WebSocket not connected')
    }
  }

  // Add socket property for external access
  get socket() {
    return this.socket
  }

  // NEW: Auto-save project data for persistence
  private autoSaveProjectData(projectId: string, data: any) {
    try {
      const timestamp = new Date().toISOString()
      const saveData = {
        ...data,
        saved_at: timestamp,
        auto_saved: true
      }
      
      // Save to localStorage as backup
      localStorage.setItem(`project_${projectId}_backup`, JSON.stringify(saveData))
      
      // Also try to save to backend (non-blocking)
      if (this.isConnected()) {
        this.socket?.emit('auto_save_project', {
          project_id: projectId,
          data: saveData
        })
      }
      
      console.log('💾 Auto-saved project data for:', projectId)
    } catch (error) {
      console.warn('Failed to auto-save project data:', error)
    }
  }

  // NEW: Add method to re-run project execution
  rerunProject(projectId: string) {
    if (this.socket && this.isConnected()) {
      console.log('🚨 RE-RUN - Triggering project re-execution:', projectId)
      
      // Get project details
      const projectStore = useProjectStore.getState()
      const project = projectStore.projects.find(p => p.id === projectId)
      
      if (project) {
        console.log('🚨 RE-RUN - Project goal:', project.goal)
        
        // Clear any existing state first
        const taskGraphStore = useTaskGraphStore.getState()
        taskGraphStore.clearProjectData(projectId)
        
        // Start fresh execution
        this.socket.emit('start_project_execution', {
          project_id: projectId,
          goal: project.goal,
          max_steps: project.max_steps || 250
        })
        
        // Set loading state
        taskGraphStore.setLoading(true)
        
        console.log('🚨 RE-RUN - Execution request sent')
      } else {
        console.error('❌ RE-RUN - Project not found:', projectId)
      }
    } else {
      console.error('❌ RE-RUN - WebSocket not connected')
    }
  }

  // NEW: Add method to force save current project
  forceSaveCurrentProject() {
    const taskGraphStore = useTaskGraphStore.getState()
    const projectStore = useProjectStore.getState()
    const currentProjectId = projectStore.currentProjectId || taskGraphStore.currentProjectId
    
    if (currentProjectId && this.socket && this.isConnected()) {
      console.log('🚨 FORCE SAVE - Manually saving current project:', currentProjectId)
      this.socket.emit('force_save_project', { project_id: currentProjectId })
    } else {
      console.error('❌ Cannot force save: no current project or not connected')
    }
  }

  // NEW: Add method to force restore current project
  forceRestoreCurrentProject() {
    const taskGraphStore = useTaskGraphStore.getState()
    const projectStore = useProjectStore.getState()
    const currentProjectId = projectStore.currentProjectId || taskGraphStore.currentProjectId
    
    if (currentProjectId) {
      console.log('🚨 FORCE RESTORE - Manually restoring current project:', currentProjectId)
      this.requestProjectRestore(currentProjectId)
    } else {
      console.error('❌ Cannot force restore: no current project')
    }
  }

  constructor() {
    // ... existing code ...
    
    // Make the service available globally for debugging
    if (typeof window !== 'undefined') {
      (window as any).websocketService = this
    }
  }
}

// Create singleton instance
export const webSocketService = new WebSocketService()

// Enhanced profile events setup
export const setupProfileEvents = (socket: any, profileStore: any) => {
  socket.on('profile_switched', (data: any) => {
    console.log('👤 Profile switched:', data)
    if (data.profile_name) {
      profileStore.getState().setCurrentProfile(data.profile_name)
    }
  })

  socket.on('profile_switch_error', (data: any) => {
    console.error('❌ Profile switch error:', data)
  })

  socket.on('profiles_updated', (data: any) => {
    console.log('👥 Profiles updated:', data)
    if (data.profiles) {
      profileStore.getState().setProfiles(data.profiles)
    }
  })
}

// Auto-connect when module loads
if (typeof window !== 'undefined') {
  // Add global debugging functions
  const globalWindow = window as any
  
  globalWindow.webSocketService = webSocketService
  globalWindow.connectWebSocket = () => webSocketService.connect()
  globalWindow.disconnectWebSocket = () => webSocketService.disconnect()
  globalWindow.getWebSocketInfo = () => webSocketService.getConnectionInfo()
  globalWindow.simulateUpdate = () => webSocketService.simulateBackendUpdate()
  globalWindow.triggerTestHITL = () => webSocketService.triggerTestHITL()
  
  // NEW: Project-specific debugging functions
  globalWindow.switchProjectWS = (projectId: string) => webSocketService.switchProject(projectId)
  globalWindow.restoreProjectWS = (projectId: string) => webSocketService.requestProjectRestore(projectId)
  globalWindow.simulateProjectUpdate = (projectId: string) => webSocketService.simulateProjectUpdate(projectId)
}

// Make the service available globally for debugging
if (typeof window !== 'undefined') {
  (window as any).websocketService = this
} 