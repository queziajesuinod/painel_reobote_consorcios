import os
import threading
import time
from queue import Queue
from datetime import datetime
from email.utils import parsedate_to_datetime

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter

load_dotenv()

API_BASE_URL = "https://api.agendor.com.br/v3"
API_URL = f"{API_BASE_URL}/deals"
API_TOKEN = os.getenv("API_TOKEN") or ""
API_AUTH_HEADER = {"Authorization": f"Token {API_TOKEN}"}


def _parse_retry_after(value):
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        try:
            retry_date = parsedate_to_datetime(value)
            delta = (retry_date - datetime.utcnow()).total_seconds()
            return max(delta, 0)
        except Exception:
            return None


class RateLimiter:
    def __init__(self, rate_per_second=3):
        self._interval = 1.0 / rate_per_second
        self._lock = threading.Lock()
        self._last_call = 0.0
        self._blocked_until = 0.0

    def wait_for_slot(self):
        with self._lock:
            now = time.monotonic()
            if now < self._blocked_until:
                time.sleep(self._blocked_until - now)
                now = time.monotonic()
            next_allowed = self._last_call + self._interval
            if now < next_allowed:
                time.sleep(next_allowed - now)
                now = time.monotonic()
            self._last_call = now

    def block_for(self, delay):
        if delay <= 0:
            return
        with self._lock:
            now = time.monotonic()
            blocked_until = now + delay
            if blocked_until > self._blocked_until:
                self._blocked_until = blocked_until


class _QueuedRequest:
    def __init__(self, method, url, kwargs):
        self.method = method
        self.url = url
        self.kwargs = kwargs
        self.response = None
        self.done = threading.Event()


class AgendorAPIClient:
    def __init__(self, rate_per_second=3, max_connections=4, max_retries=6):
        self._session = requests.Session()
        adapter = HTTPAdapter(pool_connections=max_connections, pool_maxsize=max_connections, pool_block=True)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

        self._rate_limiter = RateLimiter(rate_per_second=rate_per_second)
        self._max_retries = max_retries
        self._queue = Queue()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def request(self, method, url, **kwargs):
        item = _QueuedRequest(method, url, kwargs)
        self._queue.put(item)
        item.done.wait()
        return item.response

    def _run(self):
        while True:
            item = self._queue.get()
            try:
                item.response = self._send_with_retries(item.method, item.url, **item.kwargs)
            except Exception as exc:
                print(f"[Agendor] erro no worker de requests: {exc}")
                item.response = None
            finally:
                item.done.set()
                self._queue.task_done()

    def _send_with_retries(self, method, url, **kwargs):
        backoff = 0.6
        max_backoff = 8
        attempt = 0

        while attempt < self._max_retries:
            attempt += 1
            self._rate_limiter.wait_for_slot()
            try:
                response = self._session.request(method, url, **kwargs)
            except requests.RequestException as exc:
                print(f"[Agendor] tentativa {attempt} falhou: {exc}")
                if attempt >= self._max_retries:
                    return None
                time.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)
                continue

            if response.status_code == 429:
                retry_delay = _parse_retry_after(response.headers.get("Retry-After"))
                delay = retry_delay if retry_delay is not None else backoff
                delay = max(delay, backoff)
                print(f"[Agendor] 429 recebido, aguardando {delay:.1f}s (tentativa {attempt})")
                self._rate_limiter.block_for(delay)
                time.sleep(delay)
                backoff = min(backoff * 2, max_backoff)
                continue

            if 500 <= response.status_code < 600:
                print(f"[Agendor] {response.status_code} recebido, tentando novamente (tentativa {attempt})")
                time.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)
                continue

            return response

        print("[Agendor] excedido limite de tentativas")
        return None


AGENDOR_CLIENT = AgendorAPIClient(rate_per_second=3, max_connections=4, max_retries=6)

ano_atual = datetime.now().year
mes_atual = datetime.now().month
primeiro_dia_ano = datetime(ano_atual, 1, 1).strftime("%Y-%m-%d")
ultimo_dia_ano = datetime(ano_atual, 12, 31).strftime("%Y-%m-%d")

