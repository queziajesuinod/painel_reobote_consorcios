from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Enum
import enum

db = SQLAlchemy()


class OrigemDados(enum.Enum):
    AGENDOR = "Agendor"
    COTAS = "Cotas"

class Campanha(db.Model):
    __tablename__ = 'campanhas_vendas'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    data_inicio = db.Column(db.Date, nullable=False)
    data_fim = db.Column(db.Date, nullable=False)
    meta = db.Column(db.Float, nullable=False)
    origem = db.Column(db.Enum(OrigemDados), nullable=False)
    ativo = db.Column(db.Boolean, default=True)


class Consultor(db.Model):
    __tablename__ = 'consultores'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    id_agendor = db.Column(db.String(50), nullable=False)
    imagem_base64 = db.Column(db.Text, nullable=True)
    ativo = db.Column(db.Boolean, default=True)

class Propaganda(db.Model):
    __tablename__ = 'propagandas'
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), nullable=False)
    imagem_base64 = db.Column(db.Text, nullable=True)
    ativo = db.Column(db.Boolean, default=True)

