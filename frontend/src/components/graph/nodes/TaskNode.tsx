import React from 'react'
import { Handle, Position, NodeProps } from 'reactflow'
import { getStatusColor, truncateText } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { 
  Brain, 
  Play, 
  CheckCircle, 
  XCircle, 
  Clock, 
  Loader2,
  AlertTriangle,
  Zap,
  ArrowRight,
  Hash
} from 'lucide-react'
import type { TaskNode as TaskNodeType } from '@/types'

interface TaskNodeData {
  node: TaskNodeType
  isSelected?: boolean
  isHighlighted?: boolean
  isDimmed?: boolean
  executionRank?: number
  highlightMode?: string
}

const getStatusIcon = (status: string) => {
  const iconProps = { className: "w-3 h-3" }
  
  switch (status) {
    case 'DONE':
      return <CheckCircle {...iconProps} className="w-3 h-3 text-green-600" />
    case 'FAILED':
      return <XCircle {...iconProps} className="w-3 h-3 text-red-600" />
    case 'RUNNING':
      return <Loader2 {...iconProps} className="w-3 h-3 text-orange-600 animate-spin" />
    case 'READY':
      return <Play {...iconProps} className="w-3 h-3 text-blue-600" />
    case 'NEEDS_REPLAN':
      return <AlertTriangle {...iconProps} className="w-3 h-3 text-amber-600" />
    case 'PLAN_DONE':
      return <Zap {...iconProps} className="w-3 h-3 text-purple-600" />
    default:
      return <Clock {...iconProps} className="w-3 h-3 text-gray-500" />
  }
}

const getNodeBackgroundColor = (status: string, nodeType: string, isHighlighted?: boolean, isDimmed?: boolean) => {
  const baseColors = {
    PENDING: 'bg-gray-50 border-gray-200',
    READY: 'bg-blue-50 border-blue-200',
    RUNNING: 'bg-orange-50 border-orange-200',
    PLAN_DONE: 'bg-purple-50 border-purple-200',
    AGGREGATING: 'bg-yellow-50 border-yellow-200',
    DONE: 'bg-green-50 border-green-200',
    FAILED: 'bg-red-50 border-red-200',
    NEEDS_REPLAN: 'bg-amber-50 border-amber-200',
    CANCELLED: 'bg-gray-100 border-gray-300'
  }

  const darkColors = {
    PENDING: 'dark:bg-gray-900 dark:border-gray-700',
    READY: 'dark:bg-blue-900/30 dark:border-blue-700',
    RUNNING: 'dark:bg-orange-900/30 dark:border-orange-700',
    PLAN_DONE: 'dark:bg-purple-900/30 dark:border-purple-700',
    AGGREGATING: 'dark:bg-yellow-900/30 dark:border-yellow-700',
    DONE: 'dark:bg-green-900/30 dark:border-green-700',
    FAILED: 'dark:bg-red-900/30 dark:border-red-700',
    NEEDS_REPLAN: 'dark:bg-amber-900/30 dark:border-amber-700',
    CANCELLED: 'dark:bg-gray-800 dark:border-gray-600'
  }

  const light = baseColors[status as keyof typeof baseColors] || baseColors.PENDING
  const dark = darkColors[status as keyof typeof darkColors] || darkColors.PENDING
  
  let result = `${light} ${dark}`
  
  // Add highlighting effects
  if (isHighlighted) {
    result += ' ring-2 ring-primary ring-opacity-60 shadow-lg'
  }
  
  if (isDimmed) {
    result += ' opacity-30'
  }
  
  return result
}