params_ganhos = {
    "page": 1,
    "per_page": 100,
    "dealStatus": 2,
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
    3: "Marco",
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
    """Busca negocios com paginacao simples usando /deals/stream."""
    all_data = []
    current_page = 1
    base_params = dict(params or {})
    url = f"{API_URL}/stream"

    while True:
        query_params = {**base_params, "page": current_page, "per_page": 100}
        response = AGENDOR_CLIENT.request("GET", url, headers=API_AUTH_HEADER, params=query_params, timeout=20)
        if not response:
            break

        if response.status_code != 200:
            print(f"Erro da API Agendor (deals): {response.status_code} | {response.text}")
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

            all_data.append({
                    "ID": registro.get("id"),
                    "Valor do Negócio": registro.get("value", 0) or 0,
                    "EtapaId": deal_stage.get("id"),
                    "Etapa": deal_stage.get("name"),
                    "Funil": funnel.get("name"),
                    "Status": deal_status.get("name"),
                    "ConsultorId": owner.get("id") if isinstance(owner, dict) else None,
                    "Consultor": owner.get("name", "Sem consultor") if isinstance(owner, dict) else "Sem consultor",
                    "Data Final": registro.get("endTime"),
                    "Data Ganho": registro.get("endTime"),
                    "Nome": registro.get("name") or registro.get("title") or (registro.get("deal") or {}).get("name") or f"Negócio #{registro.get('id')}",
                })

        print(f"[deals] {len(registros)} registros carregados (pagina {current_page})")

        links = data.get("links") or {}
        meta = data.get("meta") or {}
        has_next = bool(links.get("next")) or bool(meta.get("hasNextPage"))
        if not has_next:
            break

        current_page += 1
        time.sleep(0.2)

    return all_data


def _normalize_assigned_user(assigned_users, user):
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
    """Busca tarefas com paginacao controlada e filtros dinamicos."""
    all_tasks = []
    base_params = dict(params or {})
    per_page = min(100, max(1, int(base_params.pop("per_page", 100) or 100)))
    page = 1

    while True:
        query_params = {"page": page, "per_page": per_page, **base_params}
        response = AGENDOR_CLIENT.request(
            "GET",
            f"{API_BASE_URL}/tasks",
            headers={**API_AUTH_HEADER, "Content-Type": "application/json"},
            params=query_params,
            timeout=20,
        )
        if not response:
            break

        if response.status_code != 200:
            print(f"Erro da API Agendor (tasks): {response.status_code} | {response.text}")
            break

        data = response.json()
        registros = data.get("data") or []

        for registro in registros:
            consultor_id, consultor_nome = _normalize_assigned_user(
                registro.get("assignedUsers"),
                registro.get("user"),
            )
            task_type = (registro.get("type") or "").upper()

            all_tasks.append({
                "ID": registro.get("id"),
                "Tipo": task_type,
                "Titulo": registro.get("text") or registro.get("title") or "",
                "Data": registro.get("dueDate") or registro.get("datetime") or registro.get("date"),
                "FinalizadaEm": registro.get("finishedAt"),
                "Concluida": bool(registro.get("finishedAt")),
                "DealId": (registro.get("deal") or {}).get("id"),
                "ConsultorId": consultor_id,
                "Consultor": consultor_nome or "Desconhecido",
            })

        print(f"[tasks] {len(registros)} tarefas carregadas (pagina {page})")

        links = data.get("links") or {}
        meta = data.get("meta") or {}
        has_next = bool(links.get("next")) or bool(meta.get("hasNextPage"))
        if not has_next:
            break

        page += 1
        time.sleep(0.4)

    return all_tasks


def fetch_deal_meta(params):
    response = AGENDOR_CLIENT.request("GET", API_URL, headers=API_AUTH_HEADER, params=params, timeout=20)
    if not response or response.status_code != 200:
        status = response.status_code if response else "sem resposta"
        print(f"Erro da API Agendor (meta): {status}")
        return 0
    data = response.json().get("meta", {})
    return data.get("totalCount", 0)
