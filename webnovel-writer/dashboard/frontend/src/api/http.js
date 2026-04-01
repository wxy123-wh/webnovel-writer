/**
 * Shared HTTP utilities for API modules.
 *
 * Every frontend API module should import `requestJSON` (and helpers) from
 * here instead of redefining its own copy.
 */

// ---------------------------------------------------------------------------
// URL helpers
// ---------------------------------------------------------------------------

/**
 * Resolve the current page origin, falling back to `http://localhost` when
 * `window` is unavailable (e.g. during SSR / tests).
 */
export function resolveOrigin() {
    if (typeof window !== 'undefined' && window.location?.origin) {
        return window.location.origin
    }
    return 'http://localhost'
}

/**
 * Build a fully-qualified URL from a pathname and optional query parameters.
 *
 * Empty / null / undefined values are silently omitted.  Boolean values are
 * serialised as `"true"` / `"false"`.
 */
export function createRequestUrl(pathname, query = {}) {
    const url = new URL(pathname, resolveOrigin())
    Object.entries(query).forEach(([key, value]) => {
        if (value === undefined || value === null || `${value}`.trim() === '') {
            return
        }
        if (typeof value === 'boolean') {
            url.searchParams.set(key, value ? 'true' : 'false')
            return
        }
        url.searchParams.set(key, String(value))
    })
    return url.toString()
}

// ---------------------------------------------------------------------------
// Payload helpers
// ---------------------------------------------------------------------------

/**
 * Safely parse a raw response text as JSON.  Returns an empty object for
 * empty input and wraps non-JSON text in `{ message }`.
 */
export function parsePayload(rawText) {
    if (!rawText) return {}
    try {
        return JSON.parse(rawText)
    } catch {
        return { message: rawText }
    }
}

// ---------------------------------------------------------------------------
// Error helpers
// ---------------------------------------------------------------------------

/**
 * Extract a structured `Error` from an HTTP response + parsed payload.
 * The returned error carries `.status`, `.errorCode`, `.details`, and
 * `.requestId` properties.
 */
export function toApiError(response, payload) {
    const details = payload?.detail || payload
    const message = details?.message || `${response.status} ${response.statusText}`
    const error = new Error(message)
    error.status = response.status
    error.errorCode = details?.error_code || 'api_request_failed'
    error.details = details?.details || null
    error.requestId = details?.request_id || null
    return error
}

/**
 * Create a plain-network connectivity error (thrown when `fetch` itself
 * rejects, e.g. server unreachable).
 */
export function toNetworkError(fallbackMessage = '无法连接到服务，请确认后端已启动。') {
    const error = new Error(fallbackMessage)
    error.status = 0
    error.errorCode = 'network_error'
    error.details = null
    return error
}

// ---------------------------------------------------------------------------
// Core request function
// ---------------------------------------------------------------------------

/**
 * Perform a JSON fetch request.
 *
 * @param {string} pathname  – API path (e.g. `/api/hierarchy/workspace`).
 * @param {object} [options]
 * @param {string}        [options.method='GET']
 * @param {object}        [options.query]   – query-string parameters.
 * @param {*}             [options.body]    – JSON-serialisable request body.
 * @param {AbortSignal}   [options.signal]  – abort signal.
 * @param {boolean}       [options.catchNetwork=false] – wrap network failures
 *   in a standard error (useful for modules that want offline-friendly msgs).
 * @param {string}        [options.networkMessage] – custom message on network
 *   error (used with `catchNetwork`).
 * @returns {Promise<object>} Parsed JSON payload.
 */
export async function requestJSON(pathname, {
    method = 'GET',
    query,
    body,
    signal,
    catchNetwork = false,
    networkMessage,
} = {}) {
    const fetchOptions = {
        method,
        headers: body ? { 'Content-Type': 'application/json' } : undefined,
        body: body ? JSON.stringify(body) : undefined,
        signal,
    }

    let response
    try {
        response = await fetch(createRequestUrl(pathname, query), fetchOptions)
    } catch (error) {
        if (catchNetwork) {
            throw toNetworkError(networkMessage)
        }
        throw error
    }

    const payload = parsePayload(await response.text())
    if (!response.ok) {
        throw toApiError(response, payload)
    }
    return payload
}
