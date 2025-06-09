import mysql.connector
import psutil
import platform
import time
import subprocess
import cpuinfo
import os
import re 
from datetime import timezone, datetime
from datetime import timedelta
from dotenv import load_dotenv
import requests
from jira import JIRA
import random

# Carrega variáveis do arquivo .env
load_dotenv()

# --- Constantes Globais ---
AMBIENTE = os.getenv("AMBIENTE", "local")
JIRA_URL = os.getenv('JIRA_URL')
JIRA_USERNAME = os.getenv('JIRA_USERNAME')
JIRA_API_TOKEN = os.getenv('JIRA_API_TOKEN')
JIRA_PROJECT_KEY = 'SUPSEN'
JIRA_ISSUE_TYPE_ALERT = 'Alertas'
JIRA_CUSTOM_FIELD_COMPONENT_TYPE = 'customfield_10058'
JIRA_CUSTOM_FIELD_HORA_ABERTURA= 'customfield_10124'
JIRA_CUSTOM_FIELD_SEVERITY = 'customfield_10059'    
JIRA_CUSTOM_FIELD_STORY_POINTS = 'customfield_10010' 

# Limiares principais (usados como PADRÕES ou para alertas específicos)
CPU_CRITICAL_THRESHOLD = 80.0       
RAM_CRITICAL_THRESHOLD = 90.0      
DISK_HIGH_THRESHOLD = 80.0       
NET_UPLOAD_NO_CONNECTION_THRESHOLD = 0.01 
BATTERY_CRITICAL_THRESHOLD = 0.0   
BATTERY_LOW_THRESHOLD = 10.0      
UPTIME_HIGH_THRESHOLD_HOURS = 350.0
NETWORK_USAGE_HIGH_THRESHOLD = 85.0

ALERT_COOLDOWN_MINUTES = 5

