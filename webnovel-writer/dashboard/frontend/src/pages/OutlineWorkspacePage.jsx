import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import PageScaffold from '../components/PageScaffold.jsx'
import {
    fetchOutlineBundle,
    fetchOutlineSplitHistory,
    formatOutlineApiError,
} from '../api/outlines.js'

const DUAL_LAYOUT_STYLE = {
    display: 'grid',
    gap: 14,
    gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)',
}

const TEXTAREA_STYLE = {
    width: '100%',
    minHeight: 260,
    borderRadius: 8,
    border: '2px solid #8f7f5c',
    background: '#fff',
    color: '#2a220f',
    fontSize: 13,
    lineHeight: 1.6,
    padding: 10,
    resize: 'vertical',
    fontFamily: 'inherit',
    cursor: 'default',
}

const BUTTON_STYLE = {
    border: '2px solid #2a220f',
    background: '#fff8e6',
    color: '#2a220f',
    fontSize: 13,
    fontWeight: 600,
    padding: '4px 10px',
    cursor: 'pointer',
}

function createOutlineWorkspace() {
    return {
        workspace_id: 'outline-workspace-readonly',
        project_root: process.env.REACT_APP_PROJECT_ROOT || '',
    }
}

export default function OutlineWorkspacePage() {
    const workspace = useMemo(() => createOutlineWorkspace(), [])

    const [errorMessage, setErrorMessage] = useState('')
    const [totalOutline, setTotalOutline] = useState('')
    const [detailedOutline, setDetailedOutline] = useState('')
    const [splitHistory, setSplitHistory] = useState([])
    const [loadingBundle, setLoadingBundle] = useState(true)

    const refreshBundle = useCallback(async () => {
        setLoadingBundle(true)
        setErrorMessage('')
        try {
            const [bundle, history] = await Promise.all([
                fetchOutlineBundle({
                    workspaceId: workspace.workspace_id,
                    projectRoot: workspace.project_root,
                }),
                fetchOutlineSplitHistory({
                    workspaceId: workspace.workspace_id,
                    projectRoot: workspace.project_root,
                    limit: 20,
                    offset: 0,
                }),
            ])
            setTotalOutline(bundle.total_outline || '')
            setDetailedOutline(bundle.detailed_outline || '')
            setSplitHistory(Array.isArray(history.items) ? history.items : [])
        } catch (error) {
            setErrorMessage(formatOutlineApiError(error))
        } finally {
            setLoadingBundle(false)
        }
    }, [workspace.project_root, workspace.workspace_id])

    useEffect(() => {
        void refreshBundle()
    }, [refreshBundle])

    const splitCountBadge = useMemo(() => {
        if (loadingBundle) {
            return '加载中'
        }
        return `${splitHistory.length} 条拆分记录`
    }, [loadingBundle, splitHistory.length])

    return (
        <PageScaffold
            title="双纲工作台"
            badge="Outline Workspace"
            description="[只读展示模式] 查看总纲和细纲。编辑操作请通过 Codex 直接修改文件。"
        >
            <div className="card" style={{ background: '#fff8e6', borderColor: '#d4a574' }}>
                <div className="card-header">
                    <span className="card-title">📋 只读展示模式</span>
                    <span className="card-badge badge-amber">Read-Only</span>
                </div>
                <p style={{ margin: 0, color: '#5d5035' }}>
                    此页面为只读展示。大纲的拆分、重拆、协助修改等操作已移至 CLI 命令和 Codex 直接编辑。
                    请使用 <code>webnovel codex</code> 命令来管理大纲。
                </p>
            </div>

            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button type="button" style={BUTTON_STYLE} disabled={loadingBundle} onClick={refreshBundle}>
                    刷新双纲数据
                </button>
                <span className="card-badge badge-green">mode: Read-Only</span>
                <span className="card-badge badge-blue">{splitCountBadge}</span>
            </div>

            {errorMessage ? (
                <div className="card" style={{ borderColor: '#d46a57' }}>
                    <div className="card-header">
                        <span className="card-title">请求失败</span>
                        <span className="card-badge badge-amber">可重试</span>
                    </div>
                    <p style={{ margin: 0, color: '#9a2a1a' }}>{errorMessage}</p>
                </div>
            ) : null}

            <div style={DUAL_LAYOUT_STYLE}>
                <div className="card">
                    <div className="card-header">
                        <span className="card-title">总纲区</span>
                        <span className="card-badge badge-green">Read-Only</span>
                    </div>
                    <textarea
                        value={totalOutline}
                        style={TEXTAREA_STYLE}
                        readOnly
                    />
                    <p style={{ margin: '8px 0 0 0', fontSize: 12, color: '#8f7f5c' }}>
                        提示: 编辑总纲请使用 Codex 直接修改文件。
                    </p>
                </div>

                <div className="card">
                    <div className="card-header">
                        <span className="card-title">细纲区</span>
                        <span className="card-badge badge-blue">Read-Only</span>
                    </div>
                    <textarea
                        value={detailedOutline}
                        style={TEXTAREA_STYLE}
                        readOnly
                    />
                    <p style={{ margin: '8px 0 0 0', fontSize: 12, color: '#8f7f5c' }}>
                        提示: 编辑细纲请使用 Codex 直接修改文件。
                    </p>
                </div>
            </div>

            <div className="card">
                <div className="card-header">
                    <span className="card-title">拆分历史</span>
                    <span className="card-badge badge-blue">{splitHistory.length} 条记录</span>
                </div>
                {splitHistory.length === 0 ? (
                    <p style={{ margin: 0, color: '#8f7f5c' }}>暂无拆分记录。</p>
                ) : (
                    <div className="table-wrap">
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>ID</th>
                                    <th>时间</th>
                                    <th>段数</th>
                                    <th>状态</th>
                                </tr>
                            </thead>
                            <tbody>
                                {splitHistory.map(record => (
                                    <tr key={record.id}>
                                        <td>{record.id}</td>
                                        <td>{record.created_at || '-'}</td>
                                        <td>{record.segment_count || 0}</td>
                                        <td>{record.status || 'unknown'}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </PageScaffold>
    )
}
