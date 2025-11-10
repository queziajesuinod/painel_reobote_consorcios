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
primeiro_dia_ano = datetime(ano_atual, 1, 1).strftime('%Y-%m-%d')
ultimo_dia_ano = datetime(ano_atual, 12, 31).strftime('%Y-%m-%d')

params_ganhos = {
    'page': 1,
    'per_page': 100,
    'dealStatus': 2,  # Ganhos
    'since': primeiro_dia_ano
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
def fetch_deal_data(base_url, token, params):
    import requests

    all_data = []
    current_page = 1
    headers = {'Authorization': token}
    url = f"{base_url}/stream"

    while True:
        params['page'] = current_page
        try:
            response = requests.get(url, headers=headers, params=params, timeout=20)
            if response.status_code != 200:
                print(f"⚠️ Erro da API Agendor: {response.status_code} — {response.text}")
                break

            data = response.json()
            registros = data.get('data', [])
            if not registros:
                break

            for registro in registros:
                owner = registro.get('owner') or {}
                deal_stage = registro.get('dealStage') or {}
                funnel = deal_stage.get('funnel') or {}
                deal_status = registro.get('dealStatus') or {}

                all_data.append({
                    'ID': registro.get('id'),
                    'Valor do Negócio': registro.get('value', 0) or 0,
                    'EtapaId': deal_stage.get('id'),
                    'Etapa': deal_stage.get('name'),
                    'Funil': funnel.get('name'),
                    'Status': deal_status.get('name'),
                    'ConsultorId': owner.get('id') if isinstance(owner, dict) else None,
                    'Consultor': owner.get('name', 'Sem consultor') if isinstance(owner, dict) else 'Sem consultor',
                    'Data Final': registro.get('endTime'),
                    'Data Ganho': registro.get('wonAt')
                })

            current_page += 1
            print(f"✅ {len(registros)} negócios carregados com sucesso do Agendor (página {current_page - 1})")

            if not data.get('meta') or not data['meta'].get('hasNextPage'):
                break

        except Exception as e:
            print(f"❌ Erro ao buscar dados: {e}")
            break

    return all_data

# 📊 Função para contar registros com base no filtro
def fetch_deal_meta(url, token, params):
    response = requests.get(url, headers={'Authorization': token}, params=params)
    data = response.json().get('meta', {})
    return data.get('totalCount', 0)
