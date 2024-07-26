import os
import yaml

def ask_question(question, default=None):
    if default:
        question += f" (default: {default})"
    return input(question + ": ") or default

def generate_values(chart_name, namespace, image, replicas, env_vars, args, resources, security_context, image_pull_secrets, probes):
    deployment_name = f"{chart_name}-deployment"
    service_name = f"{chart_name}-service"
    service_account_name = f"{chart_name}-serviceaccount"
    
    values = {
        "namespace": namespace,
        "replicaCount": replicas,
        "image": {
            "repository": image,
            "pullPolicy": "Always",
            "tag": "latest",
        },
        "resources": resources if resources else {},
        "securityContext": security_context if security_context else {},
        "automountServiceAccountToken": False,
        "imagePullSecrets": [{"name": secret} for secret in image_pull_secrets],
        "nameOverride": deployment_name,
        "fullnameOverride": deployment_name,
        "serviceAccount": {
            "name": service_account_name
        },
        "probes": probes,
        "env": env_vars,
        "args": args if args else [],  # Ensure args is always a list
    }
    return values, deployment_name, service_name, service_account_name

def generate_deployment(values):
    return """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Values.nameOverride | default .Chart.Name }}
  namespace: {{ .Values.namespace }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      app: {{ .Values.nameOverride | default .Chart.Name }}
  template:
    metadata:
      labels:
        app: {{ .Values.nameOverride | default .Chart.Name }}
    spec:
      containers:
      - name: {{ .Values.nameOverride | default .Chart.Name }}
        image: {{ .Values.image.repository }}:{{ .Values.image.tag }}
        imagePullPolicy: {{ .Values.image.pullPolicy }}
        {{- if .Values.env }}
        env:
        {{- range .Values.env }}
        - name: {{ .name }}
          value: {{ .value }}
        {{- end }}
        {{- end }}
        {{- if .Values.args }}
        args:
        {{- range .Values.args }}
        - {{ . }}
        {{- end }}
        {{- end }}
        {{- if .Values.resources }}
        resources:
          requests:
            memory: {{ .Values.resources.requests.memory }}
            cpu: {{ .Values.resources.requests.cpu }}
          limits:
            memory: {{ .Values.resources.limits.memory }}
            cpu: {{ .Values.resources.limits.cpu }}
        {{- end }}
        {{- if .Values.securityContext }}
        securityContext:
          {{- toYaml .Values.securityContext | nindent 10 }}
        {{- end }}
        {{- if .Values.probes.enabled }}
        livenessProbe:
          initialDelaySeconds: {{ .Values.probes.settings.livenessProbeInitialDelaySeconds }}
        readinessProbe:
          initialDelaySeconds: {{ .Values.probes.settings.readinessProbeInitialDelaySeconds }}
        {{- end }}
      serviceAccountName: {{ .Values.serviceAccount.name }}
      automountServiceAccountToken: {{ .Values.automountServiceAccountToken }}
      {{- if .Values.imagePullSecrets }}
      imagePullSecrets:
      {{- range .Values.imagePullSecrets }}
      - name: {{ .name }}
      {{- end }}
      {{- end }}
"""

def generate_serviceaccount(values):
    if values.get('serviceAccount', {}).get('name'):
        return """
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {{ .Values.serviceAccount.name }}
  namespace: {{ .Values.namespace }}
"""
    return ""

def generate_rbac(rbac_type, values):
    if rbac_type == '1':
        return """
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: {{ .Values.serviceAccount.name }}
rules:
  - apiGroups: [""]
    resources: ["services","endpoints","pods"]
    verbs: ["get","watch","list"]
  - apiGroups: ["extensions","networking.k8s.io"]
    resources: ["ingresses"]
    verbs: ["get","watch","list"]
  - apiGroups: [""]
    resources: ["nodes"]
    verbs: ["list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: {{ .Values.serviceAccount.name }}-binding
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: {{ .Values.serviceAccount.name }}
subjects:
  - kind: ServiceAccount
    name: {{ .Values.serviceAccount.name }}
    namespace: {{ .Values.namespace }}
"""
    elif rbac_type == '2':
        return """
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: {{ .Values.serviceAccount.name }}
  namespace: {{ .Values.namespace }}
rules:
  - apiGroups: [""]
    resources: ["services","endpoints","pods"]
    verbs: ["get","watch","list"]
  - apiGroups: ["extensions","networking.k8s.io"]
    resources: ["ingresses"]
    verbs: ["get","watch","list"]
  - apiGroups: [""]
    resources: ["nodes"]
    verbs: ["list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: {{ .Values.serviceAccount.name }}-binding
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: {{ .Values.serviceAccount.name }}
subjects:
  - kind: ServiceAccount
    name: {{ .Values.serviceAccount.name }}
    namespace: {{ .Values.namespace }}
"""
    return ""

