from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import socket, webbrowser, threading
from database import (init_db, init_projetos_db, autenticar, definir_senha,
                      listar_usuarios, cadastrar_usuario, atualizar_usuario, resetar_senha,
                      cadastrar_projeto, listar_projetos, buscar_projeto,
                      atribuir_etapa, listar_projetistas,
                      etapas_do_projetista, iniciar_etapa, pausar_etapa,
                      retomar_etapa, concluir_etapa, buscar_registros_etapa, buscar_etapa,
                      etapas_para_validar, validar_etapa,
                      projeto_gantt, relatorio_projetista, projetos_em_risco,
                      listar_projetos_fluxograma,
                      MOTIVOS_PARADA)
from functools import wraps

app = Flask(__name__)
app.secret_key = 'trael-engenharia-2024'

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'usuario' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'usuario' not in session:
            return redirect(url_for('login'))
        if session.get('perfil') not in ('admin', 'gestor'):
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated

def gestor_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'usuario' not in session:
            return redirect(url_for('login'))
        if session.get('perfil') != 'gestor':
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated

# ── Login ──────────────────────────────────────────────

@app.route('/', methods=['GET', 'POST'])
def login():
    if 'usuario' in session:
        return redirect(url_for('dashboard'))
    erro = None
    if request.method == 'POST':
        usuario = request.form.get('usuario','').strip().lower()
        senha   = request.form.get('senha','').strip()
        u, msg  = autenticar(usuario, senha)
        if msg == 'primeiro_acesso':
            session['temp_usuario'] = usuario
            return redirect(url_for('primeiro_acesso'))
        elif u:
            session['usuario'] = u['usuario']
            session['nome']    = u['nome']
            session['perfil']  = u['perfil']
            session['id']      = u['id']
            return redirect(url_for('dashboard'))
        else:
            erro = msg
    return render_template('login.html', erro=erro)

@app.route('/primeiro-acesso', methods=['GET', 'POST'])
def primeiro_acesso():
    usuario = session.get('temp_usuario')
    if not usuario:
        return redirect(url_for('login'))
    erro = None
    if request.method == 'POST':
        senha    = request.form.get('senha','').strip()
        confirma = request.form.get('confirma','').strip()
        if len(senha) < 6:
            erro = 'A senha deve ter pelo menos 6 caracteres.'
        elif senha != confirma:
            erro = 'As senhas não conferem.'
        else:
            definir_senha(usuario, senha)
            session.pop('temp_usuario', None)
            flash('Senha criada com sucesso! Faça login.', 'ok')
            return redirect(url_for('login'))
    return render_template('primeiro_acesso.html', usuario=usuario, erro=erro)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ── Dashboard ──────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    projetos     = listar_projetos()
    em_andamento = sum(1 for p in projetos if p['status'] == 'Em andamento')
    concluidos   = sum(1 for p in projetos if p['status'] == 'Concluído')
    minhas_etapas = etapas_do_projetista(session['id'])
    pendentes = [e for e in minhas_etapas if e['status'] in ('Pendente','Em andamento','Pausado')]
    em_risco  = projetos_em_risco() if session['perfil'] == 'gestor' else []
    aguard_val = etapas_para_validar() if session['perfil'] in ('admin','gestor') else []
    return render_template('dashboard.html',
                           nome=session['nome'], perfil=session['perfil'],
                           projetos=projetos, em_andamento=em_andamento,
                           concluidos=concluidos, minhas_etapas=pendentes,
                           em_risco=em_risco, aguard_validacao=len(aguard_val))

# ── Projetos ───────────────────────────────────────────

@app.route('/projetos/novo', methods=['GET', 'POST'])
@admin_required
def novo_projeto():
    if request.method == 'POST':
        dados = {k: request.form.get(k,'').strip() for k in
                 ['pcp','pedido','projeto','descricao','tipo',
                  'data_vsat','data_engenharia','previsao_liberacao']}
        if not all([dados['pedido'], dados['projeto'], dados['tipo']]):
            flash('Pedido, projeto e tipo são obrigatórios.', 'erro')
            return render_template('novo_projeto.html', nome=session['nome'], perfil=session['perfil'])
        pid = cadastrar_projeto(dados, session['usuario'])
        flash(f'Projeto {dados["projeto"]} cadastrado! Agora atribua as etapas.', 'ok')
        return redirect(url_for('atribuir_etapas', id=pid))
    return render_template('novo_projeto.html', nome=session['nome'], perfil=session['perfil'])

