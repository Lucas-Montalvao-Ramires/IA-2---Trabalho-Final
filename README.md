# Sistema Inteligente de Tutoria e Adaptação Curricular (EAD) — Protótipo SMA

Protótipo funcional de um **Sistema Multiagente (SMA)** para personalização do
ensino a distância, implementando fielmente os quatro agentes descritos no
relatório técnico. Acompanha a entrega obrigatória do trabalho: código-fonte com
instruções de execução, experimento/avaliação e comparação entre métodos.

## Como executar

Requer apenas **Python 3.8+**. A simulação central usa somente a biblioteca
padrão; os gráficos são opcionais e usam `matplotlib`.

```bash
# Experimento completo (200 alunos): imprime a tabela e gera resultados.csv
python3 sistema_tutoria_sma.py

# Demonstração com 1 aluno, exibindo as mensagens JSON trocadas no barramento
python3 sistema_tutoria_sma.py --demo

# Experimento + geração dos gráficos PNG (requer matplotlib)
pip install matplotlib        # se necessário
python3 sistema_tutoria_sma.py --graficos

# Para utilizar o modo de demonstração e acompanhar detalhadamente o que acontece com apenas um aluno
python sistema_tutoria_sma.py --demo
```

Saídas geradas: `resultados.csv`, `resultado_comparacao.png`,
`resultado_engajamento.png`.

## Como o sistema funciona

### Arquitetura em camadas
O protótipo reproduz a arquitetura do relatório:

- **Camada de Integração** — `BarramentoMensagens`: cada agente possui uma caixa
  de entrada e troca **mensagens estruturadas em JSON** no formato
  `{"de", "para", "tipo", "conteudo"}`. É a evidência concreta da comunicação,
  cooperação e coordenação descentralizada entre os agentes.
- **Camada de Dados** — `TOPICOS` (currículo do curso, com pré-requisitos e
  dificuldade intrínseca) e `AgenteConteudo` (banco de materiais).
- **Camada de Agentes** — os quatro agentes inteligentes.
- **Ambiente** — `AlunoSimulado`, que mantém o estado *verdadeiro e oculto* do
  estudante (parcialmente observável pelos agentes).

### Os quatro agentes (classificação conforme o relatório)

1. **Agente Aluno / Perfil** (`AgentePerfil`) — *reativo simples com elementos
   de baseado em modelo*. Mantém a **crença estimada** sobre a proficiência e o
   engajamento do aluno, atualizada a cada percepção de comportamento e a cada
   resultado de avaliação (estimador por média móvel).

2. **Agente Tutor / Pedagógico** (`AgenteTutor`) — *baseado em objetivo com
   elementos de baseado em utilidade*. **Objetivo:** levar a proficiência
   estimada de cada tópico ao limiar de domínio (0,75). **Utilidade:** escolhe a
   dificuldade do material que maximiza o ganho esperado, mirando a **Zona de
   Desenvolvimento Proximal** (nível do aluno + margem). Também troca a
   metodologia quando detecta queda de engajamento.

3. **Agente de Conteúdo** (`AgenteConteudo`) — *reativo simples*. Regra
   condição-ação pura: recebe a requisição do Tutor e devolve o material
   correspondente a (tópico, dificuldade, metodologia), sem manter estado.

4. **Agente de Avaliação** (`AgenteAvaliacao`) — *baseado em modelo com elementos
   de baseado em objetivo*. Aplica um **teste adaptativo**: a dificuldade da
   próxima questão sobe a cada acerto e desce a cada erro, convergindo para a
   habilidade real do aluno. Realimenta o Perfil com o resultado.

### Modelo de aprendizado (o "ambiente")
O `AlunoSimulado` traduz três conceitos pedagógicos do relatório em equações:

- **Ganho de aprendizado** máximo quando a dificuldade do material está um pouco
  acima da proficiência atual (curva gaussiana centrada na ZDP). A dificuldade
  *intrínseca* do tópico modula a *velocidade* de aprendizado.
- **Engajamento** sobe quando o material está no ponto ótimo; cai por **tédio**
  (fácil demais) ou **frustração** (difícil demais).
- **Evasão**: engajamento muito baixo gera risco probabilístico de desistência.

As respostas às avaliações seguem um modelo logístico estilo **TRI (Teoria de
Resposta ao Item)**: `P(acerto) = sigmoide(k·(proficiência − dificuldade))`.

### Experimento e comparação entre métodos
Cada aluno (mesmo perfil e mesma semente aleatória) é submetido a **dois
métodos**, garantindo comparação justa:

- **Adaptativo (SMA proposto):** Tutor decide dificuldade/metodologia na ZDP;
  avança o tópico só ao atingir o domínio; avaliação adaptativa.
- **Linear (linha de base tradicional):** dificuldade fixa (0,5), metodologia
  única, avança após nº fixo de sessões, avaliação não-adaptativa.

## Resultados obtidos (200 alunos simulados)

| Métrica | Adaptativo (SMA) | Linear | Melhor |
|---|---|---|---|
| Taxa de evasão (%) | 2,0 | 58,5 | Adaptativo |
| Proficiência média final | 0,895 | 0,292 | Adaptativo |
| Tópicos dominados (média de 6) | 5,92 | 0,00 | Adaptativo |
| Tópicos concluídos (média de 6) | 5,90 | 4,89 | Adaptativo |
| Engajamento final (média) | 0,849 | 0,108 | Adaptativo |
| Sessões realizadas (média) | 84,7 | 15,3 | — |

**Discussão.** O método adaptativo praticamente elimina a evasão (2% vs 58,5%) e
conduz quase todos os tópicos ao domínio, enquanto o linear avança rápido porém
sem consolidar aprendizado (0 tópicos dominados). O contraponto honesto é o
**custo em tempo**: a personalização exige muito mais sessões (≈85 vs 15), pois
insiste no domínio antes de avançar. O trade-off central é, portanto,
**eficácia/retenção versus tempo de conclusão**.

> Observação: por ser uma simulação, os valores absolutos dependem dos
> parâmetros do modelo; o que se sustenta é a **direção** dos efeitos, alinhada
> à literatura de sistemas tutores inteligentes e à hipótese do relatório.
