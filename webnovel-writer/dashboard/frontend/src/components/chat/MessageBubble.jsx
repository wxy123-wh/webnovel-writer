import { memo } from 'react'

function formatTime(isoStr) {
    try {
        return new Date(isoStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    } catch {
        return ''
    }
}

function TextPart({ payload }) {
    return <div className="msg-text">{payload.content || ''}</div>
}

function ToolCallCard({ payload }) {
    return (
        <div className="msg-tool-call">
            <div className="tool-call-header">
                <span className="tool-icon">⚡</span>
                <span className="tool-name">{payload.name || payload.skill_id || 'Tool'}</span>
            </div>
            <pre className="tool-args">{JSON.stringify(payload.arguments || {}, null, 2)}</pre>
        </div>
    )
}

function ToolResultCard({ payload }) {
    const isError = payload.status === 'error'
    return (
        <div className={`msg-tool-result ${isError ? 'error' : 'success'}`}>
            <div className="tool-result-header">
                <span>{isError ? '✗' : '✓'}</span>
                <span>Result</span>
            </div>
            <pre className="tool-output">{JSON.stringify(payload.output || {}, null, 2)}</pre>
        </div>
    )
}

function ErrorPart({ payload }) {
    return (
        <div className="msg-error">
            <span>⚠ {payload.error || 'Unknown error'}</span>
            {payload.code ? <span className="error-code">({payload.code})</span> : null}
        </div>
    )
}

const MessageBubble = memo(function MessageBubble({ message }) {
    const isUser = message.role === 'user'
    const isStreaming = message.status === 'streaming'

    return (
        <div className={`msg-bubble ${isUser ? 'user' : 'assistant'} ${isStreaming ? 'streaming' : ''}`}>
            <div className="msg-role">{isUser ? '你' : 'Agent'}</div>
            <div className="msg-content">
                {(message.parts || []).map((part, index) => {
                    switch (part.type) {
                        case 'text':
                            return <TextPart key={index} payload={part.payload || {}} />
                        case 'tool_call':
                            return <ToolCallCard key={index} payload={part.payload || {}} />
                        case 'tool_result':
                            return <ToolResultCard key={index} payload={part.payload || {}} />
                        case 'error':
                            return <ErrorPart key={index} payload={part.payload || {}} />
                        default:
                            return <pre key={index}>{JSON.stringify(part.payload || {}, null, 2)}</pre>
                    }
                })}
            </div>
            <div className="msg-meta">
                {isStreaming ? <span className="streaming-dot">●</span> : null}
                <span className="msg-time">{formatTime(message.created_at)}</span>
            </div>
        </div>
    )
})

export default MessageBubble
