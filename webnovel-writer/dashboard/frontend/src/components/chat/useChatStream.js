import { useCallback, useRef } from 'react'
import { getMessages, streamMessage } from '../../api/chat.js'

export function useChatStream({
    chatId,
    appendStreamText,
    addAssistantPart,
    startStream,
    finalizeStream,
    setError,
    setSyncError,
    addUserMessage,
    loadMessages,
}) {
    const abortRef = useRef(null)
    const providerRef = useRef(null)

    const sendStream = useCallback(async content => {
        if (!chatId) return

        const userMessage = {
            message_id: `temp-${Date.now()}`,
            role: 'user',
            status: 'complete',
            parts: [{ type: 'text', payload: { content } }],
            created_at: new Date().toISOString(),
        }

        addUserMessage(userMessage)
        startStream()

        const handle = streamMessage(chatId, content, {
            onEvent: (eventType, data) => {
                switch (eventType) {
                    case 'message_start':
                        providerRef.current = data?.provider || null
                        break
                    case 'text_delta':
                        appendStreamText(data?.delta || '', data?.message_id)
                        break
                    case 'tool_call':
                        addAssistantPart('tool_call', data || {}, data?.message_id)
                        break
                    case 'tool_result':
                        addAssistantPart('tool_result', data || {}, data?.message_id)
                        break
                    case 'message_error':
                        addAssistantPart('error', data || {}, data?.message_id)
                        setError(data?.error || 'Stream error')
                        break
                    case 'message_complete':
                        finalizeStream()
                        break
                    default:
                        break
                }
            },
            onError: error => {
                setError(error?.message || 'Connection error')
            },
            onComplete: async () => {
                finalizeStream()
                try {
                    const messages = await getMessages(chatId)
                    loadMessages(messages)
                } catch {
                    setSyncError('消息同步失败，显示内容可能不完整')
                }
            },
        })

        abortRef.current = handle
    }, [
        addAssistantPart,
        addUserMessage,
        appendStreamText,
        chatId,
        finalizeStream,
        loadMessages,
        setError,
        setSyncError,
        startStream,
    ])

    const abort = useCallback(() => {
        abortRef.current?.abort()
        abortRef.current = null
        finalizeStream()
    }, [finalizeStream])

    return { sendStream, abort, providerRef }
}
