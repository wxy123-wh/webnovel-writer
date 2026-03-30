import { useCallback, useReducer } from 'react'

const initialState = {
    chatId: null,
    title: '',
    messages: [],
    isLoading: false,
    isStreaming: false,
    error: '',
}

function buildAssistantPart(type, payload) {
    return {
        type,
        payload: payload || {},
    }
}

function appendAssistantPart(messages, part, messageId = 'streaming') {
    const lastMessage = messages[messages.length - 1]
    if (lastMessage?.role === 'assistant' && lastMessage?.status === 'streaming') {
        return [
            ...messages.slice(0, -1),
            {
                ...lastMessage,
                message_id: messageId || lastMessage.message_id,
                parts: [...(lastMessage.parts || []), part],
            },
        ]
    }

    return [
        ...messages,
        {
            message_id: messageId,
            role: 'assistant',
            status: 'streaming',
            parts: [part],
            created_at: new Date().toISOString(),
        },
    ]
}

function chatReducer(state, action) {
    switch (action.type) {
        case 'SET_CHAT':
            return {
                ...state,
                chatId: action.chat.chat_id,
                title: action.chat.title || '',
                messages: [],
                error: '',
            }
        case 'LOAD_MESSAGES':
            return {
                ...state,
                messages: Array.isArray(action.messages) ? action.messages : [],
                isLoading: false,
                error: '',
            }
        case 'ADD_USER_MESSAGE':
            return {
                ...state,
                messages: [...state.messages, action.message],
                error: '',
            }
        case 'START_STREAM':
            return {
                ...state,
                isStreaming: true,
                isLoading: false,
                error: '',
            }
        case 'APPEND_STREAM_TEXT': {
            const lastMessage = state.messages[state.messages.length - 1]
            if (lastMessage?.role === 'assistant' && lastMessage?.status === 'streaming') {
                const parts = [...(lastMessage.parts || [])]
                const lastPart = parts[parts.length - 1]
                if (lastPart?.type === 'text') {
                    parts[parts.length - 1] = {
                        ...lastPart,
                        payload: {
                            ...(lastPart.payload || {}),
                            content: `${lastPart.payload?.content || ''}${action.delta}`,
                        },
                    }
                } else {
                    parts.push(buildAssistantPart('text', { content: action.delta }))
                }

                return {
                    ...state,
                    messages: [
                        ...state.messages.slice(0, -1),
                        {
                            ...lastMessage,
                            message_id: action.messageId || lastMessage.message_id,
                            parts,
                        },
                    ],
                }
            }

            return {
                ...state,
                messages: [
                    ...state.messages,
                    {
                        message_id: action.messageId || 'streaming',
                        role: 'assistant',
                        status: 'streaming',
                        parts: [buildAssistantPart('text', { content: action.delta })],
                        created_at: new Date().toISOString(),
                    },
                ],
            }
        }
        case 'ADD_ASSISTANT_PART':
            return {
                ...state,
                messages: appendAssistantPart(
                    state.messages,
                    buildAssistantPart(action.partType, action.payload),
                    action.messageId,
                ),
            }
        case 'FINALIZE_STREAM':
            return {
                ...state,
                isStreaming: false,
                messages: state.messages.map(message => (
                    message.status === 'streaming'
                        ? { ...message, status: 'complete' }
                        : message
                )),
            }
        case 'SET_ERROR':
            return {
                ...state,
                error: action.error,
                isLoading: false,
                isStreaming: false,
            }
        case 'SET_LOADING':
            return {
                ...state,
                isLoading: action.loading,
            }
        default:
            return state
    }
}

export function useChatState() {
    const [state, dispatch] = useReducer(chatReducer, initialState)

    const setChat = useCallback(chat => dispatch({ type: 'SET_CHAT', chat }), [])
    const loadMessages = useCallback(messages => dispatch({ type: 'LOAD_MESSAGES', messages }), [])
    const addUserMessage = useCallback(message => dispatch({ type: 'ADD_USER_MESSAGE', message }), [])
    const startStream = useCallback(() => dispatch({ type: 'START_STREAM' }), [])
    const appendStreamText = useCallback(
        (delta, messageId) => dispatch({ type: 'APPEND_STREAM_TEXT', delta, messageId }),
        [],
    )
    const addAssistantPart = useCallback(
        (partType, payload, messageId) => dispatch({ type: 'ADD_ASSISTANT_PART', partType, payload, messageId }),
        [],
    )
    const finalizeStream = useCallback(() => dispatch({ type: 'FINALIZE_STREAM' }), [])
    const setError = useCallback(error => dispatch({ type: 'SET_ERROR', error }), [])
    const setLoading = useCallback(loading => dispatch({ type: 'SET_LOADING', loading }), [])

    return {
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
    }
}
