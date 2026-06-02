#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
 Sistema Inteligente de Tutoria e Adaptacao Curricular (EAD)
 Protótipo funcional de um Sistema Multiagente (SMA)
=============================================================================

Implementa os quatro agentes descritos no relatório técnico:

    - Agente Aluno (Perfil)      : monitora e modela o estado do estudante
    - Agente Tutor (Pedagógico)  : decide topico, dificuldade e metodologia
    - Agente de Conteúdo         : fornece materiais didáticos sob demanda
    - Agente de Avaliação        : aplica testes adaptativos e mede desempenho

Os agentes se comunicam por mensagens estruturadas (JSON) trafegadas em um
Barramento de Mensagens (camada de integração). A coordenação é
descentralizada e a cooperação é total (objetivo comum: o aprendizado).

O protótipo inclui um EXPERIMENTO que compara o método ADAPTATIVO (SMA)
contra um método LINEAR (tradicional, sem adaptação), gerando os dados
para as tabelas e gráficos do artigo.

Execução:
    python3 sistema_tutoria_sma.py              # experimento completo
    python3 sistema_tutoria_sma.py --demo       # 1 aluno, com log das mensagens
    python3 sistema_tutoria_sma.py --graficos   # tambem gera os PNGs (matplotlib)

Dependências: apenas a biblioteca padrão do Python (>=3.8).
Os gráficos são opcionais e usam matplotlib, se instalado.

