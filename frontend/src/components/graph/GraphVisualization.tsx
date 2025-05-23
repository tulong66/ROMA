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
    selectNode,
    showContextFlow 
  } = useTaskGraphStore()

  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const { fitView } = useReactFlow()
  
  // Use refs to track previous state for better change detection
  const prevNodeCountRef = useRef(0)
  const isUpdatingRef = useRef(false)

  console.log('🔄 FlowContent render:', {
    graphNodesCount: Object.keys(graphNodes).length,
    graphsCount: Object.keys(graphs).length,
    selectedNodeId
  })

  // Convert backend data to React Flow format - optimized with better memoization
  const flowData = useMemo(() => {
    console.log('🔄 Converting flow data...')
    try {
      const flowNodes = convertToFlowNodes(graphNodes, selectedNodeId)
      const flowEdges = convertToFlowEdges(graphNodes, graphs, showContextFlow)
      console.log('✅ Flow data converted:', { 
        nodes: flowNodes.length, 
        edges: flowEdges.length
      })
      return { nodes: flowNodes, edges: flowEdges }
    } catch (error) {
      console.error('❌ Error converting flow data:', error)
      return { nodes: [], edges: [] }
    }
  }, [graphNodes, graphs, selectedNodeId, showContextFlow])

  // Update React Flow nodes and edges when data changes - optimized
  useEffect(() => {
    if (isUpdatingRef.current) {
      console.log('⚠️ Update already in progress, skipping')
      return
    }

    const currentNodeCount = Object.keys(graphNodes).length
    const hasNewNodes = currentNodeCount > prevNodeCountRef.current
    
    // Only update if there are actual changes
    if (currentNodeCount !== prevNodeCountRef.current || hasNewNodes) {
      isUpdatingRef.current = true
      
      console.log('🔄 Updating React Flow:', {
        previousNodes: prevNodeCountRef.current,
        currentNodes: currentNodeCount,
        hasNewNodes
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
          }, 200)
        }

        // Update refs
        prevNodeCountRef.current = currentNodeCount
      } catch (error) {
        console.error('❌ Error updating React Flow:', error)
      } finally {
        isUpdatingRef.current = false
      }
    }
  }, [flowData.nodes, flowData.edges, graphNodes, setNodes, setEdges, fitView])

  // Optimized node click handler with error boundary
  const onNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      try {
        console.log('🖱️ Node clicked:', node.id)
        const newSelection = node.id === selectedNodeId ? undefined : node.id
        selectNode(newSelection)
      } catch (error) {
        console.error('❌ Error handling node click:', error)
      }
    },
    [selectNode, selectedNodeId]
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