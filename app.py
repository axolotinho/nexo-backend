from flask import Flask, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from supabase import create_client
import uuid
import os
app = Flask(__name__)

CORS(app)

jwt = JWTManager(app)

# ==============================
# CONFIGURAÇÃO DO BANCO SUPABASE
# ==============================

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config["JWT_SECRET_KEY"] = os.getenv("JWT_KEY")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

db = SQLAlchemy(app)


# ==============================
# MODEL
# ==============================

from datetime import time

class Usuario(db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(100), nullable=False)
    cpf = db.Column(db.String(14), nullable=False, unique=True)
    email = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)
    cargo = db.Column(db.String(20), nullable=False)

    foto = db.Column(db.String(255))
    idade = db.Column(db.Integer)
    hora_entrada = db.Column(db.Time)
    hora_saida = db.Column(db.Time)

    def to_dict(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "cpf": self.cpf,
            "email": self.email,
            "cargo": self.cargo,
            "foto": self.foto,
            "idade": self.idade,
            "hora_entrada": self.hora_entrada.strftime("%H:%M") if self.hora_entrada else None,
            "hora_saida": self.hora_saida.strftime("%H:%M") if self.hora_saida else None,
        }


class Kanban(db.Model):
    __tablename__ = "kanban"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    color = db.Column(db.String(100), nullable=False)

    cards = db.relationship(
        "Card",
        backref="kanban",
        lazy=True,
        cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color,
        }


# Relação muitos-para-muitos entre Card e Usuario
card_responsavel = db.Table(
    "card_responsavel",
    db.Column(
        "card_id",
        db.Integer,
        db.ForeignKey("card.id"),
        primary_key=True
    ),
    db.Column(
        "usuario_id",
        db.Integer,
        db.ForeignKey("usuarios.id"),
        primary_key=True
    )
)


class Card(db.Model):
    __tablename__ = "card"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    progress = db.Column(db.Integer, nullable=False, default=0)

    # Prazo
    due_date = db.Column(db.DateTime)

    # Níveis de 1 a 5
    difficulty = db.Column(db.Integer, nullable=False, default=1)
    workload = db.Column(db.Integer, nullable=False, default=1)

    # URLs das imagens e arquivos
    images = db.Column(db.ARRAY(db.String), nullable=False, default=list)
    files = db.Column(db.ARRAY(db.String), nullable=False, default=list)

    # Data de criação
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Quem criou
    created_by_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id"),
        nullable=False
    )

    created_by = db.relationship(
        "Usuario",
        foreign_keys=[created_by_id]
    )

    # Responsáveis
    responsaveis = db.relationship(
        "Usuario",
        secondary=card_responsavel,
        backref=db.backref("cards", lazy=True)
    )

    # Coluna do Kanban
    kanban_id = db.Column(
        db.Integer,
        db.ForeignKey("kanban.id"),
        nullable=False
    )

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "progress": self.progress,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "difficulty": self.difficulty,
            "workload": self.workload,
            "images": self.images,
            "files": self.files,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by.to_dict() if self.created_by else None,
            "responsaveis": [usuario.to_dict() for usuario in self.responsaveis],
            "kanban_id": self.kanban_id,
        }

# ==============================
# FUNÇÕES
# ==============================

def upload_foto_supabase(foto):
    nome_arquivo = f"{uuid.uuid4()}-{foto.filename}"

    # .read() lê os bytes do arquivo enviado pelo Flask
    arquivo_bytes = foto.read()

    # Faz o upload enviando os bytes brutos
    supabase.storage.from_("usuarios").upload(
        file=arquivo_bytes,
        path=nome_arquivo,
        file_options={
            "content-type": foto.content_type
        }
    )

    # Retorna a URL pública
    url_data = supabase.storage.from_("usuarios").get_public_url(nome_arquivo)

    return url_data

# ==============================
# ROTAS
# ==============================



@app.route("/create-user", methods=["POST"])
def create_user():

    nome = request.form["nome"]
    cpf = request.form["cpf"]
    email = request.form["email"]
    senha = request.form["password"]
    cargo = request.form["cargo"]
    idade = request.form["idade"]
    hora_entrada = request.form["hora_entrada"]
    hora_saida = request.form["hora_saida"]

    foto = request.files.get("foto")


    # verifica se já existe
    if Usuario.query.filter(
        (Usuario.cpf == cpf) |
        (Usuario.email == email)
    ).first():

        return {
            "erro": "Usuário já existe."
        }, 400


    foto_url = None

    if foto:
        foto_url = upload_foto_supabase(foto)



    usuario = Usuario(

        nome=nome,

        cpf=cpf,

        email=email,

        password=generate_password_hash(senha),

        cargo=cargo,

        idade=idade,

        hora_entrada=hora_entrada,

        hora_saida=hora_saida,

        foto=foto_url

    )


    db.session.add(usuario)

    db.session.commit()


    return {
        "mensagem": "Usuário criado com sucesso!"
    }, 201

@app.route("/login", methods=["POST"])
def login():
    dados = request.json
    print(f"DEBUG LOGIN - Dados recebidos: {dados}") # Verifique se chegou tudo certo

    identificador = dados.get("duq")
    senha = dados.get("password")
    cargo = dados.get("cargo")

    # Busca o usuário
    user = Usuario.query.filter(
        (Usuario.email == identificador) |
        (Usuario.cpf == identificador)
    ).first()

    if not user:
        print("DEBUG LOGIN FALHOU: Usuário não encontrado no banco com este email/CPF.")
        return {"erro": "Falha na autenticação"}, 401

    senha_valida = check_password_hash(user.password, senha)
    if not senha_valida:
        print("DEBUG LOGIN FALHOU: Senha incorreta.")
        return {"erro": "Falha na autenticação"}, 401

    if user.cargo != cargo:
        print(f"DEBUG LOGIN FALHOU: Cargo incorreto. Banco: '{user.cargo}' | Recebido: '{cargo}'")
        return {"erro": "Falha na autenticação"}, 401

    # Se passou por tudo, gera o token
    token = create_access_token(
        identity=str(user.id),
        additional_claims={
            "nome": user.nome,
            "cargo": user.cargo,
            "foto": user.foto
        }
    )

    return {"token": token}, 200

@app.route("/kanban", methods=["GET"])
def get_kanban():
    kanbans = Kanban.query.all()
    return [k.to_dict() for k in kanbans]


@app.route("/card", methods=["GET"])
def get_card():
    cards = Card.query.all()
    return [c.to_dict() for c in cards]

# ==============================
# INICIAR APP
# ==============================

with app.app_context():
    db.create_all()


if __name__ == "__main__":

    app.run(debug=True)