@app.route('/projetos/<int:id>/etapas', methods=['GET', 'POST'])
@admin_required
def atribuir_etapas(id):
    projeto, etapas = buscar_projeto(id)
    if not projeto:
        flash('Projeto não encontrado.', 'erro')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        for etapa in etapas:
            eid  = etapa['id']
            pid  = request.form.get(f'projetista_{eid}','')
            hrs  = request.form.get(f'horas_{eid}','')
            ativo = 1 if request.form.get(f'ativo_{eid}') else 0
            pnome = ''
            if pid:
                ps = listar_projetistas()
                p  = next((p for p in ps if str(p['id']) == pid), None)
                pnome = p['nome'] if p else ''
            try:
                horas = float(hrs) if hrs else None
            except:
                horas = None
            atribuir_etapa(eid, pid or None, pnome, horas, ativo)
        flash('Etapas atribuídas com sucesso!', 'ok')
        return redirect(url_for('dashboard'))
    projetistas = listar_projetistas()
    return render_template('atribuir_etapas.html', projeto=projeto, etapas=etapas,
                           projetistas=projetistas, nome=session['nome'], perfil=session['perfil'])

@app.route('/projetos/<int:id>')
@login_required
def ver_projeto(id):
    projeto, etapas = buscar_projeto(id)
    if not projeto:
        flash('Projeto não encontrado.', 'erro')
        return redirect(url_for('dashboard'))
    return render_template('ver_projeto.html', projeto=projeto, etapas=etapas,
                           nome=session['nome'], perfil=session['perfil'])

@app.route('/projetos/<int:id>/gantt')
@login_required
def gantt_projeto(id):
    projeto, etapas = projeto_gantt(id)
    if not projeto:
        flash('Projeto não encontrado.', 'erro')
        return redirect(url_for('dashboard'))
    return render_template('gantt.html', projeto=projeto, etapas=etapas,
                           nome=session['nome'], perfil=session['perfil'])

# ── Validação ──────────────────────────────────────────

@app.route('/validacao')
@admin_required
def validacao():
    etapas = etapas_para_validar()
    return render_template('validacao.html', etapas=etapas,
                           nome=session['nome'], perfil=session['perfil'])

@app.route('/validacao/<int:id>', methods=['POST'])
@admin_required
def fazer_validacao(id):
    aprovado = request.form.get('acao') == 'aprovar'
    obs      = request.form.get('observacao','').strip()
    validar_etapa(id, aprovado, session['nome'], obs)
    msg = 'Etapa aprovada!' if aprovado else 'Etapa rejeitada — voltou para o projetista.'
    flash(msg, 'ok' if aprovado else 'erro')
    return redirect(url_for('validacao'))

# ── Relatório do gestor ────────────────────────────────

@app.route('/relatorio')
@gestor_required
def relatorio():
    projetistas = relatorio_projetista()
    projetos    = listar_projetos()
    em_risco    = projetos_em_risco()
    return render_template('relatorio.html',
                           projetistas=projetistas, projetos=projetos,
                           em_risco=em_risco, nome=session['nome'], perfil=session['perfil'])

# ── Fluxograma ────────────────────────────────────────

@app.route('/fluxograma')
@admin_required
def fluxograma():
    projetos = listar_projetos_fluxograma()
    return render_template('fluxograma.html', projetos=projetos,
                           nome=session['nome'], perfil=session['perfil'])

# ── Tela do projetista ─────────────────────────────────

@app.route('/minhas-atividades')
@login_required
def minhas_atividades():
    etapas = etapas_do_projetista(session['id'])
    return render_template('minhas_atividades.html', etapas=etapas,
                           nome=session['nome'], perfil=session['perfil'],
                           motivos=MOTIVOS_PARADA)

@app.route('/etapa/<int:id>')
@login_required
def ver_etapa(id):
    etapa = buscar_etapa(id)
    if not etapa or etapa['projetista_id'] != session['id']:
        flash('Atividade não encontrada.', 'erro')
        return redirect(url_for('minhas_atividades'))
    registros = buscar_registros_etapa(id)
    return render_template('ver_etapa.html', etapa=etapa, registros=registros,
                           nome=session['nome'], perfil=session['perfil'],
                           motivos=MOTIVOS_PARADA)

