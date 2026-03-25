import { useCallback, useEffect, useMemo, useState } from 'react'
import PageScaffold from '../components/PageScaffold.jsx'
import {
    fetchReadingPower,
    fetchReviewMetrics,
    formatApiError,
} from '../api/dashboardPages.js'

const RETRY_BUTTON_STYLE = {
    border: '2px solid var(--border-main)',
    background: '#fff8e6',
    color: 'var(--text-main)',
    fontFamily: 'var(--font-body)',
    fontSize: 13,
    fontWeight: 700,
    padding: '6px 12px',
    cursor: 'pointer',
}

function formatNumber(value) {
    return new Intl.NumberFormat('zh-CN').format(value || 0)
}

function formatScore(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
        return '-'
    }
    return Number(value).toFixed(2)
}

function formatSeverityCounts(value) {
    if (!value || typeof value !== 'object') {
        return '-'
    }
    const entries = Object.entries(value)
    if (entries.length === 0) {
        return '-'
    }
    return entries
        .map(([key, count]) => `${key}:${count}`)
        .join(', ')
}

function pickHookBadge(strength) {
    if (strength === 'strong') return 'badge-green'
    if (strength === 'weak') return 'badge-red'
    return 'badge-amber'
}

export default function ReadingPowerPage() {
    const [readingRows, setReadingRows] = useState([])
    const [reviewRows, setReviewRows] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')
    const [hookFilter, setHookFilter] = useState('')

    const refresh = useCallback(async () => {
        setLoading(true)
        setError('')
        try {
            const [readingResponse, reviewResponse] = await Promise.all([
                fetchReadingPower({ limit: 120 }),
                fetchReviewMetrics({ limit: 30 }),
            ])
            setReadingRows(readingResponse)
            setReviewRows(reviewResponse)
        } catch (err) {
            setError(formatApiError(err, '加载追读力数据失败'))
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        void refresh()
    }, [refresh])

    const hookTypes = useMemo(() => {
        const set = new Set()
        readingRows.forEach(item => {
            if (item.hookStrength) {
                set.add(item.hookStrength)
            }
        })
        return Array.from(set).sort()
    }, [readingRows])

    const filteredReadingRows = useMemo(() => {
        if (!hookFilter) {
            return readingRows
        }
        return readingRows.filter(item => item.hookStrength === hookFilter)
    }, [hookFilter, readingRows])

    const summary = useMemo(() => {
        const latestChapter = filteredReadingRows.reduce(
            (max, item) => Math.max(max, Number(item.chapter) || 0),
            0,
        )
        const avgDebt = filteredReadingRows.length > 0
            ? filteredReadingRows.reduce((sum, item) => sum + item.debtBalance, 0) / filteredReadingRows.length
            : 0
        const validReviewScores = reviewRows
            .map(item => Number(item.overallScore))
            .filter(score => Number.isFinite(score))
        const avgReviewScore = validReviewScores.length > 0
            ? validReviewScores.reduce((sum, score) => sum + score, 0) / validReviewScores.length
            : null
        return {
            latestChapter: latestChapter > 0 ? latestChapter : null,
            avgDebt,
            avgReviewScore,
        }
    }, [filteredReadingRows, reviewRows])

    const isEmpty = !loading && !error && readingRows.length === 0 && reviewRows.length === 0

    return (
        <PageScaffold
            title="追读力"
            badge={loading ? '加载中' : `${filteredReadingRows.length} 章数据`}
            description="追读力和审查指标来自 /api/reading-power 与 /api/review-metrics。"
        >
            {loading ? (
                <div className="loading">追读力数据加载中...</div>
            ) : null}

            {!loading && error ? (
                <div className="card" role="alert">
                    <div className="card-header">
                        <span className="card-title">加载失败</span>
                        <span className="card-badge badge-red">Error</span>
                    </div>
                    <p style={{ marginTop: 0 }}>{error}</p>
                    <button type="button" style={RETRY_BUTTON_STYLE} onClick={() => void refresh()}>
                        重试
                    </button>
                </div>
            ) : null}

            {isEmpty ? (
                <div className="card empty-state">
                    <div className="empty-icon">R</div>
                    <p>当前暂无追读力与审查指标数据。</p>
                </div>
            ) : null}

            {!loading && !error && !isEmpty ? (
                <>
                    <div className="dashboard-grid">
                        <div className="card stat-card">
                            <span className="stat-label">追读力记录</span>
                            <span className="stat-value">{formatNumber(filteredReadingRows.length)}</span>
                            <span className="stat-sub">过滤后章节数</span>
                        </div>
                        <div className="card stat-card">
                            <span className="stat-label">最新章节</span>
                            <span className="stat-value">{summary.latestChapter ?? '-'}</span>
                            <span className="stat-sub">依据追读力章节号</span>
                        </div>
                        <div className="card stat-card">
                            <span className="stat-label">平均债务余额</span>
                            <span className="stat-value">{summary.avgDebt.toFixed(2)}</span>
                            <span className="stat-sub">过滤后均值</span>
                        </div>
                        <div className="card stat-card">
                            <span className="stat-label">审查均分</span>
                            <span className="stat-value plain">{formatScore(summary.avgReviewScore)}</span>
                            <span className="stat-sub">依据 review_metrics</span>
                        </div>
                    </div>

                    <div className="card">
                        <div className="filter-group">
                            <button
                                type="button"
                                className={`filter-btn ${hookFilter === '' ? 'active' : ''}`}
                                onClick={() => setHookFilter('')}
                            >
                                全部强度
                            </button>
                            {hookTypes.map(type => (
                                <button
                                    type="button"
                                    key={type}
                                    className={`filter-btn ${hookFilter === type ? 'active' : ''}`}
                                    onClick={() => setHookFilter(type)}
                                >
                                    {type}
                                </button>
                            ))}
                        </div>
                    </div>

                    <div className="card">
                        <div className="card-header">
                            <span className="card-title">章节追读力</span>
                            <span className="card-badge badge-amber">{filteredReadingRows.length} 条</span>
                        </div>
                        <div className="table-wrap">
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>章节</th>
                                        <th>钩子类型</th>
                                        <th>钩子强度</th>
                                        <th>过渡章</th>
                                        <th>Override</th>
                                        <th>债务余额</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {filteredReadingRows.map(item => (
                                        <tr key={item.chapter}>
                                            <td>第 {item.chapter} 章</td>
                                            <td>{item.hookType || '-'}</td>
                                            <td>
                                                <span className={`card-badge ${pickHookBadge(item.hookStrength)}`}>
                                                    {item.hookStrength || 'unknown'}
                                                </span>
                                            </td>
                                            <td>{item.isTransition ? '是' : '否'}</td>
                                            <td>{item.overrideCount}</td>
                                            <td>{item.debtBalance.toFixed(2)}</td>
                                        </tr>
                                    ))}
                                    {filteredReadingRows.length === 0 ? (
                                        <tr>
                                            <td colSpan={6}>筛选后暂无追读力记录。</td>
                                        </tr>
                                    ) : null}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <div className="card">
                        <div className="card-header">
                            <span className="card-title">审查指标</span>
                            <span className="card-badge badge-blue">{reviewRows.length} 条</span>
                        </div>
                        <div className="table-wrap">
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>章节范围</th>
                                        <th>整体分数</th>
                                        <th>严重级统计</th>
                                        <th>关键问题</th>
                                        <th>更新时间</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {reviewRows.map(item => (
                                        <tr key={`${item.startChapter}-${item.endChapter}`}>
                                            <td>{item.startChapter} - {item.endChapter}</td>
                                            <td>{formatScore(item.overallScore)}</td>
                                            <td>{formatSeverityCounts(item.severityCounts)}</td>
                                            <td className="truncate">
                                                {Array.isArray(item.criticalIssues) && item.criticalIssues.length > 0
                                                    ? String(item.criticalIssues[0])
                                                    : '-'}
                                            </td>
                                            <td>{item.updatedAt || '-'}</td>
                                        </tr>
                                    ))}
                                    {reviewRows.length === 0 ? (
                                        <tr>
                                            <td colSpan={5}>暂无审查指标记录。</td>
                                        </tr>
                                    ) : null}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </>
            ) : null}
        </PageScaffold>
    )
}
