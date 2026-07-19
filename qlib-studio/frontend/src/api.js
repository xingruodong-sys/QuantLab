import axios from 'axios'

const API_BASE = '/api'

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
})

// 获取默认配置
export const getDefaultConfig = async () => {
  const res = await api.get('/config/default')
  return res.data
}

// 获取配置模板
export const getConfigTemplates = async () => {
  const res = await api.get('/config/templates')
  return res.data
}

// 验证配置
export const validateConfig = async (config) => {
  const res = await api.post('/config/validate', config)
  return res.data
}

// 创建实验
export const createExperiment = async (config) => {
  const res = await api.post('/experiments', config)
  return res.data
}

// 列出实验
export const listExperiments = async (params = {}) => {
  const res = await api.get('/experiments', { params })
  return res.data
}

// 获取实验详情
export const getExperiment = async (expId) => {
  const res = await api.get(`/experiments/${expId}`)
  return res.data
}

// 启动实验
export const startExperiment = async (expId) => {
  const res = await api.post(`/experiments/${expId}/start`)
  return res.data
}

// 停止实验
export const stopExperiment = async (expId) => {
  const res = await api.post(`/experiments/${expId}/stop`)
  return res.data
}

// 删除实验
export const deleteExperiment = async (expId) => {
  const res = await api.delete(`/experiments/${expId}`)
  return res.data
}

// 获取指标
export const getMetrics = async (expId) => {
  const res = await api.get(`/experiments/${expId}/metrics`)
  return res.data
}

// 获取日志
export const getLogs = async (expId, tail = 200) => {
  const res = await api.get(`/experiments/${expId}/logs`, { params: { tail } })
  return res.data
}

// 获取组合净值
export const getPortfolio = async (expId) => {
  const res = await api.get(`/experiments/${expId}/portfolio`)
  return res.data
}

// 对比实验
export const compareExperiments = async (expIds) => {
  const res = await api.post('/experiments/compare', expIds)
  return res.data
}

// 列出模型
export const listModels = async () => {
  const res = await api.get('/models')
  return res.data
}

// 注册模型
export const registerModel = async (expId, modelName) => {
  const res = await api.post(`/models/${expId}/register`, null, {
    params: { model_name: modelName }
  })
  return res.data
}

// 启动迭代训练
export const startIteration = async (expId, config) => {
  const res = await api.post(`/experiments/${expId}/iterate`, config)
  return res.data
}

// 系统状态
export const getSystemStatus = async () => {
  const res = await api.get('/system/status')
  return res.data
}
