import test from 'node:test'
import assert from 'node:assert/strict'

const originalFetch = globalThis.fetch
const originalWindow = globalThis.window

function mockWindow() {
    globalThis.window = {
        location: {
            origin: 'http://localhost:5173',
        },
    }
}

function restoreWindow() {
    if (originalWindow === undefined) {
        delete globalThis.window
        return
    }
    globalThis.window = originalWindow
}

function mockJsonResponse(status, payload, statusText = 'OK') {
    return {
        ok: status >= 200 && status < 300,
        status,
        statusText,
        text: async () => JSON.stringify(payload),
    }
}

function restoreFetch() {
    globalThis.fetch = originalFetch
}

async function loadModule() {
    return import(`./authoring.js?test_case=${Date.now()}_${Math.random().toString(16).slice(2)}`)
}

test('fetchAuthoringWorkspace normalizes workspace snapshot, canon entries, proposals, and index state', async () => {
    mockWindow()
    const requests = []
    globalThis.fetch = async url => {
        requests.push(String(url))
        if (String(url).endsWith('/api/hierarchy/workspace')) {
            return mockJsonResponse(200, {
                book: { book_id: 'book-1', title: '霜原长夜', synopsis: '简介', version: 2 },
                outlines: [{ outline_id: 'outline-1', book_id: 'book-1', title: '总纲', body: '总纲正文', metadata: {}, position: 0, version: 3, created_at: 'a', updated_at: 'b' }],
                plots: [{ plot_id: 'plot-1', book_id: 'book-1', outline_id: 'outline-1', title: '主线', body: '主线正文', metadata: {}, position: 0, version: 4, created_at: 'a', updated_at: 'b' }],
                events: [],
                scenes: [],
                chapters: [{ chapter_id: 'chapter-1', book_id: 'book-1', scene_id: 'scene-1', title: '第一章', body: '章节正文', metadata: {}, position: 0, version: 7, created_at: 'a', updated_at: 'b' }],
                settings: [{ setting_id: 'setting-1', book_id: 'book-1', title: '天穹城', body: '设定正文', metadata: {}, position: 0, version: 5, created_at: 'a', updated_at: 'b' }],
                canon_entries: [{ canon_id: 'canon-1', book_id: 'book-1', title: '已采纳设定', body: 'canon', metadata: {}, position: 0, version: 1, created_at: 'a', updated_at: 'b' }],
                proposals: [
                    {
                        proposal_id: 'proposal-1',
                        proposal_type: 'plot_split',
                        target_type: 'event',
                        status: 'pending',
                        payload: {
                            kind: 'structural_children',
                            parent_type: 'plot',
                            parent_id: 'plot-1',
                            child_type: 'event',
                            proposed_children: [{ title: '候选事件', body: '草案', metadata: {} }],
                        },
                    },
                    {
                        proposal_id: 'proposal-2',
                        proposal_type: 'chapter_edit',
                        target_type: 'chapter',
                        status: 'pending',
                        payload: {
                            kind: 'chapter_edit',
                            chapter_id: 'chapter-1',
                            summary: '强化章节收束',
                            proposed_update: { title: '第一章（修订）', body: '修订章节正文', metadata: {} },
                        },
                    },
                ],
                index_state: {
                    index_state_id: 'index-1',
                    book_id: 'book-1',
                    generation: 3,
                    status: 'failed',
                    source_fingerprint: 'fp-3',
                    details: { reason: 'manual_retry', active_generation: null, published_generation: 2 },
                    version: 1,
                    created_at: 'a',
                    updated_at: 'b',
                },
            })
        }
        if (String(url).includes('/revisions/outline/outline-1')) {
            return mockJsonResponse(200, [{ revision_id: 'rev-1', revision_number: 1, entity_version: 3, snapshot: {}, created_at: 'a' }])
        }
        if (String(url).includes('/revisions/plot/plot-1')) {
            return mockJsonResponse(200, [{ revision_id: 'rev-2', revision_number: 2, entity_version: 4, snapshot: {}, created_at: 'a' }])
        }
        if (String(url).includes('/revisions/chapter/chapter-1')) {
            return mockJsonResponse(200, [{ revision_id: 'rev-3', revision_number: 3, entity_version: 7, snapshot: {}, created_at: 'a' }])
        }
        if (String(url).includes('/revisions/setting/setting-1')) {
            return mockJsonResponse(200, [{ revision_id: 'rev-4', revision_number: 4, entity_version: 5, snapshot: {}, created_at: 'a' }])
        }
        return mockJsonResponse(200, [])
    }

    const module = await loadModule()
    try {
        const workspace = await module.fetchAuthoringWorkspace()
        assert.equal(workspace.book.bookId, 'book-1')
        assert.equal(workspace.nodes.length, 5)
        assert.equal(workspace.entities['plot-1'].proposals[0].proposalId, 'proposal-1')
        assert.equal(workspace.entities['chapter-1'].proposals[0].proposalId, 'proposal-2')
        assert.equal(workspace.entities['chapter-1'].proposals[0].canReview, true)
        assert.equal(workspace.entities['canon-1'].entityType, 'canon_entry')
        assert.equal(workspace.indexState.status, 'failed')
        assert.equal(workspace.indexState.details.publishedGeneration, 2)
        assert.equal(workspace.entities['plot-1'].revisions[0].revisionNumber, 2)
        assert.equal(workspace.entities['chapter-1'].supportsRevisions, true)
        assert.ok(requests.some(url => url.endsWith('/api/hierarchy/workspace')))
    } finally {
        restoreFetch()
        restoreWindow()
    }
})

