from flask import Flask, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
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
    password = db.Column(db.Integer, nullable=False)
    cargo = db.Column(db.Integer, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "duq": self.duq,
            "password": self.password,
            "cargo": self.cargo,
        }


# ==============================
# ROTAS
# ==============================

from flask_jwt_extended import create_access_token

@app.route("/login", methods=["POST"])
def login():

    dados = request.json

    duq = dados["duq"]
    senha = dados["password"]
    cargo = dados["cargo"]

    user = Usuario.query.filter_by(duq=duq).first()

    if user and user.password == senha and user.cargo == cargo:

        token = create_access_token(
            identity=user.id
        )

        return {
            "token": token
        }, 200


    return {
        "erro": "Falha na autenticação"
    }, 401


# ==============================
# INICIAR APP
# ==============================

if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    app.run(debug=True)