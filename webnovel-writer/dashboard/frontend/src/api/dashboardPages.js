import { requestJSON as baseRequestJSON } from './http.js'

function toInt(value, fallback = 0) {
    const num = Number(value)
    return Number.isFinite(num) ? Math.trunc(num) : fallback
}

function toFloat(value, fallback = 0) {
    const num = Number(value)
    return Number.isFinite(num) ? num : fallback
}

function toNullableFloat(value) {
    if (value === null || value === undefined || value === '') {
        return null
    }
    const num = Number(value)
    return Number.isFinite(num) ? num : null
}

function parseJSONSafely(value, fallback) {
    if (value && typeof value === 'object') {
        return value
    }
    if (typeof value !== 'string' || !value.trim()) {
        return fallback
    }
    try {
        return JSON.parse(value)
    } catch {
        return fallback
    }
}

function extractErrorDetails(payload) {
    if (!payload || typeof payload !== 'object') {
        return null
    }
    if (payload.details !== undefined) {
        return payload.details
    }
    if (payload.detail !== undefined) {
        return payload.detail
    }
    return payload
}

function extractErrorMessage(payload, fallback) {
    if (!payload || typeof payload !== 'object') {
        return fallback
    }
    if (typeof payload.message === 'string' && payload.message.trim()) {
        return payload.message
    }
    if (typeof payload.detail === 'string' && payload.detail.trim()) {
        return payload.detail
    }
    return fallback
}

function extractErrorCode(payload, statusCode) {
    if (!payload || typeof payload !== 'object') {
        return `http_${statusCode}`
    }
    const code = payload.error_code || payload.errorCode
    if (typeof code === 'string' && code.trim()) {
        return code
    }
    return `http_${statusCode}`
}

function normalizeHookDistribution(distribution) {
    const safe = distribution && typeof distribution === 'object' ? distribution : {}
    return {
        strong: toInt(safe.strong, 0),
        medium: toInt(safe.medium, 0),
        weak: toInt(safe.weak, 0),
        unknown: toInt(safe.unknown, 0),
    }
}

function normalizeTreeNode(node) {
    const isDirectory = node?.type === 'dir'
    const children = Array.isArray(node?.children)
        ? node.children.map(normalizeTreeNode)
        : []
    return {
        name: node?.name || '',
        type: isDirectory ? 'dir' : 'file',
        path: node?.path || '',
        size: toInt(node?.size, 0),
        children,
    }
}

function normalizeFolderMap(payload) {
    const safe = payload && typeof payload === 'object' ? payload : {}
    const folders = Object.keys(safe).map(name => ({
        name,
        nodes: Array.isArray(safe[name]) ? safe[name].map(normalizeTreeNode) : [],
    }))
    return {
        raw: safe,
        folders,
    }
}

export class DashboardApiError extends Error {
    constructor(
        message,
        { status = 0, errorCode = 'dashboard_api_error', details = null } = {},
    ) {
        super(message)
        this.name = 'DashboardApiError'
        this.status = status
        this.errorCode = errorCode
        this.details = details
    }
}

export function formatApiError(error, fallback = '请求失败，请稍后重试') {
    if (!error) return fallback
    const message = typeof error.message === 'string' && error.message.trim()
        ? error.message
        : fallback
    const code = error.errorCode ? ` (${error.errorCode})` : ''
    return `${message}${code}`
}

function toDashboardApiError(error) {
    if (error instanceof DashboardApiError) return error
    return new DashboardApiError(error?.message || '请求失败', {
        status: error?.status || 0,
        errorCode: error?.errorCode || 'dashboard_api_error',
        details: error?.details || null,
    })
}

export const requestJSON = (path, options = {}) => (
    baseRequestJSON(path, options).catch(error => {
        throw toDashboardApiError(error)
    })
)

export async function fetchDashboardOverview(options = {}) {
    const payload = await requestJSON('/api/dashboard/overview', {
        signal: options.signal,
    })

    return {
        status: payload?.status || 'ok',
        counts: {
            entities: toInt(payload?.counts?.entities, 0),
            relationships: toInt(payload?.counts?.relationships, 0),
            chapters: toInt(payload?.counts?.chapters, 0),
            files: toInt(payload?.counts?.files, 0),
        },
        readingPower: {
            totalRows: toInt(payload?.reading_power?.total_rows, 0),
            latestChapter: payload?.reading_power?.latest_chapter ?? null,
            transitionChapters: toInt(payload?.reading_power?.transition_chapters, 0),
            avgDebtBalance: toNullableFloat(payload?.reading_power?.avg_debt_balance),
            hookStrengthDistribution: normalizeHookDistribution(
                payload?.reading_power?.hook_strength_distribution,
            ),
        },
    }
}

