import requests
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# 🔐 Pegando o token do .env
API_URL = "https://api.agendor.com.br/v3/deals"
API_TOKEN = f"Token {os.getenv('API_TOKEN')}"

# 📅 Parâmetros de filtros
ano_atual = datetime.now().year
mes_atual = datetime.now().month
primeiro_dia_ano = datetime(ano_atual, 1, 1).strftime('%Y-%m-%dT00:00:00Z')
ultimo_dia_ano = datetime(ano_atual, 12, 31).strftime('%Y-%m-%dT23:59:59Z')

params_ganhos = {
    'page': 1,
    'per_page': 100,
    'dealStatus': 2,  # Ganhos
    'endAtGt': primeiro_dia_ano,
    'endAtLt': ultimo_dia_ano
}

params_prospeccao = {
    'dealStatus': 1,
    'startAtGt': primeiro_dia_ano,
    'dealStageOrder': 1
}

params_quentes = {
    'dealStatus': 1,
    'startAtGt': primeiro_dia_ano,
    'dealStageOrder': 5
}

# 🧠 Mapeamento de meses
meses = {
    1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
    5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
    9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
}

# 📥 Função para buscar dados de negócios
def fetch_deal_data(url, token, params):
    all_data = []
    current_page = 1

    while True:
        params['page'] = current_page
        try:
            response = requests.get(url, headers={'Authorization': token}, params=params)
            data = response.json().get('data', [])
            if not data:
                break
            all_data.extend(data)
            current_page += 1
        except Exception as e:
            print(f"Erro ao buscar dados: {e}")
            break

    result = [{
        'ID': registro['id'],
        'Valor do Negócio': registro['value'],
        'EtapaId': registro['dealStage']['id'],
        'Etapa': registro['dealStage']['name'],
        'Funil': registro['dealStage']['funnel']['name'],
        'Status': registro['dealStatus']['name'],
        'ConsultorId': registro['owner']['id'],
        'Consultor': registro['owner']['name'],
        'Data Final': registro.get('endTime', None),
        'Data Ganho': registro.get('wonAt', None),
    } for registro in all_data]

    return result

# 📊 Função para contar registros com base no filtro
def fetch_deal_meta(url, token, params):
    response = requests.get(url, headers={'Authorization': token}, params=params)
    data = response.json().get('meta', {})
    return data.get('totalCount', 0)
