from fastapi import FastAPI, HTTPException, Query
import sqlite3
from typing import List, Dict, Any

app = FastAPI(title="Leis Nova Veneza API", description="API para consulta de leis municipais de Nova Veneza.")

DB_NAME = 'leis-nova-veneza.db'

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/search")
def search_leis(q: str = Query(..., description="Termo de busca")):
    """
    Realiza uma busca textual básica nas leis.
    A busca é feita no título, texto completo e outros metadados.
    """
    if not q:
        raise HTTPException(status_code=400, detail="Query string 'q' is required.")

    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT id, filename, titulo, tipo, numero, data, situacao, url, texto_completo
        FROM leis_municipais 
        WHERE titulo LIKE ? OR texto_completo LIKE ?
        LIMIT 50
    """
    
    search_term = f"%{q}%"
    
    try:
        cursor.execute(query, (search_term, search_term))
        rows = cursor.fetchall()
        
        results = []
        for row in rows:
            results.append(dict(row))
            
        return {"total": len(results), "results": results}
    except sqlite3.OperationalError as e:
        # Se a tabela não existir, provavelmente o banco de dados não foi construído
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        conn.close()

@app.get("/")
def read_root():
    return {"message": "Bem-vindo à API de Leis de Nova Veneza. Acesse /docs para ver a documentação."}
