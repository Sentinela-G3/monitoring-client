📊 Sistema de Monitoramento Sentinela
Python
MySQL
License

O Sentinela é um sistema avançado de monitoramento de hardware e software que coleta métricas em tempo real e armazena em banco de dados MySQL para análise contínua.

📋 Pré-requisitos
Python 3.8+

MySQL Server 5.7+

Acesso administrativo (para instalação de dependências)

🛠️ Instalação
Clone o repositório:

bash
git clone https://github.com/seu-usuario/sentinela-monitoring.git
cd sentinela-monitoring
Instale as dependências:

bash
pip install -r requirements.txt
⚙️ Configuração
Banco de Dados
Crie um arquivo .env na raiz do projeto:

ini
AMBIENTE=local  # ou "producao" para ambiente de produção
Edite as configurações no arquivo nova-api.py:

python
CONFIG = {
    "local": {
        "host": "127.0.0.1",
        "port": 3306,
        "user": "seu_usuario",
        "password": "sua_senha",
        "database": "sentinela_db"
    },
    "producao": {
        "host": "servidor-producao",
        "port": 3306,
        "user": "usuario_prod",
        "password": "senha_segura",
        "database": "sentinela_prod"
    }
}
⚠️ Importante: Nunca commit credenciais no repositório!

🚀 Execução
bash
python nova-api.py
✨ Funcionalidades
✅ Monitoramento em tempo real de:

CPU, RAM e Disco

Atividade de rede

Temperatura e frequência

Uptime do sistema

🔍 Identificação automática de hardware

📈 Armazenamento histórico de métricas

🖥️ Interface de console intuitiva

🗃️ Estrutura do Banco
Certifique-se de ter as tabelas:

maquina (cadastro de equipamentos)

componente (configuração de métricas)

historico (dados coletados)


Abra um Pull Request

📄 Licença
Distribuído sob licença MIT. Veja LICENSE para mais informações.

