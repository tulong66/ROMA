import type { Project } from '@/stores/projectStore'
import type { ProjectConfig } from '@/components/project/ProjectConfigPanel'

class ProjectService {
  private baseUrl = 'http://localhost:5000/api'

  async getProjects(): Promise<{ projects: Project[], current_project_id?: string }> {
    const response = await fetch(`${this.baseUrl}/projects`)
    if (!response.ok) {
      throw new Error('Failed to fetch projects')
    }
    return response.json()
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
  }

  async getProject(projectId: string): Promise<{ project: Project, state?: any }> {
    const response = await fetch(`${this.baseUrl}/projects/${projectId}`)
    if (!response.ok) {
      throw new Error('Failed to fetch project')
    }
    return response.json()
  }

  async switchProject(projectId: string): Promise<{ project: Project, message: string }> {
    const response = await fetch(`${this.baseUrl}/projects/${projectId}/switch`, {
      method: 'POST',
    })
    
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.error || 'Failed to switch project')
    }
    
    return response.json()
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
}

export const projectService = new ProjectService() 