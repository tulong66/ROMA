import React, { useCallback, useEffect, useMemo } from 'react'
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
  const { fitView } = useReactFlow() // This now works because we're inside ReactFlowProvider

  // Add debugging
  console.log('GraphVisualization render:', {
    graphNodesCount: Object.keys(graphNodes).length,
    graphsCount: Object.keys(graphs).length,
    selectedNodeId,
    showContextFlow
  })

  // Convert backend data to React Flow format
  const flowData = useMemo(() => {
    console.log('Converting flow data...')
    try {
      const flowNodes = convertToFlowNodes(graphNodes, selectedNodeId)
      const flowEdges = convertToFlowEdges(graphNodes, graphs, showContextFlow)
      console.log('Flow data converted:', { nodes: flowNodes.length, edges: flowEdges.length })
      return { nodes: flowNodes, edges: flowEdges }
    } catch (error) {
      console.error('Error converting flow data:', error)
      return { nodes: [], edges: [] }
    }
  }, [graphNodes, graphs, selectedNodeId, showContextFlow])

  // Update React Flow nodes and edges when data changes
  useEffect(() => {
    console.log('Updating React Flow with:', flowData)
    setNodes(flowData.nodes)
    setEdges(flowData.edges)
    
    // Auto-fit view if we have nodes
    if (flowData.nodes.length > 0) {
      setTimeout(() => {
        fitView({ padding: 0.2, duration: 800 })
      }, 100)
    }
  }, [flowData, setNodes, setEdges, fitView])

  const onNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      selectNode(node.id === selectedNodeId ? undefined : node.id)
    },
    [selectNode, selectedNodeId]
  )

  const onPaneClick = useCallback(() => {
    selectNode(undefined)
  }, [selectNode])

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
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