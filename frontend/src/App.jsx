import React from 'react'
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { Layout, Menu, theme } from 'antd'
import {
  DashboardOutlined,
  ExperimentOutlined,
  SettingOutlined,
  BarChartOutlined,
  DatabaseOutlined,
  RocketOutlined,
} from '@ant-design/icons'

import Dashboard from './pages/Dashboard'
import ExperimentList from './pages/ExperimentList'
import ExperimentDetail from './pages/ExperimentDetail'
import ConfigEditor from './pages/ConfigEditor'
import ModelRegistry from './pages/ModelRegistry'
import BacktestViewer from './pages/BacktestViewer'

const { Header, Sider, Content } = Layout

const menuItems = [
  { key: '/dashboard', icon: <DashboardOutlined />, label: '仪表盘' },
  { key: '/experiments', icon: <ExperimentOutlined />, label: '实验管理' },
  { key: '/config', icon: <SettingOutlined />, label: '配置编辑器' },
  { key: '/backtest', icon: <BarChartOutlined />, label: '回测分析' },
  { key: '/models', icon: <DatabaseOutlined />, label: '模型仓库' },
]

const App = () => {
  const navigate = useNavigate()
  const [collapsed, setCollapsed] = React.useState(false)
  const { token } = theme.useToken()

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        theme="dark"
        width={220}
      >
        <div style={{
          height: 64,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderBottom: '1px solid rgba(255,255,255,0.1)'
        }}>
          <RocketOutlined style={{ fontSize: 24, color: '#1890ff' }} />
          {!collapsed && (
            <span style={{ color: '#fff', fontSize: 18, fontWeight: 600, marginLeft: 8 }}>
              Qlib Studio
            </span>
          )}
        </div>

        <Menu
          theme="dark"
          mode="inline"
          defaultSelectedKeys={['/dashboard']}
          items={menuItems}
          onClick={({ key }) => navigate(key)}   // ✅ 关键修复
        />
      </Sider>

      <Layout>
        <Header className="app-header">
          <h1>
            Qlib Studio <span className="subtitle">AI 量化投资训练平台</span>
          </h1>
          <div style={{ color: 'rgba(255,255,255,0.65)', fontSize: 13 }}>
            后端状态: <span style={{ color: '#52c41a' }}>●</span> 运行中
          </div>
        </Header>

        <Content className="app-content">
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/experiments" element={<ExperimentList />} />
            <Route path="/experiments/:id" element={<ExperimentDetail />} />
            <Route path="/config" element={<ConfigEditor />} />
            <Route path="/backtest" element={<BacktestViewer />} />
            <Route path="/models" element={<ModelRegistry />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  )
}

export default App
