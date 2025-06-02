import mysql.connector
import psutil
import platform
import time
import subprocess
import cpuinfo
import os
import re 
from datetime import datetime, timedelta
from dotenv import load_dotenv
import requests
from jira import JIRA
import random

# Carrega variáveis do arquivo .env
load_dotenv()

AMBIENTE = os.getenv("AMBIENTE", "local")
JIRA_URL = os.getenv('JIRA_URL')
JIRA_USERNAME = os.getenv('JIRA_USERNAME')
JIRA_API_TOKEN = os.getenv('JIRA_API_TOKEN')
JIRA_PROJECT_KEY = 'SUPSEN'
JIRA_ISSUE_TYPE_ALERT = 'Alertas'
JIRA_CUSTOM_FIELD_COMPONENT_TYPE = 'customfield_10058'
JIRA_CUSTOM_FIELD_SEVERITY = 'customfield_10059'
JIRA_CUSTOM_FIELD_STORY_POINTS = 'customfield_10010'
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

# --- Configuração do Jira ---
jira_client = None
if not all([JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN]):
    print("AVISO: Credenciais do Jira não configuradas. Integração desabilitada.")
else:
    try:
        jira_client = JIRA(server=JIRA_URL, basic_auth=(JIRA_USERNAME, JIRA_API_TOKEN))
    except Exception as e:
        print(f"Erro ao conectar ao Jira: {e}. Integração desabilitada.")
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

# Lógica para obter serial number
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

def print_linha(char="=", length=73): print(f"\n{char * length}")
def encerrar_servico():
    print_linha(); print("\nServiço encerrado.");
    if cnx and cnx.is_connected(): cnx.close()
    exit()
def voltar_ao_menu_ou_encerrar():
    print_linha(); escolha = input("Voltar ao menu principal? (S/N): ").strip().lower()
    return escolha == 's'
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
    
    if voltar_ao_menu_ou_encerrar(): 
        return
    else: 
        encerrar_servico()

def verificar_maquina_registrada():
    global id_empresa_global; print_linha(); print("🔍 Buscando máquina...");
    sql = "SELECT id_maquina, fk_maquina_empresa FROM maquina WHERE serial_number = %s"
    mycursor.execute(sql, (serial_number,)); resultado = mycursor.fetchone()
    if resultado:
        id_maquina_atual = resultado['id_maquina']; id_empresa_global = resultado['fk_maquina_empresa']
        print(f"✅ Máquina '{serial_number}' (ID:{id_maquina_atual}) encontrada, empresa ID:{id_empresa_global}.")
        return True, id_maquina_atual, id_empresa_global
    print(f"❌ Máquina '{serial_number}' não encontrada."); return False, None, None

def fazer_login_e_registrar_maquina():
    global id_empresa_global; print_linha(); print("🔐 Login para associar máquina.")
    while True:
        email = input("E-mail: ").strip(); senha = input("Senha: ").strip()
        sql_user = "SELECT id_usuario, fk_colaborador_empresa FROM colaborador WHERE email = %s AND senha = SHA2(%s, 256)"
        mycursor.execute(sql_user, (email, senha)); usuario = mycursor.fetchone()
        if usuario:
            print("🔓 Login sucesso."); id_empresa_global = usuario['fk_colaborador_empresa']
            id_maquina_cadastrada = cadastrar_maquina_atual(id_empresa_global)
            if id_maquina_cadastrada: return True, id_maquina_cadastrada, id_empresa_global
            print("❌ Falha ao cadastrar máquina pós-login."); return False, None, id_empresa_global
        print("❌ Credenciais inválidas."); retry = input("Tentar (S/N)? ").strip().lower()
        if retry != 's': return False, None, None

def cadastrar_maquina_atual(id_empresa_param):
    print_linha(); setor = input(f"Setor da máquina '{serial_number}': ").strip(); print_linha()
    print(f"SO: {sistema_detalhado}\nSerial: {serial_number}\nINICIANDO CADASTRO...");
    try:
        sql_insert = "INSERT INTO maquina (so, serial_number, setor, fk_maquina_empresa) VALUES (%s, %s, %s, %s)"
        mycursor.execute(sql_insert, (sistema_detalhado, serial_number, setor, id_empresa_param)); cnx.commit()
        id_maquina_nova = mycursor.lastrowid; print(f"✅ MÁQUINA REGISTRADA! ID: {id_maquina_nova}")
        cadastrar_metricas_padrao(id_maquina_nova); return id_maquina_nova
    except mysql.connector.Error as err: print(f"❌ Erro ao cadastrar máquina: {err}"); return None