Autor: (preencher) - Ciência da Computação - IESB
=============================================================================
"""

import json
import math
import random
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


# ===========================================================================
# 1. BARRAMENTO DE MENSAGENS  (Camada de Integração)
#    Implementa a comunicação por troca de mensagens JSON entre os agentes.
# ===========================================================================
class BarramentoMensagens:
    """Barramento simples: cada agente possui uma caixa de entrada (mailbox).

    Uma mensagem é um dicionário serializável em JSON com o formato:
        {"de": ..., "para": ..., "tipo": ..., "conteudo": {...}}
    """

    def __init__(self, registrar_log: bool = False):
        self.caixas: Dict[str, List[dict]] = {}
        self.registrar_log = registrar_log
        self.log: List[str] = []

    def registrar_agente(self, nome: str) -> None:
        self.caixas.setdefault(nome, [])

    def enviar(self, de: str, para: str, tipo: str, conteudo: dict) -> None:
        msg = {"de": de, "para": para, "tipo": tipo, "conteudo": conteudo}
        self.caixas.setdefault(para, []).append(msg)
        if self.registrar_log:
            # serializa em JSON para evidenciar a natureza estruturada da troca
            self.log.append(json.dumps(msg, ensure_ascii=False))

    def receber(self, nome: str) -> List[dict]:
        msgs = self.caixas.get(nome, [])
        self.caixas[nome] = []
        return msgs


# ===========================================================================
# 2. BANCO DE CONTEÚDO  (Camada de Dados)
#    Define a estrutura curricular do curso e os materiais disponíveis.
# ===========================================================================
# Curso de exemplo: "Lógica de Programação", com 6 tópicos em ordem de
# pré-requisito. Cada tópico tem dificuldade intrínseca crescente.
TOPICOS = [
    {"id": 0, "nome": "Variáveis e Tipos",      "dificuldade": 0.20},
    {"id": 1, "nome": "Operadores",             "dificuldade": 0.30},
    {"id": 2, "nome": "Estruturas Condicionais", "dificuldade": 0.45},
    {"id": 3, "nome": "Laços de Repetição",      "dificuldade": 0.60},
    {"id": 4, "nome": "Funções",                 "dificuldade": 0.72},
    {"id": 5, "nome": "Vetores e Listas",        "dificuldade": 0.85},
]

# Metodologias didáticas disponíveis para cada material.
METODOLOGIAS = ["texto", "video", "exercicio_guiado", "estudo_de_caso"]


class AgenteConteudo:
    """Agente de Conteúdo  -  Classificação: agente REATIVO SIMPLES.

    Reage diretamente a uma requisição (percepção) devolvendo o material que
    casa com (tópico, nível de dificuldade, metodologia). Não mantém estado
    interno sobre o aluno: regra condição-ação pura.
    """

    NOME = "AgenteConteudo"

    def __init__(self, barramento: BarramentoMensagens):
        self.bus = barramento
        self.bus.registrar_agente(self.NOME)

    def processar(self) -> None:
        for msg in self.bus.receber(self.NOME):
            if msg["tipo"] == "REQUISITAR_CONTEUDO":
                c = msg["conteudo"]
                material = {
                    "topico_id": c["topico_id"],
                    "topico_nome": TOPICOS[c["topico_id"]]["nome"],
                    "dificuldade": round(c["dificuldade"], 2),
                    "metodologia": c["metodologia"],
                    "id_material": f"M{c['topico_id']}-{c['metodologia']}-{int(c['dificuldade']*100)}",
                }
                # regra reativa: percebeu requisição -> entrega material
                self.bus.enviar(self.NOME, msg["de"], "CONTEUDO_ENTREGUE", material)


# ===========================================================================
# 3. SIMULADOR DO ALUNO REAL  (o "Ambiente" sob o ponto de vista dos agentes)
#    Mantém o estado VERDADEIRO e OCULTO do estudante. Os agentes só o
#    percebem indiretamente (ambiente parcialmente observável).
# ===========================================================================
class AlunoSimulado:
    """Modela o aprendizado real do estudante de forma probabilística.

    Conceitos pedagógicos embutidos (Zona de Desenvolvimento Proximal):
      - O ganho de aprendizado é máximo quando a dificuldade do material está
        um pouco ACIMA da proficiência atual ("ponto ótimo").
      - Material fácil demais  -> tédio  -> queda de engajamento.
      - Material difícil demais -> frustração -> queda de engajamento.
      - Engajamento muito baixo  -> risco de EVASÃO.

    Esse modelo conecta diretamente os três problemas citados no relatório:
    desengajamento, evasão e baixo desempenho.
    """

    GANHO_IDEAL = 0.12   # distância ideal (dificuldade - proficiência)
    SIGMA = 0.18         # tolerância em torno do ponto ótimo

    def __init__(self, taxa_aprendizado: float, engajamento_inicial: float,
                 seed: Optional[int] = None):
        self.rng = random.Random(seed)
        # proficiência verdadeira por tópico (inicia baixa)
        self.proficiencia = [self.rng.uniform(0.0, 0.15) for _ in TOPICOS]
        self.taxa_aprendizado = taxa_aprendizado
        self.engajamento = engajamento_inicial
        self.evadiu = False
        # sensores de comportamento acumulados
        self.tempo_total = 0.0
        self.cliques = 0

    # --- efeito de estudar um material -------------------------------------
    def estudar(self, topico_id: int, dificuldade: float, metodologia: str) -> dict:
        """Atualiza a proficiência e o engajamento após estudar um material.

        - 'dificuldade' é a dificuldade do MATERIAL, na mesma escala [0,1] da
          proficiência. O ganho é máximo quando ela está ~GANHO_IDEAL acima
          da proficiência atual (Zona de Desenvolvimento Proximal).
        - A dificuldade INTRÍNSECA do tópico modula a VELOCIDADE de aprendizado:
          tópicos mais avançados são aprendidos mais lentamente.
        """
        p = self.proficiencia[topico_id]
        gap = dificuldade - p
        # eficácia gaussiana centrada no ganho ideal (ZDP)
        eficacia = math.exp(-((gap - self.GANHO_IDEAL) ** 2) / (2 * self.SIGMA ** 2))

        # ganho de proficiência: modulado pela dificuldade intrínseca do tópico
        fator_topico = 1 - 0.5 * TOPICOS[topico_id]["dificuldade"]
        ganho = self.taxa_aprendizado * eficacia * (1 - p) * fator_topico
        self.proficiencia[topico_id] = min(1.0, p + ganho)

        # dinâmica de engajamento
        if eficacia > 0.55:        # material no ponto ótimo -> motivação
            self.engajamento = min(1.0, self.engajamento + 0.05)
        elif gap < -0.08:          # fácil demais -> tédio
            self.engajamento = max(0.0, self.engajamento - 0.05)
        else:                      # difícil demais -> frustração
            self.engajamento = max(0.0, self.engajamento - 0.08)

        if self.engajamento < 0.18 and self.rng.random() < 0.15:
            self.evadiu = True

        # sensores: tempo de tela e cliques observáveis pelos agentes
        tempo = self.rng.uniform(8, 15) * (0.5 + self.engajamento)
        self.tempo_total += tempo
        self.cliques += int(self.rng.uniform(3, 9) * (0.5 + self.engajamento))

        return {"tempo_tela": round(tempo, 1), "engajamento_obs": round(self.engajamento, 2)}

    # --- responder a uma questão de avaliação ------------------------------
    def responder(self, topico_id: int, dificuldade_questao: float) -> int:
        """Probabilidade de acerto via modelo logístico (estilo IRT):
        P(acerto) = sigmoide( k * (proficiencia - dificuldade) )."""
        k = 6.0
        p = self.proficiencia[topico_id]
        prob = 1 / (1 + math.exp(-k * (p - dificuldade_questao)))
        return 1 if self.rng.random() < prob else 0


# ===========================================================================
# 4. AGENTE ALUNO (PERFIL)
#    Classificação: REATIVO SIMPLES com elementos de AGENTE BASEADO EM MODELO.
#    Mantém o MODELO ESTIMADO do aluno (diferente do estado oculto real).
# ===========================================================================
class AgentePerfil:
    NOME = "AgentePerfil"

    def __init__(self, barramento: BarramentoMensagens):
        self.bus = barramento
        self.bus.registrar_agente(self.NOME)
        # crença (estimativa) sobre a proficiência em cada tópico
        self.proficiencia_estimada = [0.1 for _ in TOPICOS]
        self.engajamento_estimado = 0.7
        self.historico_tempo: List[float] = []

    def processar(self) -> None:
        for msg in self.bus.receber(self.NOME):
            c = msg["conteudo"]
            if msg["tipo"] == "PERCEPCAO_COMPORTAMENTO":
                # atualiza o modelo com sensores de comportamento
                self.engajamento_estimado = c["engajamento_obs"]
                self.historico_tempo.append(c["tempo_tela"])
            elif msg["tipo"] == "RESULTADO_AVALIACAO":
                # atualiza a crença de proficiência (estimador por média móvel)
                t = c["topico_id"]
                medido = c["proficiencia_medida"]
                self.proficiencia_estimada[t] = (
                    0.4 * self.proficiencia_estimada[t] + 0.6 * medido
                )

    def snapshot(self) -> dict:
        """Fornece o modelo atual do aluno a quem solicitar (ex.: Tutor)."""
        return {
            "proficiencia_estimada": [round(x, 3) for x in self.proficiencia_estimada],
            "engajamento_estimado": round(self.engajamento_estimado, 3),
        }


# ===========================================================================
# 5. AGENTE DE AVALIAÇÃO
#    Classificação: AGENTE BASEADO EM MODELO com elementos BASEADO EM OBJETIVO.
#    Aplica um TESTE ADAPTATIVO: a dificuldade da próxima questão depende da
#    resposta anterior, convergindo para a habilidade do aluno.
# ===========================================================================
class AgenteAvaliacao:
    NOME = "AgenteAvaliacao"

    def __init__(self, barramento: BarramentoMensagens, adaptativo: bool = True):
        self.bus = barramento
        self.bus.registrar_agente(self.NOME)
        self.adaptativo = adaptativo

    def avaliar(self, aluno: AlunoSimulado, topico_id: int,
                nivel_inicial: float, n_questoes: int = 6) -> dict:
        dificuldade = nivel_inicial
        acertos = 0
        trilha = []
        for _ in range(n_questoes):
            dificuldade = max(0.05, min(0.95, dificuldade))
            r = aluno.responder(topico_id, dificuldade)
            acertos += r
            trilha.append((round(dificuldade, 2), r))
            if self.adaptativo:
                # teste adaptativo: acertou -> sobe; errou -> desce
                dificuldade += 0.12 if r == 1 else -0.12
            # no modo não-adaptativo, dificuldade fixa (nivel_inicial)
            else:
                dificuldade = nivel_inicial

        proficiencia_medida = acertos / n_questoes
        resultado = {
            "topico_id": topico_id,
            "acertos": acertos,
            "total": n_questoes,
            "proficiencia_medida": round(proficiencia_medida, 3),
            "trilha": trilha,
        }
        # coopera: informa o Perfil para atualizar o modelo do aluno
        self.bus.enviar(self.NOME, AgentePerfil.NOME, "RESULTADO_AVALIACAO", resultado)
        return resultado


# ===========================================================================
# 6. AGENTE TUTOR (PEDAGÓGICO)
#    Classificação: AGENTE BASEADO EM OBJETIVO com elementos BASEADO EM
#    UTILIDADE. Objetivo: levar o aluno ao domínio de todos os tópicos.
#    Utilidade: escolhe a ação (dificuldade/metodologia) que maximiza o
#    ganho esperado de aprendizado (mira a Zona de Desenvolvimento Proximal).
# ===========================================================================
class AgenteTutor:
    NOME = "AgenteTutor"
    LIMIAR_DOMINIO = 0.75   # objetivo: proficiência estimada >= 0.75 por tópico
    MARGEM_ZDP = 0.15       # mira a dificuldade um pouco acima do nível atual

    def __init__(self, barramento: BarramentoMensagens, perfil: AgentePerfil):
        self.bus = barramento
        self.bus.registrar_agente(self.NOME)
        self.perfil = perfil
        self.metodologia_atual = "texto"
        self.engajamento_anterior = 0.7

    def decidir_dificuldade(self, topico_id: int) -> float:
        """Função de utilidade: escolhe a dificuldade do material que maximiza
        o ganho esperado de aprendizado, mirando a Zona de Desenvolvimento
        Proximal (ZDP) -> nível estimado do aluno + uma pequena margem.

        Diferente do método linear (dificuldade fixa), aqui o material
        acompanha continuamente a evolução do aluno até o domínio."""
        nivel = self.perfil.proficiencia_estimada[topico_id]
        alvo = nivel + self.MARGEM_ZDP
        return max(0.1, min(0.98, alvo))

    def decidir_metodologia(self) -> str:
        """Se o engajamento estimado caiu, troca de metodologia (Alteração de
        Metodologia / atuador descrito no PEAS)."""
        eng = self.perfil.engajamento_estimado
        if eng < self.engajamento_anterior - 0.03:
            idx = METODOLOGIAS.index(self.metodologia_atual)
            self.metodologia_atual = METODOLOGIAS[(idx + 1) % len(METODOLOGIAS)]
        self.engajamento_anterior = eng
        return self.metodologia_atual

    def topico_dominado(self, topico_id: int) -> bool:
        return self.perfil.proficiencia_estimada[topico_id] >= self.LIMIAR_DOMINIO

    def requisitar_conteudo(self, topico_id: int) -> None:
        pedido = {
            "topico_id": topico_id,
            "dificuldade": self.decidir_dificuldade(topico_id),
            "metodologia": self.decidir_metodologia(),
        }
        self.bus.enviar(self.NOME, AgenteConteudo.NOME, "REQUISITAR_CONTEUDO", pedido)


# ===========================================================================
# 7. AMBIENTE / ORQUESTRAÇÃO
#    Loop principal que coordena uma sessão de aprendizado completa de um
#    aluno, integrando os quatro agentes via barramento.
# ===========================================================================
def executar_sessao(aluno: AlunoSimulado, adaptativo: bool,
                    registrar_log: bool = False, max_passos: int = 120) -> dict:
    """Executa o curso completo para um aluno.

    adaptativo=True  -> Sistema Multiagente com adaptação (proposta).
    adaptativo=False -> Linha de base LINEAR: dificuldade média fixa,
                        metodologia única, avança após nº fixo de sessões,
                        avaliação não-adaptativa.
    """
    bus = BarramentoMensagens(registrar_log=registrar_log)
    perfil = AgentePerfil(bus)
    conteudo = AgenteConteudo(bus)
    avaliacao = AgenteAvaliacao(bus, adaptativo=adaptativo)
    tutor = AgenteTutor(bus, perfil)

    passos = 0
    topico_atual = 0
    sessoes_no_topico = 0
    historico_eng: List[float] = []

    while topico_atual < len(TOPICOS) and passos < max_passos:
        if aluno.evadiu:
            break
        passos += 1
        sessoes_no_topico += 1

        # ---- decisão do Tutor + entrega de Conteúdo -----------------------
        if adaptativo:
            tutor.requisitar_conteudo(topico_atual)
        else:
            # método linear: dificuldade fixa 0.5, metodologia única "texto"
            bus.enviar(tutor.NOME, conteudo.NOME, "REQUISITAR_CONTEUDO",
                       {"topico_id": topico_atual, "dificuldade": 0.5,
                        "metodologia": "texto"})
        conteudo.processar()

        material = None
        for msg in bus.receber(tutor.NOME):
            if msg["tipo"] == "CONTEUDO_ENTREGUE":
                material = msg["conteudo"]

        # ---- aluno estuda; sensores reportam ao Perfil --------------------
        obs = aluno.estudar(material["topico_id"], material["dificuldade"],
                            material["metodologia"])
        bus.enviar("Ambiente", perfil.NOME, "PERCEPCAO_COMPORTAMENTO", obs)
        perfil.processar()
        historico_eng.append(aluno.engajamento)

        # ---- avaliação periódica ------------------------------------------
        nivel_ini = (perfil.proficiencia_estimada[topico_atual]
                     if adaptativo else 0.5)
        resultado = avaliacao.avaliar(aluno, topico_atual, nivel_ini)
        perfil.processar()  # Perfil consome o RESULTADO_AVALIACAO

        # ---- decisão de avançar -------------------------------------------
        if adaptativo:
            # avança somente quando o objetivo (domínio) é atingido
            if tutor.topico_dominado(topico_atual):
                topico_atual += 1
                sessoes_no_topico = 0
        else:
            # linear: avança após 3 sessões, independentemente do domínio
            if sessoes_no_topico >= 3:
                topico_atual += 1
                sessoes_no_topico = 0

    # ---- métricas finais (Performance do PEAS) ----------------------------
    proficiencia_media = sum(aluno.proficiencia) / len(TOPICOS)
    topicos_dominados = sum(1 for p in aluno.proficiencia if p >= 0.75)

    return {
        "evadiu": aluno.evadiu,
        "passos": passos,
        "topicos_concluidos": topico_atual,
        "topicos_dominados": topicos_dominados,
        "proficiencia_media": round(proficiencia_media, 3),
        "engajamento_final": round(aluno.engajamento, 3),
        "proficiencia_por_topico": [round(p, 3) for p in aluno.proficiencia],
        "historico_engajamento": historico_eng,
        "log_mensagens": bus.log,
    }


# ===========================================================================
# 8. EXPERIMENTO  -  comparação entre métodos (Adaptativo x Linear)
# ===========================================================================
def rodar_experimento(n_alunos: int = 200, seed: int = 42) -> dict:
    rng = random.Random(seed)
    resultados = {"adaptativo": [], "linear": []}

    for i in range(n_alunos):
        # mesmo perfil de aluno é submetido aos dois métodos (comparação justa)
        taxa = rng.uniform(0.20, 0.42)
        eng0 = rng.uniform(0.55, 0.85)
        s = rng.randint(0, 10_000_000)

        aluno_a = AlunoSimulado(taxa, eng0, seed=s)
        resultados["adaptativo"].append(executar_sessao(aluno_a, adaptativo=True))

        aluno_l = AlunoSimulado(taxa, eng0, seed=s)
        resultados["linear"].append(executar_sessao(aluno_l, adaptativo=False))

    return resultados


def resumir(lista: List[dict]) -> dict:
    n = len(lista)
    return {
        "n": n,
        "taxa_evasao_%": round(100 * sum(r["evadiu"] for r in lista) / n, 1),
        "proficiencia_media": round(sum(r["proficiencia_media"] for r in lista) / n, 3),
        "topicos_dominados_media": round(sum(r["topicos_dominados"] for r in lista) / n, 2),
        "topicos_concluidos_media": round(sum(r["topicos_concluidos"] for r in lista) / n, 2),
        "engajamento_final_media": round(sum(r["engajamento_final"] for r in lista) / n, 3),
        "passos_medios": round(sum(r["passos"] for r in lista) / n, 1),
    }


def imprimir_tabela(res_adapt: dict, res_lin: dict) -> None:
    metricas = [
        ("Taxa de evasão (%)",            "taxa_evasao_%",          "menor"),
        ("Proficiência média final",      "proficiencia_media",     "maior"),
        ("Tópicos dominados (média)",     "topicos_dominados_media", "maior"),
        ("Tópicos concluídos (média)",    "topicos_concluidos_media", "maior"),
        ("Engajamento final (média)",     "engajamento_final_media", "maior"),
        ("Passos/sessões (média)",        "passos_medios",          "-"),
    ]
    print("\n" + "=" * 70)
    print("  RESULTADOS DO EXPERIMENTO  (Adaptativo/SMA  x  Linear)")
    print(f"  Alunos simulados: {res_adapt['n']}")
    print("=" * 70)
    print(f"{'Métrica':<32}{'Adaptativo':>12}{'Linear':>10}{'Melhor':>14}")
    print("-" * 70)
    for nome, chave, sentido in metricas:
        a = res_adapt[chave]
        l = res_lin[chave]
        if sentido == "maior":
            melhor = "Adaptativo" if a > l else ("Linear" if l > a else "empate")
        elif sentido == "menor":
            melhor = "Adaptativo" if a < l else ("Linear" if l < a else "empate")
        else:
            melhor = "-"
        print(f"{nome:<32}{a:>12}{l:>10}{melhor:>14}")
    print("=" * 70)


def gerar_csv(res_adapt: dict, res_lin: dict, caminho: str) -> None:
    """Salva as métricas em CSV (útil para tabelas/gráficos no artigo)."""
    linhas = ["metrica,adaptativo,linear"]
    for chave in ["taxa_evasao_%", "proficiencia_media", "topicos_dominados_media",
                  "topicos_concluidos_media", "engajamento_final_media", "passos_medios"]:
        linhas.append(f"{chave},{res_adapt[chave]},{res_lin[chave]}")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")
    print(f"\n[ok] Métricas salvas em: {caminho}")


def gerar_graficos(resultados: dict, res_adapt: dict, res_lin: dict,
                   prefixo: str) -> None:
    """Gera gráficos comparativos (PNG) usando matplotlib, se disponível."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("[aviso] matplotlib não instalado; gráficos não gerados.")
        return

    # --- Gráfico 1: barras comparativas das métricas principais ------------
    rotulos = ["Proficiência\nmédia", "Tópicos\ndominados", "Engajamento\nfinal",
               "Taxa evasão\n(/10)"]
    val_a = [res_adapt["proficiencia_media"], res_adapt["topicos_dominados_media"] / 6,
             res_adapt["engajamento_final_media"], res_adapt["taxa_evasao_%"] / 10]
    val_l = [res_lin["proficiencia_media"], res_lin["topicos_dominados_media"] / 6,
             res_lin["engajamento_final_media"], res_lin["taxa_evasao_%"] / 10]
    x = range(len(rotulos))
    larg = 0.35
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar([i - larg / 2 for i in x], val_a, larg, label="Adaptativo (SMA)", color="#2a9d8f")
    ax.bar([i + larg / 2 for i in x], val_l, larg, label="Linear", color="#e76f51")
    ax.set_xticks(list(x))
    ax.set_xticklabels(rotulos)
    ax.set_ylabel("Valor normalizado")
    ax.set_title("Comparação de Desempenho: Adaptativo (SMA) x Linear")
    ax.legend()
    fig.tight_layout()
    fig.savefig(f"{prefixo}_comparacao.png", dpi=150)
    plt.close(fig)

    # --- Gráfico 2: curva média de engajamento ao longo das sessões --------
    def media_curva(lista):
        max_len = max(len(r["historico_engajamento"]) for r in lista)
        soma = [0.0] * max_len
        cont = [0] * max_len
        for r in lista:
            for i, v in enumerate(r["historico_engajamento"]):
                soma[i] += v
                cont[i] += 1
        return [soma[i] / cont[i] for i in range(max_len) if cont[i] > 0]

    curva_a = media_curva(resultados["adaptativo"])
    curva_l = media_curva(resultados["linear"])
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(range(1, len(curva_a) + 1), curva_a, label="Adaptativo (SMA)",
            color="#2a9d8f", linewidth=2)
    ax.plot(range(1, len(curva_l) + 1), curva_l, label="Linear",
            color="#e76f51", linewidth=2)
    ax.set_xlabel("Sessão de estudo")
    ax.set_ylabel("Engajamento médio")
    ax.set_title("Evolução do Engajamento ao longo do curso")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(f"{prefixo}_engajamento.png", dpi=150)
    plt.close(fig)

    print(f"[ok] Gráficos gerados: {prefixo}_comparacao.png, {prefixo}_engajamento.png")


