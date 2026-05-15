#!/bin/bash
if [ ! -f "leis-nova-veneza.db" ]; then
    echo "Construindo o banco de dados..."
    python build_db.py
fi
echo "Iniciando a API..."
uvicorn api:app --host 0.0.0.0 --port 8000
