/** Shared TypeScript types for Code-Pulse frontend. */

export interface AgentInfo {
  slot_id: number
  state: 'sleeping' | 'processing' | 'discussing'
  synopsis: string
  is_current: boolean
}

export interface HeatMapEntry {
  path: string
  touch_count: number
  lines_changed: number
  intensity: number
}

export interface HeatMapData {
  entries: HeatMapEntry[]
  max_touch_count: number
  max_lines_changed: number
}

export interface FileDiff {
  path: string
  change_type: 'added' | 'modified' | 'deleted'
  lines_added: number
  lines_removed: number
  directory: string
}

export interface TurnRecord {
  turn_index: number
  timestamp: string
  user_message: string
  assistant_message: string
  synopsis: string
  agent_slot: number
  diff_path: string | null
}

export interface HandoffRecord {
  from_slot: number
  to_slot: number
  synopsis: string
  timestamp: string
}

export interface ProcessInfo {
  name: string
  command: string
  status: 'stopped' | 'running' | 'error'
  pid: number | null
  exit_code: number | null
  recent_output: string[]
}

export interface ActionDefinition {
  id: string
  label: string
  icon: string
  prompt: string | null
  needs_sub_prompt: boolean
  sub_prompt_label: string
  color: string
}

export interface AppSnapshot {
  project_name: string
  project_path: string
  session_date: string
  turn_count: number
  current_agent_slot: number
  agent_pool_size: number
  is_streaming: boolean
  heatmap: HeatMapData
  agents: AgentInfo[]
  processes: ProcessInfo[]
  recent_turns: TurnRecord[]
  handoffs: HandoffRecord[]
}

// WebSocket event messages

export type WSMessage =
  | { type: 'ping' }
  | { type: 'snapshot'; data: AppSnapshot }
  | { type: 'stream_start'; user_message: string }
  | { type: 'stream_chunk'; text: string }
  | { type: 'stream_end'; turn_index: number; synopsis: string; agent_slot: number; next_agent_slot: number; diff: { files_changed: number; lines_added: number; lines_removed: number; files: FileDiff[] }; heatmap: HeatMapData }
  | { type: 'tool_call'; tool: string; count: number }
  | { type: 'tools_cleared' }
  | { type: 'process_output'; name: string; line: string }
  | { type: 'process_status'; name: string; status: 'stopped' | 'running' | 'error' }
  | { type: 'discuss_opened'; synopsis_preview: string }
  | { type: 'discuss_closed' }
  | { type: 'discuss_start'; user_message: string }
  | { type: 'discuss_chunk'; text: string }
  | { type: 'discuss_end' }
  | { type: 'error'; message: string }
