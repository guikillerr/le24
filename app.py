from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify
)

import sqlite3
import re

from datetime import (
    datetime,
    date,
    timedelta
)


app = Flask(__name__)

app.secret_key = "l24-chave-desenvolvimento"


# ==========================================================
# WHATSAPP DA BARBEARIA
# Troque depois pelo número verdadeiro.
# 55 + DDD + número
# ==========================================================

WHATSAPP_BARBEARIA = "5511999999999"


# ==========================================================
# BANCO DE DADOS
# ==========================================================

def conectar_banco():

    banco = sqlite3.connect(
        "barbearia.db"
    )

    banco.row_factory = sqlite3.Row

    return banco


def criar_tabelas():

    banco = conectar_banco()


    banco.execute("""
        CREATE TABLE IF NOT EXISTS barbeiros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL
        )
    """)


    banco.execute("""
        CREATE TABLE IF NOT EXISTS servicos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            preco REAL NOT NULL,
            duracao INTEGER NOT NULL
        )
    """)


    banco.execute("""
        CREATE TABLE IF NOT EXISTS agendamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            cliente TEXT NOT NULL,
            telefone TEXT NOT NULL,

            barbeiro_id INTEGER NOT NULL,
            servico_id INTEGER NOT NULL,

            data TEXT NOT NULL,
            horario TEXT NOT NULL,

            status TEXT NOT NULL DEFAULT 'confirmado',

            FOREIGN KEY (barbeiro_id)
            REFERENCES barbeiros(id),

            FOREIGN KEY (servico_id)
            REFERENCES servicos(id)
        )
    """)


    banco.commit()


    # ======================================================
    # EMERSON COMO ÚNICO BARBEIRO
    # ======================================================

    emerson = banco.execute("""
        SELECT id
        FROM barbeiros
        WHERE nome = ?
    """, (
        "Emerson",
    )).fetchone()


    if emerson is None:

        cursor = banco.execute("""
            INSERT INTO barbeiros (
                nome
            )

            VALUES (?)
        """, (
            "Emerson",
        ))

        emerson_id = cursor.lastrowid

    else:

        emerson_id = emerson["id"]


    # Mantém agendamentos antigos ligados ao Emerson.

    banco.execute("""
        UPDATE agendamentos
        SET barbeiro_id = ?
    """, (
        emerson_id,
    ))


    banco.execute("""
        DELETE FROM barbeiros
        WHERE id != ?
    """, (
        emerson_id,
    ))


    # ======================================================
    # SERVIÇOS
    # ======================================================

    quantidade_servicos = banco.execute("""
        SELECT COUNT(*)
        FROM servicos
    """).fetchone()[0]


    if quantidade_servicos == 0:

        servicos = [

            (
                "Corte masculino",
                35.00,
                40
            ),

            (
                "Barba",
                25.00,
                30
            ),

            (
                "Corte + barba",
                50.00,
                60
            )

        ]


        banco.executemany("""
            INSERT INTO servicos (
                nome,
                preco,
                duracao
            )

            VALUES (?, ?, ?)
        """, servicos)


    banco.commit()


    # ======================================================
    # REMOVE AGENDAMENTOS DUPLICADOS ANTIGOS
    # ======================================================

    banco.execute("""
        DELETE FROM agendamentos

        WHERE status = 'confirmado'

        AND id NOT IN (

            SELECT MIN(id)

            FROM agendamentos

            WHERE status = 'confirmado'

            GROUP BY
                barbeiro_id,
                data,
                horario
        )
    """)


    banco.commit()


    # ======================================================
    # BLOQUEIO REAL DE HORÁRIO DUPLICADO
    # ======================================================

    banco.execute("""
        CREATE UNIQUE INDEX
        IF NOT EXISTS horario_confirmado_unico

        ON agendamentos (
            barbeiro_id,
            data,
            horario
        )

        WHERE status = 'confirmado'
    """)


    banco.commit()

    banco.close()


criar_tabelas()


# ==========================================================
# HORÁRIOS
# ==========================================================

HORARIOS_PADRAO = [

    "09:00",
    "09:40",
    "10:20",
    "11:00",

    "13:00",
    "13:40",
    "14:20",

    "15:00",
    "15:40",
    "16:20",

    "17:00",
    "17:40",
    "18:20"

]


# ==========================================================
# BUSCAR HORÁRIOS DISPONÍVEIS
# ==========================================================

