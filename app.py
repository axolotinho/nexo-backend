from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import jwt_required, JWTManager, create_access_token, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, time
from supabase import create_client
from sqlalchemy.orm.attributes import flag_modified
import traceback
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

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
db = SQLAlchemy(app)


# ==============================
# MODELOS (MODIFIED)
# ==============================

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


# Tabela associativa muitos-para-muitos entre Grupo e Usuario
grupo_membro = db.Table(
    "grupo_membro",
    db.Column("grupo_id", db.Integer, db.ForeignKey("grupo.id", ondelete="CASCADE"), primary_key=True),
    db.Column("usuario_id", db.Integer, db.ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True)
)


class Grupo(db.Model):
    __tablename__ = "grupo"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    card_id = db.Column(db.Integer, db.ForeignKey("card.id", ondelete="CASCADE"), nullable=True)

    # Membros do grupo
    membros = db.relationship(
        "Usuario",
        secondary=grupo_membro,
        backref=db.backref("grupos", lazy=True)
    )

    def to_dict(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "card_id": self.card_id,
            "membros": [m.to_dict() for m in self.membros]
        }


# Modelo associativo customizado para guardar o tempo que cada usuário leva em cada card
class CardResponsavel(db.Model):
    __tablename__ = "card_responsavel"

    card_id = db.Column(db.Integer, db.ForeignKey("card.id", ondelete="CASCADE"), primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True)
    
    # Tempo gasto por este usuário específico neste card (em segundos)
    tempo_gasto = db.Column(db.Integer, nullable=False, default=0)

    # Relacionamentos auxiliares
    usuario = db.relationship("Usuario", backref=db.backref("card_associacoes", lazy=True))


class Card(db.Model):
    __tablename__ = "card"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    progress = db.Column(db.Integer, nullable=False, default=0)
    due_date = db.Column(db.DateTime)
    difficulty = db.Column(db.Integer, nullable=False, default=1)
    workload = db.Column(db.Integer, nullable=False, default=1)
    
    images = db.Column(db.ARRAY(db.String), nullable=False, default=list)
    files = db.Column(db.ARRAY(db.String), nullable=False, default=list)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    created_by_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    created_by = db.relationship("Usuario", foreign_keys=[created_by_id])

    # Relacionamento com a tabela associativa que possui os tempos gastos
    responsavel_associacoes = db.relationship(
        "CardResponsavel",
        backref="card",
        lazy=True,
        cascade="all, delete-orphan"
    )

    # Relacionamento um-para-um / um-para-muitos opcional com o Grupo criado
    grupo = db.relationship(
        "Grupo",
        backref="card",
        uselist=False,
        cascade="all, delete-orphan"
    )

    kanban_id = db.Column(db.Integer, db.ForeignKey("kanban.id"), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "progress": self.progress,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "difficulty": self.difficulty,
            "workload": self.workload,
            "images": self.images if self.images else [],
            "files": self.files if self.files else [],
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by.to_dict() if self.created_by else None,
            "responsaveis": [
                {
                    **assoc.usuario.to_dict(),
                    "tempo_gasto_segundos": assoc.tempo_gasto
                } for assoc in self.responsavel_associacoes
            ],
            "grupo": {
                "id": self.grupo.id,
                "nome": self.grupo.nome
            } if self.grupo else None,
            "kanban_id": self.kanban_id,
        }

# ==============================
# FUNÇÕES SUPABASE
# ==============================

# ==============================
# NOVO MODELO: CONTROLE DE HISTÓRICO E REQUISIÇÕES DA IA
# ==============================

class MensagemChat(db.Model):
    __tablename__ = "mensagens_chat"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    sender = db.Column(db.String(10), nullable=False) # 'user' ou 'ia'
    texto = db.Column(db.Text, nullable=False)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "sender": self.sender,
            "text": self.texto
        }


# ==============================
# NOVA ROTA: ASSISTENTE DE IA (CONVERSA COM LIMITE DE 5 ENVIOS)
# ==============================

import requests # Certifique-se de importar 'requests' no topo do seu arquivo

