from flask import Flask, render_template, request, redirect, session, jsonify
from flask_bootstrap import Bootstrap
from models import db, Consultor, Propaganda, Campanha, OrigemDados, Cota, Meta
from dotenv import load_dotenv
from utils_agendor import (
    fetch_deal_data,
    fetch_deal_meta,
    fetch_tasks,
    params_ganhos,
    params_prospeccao,
    params_quentes,
    API_BASE_URL,
    API_URL,
    API_TOKEN,
    meses
)
from dateutil import parser
from collections import defaultdict
from datetime import datetime, time, date, timedelta
from flask import flash, has_app_context
from sqlalchemy import func, or_
import os, base64, calendar, unicodedata, hashlib, json, threading

EXCLUDED_CONSULTOR_IDS = {'640301'}
EXCLUDED_COTA_CONSULTORES = {2}

_dashboard_cache = {'dados': None, 'last_update': None}
_dashboard_cache_lock = threading.Lock()
_dashboard_stop_event = threading.Event()
_dashboard_thread = None

load_dotenv()

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_segura'
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True
}

# Inicialização
Bootstrap(app)
db.init_app(app)

@app.context_processor
def inject_current_year():
    return {'current_year': datetime.now().year}

def format_valor(valor):
    if valor >= 1_000_000:
        return f"{valor/1_000_000:.1f}M"
    elif valor >= 1_000:
        return f"{valor/1_000:.0f}K"
    return f"{valor:.0f}"
app.jinja_env.filters['format_valor'] = format_valor


def parse_dt_safe(s):
    if not s or (isinstance(s, str) and not s.strip()):
        return None
    try:
        from dateutil import parser as _p
        return _p.parse(s)
    except Exception:
        return None


def data_negocio(negocio):
    if not negocio:
        return None
    return parse_dt_safe(negocio.get('Data Ganho') or negocio.get('Data Final') or negocio.get('endTime') or negocio.get('end_time'))


def negocio_excluido(negocio):
    if not negocio:
        return False
    consultor_id = negocio.get('ConsultorId')
    return consultor_id is not None and str(consultor_id) in EXCLUDED_CONSULTOR_IDS


def data_no_intervalo(data_ref, inicio, fim):
    if not data_ref:
        return False
    data_base = data_ref.date() if isinstance(data_ref, datetime) else data_ref
    return inicio <= data_base <= fim


def gerar_semanas_periodo(inicio, fim):
    semanas = []
    atual = inicio
    while atual <= fim:
        semana_inicio = atual
        semana_fim = min(semana_inicio + timedelta(days=6 - semana_inicio.weekday()), fim)
        label = f"{semana_inicio.strftime('%d/%m')} - {semana_fim.strftime('%d/%m')}"
        semanas.append({
            'inicio': semana_inicio,
            'fim': semana_fim,
            'label': label
        })
        atual = semana_fim + timedelta(days=1)
    return semanas


def normalize_task_type(tipo):
    if not tipo:
        return ''
    if not isinstance(tipo, str):
        tipo = str(tipo)
    normalized = unicodedata.normalize('NFKD', tipo)
    normalized = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
    return normalized.strip().upper()


def ensure_datetime(value, end=False):
    if value is None:
        return None
    if isinstance(value, str):
        value = parser.parse(value)
    if isinstance(value, datetime):
        if end:
            return value.replace(hour=23, minute=59, second=59, microsecond=999999)
        return value
    return datetime.combine(value, time.max if end else time.min)


def ensure_date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return parser.parse(value).date()
        except Exception:
            return None
    return value


def total_cotas(ano=None, inicio=None, fim=None, campo='valor_total', exclude_consultores=None):
    coluna = getattr(Cota, campo, Cota.valor_total)
    query = db.session.query(func.coalesce(func.sum(coluna), 0))
    if ano is not None:
        query = query.filter(func.extract('year', Cota.data_aquisicao) == ano)
    if inicio is not None:
        query = query.filter(Cota.data_aquisicao >= inicio)
    if fim is not None:
        query = query.filter(Cota.data_aquisicao <= fim)
    if exclude_consultores:
        query = query.filter(~Cota.consultor_id.in_(tuple(exclude_consultores)))
    total = query.scalar()
    return float(total or 0)


