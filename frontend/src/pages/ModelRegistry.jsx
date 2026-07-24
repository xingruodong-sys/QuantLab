import React, { useEffect, useState } from 'react'
import { Card, Table, Button, Tag, Input, message, Modal } from 'antd'
import { DatabaseOutlined, AppstoreAddOutlined } from '@ant-design/icons'
import { listModels, registerModel } from '../api'

export default function ModelRegistry() {
  const [models, setModels] = useState([])
  const [loading, setLoading] = useState(false)

  const fetchModels = async () => {
    setLoading(true)
    try {
      const res = await listModels()
      setModels(res.models || [])
    } catch (err) {
      message.error('获取模型列表失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchModels() }, [])

  const handleRegister = (expId, currentName) => {
    Modal.confirm({
      title: '注册模型',
      content: (
        <div>
          <p>为实验 {expId} 的模型命名：</p>
          <Input defaultValue={currentName || expId} id="model-name-input" />
        </div>
      ),
      onOk: async () => {
        const name = document.getElementById('model-name-input').value
        if (!name) {
          message.warning('请输入模型名称')
          return
        }
        try {
          await registerModel(expId, name)
          message.success(`模型 ${name} 注册成功`)
          fetchModels()
        } catch (err) {
          message.error('注册失败: ' + err.message)
        }
      },
    })
  }

  const columns = [
    { title: '实验ID', dataIndex: 'exp_id', key: 'exp_id' },
    { title: '模型名称', dataIndex: 'experiment_name', key: 'experiment_name' },
    { title: '模型类型', dataIndex: 'model_type', key: 'model_type',
      render: (t) => <Tag color="blue">{t || 'N/A'}</Tag> },
    { title: '文件大小(MB)', dataIndex: 'size_mb', key: 'size_mb' },
    { title: '路径', dataIndex: 'path', key: 'path', ellipsis: true },
    {
      title: '操作', key: 'actions', width: 120,
      render: (_, record) => (
        <Button type="link" icon={<AppstoreAddOutlined />}
                onClick={() => handleRegister(record.exp_id, record.experiment_name)}>
          注册
        </Button>
      ),
    },
  ]

  return (
    <Card title={<><DatabaseOutlined /> 模型仓库</>}>
      <Table
        columns={columns}
        dataSource={models}
        rowKey="exp_id"
        loading={loading}
        pagination={{ pageSize: 20 }}
      />
    </Card>
  )
}
