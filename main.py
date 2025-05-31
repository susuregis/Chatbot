from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

cardapio = {
    "Entrada": [
        {"nome": "Bruschetta", "descricao": "Pão com tomate", "preco": 12.00}
    ],
    "Prato Principal": [
        {"nome": "Feijoada", "descricao": "Completa com arroz e farofa", "preco": 38.00}
    ],
    "Bebida": [
        {"nome": "Suco de Laranja", "descricao": "Natural", "preco": 7.00}
    ],
    "Sobremesa": [
        {"nome": "Mousse de Maracujá", "descricao": "Com chantilly", "preco": 10.00}
    ]
}

@app.get("/cardapio")
def get_cardapio():
    return cardapio



frete = {
    "centro": 10.00,
    "jardim": 8.00,
    "vila nova": 12.00,
    "planalto": 15.00
}

@app.get("/frete")
def get_frete():
    return frete