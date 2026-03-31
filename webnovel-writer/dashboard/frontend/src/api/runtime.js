function createRequestUrl(pathname) {
    return new URL(pathname, window.location.origin).toString()
}

async function requestJSON(pathname, { signal } = {}) {
    let response
    try {
        response = await fetch(createRequestUrl(pathname), { signal })
    } catch {
        throw new Error('无法连接到运行时服务，请确认后端已启动。')
    }

    const rawText = await response.text()
    let payload = {}
    if (rawText) {
        try {
            payload = JSON.parse(rawText)
        } catch {
            payload = { message: rawText }
        }
    }

    if (!response.ok) {
        const details = payload?.detail || payload
        const message = details?.message || `${response.status} ${response.statusText}`
        const error = new Error(message)
        error.status = response.status
        error.details = details?.details || null
        throw error
    }

    return payload
}

function normalizeGenerationProfile(generation) {
    if (!generation || typeof generation !== 'object') {
        return {
            provider: '',
            configured: false,
            api_key_configured: false,
            model: '',
            base_url: '',
        }
    }

    return {
        provider: typeof generation.provider === 'string' ? generation.provider : '',
        configured: Boolean(generation.configured),
        api_key_configured: Boolean(generation.api_key_configured),
        model: typeof generation.model === 'string' ? generation.model : '',
        base_url: typeof generation.base_url === 'string' ? generation.base_url : '',
    }
}

export async function fetchRuntimeProfile({ signal } = {}) {
    const payload = await requestJSON('/api/runtime/profile', { signal })
    return {
        ...payload,
        generation: normalizeGenerationProfile(payload?.generation),
    }
}
