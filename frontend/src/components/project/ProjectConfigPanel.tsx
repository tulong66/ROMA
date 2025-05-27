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
import { Info, Settings, Zap, Brain, Database, MessageSquare } from 'lucide-react'
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
    enable_hitl: boolean
    hitl_root_plan_only: boolean
    hitl_timeout_seconds: number
    hitl_after_plan_generation: boolean
    hitl_after_modified_plan: boolean
    hitl_after_atomizer: boolean
    hitl_before_execute: boolean
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
          Configure your project settings, AI model, and execution parameters
        </p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="project" className="flex items-center gap-2">
            <Settings className="h-4 w-4" />
            Project
          </TabsTrigger>
          <TabsTrigger value="llm" className="flex items-center gap-2">
            <Brain className="h-4 w-4" />
            AI Model
          </TabsTrigger>
          <TabsTrigger value="execution" className="flex items-center gap-2">
            <Zap className="h-4 w-4" />
            Execution
          </TabsTrigger>
          <TabsTrigger value="advanced" className="flex items-center gap-2">
            <Database className="h-4 w-4" />
            Advanced
          </TabsTrigger>
        </TabsList>

        {/* Project Settings Tab */}
        <TabsContent value="project" className="space-y-6">
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
                  value={config.project.goal}
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
                    value={config.project.max_steps}
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

        {/* LLM Configuration Tab */}
        <TabsContent value="llm" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>AI Model Configuration</CardTitle>
              <CardDescription>
                Choose your AI provider and model settings
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="provider">Provider</Label>
                  <Select
                    value={config.llm.provider}
                    onValueChange={(value) => updateConfig('llm', 'provider', value)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="openai">OpenAI</SelectItem>
                      <SelectItem value="anthropic">Anthropic</SelectItem>
                      <SelectItem value="openrouter">OpenRouter</SelectItem>
                      <SelectItem value="azure">Azure OpenAI</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="model">Model</Label>
                  <Select
                    value={config.llm.model}
                    onValueChange={(value) => updateConfig('llm', 'model', value)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {config.llm.provider === 'openai' && (
                        <>
                          <SelectItem value="gpt-4">GPT-4</SelectItem>
                          <SelectItem value="gpt-4-turbo">GPT-4 Turbo</SelectItem>
                          <SelectItem value="gpt-3.5-turbo">GPT-3.5 Turbo</SelectItem>
                        </>
                      )}
                      {config.llm.provider === 'anthropic' && (
                        <>
                          <SelectItem value="claude-3-opus-20240229">Claude 3 Opus</SelectItem>
                          <SelectItem value="claude-3-sonnet-20240229">Claude 3 Sonnet</SelectItem>
                          <SelectItem value="claude-3-haiku-20240307">Claude 3 Haiku</SelectItem>
                        </>
                      )}
                      {config.llm.provider === 'openrouter' && (
                        <>
                          <SelectItem value="openai/gpt-4">OpenAI GPT-4</SelectItem>
                          <SelectItem value="anthropic/claude-3-opus">Claude 3 Opus</SelectItem>
                          <SelectItem value="anthropic/claude-3-sonnet">Claude 3 Sonnet</SelectItem>
                          <SelectItem value="meta-llama/llama-2-70b-chat">Llama 2 70B</SelectItem>
                        </>
                      )}
                      {config.llm.provider === 'azure' && (
                        <>
                          <SelectItem value="gpt-4">Azure GPT-4</SelectItem>
                          <SelectItem value="gpt-35-turbo">Azure GPT-3.5 Turbo</SelectItem>
                        </>
                      )}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              
              <div className="grid grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="temperature">
                    Temperature
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Info className="h-3 w-3 ml-1 inline" />
                        </TooltipTrigger>
                        <TooltipContent>
                          <p>Controls randomness: 0 = deterministic, 1 = creative</p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </Label>
                  <Input
                    id="temperature"
                    type="number"
                    step="0.1"
                    min="0"
                    max="2"
                    value={config.llm.temperature}
                    onChange={(e) => updateConfig('llm', 'temperature', parseFloat(e.target.value) || 0.7)}
                  />
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="timeout">Timeout (seconds)</Label>
                  <Input
                    id="timeout"
                    type="number"
                    value={config.llm.timeout}
                    onChange={(e) => updateConfig('llm', 'timeout', parseInt(e.target.value) || 30)}
                    min={10}
                    max={300}
                  />
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="max_retries">Max Retries</Label>
                  <Input
                    id="max_retries"
                    type="number"
                    value={config.llm.max_retries}
                    onChange={(e) => updateConfig('llm', 'max_retries', parseInt(e.target.value) || 3)}
                    min={0}
                    max={10}
                  />
                </div>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="max_tokens">Max Tokens (Optional)</Label>
                <Input
                  id="max_tokens"
                  type="number"
                  value={config.llm.max_tokens || ''}
                  onChange={(e) => updateConfig('llm', 'max_tokens', e.target.value ? parseInt(e.target.value) : undefined)}
                  placeholder="Leave empty for model default"
                />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Execution Configuration Tab */}
        <TabsContent value="execution" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Execution Settings</CardTitle>
              <CardDescription>
                Configure how your project will be executed
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="max_concurrent">Max Concurrent Nodes</Label>
                  <Input
                    id="max_concurrent"
                    type="number"
                    value={config.execution.max_concurrent_nodes}
                    onChange={(e) => updateConfig('execution', 'max_concurrent_nodes', parseInt(e.target.value) || 3)}
                    min={1}
                    max={10}
                  />
                  <p className="text-xs text-muted-foreground">
                    Number of tasks that can run simultaneously
                  </p>
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="max_execution_steps">Max Execution Steps</Label>
                  <Input
                    id="max_execution_steps"
                    type="number"
                    value={config.execution.max_execution_steps}
                    onChange={(e) => updateConfig('execution', 'max_execution_steps', parseInt(e.target.value) || 250)}
                    min={10}
                    max={1000}
                  />
                </div>
              </div>
              
              <Separator />
              
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="space-y-1">
                    <Label className="text-base font-medium">Human-in-the-Loop (HITL)</Label>
                    <p className="text-sm text-muted-foreground">
                      Enable human review and approval at key decision points
                    </p>
                  </div>
                  <Switch
                    checked={config.execution.enable_hitl}
                    onCheckedChange={(checked) => updateConfig('execution', 'enable_hitl', checked)}
                  />
                </div>
                
                {config.execution.enable_hitl && (
                  <div className="ml-4 space-y-4 border-l-2 border-muted pl-4">
                    <div className="flex items-center justify-between">
                      <div className="space-y-1">
                        <Label>Root Plan Only</Label>
                        <p className="text-xs text-muted-foreground">
                          Only review the initial high-level plan, not sub-plans
                        </p>
                      </div>
                      <Switch
                        checked={config.execution.hitl_root_plan_only}
                        onCheckedChange={(checked) => updateConfig('execution', 'hitl_root_plan_only', checked)}
                      />
                    </div>
                    
                    {!config.execution.hitl_root_plan_only && (
                      <div className="space-y-3">
                        <Label className="text-sm font-medium">Review Checkpoints</Label>
                        
                        <div className="space-y-2">
                          <div className="flex items-center justify-between">
                            <Label className="text-sm">After Plan Generation</Label>
                            <Switch
                              checked={config.execution.hitl_after_plan_generation}
                              onCheckedChange={(checked) => updateConfig('execution', 'hitl_after_plan_generation', checked)}
                            />
                          </div>
                          
                          <div className="flex items-center justify-between">
                            <Label className="text-sm">After Plan Modification</Label>
                            <Switch
                              checked={config.execution.hitl_after_modified_plan}
                              onCheckedChange={(checked) => updateConfig('execution', 'hitl_after_modified_plan', checked)}
                            />
                          </div>
                          
                          <div className="flex items-center justify-between">
                            <Label className="text-sm">After Atomizer</Label>
                            <Switch
                              checked={config.execution.hitl_after_atomizer}
                              onCheckedChange={(checked) => updateConfig('execution', 'hitl_after_atomizer', checked)}
                            />
                          </div>
                          
                          <div className="flex items-center justify-between">
                            <Label className="text-sm">Before Execution</Label>
                            <Switch
                              checked={config.execution.hitl_before_execute}
                              onCheckedChange={(checked) => updateConfig('execution', 'hitl_before_execute', checked)}
                            />
                          </div>
                        </div>
                      </div>
                    )}
                    
                    <div className="space-y-2">
                      <Label htmlFor="hitl_timeout">HITL Timeout (seconds)</Label>
                      <Input
                        id="hitl_timeout"
                        type="number"
                        value={config.execution.hitl_timeout_seconds}
                        onChange={(e) => updateConfig('execution', 'hitl_timeout_seconds', parseInt(e.target.value) || 300)}
                        min={30}
                        max={3600}
                      />
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Advanced Settings Tab */}
        <TabsContent value="advanced" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Cache Configuration</CardTitle>
              <CardDescription>
                Configure caching to improve performance and reduce API costs
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <Label className="text-base font-medium">Enable Caching</Label>
                  <p className="text-sm text-muted-foreground">
                    Cache AI responses to avoid redundant API calls
                  </p>
                </div>
                <Switch
                  checked={config.cache.enabled}
                  onCheckedChange={(checked) => updateConfig('cache', 'enabled', checked)}
                />
              </div>
              
              {config.cache.enabled && (
                <div className="space-y-4">
                  <div className="grid grid-cols-3 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="cache_type">Cache Type</Label>
                      <Select
                        value={config.cache.cache_type}
                        onValueChange={(value) => updateConfig('cache', 'cache_type', value)}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="memory">Memory</SelectItem>
                          <SelectItem value="file">File</SelectItem>
                          <SelectItem value="redis">Redis</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    
                    <div className="space-y-2">
                      <Label htmlFor="ttl_seconds">TTL (seconds)</Label>
                      <Input
                        id="ttl_seconds"
                        type="number"
                        value={config.cache.ttl_seconds}
                        onChange={(e) => updateConfig('cache', 'ttl_seconds', parseInt(e.target.value) || 3600)}
                        min={60}
                        max={86400}
                      />
                    </div>
                    
                    <div className="space-y-2">
                      <Label htmlFor="max_size">Max Size</Label>
                      <Input
                        id="max_size"
                        type="number"
                        value={config.cache.max_size}
                        onChange={(e) => updateConfig('cache', 'max_size', parseInt(e.target.value) || 1000)}
                        min={10}
                        max={10000}
                      />
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader>
              <CardTitle>Configuration Summary</CardTitle>
              <CardDescription>
                Review your configuration before creating the project
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">AI Model:</span>
                  <Badge variant="secondary">
                    {config.llm.provider}/{config.llm.model}
                  </Badge>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">Temperature:</span>
                  <Badge variant="outline">{config.llm.temperature}</Badge>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">Max Steps:</span>
                  <Badge variant="outline">{config.execution.max_execution_steps}</Badge>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">HITL:</span>
                  <Badge variant={config.execution.enable_hitl ? "default" : "secondary"}>
                    {config.execution.enable_hitl ? 
                      (config.execution.hitl_root_plan_only ? "Root Plan Only" : "Full Review") : 
                      "Disabled"
                    }
                  </Badge>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">Cache:</span>
                  <Badge variant={config.cache.enabled ? "default" : "secondary"}>
                    {config.cache.enabled ? config.cache.cache_type : "Disabled"}
                  </Badge>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Action Buttons */}
      <div className="flex justify-between pt-6 border-t">
        <Button variant="outline" onClick={onCancel} disabled={isCreating}>
          Cancel
        </Button>
        
        <div className="flex gap-2">
          <Button
            variant="secondary"
            onClick={() => {
              // Reset to defaults
              const defaultConfig: ProjectConfig = {
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
                  goal: config.project.goal,
                  max_steps: 250
                }
              }
              onChange(defaultConfig)
            }}
            disabled={isCreating}
          >
            Reset to Defaults
          </Button>
          
          <Button 
            onClick={onSubmit} 
            disabled={!config.project.goal.trim() || isCreating}
            className="min-w-[120px]"
          >
            {isCreating ? (
              <>
                <MessageSquare className="w-4 h-4 mr-2 animate-pulse" />
                Creating...
              </>
            ) : (
              'Create Project'
            )}
          </Button>
        </div>
      </div>
    </div>
  )
}

export default ProjectConfigPanel 