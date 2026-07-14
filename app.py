from flask import Flask, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token
from werkzeug.security import generate_password_hash, check_password_hash
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

db = SQLAlchemy(app)


# ==============================
# MODEL
# ==============================

class Usuario(db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    duq = db.Column(db.String(100), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)
    cargo = db.Column(db.String(20), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "duq": self.duq,
            "password": self.password,
            "cargo": self.cargo,
        }

class Kanban(db.Model):
    __tablename__ = "kanban"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    color = db.Column(db.String(100), nullable=False)

    cards = db.relationship("Card", backref="kanban", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color,
        }

class Card(db.Model):
    __tablename__ = "card"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(100), nullable=False)
    progress = db.Column(db.Integer, nullable=False)
    responsavel = db.Column(db.String(100), nullable=False)

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
            "responsavel": self.responsavel,
            "kanban_id": self.kanban_id,
        }

# ==============================
# ROTAS
# ==============================

@app.route("/create-user")
def form():

    return """
    <form method="POST">

        <input name="duq" placeholder="Email ou CPF">

        <input name="password" placeholder="Senha">

        <select name="cargo">
            <option value="G">Gestor</option>
            <option value="F">Funcionário</option>
        </select>

        <button>Criar</button>

    </form>
    """

@app.route("/create-user", methods=["POST"])
def create_user():

    duq = request.form["duq"]
    senha = request.form["password"]
    cargo = request.form["cargo"]

    if Usuario.query.filter_by(duq=duq).first():
        return "Usuário já existe."

    usuario = Usuario(
        duq=duq,
        password=generate_password_hash(senha),
        cargo=cargo
    )

    db.session.add(usuario)
    db.session.commit()

    return "Usuário criado com sucesso!"

@app.route("/login", methods=["POST"])
def login():

    dados = request.json

    duq = dados["duq"]
    senha = dados["password"]
    cargo = dados["cargo"]

    user = Usuario.query.filter_by(duq=duq).first()

    if user and check_password_hash(user.password, senha) and user.cargo == cargo:

        token = create_access_token(
            identity=user.id
        )

        return {
            "token": token
        }, 200


    return {
        "erro": "Falha na autenticação"
    }, 401

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

    if Kanban.query.count() == 0:
        kanbans = [
            Kanban(name="A Fazer", color="#780000"),
            Kanban(name="Em Andamento", color="#fdf0d5"),
            Kanban(name="Concluído", color="#669bbc")
        ]

        db.session.add_all(kanbans)
        db.session.commit()


if __name__ == "__main__":

    app.run(debug=True)
