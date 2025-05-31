import React, { useState, useEffect } from 'react'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Bot, CheckCircle, AlertCircle, Loader2, RefreshCw, Info, Crown } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'

interface Profile {
  name: string
  description: string
  planner_mappings: Record<string, string>
  executor_mappings: Record<string, string>
  atomizer: string
  aggregator: string
  plan_modifier: string
  default_planner: string
  default_executor: string
  is_current: boolean
  is_valid: boolean
  validation?: {
    blueprint_valid: boolean
    missing_agents?: string[]
  }
  root_planner: string
  recommended_for?: string[]
}

interface ProjectProfileSelectorProps {
  selectedProfile: string
  onProfileChange: (profileName: string) => void
}

const ProjectProfileSelector: React.FC<ProjectProfileSelectorProps> = ({
  selectedProfile,
  onProfileChange
}) => {
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Load profiles from API
  useEffect(() => {
    const loadProfiles = async () => {
      try {
        setLoading(true)
        console.log('🔍 Attempting to fetch profiles from /api/profiles')
        
        const response = await fetch('/api/profiles')
        console.log('📡 Response status:', response.status, response.statusText)
        console.log('📡 Response headers:', Object.fromEntries(response.headers.entries()))
        
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`)
        }
        
        const responseText = await response.text()
        console.log('📄 Raw response text (first 200 chars):', responseText.substring(0, 200))
        
        // Check if response is HTML (indicates API route not working)
        if (responseText.trim().startsWith('<!doctype') || responseText.trim().startsWith('<html')) {
          throw new Error('API returned HTML instead of JSON - API route may not be working')
        }
        
        let data
        try {
          data = JSON.parse(responseText)
        } catch (parseError) {
          console.error('❌ JSON parse error:', parseError)
          console.error('📄 Full response text:', responseText)
          throw new Error(`Invalid JSON response: ${parseError.message}`)
        }
        
        console.log('✅ Parsed data:', data)
        
        if (data.profiles) {
          // Transform API data to match our interface
          const transformedProfiles = data.profiles.map((profile: any) => ({
            name: profile.name,
            description: profile.description,
            root_planner: profile.root_planner,
            planner_mappings: profile.planner_mappings || {},
            executor_mappings: profile.executor_mappings || {},
            is_valid: profile.is_valid,
            validation: profile.validation
          }))
          
          console.log('🔄 Transformed profiles:', transformedProfiles)
          setProfiles(transformedProfiles)
          
          // If no profile is selected, select the first valid one or the current one
          if (!selectedProfile && data.profiles.length > 0) {
            const currentProfile = data.profiles.find((p: Profile) => p.is_current)
            const firstValidProfile = data.profiles.find((p: Profile) => p.is_valid)
            const defaultProfile = currentProfile || firstValidProfile || data.profiles[0]
            onProfileChange(defaultProfile.name)
          }
        } else {
          throw new Error('Invalid API response format - missing profiles field')
        }
      } catch (err) {
        console.error('❌ Failed to load profiles:', err)
        setError(err instanceof Error ? err.message : 'Failed to load profiles')
        
        // Fallback to hardcoded profiles if API fails
        console.log('🔄 Using fallback hardcoded profiles')
        setProfiles([
          {
            name: 'deep_research_agent',
            description: 'Comprehensive research agent with specialized root planner and task-specific executors',
            root_planner: 'DeepResearchPlanner',
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
            is_valid: true
          }
        ])
        if (!selectedProfile) {
          onProfileChange('deep_research_agent')
        }
      } finally {
        setLoading(false)
      }
    }

    loadProfiles()
  }, [])

  const selectedProfileData = profiles.find(p => p.name === selectedProfile)

  const getDisplayName = (profileName: string) => {
    // Convert snake_case to Title Case
    return profileName
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ')
  }

  const getRecommendedFor = (profile: Profile): string[] => {
    if (!profile) return ['Custom tasks'] // Safety check
    
    if (profile.name === 'deep_research_agent') {
      return ['Academic research', 'Market analysis', 'Technical investigation']
    }
    if (profile.name === 'general_agent') {
      return ['General tasks', 'Quick analysis', 'Simple research']
    }
    return ['Custom tasks']
  }

  if (loading) {
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
        <CardContent className="flex items-center justify-center py-8">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading profiles...
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Bot className="h-5 w-5" />
          Agent Profile
          {loading && <Loader2 className="h-4 w-4 animate-spin" />}
        </CardTitle>
        <CardDescription>
          Choose the AI agent profile that best fits your project type
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && (
          <div className="p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <AlertCircle className="h-4 w-4 text-yellow-600" />
                <span className="text-sm text-yellow-700 dark:text-yellow-300">
                  API Error: {error}
                </span>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  // Implement retry logic here
                }}
                className="h-6 text-xs"
              >
                <RefreshCw className="h-3 w-3 mr-1" />
                Retry
              </Button>
            </div>
            <p className="text-xs text-yellow-600 dark:text-yellow-400 mt-1">
              Using fallback configuration. Some features may be limited.
            </p>
          </div>
        )}

        <div className="space-y-2">
          <Label htmlFor="profile-select">Select Profile</Label>
          <Select value={selectedProfile} onValueChange={onProfileChange} disabled={loading}>
            <SelectTrigger id="profile-select">
              <SelectValue placeholder="Choose an agent profile..." />
            </SelectTrigger>
            <SelectContent>
              {profiles.map((profile) => (
                <SelectItem key={profile.name} value={profile.name}>
                  <div className="flex items-center space-x-2">
                    {profile.is_valid ? (
                      <CheckCircle className="w-4 h-4 text-green-500" />
                    ) : (
                      <AlertCircle className="w-4 h-4 text-yellow-500" />
                    )}
                    <span>{getDisplayName(profile.name)}</span>
                    {profile.is_current && (
                      <Badge variant="secondary" className="text-xs ml-2">
                        Current
                      </Badge>
                    )}
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
              <h4 className="font-medium text-sm">{getDisplayName(selectedProfileData.name)}</h4>
              <div className="flex items-center space-x-2">
                {selectedProfileData.is_current && (
                  <Badge variant="default" className="text-xs">
                    Active
                  </Badge>
                )}
                <Badge variant={selectedProfileData.is_valid ? "secondary" : "outline"} className="text-xs">
                  {selectedProfileData.is_valid ? 'Ready' : 'Issues'}
                </Badge>
              </div>
            </div>
            
            <p className="text-sm text-muted-foreground">
              {selectedProfileData.description}
            </p>

            {/* Validation Issues */}
            {!selectedProfileData.is_valid && selectedProfileData.validation?.missing_agents && (
              <div className="p-2 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded">
                <p className="text-xs font-medium text-yellow-700 dark:text-yellow-300 mb-1">
                  Validation Issues:
                </p>
                <ul className="text-xs text-yellow-600 dark:text-yellow-400 space-y-1">
                  {selectedProfileData.validation.missing_agents.map((agent, index) => (
                    <li key={index}>• Missing agent: {agent}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Recommended For */}
            {selectedProfileData.recommended_for && selectedProfileData.recommended_for.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {selectedProfileData.recommended_for.map((use, index) => (
                  <Badge key={index} variant="secondary" className="text-xs">
                    {use}
                  </Badge>
                ))}
              </div>
            )}

            {/* Root Planner - NEW */}
            <div className="border-t pt-3">
              <div className="flex items-center gap-2 mb-2">
                <Crown className="h-4 w-4 text-amber-500" />
                <p className="text-xs font-medium">Root Planner:</p>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger>
                      <Info className="h-3 w-3 text-muted-foreground" />
                    </TooltipTrigger>
                    <TooltipContent>
                      <p className="text-xs">Specialized planner for initial project decomposition</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
              <Badge variant="default" className="text-xs bg-amber-100 text-amber-800 border-amber-200">
                {selectedProfileData.root_planner}
              </Badge>
            </div>

            {/* Capabilities */}
            <div className="grid grid-cols-2 gap-3 text-xs border-t pt-3">
              <div>
                <p className="font-medium mb-1">Sub-task Planners:</p>
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

        {profiles.length === 0 && !loading && (
          <div className="text-center py-4 text-sm text-muted-foreground">
            No profiles available
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default ProjectProfileSelector 