def cadastrar_metricas_padrao(id_maquina_param):
    """Cadastra um conjunto padrão de métricas/componentes para uma nova máquina."""
    network_info_initial = get_active_network_link_info(verbose=False) 
    modelo_rede_principal = f"{network_info_initial.get('type', 'Rede')} ({network_info_initial.get('interface', 'Padrão')})"

    metricas_definidas = [
        {"tipo": "cpu_percent", "descricao": "Percentual de CPU", "modelo": processador_modelo, "unidade": "%"},
        {"tipo": "disk_percent", "descricao": "Percentual de uso de disco", "modelo": "Disco Principal", "unidade": "%"},
        {"tipo": "ram_percent", "descricao": "Percentual de uso de RAM", "modelo": "Memória RAM", "unidade": "%"},
        {"tipo": "disk_usage_gb", "descricao": "Uso de Disco em GB", "modelo": "Disco Principal", "unidade": "GB"},
        {"tipo": "ram_usage_gb", "descricao": "Uso de RAM em GB", "modelo": "Memória RAM", "unidade": "GB"},
        
        # Métricas de rede existentes
        {"tipo": "net_upload", "descricao": "Velocidade de Upload Atual", "modelo": modelo_rede_principal, "unidade": "Mbps"}, 
        {"tipo": "net_download", "descricao": "Velocidade de Download Atual", "modelo": modelo_rede_principal, "unidade": "Mbps"},
        
        {"tipo": "link_speed_mbps", "descricao": "Velocidade do Link de Rede", "modelo": modelo_rede_principal, "unidade": "Mbps"},
        {"tipo": "net_usage_percent", "descricao": "Percentual de Uso do Link de Rede", "modelo": modelo_rede_principal, "unidade": "%"},

        {"tipo": "battery_percent", "descricao": "Bateria em uso", "modelo": "Bateria", "unidade": "%"},
        {"tipo": "cpu_freq_ghz", "descricao": "Frequência da CPU", "modelo": processador_modelo, "unidade": "GHz"},
        {"tipo": "uptime_hours", "descricao": "Tempo de atividade", "modelo": "Sistema", "unidade": "horas"}
    ]
    print_linha()
    print("CADASTRANDO MÉTRICAS PADRÃO AUTOMATICAMENTE...")
    for metrica in metricas_definidas:
        try:
            minimo, maximo = 0, 100
            if metrica['tipo'] in ['cpu_percent', 'disk_percent', 'ram_percent', 'battery_percent', 'net_usage_percent']:
                minimo, maximo = 0, 100 
                if metrica['tipo'] != 'net_usage_percent' and metrica['tipo'] != 'battery_percent': 
                     minimo, maximo = 30, 70
            elif metrica['tipo'] == 'cpu_freq_ghz' and cpu_frequencia_max_ghz > 0:
                minimo, maximo = round(cpu_frequencia_max_ghz * 0.3, 2), round(cpu_frequencia_max_ghz * 0.8, 2)
            elif metrica['tipo'] == 'disk_usage_gb' and disco_total_gb > 0:
                minimo, maximo = round(disco_total_gb * 0.3, 2), round(disco_total_gb * 0.7, 2)
            elif metrica['tipo'] == 'ram_usage_gb' and memoria_total_gb > 0:
                minimo, maximo = round(memoria_total_gb * 0.3, 2), round(memoria_total_gb * 0.7, 2)
            elif metrica['tipo'] in ['net_upload', 'net_download', 'link_speed_mbps']:
                minimo, maximo = 0, 1000 
            
            sql = """
            INSERT INTO componente (tipo, modelo, valor, minimo, maximo, fk_componente_maquina, unidade_medida)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE modelo=VALUES(modelo), minimo=VALUES(minimo), maximo=VALUES(maximo), unidade_medida=VALUES(unidade_medida)
            """
            val = (metrica['tipo'], metrica['modelo'], 0, minimo, maximo, id_maquina_param, metrica['unidade'])
            mycursor.execute(sql, val)
            print(f"✅ Métrica '{metrica['descricao']}' ({metrica['tipo']}) configurada com modelo '{metrica['modelo']}'.")
        except mysql.connector.Error as err:
            print(f"❌ Erro ao cadastrar métrica '{metrica['descricao']}': {err}")
    cnx.commit()
    print_linha(); print("TODAS AS MÉTRICAS PADRÃO FORAM CONFIGURADAS!")


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
        cmd = "netsh wlan show interfaces"; result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=False, encoding='cp850', errors='ignore')
        if result.returncode != 0: return None
        output = result.stdout
        for pattern_key in [r'Transmit rate \(Mbps\)\s*:\s*([\d.]+)', r'Receive rate \(Mbps\)\s*:\s*([\d.]+)', r'Taxa de transmissão \(Mbps\)\s*:\s*([\d.]+)', r'Taxa de recepção \(Mbps\)\s*:\s*([\d.]+)']:
            match = re.search(pattern_key, output)
            if match: return float(match.group(1))
    except: return None
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
        cmd = f'wmic nic where "NetConnectionStatus=2 AND (Name LIKE \'%{adapter_name_hint}%\' OR NetConnectionID LIKE \'%{adapter_name_hint}%\')" get Speed'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=False, encoding='cp850', errors='ignore')
        if result.returncode != 0: return None
        output = result.stdout.strip(); lines = output.splitlines()
        if len(lines) > 1:
            for line in lines[1:]:
                if line.strip().isdigit(): speed_bps = int(line.strip()); return speed_bps / 1000000 # Mbps
    except FileNotFoundError: print(f"AVISO: 'wmic' não encontrado para Ethernet em Windows."); return None
    except: return None
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
    """Tenta detectar a conexão ativa (Wi-Fi ou Ethernet) e retorna sua velocidade e tipo."""
    link_speed = None
    connection_type = "Desconhecido"
    active_interface = "N/A"

    if verbose: print("Procurando link Wi-Fi ativo...")
    if sistema_operacional == "Linux":
        interfaces_wifi_linux = ['wlan0', 'wlp2s0', 'wlp3s0', 'wlp1s0', 'wlp0s20f3']
        for iface in interfaces_wifi_linux:
            speed = get_wifi_link_speed_linux(interface=iface)
            if speed is not None: active_interface, connection_type, link_speed = iface, "Wi-Fi", speed; break
    elif sistema_operacional == "Windows":
        speed = get_wifi_link_speed_windows()
        if speed is not None: active_interface, connection_type, link_speed = "Wi-Fi Padrão", "Wi-Fi", speed
    elif sistema_operacional == "Darwin":
        speed = get_wifi_link_speed_macos()
        if speed is not None: active_interface, connection_type, link_speed = "Airport", "Wi-Fi", speed
    
    if link_speed is not None and verbose:
        print(f"Conexão {connection_type} ({active_interface}) encontrada: {link_speed} Mbps")
    elif verbose:
        print("Nenhum link Wi-Fi ativo encontrado ou velocidade não obtida. Procurando Ethernet...")

    if link_speed is None: 
        if sistema_operacional == "Linux":
            interfaces_eth_linux = ['eth0', 'enp2s0', 'enp3s0', 'enp1s0', 'eno1']
            for iface in interfaces_eth_linux:
                speed = get_ethernet_link_speed_linux(interface=iface)
                if speed is not None: active_interface, connection_type, link_speed = iface, "Ethernet", speed; break
        elif sistema_operacional == "Windows":
            ethernet_adapter_hints = ["Ethernet", "Local Area Connection", "Conexão Local"]
            for hint in ethernet_adapter_hints:
                speed = get_ethernet_link_speed_windows(adapter_name_hint=hint)
                if speed is not None: active_interface, connection_type, link_speed = hint, "Ethernet", speed; break
        elif sistema_operacional == "Darwin":
            ethernet_ports_macos = ['en0', 'en1', 'en2']
            for port in ethernet_ports_macos:
                speed = get_ethernet_link_speed_macos(interface_port=port)
                if speed is not None: active_interface, connection_type, link_speed = port, "Ethernet", speed; break
        
        if link_speed is not None and verbose:
            print(f"Conexão {connection_type} ({active_interface}) encontrada: {link_speed} Mbps")
        elif verbose:
            print("Nenhum link Ethernet ativo encontrado ou velocidade não obtida.")

    if link_speed is None and sistema_operacional == "Linux" and verbose:
        custom_interface = input("Interface Wi-Fi customizada (ou Enter para pular): ").strip()
        if custom_interface:
            speed = get_wifi_link_speed_linux(interface=custom_interface)
            if speed is not None: active_interface,connection_type,link_speed = custom_interface,"Wi-Fi Custom",speed
    
    if link_speed is None and verbose:
         print("Não foi possível determinar a velocidade do link de rede ativa.")

    return {'speed_mbps': link_speed, 'type': connection_type, 'interface': active_interface, 'modelo_detalhado': f"{connection_type} ({active_interface})"}

