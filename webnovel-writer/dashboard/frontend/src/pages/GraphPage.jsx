import { useCallback, useEffect, useMemo, useState } from 'react'
import PageScaffold from '../components/PageScaffold.jsx'
import { fetchGraph, formatApiError } from '../api/dashboardPages.js'

const CONTROL_STYLE = {
    border: '2px solid var(--border-main)',
    background: '#fff',
    color: 'var(--text-main)',
    fontFamily: 'var(--font-body)',
    fontSize: 13,
    padding: '4px 8px',
}

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

const PANEL_LAYOUT_STYLE = {
    display: 'grid',
    gap: 14,
    gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)',
}

function normalizeText(value) {
    return (value || '').toString().trim().toLowerCase()
}

export default function GraphPage() {
    const [graph, setGraph] = useState({ nodes: [], edges: [], meta: { nodeCount: 0, edgeCount: 0 } })
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')
    const [nodeKeyword, setNodeKeyword] = useState('')
    const [nodeTypeFilter, setNodeTypeFilter] = useState('')
    const [edgeTypeFilter, setEdgeTypeFilter] = useState('')

    const refresh = useCallback(async () => {
        setLoading(true)
        setError('')
        try {
            const response = await fetchGraph({ includeArchived: false, limit: 2000 })
            setGraph(response)
        } catch (err) {
            setError(formatApiError(err, '加载图谱数据失败'))
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        void refresh()
    }, [refresh])

    const nodeTypeOptions = useMemo(() => {
        const set = new Set()
        graph.nodes.forEach(node => {
            if (node.type) {
                set.add(node.type)
            }
        })
        return Array.from(set).sort((a, b) => a.localeCompare(b, 'zh-CN'))
    }, [graph.nodes])

    const filteredNodes = useMemo(() => {
        const search = normalizeText(nodeKeyword)
        return graph.nodes.filter(node => {
            if (nodeTypeFilter && node.type !== nodeTypeFilter) {
                return false
            }
            if (!search) {
                return true
            }
            const label = normalizeText(node.label)
            const id = normalizeText(node.id)
            return label.includes(search) || id.includes(search)
        })
    }, [graph.nodes, nodeKeyword, nodeTypeFilter])

    const edgeTypeOptions = useMemo(() => {
        const set = new Set()
        graph.edges.forEach(edge => {
            if (edge.type) {
                set.add(edge.type)
            }
        })
        return Array.from(set).sort((a, b) => a.localeCompare(b, 'zh-CN'))
    }, [graph.edges])

    const filteredEdges = useMemo(() => {
        const visibleNodeIds = new Set(filteredNodes.map(node => node.id))
        return graph.edges.filter(edge => {
            if (!visibleNodeIds.has(edge.source) || !visibleNodeIds.has(edge.target)) {
                return false
            }
            if (edgeTypeFilter && edge.type !== edgeTypeFilter) {
                return false
            }
            return true
        })
    }, [edgeTypeFilter, filteredNodes, graph.edges])

    const isEmpty = !loading && !error && graph.nodes.length === 0 && graph.edges.length === 0
    const noMatch = !loading
        && !error
        && (graph.nodes.length > 0 || graph.edges.length > 0)
        && filteredNodes.length === 0
        && filteredEdges.length === 0

    return (
        <PageScaffold
            title="关系图谱"
            badge={loading ? '加载中' : `${filteredNodes.length} 节点 / ${filteredEdges.length} 边`}
            description="最小可用图谱视图：支持节点与边列表筛选，数据来自 /api/graph。"
        >
            {loading ? (
                <div className="loading">图谱数据加载中...</div>
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
                    <div className="empty-icon">G</div>
                    <p>当前图谱暂无节点和边数据。</p>
                </div>
            ) : null}

            {!loading && !error && !isEmpty ? (
                <>
                    <div className="card">
                        <div className="filter-group">
                            <input
                                style={CONTROL_STYLE}
                                placeholder="按节点名称或 ID 搜索"
                                value={nodeKeyword}
                                onChange={event => setNodeKeyword(event.target.value)}
                            />
                            <select
                                style={CONTROL_STYLE}
                                value={nodeTypeFilter}
                                onChange={event => setNodeTypeFilter(event.target.value)}
                            >
                                <option value="">全部节点类型</option>
                                {nodeTypeOptions.map(type => (
                                    <option key={type} value={type}>
                                        {type}
                                    </option>
                                ))}
                            </select>
                            <select
                                style={CONTROL_STYLE}
                                value={edgeTypeFilter}
                                onChange={event => setEdgeTypeFilter(event.target.value)}
                            >
                                <option value="">全部关系类型</option>
                                {edgeTypeOptions.map(type => (
                                    <option key={type} value={type}>
                                        {type}
                                    </option>
                                ))}
                            </select>
                            <span className="card-badge badge-blue">
                                原始: {graph.meta.nodeCount} 节点 / {graph.meta.edgeCount} 边
                            </span>
                        </div>
                    </div>

                    {noMatch ? (
                        <div className="card empty-state compact">
                            <p>筛选后没有匹配的节点与边。</p>
                        </div>
                    ) : (
                        <div style={PANEL_LAYOUT_STYLE}>
                            <div className="card">
                                <div className="card-header">
                                    <span className="card-title">节点列表</span>
                                    <span className="card-badge badge-green">{filteredNodes.length}</span>
                                </div>
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
                                            {filteredNodes.map(node => (
                                                <tr key={node.id}>
                                                    <td>{node.id}</td>
                                                    <td>
                                                        {node.label}
                                                        {node.isProtagonist ? ' ★' : ''}
                                                    </td>
                                                    <td>{node.type || '-'}</td>
                                                    <td>{node.tier || '-'}</td>
                                                    <td>{node.firstAppearance ?? '-'}</td>
                                                    <td>{node.lastAppearance ?? '-'}</td>
                                                </tr>
                                            ))}
                                            {filteredNodes.length === 0 ? (
                                                <tr>
                                                    <td colSpan={6}>当前筛选条件下无节点。</td>
                                                </tr>
                                            ) : null}
                                        </tbody>
                                    </table>
                                </div>
                            </div>

                            <div className="card">
                                <div className="card-header">
                                    <span className="card-title">关系边列表</span>
                                    <span className="card-badge badge-blue">{filteredEdges.length}</span>
                                </div>
                                <div className="table-wrap">
                                    <table className="data-table">
                                        <thead>
                                            <tr>
                                                <th>来源</th>
                                                <th>目标</th>
                                                <th>关系</th>
                                                <th>章节</th>
                                                <th>描述</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {filteredEdges.map(edge => (
                                                <tr key={edge.id}>
                                                    <td>{edge.source || '-'}</td>
                                                    <td>{edge.target || '-'}</td>
                                                    <td>{edge.type || '-'}</td>
                                                    <td>{edge.chapter ?? '-'}</td>
                                                    <td className="truncate">{edge.description || '-'}</td>
                                                </tr>
                                            ))}
                                            {filteredEdges.length === 0 ? (
                                                <tr>
                                                    <td colSpan={5}>当前筛选条件下无关系边。</td>
                                                </tr>
                                            ) : null}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    )}
                </>
            ) : null}
        </PageScaffold>
    )
}
