import React, { useState, useEffect } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { ScrollArea } from '@/components/ui/scroll-area'
import { CheckCircle, XCircle, Edit, Clock, AlertTriangle, Loader2, Target, Users, Calendar, FileText, CheckCircle2, ArrowRight } from 'lucide-react'
import { useTaskGraphStore } from '@/stores/taskGraphStore'
import { webSocketService } from '@/services/websocketService'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'

interface HITLRequest {
  checkpoint_name: string
  context_message: string
  data_for_review: any
  node_id: string
  current_attempt: number
  request_id: string
  timestamp: string
}

export function HITLModal() {
  const { hitlRequest, clearHITLRequest } = useTaskGraphStore()
  const [selectedAction, setSelectedAction] = useState<'approve' | 'modify' | 'abort' | null>(null)
  const [modificationInstructions, setModificationInstructions] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isWaitingForModification, setIsWaitingForModification] = useState(false)
  const [lastProcessedRequestId, setLastProcessedRequestId] = useState<string | null>(null)

  const isOpen = hitlRequest !== null
  const request = hitlRequest as HITLRequest | null

  console.log('🤔 HITLModal render:', { 
    isOpen, 
    hasRequest: !!request, 
    requestId: request?.request_id,
    checkpoint: request?.checkpoint_name,
    attempt: request?.current_attempt,
    isSubmitting,
    isWaitingForModification,
    lastProcessedRequestId
  })

  // Add effect to track when requests change
  useEffect(() => {
    if (request) {
      console.log('🆕 New HITL request received:', {
        requestId: request.request_id,
        checkpoint: request.checkpoint_name,
        attempt: request.current_attempt,
        timestamp: request.timestamp
      })
    } else {
      console.log('❌ HITL request cleared')
    }
  }, [request?.request_id])

  // Add effect to track when modal opens/closes
  useEffect(() => {
    console.log(`🚪 Modal ${isOpen ? 'OPENED' : 'CLOSED'}`)
  }, [isOpen])

  // Enhanced effect to detect when modification is complete
  useEffect(() => {
    if (isWaitingForModification && request) {
      // Check if we received a NEW HITL request (different request_id)
      // AND it's a modified plan review checkpoint
      const isNewRequest = request.request_id !== lastProcessedRequestId
      const isModifiedPlanReview = request.checkpoint_name.includes('PostModifiedPlanReview') || 
                                   request.checkpoint_name.includes('PostInitialPlanGeneration')
      
      if (isNewRequest && isModifiedPlanReview) {
        console.log('✅ Modification complete - received new plan review request:', { 
          checkpoint: request.checkpoint_name,
          requestId: request.request_id,
          lastProcessedId: lastProcessedRequestId,
          isNewRequest,
          isModifiedPlanReview
        })
        
        setIsWaitingForModification(false)
        setSelectedAction(null)
        setModificationInstructions('')
        setLastProcessedRequestId(request.request_id)
        // Don't clear the HITL request - we need to show the modified plan
      }
    }
  }, [isWaitingForModification, request?.checkpoint_name, request?.request_id, lastProcessedRequestId])

  // Track when we start processing a new request
  useEffect(() => {
    if (request && !isWaitingForModification) {
      setLastProcessedRequestId(request.request_id)
    }
  }, [request?.request_id, isWaitingForModification])

  const handleClose = () => {
    console.log('🚪 User attempting to close modal:', { isSubmitting, isWaitingForModification })
    if (!isSubmitting && !isWaitingForModification) {
      console.log('✅ Closing modal and clearing request')
      clearHITLRequest()
      setSelectedAction(null)
      setModificationInstructions('')
      setIsWaitingForModification(false)
    } else {
      console.log('❌ Cannot close modal - operation in progress')
    }
  }

  const handleResponse = async (action: 'approve' | 'modify' | 'abort', feedback?: string) => {
    if (!hitlRequest) return;

    console.log('📤 Sending HITL response:', { action, feedback, requestId: hitlRequest.request_id });
    
    try {
      await webSocketService.sendHITLResponse({
        request_id: hitlRequest.request_id,
        action,
        modification_instructions: feedback || ''
      });

      if (action === 'modify') {
        console.log('⏳ Waiting for modified plan to be generated...');
        setIsWaitingForModification(true);
        // Don't clear the request - wait for the new plan
      } else {
        // Only clear for approve/abort
        clearHITLRequest();
        setIsWaitingForModification(false);
      }
    } catch (error) {
      console.error('Failed to send HITL response:', error);
    }
  };

  // Clear HITL request when modal closes (only for non-modify cases)
  useEffect(() => {
    if (!isOpen && hitlRequest && !isWaitingForModification) {
      console.log('❌ HITL request cleared');
      clearHITLRequest();
    }
  }, [isOpen, hitlRequest, isWaitingForModification]);

  const renderPlanData = (data: any) => {
    if (!data) return <div className="text-muted-foreground">No data provided</div>

    // Handle different types of HITL data structures
    if (data.proposed_plan || data.proposed_modified_plan) {
      return renderPlanStructure(data)
    } else if (data.task_goal || data.goal) {
      return renderTaskData(data)
    } else {
      return renderGenericData(data)
    }
  }

  const renderPlanStructure = (data: any) => {
    const plan = data.proposed_plan || data.proposed_modified_plan
    const taskGoal = data.task_goal || data.goal
    const plannerInput = data.planner_input_summary
    const modificationInstructions = data.user_modification_instructions
    const replanReason = data.reason_for_current_replan

    return (
      <div className="space-y-6">
        {/* Task Goal Section */}
        {taskGoal && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-lg">
                <Target className="w-5 h-5 text-blue-600" />
                Task Goal
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm leading-relaxed">{taskGoal}</p>
            </CardContent>
          </Card>
        )}

        {/* Modification Context (if this is a replan) */}
        {(modificationInstructions || replanReason) && (
          <Card className="border-orange-200 bg-orange-50">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-lg text-orange-800">
                <AlertTriangle className="w-5 h-5" />
                Modification Context
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {modificationInstructions && (
                <div>
                  <h4 className="font-medium text-orange-800 mb-1">Your Previous Instructions:</h4>
                  <p className="text-sm text-orange-700 bg-orange-100 p-3 rounded border">{modificationInstructions}</p>
                </div>
              )}
              {replanReason && (
                <div>
                  <h4 className="font-medium text-orange-800 mb-1">Reason for Replan:</h4>
                  <p className="text-sm text-orange-700">{replanReason}</p>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Project Context */}
        {plannerInput && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-lg">
                <FileText className="w-5 h-5 text-green-600" />
                Project Context
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {plannerInput.overall_objective && (
                <div>
                  <h4 className="font-medium text-gray-700 mb-1">Overall Objective:</h4>
                  <p className="text-sm text-gray-600">{plannerInput.overall_objective}</p>
                </div>
              )}
              {plannerInput.context_summary && (
                <div>
                  <h4 className="font-medium text-gray-700 mb-1">Context Summary:</h4>
                  <p className="text-sm text-gray-600">{plannerInput.context_summary}</p>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Proposed Plan */}
        {plan && (
          <Card className="border-blue-200">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-lg text-blue-800">
                <CheckCircle2 className="w-5 h-5" />
                {data.proposed_modified_plan ? 'Modified Plan' : 'Proposed Plan'}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {renderPlan(plan)}
            </CardContent>
          </Card>
        )}
      </div>
    )
  }

  const renderPlan = (plan: any) => {
    if (!plan) return <div className="text-muted-foreground">No plan data</div>

    // Handle different plan structures
    if (plan.subtasks && Array.isArray(plan.subtasks)) {
      return (
        <div className="space-y-4">
          {plan.description && (
            <div className="mb-4">
              <h4 className="font-medium text-gray-700 mb-2">Plan Description:</h4>
              <p className="text-sm text-gray-600 bg-gray-50 p-3 rounded">{plan.description}</p>
            </div>
          )}
          
          <div>
            <h4 className="font-medium text-gray-700 mb-3">Subtasks ({plan.subtasks.length}):</h4>
            <div className="space-y-3">
              {plan.subtasks.map((subtask: any, index: number) => (
                <div key={index} className="border rounded-lg p-4 bg-white">
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-800 rounded-full flex items-center justify-center text-sm font-medium">
                      {index + 1}
                    </div>
                    <div className="flex-1 space-y-2">
                      <h5 className="font-medium text-gray-800">{subtask.goal || subtask.description || `Subtask ${index + 1}`}</h5>
                      {subtask.description && subtask.goal !== subtask.description && (
                        <p className="text-sm text-gray-600">{subtask.description}</p>
                      )}
                      {subtask.agent_name && (
                        <div className="flex items-center gap-1 text-xs text-gray-500">
                          <Users className="w-3 h-3" />
                          Agent: {subtask.agent_name}
                        </div>
                      )}
                      {subtask.expected_output && (
                        <div className="text-xs text-gray-500">
                          <span className="font-medium">Expected Output:</span> {subtask.expected_output}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )
    }

    // Handle simple plan structures or fallback
    return renderGenericData(plan)
  }

  const renderTaskData = (data: any) => {
    return (
      <div className="space-y-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Target className="w-5 h-5 text-blue-600" />
              Task Information
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {data.task_goal && (
              <div>
                <h4 className="font-medium text-gray-700 mb-1">Goal:</h4>
                <p className="text-sm text-gray-600">{data.task_goal}</p>
              </div>
            )}
            {data.agent_name && (
              <div>
                <h4 className="font-medium text-gray-700 mb-1">Agent:</h4>
                <p className="text-sm text-gray-600">{data.agent_name}</p>
              </div>
            )}
            {data.task_type && (
              <div>
                <h4 className="font-medium text-gray-700 mb-1">Task Type:</h4>
                <Badge variant="outline">{data.task_type}</Badge>
              </div>
            )}
          </CardContent>
        </Card>
        
        {/* Show other fields if present */}
        {Object.keys(data).some(key => !['task_goal', 'agent_name', 'task_type', 'task_id'].includes(key)) && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-lg">Additional Details</CardTitle>
            </CardHeader>
            <CardContent>
              {renderGenericData(Object.fromEntries(
                Object.entries(data).filter(([key]) => !['task_goal', 'agent_name', 'task_type', 'task_id'].includes(key))
              ))}
            </CardContent>
          </Card>
        )}
      </div>
    )
  }

  const renderGenericData = (data: any) => {
    if (!data || typeof data !== 'object') {
      return <pre className="text-sm text-gray-600 whitespace-pre-wrap">{String(data)}</pre>
    }

    return (
      <div className="space-y-3">
        {Object.entries(data).map(([key, value]) => (
          <div key={key} className="border-b border-gray-100 pb-2 last:border-b-0">
            <h4 className="font-medium text-gray-700 mb-1 capitalize">
              {key.replace(/_/g, ' ')}:
            </h4>
            <div className="text-sm text-gray-600">
              {typeof value === 'object' && value !== null ? (
                <pre className="bg-gray-50 p-2 rounded text-xs overflow-x-auto">
                  {JSON.stringify(value, null, 2)}
                </pre>
              ) : (
                <span>{String(value)}</span>
              )}
            </div>
          </div>
        ))}
      </div>
    )
  }

  const getActionIcon = (action: string) => {
    switch (action) {
      case 'approve': return <CheckCircle className="w-4 h-4" />
      case 'modify': return <Edit className="w-4 h-4" />
      case 'abort': return <XCircle className="w-4 h-4" />
      default: return <Clock className="w-4 h-4" />
    }
  }

  const getActionColor = (action: string) => {
    switch (action) {
      case 'approve': return 'bg-green-500 hover:bg-green-600 text-white'
      case 'modify': return 'bg-blue-500 hover:bg-blue-600 text-white'
      case 'abort': return 'bg-red-500 hover:bg-red-600 text-white'
      default: return 'bg-gray-500 hover:bg-gray-600'
    }
  }

  if (!request) return null

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="max-w-4xl w-full h-[90vh] p-0 gap-0">
        {/* Header - Fixed */}
        <DialogHeader className="p-6 pb-4 border-b">
          <DialogTitle className="flex items-center gap-2">
            <Clock className="w-5 h-5" />
            Human Review Required
            {request?.current_attempt && request.current_attempt > 1 && (
              <Badge variant="secondary">Attempt {request.current_attempt}</Badge>
            )}
          </DialogTitle>
          <DialogDescription>
            {isWaitingForModification ? (
              <div className="flex items-center gap-2 text-blue-600">
                <Loader2 className="w-4 h-4 animate-spin" />
                Processing your modification request... Please wait for the updated plan.
              </div>
            ) : (
              `Checkpoint: ${request?.checkpoint_name || 'Unknown'} | Node: ${request?.node_id || 'Unknown'}`
            )}
          </DialogDescription>
        </DialogHeader>

        {isWaitingForModification ? (
          <div className="flex-1 flex items-center justify-center py-8">
            <div className="text-center">
              <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4 text-blue-600" />
              <h3 className="text-lg font-medium mb-2">Generating Modified Plan</h3>
              <p className="text-muted-foreground">
                The system is processing your modification request and will show you the updated plan shortly.
              </p>
            </div>
          </div>
        ) : (
          <>
            {/* Scrollable Content Area */}
            <div className="flex-1 overflow-hidden">
              <ScrollArea className="h-full">
                <div className="p-6 space-y-4">
                  {/* Context Message */}
                  {request?.context_message && (
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                      <h3 className="font-medium text-blue-900 mb-2">Context</h3>
                      <p className="text-blue-800 text-sm whitespace-pre-wrap">{request.context_message}</p>
                    </div>
                  )}

                  {/* Data for Review - Now with improved rendering */}
                  <div>
                    <h3 className="font-medium mb-4">Plan Review</h3>
                    <div className="border rounded-lg bg-white">
                      <ScrollArea className="max-h-[400px]">
                        <div className="p-4">
                          {renderPlanData(request?.data_for_review)}
                        </div>
                      </ScrollArea>
                    </div>
                  </div>
                </div>
              </ScrollArea>
            </div>

            {/* Action Selection - Fixed at bottom */}
            <div className="border-t bg-white p-6 space-y-4">
              <div>
                <h3 className="font-medium mb-3">Choose Action</h3>
                <div className="grid grid-cols-3 gap-2">
                  {(['approve', 'modify', 'abort'] as const).map((action) => (
                    <Button
                      key={action}
                      variant={selectedAction === action ? 'default' : 'outline'}
                      onClick={() => setSelectedAction(action)}
                      className="flex items-center gap-2 justify-center"
                      type="button"
                    >
                      {getActionIcon(action)}
                      {action.charAt(0).toUpperCase() + action.slice(1)}
                    </Button>
                  ))}
                </div>
              </div>

              {/* Modification Instructions */}
              {selectedAction === 'modify' && (
                <div>
                  <label htmlFor="modification-instructions" className="block text-sm font-medium mb-2">
                    Modification Instructions
                  </label>
                  <Textarea
                    id="modification-instructions"
                    placeholder="Describe what changes you want to make to the plan..."
                    value={modificationInstructions}
                    onChange={(e) => setModificationInstructions(e.target.value)}
                    className="min-h-[100px] resize-none"
                  />
                </div>
              )}

              {/* Submit Buttons */}
              <div className="flex justify-end gap-2 pt-4 border-t">
                <Button 
                  variant="outline" 
                  onClick={handleClose} 
                  disabled={isSubmitting}
                  type="button"
                >
                  Cancel
                </Button>
                <Button 
                  onClick={() => handleResponse(selectedAction as 'approve' | 'modify' | 'abort', selectedAction === 'modify' ? modificationInstructions : undefined)} 
                  disabled={!selectedAction || isSubmitting || (selectedAction === 'modify' && !modificationInstructions.trim())}
                  type="button"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin mr-2" />
                      Submitting...
                    </>
                  ) : (
                    `Submit ${selectedAction ? selectedAction.charAt(0).toUpperCase() + selectedAction.slice(1) : ''}`
                  )}
                </Button>
              </div>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
} 