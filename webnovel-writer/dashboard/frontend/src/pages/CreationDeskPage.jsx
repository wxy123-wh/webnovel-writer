import PageScaffold from '../components/PageScaffold.jsx'

export default function CreationDeskPage() {
    return (
        <PageScaffold title="创作台" badge="Coming Soon">
            <div className="card">
                <div className="card-header">
                    <span className="card-title">创作台 — coming soon</span>
                </div>
                <p style={{ margin: 0, color: '#5d5035' }}>
                    创作台功能即将上线，敬请期待。
                </p>
            </div>
        </PageScaffold>
    )
}
