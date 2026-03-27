const DEFAULT_WORKSPACE_ID = 'workspace-default'

let cachedAutoProjectRoot = ''
let pendingAutoProjectRootPromise = null

export function resolveOutlineProjectRoot(explicitProjectRoot) {
    if (typeof explicitProjectRoot === 'string' && explicitProjectRoot.trim()) {
        return explicitProjectRoot.trim()
    }
    if (typeof window === 'undefined') {
        return ''
    }
    const fromGlobal = typeof window.__WEBNOVEL_PROJECT_ROOT === 'string'
        ? window.__WEBNOVEL_PROJECT_ROOT.trim()
        : ''
    if (fromGlobal) {
        return fromGlobal
    }
    const fromQuery = new URLSearchParams(window.location.search).get('project_root')
    return typeof fromQuery === 'string' ? fromQuery.trim() : ''
}

export function createOutlineWorkspace({ workspaceId, projectRoot } = {}) {
    return {
        workspace_id: workspaceId || DEFAULT_WORKSPACE_ID,
        project_root: resolveOutlineProjectRoot(projectRoot),
    }
}

export function __resetOutlineProjectRootCacheForTests() {
    cachedAutoProjectRoot = ''
    pendingAutoProjectRootPromise = null
}

function createRequestUrl(pathname, query = {}) {
    const url = new URL(pathname, window.location.origin)
    Object.entries(query).forEach(([key, value]) => {
        if (value !== undefined && value !== null && `${value}`.trim() !== '') {
            url.searchParams.set(key, value)
        }
    })
    return url.toString()
}

function parsePayload(rawText) {
    if (!rawText) {
        return {}
    }
    try {
        return JSON.parse(rawText)
    } catch {
        return { message: rawText }
    }
}

function toApiError(response, payload) {
    const details = payload?.detail || payload
    const message = details?.message || `${response.status} ${response.statusText}`
    const error = new Error(message)
    error.status = response.status
    error.errorCode = details?.error_code || 'api_request_failed'
    error.details = details?.details || null
    return error
}

async function requestJSON(pathname, { method = 'GET', query, body, signal } = {}) {
    const response = await fetch(createRequestUrl(pathname, query), {
        method,
        headers: body ? { 'Content-Type': 'application/json' } : undefined,
        body: body ? JSON.stringify(body) : undefined,
        signal,
    })

    const payload = parsePayload(await response.text())
    if (!response.ok) {
        throw toApiError(response, payload)
    }
    return payload
}

async function resolveOutlineProjectRootForRequest(options = {}) {
    const explicit = resolveOutlineProjectRoot(options.projectRoot)
    if (explicit) {
        return explicit
    }

    if (cachedAutoProjectRoot) {
        return cachedAutoProjectRoot
    }

    if (!pendingAutoProjectRootPromise) {
        pendingAutoProjectRootPromise = requestJSON('/api/project/root', {
            signal: options.signal,
        })
            .then(payload => {
                const resolved = typeof payload?.project_root === 'string'
                    ? payload.project_root.trim()
                    : ''
                if (payload?.status === 'ok' && resolved) {
                    cachedAutoProjectRoot = resolved
                    if (typeof window !== 'undefined') {
                        window.__WEBNOVEL_PROJECT_ROOT = resolved
                    }
                    return resolved
                }
                return ''
            })
            .catch(() => '')
            .finally(() => {
                pendingAutoProjectRootPromise = null
            })
    }

    return pendingAutoProjectRootPromise
}

async function createOutlineWorkspaceForRequest(options = {}) {
    return {
        workspace_id: options.workspaceId || DEFAULT_WORKSPACE_ID,
        project_root: await resolveOutlineProjectRootForRequest(options),
    }
}

export function formatOutlineApiError(error, fallbackCode = 'api_request_failed') {
    const code = typeof error?.errorCode === 'string' && error.errorCode.trim()
        ? error.errorCode.trim()
        : fallbackCode
    const message = typeof error?.message === 'string' && error.message.trim()
        ? error.message.trim()
        : '请求失败，请稍后重试。'
    return `${code}: ${message}`
}

export async function fetchOutlineBundle(options = {}) {
    const workspace = await createOutlineWorkspaceForRequest(options)
    const payload = await requestJSON('/api/outlines', {
        query: {
            workspace_id: workspace.workspace_id,
            project_root: workspace.project_root,
        },
        signal: options.signal,
    })
    return {
        status: payload?.status || 'ok',
        total_outline: payload?.total_outline || '',
        detailed_outline: payload?.detailed_outline || '',
        splits: Array.isArray(payload?.splits) ? payload.splits : [],
        isMock: false,
    }
}

export async function previewOutlineSplit(options = {}) {
    const workspace = await createOutlineWorkspaceForRequest(options)
    const payload = {
        workspace,
        selection_start: Math.max(0, options.selectionStart ?? 0),
        selection_end: Math.max(0, options.selectionEnd ?? 0),
        selection_text: options.selectionText || '',
    }
    const result = await requestJSON('/api/outlines/split/preview', {
        method: 'POST',
        body: payload,
        signal: options.signal,
    })
    return {
        status: result?.status || 'ok',
        segments: Array.isArray(result?.segments) ? result.segments : [],
        anchors: Array.isArray(result?.anchors) ? result.anchors : [],
        isMock: false,
    }
}

export async function applyOutlineSplit(options = {}) {
    const workspace = await createOutlineWorkspaceForRequest(options)
    const payload = {
        workspace,
        selection_start: Math.max(0, options.selectionStart ?? 0),
        selection_end: Math.max(0, options.selectionEnd ?? 0),
        idempotency_key: options.idempotencyKey || '',
    }
    const result = await requestJSON('/api/outlines/split/apply', {
        method: 'POST',
        body: payload,
        signal: options.signal,
    })
    return {
        status: result?.status || 'ok',
        record: result?.record || null,
        idempotency: result?.idempotency || null,
        isMock: false,
    }
}

export async function fetchOutlineSplitHistory(options = {}) {
    const workspace = await createOutlineWorkspaceForRequest(options)
    const payload = await requestJSON('/api/outlines/splits', {
        query: {
            workspace_id: workspace.workspace_id,
            project_root: workspace.project_root,
            limit: options.limit ?? 100,
            offset: options.offset ?? 0,
        },
        signal: options.signal,
    })
    return {
        status: payload?.status || 'ok',
        items: Array.isArray(payload?.items) ? payload.items : [],
        total: Number.isFinite(payload?.total) ? payload.total : 0,
        isMock: false,
    }
}
