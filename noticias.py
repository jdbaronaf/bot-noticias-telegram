# Configuración de Telegram
# TOKEN = "8668968223:AAEBbMlX5M4blE9qU-Ln1IJpTVl5ubTdV8A"
#CHANNEL_ID = "-1004298458383"  # O el ID numérico del canal (ej: -100xxxxxxxxxx)
import sqlite3
import feedparser
import requests
from telegram import Bot
from telegram.error import RetryAfter, TimedOut
import asyncio
import urllib.parse
import re
import html
from datetime import datetime

# Configuración de Telegram
TOKEN = "8668968223:AAEBbMlX5M4blE9qU-Ln1IJpTVl5ubTdV8A"
CHANNEL_ID = "-1004298458383"

# Cantidad exacta de noticias NUEVAS que quieres obtener por categoría en cada ejecución
NOTICIAS_POR_CATEGORIA = 15

def init_db():
    conn = sqlite3.connect("noticias_enviadas.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS enviadas (
            link TEXT PRIMARY KEY
        )
    """)
    conn.commit()
    conn.close()

def noticia_fue_enviada(link):
    conn = sqlite3.connect("noticias_enviadas.db")
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM enviadas WHERE link = ?", (link,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def registrar_noticia(link):
    conn = sqlite3.connect("noticias_enviadas.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO enviadas (link) VALUES (?)", (link,))
    conn.commit()
    conn.close()

def limpiar_texto(texto):
    sin_tags = re.sub('<[^<]+?>', '', texto)
    return html.unescape(sin_tags).strip()

def obtener_noticias_google(query):
    query_completa = f"{query} when:1d"
    query_encoded = urllib.parse.quote(query_completa)
    url_rss = f"https://news.google.com/rss/search?q={query_encoded}&hl=es-419&gl=CO&ceid=CO:es-419"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url_rss, headers=headers, timeout=10)
        if response.status_code != 200:
            return []
        
        feed = feedparser.parse(response.content)
        noticias = []
        
        for entry in feed.entries[:50]:
            titulo = limpiar_texto(entry.get('title', 'Sin título'))
            link = entry.get('link', '')
            descripcion = limpiar_texto(entry.get('summary', 'Sin descripción disponible.'))
            
            # Extraer y formatear la fecha de publicación del RSS si está disponible
            published_parsed = entry.get('published_parsed')
            if published_parsed:
                dt = datetime(*published_parsed[:6])
                fecha_formateada = dt.strftime("%Y-%m-%d %H:%M:%S")
            else:
                fecha_formateada = "Fecha no disponible"
            
            if link:
                noticias.append({
                    "titulo": titulo,
                    "link": link,
                    "descripcion": descripcion,
                    "fecha": fecha_formateada
                })
        return noticias
    except Exception as e:
        print(f"Error obteniendo noticias de {query}: {e}")
        return []

async def enviar_noticias():
    bot = Bot(token=TOKEN)
    init_db()
    
    categorias = ["Tecnología", "Colombia", "Cali", "Deportes", "Economía", "Entretenimiento"]
    enviadas_en_esta_sesion = 0
    
    for categoria in categorias:
        todas_las_noticias = obtener_noticias_google(categoria)
        nuevas_de_esta_categoria = 0
        
        print(f"Revisando categoría '{categoria}'...")
        
        for noticia in todas_las_noticias:
            if nuevas_de_esta_categoria >= NOTICIAS_POR_CATEGORIA:
                break
                
            if noticia_fue_enviada(noticia["link"]):
                continue
            
            # Mensaje incluyendo la fecha y hora de publicación
            mensaje = (
                f"📰 <b>{noticia['titulo']}</b>\n\n"
                f"📂 <b>Categoría:</b> {categoria}\n"
                f"⏱ <b>Publicado:</b> {noticia['fecha']}\n\n"
                f"📝 {noticia['descripcion']}\n\n"
                f"🔗 <a href='{noticia['link']}'>Leer noticia completa</a>"
            )
            
            enviado = False
            while not enviado:
                try:
                    await bot.send_message(
                        chat_id=CHANNEL_ID,
                        text=mensaje,
                        parse_mode="HTML",
                        disable_web_page_preview=False
                    )
                    registrar_noticia(noticia["link"])
                    
                    enviadas_en_esta_sesion += 1
                    nuevas_de_esta_categoria += 1
                    enviado = True
                    await asyncio.sleep(4)
                    
                except RetryAfter as e:
                    print(f"Límite de Telegram alcanzado. Esperando {e.retry_after} segundos...")
                    await asyncio.sleep(e.retry_after + 1)
                except TimedOut:
                    print("Conexión lenta. Reintentando en 5 segundos...")
                    await asyncio.sleep(5)
                except Exception as e:
                    print(f"Error al enviar a Telegram: {e}")
                    enviado = True
                    
        print(f"-> Se agregaron {nuevas_de_esta_categoria} noticias nuevas para {categoria}.")
                        
    print(f"Proceso finalizado. Total de noticias nuevas enviadas: {enviadas_en_esta_sesion}.")

if __name__ == "__main__":
    asyncio.run(enviar_noticias())
