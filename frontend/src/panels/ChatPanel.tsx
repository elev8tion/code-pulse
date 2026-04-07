import { useState, useRef, useEffect, KeyboardEvent } from 'react'
import { ChatMessage } from '../App'
import './ChatPanel.css'

interface Props {
  messages: ChatMessage[]
  isStreaming: boolean
  discussionActive: boolean
  onSend: (message: string) => Promise<void>
  onDiscussMessage: (message: string) => Promise<void>
  onToggleDiscussion: () => Promise<void>
}

export default function ChatPanel({
  messages,
  isStreaming,
  discussionActive,
  onSend,
  onDiscussMessage,
  onToggleDiscussion,
}: Props) {
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    const text = input.trim()
    if (!text || isStreaming) return
    setInput('')
    if (text.startsWith('/')) {
      // Send as command
      try {
        const res = await fetch('/api/command', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ command: text }),
        })
        const data = await res.json()
        if (data.response) {
          // System message will be shown via broadcast
        }
      } catch {}
      return
    }
    if (discussionActive) {
      await onDiscussMessage(text)
    } else {
      await onSend(text)
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  // Auto-resize textarea
  const handleInput = () => {
    const ta = textareaRef.current
    if (ta) {
      ta.style.height = 'auto'
      ta.style.height = `${Math.min(ta.scrollHeight, 120)}px`
    }
  }

  return (
    <div className={`panel chat-panel ${discussionActive ? 'chat-panel--discuss' : ''}`}>
      <div className="panel-header">
        <span className="icon">💬</span>
        <span>{discussionActive ? 'Discussion Mode' : 'Chat'}</span>
        <button
          className={`btn ${discussionActive ? 'btn-danger' : 'btn-secondary'}`}
          style={{ marginLeft: 'auto', padding: '2px 10px', fontSize: '10px' }}
          onClick={onToggleDiscussion}
          title={discussionActive ? 'Exit discussion mode' : 'Enter discussion mode'}
        >
          {discussionActive ? '✖ Exit Discuss' : '💬 Discuss'}
        </button>
      </div>

      {/* Message list */}
      <div className="chat-messages">
        {messages.length === 0 ? (
          <div className="chat-empty">
            <div className="chat-empty-icon">⚡</div>
            <div className="chat-empty-text">Code-Pulse is ready.</div>
            <div className="chat-empty-hint">Type a prompt or click an action card to get started.</div>
          </div>
        ) : (
          messages.map((msg, i) => (
            <div
              key={i}
              className={`message message--${msg.role} ${msg.streaming ? 'message--streaming' : ''} animate-slide-in`}
            >
              {msg.role === 'user' && (
                <div className="message-role">You</div>
              )}
              {msg.role === 'assistant' && (
                <div className="message-role assistant-role">Claude</div>
              )}
              <div className="message-content">
                <MessageContent content={msg.content} streaming={msg.streaming} />
              </div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="chat-input-area">
        {discussionActive && (
          <div className="discuss-banner">
            💬 Discussion mode — asking about current code state
          </div>
        )}
        <div className="chat-input-row">
          <textarea
            ref={textareaRef}
            className="chat-textarea"
            value={input}
            onChange={e => { setInput(e.target.value); handleInput() }}
            onKeyDown={handleKeyDown}
            placeholder={
              isStreaming
                ? 'Claude is working…'
                : discussionActive
                  ? 'Ask about the current changes…'
                  : 'Send a prompt, or type / for commands'
            }
            disabled={isStreaming}
            rows={1}
          />
          <button
            className="btn btn-primary send-btn"
            onClick={handleSend}
            disabled={isStreaming || !input.trim()}
          >
            {isStreaming ? '…' : '↵'}
          </button>
        </div>
      </div>
    </div>
  )
}

function MessageContent({ content, streaming }: { content: string; streaming?: boolean }) {
  if (!content && streaming) {
    return <span className="cursor" />
  }
  // Simple renderer: preserve line breaks, highlight code blocks
  const parts = content.split(/(```[\s\S]*?```)/g)
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith('```') && part.endsWith('```')) {
          const inner = part.slice(3, -3).replace(/^\w+\n/, '')
          return <pre key={i}><code>{inner}</code></pre>
        }
        return (
          <span key={i} style={{ whiteSpace: 'pre-wrap' }}>
            {part}
          </span>
        )
      })}
      {streaming && <span className="cursor" />}
    </>
  )
}
