import React, { useState } from 'react'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Bot, CheckCircle, AlertCircle, Info } from 'lucide-react'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'

// Hardcoded profiles for now (until backend API is ready)
const AVAILABLE_PROFILES = [
  {
    name: 'deep_research_agent',
    displayName: 'Deep Research Agent',
    description: 'Comprehensive research agent with task-specific planners and specialized executors',
    is_valid: true,
    planner_mappings: {
      'SEARCH': 'CoreResearchPlanner',
      'WRITE': 'CoreResearchPlanner', 
      'THINK': 'CoreResearchPlanner'
    },
    executor_mappings: {
      'SEARCH': 'OpenAICustomSearcher',
      'THINK': 'SearchSynthesizer',
      'WRITE': 'BasicReportWriter'
    },
    recommended_for: ['Academic research', 'Market analysis', 'Technical investigation']
  },
  {
    name: 'general_agent',
    displayName: 'General Agent',
    description: 'Balanced agent suitable for general-purpose tasks',
    is_valid: true,
    planner_mappings: {
      'SEARCH': 'SimpleTestPlanner',
      'WRITE': 'SimpleTestPlanner',
      'THINK': 'SimpleTestPlanner'
    },
    executor_mappings: {
      'SEARCH': 'OpenAICustomSearcher',
      'THINK': 'SearchSynthesizer', 
      'WRITE': 'BasicReportWriter'
    },
    recommended_for: ['General tasks', 'Quick analysis', 'Simple research']
  }
]

interface ProjectProfileSelectorProps {
  selectedProfile: string
  onProfileChange: (profileName: string) => void
}

const ProjectProfileSelector: React.FC<ProjectProfileSelectorProps> = ({
  selectedProfile,
  onProfileChange
}) => {
  const selectedProfileData = AVAILABLE_PROFILES.find(p => p.name === selectedProfile)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Bot className="h-5 w-5" />
          Agent Profile
        </CardTitle>
        <CardDescription>
          Choose the AI agent profile that best fits your project type
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="profile-select">Select Profile</Label>
          <Select value={selectedProfile} onValueChange={onProfileChange}>
            <SelectTrigger id="profile-select">
              <SelectValue placeholder="Choose an agent profile..." />
            </SelectTrigger>
            <SelectContent>
              {AVAILABLE_PROFILES.map((profile) => (
                <SelectItem key={profile.name} value={profile.name}>
                  <div className="flex items-center space-x-2">
                    {profile.is_valid ? (
                      <CheckCircle className="w-4 h-4 text-green-500" />
                    ) : (
                      <AlertCircle className="w-4 h-4 text-yellow-500" />
                    )}
                    <span>{profile.displayName}</span>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Profile Details */}
        {selectedProfileData && (
          <div className="mt-4 p-4 bg-muted/50 rounded-lg space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="font-medium text-sm">{selectedProfileData.displayName}</h4>
              <Badge variant="secondary" className="text-xs">
                {selectedProfileData.is_valid ? 'Ready' : 'Issues'}
              </Badge>
            </div>
            
            <p className="text-sm text-muted-foreground">
              {selectedProfileData.description}
            </p>

            {/* Recommended For */}
            <div>
              <p className="text-xs font-medium mb-1">Recommended for:</p>
              <div className="flex flex-wrap gap-1">
                {selectedProfileData.recommended_for.map((use, index) => (
                  <Badge key={index} variant="outline" className="text-xs">
                    {use}
                  </Badge>
                ))}
              </div>
            </div>

            {/* Capabilities */}
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <p className="font-medium mb-1">Task Planners:</p>
                <div className="space-y-1">
                  {Object.entries(selectedProfileData.planner_mappings).map(([task, planner]) => (
                    <div key={task} className="flex justify-between">
                      <span className="text-muted-foreground">{task}:</span>
                      <span>{planner}</span>
                    </div>
                  ))}
                </div>
              </div>
              
              <div>
                <p className="font-medium mb-1">Task Executors:</p>
                <div className="space-y-1">
                  {Object.entries(selectedProfileData.executor_mappings).map(([task, executor]) => (
                    <div key={task} className="flex justify-between">
                      <span className="text-muted-foreground">{task}:</span>
                      <span>{executor}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default ProjectProfileSelector 