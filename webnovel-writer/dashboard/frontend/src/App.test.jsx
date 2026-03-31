import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'

vi.mock('./pages/ChatPage.jsx', () => ({
    default: () => <div>Chat Page Mock</div>,
}))

vi.mock('./pages/OutlineWorkspacePage.jsx', () => ({
    default: () => <div>Workspace Page Mock</div>,
}))

vi.mock('./pages/SettingsPage.jsx', () => ({
    default: () => <div>Settings Page Mock</div>,
}))

vi.mock('./pages/SkillsPage.jsx', () => ({
    default: () => <div>Skills Page Mock</div>,
}))

import App from './App.jsx'

afterEach(() => {
    window.location.hash = ''
    cleanup()
})

describe('App routing shell', () => {
    it('shows Workspace in the sidebar and switches routes by hash-aware nav clicks', () => {
        render(<App />)

        expect(screen.getByText('Chat Page Mock')).toBeTruthy()
        expect(screen.getByRole('button', { name: 'Workspace' })).toBeTruthy()
        expect(screen.getByRole('button', { name: 'Skills' })).toBeTruthy()
        expect(screen.getByRole('button', { name: 'Settings' })).toBeTruthy()

        fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))

        expect(window.location.hash).toBe('#/workspace')
        expect(screen.getByText('Workspace Page Mock')).toBeTruthy()

        fireEvent.click(screen.getByRole('button', { name: 'Skills' }))

        expect(window.location.hash).toBe('#/skills')
        expect(screen.getByText('Skills Page Mock')).toBeTruthy()

        fireEvent.click(screen.getByRole('button', { name: 'Settings' }))

        expect(window.location.hash).toBe('#/settings')
        expect(screen.getByText('Settings Page Mock')).toBeTruthy()
    })
})
