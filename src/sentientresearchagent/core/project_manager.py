import uuid
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import threading
from loguru import logger

@dataclass
class ProjectMetadata:
    """Metadata for a project/chat session"""
    id: str
    title: str
    description: str
    created_at: datetime
    updated_at: datetime
    status: str  # 'active', 'completed', 'failed', 'paused', 'running'
    goal: str
    max_steps: int
    node_count: int = 0
    completion_percentage: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        # Convert datetime objects to ISO strings
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProjectMetadata':
        # Convert ISO strings back to datetime objects
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        return cls(**data)

class ProjectManager:
    """Manages multiple projects/chat sessions"""
    
    def __init__(self, projects_dir: str = ".agent_projects"):
        self.projects_dir = Path(projects_dir)
        self.projects_dir.mkdir(exist_ok=True)
        self.projects: Dict[str, ProjectMetadata] = {}
        self.current_project_id: Optional[str] = None
        self._lock = threading.Lock()
        self._load_projects()
    
    def _load_projects(self):
        """Load existing projects from disk"""
        try:
            projects_file = self.projects_dir / "projects.json"
            if projects_file.exists():
                with open(projects_file, 'r') as f:
                    data = json.load(f)
                    for project_data in data.get('projects', []):
                        project = ProjectMetadata.from_dict(project_data)
                        self.projects[project.id] = project
                    self.current_project_id = data.get('current_project_id')
                logger.info(f"Loaded {len(self.projects)} existing projects")
        except Exception as e:
            logger.error(f"Failed to load projects: {e}")
    
    def _save_projects(self):
        """Save projects metadata to disk"""
        try:
            projects_file = self.projects_dir / "projects.json"
            data = {
                'projects': [project.to_dict() for project in self.projects.values()],
                'current_project_id': self.current_project_id
            }
            with open(projects_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save projects: {e}")
    
    def create_project(self, goal: str, max_steps: int = 250) -> ProjectMetadata:
        """Create a new project"""
        with self._lock:
            project_id = str(uuid.uuid4())
            
            # Generate a smart title from the goal
            title = self._generate_title(goal)
            
            project = ProjectMetadata(
                id=project_id,
                title=title,
                description=goal[:200] + "..." if len(goal) > 200 else goal,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                status='active',
                goal=goal,
                max_steps=max_steps
            )
            
            self.projects[project_id] = project
            self.current_project_id = project_id
            self._save_projects()
            
            # Create project directory for storing graph state
            project_dir = self.projects_dir / project_id
            project_dir.mkdir(exist_ok=True)
            
            logger.info(f"Created new project: {project_id} - {title}")
            return project
    
    def _generate_title(self, goal: str) -> str:
        """Generate a smart title from the project goal"""
        # Simple title generation - could be enhanced with AI
        words = goal.split()[:8]  # Take first 8 words
        title = " ".join(words)
        if len(goal.split()) > 8:
            title += "..."
        return title.title()
    
    def get_project(self, project_id: str) -> Optional[ProjectMetadata]:
        """Get a specific project"""
        return self.projects.get(project_id)
    
    def get_all_projects(self) -> List[ProjectMetadata]:
        """Get all projects sorted by updated_at desc"""
        return sorted(
            self.projects.values(),
            key=lambda p: p.updated_at,
            reverse=True
        )
    
    def update_project(self, project_id: str, **updates) -> Optional[ProjectMetadata]:
        """Update project metadata"""
        with self._lock:
            if project_id not in self.projects:
                return None
            
            project = self.projects[project_id]
            for key, value in updates.items():
                if hasattr(project, key):
                    setattr(project, key, value)
            
            project.updated_at = datetime.now()
            self._save_projects()
            return project
    
    def delete_project(self, project_id: str) -> bool:
        """Delete a project"""
        with self._lock:
            if project_id not in self.projects:
                return False
            
            # Remove project directory
            project_dir = self.projects_dir / project_id
            if project_dir.exists():
                import shutil
                shutil.rmtree(project_dir)
            
            # Remove from memory and update current if needed
            del self.projects[project_id]
            if self.current_project_id == project_id:
                self.current_project_id = None
            
            self._save_projects()
            logger.info(f"Deleted project: {project_id}")
            return True
    
    def set_current_project(self, project_id: str) -> bool:
        """Set the current active project"""
        if project_id not in self.projects:
            return False
        
        self.current_project_id = project_id
        self._save_projects()
        return True
    
    def get_current_project(self) -> Optional[ProjectMetadata]:
        """Get the current active project"""
        if self.current_project_id:
            return self.projects.get(self.current_project_id)
        return None
    
    def get_current_project_id(self) -> Optional[str]:
        """Get the current active project ID"""
        return self.current_project_id
    
    def switch_project(self, project_id: str) -> bool:
        """Switch to a different project (alias for set_current_project)"""
        return self.set_current_project(project_id)
    
    def save_project_state(self, project_id: str, task_graph_data: Dict[str, Any]):
        """Save the current task graph state for a project"""
        try:
            project_dir = self.projects_dir / project_id
            project_dir.mkdir(exist_ok=True)
            
            state_file = project_dir / "graph_state.json"
            with open(state_file, 'w') as f:
                json.dump(task_graph_data, f, indent=2, default=str)  # default=str to handle datetime objects
                
            # Update project stats
            node_count = len(task_graph_data.get('all_nodes', {}))
            self.update_project(project_id, node_count=node_count)
            
        except Exception as e:
            logger.error(f"Failed to save project state for {project_id}: {e}")
    
    def load_project_state(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Load the task graph state for a project"""
        try:
            project_dir = self.projects_dir / project_id
            state_file = project_dir / "graph_state.json"
            
            if state_file.exists():
                with open(state_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load project state for {project_id}: {e}")
        
        return None 