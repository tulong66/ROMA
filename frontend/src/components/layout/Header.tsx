import React from 'react'
import { Button } from '@/components/ui/button'
import { 
  Brain, 
  Settings, 
  Download,
  Eye,
  EyeOff
} from 'lucide-react'
import { useTaskGraphStore } from '@/stores/taskGraphStore'
import ThemeToggle from '@/components/theme/ThemeToggle'

const Header: React.FC = () => {
  const { 
    showContextFlow, 
    toggleContextFlow,
    nodes 
  } = useTaskGraphStore()

  const hasNodes = Object.keys(nodes).length > 0

  const handleDownloadReport = async () => {
    try {
      const response = await fetch('http://localhost:5000/api/download-report')
      if (response.ok) {
        const blob = await response.blob()
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = 'project-report.pdf'
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        window.URL.revokeObjectURL(url)
      }
    } catch (error) {
      console.error('Failed to download report:', error)
    }
  }

  return (
    <header className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="flex items-center justify-between px-6 py-3">
        {/* Logo and Title */}
        <div className="flex items-center space-x-3">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary">
            <Brain className="w-5 h-5 text-primary-foreground" />
          </div>
          <div>
            <h1 className="text-lg font-semibold">Sentient Research Agent</h1>
            <p className="text-xs text-muted-foreground">
              Hierarchical Task Decomposition System
            </p>
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center space-x-2">
          {hasNodes && (
            <>
              {/* Context Flow Toggle */}
              <Button
                variant="outline"
                size="sm"
                onClick={toggleContextFlow}
                className="text-xs"
              >
                {showContextFlow ? (
                  <>
                    <EyeOff className="w-4 h-4 mr-1" />
                    Hide Context Flow
                  </>
                ) : (
                  <>
                    <Eye className="w-4 h-4 mr-1" />
                    Show Context Flow
                  </>
                )}
              </Button>

              {/* Download Report */}
              <Button
                variant="outline"
                size="sm"
                onClick={handleDownloadReport}
                className="text-xs"
              >
                <Download className="w-4 h-4 mr-1" />
                Download Report
              </Button>
            </>
          )}

          {/* Settings */}
          <Button variant="ghost" size="icon">
            <Settings className="w-4 h-4" />
          </Button>

          {/* Theme Toggle */}
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}

export default Header 