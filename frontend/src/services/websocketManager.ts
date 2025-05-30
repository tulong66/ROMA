import { webSocketService } from './websocketService'

// Create a new file for better WebSocket management
class WebSocketManager {
  private static instance: WebSocketManager
  private initialized = false
  
  static getInstance(): WebSocketManager {
    if (!WebSocketManager.instance) {
      WebSocketManager.instance = new WebSocketManager()
    }
    return WebSocketManager.instance
  }
  
  initialize() {
    if (!this.initialized) {
      console.log('🔌 WebSocketManager: Initializing connection')
      webSocketService.connect()
      this.initialized = true
      
      // Add window event listeners to handle page lifecycle
      window.addEventListener('beforeunload', () => {
        console.log('🔌 WebSocketManager: Page unloading, disconnecting')
        webSocketService.disconnect()
      })
    }
  }
  
  isInitialized() {
    return this.initialized
  }
}

export const wsManager = WebSocketManager.getInstance() 