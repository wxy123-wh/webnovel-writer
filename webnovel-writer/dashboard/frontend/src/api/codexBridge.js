const DEFAULT_WORKSPACE_ID = 'workspace-default'

function resolveProjectRoot(explicitProjectRoot) {
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

function buildWorkspace({ workspaceId, projectRoot } = {}) {
    return {
        workspace_id: workspaceId || DEFAULT_WORKSPACE_ID,
        project_root: resolveProjectRoot(projectRoot),
    }
}

function createRequestUrl(pathname) {
    return new URL(pathname, window.location.origin).toString()
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

async function requestJSON(pathname, { body, signal } = {}) {
    const response = await fetch(createRequestUrl(pathname), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body || {}),
        signal,
    })

    const payload = parsePayload(await response.text())
    if (!response.ok) {
        throw toApiError(response, payload)
    }
    return payload
}

export function formatCodexBridgeError(error, fallbackCode = 'api_request_failed') {
    const code = typeof error?.errorCode === 'string' && error.errorCode.trim()
        ? error.errorCode.trim()
        : fallbackCode
    const message = typeof error?.message === 'string' && error.message.trim()
        ? error.message.trim()
        : '请求失败，请稍后重试。'
    return `${code}: ${message}`
}

export async function openCodexSplitDialog(options = {}) {
    const workspace = buildWorkspace(options)
    const payload = await requestJSON('/api/codex/split-dialog/open', {
        body: {
            workspace,
            selection_start: Math.max(0, options.selectionStart ?? 0),
            selection_end: Math.max(0, options.selectionEnd ?? 0),
            selection_text: options.selectionText || '',
        },
        signal: options.signal,
    })
    return {
        status: payload?.status || 'ok',
        launched: Boolean(payload?.launched),
        message: payload?.message || '',
        prompt_file: payload?.prompt_file || '',
    }
}

export async function openCodexFileEditDialog(options = {}) {
    const workspace = buildWorkspace(options)
    const payload = await requestJSON('/api/codex/file-edit/open', {
        body: {
            workspace,
            file_path: options.filePath || '',
            selection_start: Math.max(0, options.selectionStart ?? 0),
            selection_end: Math.max(0, options.selectionEnd ?? 0),
            selection_text: options.selectionText || '',
            instruction: options.instruction || '',
            source_id: options.sourceId || '',
        },
        signal: options.signal,
    })
    return {
        status: payload?.status || 'ok',
        launched: Boolean(payload?.launched),
        message: payload?.message || '',
        prompt_file: payload?.prompt_file || '',
        target_file: payload?.target_file || '',
    }
}
