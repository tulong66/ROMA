import React, { useState } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { CheckCircle, XCircle, Edit, Clock, AlertTriangle } from 'lucide-react'
import { useTaskGraphStore } from '@/stores/taskGraphStore'
import { webSocketService } from '@/services/websocketService'

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

  const isOpen = hitlRequest !== null
  const request = hitlRequest as HITLRequest | null

  console.log('🤔 HITLModal render:', { isOpen, hasRequest: !!request, requestId: request?.request_id })

  const handleClose = () => {
    if (!isSubmitting) {
      clearHITLRequest()
      setSelectedAction(null)
      setModificationInstructions('')
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

      // Close modal after sending response
      handleClose()
    } catch (error) {
      console.error('❌ Error sending HITL response:', error)
    } finally {
      setIsSubmitting(false)
    }
  }

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
      case 'approve': return 'bg-green-500 hover:bg-green-600'
      case 'modify': return 'bg-blue-500 hover:bg-blue-600'
      case 'abort': return 'bg-red-500 hover:bg-red-600'
      default: return 'bg-gray-500 hover:bg-gray-600'
    }
  }

  if (!request) return null

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-yellow-500" />
            Human Review Required: {request.checkpoint_name}
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 space-y-4 overflow-hidden">
          {/* Request Info */}
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="font-medium">Node ID:</span> {request.node_id}
            </div>
            <div>
              <span className="font-medium">Attempt:</span> {request.current_attempt}
            </div>
            <div className="col-span-2">
              <span className="font-medium">Timestamp:</span> {new Date(request.timestamp).toLocaleString()}
            </div>
          </div>

          {/* Context Message */}
          <div>
            <h3 className="font-medium mb-2">Context:</h3>
            <div className="bg-gray-50 dark:bg-gray-800 p-3 rounded-md text-sm">
              {request.context_message}
            </div>
          </div>

          {/* Data for Review */}
          <div className="flex-1 flex flex-col min-h-0">
            <h3 className="font-medium mb-2">Data for Review:</h3>
            <ScrollArea className="flex-1 bg-gray-50 dark:bg-gray-800 p-3 rounded-md">
              <pre className="text-xs whitespace-pre-wrap font-mono">
                {formatDataForDisplay(request.data_for_review)}
              </pre>
            </ScrollArea>
          </div>

          {/* Action Selection */}
          <div>
            <h3 className="font-medium mb-3">Choose Action:</h3>
            <div className="grid grid-cols-3 gap-2">
              <Button
                variant={selectedAction === 'approve' ? 'default' : 'outline'}
                onClick={() => setSelectedAction('approve')}
                className={selectedAction === 'approve' ? getActionColor('approve') : ''}
                disabled={isSubmitting}
              >
                {getActionIcon('approve')}
                Approve
              </Button>
              <Button
                variant={selectedAction === 'modify' ? 'default' : 'outline'}
                onClick={() => setSelectedAction('modify')}
                className={selectedAction === 'modify' ? getActionColor('modify') : ''}
                disabled={isSubmitting}
              >
                {getActionIcon('modify')}
                Modify
              </Button>
              <Button
                variant={selectedAction === 'abort' ? 'default' : 'outline'}
                onClick={() => setSelectedAction('abort')}
                className={selectedAction === 'abort' ? getActionColor('abort') : ''}
                disabled={isSubmitting}
              >
                {getActionIcon('abort')}
                Abort
              </Button>
            </div>
          </div>

          {/* Modification Instructions */}
          {selectedAction === 'modify' && (
            <div>
              <h3 className="font-medium mb-2">Modification Instructions:</h3>
              <Textarea
                placeholder="Describe what changes you want to make..."
                value={modificationInstructions}
                onChange={(e) => setModificationInstructions(e.target.value)}
                className="min-h-[100px]"
                disabled={isSubmitting}
              />
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={handleClose}
            disabled={isSubmitting}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!selectedAction || isSubmitting || (selectedAction === 'modify' && !modificationInstructions.trim())}
            className={selectedAction ? getActionColor(selectedAction) : ''}
          >
            {isSubmitting ? 'Submitting...' : `Submit ${selectedAction || 'Action'}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
} 