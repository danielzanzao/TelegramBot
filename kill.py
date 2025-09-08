# stop_script.py
import os
import signal
import sys
import psutil

def find_pid_by_name(process_name):
    """Encontra o PID (ID do processo) de um processo pelo seu nome."""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        # Procura tanto pelo nome do processo (ex: 'pythonw.exe')
        # quanto pelo nome do script no caminho de execução
        cmdline = proc.info['cmdline']
        if cmdline and process_name in " ".join(cmdline):
            return proc.info['pid']
    return None

def main():
    # Substitua 'main.pyw' pelo nome do seu script principal
    script_name = "main.pyw"
    
    # Encontra o PID do script principal
    pid = find_pid_by_name(script_name)
    
    if pid is None:
        print(f"O script '{script_name}' não foi encontrado.")
        sys.exit(1)
    
    try:
        # Tenta encerrar o processo gentilmente
        os.kill(pid, signal.SIGTERM)
        print(f"Sinal SIGTERM enviado para o script '{script_name}' (PID: {pid}).")
        
        # Opcional: espera o processo terminar
        try:
            psutil.Process(pid).wait(timeout=5)
            print("O script foi encerrado com sucesso.")
        except psutil.TimeoutExpired:
            print("O script não terminou em tempo. Forçando o encerramento com SIGKILL.")
            os.kill(pid, signal.SIGKILL)
            print("O script foi encerrado à força.")
            
    except ProcessLookupError:
        print(f"O processo com o PID {pid} não foi encontrado. Talvez ele já tenha sido encerrado.")
    except Exception as e:
        print(f"Ocorreu um erro: {e}")

if __name__ == "__main__":
    main()