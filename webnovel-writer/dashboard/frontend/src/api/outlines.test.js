import test from 'node:test'
import assert from 'node:assert/strict'

const originalFetch = globalThis.fetch
const originalWindow = globalThis.window

function installWindowStub() {
    globalThis.window = {
        location: {
            origin: 'http://localhost:4173',
            search: '',
        },
    }
}

function installFailingFetch() {
    globalThis.fetch = async () => {
        throw new Error('network down')
    }
}

function restoreGlobals() {
    globalThis.fetch = originalFetch
    globalThis.window = originalWindow
}

async function loadOutlinesModule() {
    return import(`./outlines.js?test=${Date.now()}-${Math.random()}`)
}

test('outlines api throws on request failure without mock fallback', async () => {
    installWindowStub()
    installFailingFetch()
    const module = await loadOutlinesModule()

    try {
        await assert.rejects(
            module.fetchOutlineBundle(),
            /network down/,
        )
        await assert.rejects(
            module.previewOutlineSplit({
                selectionStart: 0,
                selectionEnd: 22,
                selectionText: '林昭在星门废墟发现残缺星图。\n\n白莲宗派人追查星图去向。',
            }),
            /network down/,
        )
        await assert.rejects(
            module.applyOutlineSplit({
                selectionStart: 0,
                selectionEnd: 22,
                idempotencyKey: 'same-key',
            }),
            /network down/,
        )
        await assert.rejects(
            module.fetchOutlineSplitHistory({ limit: 100, offset: 0 }),
            /network down/,
        )
    } finally {
        restoreGlobals()
    }
})

test('outlines api exposes structured api error metadata', async () => {
    installWindowStub()
    globalThis.fetch = async () =>
        new Response(
            JSON.stringify({
                detail: {
                    error_code: 'OUTLINE_INVALID_SELECTION_RANGE',
                    message: 'selection_end must be greater than selection_start',
                    details: { selection_start: 8, selection_end: 8 },
                },
            }),
            {
                status: 400,
                statusText: 'Bad Request',
                headers: { 'Content-Type': 'application/json' },
            },
        )
    const module = await loadOutlinesModule()

    try {
        await assert.rejects(
            module.previewOutlineSplit({
                selectionStart: 8,
                selectionEnd: 8,
                selectionText: '',
            }),
            error => {
                assert.equal(error.errorCode, 'OUTLINE_INVALID_SELECTION_RANGE')
                assert.equal(error.status, 400)
                assert.deepEqual(error.details, { selection_start: 8, selection_end: 8 })
                assert.equal(
                    module.formatOutlineApiError(error),
                    'OUTLINE_INVALID_SELECTION_RANGE: selection_end must be greater than selection_start',
                )
                return true
            },
        )
    } finally {
        restoreGlobals()
    }
})

test('outlines api auto-resolves project_root from /api/project/root and caches it', async () => {
    installWindowStub()

    const calls = []
    globalThis.fetch = async input => {
        const url = new URL(input.toString())
        calls.push(url)

        if (url.pathname === '/api/project/root') {
            return new Response(
                JSON.stringify({
                    status: 'ok',
                    project_root: 'D:/code/webnovel-project',
                }),
                {
                    status: 200,
                    headers: { 'Content-Type': 'application/json' },
                },
            )
        }

        if (url.pathname === '/api/outlines') {
            return new Response(
                JSON.stringify({
                    status: 'ok',
                    total_outline: '总纲',
                    detailed_outline: '细纲',
                    splits: [],
                }),
                {
                    status: 200,
                    headers: { 'Content-Type': 'application/json' },
                },
            )
        }

        if (url.pathname === '/api/outlines/splits') {
            return new Response(
                JSON.stringify({
                    status: 'ok',
                    items: [],
                    total: 0,
                }),
                {
                    status: 200,
                    headers: { 'Content-Type': 'application/json' },
                },
            )
        }

        return new Response('unexpected request', { status: 500 })
    }

    const module = await loadOutlinesModule()

    try {
        module.__resetOutlineProjectRootCacheForTests()

        await module.fetchOutlineBundle()
        await module.fetchOutlineSplitHistory({ limit: 20, offset: 0 })

        assert.equal(calls[0].pathname, '/api/project/root')
        assert.equal(calls[1].pathname, '/api/outlines')
        assert.equal(calls[1].searchParams.get('workspace_id'), 'workspace-default')
        assert.equal(calls[1].searchParams.get('project_root'), 'D:/code/webnovel-project')
        assert.equal(calls[2].pathname, '/api/outlines/splits')
        assert.equal(calls[2].searchParams.get('project_root'), 'D:/code/webnovel-project')
        assert.equal(calls.filter(url => url.pathname === '/api/project/root').length, 1)
        assert.equal(window.__WEBNOVEL_PROJECT_ROOT, 'D:/code/webnovel-project')
    } finally {
        restoreGlobals()
    }
})
