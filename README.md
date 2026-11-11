# Marketplace Simplificado — Projeto 5

Implementação do projeto final de Construção de Backend (Django/Python), baseada no PDF `Projeto5_Guia_do_Aluno (1).pdf`.

> **Estado em 11/11/2026:** testes locais aprovados; `main` está sincronizada com o GitHub. O deploy Vercel aparece como `Ready`, mas o banco Supabase e os dados de produção não foram verificados nesta revisão. A integração Shopify está instalada como sandbox, sem reivindicar uma loja nem migrar o checkout. Nenhum segredo é versionado.

## 1. O que foi construído

- Cadastro de `Categoria`, `Produto`, `Pedido` e `ItemPedido`.
- Histórico de preço: `ItemPedido.preco_unitario` é copiado do preço vigente no checkout.
- Admin com isolamento: vendedor comum só lista e edita os próprios produtos; superusuário vê tudo.
- Carrinho anônimo armazenado na sessão do Django.
- Checkout protegido por login, com `transaction.atomic()` e bloqueio `select_for_update()`.
- Validação de estoque antes de qualquer gravação; estoque nunca pode ficar negativo.
- API REST:
  - `GET /api/produtos/` público;
  - `POST /api/produtos/` autenticado, com vendedor definido pelo servidor;
  - `POST /api/pedidos/` autenticado, com itens aninhados;
  - filtro opcional `GET /api/produtos/?categoria=ID`.
- Catálogo que consome a API com `fetch()`, contador de conveniência em `localStorage` e proteção CSRF.
- Filtros de catálogo por busca, categoria, preço e disponibilidade.
- Painel do vendedor com estoque, unidades vendidas e faturamento.
- Painel avançado com vendas por categoria e pedidos recentes.
- Avaliações: somente compradores com pedido pago ou enviado podem avaliar; a resposta pública não expõe a identidade do usuário.
- Configuração dual: SQLite local por padrão e PostgreSQL/Supabase quando `DATABASE_URL` existe.
- Deploy Django nativo na Vercel, com detecção automática por `manage.py` e WSGI em `marketplace/wsgi.py`.

## 2. Mapa dos arquivos

```text
marketplace/
├── manage.py
├── requirements.txt
├── .env.example
├── .gitignore
├── vercel.json
├── marketplace/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
└── loja/
    ├── admin.py
    ├── api_views.py
    ├── models.py
    ├── serializers.py
    ├── tests.py
    ├── urls.py
    ├── views.py
    ├── migrations/0001_initial.py
    └── templates/loja/
```

## 3. Pré-requisitos

- Windows PowerShell, Python 3.11+ (foi validado com Python 3.14.7).
- Conta no Supabase para produção.
- Conta no Vercel para publicação.
- Git e um repositório remoto, caso a entrega precise ser publicada no GitHub.

## 4. Execução local, passo a passo

Abra o PowerShell em `C:\marketplace`:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py check
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Se a política do PowerShell bloquear a ativação, execute apenas uma vez:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Abra:

- Catálogo: `http://127.0.0.1:8000/`
- Carrinho: `http://127.0.0.1:8000/carrinho/`
- Admin: `http://127.0.0.1:8000/admin/`
- API de produtos: `http://127.0.0.1:8000/api/produtos/`
- Login DRF: `http://127.0.0.1:8000/api-auth/login/`

No Admin, crie uma categoria, dois vendedores com `is_staff` e permissões de Produto e um comprador comum. A criação do produto por vendedor deixa o campo vendedor oculto e preenche o usuário autenticado automaticamente.

### Dados de demonstração

Após criar um usuário staff e aplicar as migrations, é possível adicionar até 50 produtos fictícios com preços aleatórios:

```powershell
python manage.py seed_demo --vendor-username <usuario-staff>
```

O comando é repetível, preserva produtos existentes e não cria ou altera contas, senhas nem pedidos. Em produção, execute somente após confirmar o banco de destino e a conta staff que será proprietária dos produtos.

## 5. Roteiro funcional detalhado

1. Abra `/` sem login e confirme que produtos aparecem pela API.
2. Clique em “Adicionar ao carrinho”; confirme que o contador muda.
3. Abra `/carrinho/` sem login; o carrinho continua visível e aparece o link de login.
4. Entre como comprador; o carrinho deve permanecer.
5. Finalize com estoque suficiente; confirme pedido, itens, baixa do estoque e limpeza da sessão.
6. Tente comprar quantidade maior que o estoque; confirme que não há pedido, não há item parcial e o carrinho é preservado.
7. Altere o preço de um produto vendido; confirme no Admin que `preco_unitario` do pedido antigo não mudou.
8. Faça `GET /api/produtos/` anônimo; deve retornar JSON.
9. Faça `POST /api/produtos/` anônimo; deve retornar `401` ou `403`.
10. Faça `POST /api/pedidos/` autenticado. O preço enviado pelo cliente é ignorado.
11. Entre como dois vendedores diferentes e confirme que cada um vê somente os próprios produtos.