def obter_meta_vigente(inicio=None, fim=None):
    inicio_date = ensure_date(inicio)
    fim_date = ensure_date(fim)

    if inicio_date is None and fim_date is None:
        hoje = datetime.now().date()
        inicio_date = hoje
        fim_date = hoje
    elif inicio_date is None:
        inicio_date = fim_date
    elif fim_date is None:
        fim_date = inicio_date

    query = Meta.query.filter(Meta.data_inicio <= fim_date)
    query = query.filter(or_(Meta.data_fim.is_(None), Meta.data_fim >= inicio_date))
    meta = query.order_by(Meta.data_inicio.desc()).first()
    if meta and meta.valor is not None:
        return float(meta.valor)
    return None

def calcular_progresso_campanha():
    campanha = Campanha.query.first()
    if not campanha:
        return 0, '', 'secondary', None, None

    inicio = campanha.data_inicio
    fim = campanha.data_fim
    origem = campanha.origem
    meta = obter_meta_vigente(inicio, fim)
    if meta is None:
        meta = campanha.meta

    # Garantir que as datas da campanha estejam no tipo date
    if isinstance(inicio, str):
        inicio = parser.parse(inicio).date()
    if isinstance(fim, str):
        fim = parser.parse(fim).date()

    valor_total = 0
    ano_atual = datetime.now().year

    if origem.value.strip().upper() == 'AGENDOR':
        ganhos = fetch_deal_data(params_ganhos)
        ganhos_periodo = []
        for g in ganhos:
            data_ref = data_negocio(g)
            if data_ref and inicio <= data_ref.date() <= fim:
                ganhos_periodo.append(g)
        valor_total = sum(g['Valor do Negócio'] for g in ganhos_periodo)

    elif origem.value.strip().upper() == 'COTAS':
        inicio_dt = ensure_datetime(inicio)
        fim_dt = ensure_datetime(fim, end=True)
        try:
            valor_total = total_cotas(
                ano=ano_atual,
                inicio=inicio_dt,
                fim=fim_dt
            )
        except Exception as e:
            print(f"⚠️ Erro ao consultar cotas no banco: {e}")
            valor_total = 0

    porcentagem = (valor_total * 100) / meta if meta else 0
    cor = 'danger' if porcentagem < 30 else 'warning' if porcentagem < 70 else 'success'
    texto = f"{porcentagem:.2f}%" if porcentagem >= 5 else ""

    return porcentagem, texto, cor, valor_total, meta

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and request.form['senha'] == 'admin123':
        session['logado'] = True
        return redirect('/home')
    return render_template('login.html')

@app.route('/home')
def home():
    if not session.get('logado'):
        return redirect('/')
    return render_template('home.html')

def update_progress(ganhos, mes_atual, ano_atual):
    df_mes_atual = []
    for g in ganhos:
        data_ref = data_negocio(g)
        if data_ref and data_ref.month == mes_atual and data_ref.year == ano_atual:
            df_mes_atual.append(g)
    valor_total_mes_atual = sum(g['Valor do Negócio'] for g in df_mes_atual)
    ultimo_dia = calendar.monthrange(ano_atual, mes_atual)[1]
    inicio_mes = date(ano_atual, mes_atual, 1)
    fim_mes = date(ano_atual, mes_atual, ultimo_dia)
    meta = obter_meta_vigente(inicio_mes, fim_mes) or 0
    porcentagem = (valor_total_mes_atual * 100) / meta if meta else 0
    cor = 'danger' if porcentagem < 30 else 'warning' if porcentagem < 70 else 'success'
    texto = f"{porcentagem:.2f}%" if porcentagem >= 5 else ""
    return porcentagem, texto, cor


