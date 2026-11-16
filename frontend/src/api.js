const BASE = import.meta.env.VITE_API_BASE || '/api'
const TOKEN_KEY = 'pp_token'

export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const setToken = (t) => (t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY))

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

async function request(path, { method = 'GET', body, form } = {}) {
  const headers = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  const options = { method, headers }
  if (form) options.body = form
  else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    options.body = JSON.stringify(body)
  }

  const res = await fetch(BASE + path, options)
  const text = await res.text()
  const data = text ? safeJson(text) : null

  if (res.status === 401 && !path.startsWith('/auth/')) {
    setToken(null)
    window.dispatchEvent(new Event('pp:logout'))
  }
  if (!res.ok) {
    const detail = (data && (data.detail || data.message)) || `Request failed (${res.status})`
    throw new ApiError(typeof detail === 'string' ? detail : JSON.stringify(detail), res.status)
  }
  return data
}

function safeJson(text) {
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

const qs = (params = {}) =>
  Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
    .join('&')

export const api = {
  // auth
  demo: () => request('/auth/demo'),
  login: (email, password) => request('/auth/login', { method: 'POST', body: { email, password } }),
  register: (email, password, name) =>
    request('/auth/register', { method: 'POST', body: { email, password, name } }),
  logout: () => request('/auth/logout', { method: 'POST' }),
  me: () => request('/auth/me'),

  // profile
  updateProfile: (body) => request('/profile', { method: 'PUT', body }),
  onboarding: (body) => request('/onboarding', { method: 'POST', body }),
  availability: () => request('/availability'),

  // academics
  dashboard: () => request('/dashboard'),
  courses: () => request('/courses'),
  deleteCourse: (id) => request(`/courses/${id}`, { method: 'DELETE' }),
  parseSyllabusText: (text) => {
    const form = new FormData()
    form.append('text', text)
    return request('/syllabus/parse', { method: 'POST', form })
  },
  parseSyllabusFile: (file) => {
    const form = new FormData()
    form.append('file', file)
    return request('/syllabus/parse', { method: 'POST', form })
  },
  confirmSyllabus: (draft) => request('/syllabus/confirm', { method: 'POST', body: { draft } }),
  addMark: (assessment_id, score, max_score = 100) =>
    request('/marks', { method: 'POST', body: { assessment_id, score, max_score } }),

  // planning
  plan: () => request('/plan'),
  buildPlan: () => request('/plan/build', { method: 'POST' }),
  replan: () => request('/plan/replan', { method: 'POST' }),
  logBlock: (id, done, minutes) =>
    request(`/blocks/${id}/log?${qs({ done, minutes })}`, { method: 'POST' }),

  // practice
  generatePractice: (payload) => request('/practice/generate', { method: 'POST', body: payload }),
  submitPractice: (id, responses, duration_s = 0) =>
    request(`/practice/${id}/submit`, { method: 'POST', body: { responses, duration_s } }),
  practiceHistory: () => request('/practice/history'),

  // tutor
  ask: (question, topic_id, level = 'intermediate') =>
    request('/tutor/ask', { method: 'POST', body: { question, topic_id, level } }),
  tutorHistory: () => request('/tutor/history'),

  // viva
  startViva: (topic_id, kind = 'viva') => request('/viva/start', { method: 'POST', body: { topic_id, kind } }),
  answerViva: (id, answer) => request(`/viva/${id}/answer`, { method: 'POST', body: { answer } }),
  vivaHistory: () => request('/viva/history'),

  // revision
  dueCards: () => request('/revision/due'),
  reviewCard: (card_id, rating) => request('/revision/review', { method: 'POST', body: { card_id, rating } }),
  generateCards: (topic_ids, count = 6) =>
    request('/revision/generate', { method: 'POST', body: { topic_ids, count } }),

  // analytics + assignments + recommendations + advisor
  analytics: () => request('/analytics'),
  assignments: () => request('/assignments'),
  createAssignment: (body) => request('/assignments', { method: 'POST', body }),
  toggleTask: (assignmentId, taskId) =>
    request(`/assignments/${assignmentId}/tasks/${taskId}/toggle`, { method: 'POST' }),
  deleteAssignment: (id) => request(`/assignments/${id}`, { method: 'DELETE' }),
  recommendations: () => request('/recommendations'),
  actOnRecommendation: (id, status) =>
    request(`/recommendations/${id}/act`, { method: 'POST', body: { status } }),
  chat: (message) => request('/advisor/chat', { method: 'POST', body: { message } }),
  advisorHistory: () => request('/advisor/history'),
}
