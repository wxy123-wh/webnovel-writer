import test from 'node:test'
import assert from 'node:assert/strict'

const originalFetch = globalThis.fetch
const originalWindow = globalThis.window

function mockWindow() {
    globalThis.window = {
        location: {
            origin: 'http://localhost:5173',
            search: '',
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
    return import(`./settings.js?test_case=${Date.now()}_${Math.random().toString(16).slice(2)}`)
}

test('fetchProviderSettings normalizes provider payload without exposing secrets', async () => {
    mockWindow()
    globalThis.fetch = async url => {
        assert.match(String(url), /\/api\/settings\/provider$/)
        return mockJsonResponse(200, {
            provider: 'openai',
            base_url: 'https://api.openai.com/v1',
            model: 'gpt-4.1-mini',
            api_key_configured: 1,
            configured: true,
            api_key: 'should-not-be-used',
        })
    }

    const module = await loadModule()
    try {
        const data = await module.fetchProviderSettings()
        assert.deepEqual(data, {
            provider: 'openai',
            base_url: 'https://api.openai.com/v1',
            model: 'gpt-4.1-mini',
            api_key_configured: true,
            configured: true,
        })
    } finally {
        restoreFetch()
        restoreWindow()
    }
})

test('updateProviderSettings sends normalized payload and returns normalized response', async () => {
    mockWindow()
    globalThis.fetch = async (url, options) => {
        assert.match(String(url), /\/api\/settings\/provider$/)
        assert.equal(options.method, 'PATCH')
        assert.equal(options.headers['Content-Type'], 'application/json')
        assert.deepEqual(JSON.parse(options.body), {
            provider: 'openrouter',
            base_url: 'https://openrouter.ai/api/v1',
            model: 'openai/gpt-4.1-mini',
            api_key: 'sk-test',
            clear_api_key: false,
        })
        return mockJsonResponse(200, {
            provider: 'openrouter',
            base_url: 'https://openrouter.ai/api/v1',
            model: 'openai/gpt-4.1-mini',
            api_key_configured: true,
            configured: true,
        })
    }

    const module = await loadModule()
    try {
        const data = await module.updateProviderSettings({
            provider: ' openrouter ',
            base_url: 'https://openrouter.ai/api/v1 ',
            model: ' openai/gpt-4.1-mini ',
            api_key: 'sk-test',
            clear_api_key: false,
        })
        assert.deepEqual(data, {
            provider: 'openrouter',
            base_url: 'https://openrouter.ai/api/v1',
            model: 'openai/gpt-4.1-mini',
            api_key_configured: true,
            configured: true,
        })
    } finally {
        restoreFetch()
        restoreWindow()
    }
})
