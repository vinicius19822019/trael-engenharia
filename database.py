import sqlite3, hashlib, os
from datetime import datetime

# No Railway: defina a variável de ambiente DB_PATH para um Volume montado,
# ex: /data/trael.db  — em desenvolvimento local usa o diretório atual.
DB_FILE = os.environ.get('DB_PATH', 'trael.db')

# Garante que o diretório existe (importante quando DB_PATH aponta para /data/)
os.makedirs(os.path.dirname(DB_FILE) if os.path.dirname(DB_FILE) else '.', exist_ok=True)

MOTIVOS_PARADA = [
    # Pausas pessoais
    'Banheiro',
    'Água / Lanche',
    'Almoço',
    'Início de expediente',
    'Fim de expediente',
    # Problemas externos
    'Problema em fábrica',
    'Aguardando dados do cliente',
    'Aguardando definição de engenharia',
    'Aguardando aprovação interna',
    # Recursos
    'Falta de material / componente',
    'Problema com software / sistema',
    # Pessoas
    'Reunião',
    'Treinamento',
    'Ausência / atestado',
    'Férias',
    # Processo
    'Retrabalho — erro identificado',
    'Revisão de projeto urgente',
    'Etapa anterior não concluída',
    'Prioridade alterada — outro projeto urgente',
    'Revisão solicitada pela gestão',
]

ETAPAS_NOVO = [
    'Check List Tarefas',
    'Cálculo',
    'Caderno de Aprovação',
    'Lista de Materiais Críticos',
    'Desenho de Enrolamento',
    'Controle do Desenho de Enrolamento',
    'Desenho Mecânico',
    'Controle do Desenho Mecânico',
    'Montagem da Epro',
    'Cadastro da Epro no Vsat',
    'Controle da Epro e do Cadastro no Vsat',
    'Envio de E-mail',
]

ETAPAS_REVISAO = [
    'Desenho de Revisão',
    'Controle do Desenho de Revisão',
    'Revisão de Cadastro',
    'Envio de E-mail',
]

ETAPAS_OPCIONAIS = ['Caderno de Aprovação', 'Lista de Materiais Críticos']

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        usuario TEXT UNIQUE NOT NULL,
        senha_hash TEXT,
        perfil TEXT NOT NULL,
        primeiro_acesso INTEGER DEFAULT 1,
        ativo INTEGER DEFAULT 1,
        criado_em TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    # Gestor
    c.execute("SELECT id FROM usuarios WHERE usuario='vinicius'")
    if not c.fetchone():
        c.execute('''INSERT INTO usuarios (nome, usuario, senha_hash, perfil, primeiro_acesso)
                     VALUES (?,?,?,?,0)''',
                  ('Vinicius', 'vinicius', hash_senha('trael2024'), 'gestor'))

    # Admin + projetista
    c.execute("SELECT id FROM usuarios WHERE usuario='kamila'")
    if not c.fetchone():
        c.execute('''INSERT INTO usuarios (nome, usuario, senha_hash, perfil, primeiro_acesso)
                     VALUES (?,?,?,?,0)''',
                  ('Kamila', 'kamila', hash_senha('trael2024'), 'admin'))

    projetistas = [
        'Juventino','Nicolas','Vitória','Lettícia',
        'Ebert','Brena','Larissa','Alice','Lucas','Lyncoln'
    ]
    for nome in projetistas:
        usuario = nome.lower().replace('í','i').replace('ó','o').replace('é','e').replace('â','a').replace('ã','a')
        c.execute("SELECT id FROM usuarios WHERE usuario=?", (usuario,))
        if not c.fetchone():
            c.execute('''INSERT INTO usuarios (nome, usuario, senha_hash, perfil, primeiro_acesso)
                         VALUES (?,?,NULL,'projetista',1)''', (nome, usuario))

    conn.commit()
    conn.close()

