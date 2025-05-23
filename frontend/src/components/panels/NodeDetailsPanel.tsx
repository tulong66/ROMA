import React, { useState } from 'react'
import { useTaskGraphStore } from '@/stores/taskGraphStore'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { 
  Brain, 
  Play, 
  CheckCircle, 
  XCircle, 
  Clock, 
  Loader2,
  AlertTriangle,
  Zap,
  Calendar,
  User,
  Target,
  ArrowRight,
  Copy,
  ChevronDown,
  ChevronRight,
  FileText,
  Link2,
  Activity,
  Layers,
  Database,
  Navigation
} from 'lucide-react'
import { getStatusColor, cn } from '@/lib/utils'
import type { TaskNode, ContextSource } from '@/types'
import FullResultModal from './FullResultModal'
import NodeNavigator from './NodeNavigator'

const getStatusIcon = (status: string) => {
  const iconProps = { className: "w-4 h-4" }
  
  switch (status) {
    case 'DONE':
      return <CheckCircle {...iconProps} className="w-4 h-4 text-green-600" />
    case 'FAILED':
      return <XCircle {...iconProps} className="w-4 h-4 text-red-600" />
    case 'RUNNING':
      return <Loader2 {...iconProps} className="w-4 h-4 text-orange-600 animate-spin" />
    case 'READY':
      return <Play {...iconProps} className="w-4 h-4 text-blue-600" />
    case 'NEEDS_REPLAN':
      return <AlertTriangle {...iconProps} className="w-4 h-4 text-amber-600" />
    case 'PLAN_DONE':
      return <Zap {...iconProps} className="w-4 h-4 text-purple-600" />
    default:
      return <Clock {...iconProps} className="w-4 h-4 text-gray-500" />
  }
}

const formatTimestamp = (timestamp?: string) => {
  if (!timestamp) return 'Not set'
  try {
    return new Date(timestamp).toLocaleString()
  } catch {
    return timestamp
  }
}

const copyToClipboard = async (text: string) => {
  try {
    await navigator.clipboard.writeText(text)
    console.log('Copied to clipboard')
  } catch (err) {
    console.error('Failed to copy to clipboard:', err)
  }
}

interface ExpandableContentProps {
  title: string
  content: string
  maxLength?: number
}

const ExpandableContent: React.FC<ExpandableContentProps> = ({ 
  title, 
  content, 
  maxLength = 200 
}) => {
  const [isExpanded, setIsExpanded] = useState(false)
  const shouldTruncate = content.length > maxLength
  const displayContent = shouldTruncate && !isExpanded 
    ? content.substring(0, maxLength) + '...' 
    : content

  return (
    <div>
      {title && (
        <div className="flex items-center justify-between mb-2">
          <h4 className="text-sm font-medium text-foreground">{title}</h4>
          {shouldTruncate && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsExpanded(!isExpanded)}
              className="h-6 px-2 text-xs"
            >
              {isExpanded ? (
                <>
                  <ChevronDown className="w-3 h-3 mr-1" />
                  Less
                </>
              ) : (
                <>
                  <ChevronRight className="w-3 h-3 mr-1" />
                  More
                </>
              )}
            </Button>
          )}
        </div>
      )}
      <p className="text-sm text-muted-foreground leading-relaxed">
        {displayContent}
      </p>
    </div>
  )
}

const ContextSourcesList: React.FC<{ sources: ContextSource[] }> = ({ sources }) => {
  const { selectNode } = useTaskGraphStore()

  if (!sources || sources.length === 0) return null

  return (
    <div className="space-y-2">
      {sources.map((source, index) => (
        <div 
          key={index}
          className="p-3 bg-muted/30 rounded-lg border cursor-pointer hover:bg-muted/50 transition-colors"
          onClick={() => {
            console.log('Navigating to context source:', source.source_task_id)
            selectNode(source.source_task_id)
          }}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Link2 className="w-3 h-3 text-muted-foreground" />
              <span className="text-xs font-medium text-foreground">
                {source.content_type}
              </span>
            </div>
            <ArrowRight className="w-3 h-3 text-muted-foreground" />
          </div>
          <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
            {source.source_task_goal_summary}
          </p>
          {source.content_type_description && (
            <p className="text-xs text-muted-foreground/80 mt-1 italic">
              {source.content_type_description}
            </p>
          )}
        </div>
      ))}
    </div>
  )
}

