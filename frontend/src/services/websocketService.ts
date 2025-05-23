import { io, Socket } from 'socket.io-client'
import { useTaskGraphStore } from '@/stores/taskGraphStore'
import type { APIResponse, HITLRequest, HITLResponse } from '@/types'

class WebSocketService {
  private socket: Socket | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectTimer: NodeJS.Timeout | null = null
  private isConnecting = false

  connect() {
    // Prevent multiple connection attempts
    if (this.isConnecting || this.socket?.connected) {
      console.log('⚠️ Already connecting or connected')
      return
    }

    this.isConnecting = true
    console.log('🔌 Attempting to connect to WebSocket at http://localhost:5000')
    
    // Clear any existing timer
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }

    this.socket = io('http://localhost:5000', {
      transports: ['websocket', 'polling'],
      autoConnect: true,
      forceNew: false, // Changed from true to false
      timeout: 10000, // Increased timeout
      reconnection: true,
      reconnectionAttempts: 3,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
    })

    this.setupEventListeners()
  }

  private setupEventListeners() {
    if (!this.socket) return

    // Remove any existing listeners to prevent duplicates
    this.socket.removeAllListeners()

    this.socket.on('connect', () => {
      console.log('✅ WebSocket connected successfully')
      this.isConnecting = false
      useTaskGraphStore.getState().setConnectionStatus(true)
      this.reconnectAttempts = 0
      
      // Clear reconnect timer on successful connection
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer)
        this.reconnectTimer = null
      }
    })

    this.socket.on('disconnect', (reason) => {
      console.log('❌ WebSocket disconnected:', reason)
      this.isConnecting = false
      useTaskGraphStore.getState().setConnectionStatus(false)
      
      // Only attempt reconnection for certain disconnect reasons
      if (reason === 'io server disconnect' || reason === 'transport close') {
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

    this.socket.on('task_graph_update', (data: APIResponse) => {
      console.log('📊 Received task graph update:', data)
      try {
        useTaskGraphStore.getState().setData(data)
      } catch (error) {
        console.error('❌ Error processing task graph update:', error)
      }
    })

    this.socket.on('hitl_request', (request: HITLRequest) => {
      console.log('🤔 Received HITL request:', request)
      try {
        useTaskGraphStore.getState().setHITLRequest(request)
      } catch (error) {
        console.error('❌ Error processing HITL request:', error)
      }
    })

    this.socket.on('project_started', (data) => {
      console.log('🚀 Project started confirmation:', data)
    })

    this.socket.on('error', (error) => {
      console.error('❌ Socket error:', error)
      useTaskGraphStore.getState().setLoading(false)
    })
  }

  private handleReconnect() {
    if (this.isConnecting) {
      console.log('⚠️ Already attempting to reconnect')
      return
    }

    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++
      const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts - 1), 5000)
      
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
      this.socket!.emit('start_project', { project_goal: projectGoal, max_steps: maxSteps })
    } else {
      console.error('❌ Cannot start project: not connected')
      useTaskGraphStore.getState().setLoading(false)
    }
  }

  disconnect() {
    console.log('🔌 Disconnecting WebSocket')
    
    // Clear reconnect timer
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    
    // Disconnect socket
    if (this.socket) {
      this.socket.removeAllListeners()
      this.socket.disconnect()
      this.socket = null
    }
    
    this.isConnecting = false
    this.reconnectAttempts = 0
    useTaskGraphStore.getState().setConnectionStatus(false)
  }
}

export const webSocketService = new WebSocketService() 