def init_projetos_db():
    conn = get_db()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS projetos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pcp TEXT,
        pedido TEXT NOT NULL,
        projeto TEXT NOT NULL,
        descricao TEXT,
        tipo TEXT NOT NULL,
        data_vsat TEXT,
        data_engenharia TEXT,
        previsao_liberacao TEXT,
        status TEXT DEFAULT 'Em andamento',
        criado_por TEXT,
        criado_em TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    try:
        c.execute("ALTER TABLE projetos ADD COLUMN descricao TEXT")
    except:
        pass

    c.execute('''CREATE TABLE IF NOT EXISTS etapas_projeto (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        projeto_id INTEGER NOT NULL,
        nome TEXT NOT NULL,
        opcional INTEGER DEFAULT 0,
        ativo INTEGER DEFAULT 1,
        projetista_id INTEGER,
        projetista_nome TEXT,
        previsao_horas REAL,
        status TEXT DEFAULT 'Pendente',
        inicio_em TEXT,
        fim_em TEXT,
        horas_trabalhadas REAL,
        horas_paradas REAL,
        observacao TEXT,
        validado INTEGER DEFAULT 0,
        validado_por TEXT,
        validado_em TEXT,
        criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (projeto_id) REFERENCES projetos(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS registros_atividade (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        etapa_id INTEGER NOT NULL,
        tipo TEXT NOT NULL,
        motivo_parada TEXT,
        observacao TEXT,
        registrado_em TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (etapa_id) REFERENCES etapas_projeto(id)
    )''')

    novas_colunas_etapas = [
        ("inicio_em", "TEXT"),
        ("fim_em", "TEXT"),
        ("horas_trabalhadas", "REAL"),
        ("horas_paradas", "REAL"),
        ("observacao", "TEXT"),
        ("validado", "INTEGER DEFAULT 0"),
        ("validado_por", "TEXT"),
        ("validado_em", "TEXT"),
    ]
    for col, tipo in novas_colunas_etapas:
        try:
            c.execute(f"ALTER TABLE etapas_projeto ADD COLUMN {col} {tipo}")
        except:
            pass

    conn.commit()
    conn.close()

# ── Usuários ───────────────────────────────────────────

def autenticar(usuario, senha):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM usuarios WHERE usuario=? AND ativo=1", (usuario,))
    u = c.fetchone()
    conn.close()
    if not u:
        return None, 'Usuário não encontrado.'
    if u['primeiro_acesso']:
        return None, 'primeiro_acesso'
    if u['senha_hash'] != hash_senha(senha):
        return None, 'Senha incorreta.'
    return dict(u), None

def definir_senha(usuario, senha):
    conn = get_db()
    conn.execute('UPDATE usuarios SET senha_hash=?, primeiro_acesso=0 WHERE usuario=?',
                 (hash_senha(senha), usuario))
    conn.commit()
    conn.close()

def listar_usuarios():
    conn = get_db()
    rows = conn.execute("SELECT * FROM usuarios ORDER BY perfil, nome").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def cadastrar_usuario(nome, usuario, perfil):
    conn = get_db()
    try:
        conn.execute('INSERT INTO usuarios (nome, usuario, perfil, primeiro_acesso) VALUES (?,?,?,1)',
                     (nome, usuario, perfil))
        conn.commit()
        conn.close()
        return True, None
    except sqlite3.IntegrityError:
        conn.close()
        return False, f'Usuário "{usuario}" já existe.'

def atualizar_usuario(id, nome, perfil, ativo):
    conn = get_db()
    conn.execute('UPDATE usuarios SET nome=?, perfil=?, ativo=? WHERE id=?',
                 (nome, perfil, ativo, id))
    conn.commit()
    conn.close()

def resetar_senha(id):
    conn = get_db()
    conn.execute('UPDATE usuarios SET senha_hash=NULL, primeiro_acesso=1 WHERE id=?', (id,))
    conn.commit()
    conn.close()

# ── Projetos ───────────────────────────────────────────

