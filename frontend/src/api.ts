export type User = {
  id: string
  email: string
  full_name: string
  is_admin: boolean
  created_at: string
}

export type Video = {
  id: string
  title: string
  description: string
  content_type: string
  size_bytes: number | null
  status: 'pending' | 'ready'
  is_published: boolean
  created_at: string
  views: number
}

export type Playback = Video & { url: string }

export type UploadTicket = {
  video: Video
  upload_url: string
  method: string
  headers: Record<string, string>
}

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** Turns FastAPI's `detail` (a string, or a list of validation errors) into one readable line. */
export function describeError(detail: unknown, fallback = 'Something went wrong'): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((e) => {
        const field = Array.isArray(e?.loc) ? e.loc[e.loc.length - 1] : undefined
        const msg = typeof e?.msg === 'string' ? e.msg.replace(/^Value error, /, '') : ''
        return field ? `${field}: ${msg}` : msg
      })
      .filter(Boolean)
      .join('; ')
  }
  return fallback
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    ...init,
    credentials: 'same-origin', // the session is an httpOnly cookie
    headers: { 'Content-Type': 'application/json', ...init.headers },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new ApiError(res.status, describeError(body?.detail, res.statusText))
  }
  return (res.status === 204 ? undefined : await res.json()) as T
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  body: body === undefined ? undefined : JSON.stringify(body),
})

export const api = {
  me: () => request<User>('/api/auth/me'),
  login: (email: string, password: string) =>
    request<User>('/api/auth/login', json('POST', { email, password })),
  signup: (email: string, full_name: string, password: string) =>
    request<User>('/api/auth/signup', json('POST', { email, full_name, password })),
  logout: () => request<void>('/api/auth/logout', json('POST')),

  videos: () => request<Video[]>('/api/videos'),
  video: (id: string) => request<Playback>(`/api/videos/${id}`),

  adminVideos: () => request<Video[]>('/api/admin/videos'),
  adminUsers: () => request<User[]>('/api/admin/users'),
  createVideo: (meta: {
    title: string
    description: string
    filename: string
    content_type: string
    size_bytes: number
  }) => request<UploadTicket>('/api/admin/videos', json('POST', meta)),
  completeVideo: (id: string) => request<Video>(`/api/admin/videos/${id}/complete`, json('POST')),
  updateVideo: (id: string, changes: Partial<Pick<Video, 'title' | 'description' | 'is_published'>>) =>
    request<Video>(`/api/admin/videos/${id}`, json('PATCH', changes)),
  deleteVideo: (id: string) => request<void>(`/api/admin/videos/${id}`, json('DELETE')),
}

/**
 * Uploads straight to the signed URL (GCS in production), bypassing the API.
 * Uses XHR rather than fetch because fetch can't report upload progress.
 */
export function uploadFile(
  ticket: UploadTicket,
  file: File,
  onProgress: (fraction: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open(ticket.method, ticket.upload_url)
    Object.entries(ticket.headers).forEach(([k, v]) => xhr.setRequestHeader(k, v))
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total)
    xhr.onload = () =>
      xhr.status >= 200 && xhr.status < 300
        ? resolve()
        : reject(new ApiError(xhr.status, `Upload failed (${xhr.status})`))
    xhr.onerror = () => reject(new ApiError(0, 'Upload failed: network error'))
    xhr.send(file)
  })
}

export function formatBytes(bytes: number | null): string {
  if (bytes === null) return '—'
  const units = ['B', 'KB', 'MB', 'GB']
  let value = bytes
  let i = 0
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024
    i++
  }
  return `${value.toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}
