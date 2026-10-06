import { Link } from 'react-router-dom'

const features = [
  { title: 'Cloud-native by design', text: 'GKE, Cloud SQL and Memorystore, provisioned end to end with Terraform.' },
  { title: 'Secure delivery', text: 'Signed images, GitOps with ArgoCD and secrets served from HashiCorp Vault.' },
  { title: 'Observable', text: 'Prometheus metrics, Grafana dashboards and SLOs on every request.' },
]

export default function Landing() {
  return (
    <>
      <section className="hero">
        <p className="eyebrow">Learning hub</p>
        <h1>Learn DevSecOps on Google Cloud, one demo at a time.</h1>
        <p className="lead">
          Watch hands-on walkthroughs of a production-grade platform: from Terraform to GitOps,
          Vault and SRE practices.
        </p>
        <div className="hero-actions">
          <Link to="/signup" className="btn btn-primary btn-lg">Create a free account</Link>
          <Link to="/login" className="btn btn-ghost btn-lg">Log in</Link>
        </div>
      </section>
      <section className="features">
        {features.map((f) => (
          <article key={f.title} className="feature">
            <h3>{f.title}</h3>
            <p>{f.text}</p>
          </article>
        ))}
      </section>
    </>
  )
}
