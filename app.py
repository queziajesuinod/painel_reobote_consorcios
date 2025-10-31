from flask import Flask, render_template, request, redirect, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap
from models import db, Consultor, Propaganda, Campanha, OrigemDados
from dotenv import load_dotenv
from conectar_cotas import conectar_cotas
from utils_agendor import fetch_deal_data, fetch_deal_meta, params_ganhos, params_prospeccao, params_quentes, API_URL, API_TOKEN, meses
from dateutil import parser
from collections import defaultdict
from datetime import datetime
from flask import flash
import os, base64
import pandas as pd


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


def converter_data_brasileira(data_str):
    if not data_str or str(data_str).strip() == '':
        return None  # ou pd.NaT, se quiser manter no padrão do pandas
    try:
        return datetime.strptime(data_str, "%d/%m/%Y").date()
    except:
        try:
            return parser.parse(data_str).date()
        except:
            return None

def calcular_progresso_campanha():
    campanha = Campanha.query.first()
    if not campanha:
        return 0, '', 'secondary', None, None

    inicio = campanha.data_inicio
    fim = campanha.data_fim
    origem = campanha.origem
    meta = campanha.meta

    # Garantir que as datas da campanha estejam no tipo date
    if isinstance(inicio, str):
        inicio = parser.parse(inicio).date()
    if isinstance(fim, str):
        fim = parser.parse(fim).date()

    valor_total = 0
    ano_atual = datetime.now().year

    if origem.value.strip().upper() == 'AGENDOR':
        ganhos = fetch_deal_data(API_URL, API_TOKEN, params_ganhos)
        def data_agendor_valida(data_str):
            try:
                data = parser.parse(data_str).date()
                return inicio <= data <= fim
            except:
                return False
        ganhos_periodo = [
            g for g in ganhos if g.get('Data Final') and data_agendor_valida(g['Data Final'])
        ]
        valor_total = sum(g['Valor do Negócio'] for g in ganhos_periodo)

    elif origem.value.strip().upper() == 'COTAS':
        try:
            cotas = conectar_cotas()

            # Caso retorne None, substitui por DataFrame vazio
            if cotas is None or not hasattr(cotas, "columns"):
                print("⚠️ conectar_cotas() retornou None ou objeto inválido — criando DataFrame vazio.")
                cotas = pd.DataFrame(columns=['ANO', 'VALOR TOTAL'])

            # Garante que a coluna ANO existe
            if 'ANO' not in cotas.columns:
                cotas['ANO'] = 0

            # Garante que VALOR TOTAL exista para evitar erro no .sum()
            if 'VALOR TOTAL' not in cotas.columns:
                cotas['VALOR TOTAL'] = 0

        except Exception as e:
            print(f"⚠️ Erro ao conectar cotas: {e}")
            cotas = pd.DataFrame(columns=['ANO', 'DATA', 'VALOR TOTAL'])
        cotas['DATA'] = cotas['DATA'].apply(converter_data_brasileira)
        cotas = cotas[cotas['DATA'].notna()]  # Remove datas inválidas
        cotas = cotas[cotas['ANO'] == ano_atual] 
      
        valor_total = cotas[
            (cotas['DATA'] >= inicio) & (cotas['DATA'] <= fim)
        ]['VALOR TOTAL'].sum()
        print(valor_total)

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
    df_mes_atual = [g for g in ganhos if g['Data Final'] and parser.parse(g['Data Final']).month == mes_atual and parser.parse(g['Data Final']).year == ano_atual]
    valor_total_mes_atual = sum(g['Valor do Negócio'] for g in df_mes_atual)
    meta = 26000000
    porcentagem = (valor_total_mes_atual * 100) / meta if meta else 0
    cor = 'danger' if porcentagem < 30 else 'warning' if porcentagem < 70 else 'success'
    texto = f"{porcentagem:.2f}%" if porcentagem >= 5 else ""
    return porcentagem, texto, cor

