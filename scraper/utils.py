import os
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.header import Header

# Encontrar el directorio base del proyecto (un nivel arriba de /scraper)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(dotenv_path=os.path.join(BASE_DIR, '.env'))

def get_env():
    """Retorna las variables de entorno configuradas."""
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = os.getenv("SMTP_PORT")
    return {
        "ucm_user": os.getenv("UCM_USER"),
        "ucm_pass": os.getenv("UCM_PASS"),
        "email_user": os.getenv("EMAIL_USER"),
        "email_pass": os.getenv("EMAIL_PASS"),
        "email_to": os.getenv("EMAIL_TO"),
        "SMTP_SERVER": smtp_server if smtp_server else "smtp.gmail.com",
        "SMTP_PORT": smtp_port if smtp_port else "465"
    }

def send_email(subject, body):
    """Envía un correo electrónico de notificación usando SMTP SSL."""
    env = get_env()
    
    if not env["email_user"] or not env["email_pass"] or not env["email_to"]:
        print(" ❗ Faltan credenciales de correo electrónico en el archivo .env. No se pudo enviar el correo.")
        return False
        
    try:
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = Header(subject, 'utf-8')
        msg['From'] = env["email_user"]
        msg['To'] = env["email_to"]

        port = int(env["SMTP_PORT"])
        server = env["SMTP_SERVER"]

        with smtplib.SMTP_SSL(server, port) as smtp:
            smtp.login(env["email_user"], env["email_pass"])
            smtp.send_message(msg)
            
        print(f" ✅ Correo enviado exitosamente a {env['email_to']}")
        return True
    except Exception as e:
        print(f" ❌ Error al enviar correo de notificación: {e}")
        return False
