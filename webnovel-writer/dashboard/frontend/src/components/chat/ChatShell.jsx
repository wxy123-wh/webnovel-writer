import { useEffect, useState } from 'react'
import { getChatSkills, getMessages } from '../../api/chat.js'
import Composer from './Composer.jsx'
import MessageList from './MessageList.jsx'
import { useChatState } from './useChatState.js'
import { useChatStream } from './useChatStream.js'

function openSkillLibrary(chatId) {
    if (typeof window === 'undefined' || !chatId) return
    window.location.hash = `#/chat/skills/${chatId}`
}

function openSkillDetail(chatId, skill) {
    if (typeof window === 'undefined' || !chatId || !skill?.skill_id) return
    const safeSkillId = encodeURIComponent(skill.skill_id)
    const safeSource = encodeURIComponent(skill.source || 'workspace')
    window.location.hash = `#/chat/skills/${chatId}/${safeSkillId}/${safeSource}`
}

export default function ChatShell({ chatId, projectSummary = null }) {
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
    const [mountedSkills, setMountedSkills] = useState([])

    const { sendStream, abort } = useChatStream({
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
        let cancelled = false

        async function loadChatMessages() {
            if (!chatId) return

            setChat({ chat_id: chatId, title: '' })
            setLoading(true)
            try {
                const [messages, skills] = await Promise.all([
                    getMessages(chatId),
                    getChatSkills(chatId),
                ])
                if (!cancelled) {
                    loadMessages(messages)
                    setMountedSkills(Array.isArray(skills) ? skills.filter(skill => skill.enabled) : [])
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
                    <button
                        className="page-btn"
                        onClick={() => openSkillLibrary(chatId)}
                        type="button"
                    >
                        技能页面
                    </button>
                </div>
                <div className="chat-skill-summary">
                    {mountedSkills.length > 0 ? (
                        <>
                            <span className="chat-skill-summary-label">当前技能约束</span>
                            <div className="chat-skill-chip-list">
                                {mountedSkills.map(skill => (
                                    <button
                                        className="chat-skill-chip chat-skill-chip-button"
                                        key={`${skill.source}:${skill.skill_id}`}
                                        onClick={() => openSkillDetail(chatId, skill)}
                                        type="button"
                                    >
                                        {skill.name || skill.skill_id}
                                    </button>
                                ))}
                            </div>
                        </>
                    ) : (
                        <span className="chat-skill-summary-empty">当前未启用额外技能；可通过上方“技能页面”查看全部技能列表。</span>
                    )}
                </div>
                {state.isLoading ? <div className="loading">消息加载中...</div> : <MessageList messages={state.messages} projectSummary={projectSummary} onStarterSelect={sendStream} />}
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
                <Composer onSend={sendStream} disabled={state.isStreaming} />
            </div>
        </div>
    )
}