def obter_dashboard_tarefas_dados():
    hoje = datetime.now().date()
    inicio_mes = hoje.replace(day=1)
    ultimo_dia = calendar.monthrange(hoje.year, hoje.month)[1]
    fim_mes = date(hoje.year, hoje.month, ultimo_dia)
    inicio_mes_dt = ensure_datetime(inicio_mes)
    fim_mes_dt = ensure_datetime(fim_mes, end=True)

    due_inicio = datetime.combine(inicio_mes, time.min).strftime('%Y-%m-%dT%H:%M:%SZ')
    due_fim = datetime.combine(fim_mes + timedelta(days=1), time.min).strftime('%Y-%m-%dT%H:%M:%SZ')
    params_tarefas = {
        'per_page': 100,
        'updatedDateGt': due_inicio,
        'updatedDateLt': due_fim,
        'createdDateGt': due_inicio,
        'createdDateLt': due_fim
    }
    tarefas = fetch_tasks(params_tarefas)

    total_visitas = 0
    total_reunioes = 0
    for tarefa in tarefas:
        data_tarefa = parse_dt_safe(tarefa.get('Data') or tarefa.get('FinalizadaEm'))
        if not data_tarefa:
            continue
        if not data_no_intervalo(data_tarefa, inicio_mes, fim_mes):
            continue
        if tarefa.get('Concluida'):
            continue
        tipo = normalize_task_type(tarefa.get('Tipo'))
        if tipo == 'VISITA':
            total_visitas += 1
        elif tipo == 'REUNIAO':
            total_reunioes += 1

    params_deals = dict(params_ganhos)
    params_deals['since'] = inicio_mes.isoformat()
    ganhos = fetch_deal_data(params_deals)
    ganhos_mes = []
    for g in ganhos:
        if data_no_intervalo(data_negocio(g), inicio_mes, fim_mes):
            ganhos_mes.append(g)

    meta_periodo = obter_meta_vigente(inicio_mes, fim_mes) or 0
    semanas = gerar_semanas_periodo(inicio_mes, fim_mes)
    meta_por_semana = meta_periodo / len(semanas) if semanas and meta_periodo else 0
    serie_semanal = []
    acumulado_real = 0
    acumulado_meta = 0
    total_liquido = 0
    for semana in semanas:
        inicio_semana_dt = ensure_datetime(semana['inicio'])
        fim_semana_dt = ensure_datetime(semana['fim'], end=True)
        valor_semana = total_cotas(
            inicio=inicio_semana_dt,
            fim=fim_semana_dt,
            campo='valor',
            exclude_consultores=EXCLUDED_COTA_CONSULTORES
        )
        total_liquido += valor_semana
        acumulado_real += valor_semana
        acumulado_meta += meta_por_semana
        serie_semanal.append({
            'label': semana['label'],
            'realizado': round(acumulado_real, 2),
            'meta': round(acumulado_meta, 2)
        })

    ranking_query = (
        db.session.query(
            Cota.consultor_id,
            func.coalesce(func.sum(Cota.valor), 0).label('total')
        )
        .filter(Cota.data_aquisicao >= inicio_mes_dt)
        .filter(Cota.data_aquisicao <= fim_mes_dt)
    )
    if EXCLUDED_COTA_CONSULTORES:
        ranking_query = ranking_query.filter(~Cota.consultor_id.in_(tuple(EXCLUDED_COTA_CONSULTORES)))
    ranking_raw = ranking_query.group_by(Cota.consultor_id).all()
    consultor_ids = [row.consultor_id for row in ranking_raw if row.consultor_id]
    consultores = {}
    if consultor_ids:
        consultores = {c.id: c for c in Consultor.query.filter(Consultor.id.in_(consultor_ids)).all()}

    ranking = []
    for pos, row in enumerate(sorted(ranking_raw, key=lambda r: float(r.total or 0), reverse=True), start=1):
        if row.consultor_id is None:
            nome = 'Sem consultor'
            imagem = None
        else:
            consultor = consultores.get(row.consultor_id)
            nome = consultor.nome if consultor else f'Consultor #{row.consultor_id}'
            imagem = consultor.imagem_base64 if consultor and consultor.imagem_base64 else None
        ranking.append({
            'posicao': pos,
            'nome': nome,
            'valor': float(row.total or 0),
            'imagem': imagem
        })

    dados = {
        'periodo_label': f"{inicio_mes.strftime('%d/%m/%Y')} - {fim_mes.strftime('%d/%m/%Y')}",
        'total_visitas': total_visitas,
        'total_reunioes': total_reunioes,
        'negocios_ganhos': len(ganhos_mes),
        'meta_periodo': round(meta_periodo, 2),
        'valor_total_liquido': round(total_liquido, 2),
        'serie_semanal': serie_semanal,
        'ranking': ranking,
        'total_tarefas': len(tarefas),
        'last_updated': datetime.now().isoformat()
    }
    dados['signature'] = hashlib.md5(json.dumps(dados, sort_keys=True, default=str).encode()).hexdigest()
    return dados


