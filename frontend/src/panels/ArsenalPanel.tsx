import './ArsenalPanel.css'

const TOOLS = [
  { name: 'Bash',      icon: '⚡', desc: 'Run commands',   keys: ['bash'] },
  { name: 'Read',      icon: '📖', desc: 'Read files',     keys: ['read_file', 'read'] },
  { name: 'Write',     icon: '✏️',  desc: 'Create files',  keys: ['write_file', 'write'] },
  { name: 'Edit',      icon: '🔄', desc: 'Modify files',   keys: ['edit_file', 'edit', 'str_replace_editor'] },
  { name: 'Glob',      icon: '🔍', desc: 'Find files',     keys: ['glob'] },
  { name: 'Grep',      icon: '🔎', desc: 'Search code',    keys: ['grep'] },
  { name: 'WebFetch',  icon: '🌐', desc: 'Fetch URL',      keys: ['web_fetch', 'webfetch'] },
  { name: 'WebSearch', icon: '🔭', desc: 'Search web',     keys: ['web_search', 'websearch'] },
  { name: 'Agent',     icon: '🤖', desc: 'Spawn agent',    keys: ['agent'] },
  { name: 'Task',      icon: '📋', desc: 'Manage tasks',   keys: ['task'] },
  { name: 'TodoWrite', icon: '✅', desc: 'Write todos',    keys: ['todowrite', 'todo_write'] },
]

interface Props {
  activeTools: Record<string, number>
  isStreaming: boolean
}

function isToolActive(tool: typeof TOOLS[0], activeTools: Record<string, number>): boolean {
  return tool.keys.some(k => k in activeTools)
}

export default function ArsenalPanel({ activeTools, isStreaming }: Props) {
  const anyActive = Object.keys(activeTools).length > 0

  return (
    <div className={`panel arsenal-panel ${anyActive ? 'glow-green' : ''}`}>
      <div className="panel-header">
        <span className="icon">🎛️</span>
        <span>Arsenal</span>
        {isStreaming && <span className="badge badge-streaming" style={{ marginLeft: 'auto' }}>ACTIVE</span>}
      </div>
      <div className="panel-body arsenal-grid">
        {TOOLS.map(tool => {
          const active = isToolActive(tool, activeTools)
          return (
            <div
              key={tool.name}
              className={`tool-card ${active ? 'tool-card--active' : ''}`}
              title={tool.desc}
            >
              <span className="tool-icon">{tool.icon}</span>
              <span className="tool-name">{tool.name}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
