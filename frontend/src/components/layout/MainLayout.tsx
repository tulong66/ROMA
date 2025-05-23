import React, { useEffect, useState, useCallback } from 'react'
import { useTaskGraphStore } from '@/stores/taskGraphStore'
import { webSocketService } from '@/services/websocketService'
import Header from './Header'
import GraphVisualization from '@/components/graph/GraphVisualization'
import NodeDetailsPanel from '@/components/panels/NodeDetailsPanel'
import ProjectInput from '@/components/project/ProjectInput'
import HITLModal from '@/components/hitl/HITLModal'
import ConnectionStatus from '@/components/status/ConnectionStatus'

const MainLayout: React.FC = () => {
  const { 
    isConnected, 
    nodes, 
    overallProjectGoal,
    isHITLModalOpen,
    isLoading
  } = useTaskGraphStore()

  const [loadingMessage, setLoadingMessage] = useState('Initializing project...')
  const [loadingDots, setLoadingDots] = useState('')

  // Initialize WebSocket connection once
  useEffect(() => {
    console.log('🔌 MainLayout: Initializing WebSocket connection')
    
    // Only connect if not already connected
    if (!webSocketService.isConnected()) {
      webSocketService.connect()
    }
    
    // Cleanup on unmount
    return () => {
      console.log('🔌 MainLayout: Cleaning up WebSocket connection')
      webSocketService.disconnect()
    }
  }, []) // Empty dependency array - only run once

  // Handle connection status changes
  useEffect(() => {
    console.log('🔌 Connection status changed:', isConnected)
  }, [isConnected])

  // Animated loading dots
  useEffect(() => {
    if (!isLoading) return

    const interval = setInterval(() => {
      setLoadingDots(prev => prev.length >= 3 ? '' : prev + '.')
    }, 500)

    return () => clearInterval(interval)
  }, [isLoading])

  // Update loading message based on time elapsed
  useEffect(() => {
    if (!isLoading) return

    const messages = [
      'Initializing project...',
      'Setting up task framework...',
      'Creating root task...',
      'Planning task decomposition...',
      'Calling AI agents...',
      'Processing initial analysis...'
    ]

    let messageIndex = 0
    setLoadingMessage(messages[0])

    const interval = setInterval(() => {
      messageIndex = (messageIndex + 1) % messages.length
      setLoadingMessage(messages[messageIndex])
    }, 3000)

    return () => clearInterval(interval)
  }, [isLoading])

  const hasNodes = Object.keys(nodes).length > 0
  
  console.log('MainLayout render:', { 
    hasNodes, 
    nodeCount: Object.keys(nodes).length, 
    isConnected,
    isLoading 
  })

  return (
    <div className="h-screen flex flex-col bg-background">
      <Header />
      
      <div className="flex-1 flex overflow-hidden">
        {/* Main Content Area */}
        <div className="flex-1 flex flex-col">
          {/* Project Goal Display */}
          {overallProjectGoal && (
            <div className="border-b bg-muted/30 px-6 py-4">
              <div className="text-sm text-muted-foreground">Current Project Goal</div>
              <div className="text-lg font-medium">{overallProjectGoal}</div>
            </div>
          )}
          
          {/* Graph or Welcome Screen */}
          <div className="flex-1 relative">
            {isLoading ? (
              <div className="flex items-center justify-center h-full">
                <div className="text-center max-w-md">
                  {/* Loading spinner */}
                  <div className="relative mb-6">
                    <div className="animate-spin rounded-full h-12 w-12 border-4 border-muted border-t-primary mx-auto"></div>
                    <div className="absolute inset-0 rounded-full h-12 w-12 border-4 border-primary/20 mx-auto animate-pulse"></div>
                  </div>
                  
                  {/* Loading message */}
                  <h3 className="text-xl font-semibold mb-2">
                    {loadingMessage}{loadingDots}
                  </h3>
                  
                  <p className="text-muted-foreground mb-4">
                    This may take 15-30 seconds as AI agents analyze your project
                  </p>
                  
                  {/* Progress indicators */}
                  <div className="space-y-2 text-sm text-muted-foreground">
                    <div className="flex items-center justify-center space-x-2">
                      <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-primary animate-pulse'}`}></div>
                      <span>{isConnected ? 'Connected to AI systems' : 'Connecting to AI systems'}</span>
                    </div>
                    {overallProjectGoal && (
                      <div className="flex items-center justify-center space-x-2">
                        <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                        <span>Project goal received</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ) : hasNodes ? (
              <GraphVisualization />
            ) : (
              <div className="flex items-center justify-center h-full">
                <ProjectInput />
              </div>
            )}
          </div>
        </div>
        
        {/* Node Details Panel - only show when we have nodes */}
        {hasNodes && <NodeDetailsPanel />}
      </div>
      
      {/* Status Components */}
      <ConnectionStatus />
      
      {/* HITL Modal */}
      {isHITLModalOpen && <HITLModal />}
    </div>
  )
}

export default MainLayout 