@app.route('/etapa/<int:id>/iniciar', methods=['POST'])
@login_required
def iniciar(id):
    etapa = buscar_etapa(id)
    if etapa and etapa['projetista_id'] == session['id']:
        iniciar_etapa(id)
        flash('Atividade iniciada!', 'ok')
    return redirect(url_for('ver_etapa', id=id))

@app.route('/etapa/<int:id>/pausar', methods=['POST'])
@login_required
def pausar(id):
    etapa = buscar_etapa(id)
    if etapa and etapa['projetista_id'] == session['id']:
        motivo = request.form.get('motivo','')
        obs    = request.form.get('observacao','')
        if not motivo:
            flash('Selecione o motivo da parada.', 'erro')
            return redirect(url_for('ver_etapa', id=id))
        pausar_etapa(id, motivo, obs)
        flash(f'Atividade pausada: {motivo}', 'ok')
    return redirect(url_for('ver_etapa', id=id))

@app.route('/etapa/<int:id>/retomar', methods=['POST'])
@login_required
def retomar(id):
    etapa = buscar_etapa(id)
    if etapa and etapa['projetista_id'] == session['id']:
        retomar_etapa(id)
        flash('Atividade retomada!', 'ok')
    return redirect(url_for('ver_etapa', id=id))

@app.route('/etapa/<int:id>/concluir', methods=['POST'])
@login_required
def concluir(id):
    etapa = buscar_etapa(id)
    if etapa and etapa['projetista_id'] == session['id']:
        obs = request.form.get('observacao','')
        concluir_etapa(id, obs)
        flash('Atividade concluída! Aguardando validação.', 'ok')
    return redirect(url_for('minhas_atividades'))

# ── Usuários ───────────────────────────────────────────

@app.route('/usuarios')
@admin_required
def usuarios():
    lista = listar_usuarios()
    return render_template('usuarios.html', usuarios=lista,
                           nome=session['nome'], perfil=session['perfil'])

@app.route('/usuarios/novo', methods=['POST'])
@admin_required
def novo_usuario():
    nome    = request.form.get('nome','').strip()
    usuario = request.form.get('usuario','').strip().lower()
    perfil  = request.form.get('perfil','projetista')
    if not nome or not usuario:
        flash('Nome e usuário são obrigatórios.', 'erro')
        return redirect(url_for('usuarios'))
    ok, msg = cadastrar_usuario(nome, usuario, perfil)
    flash(f'Usuário "{nome}" cadastrado.' if ok else msg, 'ok' if ok else 'erro')
    return redirect(url_for('usuarios'))

@app.route('/usuarios/editar/<int:id>', methods=['POST'])
@admin_required
def editar_usuario(id):
    nome   = request.form.get('nome','').strip()
    perfil = request.form.get('perfil','projetista')
    ativo  = 1 if request.form.get('ativo') else 0
    atualizar_usuario(id, nome, perfil, ativo)
    flash('Usuário atualizado.', 'ok')
    return redirect(url_for('usuarios'))

@app.route('/usuarios/resetar/<int:id>', methods=['POST'])
@admin_required
def resetar(id):
    resetar_senha(id)
    flash('Senha resetada.', 'ok')
    return redirect(url_for('usuarios'))

# ── Inicialização ──────────────────────────────────────

def abrir_navegador():
    import time; time.sleep(1.2)
    webbrowser.open('http://localhost:5000')

if __name__ == '__main__':
    init_db()
    init_projetos_db()
    ip = socket.gethostbyname(socket.gethostname())
    print("\n" + "="*55)
    print("  TRAEL — Sistema de Gestão de Projetos")
    print("="*55)
    print(f"  Este computador: http://localhost:5000")
    print(f"  Rede interna:    http://{ip}:5000")
    print("  CTRL+C para encerrar")
    print("="*55)
    print("\n  Logins: vinicius / kamila → senha: trael2024")
    print("  Projetistas → criam senha no primeiro acesso\n")
    threading.Thread(target=abrir_navegador, daemon=True).start()
    app.run(host='0.0.0.0', port=5000, debug=False)
  # Inicializa o banco quando rodando via Gunicorn
init_db()
init_projetos_db()
