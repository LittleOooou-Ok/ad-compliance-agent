import React, { useState, useEffect, useRef, useCallback } from 'react'
import ReactDOM from 'react-dom'
import {
  Star, BarChart3, BookOpen, Users, Rocket, CheckCircle2,
  AlertTriangle, XCircle, FileText, Shield, Search, TrendingUp,
  Loader2, Plus, Trash2, RefreshCw, Send, Upload, FolderOpen,
  X, ChevronDown, ChevronUp, Eye, Settings,
} from 'lucide-react'

const API_BASE = 'https://ad-compliance-agent.onrender.com'

const TABS = [
  { id: 'review', label: '提交审核', icon: Send },
  { id: 'batch', label: '批量审核', icon: FolderOpen },
  { id: 'rules', label: '规则管理', icon: BookOpen },
  { id: 'stats', label: '数据统计', icon: Rocket },
] as const

type TabId = (typeof TABS)[number]['id']

/* ── 类型 ── */

interface ReviewResult {
  review_id: string
  conclusion: 'pass' | 'reject' | 'manual_review'
  confidence: number
  risk_level: 'low' | 'medium' | 'high'
  dimensions: Record<string, { passed: boolean; details: string; confidence: number }>
  violations: { type: string; content: string; rule_ref: string; severity: string; suggestion: string }[]
  similar_cases: { case_id: string; content: string; conclusion: string; similarity: number }[]
  report_markdown: string
  created_at: string
  latency_ms: number
}

interface Rule { rule_id: string; title: string; category: string; content: string; severity: string; keywords: string[] }
interface StatsData {
  total_reviews: number; pass_rate: number; reject_rate: number; manual_review_rate: number
  avg_latency_ms: number; avg_confidence: number
  violation_distribution: Record<string, number>; risk_distribution: Record<string, number>
  dimension_stats: Record<string, { passed: number; total: number; pass_rate: number }>
}
interface BatchResult {
  file: string; conclusion: string; confidence: number; risk_level: string; latency_ms: number; reason?: string
  dimensions?: Record<string, { passed: boolean; details: string; confidence: number }>
  violations?: { type: string; content: string; rule_ref: string; severity: string; suggestion: string }[]
  similar_cases?: { case_id: string; content: string; conclusion: string; similarity: number }[]
  report_markdown?: string
}
interface BatchStatus {
  task_id: string; total: number; completed: number; passed: number; rejected: number
  manual_review: number; status: string; progress: number; results: BatchResult[]
}

/* ── 详情弹窗 ── */

interface DetailItem {
  title: string
  conclusion: string
  confidence: number
  risk_level: string
  latency_ms: number
  dimensions?: Record<string, { passed: boolean; details: string; confidence: number }>
  violations?: { type: string; content: string; rule_ref: string; severity: string; suggestion: string }[]
  similar_cases?: { case_id: string; content: string; conclusion: string; similarity: number }[]
  report_markdown?: string
  reason?: string
}

function DetailModal({ item, onClose }: { item: DetailItem; onClose: () => void }) {
  // 锁定背景滚动
  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = '' }
  }, [])

  // 使用 Portal 渲染到 body 层，避免被父容器裁剪
  return ReactDOM.createPortal(
    <DetailModalContent item={item} onClose={onClose} />,
    document.body
  )
}

