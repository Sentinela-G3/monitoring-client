import mysql.connector
import psutil
import platform
import time
import subprocess
import cpuinfo
from datetime import datetime

# Conexão com o banco de dados
try:
    cnx = mysql.connector.connect(
        host="127.0.0.1",
        user="root",
        password="senha123",
        database="Sentinela",
        port=3307
    )
    print("Conexão com o banco de dados realizada com sucesso.")
except mysql.connector.Error as err:
    print(f"Erro na conexão com o banco de dados: {err}")
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
    output = subprocess.check_output("wmic bios get serialnumber").decode().split("\n")
    serial_number = output[1].strip()
elif sistema_operacional == "Linux":
    output = subprocess.check_output("sudo dmidecode -s system-serial-number", shell=True).decode().strip()
    serial_number = output
elif sistema_operacional == "Darwin":
    output = subprocess.check_output("system_profiler SPHardwareDataType | grep 'Serial Number'").decode().split(":")
    serial_number = output[1].strip()
else:
    serial_number = "Desconhecido"

# Variável global para armazenar o ID da empresa
id_empresa = None

def gerenciar_componentes(id_maquina):
    while True:
        print_linha()
        print("       GERENCIAMENTO DE COMPONENTES E MÉTRICAS       ")
        print_linha()
        
        # Listar componentes cadastrados
        listar_componentes(id_maquina)
        
        print("\nOpções disponíveis:")
        escolha = input("""
        1. Adicionar nova métrica
        2. Editar métrica existente
        3. Excluir métrica
        0. Voltar ao menu principal
        
    Selecione uma opção: """).strip()

        if escolha == "1":
            adicionar_metrica(id_maquina)
        elif escolha == "2":
            editar_metrica(id_maquina)
        elif escolha == "3":
            excluir_metrica(id_maquina)
        elif escolha == "0":
            return
        else:
            print("Opção inválida! Tente novamente.")

def listar_componentes(id_maquina):
    print("\nCOMPONENTES CADASTRADOS:")
    print_linha()
    print("ID | Tipo | Modelo | Min | Max | Unidade")
    print_linha()
    
    try:
        sql = """
        SELECT id_componente, tipo, modelo, minimo, maximo, 
               CASE 
                   WHEN tipo LIKE '%percent' THEN '%'
                   WHEN tipo LIKE '%gb' THEN 'GB'
                   WHEN tipo LIKE '%ghz' THEN 'GHz'
                   WHEN tipo LIKE '%hours' THEN 'horas'
                   WHEN tipo LIKE '%mb' THEN 'MB/s'
                   ELSE ''
               END as unidade
        FROM componente 
        WHERE fk_componente_maquina = %s
        ORDER BY id_componente
        """
        mycursor.execute(sql, (id_maquina,))
        componentes = mycursor.fetchall()

        if not componentes:
            print("Nenhum componente cadastrado para esta máquina.")
            return False

        for comp in componentes:
            print(f"{comp['id_componente']} | {comp['tipo']} | {comp['modelo']} | {comp['minimo']} | {comp['maximo']} | {comp['unidade']}")
        
        print_linha()
        return True
        
    except mysql.connector.Error as err:
        print(f"Erro ao listar componentes: {err}")
        return False