test('saveEntityDraft and rollbackRevision send optimistic-lock payloads', async () => {
    mockWindow()
    const seen = []
    globalThis.fetch = async (url, options = {}) => {
        seen.push({ url: String(url), options })
        return mockJsonResponse(200, { ok: true })
    }

    const module = await loadModule()
    try {
        await module.saveEntityDraft({
            bookId: 'book-1',
            entityType: 'chapter',
            entityId: 'chapter-1',
            version: 7,
            title: '第一章',
            body: '更新后的章节正文',
            metadata: { tone: 'cold' },
        })
        await module.rollbackRevision({
            bookId: 'book-1',
            entityType: 'chapter',
            entityId: 'chapter-1',
            targetRevision: 3,
            version: 7,
        })

        assert.equal(seen[0].options.method, 'PATCH')
        assert.deepEqual(JSON.parse(seen[0].options.body), {
            expected_version: 7,
            title: '第一章',
            body: '更新后的章节正文',
            metadata: { tone: 'cold' },
        })
        assert.equal(seen[1].options.method, 'POST')
        assert.deepEqual(JSON.parse(seen[1].options.body), {
            target_revision: 3,
            expected_version: 7,
        })
    } finally {
        restoreFetch()
        restoreWindow()
    }
})

test('markIndexStale and rebuildIndex send the expected requests', async () => {
    mockWindow()
    const seen = []
    globalThis.fetch = async (url, options = {}) => {
        seen.push({ url: String(url), options })
        return mockJsonResponse(200, { status: 'fresh', generation: 4, details: { published_generation: 4 } })
    }

    const module = await loadModule()
    try {
        await module.markIndexStale({ bookId: 'book-1', reason: 'manual_reset' })
        await module.rebuildIndex({ bookId: 'book-1' })

        assert.equal(seen[0].options.method, 'POST')
        assert.match(seen[0].url, /\/api\/hierarchy\/books\/book-1\/index\/mark-stale$/)
        assert.deepEqual(JSON.parse(seen[0].options.body), { reason: 'manual_reset' })
        assert.equal(seen[1].options.method, 'POST')
        assert.match(seen[1].url, /\/api\/hierarchy\/books\/book-1\/index\/rebuild$/)
    } finally {
        restoreFetch()
        restoreWindow()
    }
})
