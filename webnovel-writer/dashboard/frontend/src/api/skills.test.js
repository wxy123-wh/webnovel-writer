import test from 'node:test'
import assert from 'node:assert/strict'

const originalFetch = globalThis.fetch
const originalWindow = globalThis.window

function installMockWindow() {
    const store = new Map()
    globalThis.window = {
        location: { origin: 'http://localhost:5173' },
        localStorage: {
            getItem(key) {
                return store.has(key) ? store.get(key) : null
            },
            setItem(key, value) {
                store.set(key, String(value))
            },
            removeItem(key) {
                store.delete(key)
            },
        },
    }
}

function restoreGlobals() {
    globalThis.fetch = originalFetch
    if (originalWindow === undefined) {
        delete globalThis.window
        return
    }
    globalThis.window = originalWindow
}

async function loadSkillsModule() {
    return import(`./skills.js?test_case=${Date.now()}_${Math.random().toString(16).slice(2)}`)
}

test('skills api classifies network errors', async () => {
    installMockWindow()
    globalThis.fetch = async () => {
        throw new Error('socket hang up')
    }
    const module = await loadSkillsModule()

    try {
        await assert.rejects(
            () => module.listSkills(),
            error => {
                assert.equal(error.errorCode, 'skills_network_error')
                assert.equal(error.errorType, 'network')
                assert.equal(module.classifySkillsError(error), 'network')
                return true
            },
        )
    } finally {
        restoreGlobals()
    }
})

test('skills api classifies permission errors', async () => {
    installMockWindow()
    globalThis.fetch = async () =>
        new Response(JSON.stringify({ message: 'Workspace access denied.', error_code: 'workspace_mismatch' }), {
            status: 403,
            statusText: 'Forbidden',
            headers: { 'Content-Type': 'application/json' },
        })
    const module = await loadSkillsModule()

    try {
        await assert.rejects(
            () => module.listSkills(),
            error => {
                assert.equal(error.status, 403)
                assert.equal(error.errorType, 'permission')
                assert.equal(module.classifySkillsError(error), 'permission')
                return true
            },
        )
    } finally {
        restoreGlobals()
    }
})

test('skills api classifies conflict errors', async () => {
    installMockWindow()
    globalThis.fetch = async () =>
        new Response(JSON.stringify({ message: 'Skill id already exists.', error_code: 'skill_id_conflict' }), {
            status: 409,
            statusText: 'Conflict',
            headers: { 'Content-Type': 'application/json' },
        })
    const module = await loadSkillsModule()

    try {
        await assert.rejects(
            () =>
                module.createSkill({
                    id: 'scene.splitter',
                    name: 'Scene Splitter',
                    description: '',
                    enabled: true,
                }),
            error => {
                assert.equal(error.status, 409)
                assert.equal(error.errorCode, 'skill_id_conflict')
                assert.equal(error.errorType, 'conflict')
                assert.equal(module.classifySkillsError(error), 'conflict')
                return true
            },
        )
    } finally {
        restoreGlobals()
    }
})
