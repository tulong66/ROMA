import React, { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'
import { Info, Settings, Zap, Database, MessageSquare, Layers, Clock, Target } from 'lucide-react'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'

export interface ProjectConfig {
  // LLM Configuration
  llm: {
    provider: string
    model: string
    temperature: number
    max_tokens?: number
    timeout: number
    max_retries: number
  }
  
  // Execution Configuration
  execution: {
    max_concurrent_nodes: number
    max_execution_steps: number
    max_recursion_depth: number
    task_timeout_seconds: number
    enable_hitl: boolean
    hitl_root_plan_only: boolean
    hitl_timeout_seconds: number
    hitl_after_plan_generation: boolean
    hitl_after_modified_plan: boolean
    hitl_after_atomizer: boolean
    hitl_before_execute: boolean
    max_replan_attempts: number
    execution_timeout: number
  }
  
  // Cache Configuration
  cache: {
    enabled: boolean
    ttl_seconds: number
    max_size: number
    cache_type: string
  }
  
  // Project-specific settings
  project: {
    goal: string
    max_steps: number
    description?: string
  }
}

interface ProjectConfigPanelProps {
  config: ProjectConfig
  onChange: (config: ProjectConfig) => void
  onSubmit: () => void
  onCancel: () => void
  isCreating: boolean
}

const ProjectConfigPanel: React.FC<ProjectConfigPanelProps> = ({
  config,
  onChange,
  onSubmit,
  onCancel,
  isCreating
}) => {
  const [activeTab, setActiveTab] = useState('project')

  const updateConfig = (section: keyof ProjectConfig, field: string, value: any) => {
    onChange({
      ...config,
      [section]: {
        ...config[section],
        [field]: value
      }
    })
  }

  const updateNestedConfig = (section: keyof ProjectConfig, subsection: string, field: string, value: any) => {
    onChange({
      ...config,
      [section]: {
        ...config[section],
        [subsection]: {
          ...(config[section] as any)[subsection],
          [field]: value
        }
      }
    })
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="mb-6">
        <h2 className="text-2xl font-bold mb-2">Project Configuration</h2>
        <p className="text-muted-foreground">
          Configure your project settings and execution parameters
        </p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="llm">LLM</TabsTrigger>
          <TabsTrigger value="execution">Execution</TabsTrigger>
          <TabsTrigger value="cache">Cache</TabsTrigger>
        </TabsList>

        <TabsContent value="llm" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Project Details</CardTitle>
              <CardDescription>
                Define your project goal and basic parameters
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="goal">Project Goal *</Label>
                <Textarea
                  id="goal"
                  value={config.project.goal || ''}
                  onChange={(e) => updateConfig('project', 'goal', e.target.value)}
                  placeholder="Describe what you want to research or accomplish..."
                  className="min-h-[100px]"
                />
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="max_steps">Maximum Steps</Label>
                  <Input
                    id="max_steps"
                    type="number"
                    value={config.project.max_steps || 250}
                    onChange={(e) => updateConfig('project', 'max_steps', parseInt(e.target.value) || 250)}
                    min={10}
                    max={1000}
                  />
                  <p className="text-xs text-muted-foreground">
                    Maximum number of execution steps (10-1000)
                  </p>
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="description">Description (Optional)</Label>
                  <Input
                    id="description"
                    value={config.project.description || ''}
                    onChange={(e) => updateConfig('project', 'description', e.target.value)}
                    placeholder="Brief project description..."
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="execution" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Execution Settings</CardTitle>
              <CardDescription>
                Configure how the system executes tasks
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="max_recursion_depth">Max Recursion Depth</Label>
                  <Input
                    id="max_recursion_depth"
                    type="number"
                    min="1"
                    max="10"
                    value={config.execution?.max_recursion_depth || 3}
                    onChange={(e) => updateConfig('execution', 'max_recursion_depth', parseInt(e.target.value))}
                  />
                  <p className="text-sm text-muted-foreground">
                    Maximum depth for task decomposition (1-10)
                  </p>
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="max_concurrent_nodes">Max Concurrent Nodes</Label>
                  <Input
                    id="max_concurrent_nodes"
                    type="number"
                    min="1"
                    max="20"
                    value={config.execution?.max_concurrent_nodes || 3}
                    onChange={(e) => updateConfig('execution', 'max_concurrent_nodes', parseInt(e.target.value))}
                  />
                  <p className="text-sm text-muted-foreground">
                    Maximum number of nodes to process simultaneously
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="max_replan_attempts">Max Replan Attempts</Label>
                  <Input
                    id="max_replan_attempts"
                    type="number"
                    min="1"
                    max="10"
                    value={config.execution?.max_replan_attempts || 3}
                    onChange={(e) => updateConfig('execution', 'max_replan_attempts', parseInt(e.target.value))}
                  />
                  <p className="text-sm text-muted-foreground">
                    Maximum number of replan attempts per node
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="execution_timeout">Execution Timeout (seconds)</Label>
                  <Input
                    id="execution_timeout"
                    type="number"
                    min="30"
                    max="3600"
                    value={config.execution?.execution_timeout || 300}
                    onChange={(e) => updateConfig('execution', 'execution_timeout', parseInt(e.target.value))}
                  />
                  <p className="text-sm text-muted-foreground">
                    Timeout for individual task execution
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="cache" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Database className="h-5 w-5" />
                Cache Configuration
              </CardTitle>
              <CardDescription>
                Configure caching behavior for improved performance
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label htmlFor="cache_enabled">Enable Cache</Label>
                  <p className="text-sm text-muted-foreground">
                    Cache results to improve performance
                  </p>
                </div>
                <Switch
                  id="cache_enabled"
                  checked={config.cache.enabled || false}
                  onCheckedChange={(checked) => updateConfig('cache', 'enabled', checked)}
                />
              </div>

              {config.cache.enabled && (
                <>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="cache_type">Cache Type</Label>
                      <Select
                        value={config.cache.cache_type || 'file'}
                        onValueChange={(value) => updateConfig('cache', 'cache_type', value)}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="file">File</SelectItem>
                          <SelectItem value="memory">Memory</SelectItem>
                          <SelectItem value="redis">Redis</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    
                    <div className="space-y-2">
                      <Label htmlFor="cache_ttl">TTL (seconds)</Label>
                      <Input
                        id="cache_ttl"
                        type="number"
                        min="60"
                        max="86400"
                        value={config.cache.ttl_seconds || 3600}
                        onChange={(e) => updateConfig('cache', 'ttl_seconds', parseInt(e.target.value) || 3600)}
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="cache_max_size">Max Cache Size</Label>
                    <Input
                      id="cache_max_size"
                      type="number"
                      min="100"
                      max="10000"
                      value={config.cache.max_size || 1000}
                      onChange={(e) => updateConfig('cache', 'max_size', parseInt(e.target.value) || 1000)}
                    />
                    <p className="text-xs text-muted-foreground">
                      Maximum number of items to cache
                    </p>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Action Buttons */}
      <div className="flex justify-end gap-3 pt-6 border-t">
        <Button variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button onClick={onSubmit} disabled={!config.project.goal?.trim()}>
          {isCreating ? 'Create Project' : 'Save Configuration'}
        </Button>
      </div>
    </div>
  )
}

export default ProjectConfigPanel 