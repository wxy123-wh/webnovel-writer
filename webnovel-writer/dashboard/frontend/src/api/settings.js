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

function createRequestUrl(pathname, query = {}) {
    const url = new URL(pathname, window.location.origin)
    Object.entries(query).forEach(([key, value]) => {
        if (value !== undefined && value !== null && `${value}`.trim() !== '') {
            url.searchParams.set(key, value)
        }
    })
    return url.toString()
}

async function requestJSON(pathname, { method = 'GET', query, body, signal } = {}) {
    const response = await fetch(createRequestUrl(pathname, query), {
        method,
        headers: body ? { 'Content-Type': 'application/json' } : undefined,
        body: body ? JSON.stringify(body) : undefined,
        signal,
    })

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
        const errorCode = details?.error_code || 'api_request_failed'
        const message = details?.message || `${response.status} ${response.statusText}`
        const error = new Error(message)
        error.status = response.status
        error.errorCode = errorCode
        error.details = details?.details || null
        throw error
    }

    return payload
}

function normalizeDictionaryItem(item) {
    return {
        id: item?.id || '',
        term: item?.term || '',
        type: item?.type || 'concept',
        attrs: item?.attrs && typeof item.attrs === 'object' ? item.attrs : {},
        source_file: item?.source_file || item?.sourceFile || '',
        source_span: item?.source_span || item?.sourceSpan || '0-0',
        status: item?.status || 'pending',
        fingerprint: item?.fingerprint || '',
        conflict_id: item?.conflict_id || item?.conflictId || '',
    }
}

export function isMockResponse(response) {
    return Boolean(response?.isMock)
}

export function getConflictIdFromEntry(entry) {
    if (!entry || typeof entry !== 'object') {
        return ''
    }
    if (typeof entry.conflict_id === 'string' && entry.conflict_id.trim()) {
        return entry.conflict_id.trim()
    }
    if (typeof entry.id === 'string' && entry.id.startsWith('conf-')) {
        return entry.id
    }
    return ''
}

// M1 阶段：仅保留只读查询函数
// 写操作（writeSettingsFile、extractSettingDictionary、resolveDictionaryConflict）已删除
// 这些操作已移至 CLI 命令 `webnovel codex`

export async function fetchSettingsFileTree(options = {}) {
    const workspace = buildWorkspace(options)
    const payload = await requestJSON('/api/settings/files/tree', {
        query: {
            workspace_id: workspace.workspace_id,
            project_root: workspace.project_root,
        },
        signal: options.signal,
    })
    return {
        status: payload?.status || 'ok',
        nodes: Array.isArray(payload?.nodes) ? payload.nodes : [],
    }
}

export async function readSettingsFile(options = {}) {
    const workspace = buildWorkspace(options)
    const filePath = typeof options.path === 'string' ? options.path.trim() : ''
    if (!filePath) throw new Error('文件路径不能为空')
    const payload = await requestJSON('/api/settings/files/read', {
        query: {
            workspace_id: workspace.workspace_id,
            project_root: workspace.project_root,
            path: filePath,
        },
        signal: options.signal,
    })
    return {
        status: payload?.status || 'ok',
        path: payload?.path || filePath,
        content: payload?.content || '',
    }
}

export async function listSettingDictionary(options = {}) {
    const workspace = buildWorkspace(options)
    const payload = await requestJSON('/api/settings/dictionary', {
        query: {
            workspace_id: workspace.workspace_id,
            project_root: workspace.project_root,
            term: options.term,
            type: options.type,
            status: options.status,
            limit: options.limit ?? 100,
            offset: options.offset ?? 0,
        },
        signal: options.signal,
    })
    const items = Array.isArray(payload?.items) ? payload.items.map(normalizeDictionaryItem) : []
    return {
        status: payload?.status || 'ok',
        items,
        total: Number.isFinite(payload?.total) ? payload.total : items.length,
    }
}
