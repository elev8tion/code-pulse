import { AgentInfo, HandoffRecord } from '../types'
import './OrchestrationPanel.css'

interface Props {
  agents: AgentInfo[]
  handoffs: HandoffRecord[]
  currentSlot: number
}

const STATE_LABELS: Record<string, string> = {
  sleeping: 'Idle',
  processing: 'Running',
  discussing: 'Discuss',
}

const STATE_CLASSES: Record<string, string> = {
  sleeping: 'agent--idle',
  processing: 'agent--processing',
  discussing: 'agent--discussing',
}

export default function OrchestrationPanel({ agents, handoffs, currentSlot }: Props) {
  return (
    <div className="panel orchestration-panel">
      <div className="panel-header">
        <span className="icon">🎬</span>
        <span>Orchestration</span>
        <span className="agent-slot-label" style={{ marginLeft: 'auto' }}>
          Agent {currentSlot + 1} active
        </span>
      </div>
      <div className="panel-body orchestration-body">
        {/* Agent slots */}
        <div className="agent-row">
          {agents.length === 0
            ? [0, 1, 2].map(i => (
                <div key={i} className={`agent-slot ${i === currentSlot ? 'agent--current agent--idle' : 'agent--idle'}`}>
                  <div className="agent-slot-label">Agent {i + 1}</div>
                  <div className="agent-state">Idle</div>
                </div>
              ))
            : agents.map(agent => (
                <div
                  key={agent.slot_id}
                  className={`agent-slot ${STATE_CLASSES[agent.state] || 'agent--idle'} ${agent.is_current ? 'agent--current' : ''}`}
                >
                  <div className="agent-slot-number">Agent {agent.slot_id + 1}</div>
                  <div className="agent-state">{STATE_LABELS[agent.state] || agent.state}</div>
                  {agent.synopsis && (
                    <div className="agent-synopsis" title={agent.synopsis}>
                      {agent.synopsis.slice(0, 60)}…
                    </div>
                  )}
                </div>
              ))
          }
        </div>

        {/* Handoff timeline */}
        {handoffs.length > 0 && (
          <div className="handoff-timeline">
            <div className="timeline-label">Handoff History</div>
            <div className="handoff-list">
              {handoffs.slice(-6).map((h, i) => (
                <div key={i} className="handoff-entry animate-slide-in">
                  <span className="handoff-arrow">
                    A{h.from_slot + 1} → A{h.to_slot + 1}
                  </span>
                  <span className="handoff-synopsis">
                    {h.synopsis.slice(0, 80)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