API_PROCESS_ENDPOINT = "/processos/{id_maquina}"
API_METRIC_ENDPOINT = "/medidas/{id_maquina}"

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
    "net_usage": "Rede",
    "battery_percent": "Bateria",   
    "cpu_freq_ghz": "CPU",     
    "uptime_hours": "Tempo de Uso"   
}

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
        "leve":    {"val": 70.0,                     "sum": "Disco - Nível Leve",    "desc": "Uso de Disco ('/') em {v:.1f}"}
    },
    "net_usage": {
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

# --- Configuração do Jira ---
jira_client = None
if not all([JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN]):
    print("AVISO: Credenciais do Jira não configuradas. Integração desabilitada.")
else:
    try:
        print(f"INFO: Tentando conectar ao Jira em {JIRA_URL}...")
        jira_client = JIRA(server=JIRA_URL, basic_auth=(JIRA_USERNAME, JIRA_API_TOKEN))
        print(f"✅ Conexão com o Jira ({JIRA_URL}) realizada com sucesso.")
    except Exception as e:
        print(f"❌ Erro ao conectar ao Jira: {e}. Integração desabilitada.")
        jira_client = None

# --- Configurações de Ambiente ---
CONFIG = {
    "local": {
        "host": os.getenv("LOCAL_DB_HOST", "127.0.0.1"), "port": int(os.getenv("LOCAL_DB_PORT", 3306)),
        "user": os.getenv("LOCAL_DB_USER", "root"), "password": os.getenv("LOCAL_DB_PASSWORD"),
        "database": os.getenv("LOCAL_DB_NAME", "sentinela"),
        "local_web_app_host": os.getenv("LOCAL_WEB_APP_HOST", "127.0.0.1"),
        "local_web_app_port": os.getenv("LOCAL_WEB_APP_PORT", "3333")
    },
    "producao": {
        "host": os.getenv("PROD_DB_HOST"), "port": int(os.getenv("PROD_DB_PORT", 3306)),
        "user": os.getenv("PROD_DB_USER"), "password": os.getenv("PROD_DB_PASSWORD"),
        "database": os.getenv("PROD_DB_NAME", "Sentinela"),
        "local_web_app_host": os.getenv("PROD_WEB_APP_HOST"),
        "local_web_app_port": os.getenv("PROD_WEB_APP_PORT", "3333")
    }
}
if not CONFIG[AMBIENTE].get("password") or not CONFIG[AMBIENTE].get("host") or not CONFIG[AMBIENTE].get("local_web_app_host"):
    print(f"ERRO: Configurações essenciais de DB ou WebApp para o ambiente '{AMBIENTE}' não encontradas. Verifique .env.")
    exit()

# --- Conexão com o Banco de Dados ---
cnx = None
mycursor = None
try:
    db_config_env = CONFIG[AMBIENTE]
    cnx = mysql.connector.connect(
        host=db_config_env["host"], user=db_config_env["user"], password=db_config_env["password"],
        database=db_config_env["database"], port=db_config_env["port"]
    )
    mycursor = cnx.cursor(dictionary=True)
    print(f"Conexão com o banco de dados ({AMBIENTE}) realizada com sucesso.")
except mysql.connector.Error as err:
    print(f"Erro fatal na conexão com o banco de dados: {err}")
    exit()

# --- Coleta de Informações Estáticas do Sistema ---
sistema_operacional = platform.system()
processador_modelo = ""
try:
    processador_modelo = cpuinfo.get_cpu_info()['brand_raw']
except Exception:
    processador_modelo = platform.processor()
nucleos_logicos = psutil.cpu_count(logical=True)
nucleos_fisicos = psutil.cpu_count(logical=False)
cpu_frequencia_max_ghz = (psutil.cpu_freq().max / 1000) if psutil.cpu_freq() else 0
memoria_total_gb = psutil.virtual_memory().total / (1024 ** 3)
disco_total_gb = psutil.disk_usage('/').total / (1024 ** 3)
arquitetura = platform.machine()
versao_sistema = platform.version()
sistema_detalhado = platform.platform()
serial_number = "Desconhecido"

if sistema_operacional == "Windows":
    serial_sources = [
        "wmic bios get serialnumber", "wmic csproduct get identifyingnumber",
        "powershell -Command \"Get-WmiObject Win32_BIOS | Select-Object -ExpandProperty SerialNumber\"",
        "powershell -Command \"Get-CimInstance Win32_ComputerSystemProduct | Select-Object -ExpandProperty UUID\""
    ]
    for cmd_sn in serial_sources:
        try:
            output_sn = subprocess.check_output(cmd_sn, shell=True, stderr=subprocess.DEVNULL).decode().strip()
            lines_sn = [line.strip() for line in output_sn.split('\n') if line.strip()]
            value_sn = lines_sn[1] if len(lines_sn) > 1 else (lines_sn[0] if lines_sn else "")
            if value_sn and value_sn != "To Be Filled By O.E.M." and "Default string" not in value_sn:
                serial_number = value_sn; break
        except: continue
elif sistema_operacional == "Linux":
    try:
        serial_number = subprocess.check_output("sudo dmidecode -s system-serial-number", shell=True, stderr=subprocess.DEVNULL).decode().strip()
    except:
        try:
            with open("/sys/class/dmi/id/product_uuid", "r") as f: serial_number = f.read().strip()
        except: serial_number = "Desconhecido (Linux)"
elif sistema_operacional == "Darwin":
    try:
        output_sn = subprocess.check_output("system_profiler SPHardwareDataType | grep 'Serial Number'", shell=True, stderr=subprocess.DEVNULL).decode().split(":")
        if len(output_sn) > 1: serial_number = output_sn[1].strip()
    except: serial_number = "Desconhecido (Darwin)"

# --- Variáveis Globais de Estado ---
id_empresa_global = None
alert_cooldown_tracker = {}

# --- Funções Utilitárias ---
def print_linha(char="=", length=73): print(f"\n{char * length}")
def encerrar_servico():
    print_linha(); print("\nServiço encerrado.");
    if cnx and cnx.is_connected(): cnx.close()
    exit()
def voltar_ao_menu_ou_encerrar():
    print_linha(); escolha = input("Voltar ao menu principal? (S para Sim, outra tecla para encerrar): ").strip().lower()
    return escolha == 's'

# --- Funções de Menu ---
def menu_informacoes_maquina():
    print_linha()
    print("        INFORMAÇÕES TÉCNICAS DA MÁQUINA        ")
    print_linha("-", 50)
    print(f"Modelo do processador: {processador_modelo if processador_modelo else 'N/A'}")
    print(f"Arquitetura do sistema: {arquitetura if arquitetura else 'N/A'}")
    print(f"Sistema operacional: {sistema_operacional if sistema_operacional else 'N/A'}")
    print(f"Versão do sistema: {versao_sistema if versao_sistema else 'N/A'}")
    print(f"Detalhes da plataforma: {sistema_detalhado if sistema_detalhado else 'N/A'}")
    print(f"Número de série da máquina: {serial_number if serial_number else 'N/A'}")
    print(f"Quantidade de núcleos físicos: {nucleos_fisicos if nucleos_fisicos is not None else 'N/A'}")
    print(f"Quantidade de núcleos lógicos: {nucleos_logicos if nucleos_logicos is not None else 'N/A'}")
    if cpu_frequencia_max_ghz is not None and cpu_frequencia_max_ghz > 0:
        print(f"Frequência máxima da CPU: {cpu_frequencia_max_ghz:.2f} GHz")
    else:
        print(f"Frequência máxima da CPU: N/A")
    if memoria_total_gb is not None:
        print(f"Memória RAM total: {memoria_total_gb:.2f} GB")
    else:
        print(f"Memória RAM total: N/A")
    if disco_total_gb is not None:
        print(f"Armazenamento total da partição raiz ('/'): {disco_total_gb:.2f} GB")
    else:
        print(f"Armazenamento total da partição raiz ('/'): N/A")
    print_linha("-", 50)
    print("Informações da Conexão de Rede Ativa:")
    try:
        network_info = get_active_network_link_info(verbose=False) 
        print(f"  Tipo de Conexão: {network_info.get('type', 'N/A')}")
        print(f"  Interface Ativa: {network_info.get('interface', 'N/A')}")
        link_speed = network_info.get('speed_mbps')
        if link_speed is not None:
            print(f"  Velocidade do Link: {link_speed:.2f} Mbps")
        else:
            print(f"  Velocidade do Link: N/A")
    except Exception as e_netinfo:
        print(f"  Não foi possível obter informações da rede ativa no momento: {e_netinfo}")
    if voltar_ao_menu_ou_encerrar(): return
    else: encerrar_servico()

# --- Funções de Autenticação e Registro ---
def verificar_maquina_registrada():
    global id_empresa_global
    print_linha()
    print("🔍 Buscando máquina...")
    
    sql = "SELECT id_maquina, fk_maquina_empresa, fk_modelo FROM maquina WHERE serial_number = %s"
    mycursor.execute(sql, (serial_number,))
    resultado = mycursor.fetchone()
    if resultado:
        id_maquina_atual = resultado['id_maquina']
        id_empresa_global = resultado['fk_maquina_empresa']
        fk_maquina_modelo = resultado['fk_modelo']
        print(f"✅ Máquina '{serial_number}' (ID:{id_maquina_atual}) encontrada, empresa ID:{id_empresa_global}.")
        return True, id_maquina_atual, id_empresa_global, fk_maquina_modelo
    print(f"❌ Máquina '{serial_number}' não encontrada.")
    return False, None, None, None

def fazer_login_e_registrar_maquina():
    global id_empresa_global
    print_linha()
    print("🔐 Login para associar máquina.")
    while True:
        email = input("E-mail: ").strip()
        senha = input("Senha: ").strip()
        sql_user = "SELECT id_usuario, fk_colaborador_empresa FROM colaborador WHERE email = %s AND senha = SHA2(%s, 256)"
        mycursor.execute(sql_user, (email, senha))
        usuario = mycursor.fetchone()
        if usuario:
            print("🔓 Login sucesso.")
            id_empresa_global = usuario['fk_colaborador_empresa']
            id_maquina_cadastrada = cadastrar_maquina_atual(id_empresa_global)
            if id_maquina_cadastrada:
                return True, id_maquina_cadastrada, id_empresa_global
            print("❌ Falha ao cadastrar máquina pós-login.")
            return False, None, id_empresa_global
        print("❌ Credenciais inválidas.")
        retry = input("Tentar (S/N)? ").strip().lower()
        if retry != 's':
            return False, None, None

def cadastrar_maquina_atual(id_empresa_param):
    print_linha()
    setor = input(f"Setor da máquina '{serial_number}': ").strip()
    print_linha()
    print(f"SO: {sistema_detalhado}\nSerial: {serial_number}\nINICIANDO CADASTRO...")
    try:
        sql_insert = "INSERT INTO maquina (so, serial_number, setor, fk_maquina_empresa, fk_modelo) VALUES (%s, %s, %s, %s, NULL)"
        mycursor.execute(sql_insert, (sistema_detalhado, serial_number, setor, id_empresa_param))
        cnx.commit()
        id_maquina_nova = mycursor.lastrowid
        print(f"✅ MÁQUINA REGISTRADA! ID: {id_maquina_nova}")
        cadastrar_metricas_padrao(id_maquina_nova)
        return id_maquina_nova
    except mysql.connector.Error as err:
        print(f"❌ Erro ao cadastrar máquina: {err}")
        return None

def cadastrar_metricas_padrao(id_maquina_param):
    network_info_initial = get_active_network_link_info(verbose=False)
    modelo_rede_principal = network_info_initial.get('modelo_detalhado', 'Rede (Padrão)')

    metricas_definidas = [
        {"tipo": "cpu_percent", "descricao": "Percentual de CPU", "modelo": processador_modelo, "unidade": "%"},
        {"tipo": "disk_percent", "descricao": "Percentual de uso de disco", "modelo": "Disco Principal", "unidade": "%"},
        {"tipo": "ram_percent", "descricao": "Percentual de uso de RAM", "modelo": "Memória RAM", "unidade": "%"},
        {"tipo": "disk_usage_gb", "descricao": "Uso de Disco em GB", "modelo": "Disco Principal", "unidade": "GB"},
        {"tipo": "ram_usage_gb", "descricao": "Uso de RAM em GB", "modelo": "Memória RAM", "unidade": "GB"},
        {"tipo": "net_upload", "descricao": "Velocidade de Upload Atual", "modelo": modelo_rede_principal, "unidade": "Mbps"},
        {"tipo": "net_download", "descricao": "Velocidade de Download Atual", "modelo": modelo_rede_principal, "unidade": "Mbps"},
        {"tipo": "link_speed_mbps", "descricao": "Velocidade do Link de Rede", "modelo": modelo_rede_principal, "unidade": "Mbps"},
        {"tipo": "net_usage", "descricao": "Percentual de Uso do Link de Rede", "modelo": modelo_rede_principal, "unidade": "%"},
        {"tipo": "battery_percent", "descricao": "Bateria em uso", "modelo": "Bateria", "unidade": "%"},
        {"tipo": "cpu_freq_ghz", "descricao": "Frequência da CPU", "modelo": processador_modelo, "unidade": "GHz"},
        {"tipo": "uptime_hours", "descricao": "Tempo de atividade", "modelo": "Sistema", "unidade": "horas"}
    ]
    print_linha(); print("CADASTRANDO MÉTRICAS PADRÃO E VALORES DE LIMIAR DE ALERTA...")

    for metrica_info in metricas_definidas:
        try:
            config_alerta_faixa = METRIC_THRESHOLDS_FAIXA.get(metrica_info['tipo'], {})

            threshold_leve_val = config_alerta_faixa.get("leve", {}).get("val")
            threshold_grave_val = config_alerta_faixa.get("grave", {}).get("val")
            threshold_critico_val = config_alerta_faixa.get("critico", {}).get("val")

            if metrica_info['tipo'] == 'battery_percent':
                if threshold_leve_val is None: 
                    threshold_leve_val = BATTERY_LOW_THRESHOLD
                if threshold_grave_val is None: 
                    threshold_grave_val = BATTERY_CRITICAL_THRESHOLD

            elif metrica_info['tipo'] == 'uptime_hours':
                if threshold_leve_val is None:
                    threshold_leve_val = UPTIME_HIGH_THRESHOLD_HOURS

            elif metrica_info['tipo'] == 'net_upload':
                if threshold_grave_val is None: 
                    threshold_grave_val = NET_UPLOAD_NO_CONNECTION_THRESHOLD

            sql_componente = """
                INSERT INTO componente (
                    tipo, modelo, valor,
                    fk_componente_maquina, unidade_medida,
                    threshold_leve, threshold_grave, threshold_critico
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    modelo=VALUES(modelo),
                    unidade_medida=VALUES(unidade_medida),
                    threshold_leve=VALUES(threshold_leve),
                    threshold_grave=VALUES(threshold_grave),
                    threshold_critico=VALUES(threshold_critico);
            """
            val_componente = (
                metrica_info['tipo'], metrica_info['modelo'], 0, 
                id_maquina_param, metrica_info['unidade'],
                threshold_leve_val, threshold_grave_val, threshold_critico_val
            )
            mycursor.execute(sql_componente, val_componente)
            print(f"✅ Componente '{metrica_info['descricao']}' ({metrica_info['tipo']}) e seus limiares foram configurados/atualizados.")
        except mysql.connector.Error as err:
            print(f"❌ Erro ao processar componente '{metrica_info['descricao']}': {err}")
    cnx.commit()
    print_linha(); print("TODOS OS COMPONENTES E LIMIARES PADRÃO (INCLUINDO OS DE ALERTA ESPECÍFICO) FORAM CONFIGURADOS/ATUALIZADOS!")

# --- Funções de Gerenciamento de Modelos ---
def listar_modelos_existentes():
    """Lista todos os modelos de máquina existentes no banco de dados."""
    print_linha("-", 50)
    print("Modelos de Máquina Existentes:")
    sql = "SELECT id_modelo, nome FROM modelo ORDER BY nome"
    mycursor.execute(sql)
    modelos = mycursor.fetchall()
    if not modelos:
        print("Nenhum modelo cadastrado.")
        return []
    for i, modelo in enumerate(modelos):
        print(f"  {i+1}. ID: {modelo['id_modelo']} - Nome: {modelo['nome']}")
    print_linha("-", 50)
    return modelos

def cadastrar_novo_modelo():
    """Permite ao usuário cadastrar um novo modelo de máquina."""
    print_linha()
    while True:
        nome_novo_modelo = input("Digite o nome do novo modelo: ").strip()
        if not nome_novo_modelo:
            print("O nome do modelo não pode ser vazio.")
            continue
        
        # Verifica se o modelo já existe
        sql_check = "SELECT id_modelo FROM modelo WHERE nome = %s"
        mycursor.execute(sql_check, (nome_novo_modelo,))
        if mycursor.fetchone():
            print(f"❌ Modelo '{nome_novo_modelo}' já existe. Tente outro nome ou selecione-o.")
            return None 
        
        try:
            sql_insert = "INSERT INTO modelo (nome) VALUES (%s)"
            mycursor.execute(sql_insert, (nome_novo_modelo,))
            cnx.commit()
            novo_id_modelo = mycursor.lastrowid
            print(f"✅ Modelo '{nome_novo_modelo}' cadastrado com sucesso! ID: {novo_id_modelo}")
            return novo_id_modelo
        except mysql.connector.Error as err:
            print(f"❌ Erro ao cadastrar novo modelo: {err}")
            return None

def obter_ou_atribuir_modelo_maquina(id_maquina_param, modelo_atual_id):
    """
    Permite ao usuário selecionar um modelo existente ou cadastrar um novo
    e atribui à máquina especificada.
    """
    print_linha()
    if modelo_atual_id:
        sql_get_model_name = "SELECT nome FROM modelo WHERE id_modelo = %s"
        mycursor.execute(sql_get_model_name, (modelo_atual_id,))
        modelo_nome = mycursor.fetchone()
        if modelo_nome:
            print(f"Máquina ID {id_maquina_param} já possui o modelo: {modelo_nome['nome']}")
            return True 
        else:
            print(f"Máquina ID {id_maquina_param} possui um ID de modelo ({modelo_atual_id}) que não existe. Atribuindo um novo.")
            # Se o ID do modelo não existe, tratamos como se não tivesse modelo
            modelo_atual_id = None 

    id_modelo_selecionado = None
    while id_modelo_selecionado is None:
        print("\nOpções de Modelo:")
        print("1. Selecionar modelo existente")
        print("2. Cadastrar novo modelo")
        print("0. Pular (manter sem modelo - NÃO RECOMENDADO)")
        escolha = input("Escolha uma opção: ").strip()

        if escolha == '1':
            modelos_existentes = listar_modelos_existentes()
            if not modelos_existentes:
                print("Nenhum modelo existente para selecionar. Por favor, cadastre um novo.")
                continue
            try:
                idx_selecionado = int(input("Digite o NÚMERO do modelo desejado: ").strip())
                if 1 <= idx_selecionado <= len(modelos_existentes):
                    id_modelo_selecionado = modelos_existentes[idx_selecionado - 1]['id_modelo']
                else:
                    print("Escolha inválida.")
            except ValueError:
                print("Entrada inválida. Digite um número.")
        elif escolha == '2':
            id_modelo_selecionado = cadastrar_novo_modelo()
        elif escolha == '0':
            print("Atribuição de modelo pulada.")
            return True # Retorna True para indicar que o processo foi concluído, mesmo que pulado
        else:
            print("Opção inválida.")
    
    if id_modelo_selecionado:
        try:
            sql_update = "UPDATE maquina SET fk_modelo = %s WHERE id_maquina = %s"
            mycursor.execute(sql_update, (id_modelo_selecionado, id_maquina_param))
            cnx.commit()
            print(f"✅ Modelo atribuído à máquina ID {id_maquina_param} com sucesso!")
            return True
        except mysql.connector.Error as err:
            print(f"❌ Erro ao atribuir modelo à máquina: {err}")
            return False
    return False # Se chegou aqui, algo deu errado e nenhum modelo foi atribuído

# --- Funções de Captura de Velocidade de Link ---
def get_wifi_link_speed_linux(interface='wlan0'):
    try:
        cmd = f"iw dev {interface} link"; result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=False)
        if result.returncode != 0: return None
        output = result.stdout; tx_rate, rx_rate = None, None
        for line in output.splitlines():
            line = line.strip()
            if 'tx bitrate' in line: parts = line.split(':'); tx_rate = float(parts[1].strip().split()[0]) if len(parts) > 1 else None; break
            elif 'rx bitrate' in line: parts = line.split(':'); rx_rate = float(parts[1].strip().split()[0]) if len(parts) > 1 else None
        return tx_rate if tx_rate is not None else rx_rate
    except: return None

