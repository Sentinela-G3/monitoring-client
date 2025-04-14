import mysql.connector
import psutil
import platform
import time
import subprocess
import cpuinfo
from datetime import datetime

# Conexão com o banco de dados
cnx = mysql.connector.connect(
    host = "127.0.0.1",
    user = "root",
    password = "1964",
    database = "sentinela"
)

mycursor = cnx.cursor(dictionary=True)


def menu_inicial():
    print("=====================================")
    #print(" ###                                       #             \n  #  #    # #    #  ####  #    #   ##     # #   # #####  \n  #  ##   # ##   # #    # #    #  #  #   #   #  # #    # \n  #  # #  # # #  # #    # #    # #    # #     # # #    # \n  #  #  # # #  # # #    # #    # ###### ####### # #####  \n  #  #   ## #   ## #    #  #  #  #    # #     # # #   #  \n ### #    # #    #  ####    ##   #    # #     # # #    # \n                                                         \n")
    print("    Bem-vindo ao Sistema de Monitoramento   ")
    print("            Sentinela - Versão 1.0            ")
    print("=====================================")
    print("\nEstamos prontos para começar!")
    inicio = input('Digite "Y" para iniciar o monitoramento ou qualquer outra tecla para encerrar: ').strip().lower()

    return inicio

def coleta_nome_usuario():
    print("\nPerfeito! Vamos começar.")
    nome = input("Por favor, informe o seu nome: ").strip()
    return nome

def escolha_usuario(nome):
    print("\nOlá, {}! O que você deseja fazer?".format(nome))
    escolha = input("""
    1. Ver informações da minha máquina
    2. Cadastrar maquina no sistema
    3. Iniciar monitoramento em tempo real
    0. Encerrar o serviço
    Escolha uma opção (1, 2, 3 ou 0): """).strip()

    return escolha
# Quantidade de núcleos lógicos e físicos da máquina
nucleos_logicos = psutil.cpu_count(logical=True)
nucleos_fisicos = psutil.cpu_count(logical=False)
# Frequência da CPU em MHz
cpu_frequencia = psutil.cpu_freq().max / 1000
# Total de memória RAM em GB
memoria_total = psutil.virtual_memory().total / (1024 ** 3)
# Total de disco em GB
disco_total = psutil.disk_usage('/').total / (1024 ** 3)
# Nome do processador
processador = cpuinfo.get_cpu_info()['brand_raw']
# Arquitetura do sistema (32 bits ou 64 bits)
arquitetura = platform.machine()
# Nome do sistema operacional
sistema_operacional = platform.system()
# Versão do sistema operacional
versao_sistema = platform.version()
sistema_detalhado = platform.platform()
# Número serial da máquina Windows
output = subprocess.check_output("wmic bios get serialnumber").decode().split("\n")
serial_number = output[1].strip()


def menu_informacoes_maquina():
    print("\n=========================================================================")
    print("Número de núcleos lógicos: {}".format(nucleos_logicos))
    print("Número de núcleos físicos: {}".format(nucleos_fisicos))
    print("Frequência máxima da CPU: {:.2f} MHz".format(cpu_frequencia))
    print("Memória total: {:.2f} GB".format(memoria_total))
    print("Espaço total do disco: {:.2f} GB".format(disco_total))
    print("Processador: {}".format(processador))
    print("Arquitetura do sistema: {}".format(arquitetura))
    print("Sistema operacional: {}".format(sistema_operacional))
    print("Versão do sistema operacional: {}".format(versao_sistema))
    print("Número de série: {}".format(serial_number))
    print("=========================================================================")
    return 

def cadastrar_maquina():
    # print("\nCadastrando Maquina...")
    print("\n=========================================================================")
    modelo_maquina = input("Qual é o modelo da maquina?: ").strip()
    print("\n=========================================================================")
    setor = input("Qual é o setor da sua máquina?: ").strip()
    print("\n=========================================================================")

    print("Identificamos o modelo do sistema operacional da sua maquina {}".format(sistema_detalhado))
    
    def get_serial():
        if sistema_operacional == "Windows":
            result = subprocess.check_output("wmic bios get serialnumber", shell=True)
            return result.decode().split("\n")[1].strip()
        elif sistema_operacional == "Linux":
            result = subprocess.check_output("sudo dmidecode -s system-serial-number", shell=True)
            return result.decode().strip()
        elif sistema_operacional == "Darwin":
            result = subprocess.check_output("system_profiler SPHardwareDataType | grep 'Serial Number'", shell=True)
            return result.decode().split(":")[1].strip()
        return "Não encontrado"

    print("Identificamos o número serial da sua maquina {}".format(get_serial()))
    print("\n=========================================================================")
    print("\nQual é o status da sua máquina?")
    status = input("""
    1. Ativo
    2. Inativo
    0. Cancelar
    Escolha uma opção (1, 2 ou 0):""").strip()
    print("\n=========================================================================")
    print("Cadastrando máquina...")
    print("\n=========================================================================")
    sql = "INSERT INTO maquina (modelo, so, serial_number, status, setor, fk_maquina_empresa) VALUES (%s, %s, %s, %s, %s, %s)"
    val = (modelo_maquina, sistema_detalhado, serial_number, status, setor, 1)
    mycursor.execute(sql,val)
    cnx.commit()
    # cnx.close()

