import React, { useEffect, useState } from 'react'
import {
  Card, Form, Input, Select, InputNumber, Switch, Button, Tabs,
  Divider, Space, message, Tooltip, Tag, Row, Col, Modal
} from 'antd'
import {
  SaveOutlined, RocketOutlined, CopyOutlined, QuestionCircleOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons'
import AceEditor from 'react-ace'
import 'ace-builds/src-noconflict/mode-yaml'
import 'ace-builds/src-noconflict/theme-monokai'
import { getDefaultConfig, getConfigTemplates, validateConfig, createExperiment } from '../api'
import { useNavigate } from 'react-router-dom'
import yaml from 'yaml'

const { TabPane } = Tabs

export default function ConfigEditor() {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(true)
  const [yamlText, setYamlText] = useState('')
  const [templates, setTemplates] = useState({})
  const [activeTab, setActiveTab] = useState('basic')
  const [submitting, setSubmitting] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    const init = async () => {
      try {
        const [defaultCfg, tmpls] = await Promise.all([
          getDefaultConfig(),
          getConfigTemplates(),
        ])
        setTemplates(tmpls)
        form.setFieldsValue(transformToForm(defaultCfg))
        setYamlText(yaml.stringify(defaultCfg))
      } catch (err) {
        message.error('加载配置失败')
      } finally {
        setLoading(false)
      }
    }
    init()
  }, [])

  const transformToForm = (cfg) => ({
    experiment_name: cfg.experiment_name,
    description: cfg.description,
    region: cfg.qlib_init?.region,
    provider_uri: cfg.qlib_init?.provider_uri,
    instruments: cfg.data_handler?.instruments,
    factor_class: cfg.data_handler?.class_name,
    start_time: cfg.data_handler?.start_time,
    end_time: cfg.data_handler?.end_time,
    fit_start_time: cfg.data_handler?.fit_start_time,
    fit_end_time: cfg.data_handler?.fit_end_time,
    model_type: cfg.model?.model_type,
    model_class: cfg.model?.class_name,
    loss: cfg.model?.loss,
    learning_rate: cfg.model?.learning_rate,
    num_leaves: cfg.model?.num_leaves,
    max_depth: cfg.model?.max_depth,
    num_boost_round: cfg.model?.num_boost_round,
    early_stopping_rounds: cfg.model?.early_stopping_rounds,
    hidden_size: cfg.model?.hidden_size,
    num_layers: cfg.model?.num_layers,
    dropout: cfg.model?.dropout,
    epochs: cfg.model?.epochs,
    batch_size: cfg.model?.batch_size,
    topk: cfg.strategy?.topk,
    n_drop: cfg.strategy?.n_drop,
    strategy_class: cfg.strategy?.class_name,
    backtest_start: cfg.backtest?.start_time,
    backtest_end: cfg.backtest?.end_time,
    account: cfg.backtest?.account,
    benchmark: cfg.backtest?.benchmark,
    deal_price: cfg.backtest?.exchange?.deal_price,
    open_cost: cfg.backtest?.exchange?.open_cost,
    close_cost: cfg.backtest?.exchange?.close_cost,
    limit_threshold: cfg.backtest?.exchange?.limit_threshold,
    iteration_enabled: cfg.iteration?.enabled,
    max_iterations: cfg.iteration?.max_iterations,
    param_search: cfg.iteration?.param_search,
    early_stop_metric: cfg.iteration?.early_stop_metric,
    tags: cfg.tags?.join(', '),
  })

  const transformToConfig = (values) => ({
    experiment_name: values.experiment_name || '',
    description: values.description || '',
    qlib_init: {
      provider_uri: values.provider_uri || '~/.qlib/qlib_data/cn_data',
      region: values.region || 'cn',
      auto_mount: true,
      concurrent_limit: 6,
    },
    data_handler: {
      class_name: values.factor_class || 'Alpha158',
      module_path: 'qlib.contrib.data.handler',
      start_time: values.start_time || '2008-01-01',
      end_time: values.end_time || '2024-12-31',
      fit_start_time: values.fit_start_time || '2008-01-01',
      fit_end_time: values.fit_end_time || '2014-12-31',
      instruments: values.instruments || 'csi300',
    },
    dataset: {
      class_name: 'DatasetH',
      module_path: 'qlib.data.dataset',
      segments: {
        train: [values.fit_start_time || '2008-01-01', values.fit_end_time || '2014-12-31'],
        valid: ['2015-01-01', '2016-12-31'],
        test: ['2017-01-01', values.end_time || '2024-12-31'],
      },
    },
    model: {
      model_type: values.model_type || 'gbdt',
      class_name: values.model_class || 'LGBModel',
      module_path: values.model_type === 'dnn' ? 'qlib.contrib.model.pytorch' :
                   values.model_type === 'transformer' ? 'qlib.contrib.model.pytorch_transformer' :
                   'qlib.contrib.model.gbdt',
      loss: values.loss || 'mse',
      learning_rate: Number(values.learning_rate) || 0.05,
      num_leaves: Number(values.num_leaves) || 64,
      max_depth: Number(values.max_depth) || -1,
      num_boost_round: Number(values.num_boost_round) || 1000,
      early_stopping_rounds: Number(values.early_stopping_rounds) || 50,
      hidden_size: Number(values.hidden_size) || 512,
      num_layers: Number(values.num_layers) || 3,
      dropout: Number(values.dropout) || 0.1,
      epochs: Number(values.epochs) || 100,
      batch_size: Number(values.batch_size) || 2048,
      optimizer: 'adam',
      lr_scheduler: 'cosine',
    },
    strategy: {
      class_name: values.strategy_class || 'TopkDropoutStrategy',
      module_path: 'qlib.contrib.strategy.signal_strategy',
      topk: Number(values.topk) || 50,
      n_drop: Number(values.n_drop) || 5,
      signal_type: 'score',
    },
    backtest: {
      start_time: values.backtest_start || '2017-01-01',
      end_time: values.backtest_end || '2024-12-31',
      account: Number(values.account) || 100000000,
      benchmark: values.benchmark || 'SH000300',
      exchange: {
        limit_threshold: Number(values.limit_threshold) || 0.095,
        deal_price: values.deal_price || 'close',
        open_cost: Number(values.open_cost) || 0.0005,
        close_cost: Number(values.close_cost) || 0.0015,
        min_cost: 5,
        trade_unit: 100,
        cancel_unit: 100,
        open_tax: 0,
        close_tax: 0.001,
      },
    },
    iteration: {
      enabled: values.iteration_enabled || false,
      max_iterations: Number(values.max_iterations) || 10,
      param_search: values.param_search || 'grid',
      early_stop_metric: values.early_stop_metric || 'information_ratio',
      early_stop_patience: 3,
    },
    tags: (values.tags || '').split(',').map(t => t.trim()).filter(Boolean),
  })

  const handleApplyTemplate = (key) => {
    const tmpl = templates[key]
    if (tmpl) {
      form.setFieldsValue(transformToForm(tmpl.config))
      const yamlCfg = transformToConfig(transformToForm(tmpl.config))
      setYamlText(yaml.stringify(yamlCfg))
      message.success(`已应用模板: ${tmpl.name}`)
    }
  }

  const handleSubmit = async (create_and_run = false) => {
    try {
      const values = await form.validateFields()
      const config = transformToConfig(values)

      // 验证
      const validation = await validateConfig(config)
      if (!validation.valid) {
        Modal.error({
          title: '配置验证失败',
          content: (
            <ul>
              {validation.errors.map((e, i) => <li key={i}>{e}</li>)}
            </ul>
          ),
        })
        return
      }

      setSubmitting(true)
      const res = await createExperiment(config)
      message.success(`实验创建成功: ${res.exp_id}`)

      if (create_and_run) {
        // 创建后立即启动
        const { startExperiment } = await import('../api')
        await startExperiment(res.exp_id)
        message.success('实验已启动')
        navigate(`/experiments/${res.exp_id}`)
      } else {
        navigate('/experiments')
      }
    } catch (err) {
      if (err.errorFields) return // 表单验证错误
      message.error('提交失败: ' + (err.message || '未知错误'))
    } finally {
      setSubmitting(false)
    }
  }

  const handleYamlChange = (text) => {
    setYamlText(text)
    try {
      const parsed = yaml.parse(text)
      form.setFieldsValue(transformToForm(parsed))
    } catch (e) {
      // YAML 解析错误，忽略
    }
  }

  if (loading) return <div>加载中...</div>

  return (
    <div>
      <Card title="配置编辑器" extra={
        <Space>
          <Select placeholder="选择模板" style={{ width: 220 }}
                  onSelect={handleApplyTemplate}>
            {Object.entries(templates).map(([key, tmpl]) => (
              <Select.Option key={key} value={key}>
                {tmpl.name}
              </Select.Option>
            ))}
          </Select>
        </Space>
      }>
        <Tabs activeKey={activeTab} onChange={setActiveTab}>
          {/* 基础配置 */}
          <TabPane tab="基础信息" key="basic">
            <Form form={form} layout="vertical" size="middle">
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item label="实验名称" name="experiment_name">
                    <Input placeholder="如: LightGBM_Alpha158_v1" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="标签" name="tags">
                    <Input placeholder="逗号分隔，如: gbdt, alpha158, csi300" />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item label="实验描述" name="description">
                <Input.TextArea rows={2} placeholder="描述本次实验的目的和特点" />
              </Form.Item>
              <Row gutter={16}>
                <Col span={8}>
                  <Form.Item label="市场区域" name="region">
                    <Select options={[
                      { value: 'cn', label: 'A股 (cn)' },
                      { value: 'us', label: '美股 (us)' },
                    ]} />
                  </Form.Item>
                </Col>
                <Col span={16}>
                  <Form.Item label="数据路径" name="provider_uri">
                    <Input placeholder="~/.qlib/qlib_data/cn_data" />
                  </Form.Item>
                </Col>
              </Row>
            </Form>
          </TabPane>

          {/* 数据配置 */}
          <TabPane tab="数据 & 因子" key="data">
            <Form form={form} layout="vertical">
              <Row gutter={16}>
                <Col span={8}>
                  <Form.Item label="股票池" name="instruments">
                    <Select options={[
                      { value: 'csi300', label: '沪深300' },
                      { value: 'csi500', label: '中证500' },
                      { value: 'all', label: '全市场' },
                    ]} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item label="因子库" name="factor_class">
                    <Select options={[
                      { value: 'Alpha158', label: 'Alpha158 (158因子)' },
                      { value: 'Alpha360', label: 'Alpha360 (360因子)' },
                    ]} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item label="拟合结束时间" name="fit_end_time">
                    <Input placeholder="2014-12-31" />
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={16}>
                <Col span={6}>
                  <Form.Item label="数据开始" name="start_time">
                    <Input placeholder="2008-01-01" />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="数据结束" name="end_time">
                    <Input placeholder="2024-12-31" />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="拟合开始" name="fit_start_time">
                    <Input placeholder="2008-01-01" />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="拟合结束" name="fit_end_time">
                    <Input placeholder="2014-12-31" />
                  </Form.Item>
                </Col>
              </Row>
            </Form>
          </TabPane>

          {/* 模型配置 */}
          <TabPane tab="模型" key="model">
            <Form form={form} layout="vertical">
              <Row gutter={16}>
                <Col span={8}>
                  <Form.Item label="模型类型" name="model_type">
                    <Select options={[
                      { value: 'gbdt', label: 'GBDT (LightGBM/XGBoost)' },
                      { value: 'dnn', label: 'DNN (PyTorch MLP)' },
                      { value: 'transformer', label: 'Transformer' },
                      { value: 'ensemble', label: 'Ensemble (集成)' },
                    ]} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item label="模型类" name="model_class">
                    <Input placeholder="LGBModel" />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item label="损失函数" name="loss">
                    <Select options={[
                      { value: 'mse', label: 'MSE' },
                      { value: 'mae', label: 'MAE' },
                      { value: 'binary', label: 'Binary' },
                      { value: 'cross_entropy', label: 'Cross Entropy' },
                    ]} />
                  </Form.Item>
                </Col>
              </Row>

              {/* GBDT 参数 */}
              <Divider orientation="left">GBDT 参数</Divider>
              <Row gutter={16}>
                <Col span={6}>
                  <Form.Item label="学习率" name="learning_rate">
                    <InputNumber min={0.001} max={1} step={0.001} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="叶子数" name="num_leaves">
                    <InputNumber min={2} max={1024} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="最大深度" name="max_depth">
                    <InputNumber min={-1} max={50} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="Boosting 轮数" name="num_boost_round">
                    <InputNumber min={10} max={10000} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={16}>
                <Col span={8}>
                  <Form.Item label="早停轮数" name="early_stopping_rounds">
                    <InputNumber min={5} max={500} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>

              {/* DNN 参数 */}
              <Divider orientation="left">DNN 参数</Divider>
              <Row gutter={16}>
                <Col span={6}>
                  <Form.Item label="隐藏层大小" name="hidden_size">
                    <InputNumber min={32} max={4096} step={32} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="层数" name="num_layers">
                    <InputNumber min={1} max={20} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="Dropout" name="dropout">
                    <InputNumber min={0} max={0.9} step={0.05} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="Epochs" name="epochs">
                    <InputNumber min={1} max={1000} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={16}>
                <Col span={6}>
                  <Form.Item label="Batch Size" name="batch_size">
                    <InputNumber min={16} max={8192} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>
            </Form>
          </TabPane>

          {/* 策略配置 */}
          <TabPane tab="策略" key="strategy">
            <Form form={form} layout="vertical">
              <Row gutter={16}>
                <Col span={8}>
                  <Form.Item label="策略类" name="strategy_class">
                    <Select options={[
                      { value: 'TopkDropoutStrategy', label: 'TopK Dropout' },
                      { value: 'WeightStrategy', label: 'Weight Strategy' },
                    ]} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item label="持仓数量 (TopK)" name="topk">
                    <InputNumber min={1} max={500} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item label="调出数量 (Drop)" name="n_drop">
                    <InputNumber min={0} max={100} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>
            </Form>
          </TabPane>

          {/* 回测配置 */}
          <TabPane tab="回测" key="backtest">
            <Form form={form} layout="vertical">
              <Row gutter={16}>
                <Col span={6}>
                  <Form.Item label="回测开始" name="backtest_start">
                    <Input placeholder="2017-01-01" />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="回测结束" name="backtest_end">
                    <Input placeholder="2024-12-31" />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="初始资金" name="account">
                    <InputNumber min={10000} step={10000} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="基准指数" name="benchmark">
                    <Input placeholder="SH000300" />
                  </Form.Item>
                </Col>
              </Row>
              <Divider orientation="left">交易成本</Divider>
              <Row gutter={16}>
                <Col span={6}>
                  <Form.Item label="涨跌停限制" name="limit_threshold">
                    <InputNumber min={0} max={0.2} step={0.005} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="成交价" name="deal_price">
                    <Select options={[
                      { value: 'close', label: '收盘价' },
                      { value: 'open', label: '开盘价' },
                      { value: 'vwap', label: 'VWAP' },
                    ]} />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="买入费率" name="open_cost">
                    <InputNumber min={0} max={0.01} step={0.0001} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="卖出费率" name="close_cost">
                    <InputNumber min={0} max={0.01} step={0.0001} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>
            </Form>
          </TabPane>

          {/* 迭代训练 */}
          <TabPane tab="迭代训练" key="iteration">
            <Form form={form} layout="vertical">
              <Row gutter={16}>
                <Col span={6}>
                  <Form.Item label="启用迭代" name="iteration_enabled" valuePropName="checked">
                    <Switch />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="最大迭代次数" name="max_iterations">
                    <InputNumber min={1} max={100} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="搜索策略" name="param_search">
                    <Select options={[
                      { value: 'grid', label: '网格搜索' },
                      { value: 'random', label: '随机搜索' },
                      { value: 'bayesian', label: '贝叶斯优化' },
                    ]} />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="早停指标" name="early_stop_metric">
                    <Select options={[
                      { value: 'information_ratio', label: '信息比率 (IR)' },
                      { value: 'annualized_return', label: '年化收益' },
                      { value: 'sharpe_ratio', label: '夏普比率' },
                      { value: 'max_drawdown', label: '最大回撤' },
                    ]} />
                  </Form.Item>
                </Col>
              </Row>
            </Form>
          </TabPane>

          {/* YAML 编辑器 */}
          <TabPane tab="YAML 源码" key="yaml">
            <div className="yaml-editor">
              <AceEditor
                mode="yaml"
                theme="monokai"
                value={yamlText}
                onChange={handleYamlChange}
                name="yaml-editor"
                editorProps={{ $blockScrolling: true }}
                style={{ width: '100%', height: '500px' }}
                fontSize={13}
                showPrintMargin={false}
                setOptions={{ useWorker: false }}
              />
            </div>
          </TabPane>
        </Tabs>

        <Divider />
        <Space>
          <Button type="primary" icon={<SaveOutlined />} loading={submitting}
                  onClick={() => handleSubmit(false)}>
            保存实验
          </Button>
          <Button type="primary" icon={<RocketOutlined />} loading={submitting}
                  onClick={() => handleSubmit(true)}>
            保存并启动
          </Button>
          <Button icon={<CopyOutlined />} onClick={() => {
            navigator.clipboard.writeText(yamlText)
            message.success('YAML 已复制到剪贴板')
          }}>
            复制 YAML
          </Button>
        </Space>
      </Card>
    </div>
  )
}
