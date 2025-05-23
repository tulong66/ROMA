import React from 'react'

const NodeDetailsPanel: React.FC = () => {
  return (
    <div className="w-96 border-l bg-background p-6">
      <h3 className="text-lg font-semibold mb-4">Node Details</h3>
      <p className="text-muted-foreground">
        Select a node to view its details here
      </p>
    </div>
  )
}

export default NodeDetailsPanel 