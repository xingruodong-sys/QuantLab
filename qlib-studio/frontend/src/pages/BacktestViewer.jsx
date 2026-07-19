import React, { useEffect, useState } from 'react'
import {
  Card, Select, Button, Row, Col, Statistic, Table, message, Space
} from 'antd'
import { BarChartOutlined, ReloadOutlined } from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import { listExperiments, compareExperiments, getPortfolio } from '../api'

export default function BacktestViewer() {
  const [experiments, setExperiments] = useState([])
  const [selectedExpIds, setSelectedExpIds] = useState([])
  const [comparison, setComparison] = useState(null)
  const [portfolioData, setPortfolioData] = useState({})

  useEffect(() => {
    const fetchExp = async () => {
      try {
        const res = await listExperiments({ limit: 100 })
        setExperiments(res.experiments || [])
      } catch (err) {
        message.error('获取实验列表失败')
      }
    }
    fetchExp()
  }, [])

  const handleCompare = async () => {
    if (selectedExpIds.length < 2) {
      message.warning('请至少选择 2 个实验进行对比')
      return
    }
    try {
      const res = await compareExperiments(selectedExpIds)
      setComparison(res.comparison || [])

      // 获取各实验的净值数据
      const portfolioMap = {}
      for (const expId of selectedExpIds) {
        try {
          const data = await getPortfolio(expId)
          if (data && data.dates) {
            portfolioMap[expId] = data
          }
        } catch (e) {}
      }
      setPortfolioData(portfolioMap)
    } catch (err) {
      message.error('对比失败')
    }
  }

  // 对比图表
  const chartOption = Object.keys(portfolioData).length > 0 ? {
    title: { text: '净值曲线对比', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0 },
    xAxis: {
      type: 'category',
      data: portfolioData[Object.keys(portfolioData)[0]]?.dates || [],
      axisLabel: { rotate: 45, fontSize: 10 }
    },
    yAxis: { type: 'value', scale: true },
    series: Object.entries(portfolioData).map(([expId, data], idx) => ({
      name: expId,
      type: 'line',
      data: data.portfolio_value,
      smooth: true,
      lineStyle: { width: 2 },
    })),
    grid: { left: 60, right: 20, bottom: 60, top: 50 },
  } : null

  // 指标对比表格
  const metricColumns = [
    { title: '实验', dataIndex: 'name', key: 'name', fixed: 'left' },
    { title: '状态', dataIndex: 'status', key: 'status' },
  ]

  // 动态添加指标列
  if (comparison && comparison.length > 0) {
    const allMetrics = new Set()
    comparison.forEach(c => {
      if (c.metrics && typeof c.metrics === 'object') {
        Object.keys(c.metrics).forEach(k => allMetrics.add(k))
      }
    })
    Array.from(allMetrics).slice(0, 10).forEach(metricKey => {
      metricColumns.push({
        title: metricKey,
        key: metricKey,
        render: (_, record) => {
          const val = record.metrics?.[metricKey]
          return val !== undefined ? (typeof val === 'number' ? val.toFixed(4) : String(val)) : '-'
        },
      })
    })
  }

  return (
    <div>
      <Card title={<><BarChartOutlined /> 回测分析 & 实验对比</>}>
        <Space style={{ marginBottom: 16 }}>
          <Select
            mode="multiple"
            placeholder="选择要对比的实验"
            value={selectedExpIds}
            onChange={setSelectedExpIds}
            style={{ width: 500 }}
            options={experiments.map(e => ({
              value: e.id,
              label: e.name || e.id,
            }))}
          />
          <Button type="primary" onClick={handleCompare}>对比</Button>
          <Button icon={<ReloadOutlined />} onClick={() => {
            setComparison(null)
            setPortfolioData({})
          }}>清除</Button>
        </Space>

        {chartOption && (
          <Card title="净值曲线对比图" size="small" style={{ marginBottom: 16 }}>
            <ReactECharts option={chartOption} style={{ height: 350 }} />
          </Card>
        )}

        {comparison && comparison.length > 0 && (
          <Card title="指标对比表" size="small">
            <Table
              columns={metricColumns}
              dataSource={comparison}
              rowKey="exp_id"
              size="small"
              scroll={{ x: 'max-content' }}
              pagination={false}
            />
          </Card>
        )}
      </Card>
    </div>
  )
}
