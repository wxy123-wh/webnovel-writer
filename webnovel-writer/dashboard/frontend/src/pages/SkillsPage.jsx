import { useCallback, useEffect, useMemo, useState } from 'react'
import PageScaffold from '../components/PageScaffold.jsx'
import {
    classifySkillsError,
    listSkills,
} from '../api/skills.js'

function getErrorMessage(error, fallback = '请求失败') {
    const type = classifySkillsError(error)
    const code = error?.errorCode || error?.error_code || ''
    const codeSuffix = code ? ` (${code})` : ''

    if (type === 'network') {
        return `网络连接失败，请检查服务状态后重试${codeSuffix}`
    }
    if (type === 'permission') {
        return `权限不足或工作区不匹配，请确认当前工作区配置${codeSuffix}`
    }
    if (type === 'conflict') {
        return `存在资源冲突，请刷新后重试${codeSuffix}`
    }
    if (type === 'validation') {
        return `${error?.message || '请求参数不合法'}${codeSuffix}`
    }
    return `${error?.message || fallback}${codeSuffix}`
}

function getErrorBadge(error) {
    const type = classifySkillsError(error)
    if (type === 'network') return '网络错误'
    if (type === 'permission') return '权限错误'
    if (type === 'conflict') return '冲突错误'
    if (type === 'validation') return '参数错误'
    return '请求错误'
}

function formatDateTime(value) {
    if (!value) return '-'
    const parsed = new Date(value)
    if (Number.isNaN(parsed.getTime())) return String(value)
    return parsed.toLocaleString()
}

export default function SkillsPage() {
    const [skills, setSkills] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)

    const refresh = useCallback(async () => {
        setLoading(true)
        setError(null)
        try {
            const response = await listSkills()
            setSkills(response.items)
        } catch (err) {
            setError(err)
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        void refresh()
    }, [refresh])

    const enabledCount = useMemo(
        () => skills.filter(skill => skill.enabled).length,
        [skills],
    )

    return (
        <PageScaffold
            title="技能管理"
            badge={`${enabledCount}/${skills.length} 已启用`}
            description="[只读展示模式] 技能列表查看。技能管理请通过 CLI 命令执行。"
        >
            <div className="card" style={{ background: '#fff8e6', borderColor: '#d4a574' }}>
                <div className="card-header">
                    <span className="card-title">📋 只读展示模式</span>
                    <span className="card-badge badge-amber">Read-Only</span>
                </div>
                <p style={{ margin: 0, color: '#5d5035' }}>
                    此页面为只读展示。技能的创建、启停、删除等操作已移至 CLI 命令。
                    请使用 <code>webnovel codex session start --profile &lt;profile&gt;</code> 来管理会话级技能。
                </p>
            </div>

            {error ? (
                <div className="card" role="alert">
                    <div className="card-header">
                        <span className="card-title">错误反馈</span>
                        <span className="card-badge badge-red">{getErrorBadge(error)}</span>
                    </div>
                    <p style={{ margin: 0 }}>{getErrorMessage(error, '操作失败')}</p>
                </div>
            ) : null}

            <div className="card">
                <div className="card-header">
                    <span className="card-title">Skills Registry</span>
                    <button className="page-btn" onClick={() => void refresh()} disabled={loading}>
                        {loading ? '加载中...' : '刷新'}
                    </button>
                </div>
                <div className="table-wrap">
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>名称</th>
                                <th>描述</th>
                                <th>状态</th>
                                <th>作用域</th>
                                <th>更新时间</th>
                            </tr>
                        </thead>
                        <tbody>
                            {loading ? (
                                <tr>
                                    <td colSpan={6}>加载中...</td>
                                </tr>
                            ) : null}
                            {!loading && skills.length === 0 ? (
                                <tr>
                                    <td colSpan={6}>暂无技能。</td>
                                </tr>
                            ) : null}
                            {!loading
                                ? skills.map(skill => (
                                      <tr key={skill.id}>
                                          <td>{skill.id}</td>
                                          <td>{skill.name}</td>
                                          <td>{skill.description || '-'}</td>
                                          <td>{skill.enabled ? 'enabled' : 'disabled'}</td>
                                          <td>{skill.scope || 'workspace'}</td>
                                          <td>{formatDateTime(skill.updated_at)}</td>
                                      </tr>
                                  ))
                                : null}
                        </tbody>
                    </table>
                </div>
            </div>
        </PageScaffold>
    )
}
