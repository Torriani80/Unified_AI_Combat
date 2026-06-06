import os

def list_directory_contents(path):
    try:
        print(f"Conteúdo da pasta: {path}")
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            if os.path.isdir(item_path):
                print(f"  Pasta: {item}")
            else:
                print(f"  Arquivo: {item}")
    except FileNotFoundError:
        print(f"A pasta {path} não foi encontrada.")
    except PermissionError:
        print(f"Permissão negada para acessar a pasta {path}.")

if __name__ == '__main__':
    path = r"C:\Users\Bruno\Desktop\Unified_AI_Combat"
    list_directory_contents(path)
