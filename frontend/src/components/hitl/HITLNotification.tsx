import React, { useEffect, useState } from 'react'
import { useTaskGraphStore } from '@/stores/taskGraphStore'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { X } from 'lucide-react'

const HITLNotification: React.FC = () => {
  const { currentHITLRequest, setHITLRequest } = useTaskGraphStore()
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    if (currentHITLRequest) {
      setIsVisible(true)
      console.log('🤔 HITL Notification: Showing request', currentHITLRequest)
      
      // Auto-hide after 5 seconds
      const timer = setTimeout(() => {
        setIsVisible(false)
        setTimeout(() => setHITLRequest(undefined), 300) // Allow fade out
      }, 5000)
      
      return () => clearTimeout(timer)
    }
  }, [currentHITLRequest, setHITLRequest])

  if (!currentHITLRequest || !isVisible) {
    return null
  }

  return (
    <div className="fixed top-4 right-4 z-50 animate-in slide-in-from-right-full duration-300">
      <Card className="w-80 border-blue-200 bg-blue-50">
        <CardContent className="p-4">
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <Badge variant="secondary" className="text-xs">
                  🤔 HITL Checkpoint
                </Badge>
                <Badge variant="outline" className="text-xs">
                  {currentHITLRequest.current_attempt}
                </Badge>
              </div>
              
              <h4 className="font-medium text-sm text-blue-900 mb-1">
                {currentHITLRequest.checkpoint_name}
              </h4>
              
              <p className="text-xs text-blue-700 mb-2">
                Node: {currentHITLRequest.node_id}
              </p>
              
              <p className="text-xs text-gray-600 line-clamp-2">
                {currentHITLRequest.context_message}
              </p>
              
              <div className="mt-2 text-xs text-green-600">
                ✅ Auto-approved (WebSocket HITL in development)
              </div>
            </div>
            
            <button
              onClick={() => {
                setIsVisible(false)
                setTimeout(() => setHITLRequest(undefined), 300)
              }}
              className="text-gray-400 hover:text-gray-600"
            >
              <X size={16} />
            </button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default HITLNotification 