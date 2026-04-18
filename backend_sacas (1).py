"""
╔══════════════════════════════════════════════════════════════════╗
║        J&T EXPRESS — CONTROLE DE SACAS  |  Backend Python       ║
║        Alinhado com painel_sacas_v2.html                        ║
╠══════════════════════════════════════════════════════════════════╣
║  INSTALAÇÃO                                                      ║
║    pip install flask flask-cors gspread google-auth              ║
║                                                                  ║
║  CONFIGURAÇÃO DO GOOGLE SHEETS                                   ║
║    1. Acesse console.cloud.google.com                            ║
║    2. Crie um projeto → ative Google Sheets API + Drive API      ║
║    3. Crie uma Service Account → baixe o JSON de credenciais     ║
║    4. Renomeie o JSON para "credenciais.json" nesta pasta        ║
║    5. Compartilhe a planilha com o e-mail da Service Account     ║
║    6. Cole o ID da planilha em SPREADSHEET_ID abaixo             ║
║                                                                  ║
║  EXECUÇÃO LOCAL                                                  ║
║    python backend_sacas.py                                       ║
║    → http://localhost:5000                                       ║
║                                                                  ║
║  DEPLOY (Render / Railway / Fly.io)                              ║
║    Suba este arquivo + credenciais.json + requirements.txt       ║
║    Variável de ambiente: PORT=10000                              ║
╚══════════════════════════════════════════════════════════════════╝

ESTRUTURA DAS ABAS NA PLANILHA GOOGLE SHEETS
─────────────────────────────────────────────
  Aba "Envios"
    ID | Base | Tipo | Destino | Sacas | TipoSaca | Chips |
    Data | Responsavel | Obs | Foto | Status | ConfPor | ConfEm

  Aba "Usuarios"
    Nome | Email | Senha | Nivel | Fixo | CriadoEm

  Aba "Devolutivas"
    Base | Tipo | Qtd | Prazo | Obs | RegistradoPor | CriadoEm

  Aba "Bases_Franquias"
    Nome | Cidade | UF

  Aba "Bases_Proprias"
    Nome | Cidade | UF

NIVEIS DE ACESSO (alinhados com o HTML)
─────────────────────────────────────────
  admin       → acesso total
  destino     → confirma recebimento de sacas
  informativo → lanca metas de devolutiva
  base        → registra envios
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date
import os
import time as time_mod

app = Flask(__name__)
CORS(app)


# ═══════════════════════════════════════════════════════
#  CONFIGURAÇÃO
# ═══════════════════════════════════════════════════════
SPREADSHEET_ID   = "https://docs.google.com/spreadsheets/d/19GzGDtW4d7eF_sdxkv_OM3oy75_7_nJgoFPH2CDF1uY/edit?usp=sharing"
CREDENTIALS_FILE = "credenciais-json@controle-de-sacas-493619.iam.gserviceaccount.com"

ADMIN_FIXO = {
    "nome":     "Administrador",
    "email":    "processosrjes@gmail.com",
    "senha":    "admin@2025",
    "nivel":    "admin",
    "fixo":     True,
    "criadoEm": datetime.now().isoformat(),
}

DESTINOS_VALIDOS = ["SJM", "DC Serra"]
NIVEIS_VALIDOS   = ["admin", "destino", "informativo", "base"]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


# ═══════════════════════════════════════════════════════
#  CONEXÃO COM GOOGLE SHEETS
# ═══════════════════════════════════════════════════════
def conectar_sheets():
    creds  = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID)


def aba(sheet, titulo):
    return sheet.worksheet(titulo)


def garantir_estrutura(sheet):
    """Cria todas as abas com cabeçalhos se ainda não existirem."""
    existentes = {ws.title for ws in sheet.worksheets()}

    estrutura = {
        "Envios": [
            "ID", "Base", "Tipo", "Destino", "Sacas", "TipoSaca", "Chips",
            "Data", "Responsavel", "Obs", "Foto", "Status", "ConfPor", "ConfEm",
        ],
        "Usuarios":        ["Nome", "Email", "Senha", "Nivel", "Fixo", "CriadoEm"],
        "Devolutivas":     ["Base", "Tipo", "Qtd", "Prazo", "Obs", "RegistradoPor", "CriadoEm"],
        "Bases_Franquias": ["Nome", "Cidade", "UF"],
        "Bases_Proprias":  ["Nome", "Cidade", "UF"],
    }

    for titulo, cabecalho in estrutura.items():
        if titulo not in existentes:
            ws = sheet.add_worksheet(title=titulo, rows=1000, cols=len(cabecalho))
            ws.append_row(cabecalho)
            print(f"  + Aba criada: {titulo}")

    # Garante admin fixo
    ws_u = aba(sheet, "Usuarios")
    usuarios = ws_u.get_all_records()
    if not any(u.get("Email", "").lower() == ADMIN_FIXO["email"] for u in usuarios):
        ws_u.append_row([
            ADMIN_FIXO["nome"], ADMIN_FIXO["email"], ADMIN_FIXO["senha"],
            ADMIN_FIXO["nivel"], "Sim", ADMIN_FIXO["criadoEm"],
        ])
        print("  + Admin fixo inserido")

    _popular_bases_padrao(sheet)


def _popular_bases_padrao(sheet):
    FRANQUIAS = [
        ("F ADB-RJ","Armação dos Búzios","RJ"),("F ADC-RJ","Arraial do Cabo","RJ"),
        ("F ALT-ES","Serra","ES"),("F ANC-RJ","Rio de Janeiro","RJ"),
        ("F ANG-RJ","Angra dos Reis","RJ"),("F ARC-ES","Aracruz","ES"),
        ("F BAG-RJ","Rio de Janeiro","RJ"),("F BAN-RJ","Guapimirim","RJ"),
        ("F BDT-RJ","Rio de Janeiro","RJ"),("F BRB-RJ","Rio de Janeiro","RJ"),
        ("F BRM-RJ","Barra Mansa","RJ"),("F CDC-ES","Alegre","ES"),
        ("F CDG-RJ","Campos dos Goytacazes","RJ"),("F CDT-ES","Cachoeiro de Itapemirim","ES"),
        ("F CPG-RJ","Rio de Janeiro","RJ"),("F CRC-ES","Cariacica","ES"),
        ("F CSM-RJ","Rio de Janeiro","RJ"),("F CVI-ES","Serra","ES"),
        ("F DCT-RJ","Rio de Janeiro","RJ"),("F DUQ-RJ","Duque de Caxias","RJ"),
        ("F EST-RJ","Rio de Janeiro","RJ"),("F GDL-RJ","Rio de Janeiro","RJ"),
        ("F GDP-RJ","Rio de Janeiro","RJ"),("F GPM-RJ","Guapimirim","RJ"),
        ("F GPR-ES","Guarapari","ES"),("F GUA-RJ","Rio de Janeiro","RJ"),
        ("F IGB-RJ","Iguaba Grande","RJ"),("F ITB-RJ","Itaboraí","RJ"),
        ("F ITGU-RJ","Itaguaí","RJ"),("F ITP-RJ","Itaperuna","RJ"),
        ("F JAG-ES","Jaguaré","ES"),("F JCA-RJ","Rio de Janeiro","RJ"),
        ("F JDL-ES","Serra","ES"),("F JML-ES","Serra","ES"),
        ("F JSA-RJ","São João de Meriti","RJ"),("F LIN-ES","Guarapari","ES"),
        ("F MAR-RJ","Rio de Janeiro","RJ"),("F MCE-RJ","Macaé","RJ"),
        ("F MDG-RJ","Rio de Janeiro","RJ"),("F MQT-RJ","Mesquita","RJ"),
        ("F MRC-RJ","Rio de Janeiro","RJ"),("F MRT-ES","Marataízes","ES"),
        ("F NIT-RJ","Niterói","RJ"),("F NTG-ES","São Mateus","ES"),
        ("F NTR-RJ","Niterói","RJ"),("F NVG-RJ","Nova Iguaçu","RJ"),
        ("F OST-RJ","Rio das Ostras","RJ"),("F PCR-RJ","Rio de Janeiro","RJ"),
        ("F PJC-RJ","Campos dos Goytacazes","RJ"),("F PNC-RJ","Rio de Janeiro","RJ"),
        ("F PTL-RJ","Petrópolis","RJ"),("F QSM-RJ","Petrópolis","RJ"),
        ("F RCB-RJ","Rio de Janeiro","RJ"),("F RDO-RJ","Rio das Ostras","RJ"),
        ("F RIO-RJ","Rio de Janeiro","RJ"),("F RZE-RJ","Resende","RJ"),
        ("F SAP-RJ","São Pedro da Aldeia","RJ"),("F SCT-RJ","Rio de Janeiro","RJ"),
        ("F SDG-ES","Serra","ES"),("F SMJ-ES","Santa Maria de Jetibá","ES"),
        ("F SNC-RJ","Rio de Janeiro","RJ"),("F SPA-RJ","São Pedro da Aldeia","RJ"),
        ("F SPD-RJ","Maricá","RJ"),("F STC-RJ","Rio de Janeiro","RJ"),
        ("F TBB-RJ","São Gonçalo","RJ"),("F TDE-RJ","São Gonçalo","RJ"),
        ("F TOS-RJ","Rio de Janeiro","RJ"),("F VAN-ES","Aracruz","ES"),
        ("F VIT-ES","Vitória","ES"),("F VLC-RJ","Valença","RJ"),
        ("F VLV-ES","Vila Velha","ES"),("F VRB-ES","Nova Venécia","ES"),
        ("F VTR-RJ","Barra Mansa","RJ"),
    ]
    PROPRIAS = [
        ("ACT-ES","Anchieta","ES"),("ADR -RJ","Angra dos Reis","RJ"),
        ("ALG-ES","Alegre","ES"),("ARC -ES","Aracruz","ES"),
        ("ARR -RJ","Araruama","RJ"),("BPR -RJ","Barra do Piraí","RJ"),
        ("BRX -RJ","Belford Roxo","RJ"),("BRX 02-RJ","Belford Roxo","RJ"),
        ("BSF-ES","Barra de São Francisco","ES"),("CAB-RJ","Cabo Frio","RJ"),
        ("CAR -ES","Cariacica","ES"),("CAR 02-ES","Cariacica","ES"),
        ("CDC -ES","Conceição do Castelo","ES"),("CDG -RJ","Campos dos Goytacazes","RJ"),
        ("CDM-ES","Cachoeiro de Itapemirim","ES"),("CFB -RJ","Cabo Frio","RJ"),
        ("CLN -ES","Colatina","ES"),("DC CDG-RJ","Campos dos Goytacazes","RJ"),
        ("DMT -ES","Domingos Martins","ES"),("DQC 02-RJ","Duque de Caxias","RJ"),
        ("GPR -ES","Guarapari","ES"),("IPE -RJ","Itaperuna","RJ"),
        ("ITB -RJ","Itaboraí","RJ"),("ITGU -RJ","Itaguaí","RJ"),
        ("JDL -ES","Serra","ES"),("LIN -ES","Linhares","ES"),
        ("MAC -RJ","Macaé","RJ"),("MGE -RJ","Magé","RJ"),
        ("MRCA -RJ","Maricá","RJ"),("NFG-RJ","Nova Friburgo","RJ"),
        ("NTE-RJ","Niterói","RJ"),("NVF -RJ","Nova Friburgo","RJ"),
        ("NVI 03-RJ","Nova Iguaçu","RJ"),("NVI 04-RJ","Nova Iguaçu","RJ"),
        ("PIN-ES","Pinheiros","ES"),("PMG-RJ","Rio de Janeiro","RJ"),
        ("PTL -RJ","Petrópolis","RJ"),("QMD -RJ","Queimados","RJ"),
        ("RBT -RJ","Rio Bonito","RJ"),("RIO 02-RJ","Rio de Janeiro","RJ"),
        ("RIO 03-RJ","Rio de Janeiro","RJ"),("RIO 06-RJ","Rio de Janeiro","RJ"),
        ("RIO 07-RJ","Rio de Janeiro","RJ"),("RIO 08-RJ","Rio de Janeiro","RJ"),
        ("RIO 09-RJ","Rio de Janeiro","RJ"),("RIO 11-RJ","Rio de Janeiro","RJ"),
        ("RIO 12-RJ","Rio de Janeiro","RJ"),("RIO 13-RJ","Rio de Janeiro","RJ"),
        ("RIO 15-RJ","Rio de Janeiro","RJ"),("RIO-RJ","Rio de Janeiro","RJ"),
        ("ROS-RJ","Rio das Ostras","RJ"),("RSD -RJ","Resende","RJ"),
        ("SAM-ES","São Mateus","ES"),("SAR-RJ","Duque de Caxias","RJ"),
        ("SFI-RJ","São Francisco de Itabapoana","RJ"),("SGC -RJ","São Gonçalo","RJ"),
        ("SGC 02-RJ","São Gonçalo","RJ"),("SGP-ES","São Gabriel da Palha","ES"),
        ("SJT -RJ","São João de Meriti","RJ"),("SMT -ES","São Mateus","ES"),
        ("SRR -ES","Serra","ES"),("SVT-ES","Colatina","ES"),
        ("TRI -RJ","Três Rios","RJ"),("TRS -RJ","Teresópolis","RJ"),
        ("VIN -ES","Viana","ES"),("VIR -ES","Vitória","ES"),
        ("VIR 02-ES","Vitória","ES"),("VIR 03-ES","Vitória","ES"),
        ("VLH-ES","Vila Velha","ES"),("VTR -RJ","Volta Redonda","RJ"),
        ("VVL-ES","Vila Velha","ES"),
    ]

    ws_f = aba(sheet, "Bases_Franquias")
    ws_p = aba(sheet, "Bases_Proprias")

    if len(ws_f.get_all_records()) == 0:
        ws_f.append_rows([list(b) for b in FRANQUIAS])
        print(f"  + {len(FRANQUIAS)} franquias inseridas")

    if len(ws_p.get_all_records()) == 0:
        ws_p.append_rows([list(b) for b in PROPRIAS])
        print(f"  + {len(PROPRIAS)} bases proprias inseridas")


# ═══════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════
def hoje_str():
    return date.today().isoformat()


def novo_id():
    return str(int(time_mod.time() * 1000))


def nivel_ok(niveis: list) -> bool:
    """Valida o nível do usuário enviado no header X-Nivel."""
    return request.headers.get("X-Nivel", "") in niveis


def err(msg, code=400):
    return jsonify({"sucesso": False, "erro": msg}), code


def chips_str(chips: list) -> str:
    """Lista → string separada por | para armazenar no Sheets."""
    return "|".join(str(c) for c in chips) if chips else ""


def str_chips(s) -> list:
    """String separada por | → lista."""
    if not s:
        return []
    return [c.strip() for c in str(s).split("|") if c.strip()]


def col_idx(cabecalho: list, nome: str) -> int:
    """Retorna o índice (1-based) de uma coluna pelo nome."""
    return cabecalho.index(nome) + 1


# ═══════════════════════════════════════════════════════
#  ROTAS — BASES
# ═══════════════════════════════════════════════════════
@app.route("/api/bases", methods=["GET"])
def listar_bases():
    """Retorna franquias e bases próprias separadas."""
    try:
        sh        = conectar_sheets()
        franquias = aba(sh, "Bases_Franquias").get_all_records()
        proprias  = aba(sh, "Bases_Proprias").get_all_records()
        return jsonify({
            "sucesso":   True,
            "franquias": franquias,
            "proprias":  proprias,
            "total":     len(franquias) + len(proprias),
        })
    except Exception as e:
        return err(str(e), 500)


@app.route("/api/bases/upload", methods=["POST"])
def upload_bases():
    """
    Substitui a lista de bases a partir de JSON.
    Body: { "franquias": [{nome, cidade, uf}], "proprias": [...] }
    Requer: admin
    """
    if not nivel_ok(["admin"]):
        return err("Acesso negado.", 403)
    try:
        body      = request.json
        franquias = body.get("franquias", [])
        proprias  = body.get("proprias", [])
        sh        = conectar_sheets()

        ws_f = aba(sh, "Bases_Franquias")
        ws_f.clear()
        ws_f.append_row(["Nome", "Cidade", "UF"])
        if franquias:
            ws_f.append_rows([[b.get("nome",""), b.get("cidade",""), b.get("uf","")] for b in franquias])

        ws_p = aba(sh, "Bases_Proprias")
        ws_p.clear()
        ws_p.append_row(["Nome", "Cidade", "UF"])
        if proprias:
            ws_p.append_rows([[b.get("nome",""), b.get("cidade",""), b.get("uf","")] for b in proprias])

        return jsonify({
            "sucesso": True,
            "mensagem": f"{len(franquias)} franquias e {len(proprias)} bases proprias atualizadas.",
        })
    except Exception as e:
        return err(str(e), 500)


# ═══════════════════════════════════════════════════════
#  ROTAS — USUÁRIOS
# ═══════════════════════════════════════════════════════
@app.route("/api/login", methods=["POST"])
def login():
    """
    Autentica o usuário.
    Body: { "email": "...", "senha": "..." }
    Retorna: { sucesso, usuario: { nome, email, nivel, fixo } }
    """
    try:
        body  = request.json
        email = body.get("email", "").strip().lower()
        senha = body.get("senha", "")

        if not email or not senha:
            return err("E-mail e senha sao obrigatorios.")

        sh       = conectar_sheets()
        usuarios = aba(sh, "Usuarios").get_all_records()

        u = next(
            (u for u in usuarios
             if u.get("Email","").lower() == email and u.get("Senha","") == senha),
            None
        )
        if not u:
            return err("E-mail ou senha incorretos.", 401)

        return jsonify({
            "sucesso": True,
            "usuario": {
                "nome":  u.get("Nome", ""),
                "email": u.get("Email", ""),
                "nivel": u.get("Nivel", "base"),
                "fixo":  u.get("Fixo", "") == "Sim",
            },
        })
    except Exception as e:
        return err(str(e), 500)


@app.route("/api/usuarios", methods=["GET"])
def listar_usuarios():
    """Lista todos os usuários sem expor senha. Requer: admin"""
    if not nivel_ok(["admin"]):
        return err("Acesso negado.", 403)
    try:
        sh       = conectar_sheets()
        usuarios = aba(sh, "Usuarios").get_all_records()
        for u in usuarios:
            u.pop("Senha", None)
        return jsonify({"sucesso": True, "usuarios": usuarios})
    except Exception as e:
        return err(str(e), 500)


@app.route("/api/usuarios", methods=["POST"])
def criar_usuario():
    """
    Cria novo usuário.
    Body: { nome, email, senha, nivel }
    Niveis: admin | destino | informativo | base
    Requer: admin
    """
    if not nivel_ok(["admin"]):
        return err("Acesso negado.", 403)
    try:
        body  = request.json
        nome  = body.get("nome", "").strip()
        email = body.get("email", "").strip().lower()
        senha = body.get("senha", "")
        nivel = body.get("nivel", "base")

        if not nome or not email or not senha:
            return err("Nome, e-mail e senha sao obrigatorios.")
        if len(senha) < 6:
            return err("Senha deve ter pelo menos 6 caracteres.")
        if nivel not in NIVEIS_VALIDOS:
            return err(f"Nivel invalido. Use: {', '.join(NIVEIS_VALIDOS)}")

        sh       = conectar_sheets()
        ws       = aba(sh, "Usuarios")
        usuarios = ws.get_all_records()

        if any(u.get("Email","").lower() == email for u in usuarios):
            return err("E-mail ja cadastrado.")

        ws.append_row([nome, email, senha, nivel, "Nao", datetime.now().isoformat()])
        return jsonify({"sucesso": True, "mensagem": f"Usuario {nome} criado com nivel {nivel}."})
    except Exception as e:
        return err(str(e), 500)


@app.route("/api/usuarios/<path:email>", methods=["DELETE"])
def remover_usuario(email):
    """Remove usuário pelo e-mail. Não permite remover admin fixo. Requer: admin"""
    if not nivel_ok(["admin"]):
        return err("Acesso negado.", 403)
    if email.lower() == ADMIN_FIXO["email"]:
        return err("Nao e possivel remover o administrador fixo.")
    try:
        sh    = conectar_sheets()
        ws    = aba(sh, "Usuarios")
        linhas = ws.get_all_values()
        for i, row in enumerate(linhas[1:], start=2):
            if len(row) >= 2 and row[1].lower() == email.lower():
                ws.delete_rows(i)
                return jsonify({"sucesso": True, "mensagem": f"Usuario {email} removido."})
        return err("Usuario nao encontrado.", 404)
    except Exception as e:
        return err(str(e), 500)


# ═══════════════════════════════════════════════════════
#  ROTAS — ENVIOS DE SACAS
# ═══════════════════════════════════════════════════════
@app.route("/api/envios", methods=["GET"])
def listar_envios():
    """
    Lista envios com filtros opcionais.
    Query params: status, destino, base
    Foto omitida por padrão (use /api/envios/<id> para foto completa).
    """
    try:
        sh     = conectar_sheets()
        envios = aba(sh, "Envios").get_all_records()

        status  = request.args.get("status")
        destino = request.args.get("destino")
        base    = request.args.get("base")

        if status:  envios = [e for e in envios if e.get("Status")  == status]
        if destino: envios = [e for e in envios if e.get("Destino") == destino]
        if base:    envios = [e for e in envios if e.get("Base")    == base]

        for e in envios:
            e["Chips"] = str_chips(e.get("Chips", ""))
            e.pop("Foto", None)   # omite foto do listão para economizar banda

        return jsonify({"sucesso": True, "envios": envios, "total": len(envios)})
    except Exception as e:
        return err(str(e), 500)


@app.route("/api/envios/<envio_id>", methods=["GET"])
def detalhe_envio(envio_id):
    """Retorna um envio específico incluindo foto (base64)."""
    try:
        sh     = conectar_sheets()
        envios = aba(sh, "Envios").get_all_records()
        envio  = next((e for e in envios if str(e.get("ID","")) == str(envio_id)), None)
        if not envio:
            return err("Envio nao encontrado.", 404)
        envio["Chips"] = str_chips(envio.get("Chips", ""))
        return jsonify({"sucesso": True, "envio": envio})
    except Exception as e:
        return err(str(e), 500)


@app.route("/api/envios", methods=["POST"])
def registrar_envio():
    """
    Registra novo envio de sacas — espelha exatamente o objeto salvo pelo HTML.

    Body JSON:
    {
        "base":        "F ADB-RJ",
        "tipo":        "Franquia" | "Base Propria",
        "destino":     "SJM" | "DC Serra",
        "sacas":       10,
        "tipoSaca":    "branca" | "vermelha",
        "chips":       ["JT-001", "JT-002"],
        "data":        "2026-04-17",
        "responsavel": "Joao Silva",
        "obs":         "...",
        "foto":        "data:image/png;base64,..."
    }
    Requer: base | admin
    """
    if not nivel_ok(["base", "admin"]):
        return err("Acesso negado.", 403)
    try:
        b         = request.json
        base      = b.get("base", "").strip()
        tipo      = b.get("tipo", "").strip()
        destino   = b.get("destino", "").strip()
        sacas     = int(b.get("sacas", 0))
        tipo_saca = b.get("tipoSaca", "").strip()
        chips     = b.get("chips", [])
        data      = b.get("data", hoje_str())
        resp      = b.get("responsavel", "").strip()
        obs       = b.get("obs", "").strip()
        foto      = b.get("foto", "")

        # — Validações idênticas às do HTML —
        if not base:
            return err("Base de origem e obrigatoria.")
        if destino not in DESTINOS_VALIDOS:
            return err(f"Destino invalido. Use: {', '.join(DESTINOS_VALIDOS)}")
        if sacas < 1:
            return err("Quantidade de sacas deve ser maior que zero.")
        if tipo_saca not in ("branca", "vermelha"):
            return err("TipoSaca deve ser 'branca' ou 'vermelha'.")
        if tipo_saca == "vermelha" and not chips:
            return err("Sacas vermelhas exigem pelo menos um numero de chip.")
        if not resp:
            return err("Responsavel e obrigatorio.")

        sh = conectar_sheets()
        ws = aba(sh, "Envios")
        eid = novo_id()

        ws.append_row([
            eid,
            base,
            tipo,
            destino,
            sacas,
            tipo_saca,
            chips_str(chips),   # "JT-001|JT-002|..."
            data,
            resp,
            obs,
            foto,               # base64 ou vazio
            "Em transito",
            "",                 # ConfPor
            "",                 # ConfEm
        ])

        return jsonify({
            "sucesso": True,
            "id":      eid,
            "mensagem": f"Envio registrado: {sacas} saca(s) {tipo_saca}(s) de {base} para {destino}.",
        })
    except Exception as e:
        return err(str(e), 500)


@app.route("/api/envios/<envio_id>/confirmar", methods=["POST"])
def confirmar_envio(envio_id):
    """
    Confirma o recebimento (dar OK) de um envio.
    Body: { "confirmedBy": "Nome do conferente" }
    Requer: destino | admin
    """
    if not nivel_ok(["destino", "admin"]):
        return err("Acesso negado. Somente destino ou admin podem confirmar.", 403)
    try:
        conf_por = request.json.get("confirmedBy", "").strip()
        if not conf_por:
            return err("Informe o nome de quem esta confirmando.")

        sh     = conectar_sheets()
        ws     = aba(sh, "Envios")
        linhas = ws.get_all_values()
        cab    = linhas[0]

        c_id     = col_idx(cab, "ID")
        c_status = col_idx(cab, "Status")
        c_conf   = col_idx(cab, "ConfPor")
        c_confem = col_idx(cab, "ConfEm")

        for i, row in enumerate(linhas[1:], start=2):
            if str(row[c_id - 1]) == str(envio_id):
                if row[c_status - 1] == "Confirmado":
                    return err("Este envio ja foi confirmado.")
                ws.update_cell(i, c_status, "Confirmado")
                ws.update_cell(i, c_conf,   conf_por)
                ws.update_cell(i, c_confem, hoje_str())
                return jsonify({
                    "sucesso":  True,
                    "mensagem": f"Recebimento confirmado por {conf_por}.",
                })

        return err("Envio nao encontrado.", 404)
    except Exception as e:
        return err(str(e), 500)


# ═══════════════════════════════════════════════════════
#  ROTAS — DEVOLUTIVA DE SACAS VERMELHAS
# ═══════════════════════════════════════════════════════
@app.route("/api/devolutivas", methods=["GET"])
def listar_devolutivas():
    """Retorna todas as metas de devolução de sacas vermelhas."""
    try:
        sh   = conectar_sheets()
        devs = aba(sh, "Devolutivas").get_all_records()
        return jsonify({"sucesso": True, "devolutivas": devs, "total": len(devs)})
    except Exception as e:
        return err(str(e), 500)


@app.route("/api/devolutivas/<path:base>", methods=["GET"])
def devolutiva_por_base(base):
    """
    Retorna a meta de devolução de uma base específica.
    Usado pelo aviso automático no formulário de Registrar Envio.
    """
    try:
        sh   = conectar_sheets()
        devs = aba(sh, "Devolutivas").get_all_records()
        dev  = next((d for d in devs if d.get("Base","") == base), None)
        return jsonify({"sucesso": True, "devolutiva": dev})
    except Exception as e:
        return err(str(e), 500)


@app.route("/api/devolutivas", methods=["POST"])
def registrar_devolutiva():
    """
    Registra ou substitui a meta de devolução para uma base.

    Body JSON:
    {
        "base":          "F ADB-RJ",
        "tipo":          "Franquia" | "Base Propria",
        "qtd":           5,
        "prazo":         "2026-04-30",
        "obs":           "...",
        "registradoPor": "Nome"
    }
    Requer: informativo | admin
    """
    if not nivel_ok(["informativo", "admin"]):
        return err("Acesso negado. Somente informativo ou admin.", 403)
    try:
        b       = request.json
        base    = b.get("base", "").strip()
        tipo    = b.get("tipo", "").strip()
        qtd     = int(b.get("qtd", 0))
        prazo   = b.get("prazo", "").strip()
        obs     = b.get("obs", "").strip()
        reg_por = b.get("registradoPor", "").strip()

        if not base:
            return err("Base e obrigatoria.")
        if qtd < 1:
            return err("Quantidade deve ser maior que zero.")

        sh     = conectar_sheets()
        ws     = aba(sh, "Devolutivas")
        linhas = ws.get_all_values()
        cab    = linhas[0]
        c_base = col_idx(cab, "Base")

        nova = [base, tipo, qtd, prazo, obs, reg_por, datetime.now().isoformat()]

        # Substitui se já existir para essa base
        for i, row in enumerate(linhas[1:], start=2):
            if str(row[c_base - 1]) == base:
                ws.delete_rows(i)
                ws.append_row(nova)
                return jsonify({
                    "sucesso":  True,
                    "mensagem": f"Meta de devolucao de {base} atualizada: {qtd} saca(s).",
                })

        ws.append_row(nova)
        return jsonify({
            "sucesso":  True,
            "mensagem": f"Meta de devolucao de {base} registrada: {qtd} saca(s).",
        })
    except Exception as e:
        return err(str(e), 500)


@app.route("/api/devolutivas/<path:base>", methods=["DELETE"])
def remover_devolutiva(base):
    """Remove a meta de devolução de uma base. Requer: informativo | admin"""
    if not nivel_ok(["informativo", "admin"]):
        return err("Acesso negado.", 403)
    try:
        sh     = conectar_sheets()
        ws     = aba(sh, "Devolutivas")
        linhas = ws.get_all_values()
        cab    = linhas[0]
        c_base = col_idx(cab, "Base")

        for i, row in enumerate(linhas[1:], start=2):
            if str(row[c_base - 1]) == base:
                ws.delete_rows(i)
                return jsonify({"sucesso": True, "mensagem": f"Meta de {base} removida."})

        return err("Base nao encontrada.", 404)
    except Exception as e:
        return err(str(e), 500)


# ═══════════════════════════════════════════════════════
#  ROTA — PAINEL CONSOLIDADO
# ═══════════════════════════════════════════════════════
@app.route("/api/painel", methods=["GET"])
def painel():
    """
    Dados consolidados para o painel principal do HTML.
    Retorna resumo, envios em trânsito, bases sem envio e devolutivas.
    """
    try:
        sh        = conectar_sheets()
        hoje      = hoje_str()

        envios    = aba(sh, "Envios").get_all_records()
        franquias = aba(sh, "Bases_Franquias").get_all_records()
        proprias  = aba(sh, "Bases_Proprias").get_all_records()
        devs      = aba(sh, "Devolutivas").get_all_records()

        todas_bases = franquias + proprias

        transitando = [e for e in envios if e.get("Status") == "Em transito"]
        conf_hoje   = [e for e in envios if e.get("Status") == "Confirmado" and e.get("ConfEm") == hoje]

        sacas_total     = sum(int(e.get("Sacas", 0)) for e in transitando)
        sacas_vermelhas = sum(int(e.get("Sacas", 0)) for e in transitando if e.get("TipoSaca") == "vermelha")
        sacas_brancas   = sacas_total - sacas_vermelhas
        sacas_conf_hoje = sum(int(e.get("Sacas", 0)) for e in conf_hoje)

        bases_enviando  = list({e.get("Base") for e in transitando})
        bases_sem_envio = [b for b in todas_bases if b.get("Nome") not in bases_enviando]

        # Envios em trânsito sem foto (economiza banda)
        transito_resumo = [
            {
                "ID":          e.get("ID"),
                "Base":        e.get("Base"),
                "Tipo":        e.get("Tipo"),
                "Destino":     e.get("Destino"),
                "Sacas":       e.get("Sacas"),
                "TipoSaca":    e.get("TipoSaca"),
                "Chips":       str_chips(e.get("Chips", "")),
                "Data":        e.get("Data"),
                "Responsavel": e.get("Responsavel"),
                "Status":      e.get("Status"),
            }
            for e in transitando
        ]

        return jsonify({
            "sucesso": True,
            "resumo": {
                "sacasEmTransito":        sacas_total,
                "sacasVermelhasTransito": sacas_vermelhas,
                "sacasBrancasTransito":   sacas_brancas,
                "sacasConfirmadasHoje":   sacas_conf_hoje,
                "basesEnviando":          len(bases_enviando),
                "totalBases":             len(todas_bases),
                "basesSemEnvio":          len(bases_sem_envio),
                "devolutivasPendentes":   len(devs),
            },
            "enviosTransito":  transito_resumo,
            "basesSemEnvio":   bases_sem_envio,
            "devolutivas":     devs,
        })
    except Exception as e:
        return err(str(e), 500)


# ═══════════════════════════════════════════════════════
#  ROTA — HEALTH CHECK
# ═══════════════════════════════════════════════════════
@app.route("/api/health", methods=["GET"])
def health():
    """Verifica se o servidor está no ar e conectado à planilha."""
    try:
        sh = conectar_sheets()
        return jsonify({
            "sucesso":    True,
            "status":     "online",
            "planilha":   sh.title,
            "timestamp":  datetime.now().isoformat(),
        })
    except Exception as e:
        return jsonify({"sucesso": False, "status": "erro", "erro": str(e)}), 500


# ═══════════════════════════════════════════════════════
#  INICIALIZAÇÃO
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    print()
    print("╔══════════════════════════════════════════╗")
    print("║  J&T Express — Controle de Sacas  API   ║")
    print("╚══════════════════════════════════════════╝")
    print()
    print("Conectando ao Google Sheets...")
    try:
        sh = conectar_sheets()
        print(f"Conectado: {sh.title}")
        print("Verificando estrutura das abas...")
        garantir_estrutura(sh)
        print("Estrutura OK")
    except FileNotFoundError:
        print("AVISO: credenciais.json nao encontrado.")
        print("  Configure CREDENTIALS_FILE e tente novamente.")
    except Exception as e:
        print(f"AVISO: {e}")
        print("  Verifique SPREADSHEET_ID e credenciais.json.")

    port = int(os.environ.get("PORT", 5000))
    print()
    print(f"Servidor: http://localhost:{port}")
    print()
    print("Endpoints:")
    rotas = [
        ("GET ",  "/api/health",                       ""                     ),
        ("GET ",  "/api/bases",                        ""                     ),
        ("POST",  "/api/bases/upload",                 "[admin]"              ),
        ("POST",  "/api/login",                        ""                     ),
        ("GET ",  "/api/usuarios",                     "[admin]"              ),
        ("POST",  "/api/usuarios",                     "[admin]"              ),
        ("DEL ",  "/api/usuarios/<email>",             "[admin]"              ),
        ("GET ",  "/api/envios",                       "?status=&destino=&base="),
        ("GET ",  "/api/envios/<id>",                  ""                     ),
        ("POST",  "/api/envios",                       "[base|admin]"         ),
        ("POST",  "/api/envios/<id>/confirmar",        "[destino|admin]"      ),
        ("GET ",  "/api/devolutivas",                  ""                     ),
        ("GET ",  "/api/devolutivas/<base>",           ""                     ),
        ("POST",  "/api/devolutivas",                  "[informativo|admin]"  ),
        ("DEL ",  "/api/devolutivas/<base>",           "[informativo|admin]"  ),
        ("GET ",  "/api/painel",                       ""                     ),
    ]
    for metodo, rota, nota in rotas:
        print(f"  {metodo}  {rota:<40} {nota}")
    print()

    app.run(host="0.0.0.0", port=port, debug=False)