def buscar_horarios_disponiveis(
    barbeiro_id,
    data_agendamento
):

    try:

        data_objeto = datetime.strptime(
            data_agendamento,
            "%Y-%m-%d"
        ).date()

    except ValueError:

        return []


    # Não aceita data passada.

    if data_objeto < date.today():

        return []


    # Domingo fechado.

    if data_objeto.weekday() == 6:

        return []


    banco = conectar_banco()


    ocupados = banco.execute("""
        SELECT horario

        FROM agendamentos

        WHERE barbeiro_id = ?

        AND data = ?

        AND status = 'confirmado'
    """, (

        barbeiro_id,

        data_agendamento

    )).fetchall()


    banco.close()


    horarios_ocupados = {

        item["horario"]

        for item in ocupados

    }


    horarios_livres = [

        horario

        for horario in HORARIOS_PADRAO

        if horario not in horarios_ocupados

    ]


    return horarios_livres


# ==========================================================
# CRIAR CALENDÁRIO
# ==========================================================

def criar_calendario(
    barbeiro_id
):

    calendario = []


    nomes_semana = [
        "SEG",
        "TER",
        "QUA",
        "QUI",
        "SEX",
        "SÁB",
        "DOM"
    ]


    nomes_meses = [
        "JAN",
        "FEV",
        "MAR",
        "ABR",
        "MAI",
        "JUN",
        "JUL",
        "AGO",
        "SET",
        "OUT",
        "NOV",
        "DEZ"
    ]


    nomes_meses_completos = [
        "JANEIRO",
        "FEVEREIRO",
        "MARÇO",
        "ABRIL",
        "MAIO",
        "JUNHO",
        "JULHO",
        "AGOSTO",
        "SETEMBRO",
        "OUTUBRO",
        "NOVEMBRO",
        "DEZEMBRO"
    ]


    hoje = date.today()


    # Primeiro dia do mês seguinte.

    if hoje.month == 12:

        primeiro_proximo_mes = date(
            hoje.year + 1,
            1,
            1
        )

    else:

        primeiro_proximo_mes = date(
            hoje.year,
            hoje.month + 1,
            1
        )


    # Primeiro dia do mês depois do próximo.
    # O calendário vai até o último dia do próximo mês.

    if primeiro_proximo_mes.month == 12:

        limite = date(
            primeiro_proximo_mes.year + 1,
            1,
            1
        )

    else:

        limite = date(
            primeiro_proximo_mes.year,
            primeiro_proximo_mes.month + 1,
            1
        )


    dia = hoje


    while dia < limite:

        data_texto = dia.strftime(
            "%Y-%m-%d"
        )


        domingo = (
            dia.weekday() == 6
        )


        if domingo:

            horarios = []

        else:

            horarios = (
                buscar_horarios_disponiveis(
                    barbeiro_id,
                    data_texto
                )
            )


        lotado = (
            not domingo
            and
            len(horarios) == 0
        )


        calendario.append({

            "data": data_texto,

            "dia": dia.day,

            "semana":
                nomes_semana[
                    dia.weekday()
                ],

            "mes":
                nomes_meses[
                    dia.month - 1
                ],

            "mes_nome":
                nomes_meses_completos[
                    dia.month - 1
                ],

            "mes_chave":
                f"{dia.year}-{dia.month:02d}",

            "domingo":
                domingo,

            "lotado":
                lotado,

            "livres":
                len(horarios)

        })


        dia += timedelta(
            days=1
        )


    return calendario


# ==========================================================
# HOME
# ==========================================================

@app.route("/")
def index():

    banco = conectar_banco()


    barbeiros = banco.execute("""
        SELECT *
        FROM barbeiros
    """).fetchall()


    servicos = banco.execute("""
        SELECT *
        FROM servicos
    """).fetchall()


    banco.close()


    return render_template(
        "index.html",
        barbeiros=barbeiros,
        servicos=servicos
    )


# ==========================================================
# VALIDAR TELEFONE BRASILEIRO
# ==========================================================

def normalizar_telefone(
    telefone
):

    return re.sub(
        r"\D",
        "",
        telefone or ""
    )


def telefone_brasileiro_plausivel(
    telefone
):

    telefone = normalizar_telefone(
        telefone
    )


    # Celular brasileiro com DDD:
    # precisa possuir 11 números.

    if len(telefone) != 11:

        return False


    ddds_validos = {

        "11", "12", "13", "14",
        "15", "16", "17", "18",
        "19",

        "21", "22", "24",
        "27", "28",

        "31", "32", "33", "34",
        "35", "37", "38",

        "41", "42", "43", "44",
        "45", "46", "47", "48",
        "49",

        "51", "53", "54", "55",

        "61", "62", "63", "64",
        "65", "66", "67", "68",
        "69",

        "71", "73", "74", "75",
        "77", "79",

        "81", "82", "83", "84",
        "85", "86", "87", "88",
        "89",

        "91", "92", "93", "94",
        "95", "96", "97", "98",
        "99"

    }


    if telefone[:2] not in ddds_validos:

        return False


    # Depois do DDD,
    # celular brasileiro usa 9.

    if telefone[2] != "9":

        return False


    # Evita coisas como:
    # 11111111111

    if len(set(telefone)) == 1:

        return False


    # Também evita o número local
    # inteiro repetido.

    numero_local = telefone[2:]


    if len(set(numero_local)) == 1:

        return False


    return True


