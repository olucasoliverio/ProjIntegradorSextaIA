import os
import sqlite3
from dotenv import load_dotenv
from chromadb import Documents, EmbeddingFunction, Embeddings
import chromadb
from langchain.text_splitter import RecursiveCharacterTextSplitter
import vertexai
from vertexai.language_models import TextEmbeddingModel

# Carregar variáveis de ambiente do .env
load_dotenv()

DB_NAME = 'leis-nova-veneza.db'
CHROMA_DIR = './chroma_db'

class VertexEmbeddingFunction(EmbeddingFunction):
    def __init__(self, project_id: str, location: str, model_name: str = "text-embedding-004"):
        vertexai.init(project=project_id, location=location)
        self.model = TextEmbeddingModel.from_pretrained(model_name)

    def __call__(self, input: Documents) -> Embeddings:
        # get_embeddings tem um limite de requisições por batch, 
        # o ChromaDB por padrão passa lotes, então apenas mapeamos para lista
        embeddings = self.model.get_embeddings(input)
        return [embedding.values for embedding in embeddings]

def get_leis_from_sqlite():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    # Vamos pegar apenas as leis que tem texto completo para não quebrar.
    # Em produção, você pode tirar o LIMIT ou rodar em lotes.
    cursor.execute("SELECT * FROM leis_municipais WHERE texto_completo IS NOT NULL AND texto_completo != ''")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def main():
    print("Iniciando processo de vetorização...")
    
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION")
    
    if not project_id or not location:
        print("Erro: GOOGLE_CLOUD_PROJECT e GOOGLE_CLOUD_LOCATION devem estar configurados no .env")
        return

    try:
        embedding_function = VertexEmbeddingFunction(project_id=project_id, location=location)
    except Exception as e:
        print("Erro ao inicializar VertexAIEmbeddings. Verifique se o GOOGLE_APPLICATION_CREDENTIALS está correto no .env")
        print(f"Detalhes do erro: {e}")
        return

    # 2. Configurar o banco vetorial Chroma
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = client.get_or_create_collection(
        name="leis_collection",
        embedding_function=embedding_function
    )

    # 3. Ler dados do SQLite
    leis = get_leis_from_sqlite()
    print(f"Encontradas {len(leis)} leis para processar.")

    # 4. Configurar o fatiador de texto (Text Splitter)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500,
        chunk_overlap=150,
        length_function=len,
        is_separator_regex=False,
    )

    # Chroma pede listas de IDs. Vamos continuar a partir da contagem atual
    global_chunk_id = collection.count()
    
    # Descobre quais leis já foram inseridas para podermos pular
    processed_leis = set()
    try:
        print("Verificando progresso anterior no banco vetorial...")
        # collection.get() retorna tudo se não passar limite
        existing_data = collection.get(include=["metadatas"])
        if existing_data and existing_data["metadatas"]:
            for meta in existing_data["metadatas"]:
                if meta and "id_lei" in meta:
                    processed_leis.add(meta["id_lei"])
        print(f"Encontradas {len(processed_leis)} leis já processadas no ChromaDB. Elas serão ignoradas.")
    except Exception as e:
        print("Aviso ao verificar leis já processadas:", e)

    for i, lei in enumerate(leis):
        if lei['id'] in processed_leis:
            # print(f"[{i+1}/{len(leis)}] Lei já processada. Pulando...") # Opcional: comentar para não poluir o terminal
            continue
            
        print(f"Processando lei {i+1}/{len(leis)}: {lei['titulo'][:50]}...")
        
        texto_completo = lei['texto_completo']
        chunks = text_splitter.split_text(texto_completo)
        
        if not chunks:
            continue
            
        metadatas = []
        ids = []
        
        for idx in range(len(chunks)):
            metadatas.append({
                "id_lei": lei['id'],
                "titulo": lei['titulo'] if lei['titulo'] else "Sem Titulo",
                "tipo": lei['tipo'] if lei['tipo'] else "Desconhecido",
                "numero": lei['numero'] if lei['numero'] else "S/N",
                "data": lei['data'] if lei['data'] else "S/D",
                "situacao": lei['situacao'] if lei['situacao'] else "S/S",
                "url": lei['url'] if lei['url'] else ""
            })
            ids.append(f"chunk_{global_chunk_id}")
            global_chunk_id += 1
            
        # Adiciona no banco vetorial (usando Vertex API em batches pequenos por segurança)
        # vertexai embedding max size is 250 requests per batch usually, 
        # but chromadb handles it or we can batch ourselves.
        try:
            # Chroma max batch is often 100 for some embeddings
            batch_size = 100
            for b in range(0, len(chunks), batch_size):
                collection.add(
                    documents=chunks[b:b+batch_size],
                    metadatas=metadatas[b:b+batch_size],
                    ids=ids[b:b+batch_size]
                )
        except Exception as e:
            print(f"Erro ao inserir a lei {lei['id']}: {e}")

    print(f"\nVetorização concluída! Os vetores foram salvos em {CHROMA_DIR}")
    print("Agora você pode copiar a pasta 'chroma_db' para o seu outro projeto.")

if __name__ == '__main__':
    main()
