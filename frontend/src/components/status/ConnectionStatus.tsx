import React from 'react'
import { useTaskGraphStore } from '@/stores/taskGraphStore'
import { Wifi, WifiOff } from 'lucide-react'

const ConnectionStatus: React.FC = () => {
  const { isConnected } = useTaskGraphStore()

  if (isConnected) return null

  return (
    <div className="fixed bottom-4 right-4 bg-destructive text-destructive-foreground px-3 py-2 rounded-md flex items-center space-x-2 text-sm">
      <WifiOff className="w-4 h-4" />
      <span>Backend Disconnected</span>
    </div>
  )
}

export default ConnectionStatus 