import React, { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Send, Loader2 } from 'lucide-react'
import { useTaskGraphStore } from '@/stores/taskGraphStore'
import { webSocketService } from '@/services/websocketService'

const ProjectInput: React.FC = () => {
  const [goal, setGoal] = useState('Write me a detailed report about the recent U.S. trade tariffs and their effect on the global economy')
  const [isStarting, setIsStarting] = useState(false)
  const { isConnected, setLoading } = useTaskGraphStore()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!goal.trim() || !isConnected) return

    console.log('🚀 Starting project from ProjectInput')
    setIsStarting(true)
    setLoading(true) // Set loading state in store
    
    try {
      webSocketService.startProject(goal.trim())
      console.log('✅ Project start request sent')
    } catch (error) {
      console.error('❌ Failed to start project:', error)
      setLoading(false) // Reset loading on error
    } finally {
      setIsStarting(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto p-8">
      <div className="text-center mb-8">
        <h2 className="text-3xl font-bold mb-4">Start a New Project</h2>
        <p className="text-muted-foreground">
          Describe your research goal and watch as the AI breaks it down into manageable tasks
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="relative">
          <Textarea
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder="Enter your project goal here..."
            className="min-h-[120px] pr-12 resize-none"
            disabled={isStarting}
          />
        </div>
        
        <div className="flex justify-between items-center">
          <div className="text-sm text-muted-foreground">
            {isConnected ? (
              <span className="text-green-600">✓ Connected to backend</span>
            ) : (
              <span className="text-red-600">✗ Backend disconnected</span>
            )}
          </div>
          
          <Button 
            type="submit" 
            disabled={!goal.trim() || !isConnected || isStarting}
            className="min-w-[120px]"
          >
            {isStarting ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Starting...
              </>
            ) : (
              <>
                <Send className="w-4 h-4 mr-2" />
                Start Project
              </>
            )}
          </Button>
        </div>
      </form>
    </div>
  )
}

export default ProjectInput 