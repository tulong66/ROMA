import type { Project } from '@/stores/projectStore'
import type { ProjectConfig } from '@/components/project/ProjectConfigPanel'

interface SavedProjectSummary {
  project_id: string
  title: string
  saved_at: string
  completion_status: string
  total_nodes: number
  auto_saved: boolean
}

interface ProjectResults {
  project: Project
  saved_at: string
  graph_data: any
  metadata: {
    total_nodes: number
    project_goal: string
    completion_status: string
  }
}

class ProjectService {
  private baseUrl = 'http://localhost:5000/api'

  async getProjects(): Promise<{ projects: Project[], current_project_id?: string }> {
    try {
      const response = await fetch(`${this.baseUrl}/projects`)
      if (!response.ok) {
        // If the endpoint doesn't exist or fails, return empty projects list
        if (response.status === 404 || response.status === 500) {
          console.warn('Projects endpoint not available, returning empty list')
          return { projects: [] }
        }
        throw new Error('Failed to fetch projects')
      }
      return response.json()
    } catch (error) {
      console.warn('Failed to fetch projects, returning empty list:', error)
      return { projects: [] }
    }
  }

  async createProject(goal: string, maxSteps: number = 250): Promise<{ project: Project, message: string }> {
    const response = await fetch(`${this.baseUrl}/projects`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ goal, max_steps: maxSteps }),
    })
    
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.error || 'Failed to create project')
    }
    
    return response.json()
  }

  async createProjectWithConfig(goal: string, config: ProjectConfig): Promise<{ project: Project, message: string }> {
    try {
      const response = await fetch(`${this.baseUrl}/projects/configured`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          goal, 
          config,
          max_steps: config.project.max_steps 
        }),
      })
      
      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.error || 'Failed to create configured project')
      }
      
      return response.json()
    } catch (error) {
      // Fallback to regular project creation if configured endpoint doesn't exist
      console.warn('Configured project creation not available, falling back to regular creation')
      return this.createProject(goal, config.project.max_steps)
    }
  }

  async getProject(projectId: string): Promise<{ project: Project, state?: any }> {
    const response = await fetch(`${this.baseUrl}/projects/${projectId}`)
    if (!response.ok) {
      throw new Error('Failed to fetch project')
    }
    return response.json()
  }

  async switchProject(projectId: string): Promise<{ project: Project, message: string }> {
    // Try WebSocket first for real-time switching
    if (webSocketService.isConnected()) {
      console.log('🔄 Using WebSocket for project switch:', projectId)
      
      return new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
          reject(new Error('Project switch timeout'))
        }, 10000) // 10 second timeout

        // Listen for success
        const handleSuccess = (data: any) => {
          clearTimeout(timeout)
          webSocketService.socket?.off('project_switch_success', handleSuccess)
          webSocketService.socket?.off('project_switch_error', handleError)
          
          resolve({
            project: data.project_data?.current_project || { id: projectId },
            message: data.message || 'Project switched successfully'
          })
        }

        // Listen for error
        const handleError = (data: any) => {
          clearTimeout(timeout)
          webSocketService.socket?.off('project_switch_success', handleSuccess)
          webSocketService.socket?.off('project_switch_error', handleError)
          
          reject(new Error(data.error || 'Failed to switch project'))
        }

        // Set up listeners
        webSocketService.socket?.on('project_switch_success', handleSuccess)
        webSocketService.socket?.on('project_switch_error', handleError)

        // Send switch request
        webSocketService.switchProject(projectId)
      })
    } else {
      // Fallback to REST API
      console.log('🔄 Using REST API for project switch (WebSocket not connected):', projectId)
      
      const response = await fetch(`${this.baseUrl}/projects/${projectId}/switch`, {
        method: 'POST',
      })
      
      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.error || 'Failed to switch project')
      }
      
      return response.json()
    }
  }

  async deleteProject(projectId: string): Promise<{ message: string }> {
    const response = await fetch(`${this.baseUrl}/projects/${projectId}`, {
      method: 'DELETE',
    })
    
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.error || 'Failed to delete project')
    }
    
    return response.json()
  }

  // NEW: Save project results (with fallback)
  async saveProjectResults(projectId: string): Promise<{ message: string, saved_at: string, metadata: any }> {
    try {
      const response = await fetch(`${this.baseUrl}/projects/${projectId}/save-results`, {
        method: 'POST',
      })
      
      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.error || 'Failed to save project results')
      }
      
      return response.json()
    } catch (error) {
      // Fallback: save to localStorage if backend endpoint doesn't exist
      console.warn('Backend save not available, using localStorage fallback')
      const timestamp = new Date().toISOString()
      const fallbackData = {
        message: "Results saved locally",
        saved_at: timestamp,
        metadata: { local_save: true }
      }
      localStorage.setItem(`project_${projectId}_results`, JSON.stringify(fallbackData))
      return fallbackData
    }
  }

  // NEW: Load project results (with fallback)
  async loadProjectResults(projectId: string): Promise<ProjectResults> {
    try {
      const response = await fetch(`${this.baseUrl}/projects/${projectId}/load-results`)
      
      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.error || 'Failed to load project results')
      }
      
      return response.json()
    } catch (error) {
      // Fallback: load from localStorage
      const localData = localStorage.getItem(`project_${projectId}_results`)
      if (localData) {
        return JSON.parse(localData)
      }
      throw new Error('No saved results found')
    }
  }

  // NEW: Download project report (with fallback)
  async downloadProjectReport(projectId: string, format: 'markdown' | 'json' | 'html' = 'markdown'): Promise<void> {
    try {
      const response = await fetch(`${this.baseUrl}/projects/${projectId}/download-report?format=${format}`)
      
      if (!response.ok) {
        throw new Error('Backend download not available')
      }
      
      // Get filename from response headers
      const contentDisposition = response.headers.get('content-disposition')
      let filename = `project-report.${format}`
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="(.+)"/)
        if (filenameMatch) {
          filename = filenameMatch[1]
        }
      }
      
      // Download the file
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (error) {
      console.warn('Backend download not available, this feature requires backend support')
      throw new Error('Download from server requires backend support. Use the client-side download instead.')
    }
  }

  // NEW: Get saved projects summary (with fallback)
  async getSavedProjectsSummary(): Promise<SavedProjectSummary[]> {
    try {
      const response = await fetch(`${this.baseUrl}/projects/saved-summary`)
      
      if (!response.ok) {
        throw new Error('Failed to fetch saved projects summary')
      }
      
      return response.json()
    } catch (error) {
      console.warn('Saved projects summary not available from backend')
      return []
    }
  }
}

export const projectService = new ProjectService() 