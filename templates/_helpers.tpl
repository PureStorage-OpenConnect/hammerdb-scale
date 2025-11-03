{{/*
Expand the name of the chart.
*/}}
{{- define "hammerdb-scale-test.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "hammerdb-scale-test.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "hammerdb-scale-test.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "hammerdb-scale-test.labels" -}}
helm.sh/chart: {{ include "hammerdb-scale-test.chart" . }}
{{ include "hammerdb-scale-test.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "hammerdb-scale-test.selectorLabels" -}}
app.kubernetes.io/name: {{ include "hammerdb-scale-test.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Get database driver for a given type
*/}}
{{- define "hammerdb-scale-test.dbDriver" -}}
{{- $dbType := . -}}
{{- if eq $dbType "mssql" -}}
mssqls
{{- else if eq $dbType "postgres" -}}
pg
{{- else if eq $dbType "oracle" -}}
oracle
{{- else if eq $dbType "mysql" -}}
mysql
{{- else -}}
{{- fail (printf "Unsupported database type: %s" $dbType) -}}
{{- end -}}
{{- end }}

{{/*
Get merged TPC-C configuration for a target
Merges global hammerdb.tprocc defaults with target-specific overrides
Usage: include "hammerdb-scale-test.tprocc-config" (dict "root" $ "target" .)
*/}}
{{- define "hammerdb-scale-test.tprocc-config" -}}
{{- $global := .root.Values.hammerdb.tprocc | default dict -}}
{{- $target := .target.tprocc | default dict -}}
{{- $merged := merge (deepCopy $target) $global -}}
{{- toYaml $merged -}}
{{- end }}

{{/*
Get merged TPC-H configuration for a target
Usage: include "hammerdb-scale-test.tproch-config" (dict "root" $ "target" .)
*/}}
{{- define "hammerdb-scale-test.tproch-config" -}}
{{- $global := .root.Values.hammerdb.tproch | default dict -}}
{{- $target := .target.tproch | default dict -}}
{{- $merged := merge (deepCopy $target) $global -}}
{{- toYaml $merged -}}
{{- end }}

{{/*
Get merged connection configuration for a target
Usage: include "hammerdb-scale-test.connection-config" (dict "root" $ "target" .)
*/}}
{{- define "hammerdb-scale-test.connection-config" -}}
{{- $global := .root.Values.hammerdb.connection | default dict -}}
{{- $target := .target.connection | default dict -}}
{{- $merged := merge (deepCopy $target) $global -}}
{{- toYaml $merged -}}
{{- end }}