def get_wifi_link_speed_windows():
    try:
        cmd = "netsh wlan show interfaces"; 
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=False, encoding='cp850', errors='ignore')
        if result.returncode != 0: 
            print(f"DEBUG: netsh wlan show interfaces retornou código {result.returncode}. Erro: {result.stderr.strip()}")
            return None
        output = result.stdout
        print(f"DEBUG: Saída de netsh wlan show interfaces:\n{output}")
        for pattern_key in [r'Transmit rate \(Mbps\)\s*:\s*([\d.]+)', r'Receive rate \(Mbps\)\s*:\s*([\d.]+)', r'Taxa de transmissão \(Mbps\)\s*:\s*([\d.]+)', r'Taxa de recepção \(Mbps\)\s*:\s*([\d.]+)']:
            match = re.search(pattern_key, output)
            if match: 
                print(f"DEBUG: Velocidade Wi-Fi (Windows) encontrada: {match.group(1)} Mbps")
                return float(match.group(1))
    except Exception as e: 
        print(f"ERRO: Falha ao obter velocidade Wi-Fi (Windows): {e}")
    return None

def get_wifi_link_speed_macos():
    try:
        cmd = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport -I"; result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=False)
        if result.returncode != 0: return None
        output = result.stdout
        for line in output.splitlines():
            if "lastTxRate" in line: parts = line.split(':'); return int(parts[1].strip()) if len(parts) > 1 else None
    except: return None
    return None