# ==========================================================
# AGENDAMENTO
# ==========================================================

@app.route(
    "/agendar",
    methods=[
        "GET",
        "POST"
    ]
)
def agendar():

    banco = conectar_banco()


    emerson = banco.execute("""
        SELECT *
        FROM barbeiros
        WHERE nome = ?
    """, (
        "Emerson",
    )).fetchone()


    servicos = banco.execute("""
        SELECT *
        FROM servicos
    """).fetchall()


    banco.close()


    barbeiro_id = emerson["id"]


    # ======================================================
    # POST
    # ======================================================

    if request.method == "POST":

        cliente = request.form.get(
            "cliente",
            ""
        ).strip()


        telefone = request.form.get(
            "telefone",
            ""
        ).strip()


        telefone_numeros = (
            normalizar_telefone(
                telefone
            )
        )


        servico_id = request.form.get(
            "servico"
        )


        data_agendamento = request.form.get(
            "data"
        )


        horario = request.form.get(
            "horario"
        )


        if (
            not cliente
            or
            not telefone
            or
            not servico_id
            or
            not data_agendamento
            or
            not horario
        ):

            return redirect(
                url_for(
                    "agendar"
                )
            )


        # ==================================================
        # VALIDAR TELEFONE
        # ==================================================

        if not telefone_brasileiro_plausivel(
            telefone_numeros
        ):

            return redirect(
                url_for(
                    "agendar",
                    servico=servico_id,
                    data=data_agendamento,
                    telefone_invalido="1"
                )
            )


        # ==================================================
        # CONFERE SE O HORÁRIO CONTINUA LIVRE
        # ==================================================

        horarios_livres = (
            buscar_horarios_disponiveis(
                barbeiro_id,
                data_agendamento
            )
        )


        if horario not in horarios_livres:

            return redirect(
                url_for(
                    "agendar",
                    data=data_agendamento,
                    servico=servico_id,
                    lotado="1"
                )
            )


        banco = conectar_banco()


        try:

            cursor = banco.execute("""
                INSERT INTO agendamentos (
                    cliente,
                    telefone,
                    barbeiro_id,
                    servico_id,
                    data,
                    horario,
                    status
                )

                VALUES (
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    'confirmado'
                )
            """, (

                cliente,
                telefone_numeros,
                barbeiro_id,
                servico_id,
                data_agendamento,
                horario

            ))


            banco.commit()


        except sqlite3.IntegrityError:

            banco.rollback()

            banco.close()


            return redirect(
                url_for(
                    "agendar",
                    data=data_agendamento,
                    servico=servico_id,
                    lotado="1"
                )
            )


        agendamento_id = (
            cursor.lastrowid
        )


        session[
            "telefone_cliente"
        ] = telefone_numeros


        banco.close()


        return redirect(
            url_for(
                "confirmacao",
                agendamento_id=
                    agendamento_id
            )
        )


    # ======================================================
    # GET
    # ======================================================

    servico_selecionado = (
        request.args.get(
            "servico",
            type=int
        )
    )


    data_selecionada = (
        request.args.get(
            "data"
        )
    )


    mostrar_lotado = (
        request.args.get(
            "lotado"
        )
        ==
        "1"
    )


    telefone_invalido = (
        request.args.get(
            "telefone_invalido"
        )
        ==
        "1"
    )


    calendario = criar_calendario(
        barbeiro_id
    )


    horarios = []

    dia_selecionado = None


    if data_selecionada:

        for dia in calendario:

            if (
                dia["data"]
                ==
                data_selecionada
            ):

                dia_selecionado = dia

                break


        if dia_selecionado:

            if (
                dia_selecionado[
                    "lotado"
                ]
            ):

                mostrar_lotado = True


            elif not dia_selecionado[
                "domingo"
            ]:

                horarios = (
                    buscar_horarios_disponiveis(
                        barbeiro_id,
                        data_selecionada
                    )
                )


    return render_template(

        "agendar.html",

        emerson=emerson,

        servicos=servicos,

        calendario=calendario,

        servico_selecionado=
            servico_selecionado,

        data_selecionada=
            data_selecionada,

        dia_selecionado=
            dia_selecionado,

        horarios=horarios,

        mostrar_lotado=
            mostrar_lotado,

        telefone_invalido=
            telefone_invalido,

        whatsapp=
            WHATSAPP_BARBEARIA

    )


