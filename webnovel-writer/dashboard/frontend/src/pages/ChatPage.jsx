import { useCallback, useEffect, useMemo, useState } from 'react'
import { createChat, listChats } from '../api/chat.js'
import PageScaffold from '../components/PageScaffold.jsx'
import ChatShell from '../components/chat/ChatShell.jsx'

function formatChatTime(value) {
    if (!value) return ''
    const parsed = new Date(value)
    if (Number.isNaN(parsed.getTime())) {
        return String(value).slice(5, 16)
    }
    return parsed.toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
    })
}

export default function ChatPage() {
    const [chats, setChats] = useState([])
    const [activeChatId, setActiveChatId] = useState(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')

    const loadChats = useCallback(async () => {
        setLoading(true)
        setError('')
        try {
            const list = await listChats()
            setChats(list)
            setActiveChatId(prev => prev || list[0]?.chat_id || null)
        } catch (loadError) {
            setError(loadError?.message || '加载对话列表失败')
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        void loadChats()
    }, [loadChats])

    const handleNewChat = useCallback(async () => {
        try {
            const chat = await createChat({ title: `对话 ${chats.length + 1}` })
            setChats(prev => [chat, ...prev])
            setActiveChatId(chat.chat_id)
        } catch (createError) {
            setError(createError?.message || '创建对话失败')
        }
    }, [chats.length])

    const badge = useMemo(() => {
        if (loading) return '加载中'
        return `${chats.length} 个会话`
    }, [chats.length, loading])

    return (
        <PageScaffold
            title="Chat Agent"
            badge={badge}
            description="在同一工作台中管理多轮对话、流式回复和技能挂载。"
        >
            <div className="chat-page">
                <div className="chat-sidebar card">
                    <button className="new-chat-btn" onClick={() => void handleNewChat()} type="button">
                        + 新对话
                    </button>

                    {error ? <div className="chat-error">{error}</div> : null}
                    {loading ? <div className="loading">对话列表加载中...</div> : null}

                    <div className="chat-list">
                        {chats.map(chat => (
                            <button
                                key={chat.chat_id}
                                className={`chat-list-item ${chat.chat_id === activeChatId ? 'active' : ''}`}
                                onClick={() => setActiveChatId(chat.chat_id)}
                                type="button"
                            >
                                <span className="chat-list-title">{chat.title || '未命名'}</span>
                                <span className="chat-list-time">{formatChatTime(chat.updated_at)}</span>
                            </button>
                        ))}
                    </div>
                </div>

                <div className="chat-workspace">
                    {activeChatId ? (
                        <ChatShell key={activeChatId} chatId={activeChatId} />
                    ) : (
                        <div className="chat-empty card">
                            <p>选择或创建一个对话开始写作。</p>
                        </div>
                    )}
                </div>
            </div>
        </PageScaffold>
    )
}