export async function fetchEntities(options = {}) {
    const payload = await requestJSON('/api/entities', {
        query: {
            type: options.type,
            include_archived: options.includeArchived,
        },
        signal: options.signal,
    })
    return Array.isArray(payload) ? payload : []
}

export async function fetchChapters(options = {}) {
    const payload = await requestJSON('/api/chapters', {
        signal: options.signal,
    })
    return Array.isArray(payload) ? payload : []
}

export async function fetchFilesTree(options = {}) {
    const payload = await requestJSON('/api/files/tree', {
        signal: options.signal,
    })
    return normalizeFolderMap(payload)
}

export async function readFileContent(path, options = {}) {
    const safePath = typeof path === 'string' ? path.trim() : ''
    if (!safePath) {
        const error = new DashboardApiError('文件路径不能为空。', {
            status: 400,
            errorCode: 'file_path_required',
        })
        throw error
    }

    const payload = await requestJSON('/api/files/read', {
        query: { path: safePath },
        signal: options.signal,
    })

    return {
        path: payload?.path || safePath,
        content: typeof payload?.content === 'string' ? payload.content : '',
    }
}

export async function fetchReadingPower(options = {}) {
    const payload = await requestJSON('/api/reading-power', {
        query: { limit: options.limit ?? 100 },
        signal: options.signal,
    })
    return Array.isArray(payload)
        ? payload.map(item => ({
            chapter: toInt(item?.chapter, 0),
            hookType: item?.hook_type || '',
            hookStrength: item?.hook_strength || 'unknown',
            isTransition: toInt(item?.is_transition, 0) === 1,
            overrideCount: toInt(item?.override_count, 0),
            debtBalance: toFloat(item?.debt_balance, 0),
        }))
        : []
}

export async function fetchReviewMetrics(options = {}) {
    const payload = await requestJSON('/api/review-metrics', {
        query: { limit: options.limit ?? 30 },
        signal: options.signal,
    })
    return Array.isArray(payload)
        ? payload.map(item => ({
            startChapter: toInt(item?.start_chapter, 0),
            endChapter: toInt(item?.end_chapter, 0),
            overallScore: toNullableFloat(item?.overall_score),
            dimensionScores: parseJSONSafely(item?.dimension_scores, {}),
            severityCounts: parseJSONSafely(item?.severity_counts, {}),
            criticalIssues: parseJSONSafely(item?.critical_issues, []),
            reportFile: item?.report_file || '',
            notes: item?.notes || '',
            updatedAt: item?.updated_at || item?.created_at || '',
        }))
        : []
}

export async function fetchGraph(options = {}) {
    const payload = await requestJSON('/api/graph', {
        query: {
            include_archived: options.includeArchived ?? false,
            limit: options.limit ?? 1000,
        },
        signal: options.signal,
    })

    return {
        status: payload?.status || 'ok',
        nodes: Array.isArray(payload?.nodes)
            ? payload.nodes.map(node => ({
                id: node?.id || '',
                label: node?.label || node?.name || node?.id || '',
                type: node?.type || 'unknown',
                tier: node?.tier || '',
                firstAppearance: node?.first_appearance ?? null,
                lastAppearance: node?.last_appearance ?? null,
                isProtagonist: Boolean(node?.is_protagonist),
                isArchived: Boolean(node?.is_archived),
            }))
            : [],
        edges: Array.isArray(payload?.edges)
            ? payload.edges.map(edge => ({
                id: edge?.id || `${edge?.source || ''}-${edge?.target || ''}`,
                source: edge?.source || '',
                target: edge?.target || '',
                type: edge?.type || 'unknown',
                chapter: edge?.chapter ?? null,
                description: edge?.description || '',
            }))
            : [],
        meta: {
            nodeCount: toInt(payload?.meta?.node_count, 0),
            edgeCount: toInt(payload?.meta?.edge_count, 0),
            includeArchived: Boolean(payload?.meta?.include_archived),
        },
    }
}
