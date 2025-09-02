# EnactusBOT

## Overview

EnactusBOT é um bot do Telegram para gerenciamento de horas de trabalho da Enactus. O bot permite aos membros registrarem suas horas de trabalho, acessarem recursos compartilhados e gerentes aprovarem HOs pendentes.

## Funcionalidades Principais

- **Marcar HO**: Registrar horas de trabalho com validação
- **Sistema de Aprovação**: Gerentes podem aprovar/reprovar HOs
- **Lembretes**: Sistema de notificações automáticas
- **Integração Google Sheets**: Sincronização automática de dados
- **Central Enactus**: Acesso a recursos compartilhados

## Como Usar

1. Envie `/start` para o bot no Telegram
2. Use o menu interativo para navegar pelas opções
3. Para marcar HO: Selecione nome → tipo → área/projeto → preencha dados
4. Gerentes recebem notificações semanais sobre HOs pendentes

## Configuração de Gerentes

Para configurar gerentes, edite o arquivo `data_models.py` na seção `DEFAULT_MANAGERS`. Use `/get_my_id` para descobrir IDs do Telegram.

## Architecture

- **bot.py**: Classe principal do bot
- **handlers.py**: Manipuladores de comandos e callbacks
- **data_models.py**: Modelos de dados e configurações
- **approval_system.py**: Sistema de aprovação de HOs
- **reminder_system.py**: Sistema de lembretes
- **sheets_integration.py**: Integração com Google Sheets

## User Preferences

- Linguagem: Português brasileiro
- Interface: Menus interativos com botões
- Comunicação: Linguagem simples e amigável