import mysql.connector
import psutil
import platform
import time
import subprocess
import cpuinfo
import os
from datetime import datetime , timedelta
from dotenv import load_dotenv 
import requests
from jira import JIRA

# Carrega variáveis do arquivo .env
load_dotenv()

AMBIENTE = os.getenv("AMBIENTE", "local")  

# jira_url = os.getenv('jira_url')
# username = os.getenv('username')
api_token = os.getenv('api_token')

jira_url = 'https://sentinelacomvoce.atlassian.net'
username = 'henrique.barros@sptech.school'
# api_token = ''

jira = JIRA(server=jira_url, basic_auth=(username, api_token))

# Configurações por ambiente
CONFIG = {
    "local": {
        "host": "127.0.0.1",
        "port": 3307,
        "user": "root",
        "password": "senha123",
        "database": "Sentinela",
        "local_web_app": "127.0.0.1"
    },
    "producao": {
        "host": "100.29.69.34",
        "port": 3306,
        "user": "root",
        "password": "senha123",
        "database": "sentinela",
        "local_web_app": "18.208.5.45"
    }
}

try:
    config_db = {key: CONFIG[AMBIENTE][key] for key in ("host", "user", "password", "database")}
    cnx = mysql.connector.connect(**config_db)
    print(f"Conexão com o banco de dados ({AMBIENTE}) realizada com sucesso.")
except mysql.connector.Error as err:
    print(f"Erro na conexão: {err}")
    exit()

mycursor = cnx.cursor(dictionary=True)

# Coleta de informações do sistema
nucleos_logicos = psutil.cpu_count(logical=True)
nucleos_fisicos = psutil.cpu_count(logical=False)
cpu_frequencia = psutil.cpu_freq().max / 1000
memoria_total = psutil.virtual_memory().total / (1024 ** 3)  # GB
disco_total = psutil.disk_usage('/').total / (1024 ** 3)  # GB
processador = cpuinfo.get_cpu_info()['brand_raw']
arquitetura = platform.machine()
sistema_operacional = platform.system()
versao_sistema = platform.version()
sistema_detalhado = platform.platform()

# Obtenção do número de série dependendo do sistema operacional
if sistema_operacional == "Windows":
    serial_sources = [
        "wmic bios get serialnumber",
        "wmic csproduct get identifyingnumber",
        "powershell -Command \"Get-WmiObject Win32_BIOS | Select-Object -ExpandProperty SerialNumber\"",
        "powershell -Command \"Get-CimInstance Win32_ComputerSystemProduct | Select-Object -ExpandProperty UUID\""
    ]
    
    serial_number = "Desconhecido"
    
    for cmd in serial_sources:
        try:
            output = subprocess.check_output(cmd, shell=True).decode().strip()
            lines = [line.strip() for line in output.split('\n') if line.strip()]
            
            if len(lines) > 1:
                value = lines[1]
            else:  # 
                value = lines[0] if lines else ""
                
            if value and value != "To Be Filled By O.E.M.":
                serial_number = value
                break
        except:
            continue
elif sistema_operacional == "Linux":
    output = subprocess.check_output("sudo dmidecode -s system-serial-number", shell=True).decode().strip()
    serial_number = output
elif sistema_operacional == "Darwin":
    output = subprocess.check_output("system_profiler SPHardwareDataType | grep 'Serial Number'", shell=True).decode().split(":")
    serial_number = output[1].strip()
else:
    serial_number = "Desconhecido"

# Variável global para armazenar o ID da empresa
id_empresa = None

def print_linha():
    print("\n" + "=" * 73)

def encerrar_servico():
    print_linha()
    print("\nServiço encerrado. Obrigado por usar o sistema Sentinela.")
    exit()

def voltar_ao_menu_ou_encerrar():
    print_linha()
    escolha = input("Deseja voltar ao menu principal? (Digite 'S' para sim ou qualquer outra tecla para encerrar o serviço): ").strip().lower()
    if escolha == 's':
        return True
    else:
        encerrar_servico() 

def menu_inicial():
    print_linha()
    print("                  BEM-VINDO AO SISTEMA DE MONITORAMENTO")
    print("                          SENTINELA - VERSÃO 2.0")
    print("=" * 73)

def escolha_usuario():
    print_linha()
    print("\nComo podemos ajudar você hoje?")
    escolha = input("""
        1. Consultar informações da máquina
        2. Iniciar monitoramento em tempo real
        3. Gerenciar métricas
        0. Encerrar o sistema
                    
    Selecione uma opção (1, 2, 3 ou 0): """).strip()
    return escolha