def adicionar_metrica(id_maquina):
    print_linha()
    print("ADICIONAR NOVA MÉTRICA")
    
    processador = platform.processor()
    componentes_disponiveis = {
        "1": {"tipo": "cpu_percent", "descricao": "Percentual de CPU", "modelo": processador, "unidade": "%"},
        "2": {"tipo": "disk_percent", "descricao": "Percentual de uso de disco", "modelo": "Disco Principal", "unidade": "%"},
        "3": {"tipo": "ram_percent", "descricao": "Percentual de uso de RAM", "modelo": "Memória RAM", "unidade": "%"},
        "4": {"tipo": "disk_usage_gb", "descricao": "Uso de Disco em GB", "modelo": "Disco Principal", "unidade": "GB"},
        "5": {"tipo": "ram_usage_gb", "descricao": "Uso de RAM em GB", "modelo": "Memória RAM", "unidade": "GB"},
        "6": {"tipo": "net_upload", "descricao": "Velocidade de Upload", "modelo": "Rede", "unidade": "MB/s"},
        "7": {"tipo": "net_download", "descricao": "Velocidade de Download", "modelo": "Rede", "unidade": "MB/s"},
        "8": {"tipo": "battery_percent", "descricao": "Bateria em uso", "modelo": "Bateria", "unidade": "%"},
        "9": {"tipo": "cpu_freq", "descricao": "Frequência da CPU", "modelo": processador, "unidade": "GHz"},
        "10": {"tipo": "uptime_hours", "descricao": "Tempo de atividade", "modelo": "Sistema", "unidade": "horas"}
    }

    # Mostrar apenas métricas que ainda não foram cadastradas
    sql = "SELECT tipo FROM componente WHERE fk_componente_maquina = %s"
    mycursor.execute(sql, (id_maquina,))
    metricas_cadastradas = [item['tipo'] for item in mycursor.fetchall()]

    metricas_disponiveis = {k: v for k, v in componentes_disponiveis.items() 
                           if v['tipo'] not in metricas_cadastradas}

    if not metricas_disponiveis:
        print("Todas as métricas já foram cadastradas para esta máquina.")
        return

    print("\nMétricas disponíveis para cadastro:")
    for key, comp in metricas_disponiveis.items():
        print(f"{key}. {comp['descricao']} ({comp['unidade']})")
    
    escolha = input("\nSelecione a métrica que deseja adicionar: ").strip()
    
    if escolha not in metricas_disponiveis:
        print("Opção inválida!")
        return

    comp = metricas_disponiveis[escolha]
    print(f"\nConfigurando '{comp['descricao']}'")

    try:
        # Valores padrão diferentes para cada tipo de componente
        if comp['tipo'] in ['cpu_percent', 'disk_percent', 'ram_percent', 'battery_percent']:
            padrao_min = 30
            padrao_max = 70
            faixa = (0, 100)
        elif comp['tipo'] in ['cpu_freq']:
            padrao_min = round(cpu_frequencia * 0.3, 2)
            padrao_max = round(cpu_frequencia * 0.8, 2)
            faixa = (0, cpu_frequencia)
        elif comp['tipo'] in ['disk_usage_gb']:
            padrao_min = round(disco_total * 0.3, 2)
            padrao_max = round(disco_total * 0.7, 2)
            faixa = (0, disco_total)
        elif comp['tipo'] in ['ram_usage_gb']:
            padrao_min = round(memoria_total * 0.3, 2)
            padrao_max = round(memoria_total * 0.7, 2)
            faixa = (0, memoria_total)
        else:
            padrao_min = 0
            padrao_max = 100
            faixa = (0, float('inf'))

        print(f"Valores aceitáveis: {faixa[0]} a {faixa[1]} {comp['unidade']}")
        minimo = input(f"Digite o valor mínimo (Enter para padrão {padrao_min}): ").strip()
        maximo = input(f"Digite o valor máximo (Enter para padrão {padrao_max}): ").strip()

        minimo = float(minimo) if minimo else padrao_min
        maximo = float(maximo) if maximo else padrao_max

        if not (faixa[0] <= minimo <= faixa[1] and faixa[0] <= maximo <= faixa[1] and minimo <= maximo):
            print(f"❌ Valores inválidos. Deve estar entre {faixa[0]} e {faixa[1]} {comp['unidade']}, e mínimo <= máximo.")
            return

        # Cadastrar a nova métrica
        sql = """
        INSERT INTO componente (tipo, modelo, valor, minimo, maximo, fk_componente_maquina)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        val = (
            comp['tipo'],
            comp['modelo'],
            0,  # Valor inicial
            minimo,
            maximo,
            id_maquina
        )
        mycursor.execute(sql, val)
        cnx.commit()
        print(f"✅ Métrica {comp['descricao']} adicionada com sucesso!")

    except ValueError:
        print("❌ Valor inválido.")
    except mysql.connector.Error as err:
        print(f"❌ Erro ao cadastrar métrica: {err}")

def editar_metrica(id_maquina):
    if not listar_componentes(id_maquina):
        return

    try:
        id_componente = int(input("\nDigite o ID da métrica que deseja editar: "))
        
        # Verificar se o componente pertence à máquina
        sql = """
        SELECT id_componente, tipo, modelo, minimo, maximo 
        FROM componente 
        WHERE id_componente = %s AND fk_componente_maquina = %s
        """
        mycursor.execute(sql, (id_componente, id_maquina))
        componente = mycursor.fetchone()

        if not componente:
            print("ID inválido ou métrica não pertence a esta máquina.")
            return

        print(f"\nEditando métrica: {componente['tipo']} (Modelo: {componente['modelo']})")
        print(f"Valores atuais - Mínimo: {componente['minimo']}, Máximo: {componente['maximo']}")

        # Determinar faixa de valores aceitáveis
        if componente['tipo'] in ['cpu_percent', 'disk_percent', 'ram_percent', 'battery_percent']:
            faixa = (0, 100)
        elif componente['tipo'] in ['cpu_freq']:
            faixa = (0, cpu_frequencia)
        elif componente['tipo'] in ['disk_usage_gb']:
            faixa = (0, disco_total)
        elif componente['tipo'] in ['ram_usage_gb']:
            faixa = (0, memoria_total)
        else:
            faixa = (0, float('inf'))

        print(f"Valores aceitáveis: {faixa[0]} a {faixa[1]}")

        # Solicitar novos valores
        novo_minimo = input(f"Novo valor mínimo (Enter para manter {componente['minimo']}): ").strip()
        novo_maximo = input(f"Novo valor máximo (Enter para manter {componente['maximo']}): ").strip()

        novo_minimo = float(novo_minimo) if novo_minimo else componente['minimo']
        novo_maximo = float(novo_maximo) if novo_maximo else componente['maximo']

        if not (faixa[0] <= novo_minimo <= faixa[1] and faixa[0] <= novo_maximo <= faixa[1] and novo_minimo <= novo_maximo):
            print(f"❌ Valores inválidos. Deve estar entre {faixa[0]} e {faixa[1]}, e mínimo <= máximo.")
            return

        # Atualizar no banco de dados
        sql = """
        UPDATE componente 
        SET minimo = %s, maximo = %s 
        WHERE id_componente = %s
        """
        val = (novo_minimo, novo_maximo, id_componente)
        mycursor.execute(sql, val)
        cnx.commit()
        print("✅ Métrica atualizada com sucesso!")

    except ValueError:
        print("❌ Valor inválido.")
    except mysql.connector.Error as err:
        print(f"❌ Erro ao atualizar métrica: {err}")

def excluir_metrica(id_maquina):
    if not listar_componentes(id_maquina):
        return

    try:
        id_componente = int(input("\nDigite o ID da métrica que deseja excluir: "))
        
        # Verificar se o componente pertence à máquina
        sql = "SELECT id_componente FROM componente WHERE id_componente = %s AND fk_componente_maquina = %s"
        mycursor.execute(sql, (id_componente, id_maquina))
        if not mycursor.fetchone():
            print("ID inválido ou métrica não pertence a esta máquina.")
            return

        confirmacao = input("Tem certeza que deseja excluir esta métrica? (S/N): ").strip().lower()
        if confirmacao == 's':
            sql = "DELETE FROM componente WHERE id_componente = %s"
            mycursor.execute(sql, (id_componente,))
            cnx.commit()
            print("✅ Métrica excluída com sucesso!")
        else:
            print("Operação cancelada.")

    except ValueError:
        print("❌ ID inválido.")
    except mysql.connector.Error as err:
        print(f"❌ Erro ao excluir métrica: {err}")

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
        3. Gerenciar componentes e métricas
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

    # Chama a função para identificar e cadastrar os componentes
    identificar_componente(id_maquina)

    if voltar_ao_menu_ou_encerrar():
        executar()

def identificar_componente(id_maquina):
    processador = platform.processor()

    componentes_disponiveis = {
        "1": {"tipo": "cpu_percent", "descricao": "Percentual de CPU", "modelo": processador, "unidade": "%"},
        "2": {"tipo": "disk_percent", "descricao": "Percentual de uso de disco", "modelo": "Disco Principal", "unidade": "%"},
        "3": {"tipo": "ram_percent", "descricao": "Percentual de uso de RAM", "modelo": "Memória RAM", "unidade": "%"},
        "4": {"tipo": "disk_usage_gb", "descricao": "Uso de Disco em GB", "modelo": "Disco Principal", "unidade": "GB"},
        "5": {"tipo": "ram_usage_gb", "descricao": "Uso de RAM em GB", "modelo": "Memória RAM", "unidade": "GB"},
        "6": {"tipo": "net_upload", "descricao": "Velocidade de Upload", "modelo": "Rede", "unidade": "MB/s"},
        "7": {"tipo": "net_download", "descricao": "Velocidade de Download", "modelo": "Rede", "unidade": "MB/s"},
        "8": {"tipo": "battery_percent", "descricao": "Bateria em uso", "modelo": "Bateria", "unidade": "%"},
        "9": {"tipo": "cpu_freq", "descricao": "Frequência da CPU", "modelo": processador, "unidade": "GHz"},
        "10": {"tipo": "uptime_hours", "descricao": "Tempo de atividade", "modelo": "Sistema", "unidade": "horas"}
    }

    print_linha()
    print("Selecione os componentes que deseja monitorar (digite os números separados por vírgula):")
    for key, comp in componentes_disponiveis.items():
        print(f"{key}. {comp['descricao']} ({comp['unidade']})")
    print_linha()

    escolhas = input("Sua escolha: ").strip().split(",")
    componentes_selecionados = []

    for escolha in escolhas:
        escolha = escolha.strip()
        if escolha in componentes_disponiveis:
            comp = componentes_disponiveis[escolha]
            print_linha()
            print(f"Configurando '{comp['descricao']}'")

            try:
                # Valores padrão diferentes para cada tipo de componente
                if comp['tipo'] in ['cpu_percent', 'disk_percent', 'ram_percent', 'battery_percent']:
                    padrao_min = 30
                    padrao_max = 70
                    faixa = (0, 100)
                elif comp['tipo'] in ['cpu_freq']:
                    padrao_min = round(cpu_frequencia * 0.3, 2)  # 30% da frequência máxima
                    padrao_max = round(cpu_frequencia * 0.8, 2)  # 80% da frequência máxima
                    faixa = (0, cpu_frequencia)
                elif comp['tipo'] in ['disk_usage_gb']:
                    padrao_min = round(disco_total * 0.3, 2)
                    padrao_max = round(disco_total * 0.7, 2)
                    faixa = (0, disco_total)
                elif comp['tipo'] in ['ram_usage_gb']:
                    padrao_min = round(memoria_total * 0.3, 2)
                    padrao_max = round(memoria_total * 0.7, 2)
                    faixa = (0, memoria_total)
                else:
                    padrao_min = 0
                    padrao_max = 100
                    faixa = (0, float('inf'))

                print(f"Valores aceitáveis: {faixa[0]} a {faixa[1]} {comp['unidade']}")
                minimo = input(f"Digite o valor mínimo (Enter para padrão {padrao_min}): ").strip()
                maximo = input(f"Digite o valor máximo (Enter para padrão {padrao_max}): ").strip()

                minimo = float(minimo) if minimo else padrao_min
                maximo = float(maximo) if maximo else padrao_max

                if not (faixa[0] <= minimo <= faixa[1] and faixa[0] <= maximo <= faixa[1] and minimo <= maximo):
                    print(f"❌ Valores inválidos. Deve estar entre {faixa[0]} e {faixa[1]} {comp['unidade']}, e mínimo <= máximo.")
                    continue

                componentes_selecionados.append({
                    "tipo": comp["tipo"],
                    "descricao": comp["descricao"],
                    "modelo": comp["modelo"],
                    "unidade": comp["unidade"],
                    "minimo": minimo,
                    "maximo": maximo
                })
            except ValueError:
                print("❌ Valor inválido.")
                continue

    print_linha()
    print("Cadastrando componentes no banco de dados...")
    
    for componente in componentes_selecionados:
        try:
            sql = """
            INSERT INTO componente (tipo, modelo, valor, minimo, maximo, fk_componente_maquina)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            val = (
                componente['tipo'],
                componente['modelo'],
                0,  # Valor inicial sempre 0
                componente['minimo'],
                componente['maximo'],
                id_maquina
            )
            mycursor.execute(sql, val)
            cnx.commit()
            print(f"✅ Componente {componente['descricao']} cadastrado com sucesso!")
        except mysql.connector.Error as err:
            print(f"❌ Erro ao cadastrar componente {componente['descricao']}: {err}")
    
    print_linha()
    print("Todos os componentes foram cadastrados!")
    print_linha()