function DetailModalContent({ item, onClose }: { item: DetailItem; onClose: () => void }) {
  const cm: Record<string, { label: string; color: string; icon: React.FC<{ className?: string }> }> = {
    pass: { label: '通过', color: 'bg-green-100 text-green-700 border-green-200', icon: CheckCircle2 },
    reject: { label: '拒绝', color: 'bg-red-100 text-red-700 border-red-200', icon: XCircle },
    manual_review: { label: '人工复审', color: 'bg-yellow-100 text-yellow-700 border-yellow-200', icon: AlertTriangle },
    skipped: { label: '跳过', color: 'bg-gray-100 text-gray-500 border-gray-200', icon: Shield },
    error: { label: '错误', color: 'bg-red-100 text-red-500 border-red-200', icon: XCircle },
  }
  const rm: Record<string, { label: string; color: string }> = {
    low: { label: '低风险', color: 'bg-green-50 text-green-600' },
    medium: { label: '中风险', color: 'bg-yellow-50 text-yellow-600' },
    high: { label: '高风险', color: 'bg-red-50 text-red-600' },
  }
  const dimLabel: Record<string, string> = { compliance: '合规性', authenticity: '真实性', safety: '安全性' }
  const info = cm[item.conclusion] || cm.error

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[80vh] overflow-y-auto m-4" onClick={e => e.stopPropagation()}>
        {/* 头部 */}
        <div className="sticky top-0 bg-white border-b border-gray-100 px-5 py-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-900 truncate max-w-[300px]">{item.title}</h3>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded"><X className="w-4 h-4 text-gray-400" /></button>
        </div>

        <div className="p-5 space-y-4">
          {/* 结论卡片 */}
          <div className={`flex items-center justify-between p-3 rounded-lg border ${info.color}`}>
            <div className="flex items-center gap-2">
              <info.icon className="w-5 h-5" />
              <div>
                <div className="font-semibold text-sm">{info.label}</div>
                <div className="text-xs opacity-70">置信度 {(item.confidence * 100).toFixed(0)}%</div>
              </div>
            </div>
            {rm[item.risk_level] && (
              <span className={`px-2 py-1 rounded-full text-xs font-medium ${rm[item.risk_level].color}`}>
                {rm[item.risk_level].label}
              </span>
            )}
          </div>

          {/* 耗时 */}
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <span>审核耗时：{item.latency_ms}ms</span>
          </div>

          {/* 维度详情 */}
          {item.dimensions && Object.keys(item.dimensions).length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-gray-700 mb-2">审核维度</h4>
              <div className="space-y-2">
                {['compliance', 'authenticity', 'safety'].map(k => {
                  const d = item.dimensions![k]; if (!d) return null
                  return (
                    <div key={k} className="bg-gray-50 rounded-lg p-3">
                      <div className="flex items-center gap-2 mb-1">
                        {d.passed ? <CheckCircle2 className="w-4 h-4 text-green-500" /> : <XCircle className="w-4 h-4 text-red-500" />}
                        <span className="text-xs font-medium text-gray-800">{dimLabel[k]}</span>
                        <span className="text-[10px] text-gray-400 ml-auto">{(d.confidence * 100).toFixed(0)}%</span>
                      </div>
                      <p className="text-xs text-gray-600 pl-6">{d.details}</p>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* 违规点 */}
          {item.violations && item.violations.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-gray-700 mb-2">违规点（{item.violations.length}）</h4>
              <div className="space-y-2">
                {item.violations.map((v, i) => (
                  <div key={i} className="bg-red-50 rounded-lg p-3 border border-red-100">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${v.severity === 'high' ? 'bg-red-200 text-red-800' : 'bg-orange-200 text-orange-800'}`}>
                        {v.type}
                      </span>
                      <span className="text-[10px] text-gray-500">{v.rule_ref}</span>
                    </div>
                    <p className="text-xs text-gray-800 mb-1">"{v.content}"</p>
                    <p className="text-xs text-gray-600">💡 {v.suggestion}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 相似案例 */}
          {item.similar_cases && item.similar_cases.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-gray-700 mb-2">相似案例</h4>
              <div className="space-y-1.5">
                {item.similar_cases.map(c => (
                  <div key={c.case_id} className="bg-gray-50 rounded-lg p-2.5 flex items-center justify-between">
                    <span className="text-xs text-gray-700 truncate max-w-[250px]">{c.content}</span>
                    <div className="flex items-center gap-2">
                      <span className={`text-xs font-medium ${c.conclusion === 'pass' ? 'text-green-600' : 'text-red-600'}`}>
                        {c.conclusion === 'pass' ? '通过' : '拒绝'}
                      </span>
                      <span className="text-[10px] text-gray-400">{(c.similarity * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 原因（批量审核的跳过/错误） */}
          {item.reason && (
            <div>
              <h4 className="text-xs font-semibold text-gray-700 mb-2">详情</h4>
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-700">{item.reason}</p>
              </div>
            </div>
          )}

          {/* 完整报告 */}
          {item.report_markdown && (
            <div>
              <h4 className="text-xs font-semibold text-gray-700 mb-2">完整报告</h4>
              <div className="bg-gray-50 rounded-lg p-3 max-h-[200px] overflow-y-auto">
                <pre className="text-xs text-gray-700 whitespace-pre-wrap font-mono">{item.report_markdown}</pre>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

/* ── 提交审核 ── */

function ReviewWorkbench({ result, setResult }: { result: ReviewResult | null; setResult: (r: ReviewResult | null) => void }) {
  const [content, setContent] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showDetail, setShowDetail] = useState(false)

  const onFilePick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const fl = e.target.files; if (!fl) return
    const arr: File[] = []; for (let i = 0; i < fl.length; i++) arr.push(fl[i])
    setFiles(prev => [...prev, ...arr]); e.target.value = ''
  }

  const submit = async () => {
    if (!content.trim() && files.length === 0) return
    setLoading(true); setError(''); setResult(null)
    try {
      const fd = new FormData()
      if (content.trim()) fd.append('content', content)
      files.forEach(f => fd.append('files', f))
      const res = await fetch(`${API_BASE}/api/review`, { method: 'POST', body: fd })
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || '审核失败') }
      setResult(await res.json())
    } catch (e: unknown) { setError(e instanceof Error ? e.message : '网络错误') }
    finally { setLoading(false) }
  }

  const cm: Record<string, { label: string; color: string; icon: React.FC<{ className?: string }> }> = {
    pass: { label: '通过', color: 'bg-green-100 text-green-700 border-green-200', icon: CheckCircle2 },
    reject: { label: '拒绝', color: 'bg-red-100 text-red-700 border-red-200', icon: XCircle },
    manual_review: { label: '人工复审', color: 'bg-yellow-100 text-yellow-700 border-yellow-200', icon: AlertTriangle },
  }
  const rm: Record<string, { label: string; color: string }> = {
    low: { label: '低风险', color: 'bg-green-50 text-green-600' },
    medium: { label: '中风险', color: 'bg-yellow-50 text-yellow-600' },
    high: { label: '高风险', color: 'bg-red-50 text-red-600' },
  }
  const dimLabel: Record<string, string> = { compliance: '合规性', authenticity: '真实性', safety: '安全性' }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      {/* 左侧：输入区 */}
      <div className="space-y-4">
        <div className="section-header pb-2">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-7 h-7 rounded-lg bg-black flex items-center justify-center">
              <Send className="w-3.5 h-3.5 text-white" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-gray-900">提交审核</h3>
              <p className="text-[10px] text-gray-400">输入文案或上传文件进行 AI 审核</p>
            </div>
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1.5">广告文案</label>
          <textarea
            value={content}
            onChange={e => setContent(e.target.value)}
            placeholder="粘贴广告文案进行审核..."
            className="w-full h-24 px-3.5 py-2.5 bg-white border border-gray-200 rounded-xl text-sm resize-none input-focus placeholder:text-gray-300"
          />
          <div className="flex justify-end mt-1">
            <span className="text-[10px] text-gray-300">{content.length} 字</span>
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1.5">上传文件</label>
          <label className={`upload-zone flex flex-col items-center justify-center border-2 border-dashed rounded-xl p-5 cursor-pointer ${files.length ? 'border-green-400/70 bg-green-50/50' : 'border-gray-200'}`}>
            <div className={`w-10 h-10 rounded-full flex items-center justify-center mb-2 ${files.length ? 'bg-green-100' : 'bg-gray-100'}`}>
              <Upload className={`w-5 h-5 ${files.length ? 'text-green-500' : 'text-gray-400'}`} />
            </div>
            <span className={`text-xs font-medium ${files.length ? 'text-green-600' : 'text-gray-500'}`}>
              {files.length ? `已选 ${files.length} 个文件` : '点击或拖拽上传'}
            </span>
            <span className="text-[10px] text-gray-300 mt-1">图片 / 视频 / JSON / MD</span>
            <input type="file" multiple accept=".jpg,.jpeg,.png,.gif,.webp,.bmp,.mp4,.mov,.avi,.wmv,.json,.md,.txt" onChange={onFilePick} className="hidden" />
          </label>
        </div>

        {files.length > 0 && (
          <div className="bg-gray-50/80 rounded-xl p-2.5 max-h-[80px] overflow-y-auto custom-scrollbar">
            {files.map((f, i) => (
              <div key={i} className="flex items-center justify-between py-1 px-1 hover:bg-white/60 rounded transition">
                <div className="flex items-center gap-2 min-w-0">
                  <FileText className="w-3 h-3 text-gray-400 flex-shrink-0" />
                  <span className="text-xs text-gray-600 truncate">{f.name}</span>
                </div>
                <button onClick={() => setFiles(p => p.filter((_, j) => j !== i))} className="text-gray-300 hover:text-red-500 transition p-0.5"><X className="w-3 h-3" /></button>
              </div>
            ))}
          </div>
        )}

        <button
          onClick={submit}
          disabled={loading || (!content.trim() && !files.length)}
          className="btn-primary w-full bg-black text-white py-3 rounded-xl text-sm font-medium disabled:opacity-30 flex items-center justify-center gap-2"
        >
          {loading ? <><Loader2 className="w-4 h-4 animate-spin" />AI 审核中...</> : <><Send className="w-4 h-4" />提交审核</>}
        </button>
        {error && (
          <div className="p-3 bg-red-50 border border-red-100 rounded-xl text-xs text-red-600 flex items-center gap-2">
            <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />{error}
          </div>
        )}
      </div>

      {/* 右侧：结果区 */}
      <div className="border border-gray-100 bg-gray-50/50 rounded-xl p-4 overflow-y-auto max-h-[420px] custom-scrollbar">
        {!result && !loading && (
          <div className="flex flex-col items-center justify-center h-full text-gray-300 py-16">
            <div className="w-14 h-14 rounded-2xl bg-gray-100 flex items-center justify-center mb-3">
              <Shield className="w-7 h-7 text-gray-300" />
            </div>
            <p className="text-xs font-medium text-gray-400">输入文案或上传文件</p>
            <p className="text-[10px] text-gray-300 mt-1">AI 将自动检测违规内容</p>
          </div>
        )}
        {loading && (
          <div className="flex flex-col items-center justify-center h-full text-gray-400 py-16">
            <div className="w-14 h-14 rounded-2xl bg-gray-100 flex items-center justify-center mb-3 relative">
              <Loader2 className="w-7 h-7 animate-spin text-gray-500" />
            </div>
            <p className="text-xs font-medium">AI 审核中...</p>
            <p className="text-[10px] text-gray-300 mt-1">正在分析内容合规性</p>
          </div>
        )}
        {result && (
          <div className="space-y-3 result-item">
            {/* 结论卡片 */}
            <div className={`flex items-center justify-between p-3.5 rounded-xl border ${cm[result.conclusion]?.color}`}>
              <div className="flex items-center gap-2.5">
                {React.createElement(cm[result.conclusion]?.icon || Shield, { className: 'w-5 h-5' })}
                <div>
                  <div className="font-semibold text-sm">{cm[result.conclusion]?.label}</div>
                  <div className="text-[10px] opacity-60">置信度 {(result.confidence * 100).toFixed(0)}%</div>
                </div>
              </div>
              <span className={`px-2.5 py-1 rounded-full text-[10px] font-semibold ${rm[result.risk_level]?.color}`}>{rm[result.risk_level]?.label}</span>
            </div>

            {/* 维度 */}
            <div className="space-y-1.5">
              {['compliance', 'authenticity', 'safety'].map(k => {
                const d = result.dimensions[k]; if (!d) return null
                return (
                  <div key={k} className="flex items-center justify-between bg-white rounded-lg px-3 py-2 border border-gray-100 result-item">
                    <div className="flex items-center gap-2">
                      {d.passed
                        ? <CheckCircle2 className="w-4 h-4 text-green-500" />
                        : <XCircle className="w-4 h-4 text-red-500" />}
                      <span className="text-xs font-medium text-gray-700">{dimLabel[k]}</span>
                    </div>
                    <span className="text-[10px] text-gray-400 max-w-[170px] truncate">{d.details}</span>
                  </div>
                )
              })}
            </div>

            {/* 违规点 */}
            {result.violations.length > 0 && (
              <div>
                <h4 className="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-2">违规点 · {result.violations.length}</h4>
                <div className="space-y-1.5">
                  {result.violations.map((v, i) => (
                    <div key={i} className="bg-white rounded-lg p-2.5 border border-gray-100 border-l-2 border-l-red-300 result-item">
                      <div className="flex items-center gap-1.5 mb-1">
                        <span className={`px-1.5 py-0.5 rounded-md text-[10px] font-semibold ${v.severity === 'high' ? 'bg-red-100 text-red-700' : 'bg-orange-100 text-orange-700'}`}>{v.type}</span>
                        <span className="text-[10px] text-gray-300">{v.rule_ref}</span>
                      </div>
                      <p className="text-xs text-gray-700">"{v.content}"</p>
                      <p className="text-[10px] text-gray-400 mt-1">💡 {v.suggestion}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 相似案例 */}
            {result.similar_cases.length > 0 && (
              <div>
                <h4 className="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-2">相似案例</h4>
                <div className="space-y-1">
                  {result.similar_cases.map(c => (
                    <div key={c.case_id} className="flex items-center justify-between bg-white rounded-lg px-3 py-2 border border-gray-100 result-item">
                      <span className="text-xs text-gray-600 truncate max-w-[160px]">{c.content}</span>
                      <div className="flex items-center gap-2">
                        <span className={`text-[10px] font-semibold ${c.conclusion === 'pass' ? 'text-green-600' : 'text-red-600'}`}>{c.conclusion === 'pass' ? '通过' : '拒绝'}</span>
                        <span className="text-[10px] text-gray-300">{(c.similarity * 100).toFixed(0)}%</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 底部操作 */}
            <div className="flex items-center justify-between pt-3 border-t border-gray-100">
              <span className="text-[10px] text-gray-300 flex items-center gap-1">
                <BarChart3 className="w-3 h-3" />耗时 {result.latency_ms}ms
              </span>
              <button onClick={() => setShowDetail(true)} className="btn-ghost flex items-center gap-1.5 text-xs text-gray-600 hover:text-black px-2.5 py-1.5 rounded-lg">
                <Eye className="w-3.5 h-3.5" />查看详情
              </button>
            </div>
          </div>
        )}
      </div>

      {showDetail && result && (
        <DetailModal
          item={{
            title: '提交审核详情',
            conclusion: result.conclusion,
            confidence: result.confidence,
            risk_level: result.risk_level,
            latency_ms: result.latency_ms,
            dimensions: result.dimensions,
            violations: result.violations,
            similar_cases: result.similar_cases,
            report_markdown: result.report_markdown,
          }}
          onClose={() => setShowDetail(false)}
        />
      )}
    </div>
  )
}

/* ── 自动化工作流 ── */

interface WorkflowStatus {
  workflow_id: string
  source_folder: string
  status: string
  total_tasks: number
  completed_tasks: number
  passed: number
  rejected: number
  manual_review: number
  progress: number
  updated_at: string
}

function WorkflowSection() {
  const [folderPath, setFolderPath] = useState('')
  const [workflowId, setWorkflowId] = useState<string | null>(null)
  const [wfStatus, setWfStatus] = useState<WorkflowStatus | null>(null)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')
  const [workflows, setWorkflows] = useState<WorkflowStatus[]>([])
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // 加载已有工作流
  useEffect(() => {
    fetchWorkflows()
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [])

  const fetchWorkflows = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/workflow/list`)
      const data = await res.json()
      setWorkflows(data.workflows || [])
    } catch { /* 忽略 */ }
  }

  const createWorkflow = async () => {
    if (!folderPath.trim()) return
    setCreating(true); setError('')
    try {
      const res = await fetch(`${API_BASE}/api/workflow/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_folder: folderPath }),
      })
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || '创建失败') }
      const data = await res.json()
      setWorkflowId(data.workflow_id)
      // 获取初始状态
      const sres = await fetch(`${API_BASE}/api/workflow/${data.workflow_id}/status`)
      setWfStatus(await sres.json())
      fetchWorkflows()
    } catch (e: unknown) { setError(e instanceof Error ? e.message : '创建失败') }
    finally { setCreating(false) }
  }

  const startWorkflow = async (wfId: string) => {
    setError('')
    try {
      const res = await fetch(`${API_BASE}/api/workflow/${wfId}/start`, { method: 'POST' })
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || '启动失败') }
      setWorkflowId(wfId)
      // 开始轮询
      timerRef.current = setInterval(async () => {
        try {
          const res = await fetch(`${API_BASE}/api/workflow/${wfId}/status`)
          const data: WorkflowStatus = await res.json()
          setWfStatus(data)
          if (data.status === 'completed' || data.status === 'paused') {
            if (timerRef.current) clearInterval(timerRef.current)
            fetchWorkflows()
          }
        } catch { /* 忽略 */ }
      }, 2000)
    } catch (e: unknown) { setError(e instanceof Error ? e.message : '启动失败') }
  }

  const pauseWorkflow = async (wfId: string) => {
    try {
      await fetch(`${API_BASE}/api/workflow/${wfId}/pause`, { method: 'POST' })
      if (timerRef.current) clearInterval(timerRef.current)
      fetchWorkflows()
    } catch { /* 忽略 */ }
  }

  const resumeWorkflow = (wfId: string) => {
    startWorkflow(wfId)
  }

  return (
    <div className="space-y-4 border-t border-gray-100 pt-5">
      <div className="flex items-center gap-2">
        <div className="w-6 h-6 rounded-lg bg-gray-100 flex items-center justify-center">
          <FolderOpen className="w-3 h-3 text-gray-500" />
        </div>
        <div>
          <h3 className="text-xs font-semibold text-gray-800">自动化工作流</h3>
          <p className="text-[10px] text-gray-400">选择文件夹，自动处理素材，支持断点续传</p>
        </div>
      </div>

      {/* 本地部署提示 */}
      <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-xl text-xs text-yellow-800 flex items-start gap-2">
        <AlertTriangle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
        <div>
          <span className="font-semibold">需要本地部署</span>：此功能需要后端运行在本地才能访问本地文件夹。
          <br />
          <span className="text-[10px] text-yellow-600 mt-1 block">
            远程部署请使用上方的「文件上传」功能代替。
          </span>
        </div>
      </div>

      {/* 创建工作流 */}
      <div className="flex gap-2">
        <input
          value={folderPath}
          onChange={e => setFolderPath(e.target.value)}
          placeholder="输入文件夹路径，如: D:\素材\待审核"
          className="flex-1 px-3.5 py-2.5 bg-white border border-gray-200 rounded-xl text-xs input-focus"
        />
        <button onClick={createWorkflow} disabled={creating || !folderPath.trim()} className="btn-primary px-5 py-2.5 bg-black text-white rounded-xl text-xs font-medium disabled:opacity-30">
          {creating ? '扫描中...' : '创建'}
        </button>
      </div>

      {error && (
        <div className="p-3 bg-red-50 border border-red-100 rounded-xl text-xs text-red-600 flex items-center gap-2">
          <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />{error}
        </div>
      )}

      {/* 当前工作流状态 */}
      {wfStatus && (
        <div className="bg-gray-50/80 rounded-xl p-4 space-y-3 border border-gray-100 animate-slide-down">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-gray-700 flex items-center gap-1.5">
              <div className={`w-2 h-2 rounded-full ${wfStatus.status === 'processing' ? 'bg-blue-500 animate-pulse' : wfStatus.status === 'completed' ? 'bg-green-500' : wfStatus.status === 'paused' ? 'bg-yellow-500' : 'bg-gray-400'}`} />
              {wfStatus.status === 'processing' ? '处理中' : wfStatus.status === 'completed' ? '已完成' : wfStatus.status === 'paused' ? '已暂停' : '就绪'}
            </span>
            <span className="text-[10px] text-gray-300 truncate max-w-[200px]">{wfStatus.source_folder}</span>
          </div>

          <div>
            <div className="flex items-center justify-between text-xs mb-1.5">
              <span className="text-gray-500">进度</span>
              <span className="font-bold text-gray-800">{wfStatus.progress.toFixed(0)}%（{wfStatus.completed_tasks}/{wfStatus.total_tasks}）</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
              <div className="bg-black h-2 rounded-full transition-all duration-700" style={{ width: `${wfStatus.progress}%` }} />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2">
            <div className="bg-green-50/80 rounded-lg p-2.5 text-center border border-green-100/50">
              <div className="text-sm font-bold text-green-600">{wfStatus.passed}</div>
              <div className="text-[10px] text-gray-500">通过</div>
            </div>
            <div className="bg-red-50/80 rounded-lg p-2.5 text-center border border-red-100/50">
              <div className="text-sm font-bold text-red-600">{wfStatus.rejected}</div>
              <div className="text-[10px] text-gray-500">拒绝</div>
            </div>
            <div className="bg-yellow-50/80 rounded-lg p-2.5 text-center border border-yellow-100/50">
              <div className="text-sm font-bold text-yellow-600">{wfStatus.manual_review}</div>
              <div className="text-[10px] text-gray-500">复审</div>
            </div>
          </div>

          <div className="flex gap-2">
            {wfStatus.status === 'ready' && (
              <button onClick={() => startWorkflow(wfStatus.workflow_id)} className="btn-primary flex-1 bg-green-600 text-white py-2.5 rounded-xl text-xs font-medium hover:bg-green-700">
                开始处理
              </button>
            )}
            {wfStatus.status === 'processing' && (
              <button onClick={() => pauseWorkflow(wfStatus.workflow_id)} className="btn-primary flex-1 bg-yellow-600 text-white py-2.5 rounded-xl text-xs font-medium hover:bg-yellow-700">
                暂停
              </button>
            )}
            {wfStatus.status === 'paused' && (
              <button onClick={() => resumeWorkflow(wfStatus.workflow_id)} className="btn-primary flex-1 bg-green-600 text-white py-2.5 rounded-xl text-xs font-medium hover:bg-green-700">
                继续处理
              </button>
            )}
            {wfStatus.status === 'completed' && (
              <div className="flex-1 bg-green-50 border border-green-100 text-green-700 py-2.5 rounded-xl text-xs font-semibold text-center">
                ✓ 全部完成
              </div>
            )}
          </div>
        </div>
      )}

      {/* 历史工作流 */}
      {workflows.length > 0 && (
        <div>
          <h4 className="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-2">历史工作流</h4>
          <div className="space-y-1.5 max-h-[150px] overflow-y-auto custom-scrollbar">
            {workflows.map(wf => (
              <div key={wf.workflow_id} className="card-hover flex items-center justify-between bg-white rounded-xl px-3 py-2.5 border border-gray-100 group">
                <div className="min-w-0 flex-1">
                  <div className="text-xs text-gray-700 truncate font-medium">{wf.source_folder}</div>
                  <div className="text-[10px] text-gray-400 mt-0.5 flex items-center gap-1.5">
                    <div className={`w-1.5 h-1.5 rounded-full ${wf.status === 'completed' ? 'bg-green-500' : wf.status === 'processing' ? 'bg-blue-500' : wf.status === 'paused' ? 'bg-yellow-500' : 'bg-gray-300'}`} />
                    {wf.status === 'completed' ? '已完成' : wf.status === 'processing' ? '处理中' : wf.status === 'paused' ? '已暂停' : '就绪'}
                    <span className="text-gray-300">·</span> {wf.completed_tasks}/{wf.total_tasks}
                  </div>
                </div>
                <div className="flex gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                  {(wf.status === 'ready' || wf.status === 'paused') && (
                    <button onClick={() => startWorkflow(wf.workflow_id)} className="px-2.5 py-1 bg-green-50 text-green-700 rounded-lg text-[10px] font-medium border border-green-100">
                      {wf.status === 'paused' ? '继续' : '开始'}
                    </button>
                  )}
                  {wf.status === 'processing' && (
                    <button onClick={() => pauseWorkflow(wf.workflow_id)} className="px-2.5 py-1 bg-yellow-50 text-yellow-700 rounded-lg text-[10px] font-medium border border-yellow-100">
                      暂停
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

/* ── 批量审核 ── */

function BatchWorkbench({ status, setStatus }: { status: BatchStatus | null; setStatus: (s: BatchStatus | null) => void }) {
  const [subTab, setSubTab] = useState<'upload' | 'workflow'>('upload')
  const [files, setFiles] = useState<File[]>([])
  const [taskId, setTaskId] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [error, setError] = useState('')
  const [uploadSuccess, setUploadSuccess] = useState<{files: string[], total: number} | null>(null)
  const [expanded, setExpanded] = useState<Record<number, boolean>>({})
  const [detailItem, setDetailItem] = useState<DetailItem | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const onFilePick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const fl = e.target.files; if (!fl) return
    const arr: File[] = []; for (let i = 0; i < fl.length; i++) arr.push(fl[i])
    setFiles(prev => [...prev, ...arr]); e.target.value = ''
  }

  const upload = async () => {
    if (files.length === 0) return
    setUploading(true); setError(''); setUploadSuccess(null)
    const fileNames = files.map(f => f.name)
    try {
      const fd = new FormData(); files.forEach(f => fd.append('files', f))
      const res = await fetch(`${API_BASE}/api/batch/upload`, { method: 'POST', body: fd })
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || '上传失败') }
      const data = await res.json()
      setTaskId(data.task_id); setFiles([])
      setUploadSuccess({ files: fileNames, total: data.total_files })
      const sres = await fetch(`${API_BASE}/api/batch/${data.task_id}/status`)
      setStatus(await sres.json())
    } catch (e: unknown) { setError(e instanceof Error ? e.message : '上传失败') }
    finally { setUploading(false) }
  }

  const startProcessing = async () => {
    if (!taskId) return
    setProcessing(true); setError('')
    try {
      const res = await fetch(`${API_BASE}/api/batch/${taskId}/start`, { method: 'POST' })
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || '启动失败') }
      timerRef.current = setInterval(async () => {
        try {
          const res = await fetch(`${API_BASE}/api/batch/${taskId}/status`)
          const data: BatchStatus = await res.json()
          setStatus(data)
          if (data.status === 'completed') {
            setProcessing(false)
            if (timerRef.current) clearInterval(timerRef.current)
          }
        } catch { /* 忽略 */ }
      }, 2000)
    } catch (e: unknown) { setError(e instanceof Error ? e.message : '处理失败'); setProcessing(false) }
  }

  useEffect(() => { return () => { if (timerRef.current) clearInterval(timerRef.current) } }, [])

  const cc: Record<string, string> = { pass: 'text-green-600', reject: 'text-red-600', manual_review: 'text-yellow-600', skipped: 'text-gray-400', error: 'text-red-400' }
  const ccBg: Record<string, string> = { pass: 'bg-green-50', reject: 'bg-red-50', manual_review: 'bg-yellow-50', skipped: 'bg-gray-50', error: 'bg-red-50' }
  const conclusionLabel: Record<string, string> = { pass: '通过', reject: '拒绝', manual_review: '复审', skipped: '跳过', error: '错误' }

  const toggleExpand = (i: number) => setExpanded(prev => ({ ...prev, [i]: !prev[i] }))

  return (
    <div className="space-y-4">
      {/* 头部 */}
      <div className="section-header pb-2">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-black flex items-center justify-center">
            <FolderOpen className="w-3.5 h-3.5 text-white" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-gray-900">批量审核</h3>
            <p className="text-[10px] text-gray-400">上传文件或选择文件夹进行批量审核</p>
          </div>
        </div>
      </div>

      {/* 子 Tab */}
      <div className="flex bg-gray-100 rounded-lg p-1">
        <button
          onClick={() => setSubTab('upload')}
          className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-md text-xs font-medium transition ${subTab === 'upload' ? 'bg-white text-black shadow-sm' : 'text-gray-500'}`}
        >
          <Upload className="w-3.5 h-3.5" />文件上传
        </button>
        <button
          onClick={() => setSubTab('workflow')}
          className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-md text-xs font-medium transition ${subTab === 'workflow' ? 'bg-white text-black shadow-sm' : 'text-gray-500'}`}
        >
          <FolderOpen className="w-3.5 h-3.5" />自动化工作流
        </button>
      </div>

      {/* 子 Tab 内容 */}
      {subTab === 'upload' ? (
      <div className="space-y-4">
      {/* 上传区 */}
      <div>
        <label className={`upload-zone flex flex-col items-center justify-center border-2 border-dashed rounded-xl p-5 cursor-pointer ${files.length ? 'border-green-400/70 bg-green-50/50' : 'border-gray-200'}`}>
          <div className={`w-10 h-10 rounded-full flex items-center justify-center mb-2 ${files.length ? 'bg-green-100' : 'bg-gray-100'}`}>
            <FolderOpen className={`w-5 h-5 ${files.length ? 'text-green-500' : 'text-gray-400'}`} />
          </div>
          <span className={`text-xs font-medium ${files.length ? 'text-green-600' : 'text-gray-500'}`}>
            {files.length ? `已选 ${files.length} 个文件` : '点击或拖拽上传多个文件'}
          </span>
          <span className="text-[10px] text-gray-300 mt-1">图片 / 视频 / JSON / MD</span>
          <input type="file" multiple accept=".jpg,.jpeg,.png,.gif,.webp,.bmp,.mp4,.mov,.avi,.wmv,.json,.md,.txt" onChange={onFilePick} className="hidden" />
        </label>
      </div>

      {/* 文件列表 */}
      {files.length > 0 && (
        <div className="bg-gray-50/80 rounded-xl p-2.5 max-h-[80px] overflow-y-auto custom-scrollbar">
          <div className="flex items-center justify-between mb-1.5 px-1">
            <span className="text-[10px] text-gray-400 font-medium">{files.length} 个文件</span>
            <button onClick={() => setFiles([])} className="text-[10px] text-red-400 hover:text-red-600 transition">清空</button>
          </div>
          {files.map((f, i) => (
            <div key={i} className="flex items-center justify-between py-1 px-1 hover:bg-white/60 rounded transition">
              <div className="flex items-center gap-2 min-w-0">
                <FileText className="w-3 h-3 text-gray-400 flex-shrink-0" />
                <span className="text-[10px] text-gray-600 truncate">{f.name}</span>
              </div>
              <button onClick={() => setFiles(p => p.filter((_, j) => j !== i))}><X className="w-3 h-3 text-gray-300 hover:text-red-500 transition" /></button>
            </div>
          ))}
        </div>
      )}

      {/* 操作按钮 */}
      <div className="flex gap-2">
        <button onClick={upload} disabled={uploading || !files.length} className="btn-primary flex-1 bg-black text-white py-2.5 rounded-xl text-xs font-medium disabled:opacity-30 flex items-center justify-center gap-1.5">
          {uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
          {uploading ? '上传中...' : '上传文件'}
        </button>
        {taskId && !processing && status?.status !== 'completed' && (
          <button onClick={startProcessing} className="btn-primary flex-1 bg-green-600 text-white py-2.5 rounded-xl text-xs font-medium hover:bg-green-700 flex items-center justify-center gap-1.5">
            <Rocket className="w-3.5 h-3.5" />开始处理
          </button>
        )}
        {processing && (
          <div className="flex-1 bg-blue-50 border border-blue-100 text-blue-700 py-2.5 rounded-xl text-xs font-medium flex items-center justify-center gap-1.5">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />处理中...
          </div>
        )}
      </div>

      {/* 上传成功 */}
      {uploadSuccess && (
        <div className="p-3 bg-green-50 border border-green-100 rounded-xl text-xs text-green-700 animate-slide-down">
          <div className="flex items-center gap-2 mb-1.5">
            <CheckCircle2 className="w-4 h-4" />
            <span className="font-semibold">上传成功！共 {uploadSuccess.total} 个文件</span>
          </div>
          <div className="pl-6 space-y-0.5">
            {uploadSuccess.files.map((name, i) => (
              <div key={i} className="text-[10px] text-green-500">• {name}</div>
            ))}
          </div>
        </div>
      )}

      {error && (
        <div className="p-3 bg-red-50 border border-red-100 rounded-xl text-xs text-red-600 flex items-center gap-2">
          <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />{error}
        </div>
      )}

      {/* 进度区域 */}
      {status && status.total > 0 && (
        <div className="space-y-3 animate-slide-up">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-gray-700">
              {processing ? '处理进度' : '处理完成'}
            </span>
            <span className="text-xs font-bold text-gray-900">
              {status.progress.toFixed(0)}%（{status.completed}/{status.total}）
            </span>
          </div>
          <div className="w-full bg-gray-100 rounded-full h-2.5 overflow-hidden">
            <div
              className={`h-2.5 rounded-full transition-all duration-700 ease-out ${processing ? 'bg-gradient-to-r from-blue-500 to-blue-400' : 'bg-gradient-to-r from-green-500 to-green-400'}`}
              style={{ width: `${status.progress}%` }}
            />
          </div>
          <div className="grid grid-cols-3 gap-2.5">
            <div className="bg-green-50/80 rounded-xl p-3 text-center border border-green-100/50">
              <div className="text-base font-bold text-green-600 stat-value">{status.passed}</div>
              <div className="text-[10px] text-gray-500">通过</div>
            </div>
            <div className="bg-red-50/80 rounded-xl p-3 text-center border border-red-100/50">
              <div className="text-base font-bold text-red-600 stat-value">{status.rejected}</div>
              <div className="text-[10px] text-gray-500">拒绝</div>
            </div>
            <div className="bg-yellow-50/80 rounded-xl p-3 text-center border border-yellow-100/50">
              <div className="text-base font-bold text-yellow-600 stat-value">{status.manual_review}</div>
              <div className="text-[10px] text-gray-500">复审</div>
            </div>
          </div>

          {/* 结果列表 */}
          {status.results.length > 0 && (
            <div className="max-h-[250px] overflow-y-auto space-y-1.5 custom-scrollbar pr-1">
              {status.results.map((r, i) => (
                <div key={i} className={`result-item rounded-xl border ${ccBg[r.conclusion] || 'bg-white'} border-gray-100 overflow-hidden`}>
                  <div className="flex items-center justify-between px-3 py-2">
                    <div className="flex items-center gap-2.5 min-w-0 flex-1">
                      <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${r.conclusion === 'pass' ? 'bg-green-500' : r.conclusion === 'reject' ? 'bg-red-500' : r.conclusion === 'manual_review' ? 'bg-yellow-500' : 'bg-gray-300'}`} />
                      <span className={`text-[10px] font-bold ${cc[r.conclusion]}`}>{conclusionLabel[r.conclusion]}</span>
                      <span className="text-xs text-gray-700 truncate">{r.file}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {r.confidence > 0 && <span className="text-[10px] text-gray-300">{(r.confidence * 100).toFixed(0)}%</span>}
                      <button
                        onClick={() => setDetailItem({
                          title: r.file, conclusion: r.conclusion, confidence: r.confidence,
                          risk_level: r.risk_level, latency_ms: r.latency_ms, reason: r.reason,
                          dimensions: r.dimensions, violations: r.violations,
                          similar_cases: r.similar_cases, report_markdown: r.report_markdown,
                        })}
                        className="btn-ghost p-1.5 text-gray-300 hover:text-black rounded-md"
                      >
                        <Eye className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 空状态 */}
      {!status && !uploading && (
        <div className="flex flex-col items-center justify-center py-12 text-gray-300">
          <div className="w-14 h-14 rounded-2xl bg-gray-100 flex items-center justify-center mb-3">
            <FolderOpen className="w-7 h-7 text-gray-300" />
          </div>
          <p className="text-xs font-medium text-gray-400">上传文件后开始批量审核</p>
        </div>
      )}

      {detailItem && (
        <DetailModal item={detailItem} onClose={() => setDetailItem(null)} />
      )}
      </div>
      ) : (
      /* 自动化工作流 */
      <WorkflowSection />
      )}
    </div>
  )
}

/* ── 规则管理 ── */

function RulesWorkbench() {
  const [rules, setRules] = useState<Rule[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [newRule, setNewRule] = useState({ category: '', title: '', content: '', severity: 'high', keywords: '' })
  const [error, setError] = useState('')

  const fetchRules = async () => {
    setLoading(true); setError('')
    try {
      const res = await fetch(`${API_BASE}/api/rules`); const data = await res.json()
      setRules(data.rules || []); setTotal(data.total || 0)
    } catch (e: unknown) { setError(e instanceof Error ? e.message : '网络错误') }
    finally { setLoading(false) }
  }

  const searchRules = async () => {
    if (!searchQuery.trim()) return fetchRules()
    setLoading(true); setError('')
    try {
      const res = await fetch(`${API_BASE}/api/rules/search?q=${encodeURIComponent(searchQuery)}`); const data = await res.json()
      setRules(data.results || []); setTotal(data.total || 0)
    } catch (e: unknown) { setError(e instanceof Error ? e.message : '网络错误') }
    finally { setLoading(false) }
  }

  const createRule = async () => {
    if (!newRule.category || !newRule.title || !newRule.content) return
    setLoading(true); setError('')
    try {
      const res = await fetch(`${API_BASE}/api/rules`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...newRule, keywords: newRule.keywords.split(/[,，]/).map(s => s.trim()).filter(Boolean) }),
      })
      if (!res.ok) throw new Error('创建失败')
      setShowCreate(false); setNewRule({ category: '', title: '', content: '', severity: 'high', keywords: '' }); fetchRules()
    } catch (e: unknown) { setError(e instanceof Error ? e.message : '网络错误') }
    finally { setLoading(false) }
  }

  const deleteRule = async (id: string) => {
    try { const res = await fetch(`${API_BASE}/api/rules/${id}`, { method: 'DELETE' }); if (!res.ok) throw new Error('删除失败'); fetchRules() }
    catch (e: unknown) { setError(e instanceof Error ? e.message : '网络错误') }
  }

  useEffect(() => { fetchRules() }, [])

  return (
    <div className="space-y-4">
      {/* 头部 */}
      <div className="section-header pb-2">
        <div className="flex items-center gap-2 mb-1">
          <div className="w-7 h-7 rounded-lg bg-black flex items-center justify-center">
            <BookOpen className="w-3.5 h-3.5 text-white" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-gray-900">规则管理</h3>
            <p className="text-[10px] text-gray-400">管理审核规则，定义合规标准</p>
          </div>
        </div>
      </div>

      {/* 搜索和操作栏 */}
      <div className="flex items-center gap-2">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" />
          <input
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && searchRules()}
            placeholder="搜索规则..."
            className="w-full pl-9 pr-3 py-2.5 bg-white border border-gray-200 rounded-xl text-xs input-focus"
          />
        </div>
        <button onClick={searchRules} className="btn-ghost px-4 py-2.5 bg-gray-100 rounded-xl text-xs font-medium hover:bg-gray-200 transition">
          搜索
        </button>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="btn-primary px-4 py-2.5 bg-black text-white rounded-xl text-xs font-medium flex items-center gap-1.5"
        >
          <Plus className="w-3 h-3" />{showCreate ? '收起' : '新建'}
        </button>
      </div>

      {/* 新建表单 */}
      {showCreate && (
        <div className="bg-gray-50/80 rounded-xl p-4 border border-gray-100 space-y-3 animate-slide-down">
          <div className="grid grid-cols-2 gap-3">
            <input value={newRule.category} onChange={e => setNewRule({ ...newRule, category: e.target.value })} placeholder="类别 *" className="px-3 py-2 bg-white border border-gray-200 rounded-lg text-xs input-focus" />
            <input value={newRule.title} onChange={e => setNewRule({ ...newRule, title: e.target.value })} placeholder="标题 *" className="px-3 py-2 bg-white border border-gray-200 rounded-lg text-xs input-focus" />
          </div>
          <textarea value={newRule.content} onChange={e => setNewRule({ ...newRule, content: e.target.value })} placeholder="规则内容 *" className="w-full px-3 py-2 bg-white border border-gray-200 rounded-lg text-xs h-16 resize-none input-focus" />
          <div className="grid grid-cols-2 gap-3">
            <select value={newRule.severity} onChange={e => setNewRule({ ...newRule, severity: e.target.value })} className="px-3 py-2 bg-white border border-gray-200 rounded-lg text-xs input-focus">
              <option value="high">🔴 高严重度</option><option value="medium">🟡 中严重度</option><option value="low">⚪ 低严重度</option>
            </select>
            <input value={newRule.keywords} onChange={e => setNewRule({ ...newRule, keywords: e.target.value })} placeholder="关键词（逗号分隔）" className="px-3 py-2 bg-white border border-gray-200 rounded-lg text-xs input-focus" />
          </div>
          <div className="flex gap-2 justify-end pt-1">
            <button onClick={() => setShowCreate(false)} className="btn-ghost px-4 py-2 text-xs text-gray-500 rounded-lg">取消</button>
            <button onClick={createRule} disabled={!newRule.category || !newRule.title || !newRule.content} className="btn-primary px-5 py-2 bg-black text-white rounded-lg text-xs font-medium disabled:opacity-30">创建规则</button>
          </div>
        </div>
      )}

      {error && (
        <div className="p-3 bg-red-50 border border-red-100 rounded-xl text-xs text-red-600 flex items-center gap-2">
          <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />{error}
        </div>
      )}

      {/* 规则列表头部 */}
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-gray-400 font-medium">共 {total} 条规则</span>
        <button onClick={fetchRules} className="btn-ghost flex items-center gap-1 text-[10px] text-gray-400 hover:text-gray-600 px-2 py-1 rounded-md">
          <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />刷新
        </button>
      </div>

      {/* 规则列表 */}
      <div className="space-y-2 max-h-[260px] overflow-y-auto custom-scrollbar pr-1">
        {loading ? (
          <div className="flex items-center justify-center py-12 text-gray-400">
            <Loader2 className="w-4 h-4 animate-spin mr-2" />加载中...
          </div>
        ) : rules.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-gray-300">
            <BookOpen className="w-8 h-8 mb-2" />
            <p className="text-xs">暂无规则</p>
          </div>
        ) : (
          rules.map(r => (
            <div key={r.rule_id} className="card-hover flex items-center justify-between bg-white rounded-xl px-3.5 py-3 border border-gray-100 group">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-gray-900">{r.title}</span>
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                    r.severity === 'high' ? 'bg-red-50 text-red-600 border border-red-100' :
                    r.severity === 'medium' ? 'bg-orange-50 text-orange-600 border border-orange-100' :
                    'bg-gray-50 text-gray-500 border border-gray-100'
                  }`}>
                    {r.severity === 'high' ? '高' : r.severity === 'medium' ? '中' : '低'}
                  </span>
                </div>
                <div className="text-[10px] text-gray-400 mt-1">
                  {r.category}{r.keywords?.length > 0 && <span className="text-gray-300"> · {r.keywords.slice(0, 3).join('、')}</span>}
                </div>
              </div>
              <button onClick={() => deleteRule(r.rule_id)} className="btn-ghost p-2 text-gray-200 hover:text-red-500 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity">
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

/* ── 数据统计 ── */

function StatsWorkbench({ refreshKey }: { refreshKey: number }) {
  const [stats, setStats] = useState<StatsData | null>(null)
  const [loading, setLoading] = useState(false)
  const [recentReviews, setRecentReviews] = useState<DetailItem[]>([])
  const [showRecent, setShowRecent] = useState(false)
  const [detailItem, setDetailItem] = useState<DetailItem | null>(null)

  const fetchStats = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/stats`)
      setStats(await res.json())
    } catch { /* 忽略 */ }
    finally { setLoading(false) }
  }

  const fetchRecent = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/stats/recent`)
      if (res.ok) setRecentReviews(await res.json())
    } catch { /* 忽略 */ }
  }

  useEffect(() => { fetchStats(); fetchRecent() }, [refreshKey])

  return (
    <div className="space-y-4">
      {/* 头部 */}
      <div className="section-header pb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-black flex items-center justify-center">
            <BarChart3 className="w-3.5 h-3.5 text-white" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-gray-900">数据统计</h3>
            <p className="text-[10px] text-gray-400">审核数据总览</p>
          </div>
        </div>
        <button onClick={fetchStats} disabled={loading} className="btn-ghost px-3 py-1.5 bg-gray-100 rounded-lg text-xs font-medium flex items-center gap-1.5">
          <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />刷新
        </button>
      </div>

      {loading && !stats && (
        <div className="flex items-center justify-center py-16 text-gray-400">
          <Loader2 className="w-4 h-4 animate-spin mr-2" />加载中...
        </div>
      )}

      {stats && (
        <div className="space-y-4">
          {/* 指标卡片 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { label: '审核总量', value: stats.total_reviews, unit: '条', icon: FileText, accent: 'border-l-gray-900' },
              { label: '平均耗时', value: (stats.avg_latency_ms / 1000).toFixed(1), unit: 's', icon: BarChart3, accent: 'border-l-blue-500' },
              { label: '置信度', value: (stats.avg_confidence * 100).toFixed(0), unit: '%', icon: TrendingUp, accent: 'border-l-green-500' },
              { label: '复审率', value: (stats.manual_review_rate * 100).toFixed(0), unit: '%', icon: Users, accent: 'border-l-yellow-500' },
            ].map(item => {
              const Icon = item.icon
              return (
                <div key={item.label} className={`stat-card-shine bg-white rounded-xl p-3.5 border border-gray-100 border-l-2 ${item.accent}`}>
                  <div className="flex items-center gap-2 mb-2">
                    <Icon className="w-3.5 h-3.5 text-gray-400" />
                    <span className="text-[10px] text-gray-400 font-medium">{item.label}</span>
                  </div>
                  <div className="text-xl font-bold text-gray-900 stat-value">
                    {item.value}<span className="text-xs font-normal text-gray-300 ml-0.5">{item.unit}</span>
                  </div>
                </div>
              )
            })}
          </div>

          {/* 审核结论分布 */}
          <div className="bg-white rounded-xl p-4 border border-gray-100">
            <h4 className="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-3">审核结论分布</h4>
            <div className="grid grid-cols-3 gap-4">
              {[
                { label: '通过', rate: stats.pass_rate, color: 'bg-green-500', lightBg: 'bg-green-50', textColor: 'text-green-700' },
                { label: '拒绝', rate: stats.reject_rate, color: 'bg-red-500', lightBg: 'bg-red-50', textColor: 'text-red-700' },
                { label: '复审', rate: stats.manual_review_rate, color: 'bg-yellow-500', lightBg: 'bg-yellow-50', textColor: 'text-yellow-700' },
              ].map(item => (
                <div key={item.label} className={`${item.lightBg} rounded-lg p-3 text-center`}>
                  <div className={`text-lg font-bold ${item.textColor} stat-value`}>{(item.rate * 100).toFixed(0)}%</div>
                  <div className="text-[10px] text-gray-500 mt-0.5">{item.label}</div>
                  <div className="w-full bg-white/60 rounded-full h-1 mt-2">
                    <div className={`${item.color} h-1 rounded-full dim-bar`} style={{ width: `${item.rate * 100}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* 违规类型分布 */}
          <div className="bg-white rounded-xl p-4 border border-gray-100">
            <h4 className="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-3">违规类型分布</h4>
            <div className="space-y-2">
              {Object.entries(stats.violation_distribution).sort(([, a], [, b]) => b - a).map(([key, val]) => {
                const maxVal = Math.max(...Object.values(stats.violation_distribution), 1)
                return (
                  <div key={key} className="flex items-center gap-3">
                    <span className="text-[11px] text-gray-600 w-20 text-right font-medium truncate">{key}</span>
                    <div className="flex-1 bg-gray-50 rounded-full h-2">
                      <div className="bg-gray-800 h-2 rounded-full dim-bar" style={{ width: `${(val / maxVal) * 100}%` }} />
                    </div>
                    <span className="text-[10px] font-bold text-gray-500 w-8 text-right">{val}</span>
                  </div>
                )
              })}
            </div>
          </div>

          {/* 维度通过率 */}
          <div className="bg-white rounded-xl p-4 border border-gray-100">
            <h4 className="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-3">维度通过率</h4>
            <div className="grid grid-cols-3 gap-3">
              {[{ key: 'compliance', label: '合规性', color: 'text-blue-600', bg: 'bg-blue-50', bar: 'bg-blue-500' }, { key: 'authenticity', label: '真实性', color: 'text-purple-600', bg: 'bg-purple-50', bar: 'bg-purple-500' }, { key: 'safety', label: '安全性', color: 'text-teal-600', bg: 'bg-teal-50', bar: 'bg-teal-500' }].map(({ key, label, color, bg, bar }) => {
                const dim = stats.dimension_stats[key]; if (!dim) return null
                return (
                  <div key={key} className={`${bg} rounded-lg p-3 text-center`}>
                    <div className={`text-lg font-bold ${color} stat-value`}>{(dim.pass_rate * 100).toFixed(0)}%</div>
                    <div className="text-[10px] text-gray-500 mt-0.5">{label}</div>
                    <div className="text-[9px] text-gray-400 mt-1">{dim.passed}/{dim.total}</div>
                    <div className="w-full bg-white/60 rounded-full h-1 mt-2">
                      <div className={`${bar} h-1 rounded-full dim-bar`} style={{ width: `${dim.pass_rate * 100}%` }} />
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* 最近审核记录 */}
          <div className="bg-white rounded-xl p-4 border border-gray-100">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">最近审核记录</h4>
              <button onClick={() => setShowRecent(!showRecent)} className="btn-ghost text-[10px] text-gray-500 hover:text-black px-2 py-1 rounded-md">
                {showRecent ? '收起' : '展开'}
              </button>
            </div>
            {showRecent && recentReviews.length > 0 && (
              <div className="space-y-1.5 max-h-[200px] overflow-y-auto custom-scrollbar">
                {recentReviews.map((r, i) => (
                  <div key={i} className="flex items-center justify-between bg-gray-50/80 rounded-lg px-3 py-2 hover:bg-gray-50 transition group">
                    <div className="flex items-center gap-2.5 min-w-0 flex-1">
                      <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${r.conclusion === 'pass' ? 'bg-green-500' : r.conclusion === 'reject' ? 'bg-red-500' : 'bg-yellow-500'}`} />
                      <span className="text-xs text-gray-700 truncate">{r.title}</span>
                    </div>
                    <button onClick={() => setDetailItem(r)} className="btn-ghost p-1.5 text-gray-300 hover:text-black rounded-md opacity-0 group-hover:opacity-100 transition-opacity">
                      <Eye className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}
            {showRecent && recentReviews.length === 0 && (
              <p className="text-xs text-gray-300 text-center py-6">暂无审核记录</p>
            )}
          </div>
        </div>
      )}

      {detailItem && (
        <DetailModal item={detailItem} onClose={() => setDetailItem(null)} />
      )}
    </div>
  )
}

/* ── 设置面板 ── */

interface AppSettings {
  concurrent_workers: number
  max_items_per_file: number
  save_folders: {
    pass: string
    manual_review: string
    reject: string
  }
}

function SettingsPanel({ settings, onSave, onClose }: { settings: AppSettings; onSave: (s: AppSettings) => void; onClose: () => void }) {
  const [local, setLocal] = useState(settings)
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    try {
      const res = await fetch(`${API_BASE}/api/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(local),
      })
      if (res.ok) {
        onSave(local)
        onClose()
      }
    } catch { /* 忽略 */ }
    finally { setSaving(false) }
  }

  return ReactDOM.createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 modal-backdrop" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md m-4 modal-content" onClick={e => e.stopPropagation()}>
        <div className="sticky top-0 bg-white/95 backdrop-blur-sm border-b border-gray-100 px-5 py-3.5 flex items-center justify-between z-10">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-lg bg-gray-100 flex items-center justify-center">
              <Settings className="w-3 h-3 text-gray-600" />
            </div>
            <h3 className="text-sm font-semibold text-gray-900">设置</h3>
          </div>
          <button onClick={onClose} className="btn-ghost p-1.5 hover:bg-gray-100 rounded-lg"><X className="w-4 h-4 text-gray-400" /></button>
        </div>

        <div className="p-5 space-y-5">
          {/* 处理参数 */}
          <div>
            <h4 className="text-xs font-semibold text-gray-700 mb-3">处理参数</h4>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-gray-600 mb-1">并发数量</label>
                <select
                  value={local.concurrent_workers}
                  onChange={e => setLocal({ ...local, concurrent_workers: Number(e.target.value) })}
                  className="w-full px-3 py-2.5 border border-gray-200 rounded-xl text-xs input-focus"
                >
                  {[1, 2, 3, 5, 10].map(n => (
                    <option key={n} value={n}>{n} 并发</option>
                  ))}
                </select>
                <p className="text-[10px] text-gray-400 mt-1">并发越高处理越快，但可能触发API限流</p>
              </div>
              <div>
                <label className="block text-xs text-gray-600 mb-1">每个文件最大处理条数</label>
                <select
                  value={local.max_items_per_file}
                  onChange={e => setLocal({ ...local, max_items_per_file: Number(e.target.value) })}
                  className="w-full px-3 py-2.5 border border-gray-200 rounded-xl text-xs input-focus"
                >
                  {[10, 20, 50, 100, 200, 0].map(n => (
                    <option key={n} value={n}>{n === 0 ? '不限制' : `前 ${n} 条`}</option>
                  ))}
                </select>
                <p className="text-[10px] text-gray-400 mt-1">设为"不限制"将处理全部数据（耗时较长）</p>
              </div>
            </div>
          </div>

          {/* 保存文件夹 */}
          <div>
            <h4 className="text-xs font-semibold text-gray-700 mb-3">结果保存文件夹</h4>
            <p className="text-[10px] text-gray-400 mb-3">设置后审核结果将自动保存到对应文件夹，不设置则不保存</p>
            <div className="space-y-3">
              <div>
                <label className="flex items-center gap-1.5 text-xs text-gray-600 mb-1">
                  <div className="w-2 h-2 rounded-full bg-green-400" />通过 - 保存文件夹
                </label>
                <input
                  value={local.save_folders.pass}
                  onChange={e => setLocal({ ...local, save_folders: { ...local.save_folders, pass: e.target.value } })}
                  placeholder="例如: D:\审核结果\通过"
                  className="w-full px-3 py-2.5 border border-gray-200 rounded-xl text-xs input-focus placeholder:text-gray-300"
                />
              </div>
              <div>
                <label className="flex items-center gap-1.5 text-xs text-gray-600 mb-1">
                  <div className="w-2 h-2 rounded-full bg-yellow-400" />复审 - 保存文件夹
                </label>
                <input
                  value={local.save_folders.manual_review}
                  onChange={e => setLocal({ ...local, save_folders: { ...local.save_folders, manual_review: e.target.value } })}
                  placeholder="例如: D:\审核结果\复审"
                  className="w-full px-3 py-2.5 border border-gray-200 rounded-xl text-xs input-focus placeholder:text-gray-300"
                />
              </div>
              <div>
                <label className="flex items-center gap-1.5 text-xs text-gray-600 mb-1">
                  <div className="w-2 h-2 rounded-full bg-red-400" />拒绝 - 保存文件夹
                </label>
                <input
                  value={local.save_folders.reject}
                  onChange={e => setLocal({ ...local, save_folders: { ...local.save_folders, reject: e.target.value } })}
                  placeholder="例如: D:\审核结果\拒绝"
                  className="w-full px-3 py-2.5 border border-gray-200 rounded-xl text-xs input-focus placeholder:text-gray-300"
                />
              </div>
            </div>
          </div>
        </div>

        <div className="sticky bottom-0 bg-white/95 backdrop-blur-sm border-t border-gray-100 px-5 py-3.5 flex gap-2 justify-end z-10">
          <button onClick={onClose} className="btn-ghost px-4 py-2 text-xs text-gray-500 hover:text-gray-700 rounded-lg">取消</button>
          <button onClick={handleSave} disabled={saving} className="btn-primary px-5 py-2 bg-black text-white rounded-xl text-xs font-medium disabled:opacity-30">
            {saving ? '保存中...' : '保存设置'}
          </button>
        </div>
      </div>
    </div>,
    document.body
  )
}

/* ── 主应用 ── */

function App() {
  const [activeTab, setActiveTab] = useState<TabId>('review')
  // 状态提升到 App 层，切换 tab 不丢失
  const [reviewResult, setReviewResult] = useState<ReviewResult | null>(null)
  const [batchStatus, setBatchStatus] = useState<BatchStatus | null>(null)
  const [statsRefreshKey, setStatsRefreshKey] = useState(0)
  const [showSettings, setShowSettings] = useState(false)
  const [settings, setSettings] = useState<AppSettings>({
    concurrent_workers: 5,
    max_items_per_file: 20,
    save_folders: { pass: '', manual_review: '', reject: '' }
  })

  // 加载设置
  useEffect(() => {
    fetch(`${API_BASE}/api/settings`).then(r => r.json()).then(setSettings).catch(() => {})
  }, [])

  // 切换到统计 tab 时刷新数据
  useEffect(() => {
    if (activeTab === 'stats') setStatsRefreshKey(k => k + 1)
  }, [activeTab])

  return (
    <div className="bg-white min-h-screen" style={{ fontFamily: "'Inter', sans-serif" }}>
      <div className="max-w-7xl mx-auto">
        {/* 设置按钮 - 右上角 */}
        <div className="fixed top-4 right-4 z-40">
          <button
            onClick={() => setShowSettings(true)}
            className="w-10 h-10 bg-white border border-gray-200 rounded-full shadow-sm flex items-center justify-center hover:bg-gray-50 hover:border-gray-300 transition"
            title="设置"
          >
            <Settings className="w-4 h-4 text-gray-600" />
          </button>
        </div>

        <section className="px-6 pt-24 pb-16 text-center">
          <div className="inline-flex items-center gap-2 mb-8">
            <div className="w-6 h-6 border border-gray-300 rounded flex items-center justify-center"><Star className="w-3.5 h-3.5 fill-black" /></div>
            <span className="text-sm font-medium text-black">支持图片/视频/文本多模态审核</span>
          </div>
          <h1 className="text-6xl md:text-7xl lg:text-[80px] font-normal leading-[1.1] tracking-tight mb-5">
            审核更快。判断更准。<br /><span className="bg-gradient-to-r from-black via-gray-500 to-gray-400 bg-clip-text text-transparent">AI 驱动智能审核。</span>
          </h1>
          <p className="text-lg md:text-xl text-gray-600 mb-8 max-w-2xl mx-auto">
            支持图片、视频、文本多模态输入，自动检测违禁词、虚假宣传与敏感内容，秒级输出结构化审核报告。
          </p>
          <button onClick={() => setActiveTab('review')} className="bg-black text-white px-8 py-3 rounded-full text-base font-medium hover:bg-gray-800 transition">开始免费试用</button>
        </section>

        <div className="px-6 mx-auto max-w-2xl mb-8">
          <div className="hidden md:flex bg-gray-100/80 backdrop-blur-sm rounded-xl p-1.5 items-center justify-center border border-gray-200/50">
            {TABS.map((tab) => {
              const Icon = tab.icon
              const isActive = activeTab === tab.id
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`relative flex items-center gap-2 px-6 py-2.5 rounded-lg text-sm font-medium transition-all duration-300 ${
                    isActive
                      ? 'bg-white text-black shadow-md shadow-black/5 tab-active-indicator'
                      : 'text-gray-500 hover:text-gray-800 hover:bg-white/50'
                  }`}
                >
                  <Icon className={`w-4 h-4 transition-transform duration-300 ${isActive ? 'scale-110' : ''}`} />
                  {tab.label}
                </button>
              )
            })}
          </div>
          <div className="md:hidden bg-gray-100/80 backdrop-blur-sm rounded-xl p-1.5 border border-gray-200/50">
            <div className="grid grid-cols-2 gap-1.5">
              {TABS.map(tab => {
                const Icon = tab.icon
                const isActive = activeTab === tab.id
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-300 ${
                      isActive
                        ? 'bg-white text-black shadow-md shadow-black/5'
                        : 'text-gray-500 hover:text-gray-800 hover:bg-white/50'
                    }`}
                  >
                    <Icon className="w-4 h-4" />{tab.label}
                  </button>
                )
              })}
            </div>
          </div>
        </div>

        <div className="px-6 mx-auto">
          <div className="relative rounded-3xl overflow-hidden border border-gray-200/60" style={{ minHeight: 560 }}>
            <video src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260319_165750_358b1e72-c921-48b7-aaac-f200994f32fb.mp4" autoPlay loop muted playsInline className="absolute inset-0 w-full h-full object-cover" />
            <div className="absolute inset-0 bg-gradient-to-b from-white/30 via-transparent to-white/20" />
            <div className="relative z-10 h-full flex items-center justify-center p-6 md:p-8">
              <div
                key={activeTab}
                className="w-full max-w-xl glass-card rounded-2xl shadow-xl shadow-black/8 p-6 workbench-enter custom-scrollbar"
                style={{ maxHeight: 500, overflowY: 'auto' }}
              >
                {activeTab === 'review' && <ReviewWorkbench result={reviewResult} setResult={setReviewResult} />}
                {activeTab === 'batch' && <BatchWorkbench status={batchStatus} setStatus={setBatchStatus} />}
                {activeTab === 'rules' && <RulesWorkbench />}
                {activeTab === 'stats' && <StatsWorkbench refreshKey={statsRefreshKey} />}
              </div>
            </div>
          </div>
        </div>

        <div className="mt-24 flex flex-wrap items-center justify-center gap-8 md:gap-12 pb-16">
          {['OpenAI Agents SDK', 'DeepSeek', 'MiMo', 'DashScope', 'Chroma', 'FastAPI', 'React'].map(name => (
            <div key={name} className="flex items-center gap-2 text-gray-400">
              <div className="w-6 h-6 bg-gray-200 rounded" />
              <span className="text-sm font-medium tracking-wide">{name}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 设置面板 */}
      {showSettings && (
        <SettingsPanel
          settings={settings}
          onSave={setSettings}
          onClose={() => setShowSettings(false)}
        />
      )}
    </div>
  )
}

export default App
