import { requestJSON as baseRequestJSON } from './http.js'

const API_ROOT = '/api/skills'
const DEFAULT_WORKSPACE_ID = 'workspace-default'
const WORKSPACE_ID_STORAGE_KEY = 'webnovel.workspace_id'
const PROJECT_ROOT_STORAGE_KEY = 'webnovel.project_root'

function inferErrorType({ status = 0, errorCode = '' } = {}) {
    const normalizedCode = String(errorCode || '').toLowerCase()
    if (status === 0 || normalizedCode === 'skills_network_error') {
        return 'network'
    }
    if (
        status === 401 ||
        status === 403 ||
        normalizedCode === 'workspace_mismatch' ||
        normalizedCode.includes('permission')
    ) {
        return 'permission'
    }
    if (status === 409 || normalizedCode.includes('conflict')) {
        return 'conflict'
    }
    if (status === 400 || normalizedCode.includes('invalid')) {
        return 'validation'
    }
    if (status >= 500) {
        return 'server'
    }
    return 'api'
}

export class SkillsApiError extends Error {
    constructor(
        message,
        { status = 0, errorCode = 'skills_api_error', errorType = null, details = null } = {},
    ) {
        super(message)
        this.name = 'SkillsApiError'
        this.status = status
        this.errorCode = errorCode
        this.errorType = errorType || inferErrorType({ status, errorCode })
        this.details = details
    }
}

export function classifySkillsError(error) {
    if (error instanceof SkillsApiError) {
        return error.errorType
    }

    const status = Number.isFinite(error?.status) ? Number(error.status) : 0
    const errorCode = String(error?.errorCode || error?.error_code || '')
    return inferErrorType({ status, errorCode })
}

function normalizeWorkspaceContext(options = {}) {
    const fromStorageWorkspaceId =
        typeof window !== 'undefined'
            ? window.localStorage.getItem(WORKSPACE_ID_STORAGE_KEY)
            : null
    const fromStorageProjectRoot =
        typeof window !== 'undefined'
            ? window.localStorage.getItem(PROJECT_ROOT_STORAGE_KEY)
            : null

    const workspaceId = (
        options.workspaceId ||
        fromStorageWorkspaceId ||
        DEFAULT_WORKSPACE_ID
    ).trim()

    return {
        workspace_id: workspaceId || DEFAULT_WORKSPACE_ID,
        project_root: options.projectRoot ?? fromStorageProjectRoot ?? '',
    }
}

function toSkillsApiError(error) {
    if (error instanceof SkillsApiError) return error
    const status = error?.status || 0
    const errorCode = error?.errorCode || 'skills_api_error'
    return new SkillsApiError(error?.message || 'Skills API request failed.', {
        status,
        errorCode,
        errorType: inferErrorType({ status, errorCode }),
        details: error?.details || null,
    })
}

function normalizeSkillItem(item = {}) {
    return {
        skill_id: String(item.skill_id || item.id || '').trim(),
        name: String(item.name || item.skill_id || item.id || '').trim(),
        description: String(item.description || '').trim(),
        source: String(item.source || item.scope || 'workspace').trim() || 'workspace',
        enabled: item.enabled !== false,
        updated_at: item.updated_at || '',
        needs_approval: Boolean(item.needs_approval),
    }
}

function normalizeSkillDraft(item = {}) {
    return {
        skill_id: String(item.skill_id || '').trim(),
        name: String(item.name || '').trim(),
        description: String(item.description || '').trim(),
        instruction_template: String(item.instruction_template || '').trim(),
    }
}

export async function listSkills(options = {}) {
    const workspace = normalizeWorkspaceContext(options)
    let payload
    try {
        payload = await baseRequestJSON(API_ROOT, {
            query: {
                workspace_id: workspace.workspace_id,
                project_root: workspace.project_root,
                enabled: options.enabled,
                limit: options.limit ?? 100,
                offset: options.offset ?? 0,
            },
        })
    } catch (error) {
        throw toSkillsApiError(error)
    }

    return {
        status: payload.status || 'ok',
        items: Array.isArray(payload.items) ? payload.items.map(normalizeSkillItem) : [],
        total: Number.isFinite(payload.total) ? payload.total : 0,
    }
}

export async function createSkill(payload) {
    let response
    try {
        response = await baseRequestJSON(API_ROOT, {
            method: 'POST',
            body: {
                skill_id: String(payload?.skill_id || '').trim(),
                name: String(payload?.name || '').trim(),
                description: String(payload?.description || '').trim(),
                instruction_template: String(payload?.instruction_template || '').trim(),
            },
        })
    } catch (error) {
        throw toSkillsApiError(error)
    }
    return normalizeSkillItem(response)
}

export async function generateSkillDraft(payload) {
    let response
    try {
        response = await baseRequestJSON(`${API_ROOT}/draft`, {
            method: 'POST',
            body: {
                prompt: String(payload?.prompt || '').trim(),
                current_draft: normalizeSkillDraft(payload?.currentDraft || {}),
            },
        })
    } catch (error) {
        throw toSkillsApiError(error)
    }

    return {
        reply: String(response?.reply || '').trim(),
        draft: normalizeSkillDraft(response?.draft || {}),
    }
}

export async function deleteSkill(skillId) {
    const normalizedSkillId = String(skillId || '').trim()
    if (!normalizedSkillId) {
        throw new SkillsApiError('Skill id is required.', {
            status: 400,
            errorCode: 'invalid_skill_payload',
            errorType: 'validation',
        })
    }
    try {
        await baseRequestJSON(`${API_ROOT}/${encodeURIComponent(normalizedSkillId)}`, {
            method: 'DELETE',
        })
    } catch (error) {
        throw toSkillsApiError(error)
    }
}
