import test from 'node:test'
import assert from 'node:assert/strict'

const originalFetch = globalThis.fetch
const originalWindow = globalThis.window

function mockWindow() {
    globalThis.window = {
        location: {
            origin: 'http://localhost:5173',
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
    return import(`./dashboardPages.js?test_case=${Date.now()}_${Math.random().toString(16).slice(2)}`)
}

test('fetchDashboardOverview normalizes counts and reading power fields', async () => {
    mockWindow()
    globalThis.fetch = async url => {
        assert.match(String(url), /\/api\/dashboard\/overview$/)
        return mockJsonResponse(200, {
            status: 'ok',
            counts: {
                entities: 10,
                relationships: '6',
                chapters: null,
                files: 18,
            },
            reading_power: {
                total_rows: '5',
                latest_chapter: 12,
                transition_chapters: '2',
                avg_debt_balance: '1.375',
                hook_strength_distribution: {
                    strong: 2,
                    medium: '1',
                    weak: 1,
                    unknown: 1,
                },
            },
        })
    }

    const module = await loadModule()
    try {
        const data = await module.fetchDashboardOverview()
        assert.deepEqual(data.counts, {
            entities: 10,
            relationships: 6,
            chapters: 0,
            files: 18,
        })
        assert.deepEqual(data.readingPower, {
            totalRows: 5,
            latestChapter: 12,
            transitionChapters: 2,
            avgDebtBalance: 1.375,
            hookStrengthDistribution: {
                strong: 2,
                medium: 1,
                weak: 1,
                unknown: 1,
            },
        })
    } finally {
        restoreFetch()
        restoreWindow()
    }
})

test('requestJSON throws DashboardApiError with normalized backend error metadata', async () => {
    mockWindow()
    globalThis.fetch = async () => mockJsonResponse(404, {
        error_code: 'index_db_not_found',
        message: 'index.db 不存在',
        details: { path: '/tmp/index.db' },
    }, 'Not Found')

    const module = await loadModule()
    try {
        await assert.rejects(
            () => module.requestJSON('/api/dashboard/overview'),
            error => {
                assert.equal(error.name, 'DashboardApiError')
                assert.equal(error.status, 404)
                assert.equal(error.errorCode, 'index_db_not_found')
                assert.equal(error.message, 'index.db 不存在')
                assert.deepEqual(error.details, { path: '/tmp/index.db' })
                return true
            },
        )
    } finally {
        restoreFetch()
        restoreWindow()
    }
})

test('fetchReadingPower normalizes boolean and numeric fields', async () => {
    mockWindow()
    globalThis.fetch = async url => {
        assert.match(String(url), /\/api\/reading-power/)
        return mockJsonResponse(200, [
            {
                chapter: 8,
                hook_type: '悬念',
                hook_strength: 'strong',
                is_transition: '0',
                override_count: '3',
                debt_balance: '2.5',
            },
            {
                chapter: 9,
                hook_type: '反差',
                hook_strength: 'medium',
                is_transition: 1,
                override_count: 0,
                debt_balance: 0,
            },
        ])
    }

    const module = await loadModule()
    try {
        const rows = await module.fetchReadingPower()
        assert.equal(rows.length, 2)
        assert.equal(rows[0].isTransition, false)
        assert.equal(rows[1].isTransition, true)
        assert.equal(rows[0].overrideCount, 3)
        assert.equal(rows[0].debtBalance, 2.5)
    } finally {
        restoreFetch()
        restoreWindow()
    }
})

test('fetchReviewMetrics parses JSON object fields', async () => {
    mockWindow()
    globalThis.fetch = async url => {
        assert.match(String(url), /\/api\/review-metrics/)
        return mockJsonResponse(200, [
            {
                start_chapter: 1,
                end_chapter: 5,
                overall_score: '87.5',
                dimension_scores: '{"hook":88,"logic":86}',
                severity_counts: '{"critical":1,"major":2}',
                critical_issues: '["角色动机薄弱"]',
                updated_at: '2026-03-26T00:00:00Z',
            },
        ])
    }

    const module = await loadModule()
    try {
        const rows = await module.fetchReviewMetrics()
        assert.equal(rows.length, 1)
        assert.equal(rows[0].overallScore, 87.5)
        assert.deepEqual(rows[0].dimensionScores, { hook: 88, logic: 86 })
        assert.deepEqual(rows[0].severityCounts, { critical: 1, major: 2 })
        assert.deepEqual(rows[0].criticalIssues, ['角色动机薄弱'])
    } finally {
        restoreFetch()
        restoreWindow()
    }
})
