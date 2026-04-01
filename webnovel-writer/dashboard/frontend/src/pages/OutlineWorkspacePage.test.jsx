import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

const {
    fetchAuthoringWorkspace,
    saveEntityDraft,
    confirmProposal,
    rejectProposal,
    fetchRevisionDiff,
    rollbackRevision,
    markIndexStale,
    rebuildIndex,
    formatAuthoringApiError,
} = vi.hoisted(() => ({
    fetchAuthoringWorkspace: vi.fn(),
    saveEntityDraft: vi.fn(),
    confirmProposal: vi.fn(),
    rejectProposal: vi.fn(),
    fetchRevisionDiff: vi.fn(),
    rollbackRevision: vi.fn(),
    markIndexStale: vi.fn(),
    rebuildIndex: vi.fn(),
    formatAuthoringApiError: vi.fn(error => `${error?.errorCode || 'api_error'}: ${error?.message || '请求失败'}`),
}))

vi.mock('../api/authoring.js', () => ({
    fetchAuthoringWorkspace,
    saveEntityDraft,
    confirmProposal,
    rejectProposal,
    fetchRevisionDiff,
    rollbackRevision,
    markIndexStale,
    rebuildIndex,
    formatAuthoringApiError,
}))

import OutlineWorkspacePage from './OutlineWorkspacePage.jsx'

function createWorkspacePayload() {
    return {
        book: {
            bookId: 'book-1',
            title: '霜原长夜',
            synopsis: '北境危机下的成长冒险。',
        },
        nodes: [
            { id: 'outline-1', type: 'outline', label: '总纲', depth: 0 },
            { id: 'plot-1', type: 'plot', label: '主线推进', parentId: 'outline-1', depth: 1 },
            { id: 'event-1', type: 'event', label: '候选事件', parentId: 'plot-1', depth: 2 },
            { id: 'scene-1', type: 'scene', label: '雪夜对峙', parentId: 'event-1', depth: 3 },
            { id: 'chapter-1', type: 'chapter', label: '第一章 雪夜来客', parentId: 'scene-1', depth: 4 },
            { id: 'setting-1', type: 'setting', label: '天穹城', depth: 0 },
            { id: 'canon-1', type: 'canon_entry', label: '正式设定', depth: 0 },
        ],
        selectedNodeId: 'plot-1',
        entities: {
            'plot-1': {
                entityId: 'plot-1',
                entityType: 'plot',
                title: '主线推进',
                body: '主角接到第一份危险委托。',
                version: 5,
                supportsRevisions: true,
                proposals: [
                    {
                        proposalId: 'proposal-1',
                        proposalType: 'event',
                        title: '候选事件 A',
                        summary: '守夜人带来失踪名单。',
                        status: 'pending',
                        canReview: true,
                    },
                    {
                        proposalId: 'proposal-2',
                        proposalType: 'event',
                        title: '候选事件 B',
                        summary: '雪原边境出现未知烽火。',
                        status: 'pending',
                        canReview: true,
                    },
                ],
                revisions: [
                    {
                        revisionId: 'plot-r5',
                        revisionNumber: 5,
                        label: 'r5',
                        createdAt: '2026-03-31T10:00:00Z',
                        authorLabel: 'Author',
                    },
                ],
            },
            'chapter-1': {
                entityId: 'chapter-1',
                entityType: 'chapter',
                title: '第一章 雪夜来客',
                body: '雪落在旧城墙上，主角第一次见到信使。',
                version: 7,
                supportsRevisions: true,
                proposals: [
                    {
                        proposalId: 'chapter-proposal-1',
                        proposalType: 'chapter_edit',
                        title: '章节修订草案',
                        summary: '强化章节收束',
                        status: 'pending',
                        canReview: true,
                    },
                ],
                revisions: [
                    {
                        revisionId: 'chapter-r7',
                        revisionNumber: 7,
                        label: 'r7',
                        createdAt: '2026-03-31T11:00:00Z',
                        authorLabel: 'Author',
                    },
                    {
                        revisionId: 'chapter-r3',
                        revisionNumber: 3,
                        label: 'r3',
                        createdAt: '2026-03-28T09:30:00Z',
                        authorLabel: 'Author',
                    },
                ],
            },
            'setting-1': {
                entityId: 'setting-1',
                entityType: 'setting',
                title: '天穹城',
                body: '北境最大的贸易中枢，夜间实行宵禁。',
                version: 4,
                supportsRevisions: true,
                proposals: [
                    {
                        proposalId: 'setting-proposal-1',
                        proposalType: 'setting',
                        title: '新增宵禁细则',
                        summary: '午夜后只有守夜司可以持灯通行。',
                        status: 'pending',
                        canReview: true,
                    },
                ],
                revisions: [
                    {
                        revisionId: 'setting-r4',
                        revisionNumber: 4,
                        label: 'r4',
                        createdAt: '2026-03-31T08:00:00Z',
                        authorLabel: 'Author',
                    },
                ],
            },
            'canon-1': {
                entityId: 'canon-1',
                entityType: 'canon_entry',
                title: '正式设定',
                body: '主角不会飞行。',
                version: 2,
                supportsRevisions: false,
                proposals: [],
                revisions: [],
            },
        },
        indexState: {
            indexStateId: 'index-1',
            generation: 3,
            status: 'failed',
            details: {
                reason: 'manual_retry',
                activeGeneration: null,
                publishedGeneration: 2,
                result: { artifact: 'codex-v2' },
            },
        },
    }
}

