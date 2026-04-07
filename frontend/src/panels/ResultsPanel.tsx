import { TurnRecord, HeatMapData } from '../types'
import './ResultsPanel.css'

interface Props {
  recentTurns: TurnRecord[]
  heatmap: HeatMapData
}

function intensityColor(intensity: number): string {
  // Green gradient: low → dim green, high → bright green
  const r = Math.round(0 + intensity * 0)
  const g = Math.round(80 + intensity * 175)
  const b = Math.round(40 + intensity * 48)
  return `rgb(${r}, ${g}, ${b})`
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch {
    return iso
  }
}

export default function ResultsPanel({ recentTurns, heatmap }: Props) {
  return (
    <div className="panel results-panel">
      <div className="panel-header">
        <span className="icon">📊</span>
        <span>Results Timeline</span>
      </div>
      <div className="panel-body results-body">
        {/* Turn timeline */}
        <div className="results-section">
          <div className="results-section-label">Turn History</div>
          {recentTurns.length === 0 ? (
            <div className="empty-state">No turns yet — send a message to get started.</div>
          ) : (
            <div className="turn-list">
              {[...recentTurns].reverse().map(turn => (
                <div key={turn.turn_index} className="turn-entry animate-slide-in">
                  <div className="turn-header">
                    <span className="turn-number">#{turn.turn_index}</span>
                    <span className="turn-time">{formatTime(turn.timestamp)}</span>
                    <span className="turn-agent">A{turn.agent_slot + 1}</span>
                  </div>
                  <div className="turn-user-msg">{turn.user_message.slice(0, 120)}</div>
                  {turn.synopsis && (
                    <div className="turn-synopsis">{turn.synopsis.slice(0, 150)}</div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Heatmap */}
        {heatmap.entries.length > 0 && (
          <div className="results-section">
            <div className="results-section-label">Codebase Heatmap</div>
            <div className="heatmap-list">
              {heatmap.entries.slice(0, 12).map(entry => (
                <div key={entry.path} className="heatmap-row">
                  <div className="heatmap-bar-track">
                    <div
                      className="heatmap-bar-fill"
                      style={{
                        width: `${Math.max(4, entry.intensity * 100)}%`,
                        backgroundColor: intensityColor(entry.intensity),
                      }}
                    />
                  </div>
                  <span className="heatmap-path" title={entry.path}>
                    {entry.path.split('/').pop() || entry.path}
                  </span>
                  <span className="heatmap-count">+{entry.lines_changed}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
