import { useEffect, useState } from 'react'
import { getMessages } from '../../api/chat.js'
import Composer from './Composer.jsx'
import MessageList from './MessageList.jsx'
import SkillDrawer from './SkillDrawer.jsx'
import { useChatState } from './useChatState.js'
import { useChatStream } from './useChatStream.js'

export default function ChatShell({ chatId }) {
    const {
        state,
        setChat,
        loadMessages,
        addUserMessage,
        startStream,
        appendStreamText,
        addAssistantPart,
        finalizeStream,
        setError,
        setSyncError,
        clearSyncError,
        setLoading,
    } = useChatState()
    const [skillOpen, setSkillOpen] = useState(false)
    const [isStubMode, setIsStubMode] = useState(false)

    const { sendStream, abort, providerRef } = useChatStream({
        chatId,
        addUserMessage,
        startStream,
        appendStreamText,
        addAssistantPart,
        finalizeStream,
        setError,
        setSyncError,
        loadMessages,
    })

    useEffect(() => {
        setIsStubMode(providerRef.current === 'stub')
    }, [providerRef, state.messages])

    useEffect(() => {
        let cancelled = false

        async function loadChatMessages() {
            if (!chatId) return

            setChat({ chat_id: chatId, title: '' })
            setLoading(true)
            try {
                const messages = await getMessages(chatId)
                if (!cancelled) {
                    loadMessages(messages)
                }
            } catch (error) {
                if (!cancelled) {
                    setError(error?.message || '加载消息失败')
                }
            } finally {
                if (!cancelled) {
                    setLoading(false)
                }
            }
        }

        void loadChatMessages()

        return () => {
            cancelled = true
            abort()
        }
    }, [abort, chatId, loadMessages, setChat, setError, setLoading])

    return (
        <div className="chat-shell">
            <div className="chat-main card">
                <div className="chat-toolbar">
                    <button className="page-btn" onClick={() => setSkillOpen(prev => !prev)} type="button">
                        ⚡ Skills
                    </button>
                </div>
                {state.isLoading ? <div className="loading">消息加载中...</div> : <MessageList messages={state.messages} />}
                {state.error ? <div className="chat-error">{state.error}</div> : null}
                {state.syncError ? (
                    <div className="chat-sync-warning" style={{
                        padding: '6px 12px',
                        background: '#fff3cd',
                        border: '1px solid #ffc107',
                        borderRadius: 4,
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        fontSize: 13,
                    }}>
                        <span>{state.syncError}</span>
                        <button onClick={() => {
                            clearSyncError()
                            if (chatId) {
                                getMessages(chatId).then(loadMessages).catch(() => setSyncError('重试同步失败'))
                            }
                        }} type="button" style={{
                            border: '1px solid #856404',
                            background: '#fff',
                            cursor: 'pointer',
                            padding: '2px 8px',
                            fontSize: 12,
                        }}>
                            重试
                        </button>
                    </div>
                ) : null}
                {isStubMode ? (
                    <div style={{
                        padding: '8px 12px',
                        background: '#fff3cd',
                        border: '1px solid #ffc107',
                        borderRadius: 4,
                        fontSize: 13,
                        color: '#856404',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                    }}>
                        <span>⚠️ 模拟模式 — AI 生成内容为模板占位。请配置 GENERATION_API_KEY 以启用真实生成。</span>
                        <button onClick={() => setIsStubMode(false)} type="button" style={{
                            border: 'none', background: 'transparent', cursor: 'pointer', fontSize: 16, color: '#856404',
                        }}>✕</button>
                    </div>
                ) : null}
                <Composer onSend={sendStream} disabled={state.isStreaming} />
            </div>
            <SkillDrawer chatId={chatId} open={skillOpen} onClose={() => setSkillOpen(false)} />
        </div>
    )
}