const SubTasksList: React.FC<{ taskIds: string[], allNodes: Record<string, TaskNode> }> = ({ 
  taskIds, 
  allNodes 
}) => {
  const { selectNode } = useTaskGraphStore()

  if (!taskIds || taskIds.length === 0) return null

  return (
    <div className="space-y-2">
      {taskIds.map((taskId) => {
        const task = allNodes[taskId]
        if (!task) {
          console.warn('Sub-task not found:', taskId)
          return null
        }

        return (
          <div 
            key={taskId}
            className="p-3 bg-muted/30 rounded-lg border cursor-pointer hover:bg-muted/50 transition-colors"
            onClick={() => {
              console.log('Navigating to sub-task:', taskId)
              selectNode(taskId)
            }}
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center space-x-2">
                {getStatusIcon(task.status)}
                <Badge variant="outline" className="text-xs">
                  {task.task_type}
                </Badge>
              </div>
              <div className={cn("w-2 h-2 rounded-full", getStatusColor(task.status))} />
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              {task.goal}
            </p>
          </div>
        )
      })}
    </div>
  )
}

const NodeDetailsPanel: React.FC = () => {
  const { selectedNodeId, nodes, selectNode } = useTaskGraphStore()
  const [isFullResultModalOpen, setIsFullResultModalOpen] = useState(false)
  
  const selectedNode = selectedNodeId ? nodes[selectedNodeId] : null

  if (!selectedNode) {
    return (
      <div className="w-96 border-l bg-background">
        <div className="p-6 h-full flex flex-col items-center justify-center text-center">
          <div className="mb-4 p-4 bg-muted/30 rounded-full">
            <Target className="w-8 h-8 text-muted-foreground" />
          </div>
          <h3 className="text-lg font-semibold mb-2">Node Details</h3>
          <p className="text-muted-foreground text-sm leading-relaxed">
            Click on any node in the graph to view its detailed information, 
            relationships, and advanced navigation options.
          </p>
        </div>
      </div>
    )
  }

  const isPlanNode = selectedNode.node_type === 'PLAN'
  const hasSubTasks = selectedNode.planned_sub_task_ids && selectedNode.planned_sub_task_ids.length > 0
  const hasContextSources = selectedNode.input_context_sources && selectedNode.input_context_sources.length > 0
  const hasFullResult = selectedNode.full_result != null && selectedNode.full_result !== undefined

  return (
    <>
      <div className="w-96 border-l bg-background h-full overflow-hidden flex flex-col">
        {/* Header */}
        <div className="p-6 border-b bg-muted/20">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center space-x-2">
              {isPlanNode ? (
                <Brain className="w-5 h-5 text-purple-600" />
              ) : (
                <Play className="w-5 h-5 text-blue-600" />
              )}
              <Badge variant="secondary" className="text-xs">
                {selectedNode.node_type}
              </Badge>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => copyToClipboard(selectedNode.task_id)}
              className="h-8 px-2"
            >
              <Copy className="w-3 h-3" />
            </Button>
          </div>
          
          <div className="flex items-center space-x-3 mb-2">
            {getStatusIcon(selectedNode.status)}
            <Badge 
              variant="outline" 
              className={cn("text-xs font-medium", getStatusColor(selectedNode.status))}
            >
              {selectedNode.status.replace('_', ' ')}
            </Badge>
          </div>
          
          <p className="text-xs text-muted-foreground font-mono">
            ID: {selectedNode.task_id}
          </p>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Goal Section */}
          <div className="space-y-3">
            <div className="flex items-center space-x-2 pb-2 border-b border-border/50">
              <Target className="w-4 h-4 text-blue-600" />
              <h3 className="text-sm font-semibold text-foreground">Task Goal</h3>
            </div>
            <ExpandableContent
              title=""
              content={selectedNode.goal}
              maxLength={150}
            />
          </div>

          {/* Metadata Section */}
          <div className="space-y-3">
            <div className="flex items-center space-x-2 pb-2 border-b border-border/50">
              <Activity className="w-4 h-4 text-green-600" />
              <h3 className="text-sm font-semibold text-foreground">Metadata</h3>
            </div>
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <span className="text-muted-foreground">Layer</span>
                <div className="flex items-center space-x-1 mt-1">
                  <Layers className="w-3 h-3 text-muted-foreground" />
                  <span className="font-medium">{selectedNode.layer}</span>
                </div>
              </div>
              <div>
                <span className="text-muted-foreground">Type</span>
                <div className="font-medium mt-1">{selectedNode.task_type}</div>
              </div>
            </div>

            {selectedNode.agent_name && (
              <div className="mt-3">
                <span className="text-xs text-muted-foreground">Agent</span>
                <div className="flex items-center space-x-2 mt-1">
                  <User className="w-3 h-3 text-muted-foreground" />
                  <span className="text-sm font-medium">{selectedNode.agent_name}</span>
                </div>
              </div>
            )}
          </div>

          {/* Timeline Section */}
          <div className="space-y-3">
            <div className="flex items-center space-x-2 pb-2 border-b border-border/50">
              <Calendar className="w-4 h-4 text-purple-600" />
              <h3 className="text-sm font-semibold text-foreground">Timeline</h3>
            </div>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Created</span>
                <span className="font-medium">{formatTimestamp(selectedNode.timestamp_created)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Updated</span>
                <span className="font-medium">{formatTimestamp(selectedNode.timestamp_updated)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Completed</span>
                <span className="font-medium">{formatTimestamp(selectedNode.timestamp_completed)}</span>
              </div>
            </div>
          </div>

          {/* Input/Output Section */}
          {(selectedNode.input_payload_summary || selectedNode.output_summary) && (
            <div className="space-y-3">
              <div className="flex items-center space-x-2 pb-2 border-b border-border/50">
                <FileText className="w-4 h-4 text-orange-600" />
                <h3 className="text-sm font-semibold text-foreground">Input & Output</h3>
              </div>
              {selectedNode.input_payload_summary && (
                <ExpandableContent
                  title="Input Summary"
                  content={selectedNode.input_payload_summary}
                />
              )}
              {selectedNode.output_summary && (
                <div className="mt-4">
                  <ExpandableContent
                    title="Output Summary"
                    content={selectedNode.output_summary}
                  />
                </div>
              )}
            </div>
          )}

          {/* Context Sources Section */}
          {hasContextSources && (
            <div className="space-y-3">
              <div className="flex items-center space-x-2 pb-2 border-b border-border/50">
                <Link2 className="w-4 h-4 text-cyan-600" />
                <h3 className="text-sm font-semibold text-foreground">
                  Context Sources ({selectedNode.input_context_sources!.length})
                </h3>
              </div>
              <ContextSourcesList sources={selectedNode.input_context_sources!} />
            </div>
          )}

          {/* Sub-tasks Section */}
          {hasSubTasks && (
            <div className="space-y-3">
              <div className="flex items-center space-x-2 pb-2 border-b border-border/50">
                <ArrowRight className="w-4 h-4 text-indigo-600" />
                <h3 className="text-sm font-semibold text-foreground">
                  Sub-tasks ({selectedNode.planned_sub_task_ids!.length})
                </h3>
              </div>
              <SubTasksList 
                taskIds={selectedNode.planned_sub_task_ids!} 
                allNodes={nodes}
              />
            </div>
          )}

          {/* Enhanced Navigation Section */}
          <div className="space-y-3">
            <div className="flex items-center space-x-2 pb-2 border-b border-border/50">
              <Navigation className="w-4 h-4 text-blue-600" />
              <h3 className="text-sm font-semibold text-foreground">Enhanced Navigation</h3>
            </div>
            <NodeNavigator />
          </div>

          {/* Error Section */}
          {selectedNode.error && (
            <div className="space-y-3">
              <div className="flex items-center space-x-2 pb-2 border-b border-border/50">
                <XCircle className="w-4 h-4 text-red-600" />
                <h3 className="text-sm font-semibold text-foreground">Error Details</h3>
              </div>
              <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                <p className="text-sm text-red-800 dark:text-red-200 leading-relaxed">
                  {selectedNode.error}
                </p>
              </div>
            </div>
          )}

          {/* Actions Section */}
          <div className="space-y-3">
            <div className="flex items-center space-x-2 pb-2 border-b border-border/50">
              <Activity className="w-4 h-4 text-gray-600" />
              <h3 className="text-sm font-semibold text-foreground">Actions</h3>
            </div>
            <div className="space-y-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => copyToClipboard(selectedNode.task_id)}
                className="w-full justify-start"
              >
                <Copy className="w-4 h-4 mr-2" />
                Copy Task ID
              </Button>
              
              {hasFullResult && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setIsFullResultModalOpen(true)}
                  className="w-full justify-start"
                >
                  <Database className="w-4 h-4 mr-2" />
                  View Full Result
                </Button>
              )}
              
              <Button
                variant="outline"
                size="sm"
                onClick={() => copyToClipboard(JSON.stringify(selectedNode, null, 2))}
                className="w-full justify-start"
              >
                <FileText className="w-4 h-4 mr-2" />
                Copy Raw Data
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Full Result Modal */}
      {hasFullResult && (
        <FullResultModal
          isOpen={isFullResultModalOpen}
          onClose={() => setIsFullResultModalOpen(false)}
          node={selectedNode}
        />
      )}
    </>
  )
}

export default NodeDetailsPanel 