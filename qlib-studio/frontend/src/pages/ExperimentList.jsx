import React, { useEffect, useState } from 'react'
import {
  Table, Button, Tag, Space, Modal, message, Input, Select,
  Popconfirm, Empty, Tooltip
} from 'antd'
import {
  PlusOutlined, PlayCircleOutlined, StopOutlined, DeleteOutlined,
  EyeOutlined, ReloadOutlined, ExperimentOutlined
} from '@ant-design/icons'
import { listExperiments, startExperiment, stopExperiment, deleteExperiment } from '../api'
import { useNavigate } from 'react-router-dom'

const statusColors = {
  created: 'default',
  running: 'processing',
  completed: 'success',
  failed: 'error',
  stopped: 'warning',
  iterating: 'processing',
}

export default function ExperimentList() {
  const [experiments, setExperiments] = useState([])
  const [loading, setLoading] = useState(false)
  const [filter, setFilter] = useState('all')
  const [search, setSearch] = useState('')
  const navigate = useNavigate()

  const fetchExperiments = async () => {
    setLoading(true)
    try {
      const params = {}
      if (filter !== 'all') params.status = filter
      const res = await listExperiments(params)
      setExperiments(res.experiments || [])
    } catch (err) {
      message.error('获取实验列表失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchExperiments()
  }, [filter])

  // 自动刷新运行中实验
  useEffect(() => {
    const hasRunning = experiments.some(e => e.status === 'running' || e.status === 'iterating')
    if (hasRunning) {
      const timer = setInterval(fetchExperiments, 5000)
      return () => clearInterval(timer)
    }
  }, [experiments])

  const handleStart = async (expId) => {
    try {
      await startExperiment(expId)
      message.success(`实验 ${expId} 已启动`)
      fetchExperiments()
    } catch (err) {
      message.error('启动失败: ' + err.message)
    }
  }

  const handleStop = async (expId) => {
    try {
      await stopExperiment(expId)
      message.success(`实验 ${expId} 已停止`)
      fetchExperiments()
    } catch (err) {
      message.error('停止失败')
    }
  }

  const handleDelete = async (expId) => {
    try {
      await deleteExperiment(expId)
      message.success(`实验 ${expId} 已删除`)
      fetchExperiments()
    } catch (err) {
      message.error('删除失败')
    }
  }

  const filteredData = experiments.filter(e =>
    !search || (e.name || e.id).toLowerCase().includes(search.toLowerCase())
  )

  const columns = [
    {
      title: '实验名称',
      dataIndex: 'name',
      key: 'name',
      render: (text, record) => (
        <a onClick={() => navigate(`/experiments/${record.id}`)}>
          <ExperimentOutlined /> {text || record.id}
        </a>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status) => <Tag color={statusColors[status] || 'default'}>{status}</Tag>,
    },
    {
      title: '标签',
      dataIndex: 'tags',
      key: 'tags',
      width: 150,
      render: (tags) => (
        <Space>
          {(tags || []).map(tag => <Tag key={tag}>{tag}</Tag>)}
        </Space>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 200,
    },
    {
      title: '操作',
      key: 'actions',
      width: 280,
      render: (_, record) => (
        <Space>
          <Tooltip title="查看详情">
            <Button icon={<EyeOutlined />} size="small"
                    onClick={() => navigate(`/experiments/${record.id}`)} />
          </Tooltip>
          {record.status !== 'running' && record.status !== 'iterating' && (
            <Tooltip title="启动">
              <Button type="primary" icon={<PlayCircleOutlined />} size="small"
                      onClick={() => handleStart(record.id)} />
            </Tooltip>
          )}
          {(record.status === 'running' || record.status === 'iterating') && (
            <Tooltip title="停止">
              <Button danger icon={<StopOutlined />} size="small"
                      onClick={() => handleStop(record.id)} />
            </Tooltip>
          )}
          <Popconfirm title="确认删除？" onConfirm={() => handleDelete(record.id)}>
            <Tooltip title="删除">
              <Button danger icon={<DeleteOutlined />} size="small" />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
        <Space>
          <Select
            value={filter}
            onChange={setFilter}
            style={{ width: 140 }}
            options={[
              { value: 'all', label: '全部状态' },
              { value: 'running', label: '运行中' },
              { value: 'completed', label: '已完成' },
              { value: 'failed', label: '失败' },
              { value: 'created', label: '已创建' },
            ]}
          />
          <Input.Search
            placeholder="搜索实验名称"
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ width: 250 }}
          />
        </Space>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchExperiments}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/config')}>
            新建实验
          </Button>
        </Space>
      </div>

      <Table
        columns={columns}
        dataSource={filteredData}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 15, showTotal: (t) => `共 ${t} 个实验` }}
        locale={{ emptyText: <Empty description="暂无实验" /> }}
      />
    </div>
  )
}