@app.route("/chat", methods=["POST"])
@jwt_required()
def conversar_ia():
    try:
        identity = get_jwt_identity()
        usuario_id = int(identity)
    except Exception as e:
        return {"erro": "Usuário não autenticado."}, 401

    dados = request.json
    if not dados or "message" not in dados:
        return {"erro": "A mensagem é obrigatória."}, 400

    mensagem_usuario = dados.get("message").strip()
    if not mensagem_usuario:
        return {"erro": "A mensagem não pode estar vazia."}, 400

    # 1. Verificar quantas mensagens o usuário já enviou para a IA
    envios_usuario = MensagemChat.query.filter_by(usuario_id=usuario_id, sender="user").count()

    # Se já estourou o limite de 5 mensagens enviadas pelo usuário
    if envios_usuario >= 5:
        return {
            "reply": "⚠️ Você atingiu o limite de 5 interações com a IA neste protótipo de testes. Agradecemos a sua participação e feedback para o desenvolvimento do nosso projeto de bem-estar!"
        }, 200

    # Salva a mensagem do usuário no histórico do banco de dados
    msg_user_db = MensagemChat(usuario_id=usuario_id, sender="user", texto=mensagem_usuario)
    db.session.add(msg_user_db)
    db.session.commit()

    # 2. Buscar o histórico anterior de mensagens do usuário para dar contexto à IA
    historico_db = MensagemChat.query.filter_by(usuario_id=usuario_id).order_by(MensagemChat.criado_em.asc()).all()
    
    mensagens_openai = [
        {
            "role": "system",
            "content": "Você é o Dovely, um assistente ativo focado em saúde mental, ergonomia e bem-estar corporativo. Dê respostas curtas, amigáveis, acolhedoras e diretas (no máximo 3 frases)."
        }
    ]

    for h in historico_db:
        mensagens_openai.append({
            "role": "user" if h.sender == "user" else "assistant",
            "content": h.texto
        })

    # 3. Tentar chamar a API da OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        # Se a chave não estiver configurada no seu .env do servidor, cai direto no fallback
        resposta_fallback = fallback_respostas_simuladas(mensagem_usuario)
        salvar_resposta_ia(usuario_id, resposta_fallback)
        return {"reply": resposta_fallback}, 200

    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            },
            json={
                "model": "gpt-4o-mini",
                "messages": mensagens_openai,
                "temperature": 0.7
            },
            timeout=10 # limite máximo de espera da API externa
        )

        if response.status_code != 200:
            raise Exception("Cota da API estourada ou erro no servidor da OpenAI.")

        dados_retorno = response.json()
        resposta_ia = dados_retorno["choices"][0]["message"]["content"]

    except Exception as e:
        # 4. Fallback: Se as 20 requisições globais de graça estourarem, usa respostas automáticas
        print(f"Fallback ativado devido ao erro: {str(e)}")
        resposta_ia = fallback_respostas_simuladas(mensagem_usuario)

    # Salva a resposta gerada (seja pela IA ou pelo Fallback) no banco
    salvar_resposta_ia(usuario_id, resposta_ia)
    return {"reply": resposta_ia}, 200


# ==============================
# FUNÇÕES AUXILIARES DA IA
# ==============================

def salvar_resposta_ia(usuario_id, texto):
    try:
        msg_ia_db = MensagemChat(usuario_id=usuario_id, sender="ia", texto=texto)
        db.session.add(msg_ia_db)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao salvar resposta no banco de dados: {str(e)}")


def fallback_respostas_simuladas(texto_usuario):
    msg_lower = texto_usuario.lower()
    if any(palavra in msg_lower for palavra in ["cansado", "exaurido", "sono", "cansaço"]):
        return "Parece que você está bem cansado. Recomendo fazer uma pausa agora! Vá até a janela, respire fundo 3 vezes e beba um copo de água gelada. 💧"
    elif any(palavra in msg_lower for palavra in ["foco", "concentrar", "produtividade", "concentração"]):
        return "Se precisa de foco total, inicie o timer do Método Pomodoro ali ao lado! Vou silenciar notificações imaginárias para você."
    elif any(palavra in msg_lower for palavra in ["estressado", "ansioso", "raiva", "estresse", "ansiedade"]):
        return "Se o clima pesou, pare tudo por um instante. Feche os olhos e acompanhe comigo: inspire em 4 segundos, segure por 4 e solte em 4. Você é capaz!"
    return "Estou aqui para ajudar a equilibrar sua rotina de trabalho. O que acha de fazermos uma pausa rápida para um alongamento?"



