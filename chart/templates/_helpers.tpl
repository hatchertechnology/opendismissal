{{- define "opendismissal.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "opendismissal.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "opendismissal.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" -}}
{{- end -}}

{{- define "opendismissal.labels" -}}
app.kubernetes.io/name: {{ include "opendismissal.name" . }}
helm.sh/chart: {{ include "opendismissal.chart" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "opendismissal.selectorLabels" -}}
app.kubernetes.io/name: {{ include "opendismissal.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app: {{ .Values.appLabel }}
{{- end -}}

{{- define "opendismissal.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "opendismissal.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{- define "opendismissal.serviceName" -}}
{{- if .Values.service.nameOverride -}}
{{- .Values.service.nameOverride -}}
{{- else -}}
{{- include "opendismissal.fullname" . -}}
{{- end -}}
{{- end -}}