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
        setLoading,
    } = useChatState()
    const [skillOpen, setSkillOpen] = useState(false)

    const { sendStream, abort } = useChatStream({
        chatId,
        addUserMessage,
        startStream,
        appendStreamText,
        addAssistantPart,
        finalizeStream,
        setError,
        loadMessages,
    })

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
                <Composer onSend={sendStream} disabled={state.isStreaming} />
            </div>
            <SkillDrawer chatId={chatId} open={skillOpen} onClose={() => setSkillOpen(false)} />
        </div>
    )
}