def get_ethernet_link_speed_linux(interface='eth0'):
    try:
        cmd = f"ethtool {interface}"; result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=False)
        if result.returncode != 0: return None
        output = result.stdout; match = re.search(r'Speed:\s*(\d+)\s*Mb/s', output)
        if match: return int(match.group(1))
    except FileNotFoundError: print(f"AVISO: 'ethtool' não encontrado para Ethernet em Linux."); return None
    except: return None
    return None

def get_ethernet_link_speed_windows(adapter_name_hint="Ethernet"):
    try:
        cmd = 'wmic nic where "NetConnectionStatus=2" get Name, Speed /format:list'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=False, encoding='cp850', errors='ignore')
        
        if result.returncode != 0:
            print(f"DEBUG: wmic nic retornou código {result.returncode}. Erro: {result.stderr.strip()}")
            return None
        
        output = result.stdout.strip()
        print(f"DEBUG: Saída de wmic nic para Ethernet:\n{output}")
        
        matches = re.findall(r'Name=(.*?)\s*\nSpeed=(\d+)', output, re.IGNORECASE)
        
        for name, speed_str in matches:
            if adapter_name_hint.lower() in name.lower() or "ethernet" in name.lower() or "conexão local" in name.lower():
                try:
                    speed_bps = int(speed_str)
                    speed_mbps = speed_bps / 1000000 
                    print(f"DEBUG: Velocidade Ethernet (Windows) encontrada para '{name}': {speed_mbps:.2f} Mbps")
                    return speed_mbps
                except ValueError:
                    print(f"AVISO: Não foi possível converter velocidade '{speed_str}' para número para '{name}'.")
                    continue
        
    except FileNotFoundError: 
        print(f"AVISO: 'wmic' não encontrado para Ethernet em Windows.")
    except Exception as e: 
        print(f"ERRO: Falha ao obter velocidade Ethernet (Windows): {e}")
    return None

def get_ethernet_link_speed_macos(interface_port='en0'):
    try:
        cmd = f"networksetup -getcurrentclockrate \"{interface_port}\""
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            service_name_cmd = f"networksetup -listnetworkserviceorder | grep -B 1 '{interface_port}' | head -n 1 | sed 's/.*Hardware Port: //;s/,.*//'"
            service_name_result = subprocess.run(service_name_cmd, shell=True, capture_output=True, text=True, check=False)
            if service_name_result.returncode == 0 and service_name_result.stdout.strip():
                service_name = service_name_result.stdout.strip()
                cmd = f"networksetup -getcurrentclockrate \"{service_name}\""
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=False)
                if result.returncode != 0: return None
            else: return None
        output = result.stdout
        match = re.search(r'Current Speed:\s*(\d+)\s*Mbit/s', output)
        if match: return int(match.group(1))
        match_autoselect = re.search(r'Autoselect\s*\((\d+)\s*Mbit/s\)', output)
        if match_autoselect: return int(match_autoselect.group(1))
    except FileNotFoundError: print(f"AVISO: 'networksetup' não encontrado para Ethernet em macOS."); return None
    except: return None
    return None

