import { io, Socket } from 'socket.io-client'
import { useTaskGraphStore } from '@/stores/taskGraphStore'
import type { APIResponse, HITLRequest, HITLResponse } from '@/types'

class WebSocketService {
  private socket: Socket | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5

  connect() {
    if (this.socket?.connected) {
      console.log('Already connected')
      return
    }

    console.log('Attempting to connect to WebSocket at http://localhost:5000')
    
    this.socket = io('http://localhost:5000', {
      transports: ['websocket', 'polling'], // Try both transports
      autoConnect: true,
      forceNew: true,
      timeout: 5000,
    })

    this.setupEventListeners()
  }

  private setupEventListeners() {
    if (!this.socket) return

    this.socket.on('connect', () => {
      console.log('✅ WebSocket connected successfully')
      useTaskGraphStore.getState().setConnectionStatus(true)
      this.reconnectAttempts = 0
    })

    this.socket.on('disconnect', (reason) => {
      console.log('❌ WebSocket disconnected:', reason)
      useTaskGraphStore.getState().setConnectionStatus(false)
    })

    this.socket.on('connect_error', (error) => {
      console.error('❌ WebSocket connection error:', error)
      useTaskGraphStore.getState().setConnectionStatus(false)
      this.handleReconnect()
    })

    this.socket.on('task_graph_update', (data: APIResponse) => {
      console.log('📊 Received task graph update:', data)
      useTaskGraphStore.getState().setData(data)
    })

    this.socket.on('hitl_request', (request: HITLRequest) => {
      console.log('🤔 Received HITL request:', request)
      useTaskGraphStore.getState().setHITLRequest(request)
    })

    this.socket.on('project_started', (data) => {
      console.log('🚀 Project started:', data)
    })

    this.socket.on('error', (error) => {
      console.error('❌ Socket error:', error)
    })
  }

  private handleReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++
      console.log(`🔄 Attempting to reconnect... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`)
      setTimeout(() => {
        this.connect()
      }, 1000 * this.reconnectAttempts)
    } else {
      console.error('❌ Max reconnection attempts reached')
    }
  }

  sendHITLResponse(response: HITLResponse) {
    if (this.socket?.connected) {
      console.log('📤 Sending HITL response:', response)
      this.socket.emit('hitl_response', response)
    } else {
      console.error('❌ Cannot send HITL response: not connected')
    }
  }

  startProject(projectGoal: string, maxSteps: number = 250) {
    if (this.socket?.connected) {
      console.log('📤 Starting project:', projectGoal)
      this.socket.emit('start_project', { project_goal: projectGoal, max_steps: maxSteps })
    } else {
      console.error('❌ Cannot start project: not connected')
    }
  }

  disconnect() {
    if (this.socket) {
      console.log('🔌 Disconnecting WebSocket')
      this.socket.disconnect()
      this.socket = null
    }
  }
}

export const webSocketService = new WebSocketService() 