Exemplo de pedido:

```json
{
  "itens": [
    {"produto": 1, "quantidade": 2}
  ]
}
```

Resposta ilustrativa (`201 Created`):

```json
{
  "id": 42,
  "status": "ABERTO",
  "criado_em": "2026-11-11T12:30:00Z",
  "itens": [
    {
      "produto": 1,
      "quantidade": 2,
      "preco_unitario": "24.50"
    }
  ]
}
```

## 6. Testes automatizados executados

Para manter os testes isolados do Supabase, force um arquivo SQLite temporário. Isso é
importante quando o `.env` local contém a `DATABASE_URL` de produção:

```powershell
$env:DATABASE_URL="sqlite:///C:/marketplace/test-local.sqlite3"
$env:DJANGO_DEBUG="True"
python manage.py test
```

Resultado verificado:

```text
Ran 23 tests
OK
```

O parâmetro `ssl_require` só é aplicado a URLs PostgreSQL; assim, a mesma configuração
continua segura no Supabase e funciona corretamente com SQLite durante os testes.

Os testes cobrem checkout, baixa de estoque, limpeza do carrinho, falha atômica, leitura pública da API, filtros válidos e inválidos, exigência de login, preservação do carrinho no login, isolamento do Admin, validação de preço, avaliações autorizadas/duplicadas e proteção do preço histórico.

## 7. Configuração do Supabase

### 7.1 Criar o projeto

1. Entre no painel do Supabase e crie um projeto.
2. Escolha região próxima dos usuários.
3. Defina uma senha forte para o banco e guarde-a em um gerenciador de segredos.
4. Em **Project Settings → Database**, copie a conexão PostgreSQL.
5. Prefira a conexão **Session Pooler** para ambientes serverless. Não publique a senha no GitHub.

### 7.2 Configurar localmente

Edite `.env` (nunca `.env.example`) e substitua:

```dotenv
DJANGO_SECRET_KEY=uma-chave-aleatoria-longa
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,seu-dominio.vercel.app
DATABASE_URL=postgresql://postgres.[PROJETO]:[SENHA]@[HOST]:5432/postgres
CSRF_TRUSTED_ORIGINS=https://seu-dominio.vercel.app
```

Se a senha tiver `@`, `:`, `/`, `#` ou outros caracteres reservados, aplique URL encoding antes de montar a URL. Alternativamente use a URL copiada pelo Supabase.

Execute:

```powershell
python manage.py check --deploy
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py test
```

As tabelas serão criadas pela migration Django. Não é necessário copiar SQL manual para o editor do Supabase. O painel **Table Editor** deve exibir `loja_categoria`, `loja_produto`, `loja_pedido` e `loja_itempedido`, além das tabelas internas do Django.

### 7.3 Cuidados do Supabase

- Não use a chave `service_role` no navegador.
- A aplicação Django usa o usuário PostgreSQL da conexão, portanto o controle de acesso é feito pelo Django Admin/API.
- Faça backup antes de migrations destrutivas.
- Em produção, use `DEBUG=False`, `SECRET_KEY` aleatória e domínios explícitos.

## 8. Publicação no Vercel

O Vercel detecta o projeto Django por `manage.py`, usa `marketplace/wsgi.py` como entrada WSGI e coleta os arquivos estáticos automaticamente a partir de `STATIC_ROOT`.

### Opção A — Dashboard

1. Publique o código em um repositório GitHub sem `.env`, `db.sqlite3` ou `.venv`.
2. No Vercel, selecione **Add New → Project** e importe o repositório.
3. Não sobrescreva o framework com Next.js; o `vercel.json` já define o build Python.
4. Em **Settings → Environment Variables**, adicione:
   - `DJANGO_SECRET_KEY`;
   - `DJANGO_DEBUG=False`;
   - `DJANGO_ALLOWED_HOSTS=seu-projeto.vercel.app`;
   - `DATABASE_URL`;
   - `CSRF_TRUSTED_ORIGINS=https://seu-projeto.vercel.app`.
5. Faça o deploy.
6. Após o primeiro domínio ser conhecido, atualize `DJANGO_ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` se necessário e redeploye.
7. Rode migrations de produção de forma controlada, preferencialmente no CI ou localmente usando a mesma `DATABASE_URL`:

```powershell
$env:DATABASE_URL="postgresql://..."
python manage.py migrate
```

### Opção B — CLI

```powershell
npm install -g vercel
vercel login
vercel link
vercel env add DJANGO_SECRET_KEY production
vercel env add DJANGO_DEBUG production
vercel env add DJANGO_ALLOWED_HOSTS production
vercel env add DATABASE_URL production
vercel env add CSRF_TRUSTED_ORIGINS production
vercel --prod
```

