import React, { useEffect, useState } from 'react'
import { Card, Row, Col, Statistic, Button, List, Tag, Empty, Space } from 'antd'
import {
  ExperimentOutlined,
  PlayCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  PlusOutlined,
  RocketOutlined,
} from '@ant-design/icons'
import { getSystemStatus, listExperiments, getDefaultConfig } from '../api'
import { useNavigate } from 'react-router-dom'

export default function Dashboard() {
  const [status, setStatus] = useState(null)
  const [experiments, setExperiments] = useState([])
  const navigate = useNavigate()

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [sysRes, expRes] = await Promise.all([
          getSystemStatus(),
          listExperiments({ limit: 5 }),
        ])
        setStatus(sysRes)
        setExperiments(expRes.experiments || [])
      } catch (err) {
        console.error('Failed to fetch dashboard data:', err)
      }
    }
    fetchData()
    const timer = setInterval(fetchData, 10000) // 每10秒刷新
    return () => clearInterval(timer)
  }, [])

  const runningCount = experiments.filter(e => e.status === 'running').length
  const completedCount = experiments.filter(e => e.status === 'completed').length
  const failedCount = experiments.filter(e => e.status === 'failed').length

  return (
    <div>
      <Row gutter={[16, 16]}>
        {/* 核心指标卡片 */}
        <Col xs={24} sm={12} md={6}>
          <Card className="dashboard-stat" hoverable>
            <Statistic
              title="运行中实验"
              value={runningCount}
              valueStyle={{ color: '#1890ff' }}
              prefix={<PlayCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card className="dashboard-stat" hoverable>
            <Statistic
              title="已完成实验"
              value={completedCount}
              valueStyle={{ color: '#52c41a' }}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card className="dashboard-stat" hoverable>
            <Statistic
              title="失败实验"
              value={failedCount}
              valueStyle={{ color: '#ff4d4f' }}
              prefix={<CloseCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card className="dashboard-stat" hoverable>
            <Statistic
              title="总实验数"
              value={experiments.length}
              valueStyle={{ color: '#722ed1' }}
              prefix={<ExperimentOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        {/* 快速操作 */}
        <Col xs={24} md={12}>
          <Card title="快速操作" extra={<RocketOutlined />}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                size="large"
                block
                onClick={() => navigate('/config')}
              >
                创建新实验
              </Button>
              <Button
                icon={<ExperimentOutlined />}
                size="large"
                block
                onClick={() => navigate('/experiments')}
              >
                查看所有实验
              </Button>
            </Space>
          </Card>
        </Col>

        {/* 最近实验 */}
        <Col xs={24} md={12}>
          <Card title="最近实验" extra={<a onClick={() => navigate('/experiments')}>查看全部</a>}>
            {experiments.length === 0 ? (
              <Empty description="暂无实验，去创建一个吧！" />
            ) : (
              <List
                dataSource={experiments.slice(0, 5)}
                renderItem={(item) => (
                  <List.Item
                    onClick={() => navigate(`/experiments/${item.id}`)}
                    style={{ cursor: 'pointer' }}
                    actions={[
                      <Tag color={
                        item.status === 'running' ? 'blue' :
                        item.status === 'completed' ? 'green' :
                        item.status === 'failed' ? 'red' : 'default'
                      }>
                        {item.status}
                      </Tag>
                    ]}
                  >
                    <List.Item.Meta
                      title={item.name || item.id}
                      description={`创建时间: ${item.created_at || 'N/A'}`}
                    />
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>
      </Row>

      {/* 系统信息 */}
      {status && (
        <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
          <Col span={24}>
            <Card title="系统信息">
              <Row gutter={16}>
                <Col span={6}>
                  <Statistic title="磁盘总量" value={status.disk_usage?.total_gb} suffix="GB" />
                </Col>
                <Col span={6}>
                  <Statistic title="已用空间" value={status.disk_usage?.used_gb} suffix="GB"
                           valueStyle={{ color: '#faad14' }} />
                </Col>
                <Col span={6}>
                  <Statistic title="剩余空间" value={status.disk_usage?.free_gb} suffix="GB"
                           valueStyle={{ color: '#52c41a' }} />
                </Col>
                <Col span={6}>
                  <Statistic title="Qlib 数据路径" value={status.qlib_data_path} />
                </Col>
              </Row>
            </Card>
          </Col>
        </Row>
      )}
    </div>
  )
}
