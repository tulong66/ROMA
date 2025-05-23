import React, { useEffect } from 'react'
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
    isHITLModalOpen 
  } = useTaskGraphStore()

  useEffect(() => {
    // Initialize WebSocket connection
    webSocketService.connect()
    
    // Cleanup on unmount
    return () => {
      webSocketService.disconnect()
    }
  }, [])

  const hasNodes = Object.keys(nodes).length > 0

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
            {hasNodes ? (
              <GraphVisualization />
            ) : (
              <div className="flex items-center justify-center h-full">
                <ProjectInput />
              </div>
            )}
          </div>
        </div>
        
        {/* Node Details Panel */}
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