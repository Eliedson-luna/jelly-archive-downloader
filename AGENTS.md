# Torrent Downloader

Esse é um projeto simples que visa baixar filmes do site `archive.org` via torrent se disponivel.

# Requisitos da Aplicacao

- aplicativo torrent: qbittorrent
- interface web simples
- página de configuraçao (diretório de download, alterar url de busca informando onde sera inserido o parametro)
- página de histórico de downloads
- página inicial de pesquisa (web scraping do site original)
- Confirmação de que o QBittorrent está instalado no host

# Url de busca do archive.org

>https://archive.org/details/movies?tab=collection&query=Death+Note&and%5B%5D=mediatype%3A%22movies%22

o parametro `query` é o responsavel pela pesquisa do nome do filme

# Build

A plataforma deve ser pensada para rodar em um container que rode em uma máquina com o hardware que sera apresentados mais à frente.

O container não tera o qbittorrent, deverá ser usado o do sistema, para isso deverá criar uma verificaçao antes do download ou ao 
iniciar o container, e colocar um alerta na página caso nao seja encontrado o software no sistema.

# Hardware do Servidor

- Operating System: Armbian 26.11.0-trunk.68 trixie
- Kernel: Linux 6.18.54-current-rockchip
- Architecture: arm32
- 1GB ram

## 📝 Regra de Registro de Logs (Tarefas Executadas)

O agente deve, obrigatoriamente, registrar todas as ações relevantes, decisões e conclusões no diretório `logs/`, quero um arquivo por sessão. Os logs devem seguir estritamente a estrutura e o formato descritos abaixo:

### 1. Diretrizes para Registro
* **Imediatismo:** O log deve ser gravado imediatamente após a conclusão, interrupção ou falha de uma tarefa de alta relevância.
* **Atomicidade:** Cada entrada de log deve representar uma única unidade de trabalho ou bloco de tarefas relacionadas.
* **Estado Atual:** Sempre indique claramente o status final da operação (`[SUCESSO]`, `[FALHA]`, `[EM_ANDAMENTO]`, `[PAUSADO]`).
* **Links de Contexto:** Sempre que aplicável, inclua referências a commits, hashes, arquivos criados ou URLs geradas.

### 2. Formato Padrão do Log (Snippet)
Insira as novas entradas no final do arquivo, em ordem cronológica inversa (o mais recente no topo da seção de logs) utilizando o formato abaixo:

```markdown
#### AAAA-MM-DD HH:MM (Fuso Horário) - [STATUS] Nome Curto da Tarefa
* **Agente/Contexto:** [Nome do Agente ou Escopo]
* **Descrição:** [O que foi feito de forma concisa e direta]
* **Artefatos/Modificações:**
  - `caminho/do/arquivo_modificado.ext` (Breve explicação da mudança)
* **Próximos Passos (se aplicável):** [O que ficou pendente ou deve ser feito a seguir]
```

### 3. Exemplo Prático de Aplicação
```markdown
#### 2026-11-03 18:45 (BRT) - [SUCESSO] Refatoração do módulo de autenticação JWT
* **Agente/Contexto:** Backend-Agent / Auth-Refactor
* **Descrição:** Atualizada a biblioteca de criptografia para correção da vulnerabilidade CVE-XXXX e refatorada a validação de tokens expirados.
* **Artefatos/Modificações:**
  - `src/auth/jwt.service.ts` (Implementada nova lógica de expiração e tratamento de erro)
  - `package.json` (Dependência 'jsonwebtoken' atualizada para vX.X.X)
* **Próximos Passos:** Monitorar logs de produção para capturar possíveis falsos-positivos de tokens inválidos.

```

## 🚀 Diretrizes de Controle de Versão (Git)

Para manter o histórico do repositório limpo, rastreável e seguro, todos os contribuidores devem seguir as regras abaixo:

### 1. Mensagens de Commit (Conventional Commits)
Os commits devem ser claros e padronizados usando os seguintes prefixos:
* `feat:` Para novas funcionalidades ou novos agentes/recursos.
* `fix:` Para correção de bugs, erros de sintaxe ou comportamentos inesperados.
* `docs:` Para alterações exclusivas em documentações (como arquivos `.md`).
* `refactor:` Para modificações de estrutura que não alteram o comportamento final.
* `chore:` Para atualizações de tarefas de rotina, dependências ou configurações.

*Exemplo:* `git commit -m "feat: adiciona pipeline de validação de logs"`

### 2. Fluxo de Trabalho e Branches
* **Branch Principal Protegida:** Nunca faça commits diretamente na branch `main` ou `master`.
* **Criação de Branches:** Sempre crie uma branch específica a partir da `main` atualizada para trabalhar em uma nova tarefa.
  * *Padrão de nome:* `tipo/nome-da-tarefa` (ex: `feat/novo-modulo` ou `docs/ajusta-readme`).
* **Sincronização Diária:** Execute `git pull origin main` antes de iniciar qualquer alteração para evitar conflitos de mesclagem (merge conflicts).

### 3. Boas Práticas de Código e Envio
* **Commits Atômicos:** Faça commits pequenos e focados em apenas um contexto/problema. Não misture refatoração de código com correção de bugs no mesmo commit.
* **Revisão Obrigatória:** Todas as alterações devem ser enviadas via *Pull Request (PR)* ou *Merge Request (MR)* e validadas antes de serem integradas à branch principal.
* **Higiene do Repositório:** Nunca envie arquivos de configuração local, chaves de API, senhas ou pastas temporárias (como `node_modules/`, `.env` ou `__pycache__/`). Certifique-se de que o arquivo `.gitignore` está configurado corretamente.