def verificar_maquina_registrada():
    """Verifica se a máquina está registrada e retorna o ID da empresa associada"""
    global id_empresa
    
    print_linha()
    print("🔍 Buscando sua máquina no sistema...")
    
    # Verifica se o número de série já está registrado
    sql = "SELECT fk_maquina_empresa FROM maquina WHERE serial_number = %s"
    val = (serial_number,)
    mycursor.execute(sql, val)
    resultado = mycursor.fetchone()

    if resultado:
        print("✅ Máquina com serial '{}' encontrada com sucesso!".format(serial_number))
        id_empresa = resultado['fk_maquina_empresa']
        return True
    else:
        print("❌ Máquina com serial '{}' não encontrada no sistema.".format(serial_number))
        return False

def fazer_login():
    """Realiza o login do usuário e retorna o ID da empresa associada"""
    global id_empresa
    
    print_linha()
    print("🔐 Por favor, faça o login para associar essa máquina à empresa.")
    
    while True:
        username = input("E-mail: ").strip()
        password = input("Senha: ").strip()

        # Verificar as credenciais do usuário
        sql_user = "SELECT id_usuario, fk_colaborador_empresa FROM colaborador WHERE email = %s AND senha = SHA2(%s, 256)"
        val_user = (username, password)
        mycursor.execute(sql_user, val_user)
        usuario = mycursor.fetchone()

        if usuario:
            print("🔓 Login realizado com sucesso.")
            id_empresa = usuario['fk_colaborador_empresa']
            
            cadastrar_maquina(id_empresa)
            
            return True
        else:
            print("❌ Credenciais inválidas. Tente novamente ou pressione Ctrl+C para sair.")

def menu_informacoes_maquina():
    print_linha()
    print("        INFORMAÇÕES TÉCNICAS DA MÁQUINA        ")
    print("Modelo do processador: {}".format(processador))
    print("Arquitetura do sistema: {}".format(arquitetura))
    print("Sistema operacional: {}".format(sistema_operacional))
    print("Versão do sistema: {}".format(versao_sistema))
    print("Número de série da máquina: {}".format(serial_number))
    print("Quantidade de núcleos físicos: {}".format(nucleos_fisicos))
    print("Quantidade de núcleos lógicos: {}".format(nucleos_logicos))
    print("Frequência máxima da CPU: {:.2f} MHz".format(cpu_frequencia))
    print("Memória RAM total: {:.2f} GB".format(memoria_total))
    print("Armazenamento total do disco: {:.2f} GB".format(disco_total))
    if voltar_ao_menu_ou_encerrar():
        executar()

def cadastrar_maquina(id_empresa):
    print_linha()
    modelo_maquina = input("Informe o modelo da máquina: ").strip()
    print_linha()
    setor = input("Informe o setor da máquina: ").strip()
    print_linha()
    print("Sistema operacional detectado: {}".format(sistema_detalhado))
    print("Número de série detectado: {}".format(serial_number))
    print_linha()

    print("\nDEFINA O STATUS ATUAL DA MÁQUINA:")
    status = int(input("""
        1. ATIVO
        2. INATIVO
        0. CANCELAR

    Digite a opção correspondente (1, 2 ou 0): """).strip())

    print_linha()
    print("INICIANDO CADASTRO DA MÁQUINA...")
    sql = "INSERT INTO maquina (modelo, so, serial_number, status, setor, fk_maquina_empresa) VALUES (%s, %s, %s, %s, %s, %s)"
    val = (modelo_maquina, sistema_detalhado, serial_number, status, setor, id_empresa)
    mycursor.execute(sql, val)
    cnx.commit()

    # Pega o ID da máquina recém-cadastrada
    id_maquina = mycursor.lastrowid
    print_linha()
    print("MÁQUINA REGISTRADA COM SUCESSO!")

    # Cadastra automaticamente todas as métricas para esta máquina
    cadastrar_metricas_automaticamente(id_maquina)

    if voltar_ao_menu_ou_encerrar():
        executar()