def atualizar_cache_dashboard():
    ctx = None
    if not has_app_context():
        ctx = app.app_context()
        ctx.push()
    try:
        dados = obter_dashboard_tarefas_dados()
        with _dashboard_cache_lock:
            _dashboard_cache['dados'] = dados
            _dashboard_cache['last_update'] = datetime.utcnow().isoformat()
    except Exception as e:
        print(f"⚠️ Falha ao atualizar cache do dashboard: {e}")
    finally:
        if ctx is not None:
            ctx.pop()


def obter_dashboard_cache():
    with _dashboard_cache_lock:
        dados = _dashboard_cache.get('dados')
    if dados is None:
        dados = obter_dashboard_tarefas_dados()
        with _dashboard_cache_lock:
            _dashboard_cache['dados'] = dados
    return dados


def _dashboard_updater_loop(intervalo=600):
    while not _dashboard_stop_event.is_set():
        atualizar_cache_dashboard()
        if _dashboard_stop_event.wait(intervalo):
            break

@app.route('/analytics')
def analytics():
    if not session.get('logado'):
        return redirect('/')

    ganhos_brutos = sorted(fetch_deal_data(params_ganhos), key=lambda x: x['Valor do Negócio'], reverse=True)
    prospeccao = fetch_deal_meta(params_prospeccao)
    quentes = fetch_deal_meta(params_quentes)

    ano_atual = datetime.now().year
    mes_atual = datetime.now().month
    nome_mes = meses[mes_atual]
    inicio_ano = date(ano_atual, 1, 1)
    fim_ano = date(ano_atual, 12, 31)

    ganhos_ano = []
    for ganho in ganhos_brutos:
        data_ref = data_negocio(ganho)
        if data_no_intervalo(data_ref, inicio_ano, fim_ano):
            ganhos_ano.append((ganho, data_ref))

    ganhos = [g for g, _ in ganhos_ano]

    try:
        vendas_cotas = total_cotas(ano=ano_atual)
    except Exception as e:
        print(f"⚠️ Erro ao consultar cotas no banco: {e}")
        vendas_cotas = 0

    ganhos_mes = [
        g for g, data_ref in ganhos_ano
        if data_ref.month == mes_atual and data_ref.year == ano_atual
    ]
    vendas_anuais = sum(g['Valor do Negócio'] for g, _ in ganhos_ano)
    vendas_mes = sum(g['Valor do Negócio'] for g in ganhos_mes)
    print(f"Vendas anuais: {ganhos_ano}, Vendas mês: {vendas_mes}, Vendas cotas: {vendas_cotas}")

    ganhos_mes_com_data = [g for g in ganhos_mes if data_negocio(g)]
    ultima = max(ganhos_mes_com_data, key=lambda g: data_negocio(g), default=None)
    ultima_consultora = None
    if ultima:
        data_ultima = data_negocio(ultima)
        consultor = Consultor.query.filter_by(id_agendor=str(ultima['ConsultorId'])).first()
        ultima_consultora = {
            'nome': ultima['Consultor'],
            'valor': ultima['Valor do Negócio'],
            'data': data_ultima.strftime('%d/%m/%Y') if data_ultima else '',
            'imagem_base64': consultor.imagem_base64 if consultor else None
        }

    porcentagem_churras, texto_churras, cor_churras = update_progress(ganhos, mes_atual, ano_atual)
    porcentagem_campanha, texto_campanha, cor_campanha, valor_atual, meta_campanha = calcular_progresso_campanha()

    agregado = defaultdict(lambda: {'nome': None, 'total': 0})
    for g in ganhos_mes:
        cid = g['ConsultorId']
        agregado[cid]['nome'] = g['Consultor']
        agregado[cid]['total'] += g['Valor do Negócio']

    ranking_raw = sorted([
        {'ConsultorId': cid, **info} for cid, info in agregado.items()
    ], key=lambda x: x['total'], reverse=True)[:3]

    ranking = []
    for item in ranking_raw:
        consultor = Consultor.query.filter_by(id_agendor=str(item['ConsultorId'])).first()
        ranking.append({
            'nome': item['nome'],
            'total': item['total'],
            'imagem_base64': consultor.imagem_base64 if consultor and consultor.imagem_base64 else None
        })

    propagandas_ativas = Propaganda.query.filter_by(ativo=True).all()

    return render_template('analytics.html',
                           propagandas=propagandas_ativas,
                           vendas_anuais=vendas_anuais,
                           vendas_cotas=vendas_cotas,
                           vendas_mes=vendas_mes,
                           porcentagem_churras=porcentagem_churras,
                           texto_churras=texto_churras,
                           cor_churras=cor_churras,
                           nome_mes=nome_mes,
                           ultima_consultora=ultima_consultora,
                           prospeccao=prospeccao,
                           quentes=quentes,
                           ranking=ranking,
                           valor_atual=valor_atual,
                           meta_campanha=meta_campanha,
                           campanha_ativa=Campanha.query.filter_by(ativo=True).first(),
                           porcentagem_campanha=porcentagem_campanha,
                           texto_campanha=texto_campanha,
                           cor_campanha=cor_campanha)

