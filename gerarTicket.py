from jira import JIRA
from datetime import datetime, timedelta, timezone
import random

# Configurações da API JIRA
jira_url = 'https://sentinelacomvc.atlassian.net/'
username = 'henrique_ab8@hotmail.com'
api_token = ''

jira = JIRA(server=jira_url, basic_auth=(username, api_token))

# Mapas e thresholds
JIRA_SEVERITY_MAP = {
    "critico": "Crítico", 
    "grave": "Grave",     
    "leve": "Leve"       
}

JIRA_RECURSO_MAP = {
    "cpu_percent": "CPU",  
    "ram_percent": "Memória",
    "disk_percent": "Disco",     
    "disk_usage_gb": "Disco",  
    "net_upload": "Rede",    
    "net_download": "Rede",
    "link_speed_mbps": "Rede",
    "net_usage_percent": "Rede",
    "battery_percent": "Bateria",   
    "cpu_freq_ghz": "CPU",     
    "uptime_hours": "Tempo de Uso"   
}

CPU_CRITICAL_THRESHOLD = 95.0
RAM_CRITICAL_THRESHOLD = 95.0
DISK_HIGH_THRESHOLD = 90.0
NETWORK_USAGE_HIGH_THRESHOLD = 90.0

METRIC_THRESHOLDS_FAIXA = {
    "cpu_percent": { 
        "critico": {"val": CPU_CRITICAL_THRESHOLD, "sum": "CPU - Nível Crítico", "desc": "Aumento crítico de CPU: {v:.1f}%"},
        "grave":   {"val": 75.0,                     "sum": "CPU - Nível Grave",   "desc": "Uso de CPU grave: {v:.1f}%"},
        "leve":    {"val": 60.0,                     "sum": "CPU - Nível Leve",    "desc": "Leve aumento no uso de CPU: {v:.1f}%"}
    },
    "ram_percent": {
        "critico": {"val": RAM_CRITICAL_THRESHOLD, "sum": "RAM - Nível Crítico", "desc": "Aumento crítico de RAM: {v:.1f}%"},
        "grave":   {"val": 85.0,                     "sum": "RAM - Nível Grave",   "desc": "Aumento grave de RAM: {v:.1f}%"},
        "leve":    {"val": 70.0,                     "sum": "RAM - Nível Leve",    "desc": "Leve aumento no uso da RAM: {v:.1f}%"}
    },
    "disk_percent": { 
        "grave":   {"val": DISK_HIGH_THRESHOLD,      "sum": "Disco - Nível Grave", "desc": "Uso de Disco ('/') em {v:.1f}%"},
        "leve":    {"val": 70.0,                     "sum": "Disco - Nível Leve",    "desc": "Uso de Disco ('/') em {v:.1f}%"}
    },
    "net_usage_percent": {
        "critico": {"val": NETWORK_USAGE_HIGH_THRESHOLD, "sum": "Uso de Rede - Crítico", "desc": "Aumento crítico no uso do link ({v:.1f}%)"},
        "grave":   {"val": 75.0,                         "sum": "Uso de Rede - Grave",   "desc": "Aumento grave no uso do link ({v:.1f}%)"},
        "leve":    {"val": 60.0,                         "sum": "Uso de Rede - Leve",    "desc": "Leve aumento no uso do link ({v:.1f}%)"}
    }
}

SPECIFIC_ALERT_MESSAGES = {
    "battery_grave_0_percent":  {"sum": "Bateria Crítica (0%)", "desc": "Nível de bateria em {v:.0f}%. Robô pode estar inativo*", "jira_sev": "Grave"},
    "battery_leve_low":         {"sum": "Bateria Baixa",        "desc": "Nível de bateria abaixo de {v:.0f}%", "jira_sev": "Leve"},
    "net_upload_no_connection": {"sum": "Rede - Sem Upload",    "desc": "Velocidade de upload ({v:.2f} Mbps) próxima de zero. Possível problema de rede", "jira_sev": "Grave"},
    "uptime_high":              {"sum": "Sistema - Uptime Elevado", "desc": "Robô operando por {v:.1f} horas sem interrupção*", "jira_sev": "Leve"}
}

serials = ["PE037DC0", "NHQJCAL005322003029Z00", "PE03UVN2", "FVFZTLKKL40Y"]
metrics = list(METRIC_THRESHOLDS_FAIXA.keys())

TOTAL_TICKETS = 100
HOURS = 6
MAX_TICKETS_PER_HOUR = 40

def distribuir_tickets(total, horas, max_por_hora):
    distrib = [0] * horas
    restante = total
    while restante > 0:
        for i in range(horas):
            if restante == 0:
                break
            max_possivel = min(max_por_hora - distrib[i], restante)
            if max_possivel > 0:
                a = random.randint(0, max_possivel)
                distrib[i] += a
                restante -= a
    while sum(distrib) < total:
        for i in range(horas):
            if sum(distrib) >= total:
                break
            if distrib[i] < max_por_hora:
                distrib[i] += 1
    return distrib

def criar_tickets_por_hora(hora_offset, quantidade):
    now = datetime.now(timezone.utc)
    hora_base = (now - timedelta(hours=hora_offset)).replace(minute=0, second=0, microsecond=0)
    contar = 0
    for _ in range(quantidade):
        metric = random.choice(metrics)
        serial = random.choice(serials)
        thresholds = METRIC_THRESHOLDS_FAIXA.get(metric, {})
        recurso = JIRA_RECURSO_MAP.get(metric, "Outro")

        nivel = random.choice(list(thresholds.keys()))
        v = min(100.0, random.uniform(thresholds[nivel]["val"], thresholds[nivel]["val"] + 10))
        urgencia = JIRA_SEVERITY_MAP[nivel]
        desc = thresholds[nivel]["desc"].format(v=v)

        data_alerta = hora_base + timedelta(minutes=random.randint(0, 59))
        data_formatada = data_alerta.isoformat()

        contar += 1
        print(f"{contar} - [{data_alerta}] Criando alerta: {serial}, {metric}, {urgencia}")

        jira.create_issue(fields={
            'project': {'key': 'SUPSEN'},
            'summary': f'Máquina {serial}',
            'description': desc,
            'issuetype': {'name': 'Alertas'},
            'customfield_10058': {'value': recurso},
            'customfield_10059': {'value': urgencia},
            'customfield_10010': "5",
            'customfield_10124': data_formatada,
            'assignee': None
        })

# Distribui 100 tickets entre as últimas 6 horas
tickets_por_hora = distribuir_tickets(TOTAL_TICKETS, HOURS, MAX_TICKETS_PER_HOUR)

for i, qtd in enumerate(tickets_por_hora, 1):
    criar_tickets_por_hora(i, qtd)