def generate_chart_files():
    chart_name = ask_question("Enter the name of the Helm chart", "my-chart")
    namespace = ask_question("Enter the Kubernetes namespace", "default")
    image = ask_question("Enter the Docker image", "my-image")
    replicas = int(ask_question("Enter the number of replicas", "1"))

    env_vars = []
    add_env = ask_question("Do you want to add environment variables? (yes/no)", "no").lower()
    if add_env == 'yes':
        while True:
            env_input = ask_question("Enter environment variable (key=value) or leave empty to finish")
            if not env_input:
                break
            key, value = env_input.split('=', 1)
            env_vars.append({'name': key, 'value': value})

    args = []
    add_args = ask_question("Do you want to add container arguments? (yes/no)", "no").lower()
    if add_args == 'yes':
        while True:
            arg = ask_question("Enter an argument (or leave empty to finish)")
            if not arg:
                break
            args.append(arg)

    resources = None
    add_resources = ask_question("Do you want to add resource requests/limits? (yes/no)", "no").lower()
    if add_resources == 'yes':
        resources = {
            "limits": {
                "cpu": "0.5",
                "memory": "512Mi"
            },
            "requests": {
                "cpu": "100m",
                "memory": "256Mi"
            }
        }

    security_context = None
    add_security_context = ask_question("Do you want to add security context? (yes/no)", "no").lower()
    if add_security_context == 'yes':
        security_context = {
            "allowPrivilegeEscalation": False,
            "readOnlyRootFilesystem": False,
            "runAsNonRoot": True,
            "runAsUser": 1000
        }

    image_pull_secrets = []
    add_image_pull_secrets = ask_question("Do you need any image pull secrets? (yes/no)", "no").lower()
    if add_image_pull_secrets == 'yes':
        secret_name = ask_question("Enter the image pull secret name")
        image_pull_secrets.append(secret_name)

    probes = {"enabled": False}
    add_probes = ask_question("Do you want to add readiness and liveness probes? (yes/no)", "no").lower()
    if add_probes == 'yes':
        probes = {
            "enabled": True,
            "settings": {
                "livenessProbeInitialDelaySeconds": 180,
                "readinessProbeInitialDelaySeconds": 180
            }
        }

    rbac_type = ask_question("Do you need RBAC controls? Press 1 for ClusterRole, 2 for Role, 0 for None", "0")

    values, deployment_name, service_name, service_account_name = generate_values(
        chart_name, namespace, image, replicas, env_vars, args, resources, security_context, image_pull_secrets, probes
    )

    # Create the necessary directories
    os.makedirs(os.path.join(chart_name, "templates"), exist_ok=True)
    
    # Write Chart.yaml
    with open(os.path.join(chart_name, "Chart.yaml"), "w") as f:
        f.write(f"""
apiVersion: v2
name: {chart_name}
description: A Helm chart for Kubernetes
version: 0.1.0
    """)

    # creates the values file
    with open(os.path.join(chart_name, "values.yaml"), "w") as f:
        yaml.dump(values, f)

    # creates the deployment 
    with open(os.path.join(chart_name, "templates/deployment.yaml"), "w") as f:
        f.write(generate_deployment(values))

    # creates the serviceaccount
    with open(os.path.join(chart_name, "templates/serviceaccount.yaml"), "w") as f:
        f.write(generate_serviceaccount(values))

    # creates the rbac configuration
    with open(os.path.join(chart_name, "templates/rbac.yaml"), "w") as f:
        f.write(generate_rbac(rbac_type, values))

    print(f"Helm Chart generated in {chart_name}/")

generate_chart_files()