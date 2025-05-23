import React, { useEffect, useState, useCallback } from 'react'
import { useTaskGraphStore } from '@/stores/taskGraphStore'
import { webSocketService } from '@/services/websocketService'
import Header from './Header'
import GraphVisualization from '@/components/graph/GraphVisualization'
import NodeDetailsPanel from '@/components/panels/NodeDetailsPanel'
import ComparisonPanel from '@/components/panels/ComparisonPanel'
import MultiSelectToolbar from '@/components/panels/MultiSelectToolbar'
import ProjectInput from '@/components/project/ProjectInput'
import HITLModal from '@/components/hitl/HITLModal'
import ConnectionStatus from '@/components/status/ConnectionStatus'

const MainLayout: React.FC = () => {
  const { 
    isConnected, 
    nodes, 
    overallProjectGoal,
    isHITLModalOpen,
    isLoading,
    selectedNodeIds,
    isComparisonPanelOpen
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
  const hasMultipleSelected = selectedNodeIds.size > 1
  
  console.log('MainLayout render:', { 
    hasNodes, 
    nodeCount: Object.keys(nodes).length, 
    isConnected,
    isLoading 
  })

  // 🚨 FIX: Show ProjectInput when no nodes and not loading
  if (!hasNodes && !isLoading) {
    return (
      <div className="h-screen flex flex-col bg-background">
        <Header />
        
        <main className="flex-1 overflow-hidden">
          <div className="h-full flex items-center justify-center">
            <ProjectInput />
          </div>
        </main>
        
        {/* Status Components */}
        <ConnectionStatus />
        
        {/* HITL Modal */}
        {isHITLModalOpen && <HITLModal />}
      </div>
    )
  }

  return (
    <div className="h-screen flex flex-col bg-background">
      <Header />
      
      {/* Multi-Selection Toolbar */}
      {hasNodes && <MultiSelectToolbar />}
      
      <main className="flex-1 overflow-hidden">
        <div className="h-full grid grid-cols-1 lg:grid-cols-[1fr_400px] gap-4 p-4">
          <div className="h-full">
            <GraphVisualization />
          </div>
          <div className="h-full space-y-4 overflow-y-auto">
            {/* Project Goal Display */}
            {overallProjectGoal && (
              <div className="border-b bg-muted/30 px-6 py-4">
                <div className="text-sm text-muted-foreground">Current Project Goal</div>
                <div className="text-lg font-medium">{overallProjectGoal}</div>
              </div>
            )}
            
            {/* Comparison Panel (when multiple nodes selected) */}
            {isComparisonPanelOpen && hasMultipleSelected && <ComparisonPanel />}
            
            {/* Node Details Panel (when single node selected) */}
            {!isComparisonPanelOpen && <NodeDetailsPanel />}
          </div>
        </div>
      </main>
      
      {/* Status Components */}
      <ConnectionStatus />
      
      {/* HITL Modal */}
      {isHITLModalOpen && <HITLModal />}
    </div>
  )
}

export default MainLayout 