import { useState, useEffect } from 'react'
import { ProcessInfo, ActionDefinition } from '../types'
import './ActionsPanel.css'

interface Props {
  onFireAction: (id: string, subPrompt?: string) => Promise<void>
  onToggleProcess: (name: string) => Promise<void>
  processes: ProcessInfo[]
  isStreaming: boolean
}

const COLOR_MAP: Record<string, string> = {
  red: '#ff4455',
  yellow: '#ffaa00',
  cyan: '#00ccff',
  blue: '#4488ff',
  magenta: '#cc44ff',
  green: '#00cc44',
  white: '#cccccc',
  dim: '#666666',
}

export default function ActionsPanel({ onFireAction, onToggleProcess, processes, isStreaming }: Props) {
  const [actions, setActions] = useState<ActionDefinition[]>([])
  const [subPrompt, setSubPrompt] = useState<{ id: string; label: string } | null>(null)
  const [subPromptText, setSubPromptText] = useState('')
  const [fired, setFired] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/actions')
      .then(r => r.json())
      .then(setActions)
      .catch(() => {})
  }, [])

  const handleFire = async (action: ActionDefinition) => {
    if (isStreaming) return
    if (action.needs_sub_prompt) {
      setSubPrompt({ id: action.id, label: action.sub_prompt_label || 'Enter details:' })
      return
    }
    setFired(action.id)
    setTimeout(() => setFired(null), 800)
    await onFireAction(action.id)
  }

  const handleSubPromptSubmit = async () => {
    if (!subPrompt) return
    const text = subPromptText.trim()
    setSubPrompt(null)
    setSubPromptText('')
    if (text) {
      await onFireAction(subPrompt.id, text)
    }
  }

  return (
    <div className="panel actions-panel">
      <div className="panel-header">
        <span className="icon">⚡</span>
        <span>Actions</span>
        {isStreaming && <span className="badge badge-streaming" style={{ marginLeft: 'auto' }}>RUNNING</span>}
      </div>
      <div className="panel-body actions-body">
        {/* Sub-prompt input */}
        {subPrompt && (
          <div className="sub-prompt-overlay">
            <div className="sub-prompt-label">{subPrompt.label}</div>
            <input
              type="text"
              className="sub-prompt-input"
              value={subPromptText}
              autoFocus
              onChange={e => setSubPromptText(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter') handleSubPromptSubmit()
                if (e.key === 'Escape') { setSubPrompt(null); setSubPromptText('') }
              }}
              placeholder="Type and press Enter…"
            />
          </div>
        )}

        {/* Action cards */}
        <div className="action-grid">
          {actions.map(action => {
            const color = COLOR_MAP[action.color] || '#cccccc'
            const isFired = fired === action.id
            return (
              <button
                key={action.id}
                className={`action-card ${isFired ? 'action-card--fired' : ''} ${isStreaming ? 'action-card--disabled' : ''}`}
                style={{ '--action-color': color } as React.CSSProperties}
                onClick={() => handleFire(action)}
                disabled={isStreaming}
                title={action.prompt || action.label}
              >
                <span className="action-icon">{action.icon}</span>
                <span className="action-label">{action.label}</span>
              </button>
            )
          })}
        </div>

        {/* Process controls */}
        {processes.length > 0 && (
          <div className="process-section">
            <div className="process-section-label">Processes</div>
            {processes.map(proc => (
              <div key={proc.name} className="process-row">
                <span className={`badge badge-${proc.status}`}>
                  {proc.status === 'running' ? '▶' : proc.status === 'error' ? '✖' : '■'}
                </span>
                <span className="process-name" title={proc.command}>{proc.name}</span>
                <button
                  className={`btn ${proc.status === 'running' ? 'btn-danger' : 'btn-primary'}`}
                  style={{ padding: '2px 8px', fontSize: '10px' }}
                  onClick={() => onToggleProcess(proc.name)}
                >
                  {proc.status === 'running' ? 'Stop' : 'Run'}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