@app.route('/dashboard-tarefas')
def dashboard_tarefas():
    if not session.get('logado'):
        return redirect('/')

    dados = obter_dashboard_cache()
    return render_template('dashboard_tarefas.html', dados=dados)


@app.route('/api/dashboard-tarefas')
def api_dashboard_tarefas():
    if not session.get('logado'):
        return jsonify({'error': 'unauthorized'}), 401
    dados = obter_dashboard_cache()
    return jsonify(dados)

@app.route('/verificar-novas-vendas')
def verificar_novas_vendas():
    ganhos = fetch_deal_data(params_ganhos)
    mes_atual = datetime.now().month
    ano_atual = datetime.now().year

    ganhos_mes = [g for g in ganhos if g['Data Final'] and parser.parse(g['Data Final']).month == mes_atual and parser.parse(g['Data Final']).year == ano_atual]
    ganhos_mes_com_ganho = [g for g in ganhos_mes if parse_dt_safe(g.get('Data Ganho'))]
    ultima = max(ganhos_mes_com_ganho, key=lambda g: parse_dt_safe(g['Data Ganho']), default=None)
    if not ultima:
        return jsonify({'temNovaVenda': False})

    data_ultima_venda = parser.parse(ultima['Data Ganho']).strftime('%Y-%m-%d %H:%M:%S')
    if data_ultima_venda != session.get('ultima_venda_registrada'):
        session['ultima_venda_registrada'] = data_ultima_venda
        return jsonify({'temNovaVenda': True})

    return jsonify({'temNovaVenda': False})


@app.route('/logout')
def logout():
    session.pop('logado', None)
    return redirect('/')

@app.route('/propagandas', methods=['GET', 'POST'])
def propagandas():
    if request.method == 'POST':
        titulo = request.form['titulo']
        ativo = 'ativo' in request.form
        imagem = request.files['imagem']
        imagem_base64 = base64.b64encode(imagem.read()).decode('utf-8') if imagem else None

        nova = Propaganda(titulo=titulo, imagem_base64=imagem_base64, ativo=ativo)
        db.session.add(nova)
        db.session.commit()
        return redirect('/propagandas')

    propagandas = Propaganda.query.order_by(Propaganda.id.desc()).all()
    return render_template('propagandas.html', propagandas=propagandas)

@app.route('/propaganda/toggle/<int:id>', methods=['POST'])
def toggle_propaganda(id):
    propaganda = Propaganda.query.get_or_404(id)
    propaganda.ativo = not propaganda.ativo
    db.session.commit()
    return redirect('/propagandas')

@app.route('/propaganda/deletar/<int:id>', methods=['POST'])
def deletar_propaganda(id):
    propaganda = Propaganda.query.get_or_404(id)
    db.session.delete(propaganda)
    db.session.commit()
    return redirect('/propagandas')

@app.route('/consultores')
def consultores():
    consultores = Consultor.query.all()
    return render_template('consultores.html', consultores=consultores)

@app.route('/consultor/toggle/<int:id>', methods=['POST'])
def toggle_consultor(id):
    consultor = Consultor.query.get_or_404(id)
    consultor.ativo = not consultor.ativo
    db.session.commit()
    return redirect('/consultores')

@app.route('/consultor/deletar/<int:id>', methods=['POST'])
def deletar_consultor(id):
    consultor = Consultor.query.get_or_404(id)
    db.session.delete(consultor)
    db.session.commit()
    return redirect('/consultores')

