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

nucleos_logicos = psutil.cpu_count(logical=True)
nucleos_fisicos = psutil.cpu_count(logical=False)
cpu_frequencia = psutil.cpu_freq().max / 1000
memoria_total = psutil.virtual_memory().total / (1024 ** 3)
disco_total = psutil.disk_usage('/').total / (1024 ** 3)
processador = cpuinfo.get_cpu_info()['brand_raw']
arquitetura = platform.machine()
sistema_operacional = platform.system()
versao_sistema = platform.version()
sistema_detalhado = platform.platform()
output = subprocess.check_output("wmic bios get serialnumber").decode().split("\n")
serial_number = output[1].strip()


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
    print("\nEstamos prontos para começar!")
    inicio = input('Digite "S" para iniciar o monitoramento ou qualquer outra tecla para encerrar: ').strip().lower()
    if inicio != "s":
        encerrar_servico()

def escolha_usuario():
    print_linha()
    print("\nComo podemos ajudar você hoje?")
    escolha = input("""
        1. Consultar informações da máquina
        2. Registrar nova máquina no sistema
        3. Iniciar monitoramento em tempo real
        0. Encerrar o sistema
                    
    Selecione uma opção (1, 2, 3 ou 0): """).strip()


    return escolha

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

def cadastrar_maquina():
    print_linha()
    modelo_maquina = input("Informe o modelo da máquina: ").strip()
    print_linha()
    setor = input("Informe o setor da máquina: ").strip()
    print_linha()
    print("Sistema operacional detectado: {}".format(sistema_detalhado))
    
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

    print("Número de série detectado: {}".format(get_serial()))
    print_linha()
    print("\nDEFINA O STATUS ATUAL DA MÁQUINA:")
    status = input("""
        1. ATIVO
        2. INATIVO
        0. CANCELAR

    Digite a opção correspondente (1, 2 ou 0): """).strip()

    print_linha()
    print("INICIANDO CADASTRO DA MÁQUINA...")
    sql = "INSERT INTO maquina (modelo, so, serial_number, status, setor, fk_maquina_empresa) VALUES (%s, %s, %s, %s, %s, %s)"
    val = (modelo_maquina, sistema_detalhado, serial_number, status, setor, 1)
    mycursor.execute(sql,val)
    cnx.commit()
    print_linha()
    print("INICIANDO CADASTRO DOS COMPONENTES DA MÁQUINA...")
    # desc_cpu = cpuinfo.get_cpu_info()['brand_raw']
    # print(desc_cpu)
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
        sql = "INSERT INTO componente (tipo, modelo, minimo, maximo, fk_componente_maquina) VALUES (%s,%s,%s,%s,%s)"
        val = (i["tipo"],i["modelo"],i["minimo"],i["maximo"], 1)
        mycursor.execute(sql,val)
    cnx.commit()

    if voltar_ao_menu_ou_encerrar():
        executar()


def monitoramento_em_tempo_real():
    print_linha()
    escolher_maquina = input("Qual máquina você deseja monitorar? (Digite o ID da máquina): ").strip()
    sql = "SELECT id_maquina, modelo, so, serial_number, status, setor FROM maquina WHERE id_maquina = %s"
    val = (escolher_maquina, )
    mycursor.execute(sql,val)

    maquina_escolhida = mycursor.fetchone()
    if maquina_escolhida:
        print_linha()
        print("Máquina encontrada:")
        status_maquina = "Ativo" if maquina_escolhida['status'] == 1 else "Inativo"
        print(f"ID: {maquina_escolhida['id_maquina']}")
        print(f"Modelo: {maquina_escolhida['modelo']}")
        print(f"Sistema operacional: {maquina_escolhida['so']}")
        print(f"Número de série: {maquina_escolhida['serial_number']}")
        print(f"Status: {status_maquina}")
        print(f"Setor: {maquina_escolhida['setor']}")

    else:
        print_linha()
        print("Nenhuma máquina encontrada com esse ID.")
        return

    cnx.commit()

    print_linha()
    prog_monitoracao = input("Deseja prosseguir com a monitoração? (Digite 'S' para iniciar a monitoração ou qualquer outra tecla para voltar ao menu): ").strip().lower()

    if prog_monitoracao == "s":
        print_linha()
        print("\nIniciando monitoramento em tempo real...")
    else:
        return
        
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
                print("[ERRO] Tipo '{}' não está mapeado nas funções.".format(tipo))

        time.sleep(5)



def executar():
    menu_inicial()
    
    while True:
        escolha = escolha_usuario()

        if escolha == '1':
            menu_informacoes_maquina()

        elif escolha == '2':
            cadastrar_maquina()

        elif escolha == '3':
            monitoramento_em_tempo_real()

        elif escolha == '0':
            break

        else:
            print_linha()
            print("\nOpção inválida! Tente novamente.\n")
            
    print_linha()
    print("\nServiço encerrado. Obrigado por usar o sistema Sentinela.")

            
    print_linha()
    print("\nServiço encerrado. Obrigado por usar o sistema Sentinela.")


executar()
cnx.commit()
# print(mycursor.rowcount, "record inserted.")
cnx.close()