def get_active_network_link_info(verbose=True):
    link_speed, connection_type, active_interface = None, "Desconhecido", "N/A"
    if verbose: print("Procurando link Wi-Fi ativo...")
    if sistema_operacional == "Linux":
        for iface in ['wlan0', 'wlp2s0', 'wlp3s0', 'wlp1s0', 'wlp0s20f3']:
            speed = get_wifi_link_speed_linux(interface=iface)
            if speed is not None: active_interface,connection_type,link_speed = iface,"Wi-Fi",speed; break
    elif sistema_operacional == "Windows":
        speed = get_wifi_link_speed_windows()
        if speed is not None: active_interface,connection_type,link_speed = "Wi-Fi Padrão","Wi-Fi",speed
    elif sistema_operacional == "Darwin":
        speed = get_wifi_link_speed_macos()
        if speed is not None: active_interface,connection_type,link_speed = "Airport","Wi-Fi",speed
    if link_speed is not None and verbose: print(f"Conexão {connection_type} ({active_interface}) encontrada: {link_speed} Mbps")
    elif verbose: print("Nenhum link Wi-Fi. Procurando Ethernet...")
    if link_speed is None:
        if sistema_operacional == "Linux":
            for iface in ['eth0', 'enp2s0', 'enp3s0', 'enp1s0', 'eno1']:
                speed = get_ethernet_link_speed_linux(interface=iface)
                if speed is not None: active_interface,connection_type,link_speed = iface,"Ethernet",speed; break
        elif sistema_operacional == "Windows":
            speed = get_ethernet_link_speed_windows(adapter_name_hint="Ethernet")
            if speed is None:
                speed = get_ethernet_link_speed_windows(adapter_name_hint="Conexão Local")
            if speed is not None: active_interface,connection_type,link_speed = "Ethernet Padrão","Ethernet",speed
        elif sistema_operacional == "Darwin":
            for port in ['en0', 'en1', 'en2']:
                speed = get_ethernet_link_speed_macos(interface_port=port)
                if speed is not None: active_interface,connection_type,link_speed = port,"Ethernet",speed; break
        if link_speed is not None and verbose: print(f"Conexão {connection_type} ({active_interface}) encontrada: {link_speed} Mbps")
        elif verbose: print("Nenhum link Ethernet.")
    if link_speed is None and sistema_operacional == "Linux" and verbose:
        custom_interface = input("Interface Wi-Fi custom (ou Enter): ").strip()
        if custom_interface:
            speed = get_wifi_link_speed_linux(interface=custom_interface)
            if speed is not None: active_interface,connection_type,link_speed = custom_interface,"Wi-Fi Custom",speed
    if link_speed is None and verbose: print("Não foi possível determinar velocidade do link.")
    return {'speed_mbps':link_speed,'type':connection_type,'interface':active_interface,'modelo_detalhado':f"{connection_type} ({active_interface})"}


def encerrar_processo_por_pid(pid):
    try:
        p = psutil.Process(pid)
        p.terminate() 
        return True, "Processo encerrado com sucesso."
    except psutil.NoSuchProcess:
        return False, "Processo não encontrado (já encerrado ou PID inválido)."
    except psutil.AccessDenied:
        return False, "Acesso negado para encerrar o processo."
    except Exception as e:
        return False, f"Erro inesperado ao encerrar: {e}"