@app.route('/analytics')
def analytics():
    if not session.get('logado'):
        return redirect('/')

    try:
        cotas = conectar_cotas()

        # Caso retorne None, substitui por DataFrame vazio
        if cotas is None or not hasattr(cotas, "columns"):
            print("⚠️ conectar_cotas() retornou None ou objeto inválido — criando DataFrame vazio.")
            cotas = pd.DataFrame(columns=['ANO', 'VALOR TOTAL'])

        # Garante que a coluna ANO existe
        if 'ANO' not in cotas.columns:
            cotas['ANO'] = 0

        # Garante que VALOR TOTAL exista para evitar erro no .sum()
        if 'VALOR TOTAL' not in cotas.columns:
            cotas['VALOR TOTAL'] = 0

    except Exception as e:
        print(f"⚠️ Erro ao conectar cotas: {e}")
        cotas = pd.DataFrame(columns=['ANO', 'VALOR TOTAL'])

    ganhos = sorted(fetch_deal_data(API_URL, API_TOKEN, params_ganhos), key=lambda x: x['Valor do Negócio'], reverse=True)
    prospeccao = fetch_deal_meta(API_URL, API_TOKEN, params_prospeccao)
    quentes = fetch_deal_meta(API_URL, API_TOKEN, params_quentes)

    ano_atual = datetime.now().year
    mes_atual = datetime.now().month
    nome_mes = meses[mes_atual]

    ganhos_mes = [g for g in ganhos if g['Data Final'] and parser.parse(g['Data Final']).month == mes_atual and parser.parse(g['Data Final']).year == ano_atual]
    vendas_anuais = sum(g['Valor do Negócio'] for g in ganhos)
    vendas_cotas = cotas[cotas['ANO'] == ano_atual]['VALOR TOTAL'].sum()
    vendas_mes = sum(g['Valor do Negócio'] for g in ganhos_mes)

    ganhos_mes_com_ganho = [g for g in ganhos_mes if parse_dt_safe(g.get('Data Ganho'))]
    ultima = max(ganhos_mes_com_ganho, key=lambda g: parse_dt_safe(g['Data Ganho']), default=None)
    ultima_consultora = None
    if ultima:
        consultor = Consultor.query.filter_by(id_agendor=str(ultima['ConsultorId'])).first()
        ultima_consultora = {
            'nome': ultima['Consultor'],
            'valor': ultima['Valor do Negócio'],
            'data': parser.parse(ultima['Data Ganho']).strftime('%d/%m/%Y'),
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

@app.route('/verificar-novas-vendas')
def verificar_novas_vendas():
    ganhos = fetch_deal_data(API_URL, API_TOKEN, params_ganhos)
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
        data_inicio = datetime.strptime(request.form['data_inicio'], '%Y-%m-%d')
        data_fim = datetime.strptime(request.form['data_fim'], '%Y-%m-%d')
        meta = float(request.form['meta'])
        origem = OrigemDados[request.form['origem']]
        ativo = 'ativo' in request.form

        if campanha_id:
            # Atualizar campanha existente
            campanha = Campanha.query.get_or_404(int(campanha_id))
            campanha.nome = nome
            campanha.data_inicio = data_inicio
            campanha.data_fim = data_fim
            campanha.meta = meta
            campanha.origem = origem
            campanha.ativo = ativo
            flash("Campanha atualizada com sucesso.")
        else:
            # Criar nova campanha
            nova = Campanha(
                nome=nome,
                data_inicio=data_inicio,
                data_fim=data_fim,
                meta=meta,
                origem=origem,
                ativo=ativo
            )
            db.session.add(nova)
            flash("Campanha criada com sucesso.")

        db.session.commit()
        return redirect('/campanhas')

    campanhas = Campanha.query.order_by(Campanha.data_inicio.desc()).all()
    return render_template('campanhas.html', campanhas=campanhas)

@app.route('/campanha/editar/<int:id>', methods=['GET'])
def editar_campanha(id):
    if not session.get('logado'):
        return redirect('/')

    campanha_edit = Campanha.query.get_or_404(id)
    campanhas = Campanha.query.order_by(Campanha.data_inicio.desc()).all()
    return render_template('campanhas.html', campanha_edit=campanha_edit, campanhas=campanhas)

@app.route('/campanha/toggle/<int:id>', methods=['POST'])
def toggle_campanha(id):
    campanha = Campanha.query.get_or_404(id)
    campanha.ativo = not campanha.ativo
    db.session.commit()
    return redirect('/campanhas')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=8182, debug=False)