def cadastrar_metricas_automaticamente(id_maquina):
    processador = platform.processor()

    # Lista de todas as métricas que serão capturadas automaticamente
    metricas = [
        {"tipo": "cpu_percent", "descricao": "Percentual de CPU", "modelo": processador, "unidade": "%"},
        {"tipo": "disk_percent", "descricao": "Percentual de uso de disco", "modelo": "Disco Principal", "unidade": "%"},
        {"tipo": "ram_percent", "descricao": "Percentual de uso de RAM", "modelo": "Memória RAM", "unidade": "%"},
        {"tipo": "disk_usage_gb", "descricao": "Uso de Disco em GB", "modelo": "Disco Principal", "unidade": "GB"},
        {"tipo": "ram_usage_gb", "descricao": "Uso de RAM em GB", "modelo": "Memória RAM", "unidade": "GB"},
        {"tipo": "net_upload", "descricao": "Velocidade de Upload", "modelo": "Rede", "unidade": "MB/s"},
        {"tipo": "net_download", "descricao": "Velocidade de Download", "modelo": "Rede", "unidade": "MB/s"},
        {"tipo": "battery_percent", "descricao": "Bateria em uso", "modelo": "Bateria", "unidade": "%"},
        {"tipo": "cpu_freq", "descricao": "Frequência da CPU", "modelo": processador, "unidade": "GHz"},
        {"tipo": "uptime_hours", "descricao": "Tempo de atividade", "modelo": "Sistema", "unidade": "horas"}
    ]

    print_linha()
    print("CADASTRANDO TODAS AS MÉTRICAS AUTOMATICAMENTE...")
    
    for metrica in metricas:
        try:
            if metrica['tipo'] in ['cpu_percent', 'disk_percent', 'ram_percent', 'battery_percent']:
                minimo = 30
                maximo = 70
            elif metrica['tipo'] == 'cpu_freq':
                minimo = round(cpu_frequencia * 0.3, 2)
                maximo = round(cpu_frequencia * 0.8, 2)
            elif metrica['tipo'] == 'disk_usage_gb':
                minimo = round(disco_total * 0.3, 2)
                maximo = round(disco_total * 0.7, 2)
            elif metrica['tipo'] == 'ram_usage_gb':
                minimo = round(memoria_total * 0.3, 2)
                maximo = round(memoria_total * 0.7, 2)
            else:
                minimo = 0
                maximo = 100

            # Insere a métrica no banco de dados
            sql = """
            INSERT INTO componente (tipo, modelo, valor, minimo, maximo, fk_componente_maquina)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            val = (
                metrica['tipo'],
                metrica['modelo'],
                0,  # Valor inicial
                minimo,
                maximo,
                id_maquina
            )
            mycursor.execute(sql, val)
            cnx.commit()
            print(f"✅ Métrica {metrica['descricao']} cadastrada com sucesso!")
        except mysql.connector.Error as err:
            print(f"❌ Erro ao cadastrar métrica {metrica['descricao']}: {err}")
    
    print_linha()
    print("TODAS AS MÉTRICAS FORAM CADASTRADAS AUTOMATICAMENTE!")
    print_linha()

def gerenciar_metricas(id_maquina):
    print_linha()
    print("Gerenciamento de Métricas")
    print("=" * 73)
    
    # Listar todas as métricas cadastradas
    sql = """
        SELECT c.id_componente, c.tipo, c.modelo, c.minimo, c.maximo
        FROM componente c
        JOIN maquina m ON c.fk_componente_maquina = m.id_maquina
        WHERE m.id_maquina = %s;
    """

    mycursor.execute(sql, (id_maquina,))
    metricas = mycursor.fetchall()
    
    if not metricas:
        print("❌ Nenhuma métrica encontrada para edição.")
        voltar_ao_menu_ou_encerrar()
        return

    # Exibir as métricas
    print("Métricas registradas no sistema:")
    for metrica in metricas:
        print(f"ID: {metrica['id_componente']} | Tipo: {metrica['tipo']} | Modelo: {metrica['modelo']} | Mínimo: {metrica['minimo']} | Máximo: {metrica['maximo']}")
    
    print_linha()
    
    # Solicitar ao usuário qual métrica deseja editar
    try:
        id_metrica = int(input("Digite o ID da métrica que deseja editar (ou 0 para voltar): ").strip())
        if id_metrica == 0:
            voltar_ao_menu_ou_encerrar()
            return

        # Verificar se a métrica existe
        sql = "SELECT id_componente, tipo, modelo, minimo, maximo FROM componente WHERE id_componente = %s"
        mycursor.execute(sql, (id_metrica,))
        metrica = mycursor.fetchone()

        if not metrica:
            print("❌ Métrica não encontrada.")
            voltar_ao_menu_ou_encerrar()
            return

        print(f"Editando a métrica: {metrica['tipo']} (Modelo: {metrica['modelo']})")
        print(f"Mínimo atual: {metrica['minimo']} | Máximo atual: {metrica['maximo']}")

        # Solicitar novos valores para mínimo e máximo
        minimo = float(input("Digite o novo valor mínimo: ").strip())
        maximo = float(input("Digite o novo valor máximo: ").strip())

        # Atualizar a métrica no banco de dados
        sql = """
        UPDATE componente
        SET minimo = %s, maximo = %s
        WHERE id_componente = %s
        """
        mycursor.execute(sql, (minimo, maximo, id_metrica))
        cnx.commit()

        print("✅ Métrica atualizada com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao editar a métrica: {str(e)}")

    # Voltar ou encerrar após edição
    voltar_ao_menu_ou_encerrar()

def monitoramento_em_tempo_real(id_maquina):
    print_linha()
    print("Iniciando monitoramento em tempo real...")
    print_linha()
    
    # Obtém todas as métricas cadastradas para esta máquina
    sql = """
    SELECT c.id_componente, c.tipo 
    FROM componente c
    JOIN maquina m ON c.fk_componente_maquina = m.id_maquina
    WHERE m.id_maquina = %s
    """
    mycursor.execute(sql, (id_maquina,))
    metricas = mycursor.fetchall()
    
    print("Métricas sendo monitoradas:")
    for metrica in metricas:
        print(f"- {metrica['tipo']} (ID: {metrica['id_componente']})")
        print_linha()
        print("Pressione Ctrl+C para parar o monitoramento...")
        print_linha()
        hora_desativacao = None
        alerta_bloqueado = False;

    try:
        while True:
            timestamp = datetime.now()
            dados_monitoramento = []

            for metrica in metricas:
                valor = None
                unidade = ""
                try:
                    # Captura dos valores conforme o tipo de métrica
                    if metrica['tipo'] == 'cpu_percent':
                        valor = psutil.cpu_percent(interval=1)
                        unidade = "%"
                        if valor >=80.0:
                            if alerta_bloqueado == False:
                                alerta_bloqueado = True;
                                hora_ativacao_bloqueio = datetime.now()
                                hora_desativacao = hora_ativacao_bloqueio + timedelta(minutes=5)
                                new_issue = jira.create_issue(fields={
                                                'project': {'key': 'SUPSEN'},  # Chave do projeto
                                                'summary': f'Máquina {serial_number}',  # Resumo do ticket
                                                'description': f'*Máquina {serial_number}* – Alerta de *uso maior do que o programado de CPU detectado*', 
                                                'issuetype': {'name': '[System] Incident'},   # Descrição do ticket
                                                'customfield_10060': {'value': 'CPU'},
                                                'customfield_10010': "68",  # requestTypeId específico para o seu caso
                                            })
                                print("Bloqueado:" + str(alerta_bloqueado))
                                print("Tempo para desbloquear: " + str(hora_desativacao))
                                print("Um alerta foi gerado!")

                            
                        
                    elif metrica['tipo'] == 'disk_percent':
                        valor = psutil.disk_usage('/').percent
                        unidade = "%"
                        if valor >= 80.0:
                            if alerta_bloqueado == False:
                                alerta_bloqueado = True;
                                hora_ativacao_bloqueio = datetime.now()
                                hora_desativacao = hora_ativacao_bloqueio + timedelta(minutes=5)
                                new_issue = jira.create_issue(fields={
                                                'project': {'key': 'SUPSEN'},  # Chave do projeto
                                                'summary': f'Máquina {serial_number}',  # Resumo do ticket
                                                'description': f'*Máquina {serial_number}* – Alerta de *uso maior do que o programado do Disco detectado*', 
                                                'issuetype': {'name': '[System] Incident'},   # Descrição do ticket
                                                'customfield_10060': {'value': 'Disco'},
                                                'customfield_10010': "68",  # requestTypeId específico para o seu caso
                                            })
                                print("Um alerta foi gerado!")

                    elif metrica['tipo'] == 'ram_percent':
                        valor = psutil.virtual_memory().percent
                        unidade = "%"

                        if valor >= 90.0:
                            if alerta_bloqueado == False:
                                alerta_bloqueado = True;
                                hora_ativacao_bloqueio = datetime.now()
                                hora_desativacao = hora_ativacao_bloqueio + timedelta(minutes=5)
                                new_issue = jira.create_issue(fields={
                                                'project': {'key': 'SUPSEN'},  # Chave do projeto
                                                'summary': f'Máquina {serial_number}',  # Resumo do ticket
                                                'description': f'*Máquina {serial_number}* – Alerta de *uso maior do que o programado da Memória detectado*', 
                                                'issuetype': {'name': '[System] Incident'},   # Descrição do ticket
                                                'customfield_10060': {'value': 'Memoria'},
                                                'customfield_10010': "68",  # requestTypeId específico para o seu caso
                                            })
                                print("Bloqueado:" + alerta_bloqueado)
                                print("Tempo para desbloquear: " + hora_desativacao)
                                print("Um alerta foi gerado!")

                    elif metrica['tipo'] == 'disk_usage_gb':
                        valor = psutil.disk_usage('/').used / (1024 ** 3)
                        unidade = "GB"
                    elif metrica['tipo'] == 'ram_usage_gb':
                        valor = psutil.virtual_memory().used / (1024 ** 3)
                        unidade = "GB"
                    elif metrica['tipo'] == 'net_upload':
                        net1 = psutil.net_io_counters().bytes_sent
                        time.sleep(1)
                        net2 = psutil.net_io_counters().bytes_sent
                        valor = (net2 - net1) / (1024 * 1024)  # MB/s
                        unidade = "MB/s"
                        if valor == 0.0:
                            if alerta_bloqueado == False:
                                alerta_bloqueado = True;
                                hora_ativacao_bloqueio = datetime.now()
                                hora_desativacao = hora_ativacao_bloqueio + timedelta(minutes=5)
                                new_issue = jira.create_issue(fields={
                                                'project': {'key': 'SUPSEN'},  # Chave do projeto
                                                'summary': f'Máquina {serial_number}',  # Resumo do ticket
                                                'description': f'*Máquina {serial_number}* – Alerta: *Robô sem acesso à internet*', 
                                                'issuetype': {'name': '[System] Incident'},   # Descrição do ticket
                                                'customfield_10060': {'value': 'Rede'},
                                                'customfield_10010': "68",  # requestTypeId específico para o seu caso
                                            })
                                print("Um alerta foi gerado!")

                    elif metrica['tipo'] == 'net_download':
                        net1 = psutil.net_io_counters().bytes_recv
                        time.sleep(1)
                        net2 = psutil.net_io_counters().bytes_recv
                        valor = (net2 - net1) / (1024 * 1024)  # MB/s
                        unidade = "MB/s"
                    elif metrica['tipo'] == 'battery_percent':
                        battery = psutil.sensors_battery()
                        valor = battery.percent if battery else 0
                        unidade = "%"
                        if valor == 0:
                            if alerta_bloqueado == False:
                                alerta_bloqueado = True;
                                hora_ativacao_bloqueio = datetime.now()
                                hora_desativacao = hora_ativacao_bloqueio + timedelta(minutes=5)
                                new_issue = jira.create_issue(fields={
                                                'project': {'key': 'SUPSEN'},  # Chave do projeto
                                                'summary': f'Máquina {serial_number}',  # Resumo do ticket
                                                'description': f'*Máquina {serial_number}* – Alerta: *Robô encontra-se inativo*', 
                                                'issuetype': {'name': '[System] Incident'},   # Descrição do ticket
                                                'customfield_10060': {'value': 'Bateria'},
                                                'customfield_10010': "68",  # requestTypeId específico para o seu caso
                                            })
                                print("Um alerta foi gerado!")

                        if valor <= 10:
                            if alerta_bloqueado == False:
                                alerta_bloqueado = True;
                                hora_ativacao_bloqueio = datetime.now()
                                hora_desativacao = hora_ativacao_bloqueio + timedelta(minutes=5)
                                new_issue = jira.create_issue(fields={
                                                'project': {'key': 'SUPSEN'},  # Chave do projeto
                                                'summary': f'Máquina {serial_number}',  # Resumo do ticket
                                                'description': f'*Máquina {serial_number}* – Alerta: *nível de bateria abaixo de 10%. baixa*', 
                                                'issuetype': {'name': '[System] Incident'},   # Descrição do ticket
                                                'customfield_10060': {'value': 'Bateria'},
                                                'customfield_10010': "68",  # requestTypeId específico para o seu caso
                                            })
                                print("Um alerta foi gerado!")

                    elif metrica['tipo'] == 'cpu_freq':
                        valor = psutil.cpu_freq().current / 1000  # GHz
                        unidade = "GHz"
                    elif metrica['tipo'] == 'uptime_hours':
                        valor = round(time.time() - psutil.boot_time(), 2) / 3600  # horas
                        unidade = "horas"
                        if valor >= 350.0:
                            if alerta_bloqueado == False:
                                alerta_bloqueado = True;
                                hora_ativacao_bloqueio = datetime.now()
                                hora_desativacao = hora_ativacao_bloqueio + timedelta(minutes=5)
                                new_issue = jira.create_issue(fields={
                                                'project': {'key': 'SUPSEN'},  # Chave do projeto
                                                'summary': f'Máquina {serial_number}',  # Resumo do ticket
                                                'description': f'*Máquina {serial_number}* – Alerta: *Robô operando por mais de 14 dias sem interrupção.*', 
                                                'issuetype': {'name': '[System] Incident'},   # Descrição do ticket
                                                'customfield_10060': {'value': 'Tempo de Uso'},
                                                'customfield_10010': "68",  # requestTypeId específico para o seu caso
                                            })
                                print("Um alerta foi gerado!")

                    if hora_desativacao and datetime.now() > hora_desativacao:
                        print("Entrei aqui")
                        alerta_bloqueado = False

                    # Inserir no histórico
                    if valor is not None:
                        payload = {
                            "timestamp": timestamp.isoformat(),
                            "tipo": metrica['tipo'],
                            "valor": valor,
                            "unidade": unidade,
                            "serial_number": serial_number
                        }
                    try:
                        response = requests.post(f"http://{CONFIG[AMBIENTE]['local_web_app']}:3333/medidas/{id_maquina}", json=payload)
                        if response.status_code == 200:
                            print(f"Dado enviado para a API: {payload}")
                        else:
                            print(f"❌ Erro ao enviar para API: {response.status_code} - {response.text}")
                    except Exception as e:
                        print(f"❌ Erro de conexão ao enviar para API: {str(e)}")
                    
                except Exception as e:
                    print(f"Erro ao capturar {metrica['tipo']}: {str(e)}")
                    valor = None
                    unidade = "ERRO"
                
                if valor is not None:
                    dados_monitoramento.append({
                        'tipo': metrica['tipo'],
                        'valor': valor,
                        'unidade': unidade
                    })

                if valor is not None:
                    sql_historico = """
                    INSERT INTO historico (data_captura, valor, fk_historico_componente)
                    VALUES (%s, %s, %s)
                    """
                    val_historico = (timestamp, valor, metrica['id_componente'])
                    mycursor.execute(sql_historico, val_historico)
                    
                cnx.commit()
            
            # Exibir os dados coletados
            print(f"\n{timestamp.strftime('%Y-%m-%d %H:%M:%S')} - Status do Sistema:")
            for dado in dados_monitoramento:
                print(f"{dado['tipo']}: {dado['valor']:.2f}{dado['unidade']}")
            
            cnx.commit()  # Salva todas as inserções no histórico
            time.sleep(2)  # Intervalo entre coletas
            os.system('cls' if os.name == 'nt' else 'clear')
            
    except KeyboardInterrupt:
        print("\nMonitoramento interrompido pelo usuário.")
        cnx.commit()  # Garante que os últimos dados sejam salvos
        if voltar_ao_menu_ou_encerrar():
            return
        else:
            encerrar_servico()

def executar():
    global id_empresa
    
    # Verifica se a máquina já está registrada
    if not verificar_maquina_registrada():
        # Se não estiver registrada, pede login
        if not fazer_login():
            encerrar_servico()
    
    # Obter o ID da máquina (assumindo que já está cadastrada)
    sql = "SELECT id_maquina FROM maquina WHERE serial_number = %s"
    mycursor.execute(sql, (serial_number,))
    resultado = mycursor.fetchone()
    id_maquina = resultado['id_maquina'] if resultado else None
    
    while True:
        menu_inicial()
        escolha = escolha_usuario()

        if escolha == "1":
            menu_informacoes_maquina()
        elif escolha == "2":
            monitoramento_em_tempo_real(id_maquina)
        elif escolha == "3":
            gerenciar_metricas(id_maquina)
        elif escolha == "0":
            encerrar_servico()
        else:
            print_linha()
            print("Opção inválida! Tente novamente.")

# Chama a função para iniciar o sistema
executar()