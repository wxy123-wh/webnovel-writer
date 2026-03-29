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

function restoreGlobals() {
    globalThis.fetch = originalFetch
    globalThis.window = originalWindow
}

async function loadModule() {
    return import(`./codexBridge.js?test=${Date.now()}-${Math.random()}`)
}

test('codex bridge sends expected payload for file-edit launch', async () => {
    installWindowStub()
    const calls = []
    globalThis.fetch = async (input, init) => {
        calls.push({ url: new URL(input.toString()), init })
        return new Response(
            JSON.stringify({
                status: 'ok',
                launched: true,
                message: 'started',
                prompt_file: 'D:/demo/.webnovel/tmp/codex-file-edit-1.md',
                target_file: '设定集/角色.md',
            }),
            {
                status: 200,
                headers: { 'Content-Type': 'application/json' },
            },
        )
    }
    const module = await loadModule()

    try {
        const result = await module.openCodexFileEditDialog({
            workspaceId: 'ws-1',
            projectRoot: 'D:/demo',
            filePath: '设定集/角色.md',
            selectionStart: 2,
            selectionEnd: 10,
            selectionText: '林昭(角色)',
            instruction: '润色并增强人物目标冲突',
            sourceId: 'settings.editor.textarea',
        })

        assert.equal(result.status, 'ok')
        assert.equal(result.launched, true)
        assert.equal(calls.length, 1)
        assert.equal(calls[0].url.pathname, '/api/codex/file-edit/open')
        assert.equal(calls[0].init.method, 'POST')

        const body = JSON.parse(calls[0].init.body)
        assert.deepEqual(body.workspace, {
            workspace_id: 'ws-1',
            project_root: 'D:/demo',
        })
        assert.equal(body.file_path, '设定集/角色.md')
        assert.equal(body.selection_start, 2)
        assert.equal(body.selection_end, 10)
        assert.equal(body.selection_text, '林昭(角色)')
        assert.equal(body.source_id, 'settings.editor.textarea')
    } finally {
        restoreGlobals()
    }
})

test('codex bridge exposes structured api error metadata', async () => {
    installWindowStub()
    globalThis.fetch = async () =>
        new Response(
            JSON.stringify({
                detail: {
                    error_code: 'CODEX_FILE_EDIT_SELECTION_INVALID',
                    message: '请先选中有效文本后再启动 Codex 文件编辑。',
                    details: { selection_start: 8, selection_end: 8 },
                },
            }),
            {
                status: 400,
                headers: { 'Content-Type': 'application/json' },
            },
        )

    const module = await loadModule()

    try {
        await assert.rejects(
            module.openCodexFileEditDialog({
                filePath: '设定集/角色.md',
                selectionStart: 8,
                selectionEnd: 8,
                selectionText: '',
            }),
            error => {
                assert.equal(error.status, 400)
                assert.equal(error.errorCode, 'CODEX_FILE_EDIT_SELECTION_INVALID')
                assert.deepEqual(error.details, { selection_start: 8, selection_end: 8 })
                assert.equal(
                    module.formatCodexBridgeError(error),
                    'CODEX_FILE_EDIT_SELECTION_INVALID: 请先选中有效文本后再启动 Codex 文件编辑。',
                )
                return true
            },
        )
    } finally {
        restoreGlobals()
    }
})