const TaskNodeComponent: React.FC<NodeProps<TaskNodeData>> = ({ data, selected }) => {
  const { node, isHighlighted, isDimmed, executionRank, highlightMode } = data
  const isPlanNode = node.node_type === 'PLAN'
  const backgroundColorClass = getNodeBackgroundColor(node.status, node.node_type, isHighlighted, isDimmed)
  
  // Enhanced styling for context flow
  const nodeClassName = `
    min-w-[280px] max-w-[320px] p-4 rounded-xl border-2 shadow-lg transition-all duration-300
    ${backgroundColorClass}
    ${selected ? 'ring-2 ring-primary scale-105 shadow-xl' : 'hover:shadow-md'}
    ${node.status === 'RUNNING' ? 'pulse-glow' : ''}
    ${isHighlighted ? 'transform scale-105 z-10' : ''}
    ${isDimmed ? 'opacity-30' : ''}
  `

  return (
    <div className={nodeClassName}>
      {/* Input Handle with enhanced styling */}
      <Handle
        type="target"
        position={Position.Top}
        className={`w-3 h-3 border-2 border-white shadow-md transition-all duration-200 ${
          isHighlighted ? 'scale-125 ring-2 ring-primary' : ''
        }`}
        style={{ 
          background: isHighlighted ? 'hsl(var(--primary))' : 'hsl(var(--primary))',
          opacity: isDimmed ? 0.3 : 1
        }}
      />
      
      {/* Execution Order Indicator */}
      {executionRank !== undefined && highlightMode === 'executionPath' && (
        <div className="absolute -top-2 -left-2 w-6 h-6 bg-amber-500 text-white rounded-full flex items-center justify-center text-xs font-bold shadow-md">
          {executionRank + 1}
        </div>
      )}

      {/* Context Flow Indicator */}
      {isHighlighted && highlightMode === 'dataFlow' && (
        <div className="absolute -top-1 -right-1 w-4 h-4 bg-green-500 rounded-full flex items-center justify-center">
          <ArrowRight className="w-2 h-2 text-white" />
        </div>
      )}
      
      {/* Node Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          {isPlanNode ? (
            <Brain className="w-5 h-5 text-purple-600" />
          ) : (
            <Play className="w-5 h-5 text-blue-600" />
          )}
          <Badge variant="outline" className="text-xs font-medium">
            {node.task_type}
          </Badge>
          {node.layer > 0 && (
            <Badge variant="secondary" className="text-xs">
              L{node.layer}
            </Badge>
          )}
        </div>
        <div className="flex items-center space-x-2">
          {getStatusIcon(node.status)}
          <div className={`w-3 h-3 rounded-full ${getStatusColor(node.status)} shadow-sm`} />
        </div>
      </div>
      
      {/* Node Content */}
      <div className="space-y-2">
        <div className="text-sm font-semibold leading-tight text-foreground">
          {truncateText(node.goal, 120)}
        </div>
        
        {node.agent_name && (
          <div className="text-xs text-muted-foreground bg-background/50 rounded px-2 py-1">
            🤖 {truncateText(node.agent_name, 25)}
          </div>
        )}

        {/* Context Sources Indicator */}
        {node.input_context_sources && node.input_context_sources.length > 0 && (
          <div className="text-xs text-muted-foreground flex items-center space-x-1">
            <Hash className="w-3 h-3" />
            <span>{node.input_context_sources.length} context sources</span>
          </div>
        )}
        
        {node.output_summary && (
          <div className="text-xs text-muted-foreground border-t border-border/50 pt-2 mt-2">
            📋 {truncateText(node.output_summary, 100)}
          </div>
        )}

        {/* Execution timestamp for highlighted nodes */}
        {isHighlighted && highlightMode === 'executionPath' && node.timestamp_created && (
          <div className="text-xs text-muted-foreground border-t border-border/50 pt-1 mt-1">
            ⏰ {new Date(node.timestamp_created).toLocaleTimeString()}
          </div>
        )}
      </div>
      
      {/* Output Handle with enhanced styling */}
      <Handle
        type="source"
        position={Position.Bottom}
        className={`w-3 h-3 border-2 border-white shadow-md transition-all duration-200 ${
          isHighlighted ? 'scale-125 ring-2 ring-primary' : ''
        }`}
        style={{ 
          background: isHighlighted ? 'hsl(var(--primary))' : 'hsl(var(--primary))',
          opacity: isDimmed ? 0.3 : 1
        }}
      />
    </div>
  )
}

export default TaskNodeComponent 