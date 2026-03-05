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

{{/*
Get merged Oracle configuration for a target
Merges databases.oracle defaults with target-specific Oracle overrides
Usage: include "hammerdb-scale-test.oracle-config" (dict "root" $ "target" .)
Returns: service, tablespace, tempTablespace, tproccUser, tprochUser, degreeOfParallel
*/}}
{{- define "hammerdb-scale-test.oracle-config" -}}
{{- $oracleDefaults := .root.Values.databases.oracle | default dict -}}
{{- $target := .target -}}

{{/* Service name or SID */}}
service: {{ $target.oracleService | default $oracleDefaults.service | default "ORCL" | quote }}
{{- if $target.oracleSid }}
sid: {{ $target.oracleSid | quote }}
{{- end }}

{{/* Tablespaces */}}
tablespace: {{ $target.oracleTablespace | default $oracleDefaults.tablespace | default "USERS" | quote }}
tempTablespace: {{ $target.oracleTempTablespace | default $oracleDefaults.tempTablespace | default "TEMP" | quote }}
port: {{ $target.oraclePort | default $oracleDefaults.port | default 1521 }}

{{/* TPC-C user and password */}}
{{- if $target.tprocc }}
tproccUser: {{ $target.tprocc.user | default (($oracleDefaults.tprocc | default dict).user) | default "tpcc" | quote }}
tproccPassword: {{ $target.tprocc.password | default (($oracleDefaults.tprocc | default dict).password) | default $target.password | quote }}
{{- else }}
tproccUser: {{ (($oracleDefaults.tprocc | default dict).user) | default "tpcc" | quote }}
tproccPassword: {{ (($oracleDefaults.tprocc | default dict).password) | default $target.password | quote }}
{{- end }}

{{/* TPC-H user, password, and parallelism */}}
{{- if $target.tproch }}
tprochUser: {{ $target.tproch.user | default (($oracleDefaults.tproch | default dict).user) | default "tpch" | quote }}
tprochPassword: {{ $target.tproch.password | default (($oracleDefaults.tproch | default dict).password) | default $target.password | quote }}
degreeOfParallel: {{ $target.tproch.degreeOfParallel | default (($oracleDefaults.tproch | default dict).degreeOfParallel) | default 8 }}
{{- else }}
tprochUser: {{ (($oracleDefaults.tproch | default dict).user) | default "tpch" | quote }}
tprochPassword: {{ (($oracleDefaults.tproch | default dict).password) | default $target.password | quote }}
degreeOfParallel: {{ (($oracleDefaults.tproch | default dict).degreeOfParallel) | default 8 }}
{{- end }}
{{- end }}

{{/*
Get list of database types used in targets
Returns a JSON object with a "types" array containing unique database types
Usage: include "hammerdb-scale-test.usedDatabaseTypes" . | fromJson
*/}}
{{- define "hammerdb-scale-test.usedDatabaseTypes" -}}
{{- $types := list -}}
{{- range .Values.targets -}}
  {{- if not (has .type $types) -}}
    {{- $types = append $types .type -}}
  {{- end -}}
{{- end -}}
{{- dict "types" $types | toJson -}}
{{- end }}