def capturar_processos_sistema():
    processos_lista = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            info = proc.info
            if info['name'] and info['name'] != "System" and info['pid'] != 0:
                processos_lista.append({'timestamp': datetime.now().isoformat(), 'pid': info['pid'], 
                                       'nome': info['name'], 'cpu_percent': info['cpu_percent'], 
                                       'memory_percent': info['memory_percent']})
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess): pass
    return processos_lista

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
    if not jira_client: print(f"AVISO Jira: Não configurado. Alerta '{componente_tipo}' não enviado."); return False
    try:
        issue_dict = {'project': {'key': JIRA_PROJECT_KEY}, 'summary': f"Máquina {serial_number}: {resumo_especifico}",
                      'description': f"*Máquina {serial_number}* – {descricao_detalhada}", 
                      'issuetype': {'name': JIRA_ISSUE_TYPE_ALERT},
                      JIRA_CUSTOM_FIELD_COMPONENT_TYPE: {'value': componente_tipo},
                      JIRA_CUSTOM_FIELD_SEVERITY: {'value': severidade}}
        if JIRA_CUSTOM_FIELD_STORY_POINTS: issue_dict[JIRA_CUSTOM_FIELD_STORY_POINTS] = "5" # Exemplo
        new_issue = jira_client.create_issue(fields=issue_dict)
        print(f"✅ Alerta Jira '{componente_tipo}': {new_issue.key}"); return True
    except Exception as e: print(f"❌ Erro criar alerta Jira '{componente_tipo}': {e}"); return False

