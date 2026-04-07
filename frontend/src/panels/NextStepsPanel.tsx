import './NextStepsPanel.css'

interface Props {
  synopsis: string
  turnCount: number
  sessionDate: string
  projectName: string
  isStreaming: boolean
  onExport: () => Promise<void>
}

function extractNextSteps(synopsis: string): string[] {
  if (!synopsis) return []
  // Try to extract bullet-point lines first (•, -, *)
  const lines = synopsis.split('\n').filter(l => l.trim().startsWith('•') || l.trim().startsWith('-') || l.trim().startsWith('*'))
  if (lines.length > 0) {
    return lines.map(l => l.replace(/^[•\-*]\s*/, '').trim()).slice(0, 5)
  }
  // Fallback: split on sentence boundaries and take first 3 non-trivial sentences
  return synopsis.split(/[.!?]/).filter(s => s.trim().length > 10).slice(0, 3).map(s => s.trim())
}

export default function NextStepsPanel({
  synopsis,
  turnCount,
  sessionDate,
  projectName,
  isStreaming,
  onExport,
}: Props) {
  const steps = extractNextSteps(synopsis)

  return (
    <div className="panel nextsteps-panel">
      <div className="panel-header">
        <span className="icon">➡️</span>
        <span>Next Steps</span>
      </div>
      <div className="panel-body nextsteps-body">
        {/* Status section */}
        <div className="nextsteps-section">
          <div className="nextsteps-section-label">Session</div>
          <div className="status-grid">
            <div className="status-item">
              <span className="status-label">Project</span>
              <span className="status-value">{projectName}</span>
            </div>
            <div className="status-item">
              <span className="status-label">Date</span>
              <span className="status-value">{sessionDate}</span>
            </div>
            <div className="status-item">
              <span className="status-label">Turns</span>
              <span className="status-value">{turnCount}</span>
            </div>
            <div className="status-item">
              <span className="status-label">Status</span>
              <span className={`status-value ${isStreaming ? 'status-streaming' : 'status-ready'}`}>
                {isStreaming ? '⟳ Working' : '● Ready'}
              </span>
            </div>
          </div>
        </div>

        {/* Next steps derived from synopsis */}
        <div className="nextsteps-section nextsteps-main">
          <div className="nextsteps-section-label">Recommendations</div>
          {steps.length === 0 ? (
            <div className="nextsteps-empty">
              {turnCount === 0
                ? 'Send your first prompt to see recommendations here.'
                : 'Waiting for synopsis from next completed turn…'
              }
            </div>
          ) : (
            <ul className="steps-list">
              {steps.map((step, i) => (
                <li key={i} className={`step-item ${i === 0 ? 'step-item--primary' : ''} animate-slide-in`}>
                  <span className="step-bullet">{i === 0 ? '▶' : '○'}</span>
                  <span className="step-text">{step}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Actions */}
        <div className="nextsteps-actions">
          <button
            className="btn btn-secondary"
            style={{ width: '100%', justifyContent: 'center', fontSize: '11px' }}
            onClick={onExport}
          >
            📄 Export Session
          </button>
        </div>
      </div>
    </div>
  )
}