# ===========================================================================
# 9. MODO DEMONSTRAÇÃO  -  acompanha 1 aluno e mostra as mensagens JSON
# ===========================================================================
def demo() -> None:
    print("=" * 70)
    print("  MODO DEMO  -  acompanhando 1 aluno no Sistema Multiagente")
    print("=" * 70)
    aluno = AlunoSimulado(taxa_aprendizado=0.22, engajamento_inicial=0.7, seed=7)
    res = executar_sessao(aluno, adaptativo=True, registrar_log=True, max_passos=40)

    print("\n--- Amostra das mensagens trocadas no barramento (JSON) ---\n")
    for linha in res["log_mensagens"][:12]:
        print(linha)

    print("\n--- Resultado final do aluno ---")
    print(f"  Evadiu: {res['evadiu']}")
    print(f"  Sessões realizadas: {res['passos']}")
    print(f"  Tópicos concluídos: {res['topicos_concluidos']}/{len(TOPICOS)}")
    print(f"  Proficiência por tópico: {res['proficiencia_por_topico']}")
    print(f"  Proficiência média: {res['proficiencia_media']}")
    print(f"  Engajamento final: {res['engajamento_final']}")


# ===========================================================================
# 10. PONTO DE ENTRADA
# ===========================================================================
def main() -> None:
    args = sys.argv[1:]

    if "--demo" in args:
        demo()
        return

    print("Executando experimento (Adaptativo/SMA x Linear)...")
    resultados = rodar_experimento(n_alunos=200, seed=42)
    res_adapt = resumir(resultados["adaptativo"])
    res_lin = resumir(resultados["linear"])

    imprimir_tabela(res_adapt, res_lin)
    gerar_csv(res_adapt, res_lin, "resultados.csv")

    if "--graficos" in args:
        gerar_graficos(resultados, res_adapt, res_lin, "resultado")


if __name__ == "__main__":
    main()
