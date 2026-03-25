import { useCallback, useEffect, useMemo, useState } from 'react'
import PageScaffold from '../components/PageScaffold.jsx'
import {
    fetchDashboardOverview,
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

function formatCount(value) {
    return new Intl.NumberFormat('zh-CN').format(value || 0)
}

export default function DashboardPage() {
    const [overview, setOverview] = useState(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')

    const refresh = useCallback(async () => {
        setLoading(true)
        setError('')
        try {
            const response = await fetchDashboardOverview()
            setOverview(response)
        } catch (err) {
            setError(formatApiError(err, '加载总览数据失败'))
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        void refresh()
    }, [refresh])

    const isEmpty = useMemo(() => {
        if (!overview) return false
        const counts = overview.counts
        const reading = overview.readingPower
        return (
            counts.entities === 0
            && counts.relationships === 0
            && counts.chapters === 0
            && counts.files === 0
            && reading.totalRows === 0
        )
    }, [overview])

    return (
        <PageScaffold
            title="数据总览"
            badge={loading ? '加载中' : '实时数据'}
            description="展示项目基础规模与追读力核心指标。"
        >
            {loading ? (
                <div className="loading">总览数据加载中...</div>
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

            {!loading && !error && isEmpty ? (
                <div className="card empty-state">
                    <div className="empty-icon">D</div>
                    <p>当前项目暂无可展示的总览数据。</p>
                </div>
            ) : null}

            {!loading && !error && !isEmpty && overview ? (
                <>
                    <div className="dashboard-grid">
                        <div className="card stat-card">
                            <span className="stat-label">实体总数</span>
                            <span className="stat-value">{formatCount(overview.counts.entities)}</span>
                            <span className="stat-sub">来源: /api/dashboard/overview</span>
                        </div>
                        <div className="card stat-card">
                            <span className="stat-label">关系总数</span>
                            <span className="stat-value">{formatCount(overview.counts.relationships)}</span>
                            <span className="stat-sub">来源: /api/dashboard/overview</span>
                        </div>
                        <div className="card stat-card">
                            <span className="stat-label">章节总数</span>
                            <span className="stat-value">{formatCount(overview.counts.chapters)}</span>
                            <span className="stat-sub">来源: /api/dashboard/overview</span>
                        </div>
                        <div className="card stat-card">
                            <span className="stat-label">文档文件数</span>
                            <span className="stat-value">{formatCount(overview.counts.files)}</span>
                            <span className="stat-sub">来源: /api/dashboard/overview</span>
                        </div>
                    </div>

                    <div className="card">
                        <div className="card-header">
                            <span className="card-title">追读力摘要</span>
                            <span className="card-badge badge-blue">{overview.readingPower.totalRows} 条</span>
                        </div>
                        <div className="table-wrap">
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>最新章节</th>
                                        <th>过渡章节数</th>
                                        <th>平均债务余额</th>
                                        <th>强钩子</th>
                                        <th>中钩子</th>
                                        <th>弱钩子</th>
                                        <th>未知</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr>
                                        <td>{overview.readingPower.latestChapter ?? '-'}</td>
                                        <td>{overview.readingPower.transitionChapters}</td>
                                        <td>
                                            {overview.readingPower.avgDebtBalance === null
                                                ? '-'
                                                : overview.readingPower.avgDebtBalance.toFixed(2)}
                                        </td>
                                        <td>{overview.readingPower.hookStrengthDistribution.strong}</td>
                                        <td>{overview.readingPower.hookStrengthDistribution.medium}</td>
                                        <td>{overview.readingPower.hookStrengthDistribution.weak}</td>
                                        <td>{overview.readingPower.hookStrengthDistribution.unknown}</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </>
            ) : null}
        </PageScaffold>
    )
}
