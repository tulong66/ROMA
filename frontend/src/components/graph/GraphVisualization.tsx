import React, { useCallback, useEffect, useMemo, useRef } from 'react'
import ReactFlow, {
  Node,
  Edge,
  addEdge,
  Connection,
  useNodesState,
  useEdgesState,
  Controls,
  Background,
  BackgroundVariant,
  NodeTypes,
  EdgeTypes,
  ReactFlowProvider,
  useReactFlow,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { Button } from '@/components/ui/button'

import { useTaskGraphStore } from '@/stores/taskGraphStore'
import TaskNodeComponent from './nodes/TaskNode'
import CustomEdge from './edges/CustomEdge'
import { convertToFlowNodes, convertToFlowEdges } from '@/lib/graphUtils'

const nodeTypes: NodeTypes = {
  taskNode: TaskNodeComponent,
}

const edgeTypes: EdgeTypes = {
  custom: CustomEdge,
}

// Separate the flow content into its own component
const FlowContent: React.FC = () => {
  const { 
    nodes: graphNodes, 
    graphs, 
    selectedNodeId,
    selectedNodeIds,
    selectNode,
    toggleNodeSelection,
    showContextFlow,
    contextFlowMode,
    focusNodeId,
    getFilteredNodes,
    resetFilters
  } = useTaskGraphStore()

  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const { fitView } = useReactFlow()
  
  // Use refs to track previous state for better change detection
  const prevNodeCountRef = useRef(0)
  const lastUpdateRef = useRef(0)
  const isUpdatingRef = useRef(false)
  const updateTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  // Get filtered nodes
  const filteredNodes = getFilteredNodes()

  console.log('🔄 FlowContent render:', {
    totalNodesCount: Object.keys(graphNodes).length,
    filteredNodesCount: Object.keys(filteredNodes).length,
    graphsCount: Object.keys(graphs).length,
    selectedNodeId
  })

  // Create a stable signature that changes less frequently
  const stableGraphSignature = useMemo(() => {
    const nodeEntries = Object.entries(filteredNodes)
    // Only update signature for significant changes
    return {
      nodeCount: nodeEntries.length,
      statusSignature: nodeEntries.map(([id, node]) => `${id}:${node.status}`).sort().join('|'),
      selectedNodeId,
      showContextFlow,
    }
  }, [
    Object.keys(filteredNodes).length,
    // Only update when status actually changes, not on every render
    Object.values(filteredNodes).map(n => n.status).sort().join('|'),
    selectedNodeId,
    showContextFlow
  ])

  // Enhanced node click handler for multi-selection
  const onNodeClick = useCallback(
    (event: React.MouseEvent, node: Node) => {
      try {
        console.log('🖱️ Node clicked:', node.id, 'Multi-select:', event.ctrlKey || event.metaKey)
        
        const isMultiSelect = event.ctrlKey || event.metaKey
        toggleNodeSelection(node.id, isMultiSelect)
      } catch (error) {
        console.error('❌ Error handling node click:', error)
      }
    },
    [toggleNodeSelection]
  )

  const onPaneClick = useCallback(() => {
    try {
      selectNode(undefined)
    } catch (error) {
      console.error('❌ Error handling pane click:', error)
    }
  }, [selectNode])

  const onConnect = useCallback(
    (params: Connection) => {
      try {
        setEdges((eds) => addEdge(params, eds))
      } catch (error) {
        console.error('❌ Error handling connection:', error)
      }
    },
    [setEdges]
  )

  // Convert backend data to React Flow format with multi-selection support
  const flowData = useMemo(() => {
    console.log('🔄 Converting flow data with multi-selection support...')
    try {
      const options = {
        selectedNodeId,
        filteredNodes,
        showContextFlow,
        highlightMode: contextFlowMode,
        focusNodeId
      }
      
      const flowNodes = convertToFlowNodes(graphNodes, options).map(flowNode => ({
        ...flowNode,
        data: {
          ...flowNode.data,
          isMultiSelected: selectedNodeIds.has(flowNode.id)
        }
      }))
      
      const flowEdges = convertToFlowEdges(graphNodes, graphs, options)
      
      console.log('✅ Multi-selection flow data converted:', { 
        nodes: flowNodes.length, 
        edges: flowEdges.length,
        selectedCount: selectedNodeIds.size
      })
      return { nodes: flowNodes, edges: flowEdges }
    } catch (error) {
      console.error('❌ Error converting multi-selection flow data:', error)
      return { nodes: [], edges: [] }
    }
  }, [stableGraphSignature, contextFlowMode, focusNodeId, selectedNodeIds, graphNodes])

  // Much slower update function - only every 2 seconds
  const throttledUpdate = useCallback(() => {
    const now = Date.now()
    const timeSinceLastUpdate = now - lastUpdateRef.current
    const minUpdateInterval = 2000 // 2 seconds minimum between updates

    if (updateTimeoutRef.current) {
      clearTimeout(updateTimeoutRef.current)
    }

    const scheduleUpdate = () => {
      if (isUpdatingRef.current) {
        console.log('⚠️ Update already in progress, skipping')
        return
      }

      const currentNodeCount = Object.keys(filteredNodes).length
      const hasNewNodes = currentNodeCount > prevNodeCountRef.current
      const hasSignificantChange = currentNodeCount !== prevNodeCountRef.current

      // Only update for significant changes or new nodes
      if (hasSignificantChange || hasNewNodes) {
        isUpdatingRef.current = true
        lastUpdateRef.current = now
        
        console.log('🔄 Updating React Flow (throttled):', {
          previousNodes: prevNodeCountRef.current,
          currentNodes: currentNodeCount,
          hasNewNodes,
          timeSinceLastUpdate
        })

        try {
          setNodes(flowData.nodes)
          setEdges(flowData.edges)

          // Auto-fit view when new nodes are added
          if (hasNewNodes && flowData.nodes.length > 0) {
            console.log('🎯 Auto-fitting view for new nodes')
            setTimeout(() => {
              try {
                fitView({ 
                  padding: 0.2, 
                  duration: 800,
                  includeHiddenNodes: false
                })
              } catch (error) {
                console.error('❌ Error fitting view:', error)
              }
            }, 400)
          }

          prevNodeCountRef.current = currentNodeCount
        } catch (error) {
          console.error('❌ Error updating React Flow:', error)
        } finally {
          setTimeout(() => {
            isUpdatingRef.current = false
          }, 500) // Longer delay before allowing next update
        }
      }
    }

    // If enough time has passed, update immediately
    if (timeSinceLastUpdate >= minUpdateInterval) {
      scheduleUpdate()
    } else {
      // Otherwise, schedule for later
      const delay = minUpdateInterval - timeSinceLastUpdate
      console.log(`⏳ Throttling update, will update in ${delay}ms`)
      updateTimeoutRef.current = setTimeout(scheduleUpdate, delay)
    }
  }, [flowData.nodes, flowData.edges, filteredNodes, setNodes, setEdges, fitView])

  // Use throttled update with longer intervals
  useEffect(() => {
    throttledUpdate()
    
    // Cleanup timeout on unmount
    return () => {
      if (updateTimeoutRef.current) {
        clearTimeout(updateTimeoutRef.current)
      }
    }
  }, [throttledUpdate])

  // Show filtered empty state
  if (Object.keys(graphNodes).length > 0 && Object.keys(filteredNodes).length === 0) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-muted/20">
        <div className="text-center max-w-md">
          <h3 className="text-lg font-medium mb-2">No Nodes Match Filters</h3>
          <p className="text-muted-foreground mb-4">
            {Object.keys(graphNodes).length} nodes available, but none match your current filters
          </p>
          <Button 
            variant="outline" 
            onClick={resetFilters}
          >
            Reset Filters
          </Button>
        </div>
      </div>
    )
  }

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onConnect={onConnect}
      onNodeClick={onNodeClick}
      onPaneClick={onPaneClick}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      fitView
      fitViewOptions={{ padding: 0.2, duration: 800 }}
      defaultViewport={{ x: 0, y: 0, zoom: 1 }}
      attributionPosition="bottom-left"
      proOptions={{ hideAttribution: true }}
      // Optimized performance settings
      onlyRenderVisibleElements={true}
      nodesDraggable={true}
      nodesConnectable={false}
      elementsSelectable={true}
      minZoom={0.1}
      maxZoom={4}
      // Disable key codes to reduce unnecessary re-renders
      deleteKeyCode={null}
      multiSelectionKeyCode={null}
      // Disable snap to grid to reduce updates
      snapToGrid={false}
    >
      <Background 
        variant={BackgroundVariant.Dots} 
        gap={20} 
        size={1}
        className="opacity-30"
      />
      <Controls 
        className="bg-background border border-border rounded-lg shadow-lg" 
        showInteractive={false}
      />
    </ReactFlow>
  )
}

// Main component with ReactFlowProvider wrapper
const GraphVisualization: React.FC = () => {
  const { nodes: graphNodes } = useTaskGraphStore()

  // Show loading state or empty state
  if (Object.keys(graphNodes).length === 0) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-muted/20">
        <div className="text-center">
          <h3 className="text-lg font-medium mb-2">Waiting for Project Data</h3>
          <p className="text-muted-foreground">
            Start a project to see the task decomposition graph
          </p>
          <div className="mt-4 text-xs text-muted-foreground">
            Real-time updates enabled ⚡
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="w-full h-full bg-background">
      <ReactFlowProvider>
        <FlowContent />
      </ReactFlowProvider>
    </div>
  )
}

export default GraphVisualization 