#######################################################################
    print("Vamos cadastrar os componentes da máquina...")
    desc_cpu = cpuinfo.get_cpu_info()['brand_raw']
    print(desc_cpu)


    def identificar_componente():
        componentes = []

        componentes.append({
            "tipo": "cpu_percent",
            "modelo": processador,
            "minimo": 10.0,
            "maximo": 40.0
        })
        componentes.append({
            "tipo": "cpu_freq",
            "modelo": processador,
            "minimo": 10.0,
            "maximo": 40.0
        })
        componentes.append({
            "tipo": "virtual_memory.percent",
            "modelo": "DDR4",
            "minimo": 10.0,
            "maximo": 70.0
        })
        componentes.append({
            "tipo": "disk_usage.percent",
            "modelo": "Samsung SSD 860 EVO 500GB",
            "minimo": 20.0,
            "maximo": 80.0
        })
        return componentes
    
    for i in identificar_componente():
        # cadastro componente
        sql = "INSERT INTO componente (tipo, modelo, minimo, maximo, fk_componente_maquina) VALUES (%s,%s,%s,%s,%s)"
        val = (i["tipo"],i["modelo"],i["minimo"],i["maximo"], 1)
        mycursor.execute(sql,val)
    cnx.commit()
    # cnx.close()

menu_inicial()



def monitoramento_em_tempo_real():
    print("\n=========================================================================")

    escolher_maquina = input("Qual máquina você deseja monitorar? (digite o id da maquina):" ).strip()
    sql = "SELECT id_maquina, modelo, so, serial_number, status, setor FROM maquina WHERE id_maquina = %s"
    val = (escolher_maquina, )
    mycursor.execute(sql,val)

    maquina_escolhida = mycursor.fetchone()

    if maquina_escolhida:
        print("\n=========================================================================")
        print("Máquina encontrada:")
        print(f"ID: {maquina_escolhida['id_maquina']}")
        print(f"Modelo: {maquina_escolhida['modelo']}")
        print(f"SO: {maquina_escolhida['so']}")
        print(f"Serial: {maquina_escolhida['serial_number']}")
        print(f"Status: {maquina_escolhida['status']}")
        print(f"Setor: {maquina_escolhida['setor']}")
    else:
        print("\n=========================================================================")
        print("Nenhuma máquina encontrada com esse ID.")

    cnx.commit()
    prog_monitoracao = input("Prosseguir com a monitoração?(digite y ou qualquer outra tecla para escolher outra maquina)\n")

    
    if prog_monitoracao == "y":
        print("\nIniciando monitoramento em tempo real...")
            
        funcoes_metrica = {
            "cpu_percent": lambda: psutil.cpu_percent(interval=1),
            "cpu_freq": lambda: psutil.cpu_freq().current,
            "virtual_memory.percent": lambda: psutil.virtual_memory().percent,
            "disk_usage.percent": lambda: psutil.disk_usage('/').percent
        }

        sql = "SELECT id_componente, tipo, minimo, maximo FROM componente WHERE fk_componente_maquina = %s"
        val = (escolher_maquina,)
        mycursor.execute(sql, val)
        componentes = mycursor.fetchall()

        while True:
            for comp in componentes:
                id_comp = comp['id_componente']
                tipo = comp['tipo']
                minimo = comp['minimo']
                maximo = comp['maximo']

                if tipo in funcoes_metrica:
                    valor = funcoes_metrica[tipo]()
                    dataCaptura = datetime.now()

                    if valor < minimo or valor > maximo:
                        sql_insert = "INSERT INTO alerta (data_captura, valor, fk_alerta_componente) VALUES (%s, %s, %s)"
                        val_insert = (dataCaptura, valor, id_comp)
                        mycursor.execute(sql_insert, val_insert)
                        cnx.commit()
                    else:
                        sql_insert = "INSERT INTO historico (data_captura, valor, fk_historico_componente) VALUES (%s, %s, %s)"
                        val_insert = (dataCaptura, valor, id_comp)
                        mycursor.execute(sql_insert, val_insert)
                        cnx.commit()

                else:
                    print(f"[ERRO] Tipo '{tipo}' não está mapeado nas funções.")

            time.sleep(5)
    else:
        print("\n=========================================================================")
        print("Nenhuma máquina encontrada com esse ID.")
        return

def encerrar_servico():
    print("\nServiço encerrado. Obrigado por usar o sistema Sentinela.")
    exit()


def executar():
    while True:
        inicio = menu_inicial()

        if inicio != 'y':
            break

        nome = coleta_nome_usuario()
        escolha = escolha_usuario(nome)

        if escolha == '1':
            menu_informacoes_maquina()

        elif escolha == '2':
            cadastrar_maquina()

        elif escolha == '3':
            monitoramento_em_tempo_real()

        elif escolha == '0':
            break

        else:
            print("\nOpção inválida! Tente novamente.\n")

    print("\nServiço encerrado. Obrigado por usar o sistema Sentinela.")


executar()

cnx.commit()
print(mycursor.rowcount, "record inserted.")
cnx.close()