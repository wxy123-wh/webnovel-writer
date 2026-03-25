import { useCallback, useEffect, useMemo, useState } from 'react'
import PageScaffold from '../components/PageScaffold.jsx'
import { fetchChapters, formatApiError } from '../api/dashboardPages.js'

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

const FILTER_INPUT_STYLE = {
    border: '2px solid var(--border-main)',
    background: '#fff',
    color: 'var(--text-main)',
    fontFamily: 'var(--font-body)',
    fontSize: 13,
    padding: '4px 8px',
}

function toWordCount(item) {
    const value = Number(item?.word_count ?? item?.words ?? 0)
    return Number.isFinite(value) ? Math.max(0, Math.trunc(value)) : 0
}

function formatNumber(value) {
    return new Intl.NumberFormat('zh-CN').format(value || 0)
}

function normalizeText(value) {
    return (value || '').toString().trim().toLowerCase()
}

export default function ChaptersPage() {
    const [chapters, setChapters] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')
    const [keyword, setKeyword] = useState('')

    const refresh = useCallback(async () => {
        setLoading(true)
        setError('')
        try {
            const response = await fetchChapters()
            setChapters(Array.isArray(response) ? response : [])
        } catch (err) {
            setError(formatApiError(err, '加载章节数据失败'))
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        void refresh()
    }, [refresh])

    const filteredChapters = useMemo(() => {
        const search = normalizeText(keyword)
        if (!search) {
            return chapters
        }
        return chapters.filter(item => {
            const title = normalizeText(item?.title)
            const chapter = normalizeText(item?.chapter)
            const location = normalizeText(item?.location)
            return title.includes(search) || chapter.includes(search) || location.includes(search)
        })
    }, [chapters, keyword])

    const totalWords = useMemo(
        () => filteredChapters.reduce((sum, item) => sum + toWordCount(item), 0),
        [filteredChapters],
    )

    const hasNoMatches = !loading && !error && chapters.length > 0 && filteredChapters.length === 0

    return (
        <PageScaffold
            title="章节一览"
            badge={loading ? '加载中' : `${filteredChapters.length}/${chapters.length} 章`}
            description="章节清单支持关键词筛选，数据来自 /api/chapters。"
        >
            {loading ? (
                <div className="loading">章节数据加载中...</div>
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

            {!loading && !error && chapters.length === 0 ? (
                <div className="card empty-state">
                    <div className="empty-icon">C</div>
                    <p>当前数据库暂无章节数据。</p>
                </div>
            ) : null}

            {!loading && !error && chapters.length > 0 ? (
                <>
                    <div className="card">
                        <div className="filter-group">
                            <input
                                style={FILTER_INPUT_STYLE}
                                placeholder="按章节号、标题或地点筛选"
                                value={keyword}
                                onChange={event => setKeyword(event.target.value)}
                            />
                            <span className="card-badge badge-blue">筛选后字数: {formatNumber(totalWords)}</span>
                        </div>
                    </div>

                    <div className="card">
                        <div className="table-wrap">
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>章节</th>
                                        <th>标题</th>
                                        <th>字数</th>
                                        <th>地点</th>
                                        <th>角色</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {filteredChapters.map(item => (
                                        <tr key={item.id || item.chapter}>
                                            <td>第 {item.chapter ?? '-'} 章</td>
                                            <td>{item.title || '-'}</td>
                                            <td>{formatNumber(toWordCount(item))}</td>
                                            <td>{item.location || '-'}</td>
                                            <td className="truncate">{item.characters || '-'}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                        {hasNoMatches ? (
                            <div className="empty-state compact">
                                <p>筛选后无匹配章节。</p>
                            </div>
                        ) : null}
                    </div>
                </>
            ) : null}
        </PageScaffold>
    )
}
