
import os
import logging
from dotenv import load_dotenv
from sheets_integration import sheets_manager

# Set up logging to console
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_auth():
    print("\n🔍 **Testando Autenticação do Google Sheets**\n")
    
    load_dotenv()
    
    # Check variables
    project_id = os.environ.get('GOOGLE_PROJECT_ID')
    client_email = os.environ.get('GOOGLE_CLIENT_EMAIL')
    private_key = os.environ.get('GOOGLE_PRIVATE_KEY')
    
    print(f"📌 GOOGLE_PROJECT_ID: {project_id}")
    print(f"📌 GOOGLE_CLIENT_EMAIL: {client_email}")
    
    if private_key:
        key_len = len(private_key)
        start = private_key[:15] if key_len > 15 else private_key
        end = private_key[-15:] if key_len > 15 else ""
        print(f"📌 GOOGLE_PRIVATE_KEY: (Comprimento: {key_len}) {start}...{end}")
        
        # Check specific problematic characters
        if '\\n' in private_key:
             print("⚠️  AVISO: A chave privada contém caracteres '\\n' literais. O código tentará corrigi-los.")
        if '"' in private_key:
             print("⚠️  AVISO: A chave privada contém aspas. O código tentará removê-las.")
    else:
        print("❌ GOOGLE_PRIVATE_KEY: Não encontrado!")

    print("\n🔄 Tentando inicializar o serviço...")
    
    # Force re-initialization
    sheets_manager._initialize_service()
    
    if sheets_manager.is_available():
        print("\n✅ **SUCESSO: Autenticação realizada com sucesso!**")
        print(f"📂 Spreadsheet ID: {sheets_manager.spreadsheet_id}")
        
        # Try a read operation
        try:
             url = sheets_manager.get_spreadsheet_url()
             print(f"🔗 URL: {url}")
             print("✅ Teste de leitura OK")
        except Exception as e:
             print(f"⚠️ Erro ao ler dados: {e}")
             
    else:
        print("\n❌ **FALHA: Não foi possível autenticar.**")
        print("Verifique se o email do service account tem permissão na planilha e se a chave privada está correta.")

if __name__ == "__main__":
    test_auth()
