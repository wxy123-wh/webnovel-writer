import { requestJSON } from './http.js'

const REVISIONED_ENTITY_TYPES = new Set(['outline', 'plot', 'chapter', 'setting'])

function toCamelCaseKey(key) {
    return String(key || '').replace(/_([a-z])/g, (_, char) => char.toUpperCase())
}

function normalizeObjectKeys(raw) {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
        return {}
    }
    return Object.fromEntries(
        Object.entries(raw).map(([key, value]) => [toCamelCaseKey(key), value]),
    )
}

const ENTITY_CONFIG = {
    outline: { idKey: 'outline_id', parentKey: null },
    plot: { idKey: 'plot_id', parentKey: 'outline_id' },
    event: { idKey: 'event_id', parentKey: 'plot_id' },
    scene: { idKey: 'scene_id', parentKey: 'event_id' },
    chapter: { idKey: 'chapter_id', parentKey: 'scene_id' },
    setting: { idKey: 'setting_id', parentKey: null },
    canon_entry: { idKey: 'canon_id', parentKey: null },
}

function normalizeEntity(entityType, raw) {
    const config = ENTITY_CONFIG[entityType]
    if (!config || !raw || typeof raw !== 'object') return null
    const entityId = raw[config.idKey]
    if (!entityId) return null
    return {
        entityId,
        entityType,
        parentId: config.parentKey ? raw[config.parentKey] || '' : '',
        title: raw.title || '',
        body: raw.body || '',
        metadata: raw.metadata && typeof raw.metadata === 'object' ? raw.metadata : {},
        position: Number.isFinite(raw.position) ? raw.position : 0,
        version: Number.isFinite(raw.version) ? raw.version : 1,
        createdAt: raw.created_at || '',
        updatedAt: raw.updated_at || '',
        supportsRevisions: REVISIONED_ENTITY_TYPES.has(entityType),
        proposals: [],
        revisions: [],
    }
}

function normalizeNode(entity) {
    return {
        id: entity.entityId,
        type: entity.entityType,
        label: entity.title || `${entity.entityType} ${entity.entityId}`,
        parentId: entity.parentId || null,
        depth: 0,
        position: entity.position,
        version: entity.version,
    }
}

function computeNodeDepth(nodeMap, nodeId) {
    let depth = 0
    let current = nodeMap.get(nodeId)
    while (current?.parentId) {
        depth += 1
        current = nodeMap.get(current.parentId)
    }
    return depth
}

function normalizeRevision(raw) {
    return {
        revisionId: raw?.revision_id || '',
        revisionNumber: Number.isFinite(raw?.revision_number) ? raw.revision_number : 0,
        label: `r${Number.isFinite(raw?.revision_number) ? raw.revision_number : '?'}`,
        createdAt: raw?.created_at || '',
        entityVersion: Number.isFinite(raw?.entity_version) ? raw.entity_version : 0,
        snapshot: raw?.snapshot && typeof raw.snapshot === 'object' ? raw.snapshot : {},
    }
}

function normalizeProposal(raw) {
    const payload = raw?.payload && typeof raw.payload === 'object' ? raw.payload : {}
    const kind = typeof payload.kind === 'string' ? payload.kind : ''
    return {
        proposalId: raw?.proposal_id || '',
        proposalType: raw?.proposal_type || '',
        targetType: raw?.target_type || '',
        status: raw?.status || 'pending',
        kind,
        title: payload?.candidate?.title || payload?.proposed_children?.[0]?.title || raw?.proposal_type || '未命名提案',
        summary: payload?.candidate?.body || payload?.proposed_children?.map(item => item.title).join(' / ') || '',
        payload,
        baseVersion: Number.isFinite(raw?.base_version) ? raw.base_version : null,
        currentHeadFingerprint: raw?.current_head_fingerprint || '',
        decisionReason: raw?.decision_reason || '',
        canReview: kind === 'structural_children' || kind === 'canon_candidate' || kind === 'chapter_edit',
    }
}

function normalizeIndexState(raw) {
    if (!raw || typeof raw !== 'object') return null
    return {
        indexStateId: raw.index_state_id || '',
        generation: Number.isFinite(raw.generation) ? raw.generation : 0,
        status: raw.status || 'stale',
        sourceFingerprint: raw.source_fingerprint || '',
        details: normalizeObjectKeys(raw.details),
        version: Number.isFinite(raw.version) ? raw.version : 1,
        createdAt: raw.created_at || '',
        updatedAt: raw.updated_at || '',
    }
}

async function fetchEntityRevisions(bookId, entity) {
    if (!entity.supportsRevisions) {
        return []
    }
    const revisions = await requestJSON(`/api/hierarchy/books/${bookId}/revisions/${entity.entityType}/${entity.entityId}`)
    return Array.isArray(revisions) ? revisions.map(normalizeRevision) : []
}

