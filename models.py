from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

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

