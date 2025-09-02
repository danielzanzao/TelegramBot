# Configuração de Gerentes - EnactusBOT

## Como Configurar Gerentes

Para definir quais usuários são gerentes e quais áreas/projetos eles gerenciam, siga estes passos:

### 1. Descobrir ID do Telegram

Cada pessoa que será gerente deve:
1. Iniciar uma conversa com o bot
2. Enviar o comando `/get_my_id`
3. Copiar o número ID que aparece

### 2. Editar o Arquivo de Configuração

No arquivo `data_models.py`, procure a seção `DEFAULT_MANAGERS` (por volta da linha 200) e adicione os gerentes:

```python
DEFAULT_MANAGERS = [
    # Exemplo: (ID_do_telegram, "Nome", ["áreas_ou_projetos"])
    (123456789, "João Silva", ["DAF", "GP"]),           # Gerente de DAF e GP
    (987654321, "Maria Santos", ["Odoyá"]),             # Gerente do projeto Odoyá
    (555666777, "Pedro Costa", ["MKT", "QLD", "PSD"]),  # Gerente de múltiplas áreas
]
```

### 3. Áreas e Projetos Disponíveis

**Áreas:**
- DAF (Departamento Administrativo Financeiro)
- GP (Gestão de Pessoas)
- MKT (Marketing)
- QLD (Qualidade)
- PSD (Presidente)

**Projetos:**
- Odoyá
- Maná
- Gelé

### 4. Exemplos de Configuração

```python
DEFAULT_MANAGERS = [
    # Gerente responsável apenas por DAF
    (111111111, "Ana Costa", ["DAF"]),
    
    # Gerente responsável por múltiplas áreas
    (222222222, "Carlos Lima", ["MKT", "QLD"]),
    
    # Gerente de projeto específico
    (333333333, "Julia Santos", ["Odoyá"]),
    
    # Gerente geral (todas as áreas)
    (444444444, "Roberto Silva", ["DAF", "GP", "MKT", "QLD", "PSD"]),
    
    # Gerente de múltiplos projetos
    (555555555, "Fernanda Rocha", ["Odoyá", "Maná", "Gelé"]),
]
```

### 5. Aplicar as Mudanças

Após editar o arquivo `data_models.py`:
1. Salve o arquivo
2. Reinicie o bot (ele reinicia automaticamente quando detecta mudanças)
3. Os gerentes configurados começarão a receber notificações semanais sobre HOs pendentes

### 6. Como Funciona o Sistema de Aprovação

- **HOs Registradas**: Ficam com status "Pendente" até serem aprovadas
- **Notificações Semanais**: Gerentes recebem lista de HOs pendentes toda semana
- **Aprovação via Bot**: Gerentes podem aprovar/reprovar diretamente pelo Telegram
- **Rastreamento**: Todas as aprovações ficam registradas com data e responsável

### 7. Comandos Úteis para Gerentes

- `/get_my_id` - Descobrir ID do Telegram
- `/start` - Acessar menu principal do bot
- `/help` - Ver ajuda completa

### 8. Troubleshooting

**Problema:** Gerente não recebe notificações
- Verifique se o ID do Telegram está correto
- Confirme que o gerente já iniciou conversa com o bot
- Verifique se a área/projeto está escrita corretamente

**Problema:** ID do Telegram não funciona
- Peça para o gerente enviar `/get_my_id` novamente
- Certifique-se de copiar apenas os números, sem espaços ou caracteres especiais

---

**Nota:** Após configurar os gerentes, eles precisarão interagir com o bot ao menos uma vez (enviando /start) para que o sistema funcione corretamente.