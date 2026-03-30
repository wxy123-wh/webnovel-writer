import { useEffect, useRef } from 'react'
import MessageBubble from './MessageBubble.jsx'

export default function MessageList({ messages }) {
    const bottomRef = useRef(null)

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages])

    if (!messages.length) {
        return (
            <div className="msg-list-empty">
                <p>开始对话吧！输入你的写作需求，Agent 会帮助你推进创作。</p>
            </div>
        )
    }

    return (
        <div className="msg-list">
            {messages.map(message => (
                <MessageBubble key={message.message_id} message={message} />
            ))}
            <div ref={bottomRef} />
        </div>
    )
}