def cadastrar_projeto(dados, criado_por):
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO projetos
                 (pcp, pedido, projeto, descricao, tipo, data_vsat, data_engenharia, previsao_liberacao, criado_por)
                 VALUES (?,?,?,?,?,?,?,?,?)''',
              (dados['pcp'], dados['pedido'], dados['projeto'], dados['descricao'],
               dados['tipo'], dados['data_vsat'], dados['data_engenharia'],
               dados['previsao_liberacao'], criado_por))
    pid = c.lastrowid

    etapas = ETAPAS_NOVO if dados['tipo'] == 'Projeto Novo' else ETAPAS_REVISAO
    for nome in etapas:
        opcional = 1 if nome in ETAPAS_OPCIONAIS else 0
        c.execute('''INSERT INTO etapas_projeto (projeto_id, nome, opcional, ativo)
                     VALUES (?,?,?,1)''', (pid, nome, opcional))

    conn.commit()
    conn.close()
    return pid

def listar_projetos():
    conn = get_db()
    rows = conn.execute('''
        SELECT p.*,
               COUNT(CASE WHEN e.ativo=1 THEN 1 END) as total_etapas,
               SUM(CASE WHEN e.status='Concluído' AND e.ativo=1 THEN 1 ELSE 0 END) as etapas_concluidas
        FROM projetos p
        LEFT JOIN etapas_projeto e ON e.projeto_id = p.id
        GROUP BY p.id
        ORDER BY p.id DESC
    ''').fetchall()
    conn.close()
    return [dict(r) for r in rows]

def buscar_projeto(pid):
    conn = get_db()
    p = conn.execute("SELECT * FROM projetos WHERE id=?", (pid,)).fetchone()
    etapas = conn.execute('''
        SELECT e.*, u.nome as projetista_nome
        FROM etapas_projeto e
        LEFT JOIN usuarios u ON u.id = e.projetista_id
        WHERE e.projeto_id=?
        ORDER BY e.id
    ''', (pid,)).fetchall()
    conn.close()
    return (dict(p) if p else None), [dict(e) for e in etapas]

def listar_projetistas():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, nome FROM usuarios WHERE ativo=1 ORDER BY nome"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def atribuir_etapa(etapa_id, projetista_id, projetista_nome, horas, ativo):
    conn = get_db()
    conn.execute('''UPDATE etapas_projeto
                    SET projetista_id=?, projetista_nome=?, previsao_horas=?, ativo=?
                    WHERE id=?''',
                 (projetista_id, projetista_nome, horas, ativo, etapa_id))
    conn.commit()
    conn.close()

# ── Atividades do projetista ───────────────────────────

def etapas_do_projetista(usuario_id):
    conn = get_db()
    rows = conn.execute('''
        SELECT e.*, p.pedido, p.projeto, p.pcp, p.previsao_liberacao
        FROM etapas_projeto e
        JOIN projetos p ON p.id = e.projeto_id
        WHERE e.projetista_id=? AND e.ativo=1
        ORDER BY p.previsao_liberacao ASC, e.id ASC
    ''', (usuario_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def iniciar_etapa(etapa_id):
    agora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db()
    conn.execute('''UPDATE etapas_projeto SET status='Em andamento', inicio_em=?
                    WHERE id=? AND status='Pendente' ''', (agora, etapa_id))
    conn.execute('''INSERT INTO registros_atividade (etapa_id, tipo, registrado_em)
                    VALUES (?,?,?)''', (etapa_id, 'inicio', agora))
    conn.commit()
    conn.close()
    return agora

def pausar_etapa(etapa_id, motivo, observacao=''):
    agora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db()
    conn.execute('''UPDATE etapas_projeto SET status='Pausado' WHERE id=?''', (etapa_id,))
    conn.execute('''INSERT INTO registros_atividade (etapa_id, tipo, motivo_parada, observacao, registrado_em)
                    VALUES (?,?,?,?,?)''', (etapa_id, 'parada', motivo, observacao, agora))
    conn.commit()
    conn.close()
    return agora

def retomar_etapa(etapa_id):
    agora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db()

    ultima_parada = conn.execute('''
        SELECT registrado_em FROM registros_atividade
        WHERE etapa_id=? AND tipo='parada'
        ORDER BY id DESC LIMIT 1
    ''', (etapa_id,)).fetchone()

    if ultima_parada:
        dt_parada = datetime.strptime(ultima_parada['registrado_em'], '%Y-%m-%d %H:%M:%S')
        dt_agora  = datetime.strptime(agora, '%Y-%m-%d %H:%M:%S')
        horas_parada = (dt_agora - dt_parada).total_seconds() / 3600

        etapa = conn.execute('SELECT horas_paradas FROM etapas_projeto WHERE id=?', (etapa_id,)).fetchone()
        total_paradas = (etapa['horas_paradas'] or 0) + horas_parada
        conn.execute('UPDATE etapas_projeto SET horas_paradas=? WHERE id=?', (total_paradas, etapa_id))

    conn.execute('UPDATE etapas_projeto SET status=? WHERE id=?', ('Em andamento', etapa_id))
    conn.execute('''INSERT INTO registros_atividade (etapa_id, tipo, registrado_em)
                    VALUES (?,?,?)''', (etapa_id, 'retomada', agora))
    conn.commit()
    conn.close()
    return agora

def concluir_etapa(etapa_id, observacao):
    agora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db()
    etapa = conn.execute('SELECT * FROM etapas_projeto WHERE id=?', (etapa_id,)).fetchone()

    horas_trabalhadas = 0
    if etapa['inicio_em']:
        dt_inicio = datetime.strptime(etapa['inicio_em'], '%Y-%m-%d %H:%M:%S')
        dt_agora  = datetime.strptime(agora, '%Y-%m-%d %H:%M:%S')
        total = (dt_agora - dt_inicio).total_seconds() / 3600
        horas_trabalhadas = round(total - (etapa['horas_paradas'] or 0), 2)

    conn.execute('''UPDATE etapas_projeto
                    SET status='Concluído', fim_em=?, horas_trabalhadas=?, observacao=?
                    WHERE id=?''', (agora, horas_trabalhadas, observacao, etapa_id))
    conn.execute('''INSERT INTO registros_atividade (etapa_id, tipo, observacao, registrado_em)
                    VALUES (?,?,?,?)''', (etapa_id, 'conclusao', observacao, agora))
    conn.commit()
    conn.close()
    return agora

def buscar_registros_etapa(etapa_id):
    conn = get_db()
    rows = conn.execute('''SELECT * FROM registros_atividade
                           WHERE etapa_id=? ORDER BY id''', (etapa_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def buscar_etapa(etapa_id):
    conn = get_db()
    e = conn.execute('''
        SELECT e.*, p.pedido, p.projeto, p.descricao, p.pcp, p.previsao_liberacao
        FROM etapas_projeto e
        JOIN projetos p ON p.id = e.projeto_id
        WHERE e.id=?
    ''', (etapa_id,)).fetchone()
    conn.close()
    return dict(e) if e else None

# ── Validação ──────────────────────────────────────────

def etapas_para_validar():
    conn = get_db()
    rows = conn.execute('''
        SELECT e.*, p.pedido, p.projeto, p.pcp, p.previsao_liberacao
        FROM etapas_projeto e
        JOIN projetos p ON p.id = e.projeto_id
        WHERE e.status='Concluído' AND e.validado=0 AND e.ativo=1
        ORDER BY e.fim_em ASC
    ''').fetchall()
    conn.close()
    return [dict(r) for r in rows]

def validar_etapa(etapa_id, aprovado, validado_por, obs=''):
    agora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db()
    if aprovado:
        conn.execute('''UPDATE etapas_projeto
                        SET validado=1, validado_por=?, validado_em=?
                        WHERE id=?''', (validado_por, agora, etapa_id))
        conn.execute('''INSERT INTO registros_atividade (etapa_id, tipo, observacao, registrado_em)
                        VALUES (?,?,?,?)''', (etapa_id, 'validacao', f'Aprovado por {validado_por}. {obs}', agora))
        etapa = conn.execute('SELECT projeto_id FROM etapas_projeto WHERE id=?', (etapa_id,)).fetchone()
        pendentes = conn.execute('''SELECT COUNT(*) as n FROM etapas_projeto
                                    WHERE projeto_id=? AND ativo=1
                                    AND (status != 'Concluído' OR validado=0)''',
                                 (etapa['projeto_id'],)).fetchone()
        if pendentes['n'] == 0:
            conn.execute("UPDATE projetos SET status='Concluído' WHERE id=?", (etapa['projeto_id'],))
    else:
        conn.execute('''UPDATE etapas_projeto SET status='Pendente', inicio_em=NULL,
                        fim_em=NULL, horas_trabalhadas=NULL, horas_paradas=NULL
                        WHERE id=?''', (etapa_id,))
        conn.execute('''INSERT INTO registros_atividade (etapa_id, tipo, observacao, registrado_em)
                        VALUES (?,?,?,?)''', (etapa_id, 'rejeicao', f'Rejeitado por {validado_por}. {obs}', agora))
    conn.commit()
    conn.close()

# ── Relatórios / Gantt ─────────────────────────────────

def projeto_gantt(projeto_id):
    conn = get_db()
    p = conn.execute("SELECT * FROM projetos WHERE id=?", (projeto_id,)).fetchone()
    etapas = conn.execute('''
        SELECT e.*, u.nome as nome_projetista
        FROM etapas_projeto e
        LEFT JOIN usuarios u ON u.id = e.projetista_id
        WHERE e.projeto_id=? AND e.ativo=1
        ORDER BY e.id
    ''', (projeto_id,)).fetchall()
    conn.close()
    if not p:
        return None, []
    return dict(p), [dict(e) for e in etapas]

def relatorio_projetista():
    conn = get_db()
    rows = conn.execute('''
        SELECT u.nome, u.id,
               COUNT(e.id) as total_etapas,
               SUM(CASE WHEN e.status='Concluído' THEN 1 ELSE 0 END) as concluidas,
               SUM(CASE WHEN e.status='Em andamento' THEN 1 ELSE 0 END) as andamento,
               SUM(CASE WHEN e.status='Pausado' THEN 1 ELSE 0 END) as pausadas,
               ROUND(SUM(COALESCE(e.horas_trabalhadas,0)),1) as total_horas,
               ROUND(SUM(COALESCE(e.horas_paradas,0)),1) as total_paradas,
               ROUND(SUM(COALESCE(e.previsao_horas,0)),1) as total_previsto
        FROM usuarios u
        LEFT JOIN etapas_projeto e ON e.projetista_id = u.id AND e.ativo=1
        WHERE u.perfil IN ('projetista','admin','gestor') AND u.ativo=1
        GROUP BY u.id
        ORDER BY u.nome
    ''').fetchall()

    paradas = conn.execute('''
        SELECT e.projetista_id, r.motivo_parada, COUNT(*) as qtd
        FROM registros_atividade r
        JOIN etapas_projeto e ON e.id = r.etapa_id
        WHERE r.tipo='parada' AND r.motivo_parada IS NOT NULL
        GROUP BY e.projetista_id, r.motivo_parada
        ORDER BY qtd DESC
    ''').fetchall()

    conn.close()
    paradas_map = {}
    for p in paradas:
        pid = p['projetista_id']
        if pid not in paradas_map:
            paradas_map[pid] = []
        paradas_map[pid].append({'motivo': p['motivo_parada'], 'qtd': p['qtd']})

    result = []
    for r in rows:
        d = dict(r)
        d['paradas_detalhes'] = paradas_map.get(r['id'], [])[:5]
        result.append(d)
    return result

def listar_projetos_fluxograma():
    conn = get_db()
    projetos = conn.execute("""SELECT * FROM projetos ORDER BY previsao_liberacao ASC, id DESC""").fetchall()
    resultado = []
    for p in projetos:
        etapas = conn.execute("""SELECT e.*, u.nome as projetista_nome FROM etapas_projeto e LEFT JOIN usuarios u ON u.id = e.projetista_id WHERE e.projeto_id = ? ORDER BY e.id""", (p["id"],)).fetchall()
        d = dict(p)
        d["etapas"] = [dict(e) for e in etapas]
        resultado.append(d)
    conn.close()
    return resultado

def projetos_em_risco():
    from datetime import date
    conn = get_db()
    hoje = date.today().isoformat()
    rows = conn.execute('''
        SELECT p.*,
               COUNT(CASE WHEN e.ativo=1 THEN 1 END) as total_etapas,
               SUM(CASE WHEN e.status='Concluído' AND e.ativo=1 THEN 1 ELSE 0 END) as concluidas
        FROM projetos p
        LEFT JOIN etapas_projeto e ON e.projeto_id = p.id
        WHERE p.status='Em andamento'
        GROUP BY p.id
    ''').fetchall()
    conn.close()
    em_risco = []
    for r in rows:
        d = dict(r)
        if d['previsao_liberacao'] and d['previsao_liberacao'] <= hoje:
            d['risco'] = 'atrasado'
            em_risco.append(d)
        elif d['previsao_liberacao']:
            from datetime import datetime
            dias = (datetime.strptime(d['previsao_liberacao'], '%Y-%m-%d').date() - date.today()).days
            if dias <= 3:
                d['risco'] = 'critico'
                em_risco.append(d)
            elif dias <= 7:
                d['risco'] = 'atencao'
                em_risco.append(d)
    return em_risco