def verificar_e_disparar_alerta(metrica_tipo, valor_atual, limiar, severidade, resumo_alerta, desc_alerta):
    global alert_cooldown_tracker; agora = datetime.now()
    if valor_atual >= limiar:
        ultimo_alerta = alert_cooldown_tracker.get(metrica_tipo)
        if not ultimo_alerta or agora > ultimo_alerta:
            if criar_alerta_jira_issue(metrica_tipo, severidade, resumo_alerta, desc_alerta):
                alert_cooldown_tracker[metrica_tipo] = agora + timedelta(minutes=ALERT_COOLDOWN_MINUTES)
                print(f"ℹ️ Alerta {metrica_tipo} ativado. Cooldown até {alert_cooldown_tracker[metrica_tipo]:%H:%M:%S}")

def salvar_metrica_historico(id_componente_db, valor_capturado, timestamp_captura):
    try:
        sql = "INSERT INTO historico (data_captura, valor, fk_historico_componente) VALUES (%s, %s, %s)"
        mycursor.execute(sql, (timestamp_captura, valor_capturado, id_componente_db))
    except Exception as e: print(f"❌ Erro salvar histórico comp ID {id_componente_db}: {e}")

def monitoramento_em_tempo_real(id_maquina_param):
    global alert_cooldown_tracker
    alert_cooldown_tracker = {}

    print_linha()
    print(f"Iniciando monitoramento: Máquina ID: {id_maquina_param} (Serial: {serial_number})")
    
    network_link_info = get_active_network_link_info(verbose=True)
    current_link_speed_mbps = network_link_info.get('speed_mbps')
    current_connection_type = network_link_info.get('type', "Desconhecido")
    current_active_interface = network_link_info.get('interface', "N/A")
    
    print(f"Monitorando link de rede: Tipo='{current_connection_type}', Interface='{current_active_interface}', Velocidade Link='{current_link_speed_mbps if current_link_speed_mbps is not None else 'N/A'}' Mbps")
    print("Pressione Ctrl+C para parar.")
    print_linha()

    sql_metricas_cfg = "SELECT id_componente, tipo, unidade_medida FROM componente WHERE fk_componente_maquina = %s"
    mycursor.execute(sql_metricas_cfg, (id_maquina_param,))
    metricas_a_monitorar = mycursor.fetchall()

    if not metricas_a_monitorar:
        print("❌ Nenhuma métrica configurada. Monitoramento não pode iniciar."); return

    print("Métricas sendo monitoradas (do DB):")
    for m_cfg in metricas_a_monitorar: print(f"- Tipo: {m_cfg['tipo']} (ID Comp: {m_cfg['id_componente']})")
    print_linha()
    
    last_net_io = psutil.net_io_counters() # Contadores globais do sistema
    last_net_time = time.time()
    
    try:
        while True:
            timestamp_ciclo = datetime.now()
            dados_coletados_ciclo = []

            processos_atuais = capturar_processos_sistema()
            if processos_atuais:
                payload_proc = {'timestamp': timestamp_ciclo.isoformat(), 'processos': processos_atuais}
                enviar_dados_api(API_PROCESS_ENDPOINT, id_maquina_param, payload_proc, "processos")

            current_net_io = psutil.net_io_counters()
            current_net_time = time.time()
            elapsed_time_net = current_net_time - last_net_time
            
            net_upload_mbps, net_download_mbps = 0.0, 0.0
            if elapsed_time_net > 0:
                bytes_sent_delta = current_net_io.bytes_sent - last_net_io.bytes_sent
                bytes_recv_delta = current_net_io.bytes_recv - last_net_io.bytes_recv
                net_upload_mbps = (bytes_sent_delta * 8) / (elapsed_time_net * 1024 * 1024)
                net_download_mbps = (bytes_recv_delta * 8) / (elapsed_time_net * 1024 * 1024)
            
            last_net_io = current_net_io
            last_net_time = current_net_time

            for metrica_cfg in metricas_a_monitorar:
                id_componente = metrica_cfg['id_componente']
                tipo_metrica = metrica_cfg['tipo']
                unidade_metrica_db = metrica_cfg['unidade_medida'] 
                valor_atual = None
                unidade_final_envio = unidade_metrica_db 

                try:
                    if tipo_metrica == 'cpu_percent':
                        valor_atual = psutil.cpu_percent(interval=None)
                        verificar_e_disparar_alerta(tipo_metrica, valor_atual, CPU_CRITICAL_THRESHOLD, "Crítico", "Uso de CPU Elevado", f"CPU em {valor_atual:.1f}%.")
                    elif tipo_metrica == 'disk_percent':
                        valor_atual = psutil.disk_usage('/').percent
                        verificar_e_disparar_alerta(tipo_metrica, valor_atual, DISK_HIGH_THRESHOLD, "Leve", "Uso de Disco Elevado", f"Disco em {valor_atual:.1f}%.")
                    elif tipo_metrica == 'ram_percent':
                        valor_atual = psutil.virtual_memory().percent
                        verificar_e_disparar_alerta(tipo_metrica, valor_atual, RAM_CRITICAL_THRESHOLD, "Crítico", "Uso de RAM Elevado", f"RAM em {valor_atual:.1f}%.")
                    elif tipo_metrica == 'disk_usage_gb':
                        valor_atual = psutil.disk_usage('/').used / (1024 ** 3)
                    elif tipo_metrica == 'ram_usage_gb':
                        valor_atual = psutil.virtual_memory().used / (1024 ** 3)

                    elif tipo_metrica == 'net_upload':
                        valor_atual = net_upload_mbps
                        unidade_final_envio = "Mbps" 
                        if valor_atual < NET_UPLOAD_NO_CONNECTION_THRESHOLD and current_link_speed_mbps is not None :
                             verificar_e_disparar_alerta(tipo_metrica, NET_UPLOAD_NO_CONNECTION_THRESHOLD, NET_UPLOAD_NO_CONNECTION_THRESHOLD, "Grave", "Sem Conexão de Upload", "Upload próximo de zero.")
                    elif tipo_metrica == 'net_download':
                        valor_atual = net_download_mbps
                        unidade_final_envio = "Mbps" 

                    elif tipo_metrica == 'link_speed_mbps':
                        valor_atual = current_link_speed_mbps 
                        unidade_final_envio = "Mbps"
                    elif tipo_metrica == 'net_usage_percent':
                        if current_link_speed_mbps is not None and current_link_speed_mbps > 0:
                            trafego_total_mbps = net_upload_mbps + net_download_mbps
                            valor_atual = (trafego_total_mbps / current_link_speed_mbps) * 100
                            valor_atual = min(max(valor_atual, 0.0), 100.0) 
                            verificar_e_disparar_alerta(tipo_metrica, valor_atual, NETWORK_USAGE_HIGH_THRESHOLD, "Moderado", "Uso de Rede Elevado", f"Uso do link de rede em {valor_atual:.1f}%.")
                        else:
                            valor_atual = 0 
                        unidade_final_envio = "%"
                        
                    elif tipo_metrica == 'battery_percent':
                        battery_info = psutil.sensors_battery(); valor_atual = battery_info.percent if battery_info else 0
                        if valor_atual == BATTERY_CRITICAL_THRESHOLD: verificar_e_disparar_alerta(tipo_metrica, 0.1, 0.1, "Leve", "Robô Inativo (Bateria 0%)", "Bateria em 0%.") 
                        elif valor_atual <= BATTERY_LOW_THRESHOLD and valor_atual > BATTERY_CRITICAL_THRESHOLD : verificar_e_disparar_alerta(tipo_metrica, BATTERY_LOW_THRESHOLD - valor_atual + 0.1 , 0.1, "Leve", "Bateria Baixa", f"Bateria em {valor_atual}%.")
                    elif tipo_metrica == 'cpu_freq_ghz':
                        cpu_f = psutil.cpu_freq(); valor_atual = (cpu_f.current / 1000) if cpu_f else 0
                    elif tipo_metrica == 'uptime_hours':
                        valor_atual = (time.time() - psutil.boot_time()) / 3600
                        verificar_e_disparar_alerta(tipo_metrica, valor_atual, UPTIME_HIGH_THRESHOLD_HOURS, "Leve", "Uptime Elevado", f"Uptime {valor_atual:.1f} horas.")
                    
                    if valor_atual is not None:
                        dados_coletados_ciclo.append({'tipo': tipo_metrica, 'valor': valor_atual, 'unidade': unidade_final_envio})
                        salvar_metrica_historico(id_componente, valor_atual, timestamp_ciclo)
                        
                        payload_metrica_api = {
                            "timestamp": timestamp_ciclo.isoformat(), "tipo": tipo_metrica,
                            "valor": round(valor_atual, 4) if isinstance(valor_atual, float) else valor_atual,
                            "unidade": unidade_final_envio, "serial_number": serial_number
                        }
                        enviar_dados_api(API_METRIC_ENDPOINT, id_maquina_param, payload_metrica_api, f"métrica {tipo_metrica}")
                except Exception as e_metrica:
                    print(f"❌ Erro coletar/processar métrica {tipo_metrica}: {e_metrica}")
            
            cnx.commit()
            print_linha("-", 30)
            print(f"{timestamp_ciclo.strftime('%Y-%m-%d %H:%M:%S')} - Status:")
            for dado in dados_coletados_ciclo: print(f"  {dado['tipo']}: {dado['valor']:.2f} {dado['unidade']}")
            
            tempo_processamento_ciclo = time.time() - current_net_time 
            sleep_time = max(0, 5 - tempo_processamento_ciclo) 
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\nMonitoramento interrompido.");
        if cnx and cnx.is_connected(): cnx.commit()
    finally:
        if voltar_ao_menu_ou_encerrar(): return
        else: encerrar_servico()