def upload_foto_supabase(foto):
    nome_arquivo = f"{uuid.uuid4()}-{foto.filename}"
    arquivo_bytes = foto.read()
    supabase.storage.from_("usuarios").upload(
        file=arquivo_bytes,
        path=nome_arquivo,
        file_options={"content-type": foto.content_type}
    )
    url_data = supabase.storage.from_("usuarios").get_public_url(nome_arquivo)
    return url_data


def upload_arquivos_supabase(arquivos, pasta_bucket="cards"):
    urls_geradas = []
    for arquivo in arquivos:
        if not arquivo or arquivo.filename == '':
            continue
        nome_arquivo = f"{uuid.uuid4()}-{arquivo.filename}"
        arquivo_bytes = arquivo.read()
        supabase.storage.from_(pasta_bucket).upload(
            file=arquivo_bytes,
            path=nome_arquivo,
            file_options={"content-type": arquivo.content_type}
        )
        url_data = supabase.storage.from_(pasta_bucket).get_public_url(nome_arquivo)
        urls_geradas.append(url_data)
    return urls_geradas


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

    if Usuario.query.filter((Usuario.cpf == cpf) | (Usuario.email == email)).first():
        return {"erro": "Usuário já existe."}, 400

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
    return {"mensagem": "Usuário criado com sucesso!"}, 201


@app.route("/login", methods=["POST"])
def login():
    dados = request.json
    identificador = dados.get("duq")
    senha = dados.get("password")
    cargo = dados.get("cargo")

    user = Usuario.query.filter((Usuario.email == identificador) | (Usuario.cpf == identificador)).first()
    if not user or not check_password_hash(user.password, senha) or user.cargo != cargo:
        return {"erro": "Falha na autenticação"}, 401

    token = create_access_token(
        identity=str(user.id),
        additional_claims={"nome": user.nome, "cargo": user.cargo, "foto": user.foto}
    )
    return {"token": token}, 200


@app.route("/usuario", methods=["GET"])
def get_usuarios():
    try:
        usuarios = Usuario.query.all()
        return [u.to_dict() for u in usuarios], 200
    except Exception as e:
        return {"erro": f"Erro ao buscar usuários: {str(e)}"}, 500


@app.route("/kanban", methods=["GET"])
def get_kanban():
    kanbans = Kanban.query.all()
    return [k.to_dict() for k in kanbans]


@app.route("/kanban", methods=["POST"])
def set_kanban():
    dados = request.json
    if not dados:
        return {"erro": "Dados não enviados."}, 400

    nome = dados.get("name")
    cor = dados.get("color")
    if not nome or not cor:
        return {"erro": "Nome e cor são campos obrigatórios."}, 400

    if Kanban.query.filter_by(name=nome).first():
        return {"erro": f"Já existe uma coluna Kanban com o nome '{nome}'."}, 400

    try:
        novo_kanban = Kanban(name=nome, color=cor)
        db.session.add(novo_kanban)
        db.session.commit()
        return novo_kanban.to_dict(), 201
    except Exception as e:
        db.session.rollback()
        return {"erro": f"Erro ao salvar no banco de dados: {str(e)}"}, 500


@app.route("/card/<int:card_id>", methods=["PATCH"])
def update_card_kanban(card_id):
    dados = request.json
    novo_kanban_id = dados.get("kanban_id")

    if not novo_kanban_id:
        return {"erro": "ID do Kanban de destino é obrigatório."}, 400

    try:
        card_existente = Card.query.get(card_id)
        if not card_existente:
            return {"erro": "Card não encontrado."}, 404

        kanban_destino = Kanban.query.get(novo_kanban_id)
        if not kanban_destino:
            return {"erro": "Coluna Kanban de destino não existe."}, 404

        card_existente.kanban_id = int(novo_kanban_id)
        db.session.commit()
        return card_existente.to_dict(), 200
    except Exception as e:
        db.session.rollback()
        return {"erro": f"Erro ao mover o card: {str(e)}"}, 500


