import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import MessageBubble from './MessageBubble.jsx'

describe('MessageBubble', () => {
    it('renders persisted text parts that use payload.text', () => {
        render(
            <MessageBubble
                message={{
                    message_id: 'msg_1',
                    role: 'assistant',
                    status: 'complete',
                    created_at: '2026-03-31T00:00:00Z',
                    parts: [{ type: 'text', payload: { text: '持久化后的消息内容' } }],
                }}
            />,
        )

        expect(screen.getByText('持久化后的消息内容')).toBeTruthy()
    })
})
