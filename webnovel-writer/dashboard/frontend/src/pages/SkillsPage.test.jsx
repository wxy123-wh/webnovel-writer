import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

const {
    listSkills,
    createSkill,
    deleteSkill,
    generateSkillDraft,
    classifySkillsError,
} = vi.hoisted(() => ({
    listSkills: vi.fn(),
    createSkill: vi.fn(),
    deleteSkill: vi.fn(),
    generateSkillDraft: vi.fn(),
    classifySkillsError: vi.fn(error => error?.errorType || 'api'),
}))

const { fetchRuntimeProfile } = vi.hoisted(() => ({
    fetchRuntimeProfile: vi.fn(),
}))

vi.mock('../api/skills.js', () => ({
    listSkills,
    createSkill,
    deleteSkill,
    generateSkillDraft,
    classifySkillsError,
}))

vi.mock('../api/runtime.js', () => ({
    fetchRuntimeProfile,
}))

import SkillsPage from './SkillsPage.jsx'

describe('SkillsPage', () => {
    beforeEach(() => {
        listSkills.mockResolvedValue({
            status: 'ok',
            items: [
                {
                    skill_id: 'scene-beats',
                    name: 'Scene Beats',
                    description: 'Generate beat-first chapter scaffolds.',
                    source: 'workspace',
                    updated_at: '2026-03-30T00:00:00Z',
                    enabled: true,
                },
            ],
            total: 1,
        })
        createSkill.mockResolvedValue({
            skill_id: 'new-skill',
            name: 'New Skill',
            description: 'Freshly created',
            source: 'workspace',
            updated_at: '2026-03-31T00:00:00Z',
            enabled: true,
        })
        deleteSkill.mockResolvedValue(null)
        generateSkillDraft.mockResolvedValue({
            reply: '我已经帮你生成了一版偏向章节节拍拆解的 skill 草稿。',
            draft: {
                skill_id: 'scene-beats',
                name: 'Scene Beats',
                description: 'Generate beat-first chapter scaffolds.',
                instruction_template: '# Scene Beats\n\nAlways propose three escalating beats before drafting.',
            },
        })
        fetchRuntimeProfile.mockResolvedValue({
            generation: {
                configured: true,
                skill_draft_available: true,
                provider: 'openai',
                model: 'gpt-4o-mini',
            },
        })
    })

    afterEach(() => {
        vi.clearAllMocks()
        cleanup()
    })

    it('lists skills, creates a new template-first skill with normalized fields, keeps the draft as a reusable base, and deletes an existing one', async () => {
        render(<SkillsPage />)

        expect(await screen.findByText('Scene Beats')).toBeTruthy()

        fireEvent.change(screen.getByLabelText('Skill ID'), { target: { value: ' new-skill ' } })
        fireEvent.change(screen.getByLabelText('名称'), { target: { value: ' New Skill ' } })
        fireEvent.change(screen.getByLabelText('描述'), { target: { value: ' Freshly created ' } })
        fireEvent.change(screen.getByLabelText('模板指令'), { target: { value: ' # New Skill\n\nHelp me outline scenes.\n' } })

        fireEvent.click(screen.getByRole('button', { name: '创建技能' }))

        await waitFor(() => {
            expect(createSkill).toHaveBeenCalledWith({
                skill_id: 'new-skill',
                name: 'New Skill',
                description: 'Freshly created',
                instruction_template: '# New Skill\n\nHelp me outline scenes.',
            })
        })

        expect(await screen.findByText('技能已创建，现在可以在 Chat 中挂载。当前草稿会保留，便于继续调整后重新创建，或清空后开始下一份。')).toBeTruthy()
        expect(screen.getByLabelText('Skill ID').value).toBe('new-skill')
        expect(screen.getByLabelText('名称').value).toBe('New Skill')
        expect(screen.getByLabelText('描述').value).toBe('Freshly created')
        expect(screen.getByLabelText('模板指令').value).toBe('# New Skill\n\nHelp me outline scenes.')

        fireEvent.click(screen.getByRole('button', { name: '删除 Scene Beats' }))

        await waitFor(() => {
            expect(deleteSkill).toHaveBeenCalledWith('scene-beats')
        })
    })

    it('builds a skill draft through the local chat flow and adds the saved skill to the registry immediately', async () => {
        render(<SkillsPage />)

        await screen.findByText('Scene Beats')

        const chatInput = screen.getByLabelText('技能创建对话输入')

        fireEvent.change(chatInput, { target: { value: 'new-skill' } })
        fireEvent.click(screen.getByRole('button', { name: '直接写入草稿' }))
        expect(screen.getByLabelText('Skill ID').value).toBe('new-skill')

        fireEvent.change(chatInput, { target: { value: 'New Skill' } })
        fireEvent.click(screen.getByRole('button', { name: '直接写入草稿' }))
        expect(screen.getByLabelText('名称').value).toBe('New Skill')

        fireEvent.change(chatInput, { target: { value: 'Freshly created' } })
        fireEvent.click(screen.getByRole('button', { name: '直接写入草稿' }))
        expect(screen.getByLabelText('描述').value).toBe('Freshly created')

        fireEvent.change(chatInput, { target: { value: '# New Skill\n\nHelp me outline scenes.' } })
        fireEvent.click(screen.getByRole('button', { name: '直接写入草稿' }))
        expect(screen.getByLabelText('模板指令').value).toBe('# New Skill\n\nHelp me outline scenes.')

        fireEvent.click(screen.getByRole('button', { name: '创建技能' }))

        await waitFor(() => {
            expect(createSkill).toHaveBeenCalledWith({
                skill_id: 'new-skill',
                name: 'New Skill',
                description: 'Freshly created',
                instruction_template: '# New Skill\n\nHelp me outline scenes.',
            })
        })

        expect(await screen.findByText('技能已创建，现在可以在 Chat 中挂载。当前草稿会保留，便于继续调整后重新创建，或清空后开始下一份。')).toBeTruthy()
        expect(await screen.findByText('已更新 模板指令。右侧结构化草稿已经齐全，现在可以直接保存，或继续覆盖后重新创建。')).toBeTruthy()
        expect(await screen.findAllByText('Freshly created')).toHaveLength(2)
    })

    it('calls the real draft generation API and applies the returned draft into the editable form', async () => {
        render(<SkillsPage />)

        await screen.findByText('Scene Beats')

        fireEvent.change(screen.getByLabelText('技能创建对话输入'), {
            target: { value: '帮我生成一个专门拆章节节拍的技能' },
        })
        fireEvent.click(screen.getByRole('button', { name: 'AI 生成草稿' }))

        await waitFor(() => {
            expect(generateSkillDraft).toHaveBeenCalledWith({
                prompt: '帮我生成一个专门拆章节节拍的技能',
                currentDraft: {
                    skill_id: '',
                    name: '',
                    description: '',
                    instruction_template: '',
                },
            })
        })

        expect(await screen.findByText('我已经帮你生成了一版偏向章节节拍拆解的 skill 草稿。')).toBeTruthy()
        expect(screen.getByLabelText('Skill ID').value).toBe('scene-beats')
        expect(screen.getByLabelText('名称').value).toBe('Scene Beats')
        expect(screen.getByLabelText('描述').value).toBe('Generate beat-first chapter scaffolds.')
        expect(screen.getByLabelText('模板指令').value).toBe('# Scene Beats\n\nAlways propose three escalating beats before drafting.')
    })

    it('routes structured field input through the local draft path even when AI draft generation is available', async () => {
        render(<SkillsPage />)

        await screen.findByText('Scene Beats')

        fireEvent.change(screen.getByLabelText('技能创建对话输入'), {
            target: { value: 'name: Fast Beats' },
        })
        fireEvent.click(screen.getByRole('button', { name: 'AI 生成草稿' }))

        expect(generateSkillDraft).not.toHaveBeenCalled()
        expect(screen.getByLabelText('名称').value).toBe('Fast Beats')
        expect(await screen.findByText('已更新 名称。下一步请提供Skill ID。')).toBeTruthy()
    })

    it('still routes structured field input through the local draft path when AI draft generation is unavailable', async () => {
        fetchRuntimeProfile.mockResolvedValueOnce({
            generation: {
                configured: false,
                skill_draft_available: false,
                provider: 'local',
                model: 'local-assist-v1',
            },
        })

        render(<SkillsPage />)

        await screen.findByText('Scene Beats')

        fireEvent.change(screen.getByLabelText('技能创建对话输入'), {
            target: { value: 'name: Offline Beats' },
        })
        fireEvent.click(screen.getByRole('button', { name: 'AI 生成草稿' }))

        expect(generateSkillDraft).not.toHaveBeenCalled()
        expect(screen.getByLabelText('名称').value).toBe('Offline Beats')
        expect(await screen.findByText('已更新 名称。下一步请提供Skill ID。')).toBeTruthy()
    })

    it('shows backend validation and conflict copy without collapsing the page', async () => {
        createSkill.mockRejectedValueOnce({
            message: 'Skill payload is invalid.',
            errorCode: 'invalid_skill_payload',
            errorType: 'validation',
        })
        createSkill.mockRejectedValueOnce({
            message: 'A skill with this id already exists.',
            errorCode: 'skill_conflict',
            errorType: 'conflict',
        })

        render(<SkillsPage />)
        await screen.findByText('Scene Beats')

        fireEvent.change(screen.getByLabelText('Skill ID'), { target: { value: 'bad skill' } })
        fireEvent.change(screen.getByLabelText('名称'), { target: { value: '' } })
        fireEvent.change(screen.getByLabelText('模板指令'), { target: { value: '' } })
        fireEvent.click(screen.getByRole('button', { name: '创建技能' }))

        expect(await screen.findByText('Skill payload is invalid. (invalid_skill_payload)')).toBeTruthy()

        fireEvent.change(screen.getByLabelText('Skill ID'), { target: { value: 'scene-beats' } })
        fireEvent.change(screen.getByLabelText('名称'), { target: { value: 'Scene Beats' } })
        fireEvent.change(screen.getByLabelText('模板指令'), { target: { value: '# Scene Beats' } })
        fireEvent.click(screen.getByRole('button', { name: '创建技能' }))

        expect(await screen.findByText('存在资源冲突，请刷新后重试 (skill_conflict)')).toBeTruthy()
    })
})