def gerenciar_metricas_maquina(id_maquina_param):
    """Permite visualizar e editar limites (mínimo/máximo) das métricas de uma máquina."""
    print_linha()
    print("Gerenciamento de Métricas")
    print_linha("=", 73)

    sql_select = """
        SELECT id_componente, tipo, modelo, minimo, maximo, unidade_medida
        FROM componente
        WHERE fk_componente_maquina = %s;
    """
    mycursor.execute(sql_select, (id_maquina_param,))
    metricas = mycursor.fetchall()

    if not metricas:
        print("❌ Nenhuma métrica encontrada para esta máquina.")
        if voltar_ao_menu_ou_encerrar(): return 
        else: encerrar_servico()
        return 

    print("Métricas registradas no sistema para esta máquina:")
    for m in metricas:
        print(f"ID: {m['id_componente']} | Tipo: {m['tipo']} | Modelo: {m['modelo']} | Unidade: {m.get('unidade_medida', 'N/A')} | Mínimo: {m['minimo']} | Máximo: {m['maximo']}")

    print_linha()
    try:
        id_metrica_editar_str = input("Digite o ID da métrica que deseja editar (ou 0 para voltar): ").strip()
        if not id_metrica_editar_str:
            print("Nenhum ID fornecido.")
            if voltar_ao_menu_ou_encerrar(): return
            else: encerrar_servico()
            return

        id_metrica_editar = int(id_metrica_editar_str)

        if id_metrica_editar == 0:
            if voltar_ao_menu_ou_encerrar(): return
            else: encerrar_servico()
            return

        metrica_selecionada = next((m for m in metricas if m['id_componente'] == id_metrica_editar), None)

        if not metrica_selecionada:
            print("❌ Métrica não encontrada com o ID fornecido.")
        else:
            print(f"Editando a métrica: {metrica_selecionada['tipo']} (Modelo: {metrica_selecionada['modelo']})")
            print(f"Mínimo atual: {metrica_selecionada['minimo']} | Máximo atual: {metrica_selecionada['maximo']}")

            novo_minimo_str = input(f"Digite o novo valor mínimo (atual: {metrica_selecionada['minimo']}): ").strip()
            novo_maximo_str = input(f"Digite o novo valor máximo (atual: {metrica_selecionada['maximo']}): ").strip()

            novo_minimo = float(novo_minimo_str) if novo_minimo_str else metrica_selecionada['minimo']
            novo_maximo = float(novo_maximo_str) if novo_maximo_str else metrica_selecionada['maximo']

            if novo_minimo >= novo_maximo:
                print("❌ Erro: O valor mínimo deve ser menor que o valor máximo.")
            else:
                sql_update = "UPDATE componente SET minimo = %s, maximo = %s WHERE id_componente = %s"
                mycursor.execute(sql_update, (novo_minimo, novo_maximo, id_metrica_editar))
                cnx.commit()
                print("✅ Métrica atualizada com sucesso!")

    except ValueError:
        print("❌ Entrada inválida. Por favor, digite um número para ID, mínimo e máximo.")
    except Exception as e:
        print(f"❌ Erro ao editar a métrica: {str(e)}")

    if voltar_ao_menu_ou_encerrar(): return
    else: encerrar_servico()

def executar():
    id_maquina_ativo = None
    registrada, id_maquina_registrada, _ = verificar_maquina_registrada()
    if registrada: id_maquina_ativo = id_maquina_registrada
    else:
        login_sucesso, id_maquina_apos_login, _ = fazer_login_e_registrar_maquina()
        if login_sucesso and id_maquina_apos_login: id_maquina_ativo = id_maquina_apos_login
        else: print("❌ Falha login/registro. Encerrando."); encerrar_servico(); return
    if not id_maquina_ativo: print("ERRO CRÍTICO: ID de máquina inválido. Encerrando."); encerrar_servico(); return

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


if __name__ == "__main__":
    if not CONFIG[AMBIENTE].get("password") or not CONFIG[AMBIENTE].get("host") or not cnx or not mycursor:
        print("ERRO FATAL: Config DB falhou. Verifique .env. Encerrando.")
    else:
        print("Obtendo informações de rede para configuração inicial...")
        get_active_network_link_info(verbose=False) #
        print("Pronto para iniciar.")
        executar()