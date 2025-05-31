import React, { useState, useEffect } from 'react';
import { ChevronDown, User, Settings, Cpu, AlertCircle, CheckCircle, Layers, Zap } from 'lucide-react';

interface Profile {
  name: string;
  description: string;
  root_planner: string;
  default_planner: string;
  default_executor: string;
  aggregator: string;
  atomizer: string;
  plan_modifier: string;
  planner_mappings: Record<string, string>;
  executor_mappings: Record<string, string>;
  validation_issues?: string[];
  recommended_for?: string[];
  is_valid: boolean;
}

interface ProjectProfileSelectorProps {
  selectedProfile: string;
  onProfileChange: (profileName: string) => void;
}

const ProjectProfileSelector: React.FC<ProjectProfileSelectorProps> = ({
  selectedProfile: currentProfile,
  onProfileChange
}) => {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    const loadProfiles = async () => {
      try {
        console.log('🔍 Attempting to fetch profiles from /api/profiles');
        const response = await fetch('/api/profiles');
        console.log('📡 Response status:', response.status, response.statusText);
        
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        console.log('✅ Parsed data:', data);
        
        setProfiles(data.profiles || []);
        
        // ✅ Auto-select the current profile from backend
        if (data.current_profile && (!currentProfile || currentProfile !== data.current_profile)) {
          console.log('🎯 Auto-selecting current profile:', data.current_profile);
          onProfileChange?.(data.current_profile);
        }
      } catch (error) {
        console.error('❌ Failed to load profiles:', error);
        setError('Failed to load agent profiles');
      } finally {
        setLoading(false);
      }
    };

    loadProfiles();
  }, []); // Remove currentProfile dependency to avoid infinite loops

  const selectedProfileData = profiles.find(p => p.name === currentProfile);

  if (loading) {
    return (
      <div className="space-y-2">
        <label className="text-sm font-medium text-gray-700">Agent Profile</label>
        <div className="animate-pulse bg-gray-200 h-10 rounded-md"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-2">
        <label className="text-sm font-medium text-gray-700">Agent Profile</label>
        <div className="flex items-center space-x-2 text-red-600 text-sm">
          <AlertCircle className="h-4 w-4" />
          <span>{error}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-gray-700">Agent Profile</label>
      
      <div className="relative">
        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          className="w-full flex items-center justify-between px-3 py-2 border border-gray-300 rounded-md shadow-sm bg-white text-left focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        >
          <div className="flex items-center space-x-2">
            <User className="h-4 w-4 text-gray-500" />
            <span className="text-sm">
              {selectedProfileData?.name || 'Select Profile'}
            </span>
          </div>
          <ChevronDown className={`h-4 w-4 text-gray-500 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
        </button>

        {isOpen && (
          <div className="absolute z-10 mt-1 w-full bg-white border border-gray-300 rounded-md shadow-lg max-h-96 overflow-auto">
            {profiles.map((profile) => (
              <button
                key={profile.name}
                type="button"
                onClick={() => {
                  onProfileChange(profile.name);
                  setIsOpen(false);
                }}
                className={`w-full px-3 py-3 text-left hover:bg-gray-50 focus:outline-none focus:bg-gray-50 border-b border-gray-100 last:border-b-0 ${
                  currentProfile === profile.name ? 'bg-blue-50' : ''
                }`}
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-sm">{profile.name}</span>
                    {profile.is_valid ? (
                      <CheckCircle className="h-4 w-4 text-green-500" />
                    ) : (
                      <AlertCircle className="h-4 w-4 text-red-500" />
                    )}
                  </div>
                  
                  <p className="text-xs text-gray-600">{profile.description}</p>
                  
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="flex items-center space-x-1">
                      <Settings className="h-3 w-3 text-gray-400" />
                      <span className="text-gray-500">Root:</span>
                      <span className="font-mono text-gray-700">{profile.root_planner}</span>
                    </div>
                    <div className="flex items-center space-x-1">
                      <Cpu className="h-3 w-3 text-gray-400" />
                      <span className="text-gray-500">Executor:</span>
                      <span className="font-mono text-gray-700">{profile.default_executor}</span>
                    </div>
                  </div>

                  {!profile.is_valid && (profile.validation_issues || []).length > 0 && (
                    <div className="text-xs text-red-600">
                      <span className="font-medium">Issues:</span>
                      <ul className="list-disc list-inside ml-2">
                        {(profile.validation_issues || []).map((issue, idx) => (
                          <li key={idx}>{issue}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {selectedProfileData && (
        <div className="mt-3 p-3 bg-gray-50 rounded-md">
          <h4 className="text-sm font-medium text-gray-900 mb-3">{selectedProfileData.name}</h4>
          
          {/* Core Adapters */}
          <div className="space-y-2 text-xs text-gray-600 mb-3">
            <div className="flex justify-between">
              <span className="flex items-center space-x-1">
                <Settings className="h-3 w-3" />
                <span>Root Planner:</span>
              </span>
              <span className="font-mono text-gray-800">{selectedProfileData.root_planner}</span>
            </div>
            <div className="flex justify-between">
              <span className="flex items-center space-x-1">
                <Settings className="h-3 w-3" />
                <span>Default Planner:</span>
              </span>
              <span className="font-mono text-gray-800">{selectedProfileData.default_planner}</span>
            </div>
            <div className="flex justify-between">
              <span className="flex items-center space-x-1">
                <Cpu className="h-3 w-3" />
                <span>Default Executor:</span>
              </span>
              <span className="font-mono text-gray-800">{selectedProfileData.default_executor}</span>
            </div>
            <div className="flex justify-between">
              <span className="flex items-center space-x-1">
                <Layers className="h-3 w-3" />
                <span>Aggregator:</span>
              </span>
              <span className="font-mono text-gray-800">{selectedProfileData.aggregator}</span>
            </div>
            <div className="flex justify-between">
              <span className="flex items-center space-x-1">
                <Zap className="h-3 w-3" />
                <span>Atomizer:</span>
              </span>
              <span className="font-mono text-gray-800">{selectedProfileData.atomizer}</span>
            </div>
            <div className="flex justify-between">
              <span className="flex items-center space-x-1">
                <Settings className="h-3 w-3" />
                <span>Plan Modifier:</span>
              </span>
              <span className="font-mono text-gray-800">{selectedProfileData.plan_modifier}</span>
            </div>
          </div>

          {/* Task-Specific Planners */}
          {selectedProfileData.planner_mappings && Object.keys(selectedProfileData.planner_mappings).length > 0 && (
            <div className="mb-3">
              <h5 className="text-xs font-medium text-gray-700 mb-1">Task-Specific Planners:</h5>
              <div className="space-y-1">
                {Object.entries(selectedProfileData.planner_mappings).map(([taskType, planner]) => (
                  <div key={taskType} className="flex justify-between text-xs">
                    <span className="text-gray-500">{taskType}:</span>
                    <span className="font-mono text-gray-700">{planner}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Task-Specific Executors */}
          {selectedProfileData.executor_mappings && Object.keys(selectedProfileData.executor_mappings).length > 0 && (
            <div className="mb-3">
              <h5 className="text-xs font-medium text-gray-700 mb-1">Task-Specific Executors:</h5>
              <div className="space-y-1">
                {Object.entries(selectedProfileData.executor_mappings).map(([taskType, executor]) => (
                  <div key={taskType} className="flex justify-between text-xs">
                    <span className="text-gray-500">{taskType}:</span>
                    <span className="font-mono text-gray-700">{executor}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          
          {!selectedProfileData.is_valid && (selectedProfileData.validation_issues || []).length > 0 && (
            <div className="mt-2 p-2 bg-red-50 rounded border border-red-200">
              <div className="flex items-center space-x-1 text-red-700 text-xs font-medium mb-1">
                <AlertCircle className="h-3 w-3" />
                <span>Validation Issues:</span>
              </div>
              <ul className="text-xs text-red-600 space-y-1">
                {(selectedProfileData.validation_issues || []).map((issue, idx) => (
                  <li key={idx}>• {issue}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ProjectProfileSelector;