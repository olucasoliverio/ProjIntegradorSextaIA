import os
import re
import sqlite3

def parse_markdown(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract titulo from the first line (e.g. # DECRETO DP Nº 01...)
    titulo_match = re.search(r'^#\s+(.+)', content, re.MULTILINE)
    titulo = titulo_match.group(1).strip() if titulo_match else ""

    # Extract properties
    tipo_match = re.search(r'\*\*Tipo:\*\*\s*(.*)', content)
    tipo = tipo_match.group(1).strip() if tipo_match else ""

    numero_match = re.search(r'\*\*Número:\*\*\s*(.*)', content)
    numero = numero_match.group(1).strip() if numero_match else ""

    data_match = re.search(r'\*\*Data:\*\*\s*(.*)', content)
    data = data_match.group(1).strip() if data_match else ""

    situacao_match = re.search(r'\*\*Situação:\*\*\s*(.*)', content)
    situacao = situacao_match.group(1).strip() if situacao_match else ""

    url_match = re.search(r'\*\*URL:\*\*\s*(.*)', content)
    url = url_match.group(1).strip() if url_match else ""

    # Extract texto completo
    texto_completo_match = re.search(r'##\s+Texto Completo(.*)', content, re.DOTALL | re.IGNORECASE)
    if texto_completo_match:
        texto_completo = texto_completo_match.group(1).strip()
    else:
        texto_completo = ""

    return {
        'filename': os.path.basename(filepath),
        'titulo': titulo,
        'tipo': tipo,
        'numero': numero,
        'data': data,
        'situacao': situacao,
        'url': url,
        'texto_completo': texto_completo
    }

def main():
    leis_dir = 'leis'
    db_name = 'leis-nova-veneza.db'
    
    print(f"Lendo arquivos de: {leis_dir}")
    if not os.path.exists(leis_dir):
        print(f"Diretório {leis_dir} não encontrado.")
        return

    files = [f for f in os.listdir(leis_dir) if f.endswith('.md')]
    print(f"Total de arquivos encontrados: {len(files)}")

    data_to_insert = []
    for file in files:
        filepath = os.path.join(leis_dir, file)
        try:
            parsed_data = parse_markdown(filepath)
            data_to_insert.append((
                parsed_data['filename'],
                parsed_data['titulo'],
                parsed_data['tipo'],
                parsed_data['numero'],
                parsed_data['data'],
                parsed_data['situacao'],
                parsed_data['url'],
                parsed_data['texto_completo']
            ))
        except Exception as e:
            print(f"Erro ao processar arquivo {file}: {e}")

    print(f"Conectando ao banco de dados: {db_name}")
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Create table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leis_municipais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            titulo TEXT,
            tipo TEXT,
            numero TEXT,
            data TEXT,
            situacao TEXT,
            url TEXT,
            texto_completo TEXT
        )
    ''')

    # Optional: Clear existing data to avoid duplicates if run multiple times
    cursor.execute('DELETE FROM leis_municipais')

    print("Inserindo dados no banco...")
    cursor.executemany('''
        INSERT INTO leis_municipais (filename, titulo, tipo, numero, data, situacao, url, texto_completo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', data_to_insert)

    conn.commit()
    conn.close()
    
    print("Processo concluído com sucesso!")

if __name__ == '__main__':
    main()
