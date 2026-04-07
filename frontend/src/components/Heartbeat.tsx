import './Heartbeat.css'

interface Props {
  active: boolean
  connected: boolean
}

export default function Heartbeat({ active, connected }: Props) {
  return (
    <div className={`heartbeat ${active ? 'heartbeat--active' : ''} ${!connected ? 'heartbeat--offline' : ''}`}>
      <div className="heartbeat-ring" />
      <div className="heartbeat-core">
        <svg viewBox="0 0 40 20" fill="none" xmlns="http://www.w3.org/2000/svg">
          <polyline
            points="0,10 8,10 11,2 14,18 17,5 20,15 23,10 32,10"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        </svg>
      </div>
    </div>
  )
}
