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
      transports: ['websocket', 'polling'],
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

    // CRITICAL: Real-time task graph updates
    this.socket.on('task_graph_update', (data: APIResponse) => {
      const now = Date.now()
      this.updateCount++
      
      console.log(`🚨🚨🚨 [UPDATE ${this.updateCount}] WEBSOCKET RECEIVED REAL UPDATE FROM BACKEND`)
      console.log('📊 Raw data:', data)
      console.log('📊 Nodes in data:', Object.keys(data.all_nodes || {}).length)
      console.log('📊 First few node IDs:', Object.keys(data.all_nodes || {}).slice(0, 3))
      
      this.lastUpdateTime = now
      
      try {
        console.log('🔄 Calling store.setData with WebSocket data...')
        useTaskGraphStore.getState().setData(data)
        console.log('✅ Store.setData completed')
      } catch (error) {
        console.error('❌ ERROR in WebSocket handler:', error)
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

    // Enhanced project switching events
    this.socket.on('project_switched', (data) => {
      console.log('🔄 Project switched:', data)
      
      // Update task graph with new project data
      if (data.project_data) {
        useTaskGraphStore.getState().setData(data.project_data)
      }
      
      // Update project store
      if (data.project_id) {
        useProjectStore.getState().setCurrentProject(data.project_id)
      }
    })

    this.socket.on('project_switch_success', (data) => {
      console.log('✅ Project switch successful:', data)
      
      // Update task graph with new project data
      if (data.project_data) {
        useTaskGraphStore.getState().setData(data.project_data)
      }
    })

    this.socket.on('project_switch_error', (data) => {
      console.error('❌ Project switch error:', data)
      // Could emit a toast notification here
    })

    this.socket.on('project_restored', (data) => {
      console.log('🔄 Project state restored:', data)
      useTaskGraphStore.getState().setData(data)
    })

    this.socket.on('project_restore_error', (data) => {
      console.error('❌ Project restore error:', data)
    })

    // Enhanced connection handler for state recovery
    this.socket.on('connect', () => {
      console.log('🔌 Connected to WebSocket')
      useTaskGraphStore.getState().setConnectionStatus(true)
      
      // Clear connection stable timer
      if (this.connectionStableTimer) {
        clearTimeout(this.connectionStableTimer)
      }
      
      // Request current project state restoration after a brief delay
      this.connectionStableTimer = setTimeout(() => {
        const currentProjectId = useProjectStore.getState().currentProjectId
        if (currentProjectId) {
          console.log('🔄 Requesting project state restoration for:', currentProjectId)
          this.requestProjectRestore(currentProjectId)
        } else {
          console.log('📋 Requesting initial state (no current project)')
          this.socket?.emit('request_initial_state')
        }
      }, 500) // Small delay to ensure connection is stable
    })
  }

  private handleReconnect() {
    if (this.isConnecting) {
      console.log('⚠️ Already attempting to reconnect')
      return
    }

    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++
      const delay = Math.min(1000 * Math.pow(1.5, this.reconnectAttempts - 1), 10000)
      
      console.log(`🔄 Attempting to reconnect... (${this.reconnectAttempts}/${this.maxReconnectAttempts}) in ${delay}ms`)
      
      this.reconnectTimer = setTimeout(() => {
        this.reconnectTimer = null
        this.connect()
      }, delay)
    } else {
      console.error('❌ Max reconnection attempts reached')
      useTaskGraphStore.getState().setConnectionStatus(false)
    }
  }

  isConnected(): boolean {
    return this.socket?.connected ?? false
  }

  sendHITLResponse(response: HITLResponse) {
    if (this.isConnected()) {
      console.log('📤 Sending HITL response:', response)
      this.socket!.emit('hitl_response', response)
    } else {
      console.error('❌ Cannot send HITL response: not connected')
    }
  }

  async checkSystemReadiness(): Promise<boolean> {
    try {
      const response = await fetch('/api/system/readiness')
      const data = await response.json()
      
      if (data.ready) {
        console.log('✅ System is ready for execution')
        return true
      } else {
        console.log('⚠️ System not ready:', data.components)
        return false
      }
    } catch (error) {
      console.error('❌ Failed to check system readiness:', error)
      return false
    }
  }

  startProject(projectGoal: string, maxSteps: number = 250) {
    if (this.isConnected()) {
      console.log('📤 Starting project:', projectGoal)
      
      // Check system readiness before starting
      this.checkSystemReadiness().then(ready => {
        if (!ready) {
          console.warn('⚠️ System may not be fully ready - HITL requests might be auto-approved')
        }
        
        useTaskGraphStore.getState().setLoading(true)
        this.socket!.emit('start_project', { project_goal: projectGoal, max_steps: maxSteps })
      })
    } else {
      console.error('❌ Cannot start project: not connected')
      useTaskGraphStore.getState().setLoading(false)
    }
  }

  disconnect() {
    console.log('🔌 Disconnecting WebSocket')
    
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    
    if (this.socket) {
      this.socket.removeAllListeners()
      this.socket.disconnect()
      this.socket = null
    }
    
    this.isConnecting = false
    this.reconnectAttempts = 0
    useTaskGraphStore.getState().setConnectionStatus(false)
  }

  getConnectionInfo() {
    return {
      connected: this.isConnected(),
      connecting: this.isConnecting,
      reconnectAttempts: this.reconnectAttempts,
      lastUpdate: this.lastUpdateTime,
      updateCount: this.updateCount
    }
  }

  // Test method to manually simulate a backend update
  simulateBackendUpdate() {
    console.log('🧪 SIMULATING BACKEND UPDATE...')
    const nodeId = 'sim-' + Date.now()
    const testData: APIResponse = {
      all_nodes: {
        [nodeId]: {
          task_id: nodeId,
          goal: 'Simulated backend node update',
          task_type: 'SIMULATION',
          node_type: 'EXECUTE',
          layer: 0,
          status: 'DONE',
        }
      },
      graphs: {},
      overall_project_goal: 'Simulated project'
    }
    
    console.log('🧪 Manually triggering task_graph_update handler with:', testData)
    
    // Manually call the handler as if the backend sent this
    const handler = this.socket?.listeners('task_graph_update')[0]
    if (handler) {
      console.log('🧪 Calling handler directly...')
      handler(testData)
    } else {
      console.log('🧪 No handler found, calling setData directly...')
      useTaskGraphStore.getState().setData(testData)
    }
  }

  // AGGRESSIVE DEBUGGING: Add method to trigger test HITL
  triggerTestHITL() {
    console.log('🧪 Manually triggering test HITL request')
    const testRequest = {
      request_id: 'manual-test-' + Date.now(),
      checkpoint_name: 'ManualTestCheckpoint',
      context_message: 'This is a manually triggered test HITL request',
      data_for_review: { 
        test: true, 
        timestamp: new Date().toISOString(),
        message: 'Manual test from frontend'
      },
      node_id: 'manual-test-node',
      current_attempt: 1,
      timestamp: new Date().toISOString()
    }
    
    console.log('🧪 Setting manual test HITL request:', testRequest)
    useTaskGraphStore.getState().setHITLRequest(testRequest)
    
    // Also emit to server for testing
    if (this.isConnected()) {
      this.socket!.emit('hitl_test_trigger', testRequest)
    }
  }

  // New methods for project operations
  switchProject(projectId: string) {
    if (this.isConnected()) {
      console.log('🔄 Switching project via WebSocket:', projectId)
      this.socket!.emit('switch_project', { project_id: projectId })
    } else {
      console.error('❌ Cannot switch project: not connected')
    }
  }

  requestProjectRestore(projectId: string) {
    if (this.isConnected()) {
      console.log('🔄 Requesting project restore:', projectId)
      this.socket!.emit('restore_project_state', { project_id: projectId })
    } else {
      console.error('❌ Cannot restore project: not connected')
    }
  }
}