describe('OutlineWorkspacePage', () => {
    beforeEach(() => {
        fetchAuthoringWorkspace.mockResolvedValue(createWorkspacePayload())
        saveEntityDraft.mockResolvedValue({ ok: true })
        confirmProposal.mockResolvedValue({ ok: true })
        rejectProposal.mockResolvedValue({ ok: true })
        fetchRevisionDiff.mockResolvedValue({
            summary: '对比已加载',
            beforeLabel: 'r3',
            afterLabel: 'r7',
            diffText: `- 雪落在旧城墙上
+ 雪落在钟楼和旧城墙上`,
        })
        rollbackRevision.mockResolvedValue({ ok: true })
        markIndexStale.mockResolvedValue({ status: 'stale', generation: 4, details: { reason: 'manual_reset' } })
        rebuildIndex.mockResolvedValue({ status: 'fresh', generation: 4, details: { publishedGeneration: 4, result: { artifact: 'codex-v3' } } })
    })

    afterEach(() => {
        vi.clearAllMocks()
        cleanup()
    })

    it('navigates hierarchy nodes and switches between chapter and setting editors', async () => {
        render(<OutlineWorkspacePage />)

        expect(await screen.findByText('主线推进')).toBeTruthy()
        expect(screen.getByRole('button', { name: /第一章 雪夜来客/ })).toBeTruthy()
        expect(screen.getByRole('button', { name: /天穹城/ })).toBeTruthy()

        fireEvent.click(screen.getByRole('button', { name: /第一章 雪夜来客/ }))
        expect(await screen.findByText('章节编辑器')).toBeTruthy()
        expect(screen.getByDisplayValue('第一章 雪夜来客')).toBeTruthy()
        expect(screen.getByDisplayValue('雪落在旧城墙上，主角第一次见到信使。')).toBeTruthy()

        fireEvent.click(screen.getByRole('button', { name: /天穹城/ }))
        expect(await screen.findByText('设定编辑器')).toBeTruthy()
        expect(screen.getByDisplayValue('天穹城')).toBeTruthy()
        expect(screen.getByDisplayValue('北境最大的贸易中枢，夜间实行宵禁。')).toBeTruthy()
    })

    it('lets the author confirm or reject proposal previews from the review panel', async () => {
        render(<OutlineWorkspacePage />)
        await screen.findByText('主线推进')

        fireEvent.click(screen.getByRole('tab', { name: '提案评审' }))

        fireEvent.click(await screen.findByRole('button', { name: '确认 候选事件 A' }))
        await waitFor(() => {
            expect(confirmProposal).toHaveBeenCalledWith({
                bookId: 'book-1',
                entityId: 'plot-1',
                entityType: 'plot',
                proposalId: 'proposal-1',
            })
        })

        fireEvent.click(screen.getByRole('button', { name: '拒绝 候选事件 B' }))
        await waitFor(() => {
            expect(rejectProposal).toHaveBeenCalledWith({
                bookId: 'book-1',
                entityId: 'plot-1',
                entityType: 'plot',
                proposalId: 'proposal-2',
            })
        })
    })

    it('lets the author review a chapter edit proposal and browse canon entries in the workspace', async () => {
        render(<OutlineWorkspacePage />)
        await screen.findByText('主线推进')

        fireEvent.click(screen.getByRole('button', { name: /正式设定/ }))
        expect(await screen.findByDisplayValue('正式设定')).toBeTruthy()
        expect(screen.getByDisplayValue('主角不会飞行。')).toBeTruthy()

        fireEvent.click(screen.getByRole('button', { name: /第一章 雪夜来客/ }))
        fireEvent.click(screen.getByRole('tab', { name: '提案评审' }))
        fireEvent.click(await screen.findByRole('button', { name: '确认 章节修订草案' }))

        await waitFor(() => {
            expect(confirmProposal).toHaveBeenCalledWith({
                bookId: 'book-1',
                entityId: 'chapter-1',
                entityType: 'chapter',
                proposalId: 'chapter-proposal-1',
            })
        })
    })

    it('shows revision history, loads a diff, and triggers rollback for versioned entities', async () => {
        render(<OutlineWorkspacePage />)
        await screen.findByText('主线推进')

        fireEvent.click(screen.getByRole('button', { name: /第一章 雪夜来客/ }))
        fireEvent.click(screen.getByRole('tab', { name: '修订记录' }))

        fireEvent.click(await screen.findByRole('button', { name: '查看 r3 对比' }))
        await waitFor(() => {
            expect(fetchRevisionDiff).toHaveBeenCalledWith({
                bookId: 'book-1',
                entityId: 'chapter-1',
                entityType: 'chapter',
                fromRevision: 3,
                toRevision: 7,
            })
        })

        expect(await screen.findByText('对比已加载')).toBeTruthy()
        expect(screen.getByText(content => content.includes('- 雪落在旧城墙上'))).toBeTruthy()

        fireEvent.click(screen.getByRole('button', { name: '回滚到 r3' }))
        await waitFor(() => {
            expect(rollbackRevision).toHaveBeenCalledWith({
                bookId: 'book-1',
                entityId: 'chapter-1',
                entityType: 'chapter',
                targetRevision: 3,
                version: 7,
            })
        })
    })

    it('surfaces stale/conflict copy when save and approval actions are rejected', async () => {
        saveEntityDraft.mockRejectedValueOnce({
            errorCode: 'stale_revision',
            message: '当前内容已经被其他窗口更新，请刷新后重试。',
        })
        confirmProposal.mockRejectedValueOnce({
            errorCode: 'proposal_version_conflict',
            message: '提案基线已过期，请重新加载最新提案。',
        })

        render(<OutlineWorkspacePage />)
        await screen.findByText('主线推进')

        fireEvent.click(screen.getByRole('button', { name: /第一章 雪夜来客/ }))
        fireEvent.change(await screen.findByLabelText('章节正文'), {
            target: { value: '新的章节正文。' },
        })
        fireEvent.click(screen.getByRole('button', { name: '保存当前内容' }))

        expect(await screen.findByText('stale_revision: 当前内容已经被其他窗口更新，请刷新后重试。')).toBeTruthy()

        fireEvent.click(screen.getByRole('button', { name: /主线推进/ }))
        fireEvent.click(screen.getByRole('tab', { name: '提案评审' }))
        fireEvent.click(await screen.findByRole('button', { name: '确认 候选事件 A' }))

        expect(await screen.findByText('proposal_version_conflict: 提案基线已过期，请重新加载最新提案。')).toBeTruthy()
    })

    it('shows persisted index status and triggers reset/rebuild actions from the workspace', async () => {
        render(<OutlineWorkspacePage />)
        await screen.findByText('主线推进')

        expect(screen.getByText('failed')).toBeTruthy()
        expect(screen.getByText(/published_generation/i)).toBeTruthy()

        fireEvent.click(screen.getByRole('button', { name: '标记为 stale' }))
        await waitFor(() => {
            expect(markIndexStale).toHaveBeenCalledWith({
                bookId: 'book-1',
                reason: 'manual_reset',
            })
        })

        fireEvent.click(screen.getByRole('button', { name: '重建索引' }))
        await waitFor(() => {
            expect(rebuildIndex).toHaveBeenCalledWith({
                bookId: 'book-1',
            })
        })
    })
})
