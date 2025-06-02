# 🐍 Imagem base com Python
FROM python:3.10

# 📁 Cria diretório da aplicação
WORKDIR /app

# 🧾 Clona o repositório com o app Flask
RUN git clone https://github.com/queziajesuinod/painel_reobote_consorcios.git .

# ✅ Garante que o pip esteja atualizado e instala dependências
RUN pip install --upgrade pip && pip install -r requirements.txt

# 🔐 Cria uma chave secreta temporária para o Flask (melhor usar variável de ambiente em produção)
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# 📂 Expõe a porta padrão do Flask
EXPOSE 8182

# ▶️ Comando para rodar o app
CMD ["python", "app.py"]
