from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import UUID
import enum

db = SQLAlchemy()


class OrigemDados(enum.Enum):
    AGENDOR = "Agendor"
    COTAS = "Cotas"

class Campanha(db.Model):
    __tablename__ = 'campanhas_vendas'
    __table_args__ = {'schema': 'dev'}  
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    data_inicio = db.Column(db.Date, nullable=False)
    data_fim = db.Column(db.Date, nullable=False)
    meta = db.Column(db.Float, nullable=False)
    origem = db.Column(db.Enum(OrigemDados), nullable=False)
    ativo = db.Column(db.Boolean, default=True)


class Consultor(db.Model):
    __tablename__ = 'consultores'
    __table_args__ = {'schema': 'dev'}  
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    id_agendor = db.Column(db.String(50), nullable=False)
    imagem_base64 = db.Column(db.Text, nullable=True)
    ativo = db.Column(db.Boolean, default=True)

class Propaganda(db.Model):
    __tablename__ = 'propagandas'
    __table_args__ = {'schema': 'dev'}  
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), nullable=False)
    imagem_base64 = db.Column(db.Text, nullable=True)
    ativo = db.Column(db.Boolean, default=True)


class Cota(db.Model):
    __tablename__ = 'cotas'
    __table_args__ = {'schema': 'dev'}

    id = db.Column(UUID(as_uuid=True), primary_key=True)
    grupo = db.Column(db.String(255), nullable=False)
    cota = db.Column(db.String(255), nullable=True)
    valor = db.Column(db.Numeric, nullable=True)
    valor_total = db.Column('valorTotal', db.Numeric, nullable=True)
    data_aquisicao = db.Column('dtaquisicao', db.DateTime(timezone=True), nullable=False)
    cliente_id = db.Column('clienteId', UUID(as_uuid=True), nullable=True)
    consultor_id = db.Column('consultorId', db.Integer, nullable=True)
    id_agendor = db.Column('idagendor', db.String(255), nullable=True)
    administradora = db.Column(db.String(255), nullable=False)
    created_at = db.Column('createdAt', db.DateTime(timezone=True), nullable=False)
    updated_at = db.Column('updatedAt', db.DateTime(timezone=True), nullable=False)
    digito = db.Column(db.String(5), nullable=True)
    consultor_legado = db.Column('consultorLegado', db.String(255), nullable=True)


class Meta(db.Model):
    __tablename__ = 'metas'
    __table_args__ = {'schema': 'dev'}

    id = db.Column(UUID(as_uuid=True), primary_key=True)
    descricao = db.Column(db.String(255), nullable=True)
    valor = db.Column(db.Numeric(15, 2), nullable=False)
    data_inicio = db.Column('dataInicio', db.Date, nullable=False)
    data_fim = db.Column('dataFim', db.Date, nullable=True)
    created_at = db.Column('createdAt', db.DateTime(timezone=True), nullable=False)
    updated_at = db.Column('updatedAt', db.DateTime(timezone=True), nullable=False)
