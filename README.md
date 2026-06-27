# Notificador de Notas UCM 🎓

Este proyecto es un sistema automatizado para alumnos de la **Universidad Católica del Maule (UCM)**. Permite extraer tus notas del portal institucional, enviarte notificaciones por correo electrónico cada vez que se publique o modifique una calificación, y visualizar tu avance e historial académico mediante un dashboard web interactivo.

---

## 🚀 Características
*   **Web Scraping con Selenium**: Autologin y extracción automática de notas del portal SAP UCM.
*   **Notificaciones por Correo**: Alertas automatizadas por email detallando notas nuevas o modificadas (evaluaciones parciales y nota final).
*   **Generación de Gráficos**: Reportes estadísticos de rendimiento (promedios, distribución de notas, etc.) actualizados de forma automática.
*   **Dashboard Interactivo**: Panel web HTML/JS responsivo con soporte para modo oscuro que permite buscar, filtrar y analizar tus materias de forma visual utilizando Chart.js.
*   **GitHub Actions**: Programación en la nube para ejecutar el scraper cada 1 hora de forma automática y mantener el dashboard remoto al día.

---

## 📁 Estructura del Proyecto
```
ucmNotifier/
├── .github/workflows/
│   └── scrape.yml             # Programación de scraping automático por hora
├── scraper/
│   ├── scraper.py             # Script principal de extracción (Selenium)
│   ├── utils.py               # Cargador de variables de entorno y utilidad de email
│   └── generate_charts.py     # Generador de analíticas de notas en gráficos
├── dashboard/
│   ├── index.html             # Interfaz del dashboard interactivo
│   ├── ramos_con_detalles.json # Base de datos local con las notas en formato JSON
│   └── public/
│       └── images/            # Ubicación de los gráficos generados (.png)
├── .gitignore                 # Exclusión de archivos confidenciales (.env)
├── requirements.txt           # Dependencias de Python requeridas
└── README.md                  # Este archivo de documentación
```

---

## 🛠️ Instalación y Configuración

### 1. Clonar el repositorio
```bash
git clone https://github.com/CdeCevin/ucmNotifier.git
cd ucmNotifier
```

### 2. Instalar las dependencias
Recomendamos usar un entorno virtual de Python:
```bash
python -m venv venv
source venv/Scripts/activate  # En Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configurar variables de entorno (`.env`)
Crea un archivo llamado `.env` en la raíz del proyecto y añade tus credenciales. **Este archivo está configurado en `.gitignore` para no subirse nunca a GitHub por seguridad.**

```ini
# Credenciales del Portal Académico UCM
UCM_USER=tu_rut_sin_puntos_ni_dv (ej: 21323396)
UCM_PASS=tu_clave_de_acceso

# Configuración del correo remitente (SMTP Gmail)
EMAIL_USER=tu_correo_de_envio@gmail.com
# Debes generar una "Contraseña de aplicación" en tu cuenta de Google
EMAIL_PASS=tu_contraseña_de_aplicacion_gmail 

# Correo destinatario (donde quieres recibir las alertas de notas)
EMAIL_TO=tu_correo_personal@gmail.com

# Opcional (Servidor SMTP por defecto es Gmail)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=465
```

---

## 💻 Uso Local

### 1. Ejecutar el Scraper
El scraper iniciará sesión, descargará las notas del semestre actual, comparará si hay cambios con respecto a los datos locales y enviará un correo si encuentra novedades. También regenerará los gráficos estadísticos automáticamente.

```bash
python scraper/scraper.py
```

### 2. Iniciar el Dashboard Web
Dado que los navegadores bloquean las peticiones CORS en archivos locales, abre el servidor web integrado de Python:
```bash
python -m http.server 8000
```
Luego, accede en tu navegador a:
👉 **[http://localhost:8000/dashboard/index.html](http://localhost:8000/dashboard/index.html)**

---

## 🤖 Automatización con GitHub Actions

El proyecto incluye un flujo de trabajo para ejecutar el scraper en la nube **cada 1 hora** e integrar automáticamente las notas actualizadas al dashboard en tu repositorio.

### Pasos para Activar los Secretos en GitHub:
Para que GitHub pueda iniciar sesión en el portal UCM y enviar correos sin exponer tus datos, debes agregarlos como Secretos de Acción en tu repositorio:

1.  Ve a tu repositorio en GitHub.
2.  Navega a **Settings** -> **Secrets and variables** -> **Actions**.
3.  Haz clic en **New repository secret** y añade los siguientes valores:
    *   `UCM_USER`: Tu usuario UCM.
    *   `UCM_PASS`: Tu contraseña UCM.
    *   `EMAIL_USER`: Correo remitente SMTP.
    *   `EMAIL_PASS`: Contraseña de aplicación SMTP.
    *   `EMAIL_TO`: Correo de recepción.
4.  Asegúrate de habilitar los permisos de escritura para que el flujo pueda guardar los resultados de vuelta en el repositorio:
    *   En **Settings** -> **Actions** -> **General** -> **Workflow permissions**.
    *   Selecciona **Read and write permissions** y haz clic en **Save**.
