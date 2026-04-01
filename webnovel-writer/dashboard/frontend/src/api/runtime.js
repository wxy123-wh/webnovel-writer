import { requestJSON } from './http.js'

function normalizeGenerationProfile(generation) {
    if (!generation || typeof generation !== 'object') {
        return {
            provider: '',
            configured: false,
            skill_draft_available: false,
            api_key_configured: false,
            model: '',
            base_url: '',
        }
    }

    return {
        provider: typeof generation.provider === 'string' ? generation.provider : '',
        configured: Boolean(generation.configured),
        skill_draft_available: Boolean(generation.skill_draft_available ?? generation.configured),
        api_key_configured: Boolean(generation.api_key_configured),
        model: typeof generation.model === 'string' ? generation.model : '',
        base_url: typeof generation.base_url === 'string' ? generation.base_url : '',
    }
}

export async function fetchRuntimeProfile({ signal } = {}) {
    const payload = await requestJSON('/api/runtime/profile', {
        signal,
        catchNetwork: true,
        networkMessage: '无法连接到运行时服务，请确认后端已启动。',
    })
    return {
        ...payload,
        generation: normalizeGenerationProfile(payload?.generation),
    }
}
