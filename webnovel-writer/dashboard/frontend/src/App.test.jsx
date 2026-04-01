import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'

vi.mock('./pages/ChatPage.jsx', () => ({
    default: () => <div>Chat Page Mock</div>,
}))

vi.mock('./pages/CreationDeskPage.jsx', () => ({
    default: () => <div>Creation Desk Page Mock</div>,
}))

vi.mock('./pages/DataPanelPage.jsx', () => ({
    default: () => <div>Data Panel Page Mock</div>,
}))

vi.mock('./pages/SettingsPage.jsx', () => ({
    default: () => <div>Settings Page Mock</div>,
}))

vi.mock('./pages/SkillsPage.jsx', () => ({
    default: () => <div>Skills Page Mock</div>,
}))

vi.mock('./pages/SkillLibraryPage.jsx', () => ({
    default: ({ chatId }) => <div>Skill Library Mock: {chatId}</div>,
}))

vi.mock('./pages/SkillDetailPage.jsx', () => ({
    default: ({ skillId }) => <div>Skill Detail Mock: {skillId}</div>,
}))

import App from './App.jsx'

afterEach(() => {
    window.location.hash = ''
    cleanup()
})

describe('App routing shell', () => {
    it('shows navigation and switches routes by hash-aware nav clicks', () => {
        render(<App />)

        expect(screen.getByText('Chat Page Mock')).toBeTruthy()
        expect(screen.getByRole('button', { name: '创作台' })).toBeTruthy()
        expect(screen.getByRole('button', { name: '数据面板' })).toBeTruthy()
        expect(screen.getByRole('button', { name: 'Skills' })).toBeTruthy()
        expect(screen.getByRole('button', { name: 'Settings' })).toBeTruthy()

        fireEvent.click(screen.getByRole('button', { name: '创作台' }))
        expect(window.location.hash).toBe('#/creation-desk')
        expect(screen.getByText('Creation Desk Page Mock')).toBeTruthy()

        fireEvent.click(screen.getByRole('button', { name: 'Skills' }))
        expect(window.location.hash).toBe('#/skills')
        expect(screen.getByText('Skills Page Mock')).toBeTruthy()

        fireEvent.click(screen.getByRole('button', { name: 'Settings' }))
        expect(window.location.hash).toBe('#/settings')
        expect(screen.getByText('Settings Page Mock')).toBeTruthy()
    })

    it('renders chat skill library page for chat skill list route', () => {
        window.location.hash = '#/chat/skills/chat-123'
        render(<App />)

        expect(screen.getByText('Skill Library Mock: chat-123')).toBeTruthy()
    })

    it('renders chat skill detail page for nested hash route', () => {
        window.location.hash = '#/chat/skills/chat-123/webnovel-dashboard/system'
        render(<App />)

        expect(screen.getByText('Skill Detail Mock: webnovel-dashboard')).toBeTruthy()
    })
})
