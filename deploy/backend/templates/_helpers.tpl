{{- define "backend.selectorLabels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "backend.labels" -}}
{{ include "backend.selectorLabels" . }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
app.kubernetes.io/part-of: learnhub
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/version: {{ .Values.image.tag | trunc 63 | quote }}
{{- end }}

{{- define "backend.image" -}}
{{ .Values.image.repository }}:{{ required "image.tag is required (the release commit SHA)" .Values.image.tag }}
{{- end }}

{{/* Pod and container settings shared by the API and the migration job. */}}
{{- define "backend.podSecurityContext" -}}
runAsNonRoot: true
runAsUser: 10001
runAsGroup: 10001
seccompProfile:
  type: RuntimeDefault
{{- end }}

{{- define "backend.containerSecurityContext" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop: ["ALL"]
{{- end }}

{{- define "backend.env" -}}
envFrom:
  - configMapRef:
      name: {{ .Release.Name }}
  - secretRef:
      name: {{ .Values.secretName }}
{{- end }}

{{- define "backend.volumeMounts" -}}
- name: tmp
  mountPath: /tmp
{{- if .Values.caCerts }}
- name: ca
  mountPath: /etc/learnhub/ca
  readOnly: true
{{- end }}
{{- end }}

{{- define "backend.volumes" -}}
- name: tmp
  emptyDir:
    sizeLimit: 64Mi
{{- if .Values.caCerts }}
- name: ca
  configMap:
    name: {{ .Release.Name }}-ca
{{- end }}
{{- end }}

{{- define "backend.nodeSelector" -}}
{{- with .Values.computeClass }}
nodeSelector:
  cloud.google.com/compute-class: {{ . }}
{{- end }}
{{- end }}