@app.route("/kanban/<int:kanban_id>", methods=["DELETE"])
def delete_kanban(kanban_id):
    try:
        coluna = Kanban.query.get(kanban_id)
        if not coluna:
            return {"erro": "Coluna Kanban não encontrada."}, 404
        db.session.delete(coluna)
        db.session.commit()
        return {"mensagem": "Coluna excluída com sucesso!"}, 200
    except Exception as e:
        db.session.rollback()
        return {"erro": f"Erro ao deletar coluna: {str(e)}"}, 500


@app.route("/card", methods=["GET"])
def get_card():
    cards = Card.query.all()
    return [c.to_dict() for c in cards]


@app.route("/card", methods=["POST"])
def set_card():
    try:
        identity = get_jwt_identity()
        criador_id = int(identity)
    except Exception as e:
        return {"erro": f"Usuário criador inválido ou não autenticado: {str(e)}"}, 401

    title = request.form.get("title")
    description = request.form.get("description")
    kanban_id = request.form.get("kanban_id")

    if not title or not description or not kanban_id:
        return {"erro": "Título, descrição e ID do Kanban são obrigatórios."}, 400

    progress = int(request.form.get("progress", 0))
    difficulty = int(request.form.get("difficulty", 1))
    workload = int(request.form.get("workload", 1))
    due_date_str = request.form.get("due_date")

    due_date = None
    if due_date_str:
        try:
            if "T" in due_date_str:
                due_date = datetime.strptime(due_date_str.split(".")[0], "%Y-%m-%dT%H:%M:%S")
            else:
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
        except ValueError as e:
            return {"erro": f"Formato de data inválido: {str(e)}"}, 400

    responsaveis_ids = request.form.getlist("responsaveis")
    usuarios_responsaveis = []
    if responsaveis_ids:
        usuarios_responsaveis = Usuario.query.filter(Usuario.id.in_(responsaveis_ids)).all()

    imagens_enviadas = request.files.getlist("images")
    documentos_enviados = request.files.getlist("files")

    urls_imagens = []
    urls_documentos = []
    try:
        if imagens_enviadas and any(f.filename != '' for f in imagens_enviadas):
            urls_imagens = upload_arquivos_supabase(imagens_enviadas, pasta_bucket="cards")
        if documentos_enviados and any(f.filename != '' for f in documentos_enviados):
            urls_documentos = upload_arquivos_supabase(documentos_enviados, pasta_bucket="cards")
    except Exception as e:
        traceback.print_exc()
        return {"erro": f"Falha ao enviar arquivos para o Supabase: {str(e)}"}, 500

    try:
        novo_card = Card(
            title=title,
            description=description,
            progress=progress,
            due_date=due_date,
            difficulty=difficulty,
            workload=workload,
            images=urls_imagens,     
            files=urls_documentos,   
            created_by_id=criador_id,
            kanban_id=int(kanban_id)
        )
        db.session.add(novo_card)
        db.session.flush()

        for usuario in usuarios_responsaveis:
            assoc = CardResponsavel(usuario=usuario, card=novo_card, tempo_gasto=0)
            db.session.add(assoc)

        novo_grupo = Grupo(
            nome=title,
            card=novo_card,
            membros=usuarios_responsaveis
        )
        db.session.add(novo_grupo)

        db.session.commit()
        return novo_card.to_dict(), 201

    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return {"erro": f"Erro interno ao salvar o card: {str(e)}"}, 500



