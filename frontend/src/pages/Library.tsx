import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type Video, formatDate } from '../api'
import { useAuth } from '../useAuth'

export default function Library() {
  const { user } = useAuth()
  const [videos, setVideos] = useState<Video[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.videos().then(setVideos).catch((e) => setError(e.message))
  }, [])

  if (error) return <p className="error">{error}</p>
  if (!videos) return <div className="spinner" aria-label="Loading" />

  return (
    <>
      <div className="page-head">
        <h1>Hi {user?.full_name.split(' ')[0]}, pick a session</h1>
        <p className="muted">{videos.length} video{videos.length === 1 ? '' : 's'} available</p>
      </div>
      {videos.length === 0 ? (
        <div className="empty">
          <h2>No videos yet</h2>
          {user?.is_admin ? (
            <p>Upload your first demo from the <Link to="/admin">admin page</Link>.</p>
          ) : (
            <p>New sessions are on the way. Check back soon.</p>
          )}
        </div>
      ) : (
        <div className="grid">
          {videos.map((v) => (
            <Link key={v.id} to={`/videos/${v.id}`} className="video-card">
              <div className="thumb" aria-hidden>
                <span className="play">▶</span>
              </div>
              <div className="video-card-body">
                <h3>{v.title}</h3>
                {v.description && <p className="clamp">{v.description}</p>}
                <p className="meta">{formatDate(v.created_at)} · {v.views} view{v.views === 1 ? '' : 's'}</p>
              </div>
            </Link>
          ))}
        </div>
      )}
    </>
  )
}
