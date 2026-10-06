import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError, type User, type Video, formatBytes, formatDate, uploadFile } from '../api'

function UploadForm({ onUploaded }: { onUploaded: () => void }) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [publish, setPublish] = useState(true)
  const [progress, setProgress] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!file) return
    setError(null)
    setProgress(0)
    try {
      // 1. register the video, 2. upload directly to storage, 3. confirm, 4. publish
      const ticket = await api.createVideo({
        title,
        description,
        filename: file.name,
        content_type: file.type || 'video/mp4',
        size_bytes: file.size,
      })
      await uploadFile(ticket, file, setProgress)
      await api.completeVideo(ticket.video.id)
      if (publish) await api.updateVideo(ticket.video.id, { is_published: true })
      setTitle('')
      setDescription('')
      setFile(null)
      if (fileInput.current) fileInput.current.value = ''
      onUploaded()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Upload failed')
    } finally {
      setProgress(null)
    }
  }

  const uploading = progress !== null
  return (
    <form className="card upload" onSubmit={onSubmit}>
      <h2>Upload a video</h2>
      <label>
        Title
        <input required maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} />
      </label>
      <label>
        Description
        <textarea rows={3} maxLength={5000} value={description}
          onChange={(e) => setDescription(e.target.value)} />
      </label>
      <label>
        Video file <small className="muted">(MP4/H.264 plays everywhere)</small>
        <input ref={fileInput} type="file" required accept="video/mp4,video/webm,video/quicktime,video/ogg"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      </label>
      <label className="checkbox">
        <input type="checkbox" checked={publish} onChange={(e) => setPublish(e.target.checked)} />
        Publish immediately
      </label>
      {uploading && (
        <div className="progress" role="progressbar" aria-valuenow={Math.round(progress * 100)}>
          <div style={{ width: `${progress * 100}%` }} />
          <span>{Math.round(progress * 100)}%</span>
        </div>
      )}
      {error && <p className="error" role="alert">{error}</p>}
      <button className="btn btn-primary" disabled={uploading || !file}>
        {uploading ? 'Uploading…' : `Upload${file ? ` (${formatBytes(file.size)})` : ''}`}
      </button>
    </form>
  )
}

export default function Admin() {
  const [videos, setVideos] = useState<Video[]>([])
  const [users, setUsers] = useState<User[]>([])
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    Promise.all([api.adminVideos(), api.adminUsers()])
      .then(([v, u]) => {
        setVideos(v)
        setUsers(u)
      })
      .catch((e) => setError(e.message))
  }, [])

  useEffect(load, [load])

  const run = (action: Promise<unknown>) => action.then(load).catch((e) => setError(e.message))

  return (
    <>
      <div className="page-head">
        <h1>Admin</h1>
        <p className="muted">{users.length} registered user{users.length === 1 ? '' : 's'}</p>
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="admin-layout">
        <UploadForm onUploaded={load} />
        <section className="card">
          <h2>Videos</h2>
          {videos.length === 0 ? (
            <p className="muted">Nothing uploaded yet.</p>
          ) : (
            <table className="table">
              <thead>
                <tr><th>Title</th><th>Size</th><th>Views</th><th>Status</th><th /></tr>
              </thead>
              <tbody>
                {videos.map((v) => (
                  <tr key={v.id}>
                    <td>
                      {v.status === 'ready' ? <Link to={`/videos/${v.id}`}>{v.title}</Link> : v.title}
                      <div className="muted small">{formatDate(v.created_at)}</div>
                    </td>
                    <td>{formatBytes(v.size_bytes)}</td>
                    <td>{v.views}</td>
                    <td>
                      <span className={`badge ${v.is_published ? 'badge-ok' : ''}`}>
                        {v.status === 'pending' ? 'uploading' : v.is_published ? 'published' : 'draft'}
                      </span>
                    </td>
                    <td className="actions">
                      {v.status === 'ready' && (
                        <button className="btn btn-ghost btn-sm"
                          onClick={() => run(api.updateVideo(v.id, { is_published: !v.is_published }))}>
                          {v.is_published ? 'Unpublish' : 'Publish'}
                        </button>
                      )}
                      <button className="btn btn-danger btn-sm"
                        onClick={() => confirm(`Delete "${v.title}"?`) && run(api.deleteVideo(v.id))}>
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>
      <section className="card">
        <h2>Users</h2>
        <table className="table">
          <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Joined</th></tr></thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.full_name}</td>
                <td>{u.email}</td>
                <td>{u.is_admin ? 'admin' : 'learner'}</td>
                <td>{formatDate(u.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  )
}
