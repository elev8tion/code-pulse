import { useState, useCallback, useRef, useEffect } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import {
  AppSnapshot, WSMessage, HeatMapData, AgentInfo,
  ProcessInfo, TurnRecord, HandoffRecord, ActionDefinition
} from './types'
import ArsenalPanel from './panels/ArsenalPanel'
import OrchestrationPanel from './panels/OrchestrationPanel'
import ActionsPanel from './panels/ActionsPanel'
import ResultsPanel from './panels/ResultsPanel'
import ChatPanel from './panels/ChatPanel'
import NextStepsPanel from './panels/NextStepsPanel'
import Heartbeat from './components/Heartbeat'
import './styles/app.css'

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  streaming?: boolean
  turn_index?: number
}

export default function App() {
  // Connection status
  const [connected, setConnected] = useState(false)

  // Snapshot data from server
  const [projectName, setProjectName] = useState('Code-Pulse')
  const [projectPath, setProjectPath] = useState('')
  const [sessionDate, setSessionDate] = useState('')
  const [turnCount, setTurnCount] = useState(0)
  const [isStreaming, setIsStreaming] = useState(false)

  // Panel data
  const [activeTools, setActiveTools] = useState<Record<string, number>>({})
  const [agents, setAgents] = useState<AgentInfo[]>([])
  const [currentAgentSlot, setCurrentAgentSlot] = useState(0)
  const [heatmap, setHeatmap] = useState<HeatMapData>({ entries: [], max_touch_count: 0, max_lines_changed: 0 })
  const [processes, setProcesses] = useState<ProcessInfo[]>([])
  const [recentTurns, setRecentTurns] = useState<TurnRecord[]>([])
  const [handoffs, setHandoffs] = useState<HandoffRecord[]>([])
  const [synopsis, setSynopsis] = useState('')
  const [discussionActive, setDiscussionActive] = useState(false)

  // Chat state
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const streamingRef = useRef('')
  const currentUserMsgRef = useRef('')  // tracks the user's message for the current turn

  // Tool clear timer
  const toolClearRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handleMessage = useCallback((msg: WSMessage) => {
    switch (msg.type) {
      case 'snapshot': {
        const d = msg.data as AppSnapshot
        setProjectName(d.project_name)
        setProjectPath(d.project_path)
        setSessionDate(d.session_date)
        setTurnCount(d.turn_count)
        setIsStreaming(d.is_streaming)
        setAgents(d.agents)
        setCurrentAgentSlot(d.current_agent_slot)
        setHeatmap(d.heatmap)
        setProcesses(d.processes)
        setRecentTurns(d.recent_turns)
        setHandoffs(d.handoffs)
        // Rebuild chat from recent turns
        if (d.recent_turns.length > 0) {
          const msgs: ChatMessage[] = []
          for (const t of d.recent_turns) {
            msgs.push({ role: 'user', content: t.user_message, turn_index: t.turn_index })
            msgs.push({ role: 'assistant', content: t.assistant_message, turn_index: t.turn_index })
          }
          setMessages(msgs)
          const lastSynopsis = d.recent_turns[d.recent_turns.length - 1]?.synopsis
          if (lastSynopsis) setSynopsis(lastSynopsis)
        }
        break
      }

      case 'stream_start': {
        setIsStreaming(true)
        streamingRef.current = ''
        currentUserMsgRef.current = msg.user_message
        setMessages(prev => [
          ...prev,
          { role: 'user', content: msg.user_message },
          { role: 'assistant', content: '', streaming: true },
        ])
        // Clear tools
        setActiveTools({})
        break
      }

      case 'stream_chunk': {
        streamingRef.current += msg.text
        setMessages(prev => {
          const updated = [...prev]
          const last = updated[updated.length - 1]
          if (last?.streaming) {
            updated[updated.length - 1] = { ...last, content: streamingRef.current }
          }
          return updated
        })
        break
      }

      case 'stream_end': {
        setIsStreaming(false)
        setTurnCount(msg.turn_index)
        setSynopsis(msg.synopsis)
        setCurrentAgentSlot(msg.next_agent_slot)
        setHeatmap(msg.heatmap)
        // Update agents to reflect rotation
        setAgents(prev => prev.map(a => ({
          ...a,
          is_current: a.slot_id === msg.next_agent_slot,
          synopsis: a.slot_id === msg.agent_slot ? msg.synopsis : a.synopsis,
        })))
        // Finalize streaming message
        setMessages(prev => {
          const updated = [...prev]
          const last = updated[updated.length - 1]
          if (last?.streaming) {
            updated[updated.length - 1] = { ...last, streaming: false, turn_index: msg.turn_index }
          }
          return updated
        })
        // Update recent turns
        setRecentTurns(prev => {
          return [...prev, {
            turn_index: msg.turn_index,
            timestamp: new Date().toISOString(),
            user_message: currentUserMsgRef.current.slice(0, 200),
            assistant_message: streamingRef.current.slice(0, 500),
            synopsis: msg.synopsis,
            agent_slot: msg.agent_slot,
            diff_path: null,
          }].slice(-10)
        })
        break
      }

      case 'tool_call': {
        setActiveTools(prev => ({ ...prev, [msg.tool]: msg.count }))
        // Auto-clear tool highlights after 2s
        if (toolClearRef.current) clearTimeout(toolClearRef.current)
        toolClearRef.current = setTimeout(() => {
          if (!isStreaming) setActiveTools({})
        }, 2000)
        break
      }

      case 'tools_cleared': {
        setActiveTools({})
        break
      }

      case 'process_status': {
        setProcesses(prev => prev.map(p =>
          p.name === msg.name ? { ...p, status: msg.status } : p
        ))
        break
      }

      case 'process_output': {
        setProcesses(prev => prev.map(p =>
          p.name === msg.name
            ? { ...p, recent_output: [...p.recent_output.slice(-19), msg.line] }
            : p
        ))
        break
      }

      case 'discuss_opened': {
        setDiscussionActive(true)
        setMessages(prev => [...prev, {
          role: 'system',
          content: `💬 Discussion mode opened. Context: ${msg.synopsis_preview}`,
        }])
        break
      }

      case 'discuss_closed': {
        setDiscussionActive(false)
        setMessages(prev => [...prev, {
          role: 'system',
          content: '💬 Discussion mode closed.',
        }])
        break
      }

      case 'discuss_start': {
        setIsStreaming(true)
        streamingRef.current = ''
        setMessages(prev => [...prev,
          { role: 'user', content: msg.user_message },
          { role: 'assistant', content: '', streaming: true },
        ])
        break
      }

      case 'discuss_chunk': {
        streamingRef.current += msg.text
        setMessages(prev => {
          const updated = [...prev]
          const last = updated[updated.length - 1]
          if (last?.streaming) {
            updated[updated.length - 1] = { ...last, content: streamingRef.current }
          }
          return updated
        })
        break
      }

      case 'discuss_end': {
        setIsStreaming(false)
        setMessages(prev => {
          const updated = [...prev]
          const last = updated[updated.length - 1]
          if (last?.streaming) {
            updated[updated.length - 1] = { ...last, streaming: false }
          }
          return updated
        })
        break
      }

      case 'error': {
        setIsStreaming(false)
        setMessages(prev => [...prev, {
          role: 'system',
          content: `⚠️ Error: ${msg.message}`,
        }])
        break
      }
    }
  }, [isStreaming])

  useWebSocket(handleMessage, setConnected)

  const sendPrompt = useCallback(async (message: string) => {
    try {
      await fetch('/api/prompt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
      })
    } catch (err) {
      setMessages(prev => [...prev, { role: 'system', content: `⚠️ Network error: ${err}` }])
    }
  }, [])

  const sendDiscussMessage = useCallback(async (message: string) => {
    try {
      await fetch('/api/discuss/message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
      })
    } catch (err) {
      setMessages(prev => [...prev, { role: 'system', content: `⚠️ Network error: ${err}` }])
    }
  }, [])

  const toggleDiscussion = useCallback(async () => {
    await fetch('/api/discuss/toggle', { method: 'POST' })
  }, [])

  const fireAction = useCallback(async (id: string, subPrompt?: string) => {
    await fetch(`/api/action/${id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sub_prompt: subPrompt }),
    })
  }, [])

  const toggleProcess = useCallback(async (name: string) => {
    await fetch(`/api/process/${name}/toggle`, { method: 'POST' })
  }, [])

  return (
    <div className="app-shell">
      {/* Top bar */}
      <header className="app-header">
        <div className="header-left">
          <Heartbeat active={isStreaming} connected={connected} />
          <span className="project-name">{projectName}</span>
          <span className="project-path">{projectPath}</span>
        </div>
        <div className="header-center">
          <span className="session-info">
            {sessionDate} · Turn {turnCount} · Agent {currentAgentSlot + 1}/{agents.length || 3}
          </span>
        </div>
        <div className="header-right">
          {connected ? (
            <span className="badge badge-running">● LIVE</span>
          ) : (
            <span className="badge badge-error">● OFFLINE</span>
          )}
        </div>
      </header>

      {/* Main grid */}
      <main className="app-grid">
        {/* Row 1: Arsenal | Orchestration | Actions */}
        <div className="grid-area-arsenal">
          <ArsenalPanel activeTools={activeTools} isStreaming={isStreaming} />
        </div>
        <div className="grid-area-orchestration">
          <OrchestrationPanel
            agents={agents}
            handoffs={handoffs}
            currentSlot={currentAgentSlot}
          />
        </div>
        <div className="grid-area-actions">
          <ActionsPanel
            onFireAction={fireAction}
            onToggleProcess={toggleProcess}
            processes={processes}
            isStreaming={isStreaming}
          />
        </div>

        {/* Row 2: Results | Chat | NextSteps */}
        <div className="grid-area-results">
          <ResultsPanel
            recentTurns={recentTurns}
            heatmap={heatmap}
          />
        </div>
        <div className="grid-area-chat">
          <ChatPanel
            messages={messages}
            isStreaming={isStreaming}
            discussionActive={discussionActive}
            onSend={sendPrompt}
            onDiscussMessage={sendDiscussMessage}
            onToggleDiscussion={toggleDiscussion}
          />
        </div>
        <div className="grid-area-nextsteps">
          <NextStepsPanel
            synopsis={synopsis}
            turnCount={turnCount}
            sessionDate={sessionDate}
            projectName={projectName}
            isStreaming={isStreaming}
            onExport={async () => {
              await fetch('/api/export', { method: 'POST' })
            }}
          />
        </div>
      </main>
    </div>
  )
}