def monitoramento_em_tempo_real(id_maquina):
    print_linha()
    print("Iniciando monitoramento em tempo real...")
    print_linha()
    
    # Verificar se existem métricas cadastradas para esta máquina
    sql = """
    SELECT c.id_componente, c.tipo 
    FROM componente c
    JOIN maquina m ON c.fk_componente_maquina = m.id_maquina
    WHERE m.id_maquina = %s
    """
    mycursor.execute(sql, (id_maquina,))
    metricas = mycursor.fetchall()
    
    if not metricas:
        print("❌ Nenhuma métrica cadastrada para monitoramento.")
        print("Por favor, cadastre métricas antes de iniciar o monitoramento.")
        if voltar_ao_menu_ou_encerrar():
            return
        else:
            encerrar_servico()
    
    print("Métricas sendo monitoradas:")
    for metrica in metricas:
        print(f"- {metrica['tipo']} (ID: {metrica['id_componente']})")
    print_linha()
    print("Pressione Ctrl+C para parar o monitoramento...")
    print_linha()
    
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
                    elif metrica['tipo'] == 'disk_percent':
                        valor = psutil.disk_usage('/').percent
                        unidade = "%"
                    elif metrica['tipo'] == 'ram_percent':
                        valor = psutil.virtual_memory().percent
                        unidade = "%"
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
                    elif metrica['tipo'] == 'cpu_freq':
                        valor = psutil.cpu_freq().current / 1000  # GHz
                        unidade = "GHz"
                    elif metrica['tipo'] == 'uptime_hours':
                        valor = round(time.time() - psutil.boot_time(), 2) / 3600  # horas
                        unidade = "horas"
                    
                    # Inserir no histórico
                    if valor is not None:
                        sql_historico = """
                        INSERT INTO historico (data_captura, valor, fk_historico_componente)
                        VALUES (%s, %s, %s)
                        """
                        val_historico = (timestamp, valor, metrica['id_componente'])
                        mycursor.execute(sql_historico, val_historico)
                    
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
            
            # Exibir os dados coletados
            print(f"\n{timestamp.strftime('%Y-%m-%d %H:%M:%S')} - Status do Sistema:")
            for dado in dados_monitoramento:
                print(f"{dado['tipo']}: {dado['valor']:.2f}{dado['unidade']}")
            
            cnx.commit()  # Salva todas as inserções no histórico
            time.sleep(2)  # Intervalo entre coletas
            
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
            if id_maquina:
                gerenciar_componentes(id_maquina)
            else:
                print("Máquina não cadastrada. Por favor, cadastre a máquina primeiro.")
        elif escolha == "0":
            encerrar_servico()
        else:
            print_linha()
            print("Opção inválida! Tente novamente.")

# Chama a função para iniciar o sistema
executar()