Não digite segredos diretamente em comandos que ficarão no histórico do shell. Use o prompt interativo do `vercel env add` ou o Dashboard.

## 9. Checklist de entrega

- [x] Quatro models e migration inicial.
- [x] Admin com isolamento entre vendedores.
- [x] Carrinho em sessão sem login.
- [x] Checkout atômico, com bloqueio de linha e validação de estoque.
- [x] Preço histórico do item.
- [x] API pública/autenticada e pedido aninhado.
- [x] Catálogo com `fetch`, contador e CSRF.
- [x] SQLite local funcional.
- [x] Configuração PostgreSQL/Supabase por `DATABASE_URL`.
- [x] Estrutura de Function e roteamento do Vercel.
- [x] `.gitignore` protegendo `.env`, banco local e ambientes virtuais.
- [x] Testes automatizados aprovados.
- [x] Filtros de catálogo por busca, preço e disponibilidade.
- [x] Painel do vendedor com métricas, vendas por categoria e pedidos recentes.
- [x] Avaliações de produtos com validação de compra e unicidade.
- [x] Restringir pedidos do Admin a superusuários.
- [x] Indicadores do vendedor consideram somente pedidos pagos ou enviados.
- [x] Exigir `DJANGO_SECRET_KEY` explícita quando `DJANGO_DEBUG=False`.
- [ ] Verificar a `DATABASE_URL` remota, migrations e dados atuais do Supabase.
- [x] Integração Shopify instalada como recurso sandbox na Vercel; sem loja reivindicada.
- [ ] Decidir/provisionar loja real e integrar pagamento ao checkout.
- [x] Deploys recentes da Vercel aparecem como `Ready`.
- [ ] Validar catálogo e API pelo domínio de produção protegido.
- [ ] Incluir screenshots do catálogo, carrinho e Admin.

## 10. Erros encontrados e soluções aplicadas

### 10.1 O PDF não tinha ferramenta `pdftotext`

**Sintoma:** o executável não estava disponível no Windows.  
**Solução:** o conteúdo foi extraído com `pypdf` em ambiente Python configurado, preservando a conferência dos 23 pages do guia.

### 10.2 `ModuleNotFoundError: No module named 'pypdf'`

**Causa:** a instalação auxiliar não ficou disponível no interpretador usado pelo PowerShell.  
**Solução:** instalação no interpretador exato com `python -m pip install --break-system-packages pypdf`; isso foi usado somente para ler o PDF, não foi adicionado às dependências da aplicação.

### 10.3 Chaves de sessão

**Risco:** JSON exige chaves textuais; usar IDs inteiros provoca inconsistências e `KeyError`.  
**Solução:** `views.py` sempre converte o ID para `str` ao salvar e ao ler.

### 10.4 CSRF ao adicionar pelo catálogo

**Risco:** POST via `fetch()` sem cookie/cabeçalho CSRF retorna `403`.  
**Solução:** `@ensure_csrf_cookie` força o cookie na página e o JavaScript envia `X-CSRFToken`.

### 10.5 Pedido parcialmente criado

**Risco:** criar pedido, item e baixa de estoque em operações separadas deixaria dados incompletos.  
**Solução:** todo o checkout e a criação aninhada da API estão em `transaction.atomic()`.

### 10.6 Concorrência de estoque

**Risco:** dois checkouts simultâneos poderiam ler o mesmo estoque.  
**Solução:** `select_for_update()` bloqueia as linhas durante a transação e a baixa usa `F("estoque") - quantidade`.

### 10.7 Migração e teste

**Resultado:** `manage.py check` não apontou problemas; a migration `0001_initial.py` foi criada; migrations internas e da loja foram aplicadas; a suíte terminou com `OK`.

### 10.8 Comando PowerShell com chaves aninhadas

**Sintoma:** um comando de validação inicial falhou com “chave de fechamento ausente”.  
**Solução:** o fluxo foi refeito em etapas sequenciais com verificação explícita de `$?`, evitando aninhamento frágil.

## 11. Limitações e próximos passos

- O checkout atual registra pedidos, mas não processa cobrança. O recurso Shopify está em sandbox; a loja não foi reivindicada nem integrada ao checkout Django.
- O estado remoto do Supabase permanece desconhecido nesta revisão. Não considerar migrations ou produtos demo como publicados até validar a conexão e o banco alvo.
- Os arquivos de credenciais devem permanecer em `.env`/Vercel Environment Variables; nunca copie valores para README, logs ou commits.
- O ambiente local gerou `db.sqlite3` e `.venv`; ambos estão protegidos pelo `.gitignore` e não devem ser enviados ao repositório.
