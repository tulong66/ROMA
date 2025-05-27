import React, { useState, useEffect } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { ScrollArea } from '@/components/ui/scroll-area'
import { CheckCircle, XCircle, Edit, Clock, AlertTriangle, Loader2 } from 'lucide-react'
import { useTaskGraphStore } from '@/stores/taskGraphStore'
import { webSocketService } from '@/services/websocketService'
import { Badge } from '@/components/ui/badge'

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

  const isOpen = hitlRequest !== null
  const request = hitlRequest as HITLRequest | null

  console.log('🤔 HITLModal render:', { 
    isOpen, 
    hasRequest: !!request, 
    requestId: request?.request_id,
    checkpoint: request?.checkpoint_name,
    attempt: request?.current_attempt,
    isSubmitting,
    isWaitingForModification
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

  const handleSubmit = async () => {
    if (!request || !selectedAction) return

    setIsSubmitting(true)

    try {
      const response = {
        request_id: request.request_id,
        checkpoint_name: request.checkpoint_name,
        node_id: request.node_id,
        action: selectedAction,
        modification_instructions: selectedAction === 'modify' ? modificationInstructions : null,
        timestamp: new Date().toISOString()
      }

      console.log('📤 Sending HITL response:', response)
      webSocketService.sendHITLResponse(response)

      // If user selected modify, show waiting state instead of closing
      if (selectedAction === 'modify') {
        setIsWaitingForModification(true)
        setSelectedAction(null)
        setModificationInstructions('')
        console.log('⏳ Waiting for modified plan to be generated...')
      } else {
        // Close modal for approve/abort actions
        handleClose()
      }
    } catch (error) {
      console.error('❌ Error sending HITL response:', error)
    } finally {
      setIsSubmitting(false)
    }
  }

  // Reset waiting state when a new request comes in
  useEffect(() => {
    if (request && isWaitingForModification) {
      setIsWaitingForModification(false)
      console.log('✅ New HITL request received, showing updated plan')
    }
  }, [request?.request_id])

  const formatDataForDisplay = (data: any): string => {
    if (!data) return 'No data provided'
    
    try {
      return JSON.stringify(data, null, 2)
    } catch {
      return String(data)
    }
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

                  {/* Data for Review */}
                  <div>
                    <h3 className="font-medium mb-2">Data for Review</h3>
                    <div className="border rounded-lg bg-gray-50">
                      <ScrollArea className="h-[300px]">
                        <pre className="p-4 text-sm whitespace-pre-wrap font-mono text-gray-800">
                          {formatDataForDisplay(request?.data_for_review)}
                        </pre>
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
                  onClick={handleSubmit} 
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