# --- Funções de Monitoramento (Core) ---
def capturar_processos_sistema():
    processos_lista = []
    current_pid = os.getpid()

    system_essentials_windows = [
        "System Idle Process", "System", "smss.exe", "csrss.exe", "wininit.exe",
        "services.exe", "lsass.exe", "winlogon.exe", "dwm.exe", "spoolsv.exe",
        "explorer.exe", 
        "nvcontainer.exe", "nvdisplay.exe", 
        "audiodg.exe", 
        "fontdrvhost.exe", 
        "dllhost.exe", 
        "conhost.exe", 
        "ctfmon.exe" 
    ]
    system_essentials_linux = [
        "init", "systemd", "kthreadd", "ksoftirqd", "rcu_sched", "migration/0",
        "cpuhp/0", "kdevtmpfs", "inet_frags", "kauditd", "jbd2/", "ext4/",
        "Xorg", 
        "gnome-shell", "kdeinit5", 
        "dbus-daemon", "pulseaudio", "pipewire" 
    ]

    if os.name == 'nt': 
        system_essentials_to_exclude = system_essentials_windows
    else: 
        system_essentials_to_exclude = system_essentials_linux

    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'username']):
        try:
            info = proc.info
            process_name_lower = info['name'].lower() if info['name'] else ''

            if (info['pid'] == current_pid or
                process_name_lower in [name.lower() for name in system_essentials_to_exclude] or
                not info['name'] or info['pid'] == 0):
                continue 

            processos_lista.append({
                'timestamp': datetime.now().isoformat(),
                'pid': info['pid'],
                'nome': info['name'],
                'cpu_percent': info['cpu_percent'],
                'memory_percent': info['memory_percent']
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
        except Exception as e:
            print(f"Erro ao processar processo {proc.pid}: {e}")
            pass

    return processos_lista


def loop_monitoramento_agente(id_maquina_atual):
        print(f"[{datetime.now()}] Agente: Verificando comandos e coletando dados...")

        try:
            sql_select_commands = "SELECT id_comando, pid_processo, tipo_comando FROM comandos_agente WHERE id_maquina = %s AND status = 'pendente'"
            mycursor.execute(sql_select_commands, (id_maquina_atual,))
            comandos_pendentes = mycursor.fetchall()

            if comandos_pendentes:
                print(f"[{datetime.now()}] Agente: {len(comandos_pendentes)} comando(s) pendente(s) encontrado(s).")
            else:
                print(f"[{datetime.now()}] Agente: Nenhum comando pendente.")

            for comando in comandos_pendentes:
                try:
                    id_comando = comando['id_comando']
                    pid_processo = comando['pid_processo']
                    tipo_comando = comando['tipo_comando']
                except TypeError:
                    id_comando = comando[0]
                    pid_processo = comando[1]
                    tipo_comando = comando[2]

                print(f"[{datetime.now()}] Agente: Processando comando {id_comando}: Tipo '{tipo_comando}', PID {pid_processo}")

                sql_update_executing = "UPDATE comandos_agente SET status = 'executando', data_execucao = %s WHERE id_comando = %s"
                mycursor.execute(sql_update_executing, (datetime.now(), id_comando))
                cnx.commit()

                sucesso, mensagem = False, "Tipo de comando desconhecido."
                if tipo_comando == 'encerrar_processo':
                    sucesso, mensagem = encerrar_processo_por_pid(pid_processo)

                status_final = 'sucesso' if sucesso else 'falha'
                sql_update_final = "UPDATE comandos_agente SET status = %s, mensagem_status = %s WHERE id_comando = %s"
                mycursor.execute(sql_update_final, (status_final, mensagem, id_comando))
                cnx.commit()
                print(f"[{datetime.now()}] Agente: Comando {id_comando} - Resultado: {status_final} - {mensagem}")

            processos_ativos = capturar_processos_sistema()

        except Exception as e:
            print(f"❌ Erro no loop de monitoramento: {e}")
            pass


def enviar_dados_api(endpoint_path_template, id_maquina_param, payload_data, description):
    if not CONFIG[AMBIENTE].get("local_web_app_host") or not CONFIG[AMBIENTE].get("local_web_app_port"):
        print(f"AVISO: Host/Porta WebApp não config. para {description}. Envio cancelado."); return
    base_url = f"http://{CONFIG[AMBIENTE]['local_web_app_host']}:{CONFIG[AMBIENTE]['local_web_app_port']}"
    url = base_url + endpoint_path_template.format(id_maquina=id_maquina_param)
    try:
        response = requests.post(url, json=payload_data, timeout=10)
        if response.status_code in [200, 201]: print(f"✅ Dados de {description} enviados para API.")
        else: print(f"❌ Erro API {description} ({url}): {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e: print(f"❌ Conexão API {description} ({url}): {str(e)}")
    except Exception as e: print(f"❌ Erro inesperado API {description} ({url}): {str(e)}")

def criar_alerta_jira_issue(componente_tipo, severidade, resumo_especifico, descricao_detalhada):
    if not jira_client: 
        print(f"AVISO Jira: Não configurado. Alerta para '{componente_tipo}' não enviado.")
        return False

    recurso_para_jira = JIRA_RECURSO_MAP.get(componente_tipo)

    if not recurso_para_jira:
        print(f"AVISO Jira: Mapeamento para 'Recurso' não encontrado para tipo_metrica '{componente_tipo}'. "
              f"Verifique JIRA_RECURSO_MAP. Enviando '{componente_tipo}' como fallback (pode falhar).")
        recurso_para_jira = componente_tipo

    try:
        data_hora_atual = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000+0000")
        issue_dict = {
            'project': {'key': JIRA_PROJECT_KEY},
            'summary': f"Máquina {serial_number}",
            'description': f"{descricao_detalhada}", 
            'issuetype': {'name': JIRA_ISSUE_TYPE_ALERT},
            JIRA_CUSTOM_FIELD_COMPONENT_TYPE: {'value': recurso_para_jira}, 
            JIRA_CUSTOM_FIELD_HORA_ABERTURA: data_hora_atual,
            JIRA_CUSTOM_FIELD_SEVERITY: {'value': severidade},
            'assignee': None
        }
        if JIRA_CUSTOM_FIELD_STORY_POINTS: 
            issue_dict[JIRA_CUSTOM_FIELD_STORY_POINTS] = "5"

        new_issue = jira_client.create_issue(fields=issue_dict)
        print(f"✅ Alerta Jira '{componente_tipo}' (Recurso: {recurso_para_jira}, Severidade: {severidade}): {new_issue.key}")
        return True
    except Exception as e: 
        print(f"❌ Erro criar alerta Jira '{componente_tipo}': {e}")
        if hasattr(e, 'text'):
             print(f"    Detalhes do erro Jira: {e.text}")
        return False

def verificar_e_disparar_alerta_faixa(dados_componente, valor_atual):
    global alert_cooldown_tracker
    agora = datetime.now()
    
    tipo_metrica = dados_componente['tipo']

    ultimo_alerta_timestamp = alert_cooldown_tracker.get(tipo_metrica)
    if ultimo_alerta_timestamp and agora <= ultimo_alerta_timestamp:
        return 

    th_critico = dados_componente.get('threshold_critico')
    th_grave = dados_componente.get('threshold_grave')
    th_leve = dados_componente.get('threshold_leve')

    nivel_alerta_acionado = None
    limiar_acionado_regra = None 
    if th_critico is not None and valor_atual >= th_critico:
        nivel_alerta_acionado = "critico"; limiar_acionado_regra = th_critico
    elif th_grave is not None and valor_atual >= th_grave:
        nivel_alerta_acionado = "grave"; limiar_acionado_regra = th_grave
    elif th_leve is not None and valor_atual >= th_leve:
        nivel_alerta_acionado = "leve"; limiar_acionado_regra = th_leve
    
    if nivel_alerta_acionado:
        templates_alerta = METRIC_THRESHOLDS_FAIXA.get(tipo_metrica, {}).get(nivel_alerta_acionado)
        if templates_alerta:
            resumo_jira = templates_alerta["sum"]
            descricao_jira = templates_alerta["desc"].format(v=valor_atual, limiar=limiar_acionado_regra)
            severidade_jira = JIRA_SEVERITY_MAP.get(nivel_alerta_acionado, "Leve")

            if criar_alerta_jira_issue(tipo_metrica, severidade_jira, resumo_jira, descricao_jira):
                alert_cooldown_tracker[tipo_metrica] = agora + timedelta(minutes=ALERT_COOLDOWN_MINUTES)
                print(f"ℹ️ Alerta Nível '{nivel_alerta_acionado.capitalize()}' para {tipo_metrica} (valor: {valor_atual:.2f}) ativado. Cooldown até {alert_cooldown_tracker[tipo_metrica]:%H:%M:%S}")
        else:
            print(f"AVISO: Templates de mensagem não encontrados em METRIC_THRESHOLDS_FAIXA para {tipo_metrica} nível {nivel_alerta_acionado}.")

def salvar_metrica_historico(id_componente_db, valor_capturado, timestamp_captura):
    try:
        sql = "INSERT INTO historico (data_captura, valor, fk_historico_componente) VALUES (%s, %s, %s)"
        mycursor.execute(sql, (timestamp_captura, valor_capturado, id_componente_db))
    except Exception as e: print(f"❌ Erro salvar histórico comp ID {id_componente_db}: {e}")

def monitoramento_em_tempo_real(id_maquina_param):
    global alert_cooldown_tracker; alert_cooldown_tracker = {}
    print_linha(); print(f"Iniciando monitoramento: Máquina ID: {id_maquina_param} (Serial: {serial_number})")
    network_link_info = get_active_network_link_info(verbose=True)
    current_link_speed_mbps = network_link_info.get('speed_mbps')
    current_connection_type = network_link_info.get('type', "Desconhecido")
    
    print(f"DEBUG: Velocidade do Link Detectada (Inicial): {current_link_speed_mbps}")
    
    current_active_interface = network_link_info.get('interface', "N/A")
    print(f"Monitorando link: Tipo='{current_connection_type}', Interface='{current_active_interface}', Velocidade Link='{current_link_speed_mbps if current_link_speed_mbps is not None else 'N/A'}' Mbps")
    print("Pressione Ctrl+C para parar."); print_linha()
    
    # Busca todos os dados do componente, incluindo os novos campos de threshold
    sql_metricas_cfg = ("SELECT id_componente, tipo, unidade_medida, threshold_leve, threshold_grave, threshold_critico "
                        "FROM componente WHERE fk_componente_maquina = %s")
    mycursor.execute(sql_metricas_cfg, (id_maquina_param,)); metricas_a_monitorar = mycursor.fetchall()
    
    if not metricas_a_monitorar: print("❌ Nenhuma métrica configurada."); return
    print("Métricas monitoradas (do DB):"); [print(f"- Tipo: {m['tipo']} (ID Comp: {m['id_componente']})") for m in metricas_a_monitorar]; print_linha()
    last_net_io, last_net_time = psutil.net_io_counters(), time.time()
    
    try:
        while True:
            # Rodando agente de comandos
            loop_monitoramento_agente(id_maquina_param)
            timestamp_ciclo = datetime.now(); dados_coletados_ciclo = []
            processos_atuais = capturar_processos_sistema()
            if processos_atuais:
                payload_proc = {'timestamp':timestamp_ciclo.isoformat(),'processos':processos_atuais}
                enviar_dados_api(API_PROCESS_ENDPOINT,id_maquina_param,payload_proc,"processos")
            
            current_net_io,current_net_time = psutil.net_io_counters(),time.time()
            elapsed_time_net = current_net_time - last_net_time
            net_upload_mbps, net_download_mbps = 0.0, 0.0
            if elapsed_time_net > 0:
                bytes_sent_delta = current_net_io.bytes_sent - last_net_io.bytes_sent
                bytes_recv_delta = current_net_io.bytes_recv - last_net_io.bytes_recv
                net_upload_mbps = (bytes_sent_delta*8)/(elapsed_time_net*1024*1024)
                net_download_mbps = (bytes_recv_delta*8)/(elapsed_time_net*1024*1024)
            last_net_io,last_net_time = current_net_io,current_net_time

            print(f"DEBUG: Velocidade do Link no Loop (para cálculo): {current_link_speed_mbps} Mbps") 

            for metrica_cfg_db in metricas_a_monitorar: 
                id_componente,tipo_metrica,unidade_db = metrica_cfg_db['id_componente'],metrica_cfg_db['tipo'],metrica_cfg_db['unidade_medida']
                valor_atual,unidade_envio = None,unidade_db
                
                try:
                    if tipo_metrica == 'cpu_percent': valor_atual = psutil.cpu_percent(interval=None)
                    elif tipo_metrica == 'disk_percent': valor_atual = psutil.disk_usage('/').percent
                    elif tipo_metrica == 'ram_percent': valor_atual = psutil.virtual_memory().percent
                    elif tipo_metrica == 'disk_usage_gb': valor_atual = psutil.disk_usage('/').used / (1024**3)
                    elif tipo_metrica == 'ram_usage_gb': valor_atual = psutil.virtual_memory().used / (1024**3)
                    elif tipo_metrica == 'net_upload': valor_atual,unidade_envio = net_upload_mbps,"Mbps"
                    elif tipo_metrica == 'net_download': valor_atual,unidade_envio = net_download_mbps,"Mbps"
                    elif tipo_metrica == 'link_speed_mbps': valor_atual,unidade_envio = current_link_speed_mbps,"Mbps"
                    elif tipo_metrica == 'net_usage':
                        print(f"DEBUG: current_link_speed_mbps para net_usage: {current_link_speed_mbps}")
                        if current_link_speed_mbps is not None and current_link_speed_mbps > 0:
                            trafego_total = net_upload_mbps + net_download_mbps
                            valor_atual = min(max((trafego_total/current_link_speed_mbps)*100,0.0),100.0)
                        else: 
                            fallback_link_speed_mbps = 100.0 
                            trafego_total = net_upload_mbps + net_download_mbps
                            if fallback_link_speed_mbps > 0:
                                valor_atual = min(max((trafego_total / fallback_link_speed_mbps) * 100, 0.0), 100.0)
                            else:
                                valor_atual = 0.0 
                            print(f"AVISO: Velocidade do link de rede não detectada ou é zero. Usando fallback ({fallback_link_speed_mbps} Mbps) para cálculo de net_usage. Valor: {valor_atual:.2f}%")
                        unidade_envio = "%" 
                    elif tipo_metrica == 'battery_percent': valor_atual = psutil.sensors_battery().percent if psutil.sensors_battery() else 0
                    elif tipo_metrica == 'cpu_freq_ghz': cpu_f=psutil.cpu_freq(); valor_atual=(cpu_f.current/1000) if cpu_f else 0; unidade_envio="GHz"
                    elif tipo_metrica == 'uptime_hours': valor_atual = (time.time()-psutil.boot_time())/3600
                    
                    if valor_atual is not None:
                        if tipo_metrica in METRIC_THRESHOLDS_FAIXA: 
                            verificar_e_disparar_alerta_faixa(metrica_cfg_db, valor_atual) 
                        else: 
                            if tipo_metrica == 'battery_percent':
                                agora = datetime.now()
                                ultimo_alerta_ts = alert_cooldown_tracker.get(tipo_metrica)
                                if not ultimo_alerta_ts or agora > ultimo_alerta_ts:
                                    msg_info = None
                                    if valor_atual == BATTERY_CRITICAL_THRESHOLD:
                                        msg_info = SPECIFIC_ALERT_MESSAGES.get("battery_grave_0_percent")
                                    elif valor_atual <= BATTERY_LOW_THRESHOLD and valor_atual > BATTERY_CRITICAL_THRESHOLD:
                                        msg_info = SPECIFIC_ALERT_MESSAGES.get("battery_leve_low")
                                    
                                    if msg_info:
                                        if criar_alerta_jira_issue(tipo_metrica, msg_info["jira_sev"], msg_info["sum"], msg_info["desc"].format(v=valor_atual)):
                                            alert_cooldown_tracker[tipo_metrica] = agora + timedelta(minutes=ALERT_COOLDOWN_MINUTES)
                                            print(f"ℹ️ Alerta Bateria Nível '{msg_info['jira_sev']}' para {tipo_metrica} ({valor_atual:.0f}) ativado. Cooldown.")

                            elif tipo_metrica == 'net_upload':
                                agora = datetime.now()
                                ultimo_alerta_ts = alert_cooldown_tracker.get(tipo_metrica)
                                if not ultimo_alerta_ts or agora > ultimo_alerta_ts:
                                    if current_link_speed_mbps is not None and valor_atual < NET_UPLOAD_NO_CONNECTION_THRESHOLD:
                                        msg_info = SPECIFIC_ALERT_MESSAGES.get("net_upload_no_connection")
                                        if msg_info and criar_alerta_jira_issue(tipo_metrica, msg_info["jira_sev"], msg_info["sum"], msg_info["desc"].format(v=valor_atual)):
                                            alert_cooldown_tracker[tipo_metrica] = agora + timedelta(minutes=ALERT_COOLDOWN_MINUTES)
                                            print(f"ℹ️ Alerta Upload Zero para {tipo_metrica} ({valor_atual:.2f}) ativado. Cooldown.")
                            
                            elif tipo_metrica == 'uptime_hours':
                                agora = datetime.now()
                                ultimo_alerta_ts = alert_cooldown_tracker.get(tipo_metrica)
                                if not ultimo_alerta_ts or agora > ultimo_alerta_ts:
                                    if valor_atual >= UPTIME_HIGH_THRESHOLD_HOURS:
                                        msg_info = SPECIFIC_ALERT_MESSAGES.get("uptime_high")
                                        if msg_info and criar_alerta_jira_issue(tipo_metrica, msg_info["jira_sev"], msg_info["sum"], msg_info["desc"].format(v=valor_atual)):
                                            alert_cooldown_tracker[tipo_metrica] = agora + timedelta(minutes=ALERT_COOLDOWN_MINUTES)
                                            print(f"ℹ️ Alerta Uptime Elevado para {tipo_metrica} ({valor_atual:.1f}) ativado. Cooldown.")
                        
                        dados_coletados_ciclo.append({'tipo':tipo_metrica,'valor':valor_atual,'unidade':unidade_envio})
                        salvar_metrica_historico(id_componente,valor_atual,timestamp_ciclo)
                        payload_api = {"timestamp":timestamp_ciclo.isoformat(),"tipo":tipo_metrica,
                                       "valor":round(valor_atual,4) if isinstance(valor_atual,float) else valor_atual,
                                       "unidade":unidade_envio,"serial_number":serial_number}
                        enviar_dados_api(API_METRIC_ENDPOINT,id_maquina_param,payload_api,f"métrica {tipo_metrica}")
                except Exception as e: print(f"❌ Erro coletar/proc métrica {tipo_metrica}: {e}")
            cnx.commit()
            print_linha("-",30); print(f"{timestamp_ciclo:%Y-%m-%d %H:%M:%S} - Status:")
            for dado in dados_coletados_ciclo: print(f"  {dado['tipo']}: {dado['valor']:.2f} {dado['unidade']}")
            tempo_proc_ciclo = time.time()-current_net_time; sleep_t = max(0,5-tempo_proc_ciclo); time.sleep(sleep_t)
    except KeyboardInterrupt: print("\nMonitoramento interrompido.");
    finally:
        if cnx and cnx.is_connected(): cnx.commit()
        if voltar_ao_menu_ou_encerrar(): return
        else: encerrar_servico()

# --- Função Gerenciar Métricas ---
def gerenciar_metricas_maquina(id_maquina_param):
    print_linha(); print("Gerenciamento de Limiares de Alerta dos Componentes"); print_linha("=",73)
    sql_comp = ("SELECT id_componente, tipo, modelo, unidade_medida, threshold_leve, threshold_grave, threshold_critico "
                "FROM componente WHERE fk_componente_maquina = %s ORDER BY tipo")
    mycursor.execute(sql_comp, (id_maquina_param,)); componentes = mycursor.fetchall()
    if not componentes: print("❌ Nenhuma métrica (componente) cadastrada.");
    else:
        print("Componentes e Limiares de Alerta Atuais:")
        for i, comp in enumerate(componentes):
            print(f"  {i+1}. Tipo: {comp['tipo']} (ID: {comp['id_componente']})")
            if comp['tipo'] in METRIC_THRESHOLDS_FAIXA: 
                 print(f"     Leve   : {comp.get('threshold_leve', 'N/A')}")
                 print(f"     Grave  : {comp.get('threshold_grave', 'N/A')}")
                 print(f"     Crítico: {comp.get('threshold_critico', 'N/A')}")
            else: print("     (Alerta específico, não editável por esta interface de faixas)")
        print_linha("-",30)
        try:
            escolha_comp_idx_str = input("Número do componente para editar limiares (0 voltar): ").strip()
            if not escolha_comp_idx_str: pass 
            else:
                escolha_comp_idx = int(escolha_comp_idx_str)
                if escolha_comp_idx > 0 and escolha_comp_idx <= len(componentes):
                    comp_sel = componentes[escolha_comp_idx - 1]
                    id_comp_sel, tipo_comp_sel = comp_sel['id_componente'], comp_sel['tipo']
                    if tipo_comp_sel not in METRIC_THRESHOLDS_FAIXA:
                        print(f"'{tipo_comp_sel}' usa alerta específico, não editável aqui.");
                    else:
                        print(f"Editando Limiares para: {tipo_comp_sel} (ID: {id_comp_sel})")
                        print("(Deixe em branco para manter; 'NULL' para remover limiar)")
                        th_l_atu,th_g_atu,th_c_atu = comp_sel.get('threshold_leve'),comp_sel.get('threshold_grave'),comp_sel.get('threshold_critico')
                        def proc_lim_inp(inp_str, atu_val):
                            if inp_str.upper()=='NULL': return None
                            return float(inp_str) if inp_str else atu_val
                        n_th_l = proc_lim_inp(input(f"Novo Leve (atual:{th_l_atu if th_l_atu is not None else 'N/A'}): ").strip(), th_l_atu)
                        n_th_g = proc_lim_inp(input(f"Novo Grave (atual:{th_g_atu if th_g_atu is not None else 'N/A'}): ").strip(), th_g_atu)
                        n_th_c = proc_lim_inp(input(f"Novo Crítico (atual:{th_c_atu if th_c_atu is not None else 'N/A'}): ").strip(), th_c_atu)
                        validos = True
                        if n_th_l is not None and n_th_g is not None and n_th_l >= n_th_g: print("❌ Leve >= Grave"); validos=False
                        if n_th_g is not None and n_th_c is not None and n_th_g >= n_th_c: print("❌ Grave >= Crítico"); validos=False
                        if n_th_l is not None and n_th_c is not None and n_th_l >= n_th_c: print("❌ Leve >= Crítico"); validos=False
                        if validos:
                            sql_upd = "UPDATE componente SET threshold_leve=%s,threshold_grave=%s,threshold_critico=%s WHERE id_componente=%s"
                            mycursor.execute(sql_upd,(n_th_l,n_th_g,n_th_c,id_comp_sel)); cnx.commit(); print("✅ Limiares atualizados!")
                        else: print("Limiares não atualizados por erro de validação.")
                elif escolha_comp_idx != 0: print("❌ Número de componente inválido.")
        except ValueError: print("❌ Entrada inválida.")
        except Exception as e: print(f"❌ Erro gerenciar limiares: {e}")
    if voltar_ao_menu_ou_encerrar(): return
    else: encerrar_servico()

# --- Função Principal de Execução ---
def executar():
    id_maquina_ativo = None
    fk_maquina_modelo_atual = None 
    registrada, id_maquina_registrada, id_empresa_registrada, fk_maquina_modelo_atual = verificar_maquina_registrada()
    
    if registrada:
        id_maquina_ativo = id_maquina_registrada
        if fk_maquina_modelo_atual is None:
            print(f"\nAVISO: A máquina '{serial_number}' não possui um modelo atribuído.")
            obter_ou_atribuir_modelo_maquina(id_maquina_ativo, fk_maquina_modelo_atual)
    else:
        login_sucesso, id_maquina_apos_login, id_empresa_apos_login = fazer_login_e_registrar_maquina()
        if login_sucesso and id_maquina_apos_login:
            id_maquina_ativo = id_maquina_apos_login
            obter_ou_atribuir_modelo_maquina(id_maquina_ativo, None) 
        else:
            print("❌ Falha login/registro. Encerrando."); encerrar_servico(); return
    
    if not id_maquina_ativo: 
        print("ERRO CRÍTICO: ID de máquina inválido. Encerrando."); encerrar_servico(); return

    def menu_inicial_display(): print_linha(); print(" Bem-vindo ao Sentinela v2.0 ".center(73, "=")); print_linha()
    def escolha_usuario_display():
        print_linha(); print("\nOpções:");
        return input("1. Info Máquina | 2. Monitorar | 3. Gerenciar Métricas | 0. Encerrar\nEscolha: ").strip()
    while True:
        menu_inicial_display(); escolha = escolha_usuario_display()
        if escolha == "1": menu_informacoes_maquina()
        elif escolha == "2": monitoramento_em_tempo_real(id_maquina_ativo)
        elif escolha == "3": gerenciar_metricas_maquina(id_maquina_ativo) 
        elif escolha == "0": encerrar_servico(); break
        else: print_linha(); print("Opção inválida!")

# --- Bloco Principal ---
if __name__ == "__main__":
    if not CONFIG[AMBIENTE].get("password") or not CONFIG[AMBIENTE].get("host") or not cnx or not mycursor:
        print("ERRO FATAL: Config DB falhou. Verifique .env. Encerrando.")
    else:
        print("Obtendo informações de rede para configuração inicial...")
        get_active_network_link_info(verbose=False) 
        print("Pronto para iniciar.")
        executar()
