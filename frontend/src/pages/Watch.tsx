import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError, type Playback, formatDate } from '../api'

export default function Watch() {
  const { id } = useParams<{ id: string }>()
  const [video, setVideo] = useState<Playback | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    api
      .video(id)
      .then(setVideo)
      .catch((e) => setError(e instanceof ApiError && e.status === 404 ? 'Video not found' : e.message))
  }, [id])

  if (error)
    return (
      <div className="empty">
        <h2>{error}</h2>
        <Link to="/">Back to the library</Link>
      </div>
    )
  if (!video) return <div className="spinner" aria-label="Loading" />

  return (
    <article className="watch">
      <Link to="/" className="back">← Library</Link>
      {/* The src is a short-lived signed URL; the browser streams it with Range requests. */}
      <video className="player" src={video.url} controls preload="metadata" playsInline />
      <h1>{video.title}</h1>
      <p className="meta">{formatDate(video.created_at)} · {video.views} view{video.views === 1 ? '' : 's'}</p>
      {video.description && <p className="description">{video.description}</p>}
    </article>
  )
}