@app.route('/consultor/editar/<int:id>', methods=['GET', 'POST'])
def editarConsultor(id):
    consultor = Consultor.query.get_or_404(id)
    if request.method == 'POST':
        consultor.nome = request.form['nome']
        consultor.id_agendor = request.form['id_agendor']
        consultor.ativo = 'ativo' in request.form

        imagem = request.files.get('imagem')
        if imagem and imagem.filename != '':
            consultor.imagem_base64 = base64.b64encode(imagem.read()).decode('utf-8')

        db.session.commit()
        return redirect('/consultores')
    return render_template('edit.html', consultor=consultor)

@app.route('/consultor/novo', methods=['POST'])
def novoConsultor():
    nome = request.form['nome']
    id_agendor = request.form['id_agendor']
    ativo = 'ativo' in request.form

    imagem = request.files['imagem']
    if imagem:
        imagem_base64 = base64.b64encode(imagem.read()).decode('utf-8')
    else:
        imagem_base64 = None

    consultor = Consultor(nome=nome, id_agendor=id_agendor, imagem_base64=imagem_base64, ativo=ativo)
    db.session.add(consultor)
    db.session.commit()
    return redirect('/consultores')

@app.route('/campanhas', methods=['GET', 'POST'])
def campanhas():
    if not session.get('logado'):
        return redirect('/')

    if request.method == 'POST':
        campanha_id = request.form.get('campanha_id')
        nome = request.form['nome']
        data_inicio = datetime.strptime(request.form['data_inicio'], '%Y-%m-%d').date()
        data_fim = datetime.strptime(request.form['data_fim'], '%Y-%m-%d').date()
        meta_valor = obter_meta_vigente(data_inicio, data_fim)
        if meta_valor is None:
            flash("Nenhuma meta encontrada para o período informado. A meta será considerada como 0.", "warning")
            meta_valor = 0
        origem = OrigemDados[request.form['origem']]
        ativo = 'ativo' in request.form

        if campanha_id:
            # Atualizar campanha existente
            campanha = Campanha.query.get_or_404(int(campanha_id))
            campanha.nome = nome
            campanha.data_inicio = data_inicio
            campanha.data_fim = data_fim
            campanha.meta = meta_valor
            campanha.origem = origem
            campanha.ativo = ativo
            flash("Campanha atualizada com sucesso.")
        else:
            # Criar nova campanha
            nova = Campanha(
                nome=nome,
                data_inicio=data_inicio,
                data_fim=data_fim,
                meta=meta_valor,
                origem=origem,
                ativo=ativo
            )
            db.session.add(nova)
            flash("Campanha criada com sucesso.")

        db.session.commit()
        return redirect('/campanhas')

    campanhas = Campanha.query.order_by(Campanha.data_inicio.desc()).all()
    meta_padrao = obter_meta_vigente()
    return render_template('campanhas.html', campanhas=campanhas, meta_padrao=meta_padrao)

@app.route('/campanha/editar/<int:id>', methods=['GET'])
def editar_campanha(id):
    if not session.get('logado'):
        return redirect('/')

    campanha_edit = Campanha.query.get_or_404(id)
    campanhas = Campanha.query.order_by(Campanha.data_inicio.desc()).all()
    meta_padrao = obter_meta_vigente(campanha_edit.data_inicio, campanha_edit.data_fim)
    return render_template('campanhas.html', campanha_edit=campanha_edit, campanhas=campanhas, meta_padrao=meta_padrao)

@app.route('/campanha/toggle/<int:id>', methods=['POST'])
def toggle_campanha(id):
    campanha = Campanha.query.get_or_404(id)
    campanha.ativo = not campanha.ativo
    db.session.commit()
    return redirect('/campanhas')

@app.before_request
def iniciar_atualizador_dashboard():
    global _dashboard_thread
    if _dashboard_thread is None:
        _dashboard_thread = threading.Thread(
            target=_dashboard_updater_loop,
            args=(600,),
            daemon=True
        )
        _dashboard_thread.start()

if __name__ == '__main__':
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            print(f"⚠️ Não foi possível criar/verificar tabelas: {e}")
    iniciar_atualizador_dashboard()
    app.run(host='0.0.0.0', port=8182, debug=False)
