import { io, Socket } from 'socket.io-client'
import { useTaskGraphStore } from '@/stores/taskGraphStore'
import type { APIResponse, HITLRequest, HITLResponse } from '@/types'

class WebSocketService {
  private socket: Socket | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 10
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private isConnecting = false
  private lastUpdateTime = 0
  private updateCount = 0
  private connectionStableTimer: ReturnType<typeof setTimeout> | null = null

  connect() {
    if (this.isConnecting || this.isConnected()) {
      console.log('⚠️ Already connecting or connected')
      return
    }

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
      console.log('🤔 Received HITL request:', request)
      try {
        // Add to HITL logs
        useTaskGraphStore.getState().addHITLLog({
          checkpoint_name: request.checkpoint_name,
          context_message: request.context_message,
          node_id: request.node_id,
          current_attempt: request.current_attempt,
          timestamp: request.timestamp || new Date().toISOString(),
          request_id: request.request_id || Math.random().toString(36)
        })
        
        // Also set for modal (when we implement it)
        useTaskGraphStore.getState().setHITLRequest(request)
      } catch (error) {
        console.error('❌ Error processing HITL request:', error)
      }
    })

    // Add test event handler for debugging
    this.socket.on('hitl_test', (data) => {
      console.log('🧪 Received HITL test event:', data)
    })

    this.socket.on('project_started', (data) => {
      console.log('🚀 Project started confirmation:', data)
      useTaskGraphStore.getState().setLoading(false)
    })

    this.socket.on('error', (error) => {
      console.error('❌ Socket error:', error)
      useTaskGraphStore.getState().setLoading(false)
    })

    // Debug: Log ALL WebSocket events
    this.socket.onAny((eventName, ...args) => {
      console.log(`🔊 WebSocket event received: "${eventName}"`, args)
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

  startProject(projectGoal: string, maxSteps: number = 250) {
    if (this.isConnected()) {
      console.log('📤 Starting project:', projectGoal)
      useTaskGraphStore.getState().setLoading(true)
      this.socket!.emit('start_project', { project_goal: projectGoal, max_steps: maxSteps })
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
}

export const webSocketService = new WebSocketService() 