import mysql.connector
import psutil
import platform
import time
import subprocess
from datetime import datetime

# Conexão com o banco de dados
cnx = mysql.connector.connect(
    host = "127.0.0.1",
    user = "root",
    password = "1964",
    database = "sentinela"
)

mycursor = cnx.cursor()


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
processador = platform.processor()
# Arquitetura do sistema (32 bits ou 64 bits)
arquitetura = platform.machine()
# Nome do sistema operacional
sistema_operacional = platform.system()
# Versão do sistema operacional
versao_sistema = platform.version()
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
    print("Identificamos o modelo do sistema operacional da sua maquina {}".format(sistema_operacional))
    # Por enquanto só de windows
    print("Identificamos o número serial da sua maquina {}".format(serial_number))
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
    val = (modelo_maquina, sistema_operacional, serial_number, status, setor, 1)
    mycursor.execute(sql,val)
    cnx.commit()
    # cnx.close()

    print("Vamos cadastrar os componentes da máquina...")


    def identificar_componente():
        componentes = []

        componentes.append({
            "tipo": "CPU",
            "modelo": processador,
            "minimo": 10.0,
            "maximo": 40.0
        })
        componentes.append({
            "tipo": "RAM",
            "modelo": "DDR4",
            "minimo": 10.0,
            "maximo": 70.0
        })
        componentes.append({
            "tipo": "DISK",
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
    print("\nIniciando monitoramento em tempo real...")
    print("Coletando dados de monitoramento...")
    while True:
        # Porcentagem de uso da CPU nos últimos 1 segundo
        cpu_porcentagem = psutil.cpu_percent(interval=1)
        # Porcentagem de memória RAM atualmente em uso
        memoria_porcentagem = psutil.virtual_memory().percent
        # Porcentagem de espaço utilizado no disco principal
        disco_percentagem = psutil.disk_usage('/').percent
        # Dados de tráfego de rede  
        rede = psutil.net_io_counters()
        # Quantidade total de bytes enviados pela rede desde a inicialização do sistema
        bytes_enviados = rede.bytes_sent  
        # Quantidade total de bytes recebidos pela rede desde a inicialização do sistema
        bytes_recebidos = rede.bytes_recv  
        # Número total de pacotes enviados pela rede desde a inicialização do sistema
        pacotes_enviados = rede.packets_sent  
        # Número total de pacotes recebidos pela rede desde a inicialização do sistema
        pacotes_recebidos = rede.packets_recv  

        print("=========================================================================")
        print("Dados de monitoramento")
        print("Uso da CPU: {:.2f}%".format(cpu_porcentagem))
        print("Uso da Memória RAM: {:.2f}%".format(memoria_porcentagem))
        print("Uso do Disco: {:.2f}%".format(disco_percentagem))
        print("Total de bytes enviados pela rede: {} bytes".format(bytes_enviados))
        print("Total de bytes recebidos pela rede: {} bytes".format(bytes_recebidos))
        print("Total de pacotes enviados pela rede: {}".format(pacotes_enviados))
        print("Total de pacotes recebidos pela rede: {}".format(pacotes_recebidos))
        print("=========================================================================")


        sql = "SELECT * FROM maquina"


        # Armazenado no histórico e alertas
        dataCaptura = datetime.now()
        valor = 18
        fkComponete = 1

        
        sql = "INSERT INTO historico (data_captura, valor, fk_historico_componente) VALUES (%s,%s,%s)"
        val = (dataCaptura, valor, fkComponete)

        # if componente < minimo or componente > maximo:
            # sql = "INSERT INTO alerta (data_captura, valor, fk_alerta_componente) VALUES (%s,%s,%s)"
            # val = (dataCaptura, valor, fkComponete)
        

        mycursor.execute(sql,val)
        cnx.commit()

        time.sleep(1)

def encerrar_servico():
    print("\nServiço encerrado. Obrigado por usar o sistema da InnovaAir.")
    exit()


def executar():
    inicio = menu_inicial()

    if inicio == 'y':
        nome = coleta_nome_usuario()
        escolha = escolha_usuario(nome)

        if escolha == '1':
            menu_informacoes_maquina()
            
            encerrar_servico()
        elif escolha == '2':
            cadastrar_maquina()
            # menu_inicial()
            # encerrar_servico()

        elif escolha == '3':
            monitoramento_em_tempo_real()

        elif escolha == '0':
            encerrar_servico()

        else:
            print("\nOpção inválida! O serviço será encerrado.")
            encerrar_servico()
    else:
        encerrar_servico()

executar()

cnx.commit()
print(mycursor.rowcount, "record inserted.")
cnx.close()