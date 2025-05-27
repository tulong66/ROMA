import React, { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Send, Loader2, Settings } from 'lucide-react'
import { useTaskGraphStore } from '@/stores/taskGraphStore'
import { useProjectStore } from '@/stores/projectStore'
import { projectService } from '@/services/projectService'
import { toast } from '@/components/ui/use-toast'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import ProjectConfigPanel, { ProjectConfig } from './ProjectConfigPanel'

const ProjectInput: React.FC = () => {
  const [goal, setGoal] = useState('Write me a detailed report about the recent U.S. trade tariffs and their effect on the global economy')
  const [isStarting, setIsStarting] = useState(false)
  const [showConfigDialog, setShowConfigDialog] = useState(false)
  const { isConnected, setLoading } = useTaskGraphStore()
  const { addProject, getCurrentProject } = useProjectStore()

  // Default configuration
  const [config, setConfig] = useState<ProjectConfig>({
    llm: {
      provider: 'openai',
      model: 'gpt-4',
      temperature: 0.7,
      timeout: 30,
      max_retries: 3
    },
    execution: {
      max_concurrent_nodes: 3,
      max_execution_steps: 250,
      enable_hitl: true,
      hitl_root_plan_only: false,
      hitl_timeout_seconds: 300,
      hitl_after_plan_generation: true,
      hitl_after_modified_plan: true,
      hitl_after_atomizer: false,
      hitl_before_execute: false
    },
    cache: {
      enabled: true,
      ttl_seconds: 3600,
      max_size: 1000,
      cache_type: 'memory'
    },
    project: {
      goal: goal,
      max_steps: 250
    }
  })

  const currentProject = getCurrentProject()

  // Update config when goal changes
  React.useEffect(() => {
    setConfig(prev => ({
      ...prev,
      project: {
        ...prev.project,
        goal: goal
      }
    }))
  }, [goal])

  const handleQuickSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!goal.trim() || !isConnected) return

    console.log('🚀 Starting project with default config')
    await createProject(config)
  }

  const handleConfiguredSubmit = async () => {
    console.log('🚀 Starting project with custom config')
    await createProject(config)
    setShowConfigDialog(false)
  }

  const createProject = async (projectConfig: ProjectConfig) => {
    setIsStarting(true)
    setLoading(true)
    
    try {
      const result = await projectService.createProjectWithConfig(
        projectConfig.project.goal.trim(),
        projectConfig
      )
      addProject(result.project)
      
      toast({
        title: "Project Created",
        description: result.message,
      })
      
      console.log('✅ Project created and started')
    } catch (error) {
      console.error('❌ Failed to create project:', error)
      setLoading(false)
      
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to create project",
        variant: "destructive",
      })
    } finally {
      setIsStarting(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto p-8">
      <div className="text-center mb-8">
        <h2 className="text-3xl font-bold mb-4">
          {currentProject ? 'Start Another Project' : 'Start a New Project'}
        </h2>
        <p className="text-muted-foreground">
          Describe your research goal and watch as the AI breaks it down into manageable tasks
        </p>
      </div>

      <form onSubmit={handleQuickSubmit} className="space-y-4">
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
          
          <div className="flex gap-2">
            {/* Quick Start Button */}
            <Button 
              type="submit" 
              disabled={!goal.trim() || !isConnected || isStarting}
              className="min-w-[120px]"
            >
              {isStarting ? (
                <>
                  <Loader2 className="w-4 w-4 mr-2 animate-spin" />
                  Creating...
                </>
              ) : (
                <>
                  <Send className="w-4 h-4 mr-2" />
                  Quick Start
                </>
              )}
            </Button>

            {/* Configure & Start Button */}
            <Dialog open={showConfigDialog} onOpenChange={setShowConfigDialog}>
              <DialogTrigger asChild>
                <Button 
                  type="button"
                  variant="outline"
                  disabled={!goal.trim() || !isConnected || isStarting}
                  className="min-w-[140px]"
                >
                  <Settings className="w-4 h-4 mr-2" />
                  Configure & Start
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-5xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle>Configure Project</DialogTitle>
                </DialogHeader>
                <ProjectConfigPanel
                  config={config}
                  onChange={setConfig}
                  onSubmit={handleConfiguredSubmit}
                  onCancel={() => setShowConfigDialog(false)}
                  isCreating={isStarting}
                />
              </DialogContent>
            </Dialog>
          </div>
        </div>
      </form>

      {/* Configuration Preview */}
      <div className="mt-6 p-4 bg-muted/50 rounded-lg">
        <h4 className="text-sm font-medium mb-2">Current Configuration:</h4>
        <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
          <div>Model: {config.llm.provider}/{config.llm.model}</div>
          <div>Temperature: {config.llm.temperature}</div>
          <div>Max Steps: {config.execution.max_execution_steps}</div>
          <div>HITL: {config.execution.enable_hitl ? 
            (config.execution.hitl_root_plan_only ? 'Root Only' : 'Full') : 
            'Disabled'
          }</div>
        </div>
      </div>
    </div>
  )
}

export default ProjectInput 