// Export singleton instance
export const webSocketService = new WebSocketService()

// AGGRESSIVE DEBUGGING: Add global access for testing - Fix the window check
if (typeof window !== 'undefined' && window) {
  const globalWindow = window as any
  
  globalWindow.webSocketService = webSocketService
  globalWindow.triggerTestHITL = () => webSocketService.triggerTestHITL()
  globalWindow.getHITLState = () => {
    const state = useTaskGraphStore.getState()
    return {
      hitlRequest: state.hitlRequest,
      currentHITLRequest: state.currentHITLRequest,
      isHITLModalOpen: state.isHITLModalOpen,
      hitlLogs: state.hitlLogs
    }
  }
}

// Add profile-related event handlers
export const setupProfileEvents = (socket: any, profileStore: any) => {
  // Listen for profile changes
  socket.on('profile_changed', (data: any) => {
    console.log('🔄 Profile changed:', data)
    profileStore.setCurrentProfile(data.profile)
    // Reload profiles to get updated state
    profileStore.loadProfiles()
  })

  // Listen for profile switch success
  socket.on('profile_switch_success', (data: any) => {
    console.log('✅ Profile switch successful:', data)
  })

  // Listen for profile switch errors
  socket.on('profile_switch_error', (data: any) => {
    console.error('❌ Profile switch error:', data)
    profileStore.setError(data.error)
  })

  // Listen for profiles list updates
  socket.on('profiles_list', (data: any) => {
    console.log('📋 Profiles list received:', data)
    profileStore.setProfiles(data.profiles)
    profileStore.setCurrentProfile(data.current_profile)
  })

  // Listen for profile errors
  socket.on('profiles_error', (data: any) => {
    console.error('❌ Profiles error:', data)
    profileStore.setError(data.error)
  })
} 