# ==========================================================
# API - HORÁRIOS SEM RECARREGAR A PÁGINA
# ==========================================================

@app.route("/api/horarios")
def api_horarios():

    data_agendamento = request.args.get(
        "data",
        ""
    ).strip()


    try:

        data_objeto = datetime.strptime(
            data_agendamento,
            "%Y-%m-%d"
        ).date()


    except ValueError:

        return jsonify({

            "erro":
                "Data inválida.",

            "horarios":
                []

        }), 400


    if data_objeto < date.today():

        return jsonify({

            "erro":
                "Não é possível agendar em uma data passada.",

            "horarios":
                []

        }), 400


    if data_objeto.weekday() == 6:

        return jsonify({

            "erro":
                "A barbearia não abre aos domingos.",

            "horarios":
                [],

            "domingo":
                True,

            "lotado":
                False

        })


    banco = conectar_banco()


    emerson = banco.execute("""
        SELECT id
        FROM barbeiros
        WHERE nome = ?
    """, (
        "Emerson",
    )).fetchone()


    banco.close()


    if emerson is None:

        return jsonify({

            "erro":
                "Barbeiro não encontrado.",

            "horarios":
                []

        }), 404


    horarios = (
        buscar_horarios_disponiveis(
            emerson["id"],
            data_agendamento
        )
    )


    return jsonify({

        "data":
            data_agendamento,

        "horarios":
            horarios,

        "lotado":
            len(horarios) == 0,

        "domingo":
            False

    })


# ==========================================================
# CONFIRMAÇÃO
# ==========================================================

@app.route(
    "/confirmacao/<int:agendamento_id>"
)
def confirmacao(
    agendamento_id
):

    banco = conectar_banco()


    agendamento = banco.execute("""
        SELECT

            agendamentos.id,

            agendamentos.cliente,

            agendamentos.telefone,

            agendamentos.data,

            agendamentos.horario,

            barbeiros.nome
            AS barbeiro,

            servicos.nome
            AS servico,

            servicos.preco
            AS preco

        FROM agendamentos

        JOIN barbeiros
        ON agendamentos.barbeiro_id
        =
        barbeiros.id

        JOIN servicos
        ON agendamentos.servico_id
        =
        servicos.id

        WHERE agendamentos.id = ?
    """, (
        agendamento_id,
    )).fetchone()


    banco.close()


    if agendamento is None:

        return (
            "Agendamento não encontrado.",
            404
        )


    return render_template(
        "confirmacao.html",
        agendamento=agendamento
    )


# ==========================================================
# MEUS AGENDAMENTOS
# ==========================================================

@app.route(
    "/meus-agendamentos"
)
def meus_agendamentos():

    telefone = session.get(
        "telefone_cliente"
    )


    if not telefone:

        return redirect(
            url_for(
                "agendar"
            )
        )


    banco = conectar_banco()


    agendamentos = banco.execute("""
        SELECT

            agendamentos.id,

            agendamentos.data,

            agendamentos.horario,

            agendamentos.status,

            barbeiros.nome
            AS barbeiro,

            servicos.nome
            AS servico

        FROM agendamentos

        JOIN barbeiros
        ON agendamentos.barbeiro_id
        =
        barbeiros.id

        JOIN servicos
        ON agendamentos.servico_id
        =
        servicos.id

        WHERE agendamentos.telefone = ?

        ORDER BY
            agendamentos.data ASC,
            agendamentos.horario ASC
    """, (
        telefone,
    )).fetchall()


    banco.close()


    return render_template(
        "meus_agendamentos.html",
        agendamentos=agendamentos
    )


# ==========================================================
# ADMIN
# ==========================================================

@app.route("/admin")
def admin():

    banco = conectar_banco()


    agendamentos = banco.execute("""
        SELECT

            agendamentos.id,

            agendamentos.cliente,

            agendamentos.telefone,

            agendamentos.data,

            agendamentos.horario,

            agendamentos.status,

            barbeiros.nome
            AS barbeiro,

            servicos.nome
            AS servico

        FROM agendamentos

        JOIN barbeiros
        ON agendamentos.barbeiro_id
        =
        barbeiros.id

        JOIN servicos
        ON agendamentos.servico_id
        =
        servicos.id

        ORDER BY
            agendamentos.data ASC,
            agendamentos.horario ASC
    """).fetchall()


    banco.close()


    return render_template(
        "admin.html",
        agendamentos=agendamentos
    )


# ==========================================================
# RODAR
# ==========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000
    )