import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

const { listChats, createChat, fetchRuntimeProfile } = vi.hoisted(() => ({
    listChats: vi.fn(),
    createChat: vi.fn(),
    fetchRuntimeProfile: vi.fn(),
}))

vi.mock('../api/chat.js', () => ({
    listChats,
    createChat,
}))

vi.mock('../api/runtime.js', () => ({
    fetchRuntimeProfile,
}))

vi.mock('../components/PageScaffold.jsx', () => ({
    default: ({ children, title }) => (
        <div>
            <h1>{title}</h1>
            {children}
        </div>
    ),
}))

vi.mock('../components/chat/ChatShell.jsx', () => ({
    default: () => <div>Chat Shell Mock</div>,
}))

import ChatPage from './ChatPage.jsx'

describe('ChatPage gating', () => {
    afterEach(() => {
        vi.clearAllMocks()
        window.location.hash = ''
        cleanup()
    })

    it('does not treat local mode as ready and routes users to Settings', async () => {
        listChats.mockResolvedValue([])
        fetchRuntimeProfile.mockResolvedValue({
            generation: {
                configured: true,
                provider: 'local',
                api_key_configured: false,
                model: 'built-in',
                base_url: '',
            },
            project: {
                title: '测试作品',
            },
        })

        render(<ChatPage />)

        expect(await screen.findByText('本地模式不再直接解锁 Chat')).toBeTruthy()
        expect(screen.getByRole('button', { name: '+ 新对话' }).disabled).toBe(true)
        expect(screen.getByText('Provider')).toBeTruthy()

        fireEvent.click(screen.getByRole('button', { name: '打开 Settings 完成配置' }))

        await waitFor(() => {
            expect(window.location.hash).toBe('#/settings')
        })
        expect(createChat).not.toHaveBeenCalled()
        expect(screen.queryByText('✅ 本地模式已就绪')).toBeNull()
    })
})
