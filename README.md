# Fitness Research Agent

Agente de pesquisa automática que busca artigos e notícias recentes sobre exercício físico e musculação, sumariza em português com IA (Claude) e gera sugestões de legenda para Instagram.

## Pré-requisitos

- Python 3.10+
- Conta na [Tavily](https://tavily.com) (plano gratuito disponível)
- Conta na [Anthropic](https://console.anthropic.com) com API key

## Instalação

```bash
# Clonar / entrar na pasta do projeto
cd fitness-researcher

# Instalar dependências
pip install -r requirements.txt

# Configurar as chaves de API
cp .env.example .env
# Edite o arquivo .env e preencha TAVILY_API_KEY e ANTHROPIC_API_KEY
```

## Uso

```bash
# Executar pesquisa manualmente
python3 main.py

# Iniciar interface web (acesse http://localhost:8080)
python3 web/app.py
```

O relatório semanal será salvo em `reports/YYYY-WNN.md` e `reports/YYYY-WNN.json`.

## Personalização

Edite `config/topics.yaml` para ajustar:
- **topics**: os temas de pesquisa (termos buscados no Tavily)
- **trusted_domains**: domínios priorizados nas buscas
- **max_results_per_topic**: quantos resultados buscar por tema

## Automatizar (semanal, toda segunda às 8h)

```bash
crontab -e
```

Adicione a linha:
```
0 8 * * 1 cd /Users/henriquej/Projects/fitness-researcher && python main.py
```

## Estrutura de Arquivos

```
fitness-researcher/
├── .env                    # Chaves de API (não versionar)
├── .env.example            # Template de variáveis
├── requirements.txt
├── main.py                 # Ponto de entrada
├── README.md
├── config/
│   └── topics.yaml         # Tópicos e fontes configuráveis
├── agent/
│   ├── researcher.py       # Busca via Tavily
│   ├── summarizer.py       # Sumarização via Claude
│   └── reporter.py         # Geração do relatório Markdown
└── reports/                # Relatórios gerados
```
