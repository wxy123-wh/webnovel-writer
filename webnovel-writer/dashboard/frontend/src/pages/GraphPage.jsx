import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import ForceGraph3D from 'react-force-graph-3d'
import * as THREE from 'three'
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

const GRAPH_FRAME_STYLE = {
    height: 500,
    border: '2px solid var(--border-soft)',
    background: '#faf8f5',
    overflow: 'hidden',
}

const GRAPH_HEADER_META_STYLE = {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    flexWrap: 'wrap',
}

const GRAPH_HINT_STYLE = {
    marginTop: 10,
    fontSize: 13,
    color: 'var(--text-sub)',
}

const GRAPH_EMPTY_STYLE = {
    height: '100%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: 'var(--text-sub)',
    fontSize: 14,
    fontWeight: 600,
}

const NODE_TYPE_COLORS = {
    角色: '#e74c3c',
    地点: '#2ecc71',
    物品: '#3498db',
    势力: '#f39c12',
    unknown: '#95a5a6',
}

const NODE_TIER_SIZE = {
    核心: 8,
    重要: 5,
    次要: 3,
    装饰: 2,
}

const CANVAS_FONT_FAMILY = '"Noto Sans SC", "Microsoft YaHei", "Segoe UI", sans-serif'

function normalizeText(value) {
    return (value || '').toString().trim().toLowerCase()
}

function getNodeColor(type) {
    return NODE_TYPE_COLORS[type] || NODE_TYPE_COLORS.unknown
}

function getNodeSize(tier) {
    return NODE_TIER_SIZE[tier] || 3
}

function createTextSprite(label) {
    const canvas = document.createElement('canvas')
    const context = canvas.getContext('2d')
    const fontSize = 28
    const paddingX = 12
    const paddingY = 8

    context.font = `600 ${fontSize}px ${CANVAS_FONT_FAMILY}`
    const textWidth = context.measureText(label).width
    canvas.width = Math.ceil(textWidth + paddingX * 2)
    canvas.height = Math.ceil(fontSize + paddingY * 2)

    context.font = `600 ${fontSize}px ${CANVAS_FONT_FAMILY}`
    context.fillStyle = 'rgba(255, 253, 246, 0.94)'
    context.fillRect(0, 0, canvas.width, canvas.height)
    context.fillStyle = '#2a220f'
    context.textBaseline = 'middle'
    context.fillText(label, paddingX, canvas.height / 2)

    const texture = new THREE.CanvasTexture(canvas)
    texture.needsUpdate = true

    const spriteMaterial = new THREE.SpriteMaterial({
        map: texture,
        transparent: true,
        depthWrite: false,
        depthTest: false,
    })
    const sprite = new THREE.Sprite(spriteMaterial)
    sprite.scale.set(canvas.width / 18, canvas.height / 18, 1)
    return sprite
}

function createNodeObject(node) {
    const radius = Math.max(2, Number(node.val) || 3)
    const group = new THREE.Group()
    const sphere = new THREE.Mesh(
        new THREE.SphereGeometry(radius, 18, 18),
        new THREE.MeshLambertMaterial({ color: getNodeColor(node.type) }),
    )
    const label = createTextSprite(node.name || node.id || '')
    label.position.set(0, radius + 8, 0)
    group.add(sphere)
    group.add(label)
    return group
}

export default function GraphPage() {
    const [graph, setGraph] = useState({ nodes: [], edges: [], meta: { nodeCount: 0, edgeCount: 0 } })
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')
    const [nodeKeyword, setNodeKeyword] = useState('')
    const [nodeTypeFilter, setNodeTypeFilter] = useState('')
    const [edgeTypeFilter, setEdgeTypeFilter] = useState('')
    const [showTableView, setShowTableView] = useState(false)
    const [graphSize, setGraphSize] = useState({ width: 960, height: 500 })
    const graphContainerRef = useRef(null)

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

    useEffect(() => {
        const container = graphContainerRef.current
        if (!container) {
            return undefined
        }

        const updateSize = () => {
            const nextWidth = Math.max(container.clientWidth, 320)
            setGraphSize(prev => {
                if (prev.width === nextWidth && prev.height === 500) {
                    return prev
                }
                return { width: nextWidth, height: 500 }
            })
        }

        updateSize()

        if (typeof ResizeObserver === 'undefined') {
            window.addEventListener('resize', updateSize)
            return () => {
                window.removeEventListener('resize', updateSize)
            }
        }

        const observer = new ResizeObserver(() => {
            updateSize()
        })
        observer.observe(container)

        return () => {
            observer.disconnect()
        }
    }, [])

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

    const graphData = useMemo(() => ({
        nodes: filteredNodes.map(node => ({
            id: node.id,
            name: node.label,
            type: node.type || 'unknown',
            tier: node.tier,
            val: getNodeSize(node.tier),
        })),
        links: filteredEdges.map(edge => ({
            source: edge.source,
            target: edge.target,
            type: edge.type,
        })),
    }), [filteredEdges, filteredNodes])

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
            description="交互式力导向图谱视图：支持节点、关系和关键词筛选，数据来自 /api/graph。"
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
                            <button
                                type="button"
                                className="page-btn"
                                onClick={() => setShowTableView(value => !value)}
                            >
                                {showTableView ? '隐藏表格视图' : '显示表格视图'}
                            </button>
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
                        <>
                            <div className="card">
                                <div className="card-header">
                                    <div style={GRAPH_HEADER_META_STYLE}>
                                        <span className="card-title">力导向关系图</span>
                                        <span className="card-badge badge-green">{graphData.nodes.length} 节点</span>
                                        <span className="card-badge badge-blue">{graphData.links.length} 边</span>
                                    </div>
                                    <span className="card-badge badge-amber">拖拽 / 缩放 / 悬停</span>
                                </div>
                                <div ref={graphContainerRef} style={GRAPH_FRAME_STYLE}>
                                    {graphData.nodes.length > 0 ? (
                                        <ForceGraph3D
                                            width={graphSize.width}
                                            height={graphSize.height}
                                            graphData={graphData}
                                            backgroundColor="#faf8f5"
                                            nodeLabel={node => node.name}
                                            nodeColor={node => getNodeColor(node.type)}
                                            nodeVal={node => node.val}
                                            linkColor={() => '#999'}
                                            linkDirectionalArrowLength={3}
                                            linkWidth={1.4}
                                            linkOpacity={0.55}
                                            nodeOpacity={1}
                                            showNavInfo={false}
                                            enableNodeDrag
                                            warmupTicks={80}
                                            cooldownTicks={120}
                                            nodeThreeObject={node => createNodeObject(node)}
                                        />
                                    ) : (
                                        <div style={GRAPH_EMPTY_STYLE}>当前筛选条件下无可绘制节点。</div>
                                    )}
                                </div>
                                <p style={GRAPH_HINT_STYLE}>
                                    节点颜色按实体类型区分，节点大小按层级区分；可拖拽旋转、缩放并悬停查看关系。
                                </p>
                            </div>

                            {showTableView ? (
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
                            ) : null}
                        </>
                    )}
                </>
            ) : null}
        </PageScaffold>
    )
}
