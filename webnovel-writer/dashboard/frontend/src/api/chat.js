import { createRequestUrl } from './http.js'

const API_BASE = '/api/chat'

function buildURL(path) {
    return createRequestUrl(`${API_BASE}${path}`)
}

export class ChatApiError extends Error {
    constructor(message, status = 0, code = 'chat_api_error') {
        super(message)
        this.name = 'ChatApiError'
        this.status = status
        this.code = code
    }
}

async function request(path, options = {}) {
    const requestOptions = {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...(options.headers || {}),
        },
    }

    let response
    try {
        response = await fetch(buildURL(path), requestOptions)
    } catch (error) {
        throw new ChatApiError('无法连接到 Chat 服务，请确认后端已启动。', 0, 'network_error')
    }

    if (!response.ok) {
        let code = 'unknown'
        let message = `HTTP ${response.status}`
        try {
            const body = await response.json()
            code = body.error_code || code
            message = body.message || message
        } catch {
            // ignore malformed error payloads
        }
        throw new ChatApiError(message, response.status, code)
    }

    if (response.status === 204) return null
    return response.json()
}

export async function listChats() {
    const payload = await request('/chats')
    return Array.isArray(payload) ? payload : []
}

export async function createChat({ title = '', profile = null, skillIds = null } = {}) {
    const body = { title }
    if (profile) body.profile = profile
    if (skillIds) body.skill_ids = skillIds
    return request('/chats', { method: 'POST', body: JSON.stringify(body) })
}

export async function deleteChat(chatId) {
    return request(`/chats/${chatId}`, { method: 'DELETE' })
}

export async function getMessages(chatId) {
    const payload = await request(`/chats/${chatId}/messages`)
    return Array.isArray(payload) ? payload : []
}

export async function listSkills() {
    const payload = await request('/skills')
    return Array.isArray(payload) ? payload : []
}

export async function getChatSkills(chatId) {
    const payload = await request(`/chats/${chatId}/skills`)
    return Array.isArray(payload) ? payload : []
}

export async function updateChatSkills(chatId, skills) {
    return request(`/chats/${chatId}/skills`, {
        method: 'PATCH',
        body: JSON.stringify({ skills }),
    })
}

export function streamMessage(chatId, content, { onEvent, onError, onComplete } = {}) {
    const controller = new AbortController()

    ;(async () => {
        try {
            const response = await fetch(buildURL(`/chats/${chatId}/stream`), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content }),
                signal: controller.signal,
            })

            if (!response.ok) {
                throw new ChatApiError(`HTTP ${response.status}`, response.status, 'stream_error')
            }

            const reader = response.body?.getReader()
            if (!reader) {
                throw new ChatApiError('流式响应不可用。', response.status, 'stream_unavailable')
            }

            const decoder = new TextDecoder()
            let buffer = ''
            let currentEvent = null

            while (true) {
                const { done, value } = await reader.read()
                if (done) break

                buffer += decoder.decode(value, { stream: true })
                const chunks = buffer.split('\n')
                buffer = chunks.pop() || ''

                chunks.forEach(line => {
                    const trimmed = line.trim()
                    if (!trimmed) {
                        currentEvent = null
                        return
                    }

                    if (trimmed.startsWith('event: ')) {
                        currentEvent = trimmed.slice(7).trim()
                        return
                    }

                    if (trimmed.startsWith('data: ') && currentEvent) {
                        try {
                            const data = JSON.parse(trimmed.slice(6))
                            onEvent?.(currentEvent, data)
                        } catch {
                            // ignore malformed event payloads
                        }
                    }
                })
            }

            onComplete?.()
        } catch (error) {
            if (error?.name !== 'AbortError') {
                onError?.(error)
            }
        }
    })()

    return {
        abort: () => controller.abort(),
    }
}
