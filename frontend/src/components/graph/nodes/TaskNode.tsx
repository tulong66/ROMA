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
  Zap
} from 'lucide-react'
import type { TaskNode as TaskNodeType } from '@/types'

interface TaskNodeData {
  node: TaskNodeType
  isSelected?: boolean
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

const getNodeBackgroundColor = (status: string, nodeType: string) => {
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
  
  return `${light} ${dark}`
}

const TaskNodeComponent: React.FC<NodeProps<TaskNodeData>> = ({ data, selected }) => {
  const { node } = data
  const isPlanNode = node.node_type === 'PLAN'
  const backgroundColorClass = getNodeBackgroundColor(node.status, node.node_type)
  
  return (
    <div className={`
      min-w-[280px] max-w-[320px] p-4 rounded-xl border-2 shadow-lg transition-all duration-300
      ${backgroundColorClass}
      ${selected ? 'ring-2 ring-primary scale-105 shadow-xl' : 'hover:shadow-md'}
      ${node.status === 'RUNNING' ? 'animate-pulse' : ''}
    `}>
      {/* Input Handle */}
      <Handle
        type="target"
        position={Position.Top}
        className="w-3 h-3 border-2 border-white shadow-md transition-all duration-200"
        style={{ background: 'hsl(var(--primary))' }}
      />
      
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
        
        {node.output_summary && (
          <div className="text-xs text-muted-foreground border-t border-border/50 pt-2 mt-2">
            📋 {truncateText(node.output_summary, 100)}
          </div>
        )}
      </div>
      
      {/* Output Handle */}
      <Handle
        type="source"
        position={Position.Bottom}
        className="w-3 h-3 border-2 border-white shadow-md transition-all duration-200"
        style={{ background: 'hsl(var(--primary))' }}
      />
    </div>
  )
}

export default TaskNodeComponent 