@app.route("/chat/historico", methods=["GET"])
def obter_historico_chat():
    try:
        identity = get_jwt_identity()
        usuario_id = int(identity)
        historico = MensagemChat.query.filter_by(usuario_id=usuario_id).order_by(MensagemChat.criado_em.asc()).all()
        
        # Se o histórico do usuário estiver vazio no banco, devolvemos a primeira de mentirinha padrão
        if not historico:
            return [{
                "id": 1,
                "sender": "ia",
                "text": "Olá! Sou o seu assistente de bem-estar. Como está se sentindo no trabalho hoje? Lembre-se de beber água!"
            }], 200

        return [h.to_dict() for h in historico], 200
    except Exception as e:
        return {"erro": f"Erro ao recuperar histórico: {str(e)}"}, 500

@app.route("/card/<int:card_id>", methods=["PUT"])
def update_card_full(card_id):
    """
    Atualiza o progresso do card e faz upload de novos anexos (acumulando-os aos antigos com segurança).
    """
    try:
        card = Card.query.get(card_id)
        if not card:
            return {"erro": "Card não encontrado."}, 404

        # 1. Atualizar campos básicos de texto se forem fornecidos no Form Data
        if "progress" in request.form:
            card.progress = int(request.form["progress"])
        if "title" in request.form:
            card.title = request.form["title"]
        if "description" in request.form:
            card.description = request.form["description"]

        # 2. Receber novos arquivos enviados do formulário do React
        novas_imagens_enviadas = request.files.getlist("images")
        novos_documentos_enviados = request.files.getlist("files")

        # 3. Fazer upload e adicionar os caminhos mantendo os antigos (Permite múltiplos anexos)
        urls_imagens_novas = []
        urls_documentos_novos = []

        if novas_imagens_enviadas and any(f.filename != '' for f in novas_imagens_enviadas):
            urls_imagens_novas = upload_arquivos_supabase(novas_imagens_enviadas, pasta_bucket="cards")
        if novos_documentos_enviados and any(f.filename != '' for f in novos_documentos_enviados):
            urls_documentos_novos = upload_arquivos_supabase(novos_documentos_enviados, pasta_bucket="cards")

        # Acumula as novas mídias tratando valores nulos/vazios com segurança
        imagens_atuais = list(card.images) if card.images else []
        arquivos_atuais = list(card.files) if card.files else []

        if urls_imagens_novas:
            card.images = imagens_atuais + urls_imagens_novas
            # Correção da linha que causou o Erro 500:
            flag_modified(card, "images") 

        if urls_documentos_novos:
            card.files = arquivos_atuais + urls_documentos_novos
            # Correção da linha que causou o Erro 500:
            flag_modified(card, "files")

        db.session.commit()
        return card.to_dict(), 200

    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return {"erro": f"Erro interno ao atualizar card: {str(e)}"}, 500


@app.route("/card/<int:card_id>", methods=["DELETE"])
def delete_card(card_id):
    """
    Exclui o card e suas relações em cascata associadas.
    """
    try:
        card = Card.query.get(card_id)
        if not card:
            return {"erro": "Card não encontrado."}, 404

        db.session.delete(card)
        db.session.commit()
        return {"mensagem": "Card excluído/arquivado com sucesso!"}, 200

    except Exception as e:
        db.session.rollback()
        return {"erro": f"Erro ao deletar card: {str(e)}"}, 500


@app.route("/card/<int:card_id>/adicionar-tempo", methods=["POST"])
def adicionar_tempo_card(card_id):
    dados = request.json
    if not dados:
        return {"erro": "Dados não enviados."}, 400

    usuario_id = dados.get("usuario_id")
    segundos = dados.get("segundos")

    if usuario_id is None or segundos is None:
        return {"erro": "Campos 'usuario_id' e 'segundos' são obrigatórios."}, 400

    try:
        associacao = CardResponsavel.query.filter_by(card_id=card_id, usuario_id=int(usuario_id)).first()
        if not associacao:
            return {"erro": "Este usuário não é responsável por este card."}, 404

        associacao.tempo_gasto += int(segundos)
        db.session.commit()

        card = Card.query.get(card_id)
        return card.to_dict(), 200

    except Exception as e:
        db.session.rollback()
        return {"erro": f"Erro ao atualizar tempo: {str(e)}"}, 500


# ==============================
# INICIAR APP
# ==============================

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
