import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

const {
    getChatSkills,
    listSkills,
    updateChatSkills,
} = vi.hoisted(() => ({
    getChatSkills: vi.fn(),
    listSkills: vi.fn(),
    updateChatSkills: vi.fn(),
}))

vi.mock('../../api/chat.js', () => ({
    getChatSkills,
    listSkills,
    updateChatSkills,
}))

import SkillDrawer from './SkillDrawer.jsx'

describe('SkillDrawer', () => {
    afterEach(() => {
        vi.clearAllMocks()
        cleanup()
    })

    it('allows mounting a newly created workspace skill in chat', async () => {
        listSkills.mockResolvedValue([
            {
                skill_id: 'scene-beats',
                name: 'Scene Beats',
                description: 'Generate beat-first chapter scaffolds.',
                source: 'workspace',
                enabled: true,
            },
        ])
        getChatSkills.mockResolvedValueOnce([]).mockResolvedValueOnce([
            {
                skill_id: 'scene-beats',
                name: 'Scene Beats',
                description: 'Generate beat-first chapter scaffolds.',
                source: 'workspace',
                enabled: true,
            },
        ])
        updateChatSkills.mockResolvedValue([
            {
                skill_id: 'scene-beats',
                source: 'workspace',
                enabled: true,
            },
        ])

        const onSkillsChanged = vi.fn()

        render(<SkillDrawer chatId="chat-1" open onClose={() => {}} onSkillsChanged={onSkillsChanged} />)

        expect(await screen.findByText('Scene Beats')).toBeTruthy()

        fireEvent.click(screen.getByRole('button', { name: '启用' }))

        await waitFor(() => {
            expect(updateChatSkills).toHaveBeenCalledWith('chat-1', [
                { skill_id: 'scene-beats', source: 'workspace', enabled: true },
            ])
        })

        await waitFor(() => {
            expect(onSkillsChanged).toHaveBeenCalledWith([
                expect.objectContaining({ skill_id: 'scene-beats', source: 'workspace', enabled: true }),
            ])
        })
    })
})
