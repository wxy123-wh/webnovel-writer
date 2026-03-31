import { useEffect, useRef } from 'react'
import MessageBubble from './MessageBubble.jsx'

export default function MessageList({ messages, projectSummary = null, onStarterSelect = null }) {
    const bottomRef = useRef(null)

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages])

    if (!messages.length) {
        return (
            <div className="msg-list-empty">
                <div className="chat-welcome-card">
                    <div className="chat-welcome-title">开始对话吧</div>
                    <p className="chat-welcome-description">输入你的写作需求，Agent 会基于当前项目状态帮助你继续推进创作。</p>
                    {projectSummary?.title || projectSummary?.genre || projectSummary?.currentChapter ? (
                        <div className="chat-welcome-meta">
                            {projectSummary?.title ? <span>作品：{projectSummary.title}</span> : null}
                            {projectSummary?.genre ? <span>类型：{projectSummary.genre}</span> : null}
                            {projectSummary?.currentChapter ? <span>当前章节：{projectSummary.currentChapter}</span> : null}
                        </div>
                    ) : null}
                    <div className="chat-welcome-starters">
                        {[
                            '帮我生成这本书的核心卖点和一句话简介',
                            '按现在的项目状态，给我一个第一章开头方案',
                            '我想先梳理主角设定，帮我列出必须补齐的三项',
                        ].map(starter => (
                            <button
                                key={starter}
                                className="chat-starter-chip"
                                onClick={() => onStarterSelect?.(starter)}
                                type="button"
                            >
                                {starter}
                            </button>
                        ))}
                    </div>
                </div>
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