export function formatAuthoringApiError(error, fallbackCode = 'api_request_failed') {
    const code = typeof error?.errorCode === 'string' && error.errorCode.trim()
        ? error.errorCode.trim()
        : fallbackCode
    const message = typeof error?.message === 'string' && error.message.trim()
        ? error.message.trim()
        : '请求失败，请稍后重试。'
    return `${code}: ${message}`
}

export async function fetchAuthoringWorkspace(options = {}) {
    const payload = await requestJSON('/api/hierarchy/workspace', { signal: options.signal })
    const bookId = payload?.book?.book_id || ''
    const entities = {}
    const nodes = []

    Object.entries(ENTITY_CONFIG).forEach(([entityType]) => {
        const collectionKey = entityType === 'canon_entry' ? 'canon_entries' : `${entityType}s`
        const items = Array.isArray(payload?.[collectionKey]) ? payload[collectionKey] : []
        items.forEach(item => {
            const entity = normalizeEntity(entityType, item)
            if (!entity) return
            entities[entity.entityId] = entity
            nodes.push(normalizeNode(entity))
        })
    })

    const nodeMap = new Map(nodes.map(node => [node.id, node]))
    nodes.forEach(node => {
        node.depth = computeNodeDepth(nodeMap, node.id)
    })
    nodes.sort((left, right) => {
        if ((left.depth || 0) !== (right.depth || 0)) return (left.depth || 0) - (right.depth || 0)
        if ((left.parentId || '') !== (right.parentId || '')) return (left.parentId || '').localeCompare(right.parentId || '')
        if ((left.position || 0) !== (right.position || 0)) return (left.position || 0) - (right.position || 0)
        return left.label.localeCompare(right.label, 'zh-CN')
    })

    const proposals = Array.isArray(payload?.proposals) ? payload.proposals.map(normalizeProposal) : []
    proposals.forEach(proposal => {
        const sourceId = proposal.kind === 'canon_candidate'
            ? proposal.payload?.source_id
            : proposal.kind === 'chapter_edit'
                ? proposal.payload?.chapter_id
            : proposal.payload?.parent_id
        if (sourceId && entities[sourceId]) {
            entities[sourceId].proposals.push(proposal)
        }
    })

    await Promise.all(
        Object.values(entities).map(async entity => {
            entity.revisions = await fetchEntityRevisions(bookId, entity)
        }),
    )

    return {
        book: {
            bookId,
            title: payload?.book?.title || '',
            synopsis: payload?.book?.synopsis || '',
            version: Number.isFinite(payload?.book?.version) ? payload.book.version : 1,
        },
        indexState: normalizeIndexState(payload?.index_state),
        nodes,
        entities,
        selectedNodeId: nodes[0]?.id || '',
    }
}

export async function saveEntityDraft({ bookId, entityType, entityId, version, title, body, metadata, signal }) {
    return requestJSON(`/api/hierarchy/books/${bookId}/entities/${entityType}/${entityId}`, {
        method: 'PATCH',
        body: {
            expected_version: version,
            title,
            body,
            metadata: metadata || {},
        },
        signal,
    })
}

export async function confirmProposal({ bookId, proposalId, signal }) {
    return requestJSON(`/api/hierarchy/books/${bookId}/proposals/${proposalId}/confirm`, {
        method: 'POST',
        signal,
    })
}

export async function rejectProposal({ bookId, proposalId, signal }) {
    return requestJSON(`/api/hierarchy/books/${bookId}/proposals/${proposalId}/reject`, {
        method: 'POST',
        signal,
    })
}

export async function fetchRevisionDiff({ bookId, entityType, entityId, fromRevision, toRevision, signal }) {
    const payload = await requestJSON(`/api/hierarchy/books/${bookId}/revisions/${entityType}/${entityId}/diff`, {
        query: {
            from_revision: fromRevision,
            to_revision: toRevision,
        },
        signal,
    })
    return {
        summary: '对比已加载',
        diffText: payload?.diff || '',
        fromRevision,
        toRevision,
    }
}

export async function rollbackRevision({ bookId, entityType, entityId, targetRevision, version, signal }) {
    return requestJSON(`/api/hierarchy/books/${bookId}/revisions/${entityType}/${entityId}/rollback`, {
        method: 'POST',
        body: {
            target_revision: targetRevision,
            expected_version: version,
        },
        signal,
    })
}

export async function markIndexStale({ bookId, reason, signal }) {
    return requestJSON(`/api/hierarchy/books/${bookId}/index/mark-stale`, {
        method: 'POST',
        body: { reason: reason || 'manual_reset' },
        signal,
    })
}

export async function rebuildIndex({ bookId, signal }) {
    return requestJSON(`/api/hierarchy/books/${bookId}/index/rebuild`, {
        method: 'POST',
        signal,
    })
}
