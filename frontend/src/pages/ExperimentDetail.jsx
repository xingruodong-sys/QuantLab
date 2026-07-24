import React, { useEffect, useState, useCallback } from 'react'
import {
  Card, Tabs, Button, Descriptions, Tag, Space, message,
  Statistic, Row, Col, Empty, Spin, Divider
} from 'antd'
import {
  PlayCircleOutlined, StopOutlined, ReloadOutlined,
  BarChartOutlined, LineChartOutlined, FileTextOutlined,
  ArrowLeftOutlined,
} from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import {
  getExperiment, startExperiment, stopExperiment,
  getLogs, getMetrics, getPortfolio
} from '../api'
import { useParams, useNavigate } from 'react-router-dom'

const { TabPane } = Tabs

export default function ExperimentDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [exp, setExp] = useState(null)
  const [logs, setLogs] = useState('')
  const [metrics, setMetrics] = useState(null)
  const [portfolio, setPortfolio] = useState(null)
  const [loading, setLoading] = useState(true)
  const [logRefreshing, setLogRefreshing] = useState(false)

  const fetchDetail = useCallback(async () => {
    try {
      const data = await getExperiment(id)
      setExp(data)
    } catch (err) {
      message.error('获取实验详情失败')
    }
  }, [id])

  const fetchLogs = useCallback(async () => {
    try {
      const data = await getLogs(id, 300)
      setLogs(data.logs || '')
    } catch (err) {
      // ignore
    }
  }, [id])

  const fetchMetrics = useCallback(async () => {
    try {
      const data = await getMetrics(id)
      setMetrics(data)
    } catch (err) {
      // ignore
    }
  }, [id])

  const fetchPortfolio = useCallback(async () => {
    try {
      const data = await getPortfolio(id)
      setPortfolio(data)
    } catch (err) {
      // ignore
    }
  }, [id])

  useEffect(() => {
    const loadAll = async () => {
      setLoading(true)
      await Promise.all([fetchDetail(), fetchLogs(), fetchMetrics(), fetchPortfolio()])
      setLoading(false)
    }
    loadAll()

    // 运行中自动刷新
    const timer = setInterval(() => {
      fetchDetail()
      fetchLogs()
      fetchMetrics()
      fetchPortfolio()
    }, 8000)
    return () => clearInterval(timer)
  }, [fetchDetail, fetchLogs, fetchMetrics, fetchPortfolio])

  const handleStart = async () => {
    try {
      await startExperiment(id)
      message.success('实验已启动')
      fetchDetail()
    } catch (err) {
      message.error('启动失败')
    }
  }

  const handleStop = async () => {
    try {
      await stopExperiment(id)
      message.success('实验已停止')
      fetchDetail()
    } catch (err) {
      message.error('停止失败')
    }
  }

  if (loading && !exp) {
    return <div style={{ textAlign: 'center', padding: 100 }}><Spin size="large" /></div>
  }

  // 净值曲线配置
  const chartOption = portfolio ? {
    title: { text: '组合净值曲线', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: portfolio.dates,
      axisLabel: { rotate: 45, fontSize: 10 }
    },
    yAxis: { type: 'value', scale: true },
    series: [{
      name: '组合净值',
      type: 'line',
      data: portfolio.portfolio_value,
      smooth: true,
      lineStyle: { color: '#1890ff', width: 2 },
      areaStyle: { color: 'rgba(24,144,255,0.1)' },
    }],
    grid: { left: 60, right: 20, bottom: 60, top: 50 },
  } : null

  // 指标展示
  const metricItems = metrics && typeof metrics === 'object' && !metrics.message ? (
    Object.entries(metrics).slice(0, 12).map(([key, value]) => (
      <Col xs={12} sm={8} md={6} key={key}>
        <Card size="small" className="metric-card">
          <div className="metric-value">
            {typeof value === 'number' ? value.toFixed(4) : String(value)}
          </div>
          <div className="metric-label">{key}</div>
        </Card>
      </Col>
    ))
  ) : (
    <Col span={24}><Empty description="暂无指标数据" /></Col>
  )

  return (
    <div>
      {/* 头部信息 */}
      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/experiments')}
                    style={{ marginBottom: 12 }}>返回列表</Button>
            <h2 style={{ margin: '8px 0' }}>{exp?.name || id}</h2>
            <Space>
              <Tag color={
                exp?.status === 'running' ? 'blue' :
                exp?.status === 'completed' ? 'green' :
                exp?.status === 'failed' ? 'red' : 'default'
              }>
                {exp?.status || 'unknown'}
              </Tag>
              {(exp?.tags || []).map(tag => <Tag key={tag}>{tag}</Tag>)}
            </Space>
          </div>
          <Space>
            {exp?.status !== 'running' && exp?.status !== 'iterating' && (
              <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleStart}>
                启动
              </Button>
            )}
            {(exp?.status === 'running' || exp?.status === 'iterating') && (
              <Button danger icon={<StopOutlined />} onClick={handleStop}>
                停止
              </Button>
            )}
            <Button icon={<ReloadOutlined />} onClick={() => {
              fetchDetail(); fetchLogs(); fetchMetrics(); fetchPortfolio()
            }}>
              刷新
            </Button>
          </Space>
        </div>
      </Card>

      <Tabs defaultActiveKey="overview">
        {/* 概览 */}
        <TabPane tab="概览" key="overview">
          <Row gutter={[16, 16]}>
            {metricItems}
          </Row>
          {chartOption && (
            <Card title="净值曲线" style={{ marginTop: 16 }}>
              <ReactECharts option={chartOption} style={{ height: 350 }} />
            </Card>
          )}
        </TabPane>

        {/* 配置 */}
        <TabPane tab="配置" key="config">
          <Card title="完整配置" extra={<FileTextOutlined />}>
            <pre style={{
              background: '#f5f5f5', padding: 16, borderRadius: 6,
              fontSize: 12, maxHeight: 500, overflow: 'auto'
            }}>
              {JSON.stringify(exp?.config, null, 2)}
            </pre>
          </Card>
        </TabPane>

        {/* 日志 */}
        <TabPane tab="训练日志" key="logs">
          <Card title="实时日志" extra={
            <Button size="small" onClick={fetchLogs} loading={logRefreshing}>刷新</Button>
          }>
            <div className="log-viewer">
              {logs || '暂无日志输出'}
            </div>
          </Card>
        </TabPane>

        {/* 指标详情 */}
        <TabPane tab="回测指标" key="metrics">
          <Card title="详细指标">
            {metrics && typeof metrics === 'object' ? (
              <Descriptions bordered column={2} size="small">
                {Object.entries(metrics).map(([k, v]) => (
                  <Descriptions.Item key={k} label={k}>
                    {typeof v === 'number' ? v.toFixed(6) : String(v)}
                  </Descriptions.Item>
                ))}
              </Descriptions>
            ) : (
              <Empty description="指标尚未生成" />
            )}
          </Card>
        </TabPane>
      </Tabs>
    </div>
  )
}
