import React, { useState, useEffect } from 'react'
import { useProjectStore } from '@/stores/projectStore'
import { useTaskGraphStore } from '@/stores/taskGraphStore'
import { projectService } from '@/services/projectService'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Plus,
  MessageSquare,
  MoreVertical,
  Trash2,
  Calendar,
  Activity,
  ChevronLeft,
  ChevronRight,
  Loader2
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { toast } from '@/components/ui/use-toast'

const ProjectSidebar: React.FC = () => {
  const {
    projects,
    currentProjectId,
    isSidebarOpen,
    isCreatingProject,
    setSidebarOpen,
    setCreatingProject,
    setProjects,
    setCurrentProject,
    addProject,
    removeProject,
    getCurrentProject,
    getRecentProjects
  } = useProjectStore()

  const { setLoading } = useTaskGraphStore()
  
  const [newProjectGoal, setNewProjectGoal] = useState('')
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [loadingProjectId, setLoadingProjectId] = useState<string | null>(null)

  // Load projects on mount
  useEffect(() => {
    loadProjects()
  }, [])

  const loadProjects = async () => {
    try {
      const data = await projectService.getProjects()
      setProjects(data.projects)
      if (data.current_project_id) {
        setCurrentProject(data.current_project_id)
      }
    } catch (error) {
      console.error('Failed to load projects:', error)
      toast({
        title: "Error",
        description: "Failed to load projects",
        variant: "destructive",
      })
    }
  }

  const handleCreateProject = async () => {
    if (!newProjectGoal.trim()) return

    setCreatingProject(true)
    try {
      const result = await projectService.createProject(newProjectGoal.trim())
      addProject(result.project)
      setNewProjectGoal('')
      setIsDialogOpen(false)
      setLoading(true) // Start loading state for graph
      
      toast({
        title: "Project Created",
        description: result.message,
      })
    } catch (error) {
      console.error('Failed to create project:', error)
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to create project",
        variant: "destructive",
      })
    } finally {
      setCreatingProject(false)
    }
  }

  const handleSwitchProject = async (projectId: string) => {
    if (projectId === currentProjectId) return

    setLoadingProjectId(projectId)
    setLoading(true)
    
    try {
      await projectService.switchProject(projectId)
      setCurrentProject(projectId)
      
      toast({
        title: "Project Switched",
        description: "Successfully switched to project",
      })
    } catch (error) {
      console.error('Failed to switch project:', error)
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to switch project",
        variant: "destructive",
      })
    } finally {
      setLoadingProjectId(null)
      setLoading(false)
    }
  }

  const handleDeleteProject = async (projectId: string, e?: React.MouseEvent) => {
    if (e) {
      e.preventDefault()
      e.stopPropagation()
    }
    
    if (!confirm('Are you sure you want to delete this project? This action cannot be undone.')) {
      return
    }

    try {
      await projectService.deleteProject(projectId)
      removeProject(projectId)
      
      toast({
        title: "Project Deleted",
        description: "Project has been deleted successfully",
      })
    } catch (error) {
      console.error('Failed to delete project:', error)
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to delete project",
        variant: "destructive",
      })
    }
  }

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))
    
    if (diffDays === 0) return 'Today'
    if (diffDays === 1) return 'Yesterday'
    if (diffDays < 7) return `${diffDays} days ago`
    return date.toLocaleDateString()
  }

  const truncateText = (text: string, maxLength: number = 100) => {
    if (text.length <= maxLength) return text
    return text.substring(0, maxLength) + '...'
  }

  const recentProjects = getRecentProjects()
  const currentProject = getCurrentProject()

  return (
    <div className={cn(
      "h-full bg-background border-r transition-all duration-300 flex flex-col",
      isSidebarOpen ? "w-80" : "w-12"
    )}>
      {/* Header */}
      <div className="p-4 border-b flex items-center justify-between">
        {isSidebarOpen && (
          <h2 className="font-semibold text-lg">Projects</h2>
        )}
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setSidebarOpen(!isSidebarOpen)}
          className="ml-auto"
        >
          {isSidebarOpen ? <ChevronLeft className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </Button>
      </div>

      {isSidebarOpen && (
        <>
          {/* New Project Button */}
          <div className="p-4">
            <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
              <DialogTrigger asChild>
                <Button className="w-full" size="sm">
                  <Plus className="h-4 w-4 mr-2" />
                  New Project
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Create New Project</DialogTitle>
                </DialogHeader>
                <div className="space-y-4">
                  <div>
                    <label className="text-sm font-medium">Project Goal</label>
                    <Textarea
                      value={newProjectGoal}
                      onChange={(e) => setNewProjectGoal(e.target.value)}
                      placeholder="Describe what you want to research or accomplish..."
                      className="mt-1"
                      rows={4}
                    />
                  </div>
                  <div className="flex justify-end space-x-2">
                    <Button
                      variant="outline"
                      onClick={() => setIsDialogOpen(false)}
                      disabled={isCreatingProject}
                    >
                      Cancel
                    </Button>
                    <Button
                      onClick={handleCreateProject}
                      disabled={!newProjectGoal.trim() || isCreatingProject}
                    >
                      {isCreatingProject ? (
                        <>
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          Creating...
                        </>
                      ) : (
                        'Create Project'
                      )}
                    </Button>
                  </div>
                </div>
              </DialogContent>
            </Dialog>
          </div>

          {/* Current Project */}
          {currentProject && (
            <div className="px-4 pb-4">
              <div className="text-xs font-medium text-muted-foreground mb-2">CURRENT PROJECT</div>
              <div className="bg-muted/50 rounded-lg p-3 border-l-4 border-blue-500">
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium text-sm truncate">{currentProject.title}</h3>
                    <p className="text-xs text-muted-foreground mt-1">
                      {truncateText(currentProject.description, 80)}
                    </p>
                    <div className="flex items-center gap-2 mt-2">
                      <Badge variant="secondary" className="text-xs">
                        {currentProject.status}
                      </Badge>
                      {currentProject.node_count > 0 && (
                        <span className="text-xs text-muted-foreground">
                          {currentProject.node_count} nodes
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Projects List */}
          <div className="flex-1 overflow-hidden">
            <div className="px-4 pb-2">
              <div className="text-xs font-medium text-muted-foreground">RECENT PROJECTS</div>
            </div>
            <ScrollArea className="flex-1 px-4">
              <div className="space-y-2">
                {recentProjects.map((project) => (
                  <div
                    key={project.id}
                    className={cn(
                      "group rounded-lg p-3 cursor-pointer transition-colors hover:bg-muted/50",
                      project.id === currentProjectId && "bg-muted/30 border border-border"
                    )}
                    onClick={() => handleSwitchProject(project.id)}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <MessageSquare className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                          <h3 className="font-medium text-sm truncate">{project.title}</h3>
                          {loadingProjectId === project.id && (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                          {truncateText(project.description, 60)}
                        </p>
                        <div className="flex items-center justify-between mt-2">
                          <div className="flex items-center gap-2">
                            <Badge variant="outline" className="text-xs">
                              {project.status}
                            </Badge>
                            {project.node_count > 0 && (
                              <span className="text-xs text-muted-foreground">
                                {project.node_count} nodes
                              </span>
                            )}
                          </div>
                          <span className="text-xs text-muted-foreground">
                            {formatDate(project.updated_at)}
                          </span>
                        </div>
                      </div>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="opacity-0 group-hover:opacity-100 transition-opacity ml-2"
                          >
                            <MoreVertical className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            onClick={(e) => handleDeleteProject(project.id, e)}
                            className="text-red-600 hover:text-red-700 hover:bg-red-50"
                          >
                            <Trash2 className="h-4 w-4 mr-2" />
                            Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </div>
        </>
      )}
    </div>
  )
}

export default ProjectSidebar 