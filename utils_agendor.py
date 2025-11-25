import os
import time
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = "https://api.agendor.com.br/v3"
API_URL = f"{API_BASE_URL}/deals"
API_TOKEN = os.getenv("API_TOKEN") or ""
API_AUTH_HEADER = {"Authorization": f"Token {API_TOKEN}"}

# Parâmetros de filtros
ano_atual = datetime.now().year
mes_atual = datetime.now().month
primeiro_dia_ano = datetime(ano_atual, 1, 1).strftime("%Y-%m-%d")
ultimo_dia_ano = datetime(ano_atual, 12, 31).strftime("%Y-%m-%d")

params_ganhos = {
    "page": 1,
    "per_page": 100,
    "dealStatus": 2,  # Ganhos
    "since": primeiro_dia_ano,
}

params_prospeccao = {
    "dealStatus": 1,
    "startAtGt": primeiro_dia_ano,
    "dealStageOrder": 1,
}

params_quentes = {
    "dealStatus": 1,
    "startAtGt": primeiro_dia_ano,
    "dealStageOrder": 5,
}

meses = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}


def fetch_deal_data(params):
    """
    Busca negócios com paginação simples usando /deals/stream.
    """
    all_data = []
    current_page = 1
    base_params = dict(params or {})
    url = f"{API_URL}/stream"

    while True:
        query_params = {**base_params, "page": current_page}
        try:
            response = requests.get(url, headers=API_AUTH_HEADER, params=query_params, timeout=20)
            if response.status_code == 429:
                print("⚠️ API Agendor (deals) retornou 429, aguardando 1s...")
                time.sleep(1)
                continue
            if response.status_code != 200:
                print(f"❌ Erro da API Agendor (deals): {response.status_code} | {response.text}")
                break

            data = response.json()
            registros = data.get("data") or []
            if not registros:
                break

            for registro in registros:
                owner = registro.get("owner") or {}
                deal_stage = registro.get("dealStage") or {}
                funnel = deal_stage.get("funnel") or {}
                deal_status = registro.get("dealStatus") or {}

                all_data.append(
                    {
                        "ID": registro.get("id"),
                        "Valor do Negócio": registro.get("value", 0) or 0,
                        "EtapaId": deal_stage.get("id"),
                        "Etapa": deal_stage.get("name"),
                        "Funil": funnel.get("name"),
                        "Status": deal_status.get("name"),
                        "ConsultorId": owner.get("id") if isinstance(owner, dict) else None,
                        "Consultor": owner.get("name", "Sem consultor") if isinstance(owner, dict) else "Sem consultor",
                        "Data Final": registro.get("endTime"),
                        "Data Ganho": registro.get("wonAt"),
                    }
                )

            print(f"ℹ️ {len(registros)} negócios carregados (página {current_page})")

            links = data.get("links") or {}
            meta = data.get("meta") or {}
            has_next = bool(links.get("next")) or bool(meta.get("hasNextPage"))
            if not has_next:
                break

            current_page += 1
            time.sleep(0.2)

        except Exception as exc:  # pragma: no cover - log defensivo
            print(f"❌ Erro ao buscar negócios: {exc}")
            break

    return all_data


def _normalize_assigned_user(assigned_users, user):
    """
    Retorna (id, nome) do consultor associado à tarefa.
    Prioriza assignedUsers (lista ou dict) e cai para user se vazio.
    """
    if isinstance(assigned_users, list) and assigned_users:
        assigned = assigned_users[0]
    elif isinstance(assigned_users, dict):
        assigned = assigned_users
    else:
        assigned = {}

    user_dict = user if isinstance(user, dict) else {}
    consultor_id = assigned.get("id") or user_dict.get("id")
    consultor_nome = assigned.get("name") or user_dict.get("name")
    return consultor_id, consultor_nome


def fetch_tasks(params):
    """
    Busca tarefas com paginação controlada (page/per_page) e filtros dinâmicos,
    espelhando o fluxo do exemplo em Node.
    """
    all_tasks = []
    base_params = dict(params or {})
    per_page = int(base_params.pop("per_page", 100) or 100)
    page = 1

    while True:
        query_params = {"page": page, "per_page": per_page, **base_params}

        try:
            response = requests.get(
                f"{API_BASE_URL}/tasks",
                headers={**API_AUTH_HEADER, "Content-Type": "application/json"},
                params=query_params,
                timeout=20,
            )

            if response.status_code == 429:
                print("⚠️ API Agendor (tasks) retornou 429, aguardando 0.4s...")
                time.sleep(0.4)
                continue

            if response.status_code != 200:
                print(f"❌ Erro da API Agendor (tasks): {response.status_code} | {response.text}")
                break

            data = response.json()
            registros = data.get("data") or []

            for registro in registros:
                consultor_id, consultor_nome = _normalize_assigned_user(
                    registro.get("assignedUsers"),
                    registro.get("user"),
                )
                task_type = (registro.get("type") or "").upper()

                all_tasks.append(
                    {
                        "ID": registro.get("id"),
                        "Tipo": task_type,
                        "Titulo": registro.get("text") or registro.get("title") or "",
                        "Data": registro.get("dueDate") or registro.get("datetime") or registro.get("date"),
                        "FinalizadaEm": registro.get("finishedAt"),
                        "Concluida": bool(registro.get("finishedAt")),
                        "DealId": (registro.get("deal") or {}).get("id"),
                        "ConsultorId": consultor_id,
                        "Consultor": consultor_nome or "Desconhecido",
                    }
                )

            print(f"ℹ️ {len(registros)} tarefas carregadas (página {page})")

            if len(registros) < per_page:
                break

            page += 1
            time.sleep(0.4)

        except Exception as exc:  # pragma: no cover - log defensivo
            print(f"❌ Erro ao buscar tarefas: {exc}")
            break

    return all_tasks


def fetch_deal_meta(params):
    response = requests.get(API_URL, headers=API_AUTH_HEADER, params=params)
    data = response.json().get("meta", {})
    return data.get("totalCount", 0)
