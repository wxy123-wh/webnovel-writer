import { useCallback, useEffect, useMemo, useState } from 'react'
import PageScaffold from '../components/PageScaffold.jsx'
import {
    classifySkillsError,
    createSkill,
    deleteSkill,
    listSkills,
    toggleSkill,
} from '../api/skills.js'

const FORM_GRID_STYLE = {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
    gap: 10,
}

const FIELD_STYLE = {
    width: '100%',
    border: '2px solid var(--border-main)',
    background: '#fff',
    color: 'var(--text-main)',
    fontFamily: 'var(--font-body)',
    fontSize: 14,
    borderRadius: 4,
    padding: '8px 10px',
}

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
        if (code === 'skill_id_conflict') {
            return `技能 ID 已存在，请使用新的 ID${codeSuffix}`
        }
        if (code === 'skill_name_conflict') {
            return `技能名称已存在，请使用新的名称${codeSuffix}`
        }
        return `存在资源冲突，请刷新后重试${codeSuffix}`
    }
    if (type === 'validation') {
        return `${error?.message || '请求参数不合法，请检查技能 ID 和名称'}${codeSuffix}`
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
    const [notice, setNotice] = useState('')
    const [busyId, setBusyId] = useState('')

    const [id, setId] = useState('')
    const [name, setName] = useState('')
    const [description, setDescription] = useState('')
    const [enabled, setEnabled] = useState(true)
    const [creating, setCreating] = useState(false)

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

    const onCreate = async event => {
        event.preventDefault()
        if (!id.trim() || !name.trim()) {
            setError({
                status: 400,
                errorCode: 'invalid_skill_form',
                message: '技能 ID 和名称不能为空',
            })
            return
        }

        setCreating(true)
        setError(null)
        setNotice('')
        try {
            await createSkill({
                id: id.trim(),
                name: name.trim(),
                description: description.trim(),
                enabled,
            })
            setNotice(`已新增技能: ${id.trim()}`)
            setId('')
            setName('')
            setDescription('')
            setEnabled(true)
            await refresh()
        } catch (err) {
            setError(err)
        } finally {
            setCreating(false)
        }
    }

    const onToggle = async skill => {
        setBusyId(skill.id)
        setError(null)
        setNotice('')
        try {
            const response = await toggleSkill({
                skillId: skill.id,
                enabled: !skill.enabled,
                reason: 'toggle-by-ui',
            })
            setSkills(current =>
                current.map(item =>
                    item.id === skill.id ? { ...item, enabled: response.enabled } : item,
                ),
            )
            setNotice(`${response.enabled ? '已启用' : '已禁用'}技能: ${skill.id}`)
        } catch (err) {
            setError(err)
        } finally {
            setBusyId('')
        }
    }

    const onDelete = async skill => {
        if (!window.confirm(`确定删除技能 ${skill.id} 吗？`)) {
            return
        }

        setBusyId(skill.id)
        setError(null)
        setNotice('')
        try {
            await deleteSkill({
                skillId: skill.id,
                hardDelete: true,
            })
            setSkills(current => current.filter(item => item.id !== skill.id))
            setNotice(`已删除技能: ${skill.id}`)
        } catch (err) {
            setError(err)
        } finally {
            setBusyId('')
        }
    }

    return (
        <PageScaffold
            title="技能管理"
            badge={`${enabledCount}/${skills.length} 已启用`}
            description="技能列表/启停/新增/删除最小闭环。"
        >
            {error ? (
                <div className="card" role="alert">
                    <div className="card-header">
                        <span className="card-title">错误反馈</span>
                        <span className="card-badge badge-red">{getErrorBadge(error)}</span>
                    </div>
                    <p style={{ margin: 0 }}>{getErrorMessage(error, '操作失败')}</p>
                </div>
            ) : null}

            {notice ? (
                <div className="card" role="status">
                    <div className="card-header">
                        <span className="card-title">操作成功</span>
                        <span className="card-badge badge-green">Success</span>
                    </div>
                    <p style={{ margin: 0 }}>{notice}</p>
                </div>
            ) : null}

            <form className="card" onSubmit={onCreate}>
                <div className="card-header">
                    <span className="card-title">新增技能</span>
                    <button className="page-btn" type="submit" disabled={creating}>
                        {creating ? '提交中...' : '新增'}
                    </button>
                </div>
                <div style={FORM_GRID_STYLE}>
                    <label>
                        <span>ID</span>
                        <input
                            style={FIELD_STYLE}
                            value={id}
                            onChange={event => setId(event.target.value)}
                            placeholder="outline.splitter"
                            required
                        />
                    </label>
                    <label>
                        <span>名称</span>
                        <input
                            style={FIELD_STYLE}
                            value={name}
                            onChange={event => setName(event.target.value)}
                            placeholder="Outline Splitter"
                            required
                        />
                    </label>
                    <label>
                        <span>描述</span>
                        <input
                            style={FIELD_STYLE}
                            value={description}
                            onChange={event => setDescription(event.target.value)}
                            placeholder="可选"
                        />
                    </label>
                    <label>
                        <span>默认状态</span>
                        <select
                            style={FIELD_STYLE}
                            value={enabled ? 'enabled' : 'disabled'}
                            onChange={event => setEnabled(event.target.value === 'enabled')}
                        >
                            <option value="enabled">enabled</option>
                            <option value="disabled">disabled</option>
                        </select>
                    </label>
                </div>
            </form>

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
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            {loading ? (
                                <tr>
                                    <td colSpan={7}>加载中...</td>
                                </tr>
                            ) : null}
                            {!loading && skills.length === 0 ? (
                                <tr>
                                    <td colSpan={7}>暂无技能，先创建一个。</td>
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
                                          <td>
                                              <div className="filter-group" style={{ marginBottom: 0 }}>
                                                  <button
                                                      type="button"
                                                      className="page-btn"
                                                      disabled={busyId === skill.id}
                                                      onClick={() => void onToggle(skill)}
                                                  >
                                                      {skill.enabled ? '禁用' : '启用'}
                                                  </button>
                                                  <button
                                                      type="button"
                                                      className="page-btn"
                                                      disabled={busyId === skill.id}
                                                      onClick={() => void onDelete(skill)}
                                                  >
                                                      删除
                                                  </button>
                                              </div>
                                          </td>
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
