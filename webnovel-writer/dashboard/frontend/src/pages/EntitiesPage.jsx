import { useCallback, useEffect, useMemo, useState } from 'react'
import PageScaffold from '../components/PageScaffold.jsx'
import { fetchEntities, formatApiError } from '../api/dashboardPages.js'

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

function normalizeText(value) {
    return (value || '').toString().trim().toLowerCase()
}

export default function EntitiesPage() {
    const [entities, setEntities] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')
    const [typeFilter, setTypeFilter] = useState('')
    const [keyword, setKeyword] = useState('')

    const refresh = useCallback(async () => {
        setLoading(true)
        setError('')
        try {
            const response = await fetchEntities({ includeArchived: false })
            setEntities(Array.isArray(response) ? response : [])
        } catch (err) {
            setError(formatApiError(err, '加载实体列表失败'))
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        void refresh()
    }, [refresh])

    const typeOptions = useMemo(() => {
        const set = new Set()
        entities.forEach(item => {
            if (item?.type) {
                set.add(item.type)
            }
        })
        return Array.from(set).sort((a, b) => a.localeCompare(b, 'zh-CN'))
    }, [entities])

    const filteredEntities = useMemo(() => {
        const search = normalizeText(keyword)
        return entities.filter(item => {
            if (typeFilter && item?.type !== typeFilter) {
                return false
            }
            if (!search) {
                return true
            }
            const name = normalizeText(item?.canonical_name || item?.name)
            const id = normalizeText(item?.id)
            return name.includes(search) || id.includes(search)
        })
    }, [entities, keyword, typeFilter])

    const hasNoMatches = !loading && !error && entities.length > 0 && filteredEntities.length === 0

    return (
        <PageScaffold
            title="设定词典"
            badge={loading ? '加载中' : `${filteredEntities.length}/${entities.length}`}
            description="实体列表支持类型与关键词筛选，数据来自 /api/entities。"
        >
            {loading ? (
                <div className="loading">实体数据加载中...</div>
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

            {!loading && !error && entities.length === 0 ? (
                <div className="card empty-state">
                    <div className="empty-icon">E</div>
                    <p>当前数据库暂无实体记录。</p>
                </div>
            ) : null}

            {!loading && !error && entities.length > 0 ? (
                <>
                    <div className="card">
                        <div className="filter-group">
                            <button
                                type="button"
                                className={`filter-btn ${typeFilter === '' ? 'active' : ''}`}
                                onClick={() => setTypeFilter('')}
                            >
                                全部类型
                            </button>
                            {typeOptions.map(type => (
                                <button
                                    type="button"
                                    key={type}
                                    className={`filter-btn ${typeFilter === type ? 'active' : ''}`}
                                    onClick={() => setTypeFilter(type)}
                                >
                                    {type}
                                </button>
                            ))}
                            <input
                                style={FILTER_INPUT_STYLE}
                                placeholder="按名称或 ID 搜索"
                                value={keyword}
                                onChange={event => setKeyword(event.target.value)}
                            />
                        </div>
                    </div>

                    <div className="card">
                        <div className="table-wrap">
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>ID</th>
                                        <th>名称</th>
                                        <th>类型</th>
                                        <th>层级</th>
                                        <th>首现</th>
                                        <th>末现</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {filteredEntities.map(item => (
                                        <tr key={item.id}>
                                            <td>{item.id}</td>
                                            <td>
                                                {item.canonical_name || item.name || '-'}
                                                {item.is_protagonist ? ' ★' : ''}
                                            </td>
                                            <td>{item.type || '-'}</td>
                                            <td>{item.tier || '-'}</td>
                                            <td>{item.first_appearance ?? '-'}</td>
                                            <td>{item.last_appearance ?? '-'}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                        {hasNoMatches ? (
                            <div className="empty-state compact">
                                <p>筛选后无匹配结果，请调整条件。</p>
                            </div>
                        ) : null}
                    </div>
                </>
            ) : null}
        </PageScaffold>
    )
}
