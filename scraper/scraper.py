from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
import re
import json
from time import sleep
from utils import get_env
import os
from datetime import datetime

# --- Importar generador de gráficos ---
try:
    from generate_charts import generate_all_charts
except ImportError:
    # Por si se ejecuta fuera del path correcto
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from generate_charts import generate_all_charts

# --- Importaciones para el correo electrónico ---
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr

# --- Directorio Base y Rutas ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(BASE_DIR, "dashboard", "ramos_con_detalles.json")
SCREENSHOT_PATH = os.path.join(BASE_DIR, "login_error.png")

# --- Configuración del Scraper ---
env_vars = get_env()
USERNAME = env_vars["ucm_user"]
PASSWORD = env_vars["ucm_pass"]
email_user = env_vars["email_user"]
email_pass = env_vars["email_pass"]
email_to = env_vars["email_to"]
smtp_server = env_vars["SMTP_SERVER"]
smtp_port = env_vars["SMTP_PORT"]

HEADLESS = True
OMIT_COMPONENTS = ["Asistencia"]
TARGET_SEMESTER = None  # Si es None, se determinará automáticamente el más reciente

# --- Funciones Auxiliares ---

def parse_float_from_text(text):
    """Convierte texto de nota (ej. '6,7' o '7.0') a float, manejando None o texto vacío."""
    if text is None or text.strip() == "":
        return None
    try:
        cleaned_text = re.sub(r'[^\d,.]', '', text)
        return float(cleaned_text.replace(',', '.'))
    except (ValueError, TypeError):
        return None

def parse_percentage_from_text(text):
    """Extrae el porcentaje de una cadena (ej. 'Parcial 30%')."""
    match = re.search(r'(\d+)%', text)
    return match.group(0) if match else None

def are_floats_approximately_equal(a, b, tolerance=1e-9):
    """Compara si dos floats son aproximadamente iguales, manejando None."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(a - b) < tolerance

def wait_for_correct_course_page(driver, wait, expected_course_name, max_attempts=3):
    """Espera hasta que la página de detalles muestre el ramo correcto."""
    for attempt in range(max_attempts):
        try:
            wait.until(EC.invisibility_of_element_located((By.ID, "sap-ui-blocklayer-popup")))
            course_name_elements = driver.find_elements(By.XPATH, "//span[contains(@class, 'sapMText') and not(contains(text(), 'Semestre'))]")
            current_course_name = None
            for element in course_name_elements:
                text = element.text.strip()
                if text and text != "Nota final" and "Asistencia" not in text:
                    current_course_name = text
                    break
            
            if current_course_name and current_course_name == expected_course_name:
                print(f" ✅ Página de detalles correcta para '{expected_course_name}'.")
                return True
            else:
                print(f" ❗ Intento {attempt + 1}: Página de detalles no muestra el ramo correcto. "
                      f"Esperado: '{expected_course_name}', Encontrado: '{current_course_name}'.")
                sleep(1)
        except Exception as e:
            print(f" ❗ Intento {attempt + 1}: Error al verificar la página de detalles: {e}")
            sleep(1)
            
    print(f" ❌ Fallo al cargar la página de detalles correcta para '{expected_course_name}' después de {max_attempts} intentos.")
    return False

def load_old_results(file_path=JSON_PATH):
    """Carga los resultados de una ejecución anterior si el archivo existe."""
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                return {ramo.get("id_curso"): ramo for ramo in data.get("ramos_con_detalles", []) if ramo.get("id_curso")}
            except json.JSONDecodeError:
                print(f" ❗ Advertencia: El archivo '{file_path}' no es un JSON válido o está vacío.")
                return {}
    return {}

def save_new_results(results, old_results_map, file_path=JSON_PATH):
    """Guarda los resultados actuales en un archivo JSON, manteniendo ramos de semestres anteriores."""
    # Asegurar que el directorio de destino exista
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    new_results_map = {ramo.get("id_curso"): ramo for ramo in results}
    
    # Combinar con los datos antiguos
    final_results = []
    if old_results_map:
        # Mantener ramos antiguos que no están en los resultados nuevos
        for old_ramo_id, old_ramo in old_results_map.items():
            if old_ramo_id not in new_results_map:
                final_results.append(old_ramo)
    
    # Agregar los ramos nuevos/actualizados
    final_results.extend(results)

    json_output = {
        "ramos_con_detalles": final_results
    }
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(json_output, f, indent=4, ensure_ascii=False)
    print(f"\n✅ Resultados guardados en {file_path}: {len(final_results)} ramos procesados.")

    js_path = os.path.join(os.path.dirname(file_path), "ramos_con_detalles.js")
    js_content = (
        "/* Archivo generado automáticamente por el scraper. No editar a mano. */\n"
        "window.ramosData = " + json.dumps(json_output, ensure_ascii=False) + ";\n"
    )
    with open(js_path, "w", encoding="utf-8") as f:
        f.write(js_content)
    print(f"✅ Versión JS para dashboard (file://) guardada en {js_path}.")

def get_latest_semestre(course_rows):
    """Obtiene el semestre más reciente basado en el año y el nombre del semestre."""
    semesters = []
    for row in course_rows:
        try:
            # Extraer el nombre del semestre
            semestre_element = row.find_element(By.XPATH, ".//td[contains(@id, '_cell1')]/span[contains(@class, 'sapMText')]")
            semestre = semestre_element.text.strip()
            # Extraer el año
            year_element = row.find_element(By.XPATH, ".//td[@data-sap-ui-column='yrColumn']/span[contains(@class, 'sapMText')]")
            year_match = re.search(r'\d{4}', year_element.text.strip())
            year = year_match.group(0) if year_match else str(datetime.now().year)
            
            if semestre:
                semesters.append((semestre, year))
        except NoSuchElementException:
            continue
            
    if not semesters:
        print(" ❗ Advertencia: No se pudo identificar ningún semestre.")
        return None
    
    # Ordenar semestres por año (descendente) y luego por nombre (Semestre 1 (Pre) antes que Semestre 2)
    def semester_sort_key(sem):
        semestre, year = sem
        priority = 1 if "Semestre 1" in semestre else 0
        return (int(year), priority)
    
    latest_semestre, latest_year = max(semesters, key=semester_sort_key)
    latest_semestre_with_year = f"{latest_semestre} {latest_year}"
    print(f" ✅ Semestre más reciente identificado: '{latest_semestre_with_year}'")
    return latest_semestre_with_year

def send_email_notification(subject, body, to_email, from_email, from_password):
    """Envía un correo electrónico con el asunto y cuerpo especificados."""
    try:
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = Header(subject, 'utf-8')
        msg['From'] = formataddr(('Notificador de Notas UCM', from_email))
        msg['To'] = to_email

        with smtplib.SMTP_SSL(smtp_server, int(smtp_port)) as smtp:
            smtp.login(from_email, from_password)
            smtp.send_message(msg)
        print(f" ✅ Correo de notificación enviado a {to_email} con asunto: '{subject}'")
        return True
    except Exception as e:
        print(f" ❌ Error al enviar correo: {e}")
        return False

def compare_and_notify_changes(old_results_map, new_results, target_semestre=None, email_config=None):
    """
    Compara resultados antiguos con nuevos y notifica los cambios,
    filtrando por semestre si se especifica y enviando correo si hay cambios.
    """
    print("\n--- Verificando cambios en las notas ---")
    changes_found = False
    notification_messages = []

    for new_ramo in new_results:
        if target_semestre and new_ramo.get("semestre") != target_semestre:
            continue

        new_ramo_id = new_ramo.get("id_curso")
        old_ramo = old_results_map.get(new_ramo_id)
        ramo_name = new_ramo.get('nombre', 'Nombre Desconocido')

        if not old_ramo:
            message = f"🆕 Nuevo ramo detectado: '{ramo_name}'."
            print(f" {message}")
            notification_messages.append(message)
            changes_found = True
            continue

        # Comparar Nota Final
        old_nota_final = old_ramo.get("nota_final")
        new_nota_final = new_ramo.get("nota_final")
        if not are_floats_approximately_equal(old_nota_final, new_nota_final):
            changes_found = True
            message = (f"🔔 Cambio en '{ramo_name}':\n"
                       f"   - Nota Final: {old_nota_final} -> {new_nota_final}")
            print(f" {message}")
            notification_messages.append(message)

        # Comparar Componentes de Nota
        old_componentes = old_ramo.get("componentes", [])
        new_componentes = new_ramo.get("componentes", [])

        old_comp_dict = {(comp.get("nombre"), comp.get("porcentaje")): comp.get("nota") for comp in old_componentes}
        new_comp_dict = {(comp.get("nombre"), comp.get("porcentaje")): comp.get("nota") for comp in new_componentes}

        for comp_key, new_comp_note in new_comp_dict.items():
            comp_name, comp_percentage = comp_key
            if comp_name in OMIT_COMPONENTS:
                continue

            old_comp_note = old_comp_dict.get(comp_key)

            if old_comp_note is None and new_comp_note is not None:
                changes_found = True
                message = (f"🔔 Nueva nota detectada en '{ramo_name}' - Componente '{comp_name}' ({comp_percentage}):\n"
                           f"   - Nota: {new_comp_note}")
                print(f" {message}")
                notification_messages.append(message)
            elif not are_floats_approximately_equal(old_comp_note, new_comp_note):
                changes_found = True
                message = (f"🔔 Cambio en '{ramo_name}' - Componente '{comp_name}' ({comp_percentage}):\n"
                           f"   - Nota: {old_comp_note} -> {new_comp_note}")
                print(f" {message}")
                notification_messages.append(message)
        
        # Detectar componentes eliminados
        for old_comp_key, old_comp_note in old_comp_dict.items():
            if old_comp_key not in new_comp_dict and old_comp_key[0] not in OMIT_COMPONENTS:
                changes_found = True
                message = (f"🔔 Componente eliminado en '{ramo_name}':\n"
                           f"   - Componente: '{old_comp_key[0]}' ({old_comp_key[1]}) con nota {old_comp_note}")
                print(f" {message}")
                notification_messages.append(message)

    if not changes_found:
        print(" ✅ No se encontraron cambios en las notas de los ramos existentes.")
    else:
        if email_config:
            subject = "📢 ¡Cambios detectados en tus notas UCM!"
            full_body = "Hola,\n\nSe han detectado los siguientes cambios en tus notas UCM:\n\n" + "\n".join(notification_messages) + "\n\nSaludos,\nTu Notificador de Notas"
            send_email_notification(subject, full_body,
                                    email_config["to_email"],
                                    email_config["from_email"],
                                    email_config["from_password"])
        else:
            print(" ❗ Configuración de correo no proporcionada. No se envió notificación por email.")

def main():
    if not USERNAME or not PASSWORD:
        print(" ❌ Error: Credenciales de la UCM (UCM_USER, UCM_PASS) no configuradas en el archivo .env.")
        return

    options = Options()
    if HEADLESS:
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1920")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-extensions")
        options.add_experimental_option('excludeSwitches', ['enable-logging'])

    driver = None
    resultados_finales = []
    
    # Cargar las credenciales de correo electrónico
    email_config = None
    if email_user and email_pass and email_to:
        email_config = {
            "from_email": email_user,
            "from_password": email_pass,
            "to_email": email_to
        }
        print(" ✅ Configuración de correo cargada.")
    else:
        print(" ❗ Advertencia: Faltan credenciales de correo electrónico en el archivo .env. No se enviarán notificaciones.")

    try:
        driver = webdriver.Chrome(options=options)
        wait = WebDriverWait(driver, 30)

        old_results_map = load_old_results()
        json_exists = os.path.exists(JSON_PATH)

        url_inicio = "https://sapprd.ucm.cl/sap/bc/ui2/flp?sap-ushell-config=embedded#CompetencyEvidence-display"
        driver.get(url_inicio)

        wait.until(EC.element_to_be_clickable((By.ID, "USERNAME_FIELD-inner"))).send_keys(USERNAME)
        driver.find_element(By.ID, "PASSWORD_FIELD-inner").send_keys(PASSWORD)
        wait.until(EC.element_to_be_clickable((By.ID, "LOGIN_LINK"))).click()
        wait.until(EC.url_contains("flp?sap-ushell-config=embedded#CompetencyEvidence-display"))

        try:
            wait.until(EC.invisibility_of_element_located((By.ID, "sap-ui-blocklayer-popup")))
            print(" ✅ Blocklayer popup disappeared after login.")
        except TimeoutException:
            print(" ❗ Advertencia: Blocklayer popup no desapareció o no existe después del login.")

        wait.until(EC.visibility_of_all_elements_located((
            By.XPATH, "//tr[starts-with(@id, '__item') and contains(@id, 'gradeList-') and contains(@class, 'sapMLIBActionable')]"
        )))
        print(" ✅ Lista principal de ramos cargada y visible después del login.")

        course_rows = wait.until(EC.visibility_of_all_elements_located((
            By.XPATH, "//tr[starts-with(@id, '__item') and contains(@id, 'gradeList-') and contains(@class, 'sapMLIBActionable')]"
        )))

        if not course_rows:
            print("❗ Advertencia: No se encontraron filas de cursos con el XPath especificado.")
            return

        latest_semestre_to_process = TARGET_SEMESTER
        if json_exists and not latest_semestre_to_process:
            latest_semestre_to_process = get_latest_semestre(course_rows)
            if not latest_semestre_to_process:
                print(" ❗ No se pudo determinar el semestre más reciente. Procesando todos los ramos.")
                json_exists = False

        if json_exists and latest_semestre_to_process:
            filtered_rows = []
            for row in course_rows:
                try:
                    semestre_element = row.find_element(By.XPATH, ".//td[contains(@id, '_cell1')]/span[contains(@class, 'sapMText')]")
                    semestre = semestre_element.text.strip()
                    year_element = row.find_element(By.XPATH, ".//td[@data-sap-ui-column='yrColumn']/span[contains(@class, 'sapMText')]")
                    year_match = re.search(r'\d{4}', year_element.text.strip())
                    year = year_match.group(0) if year_match else str(datetime.now().year)
                    semestre_with_year = f"{semestre} {year}"
                    if semestre_with_year == latest_semestre_to_process:
                        filtered_rows.append(row)
                except NoSuchElementException:
                    print(f" ❗ No se pudo extraer el semestre o año para una fila. Saltando...")
                    continue
            course_rows = filtered_rows
            print(f" ✅ Procesando {len(course_rows)} ramos del semestre '{latest_semestre_to_process}'.")
        else:
            print(f" ✅ Procesando todos los ramos disponibles ({len(course_rows)} ramos).")

        row_ids = [row.get_attribute("id") for row in course_rows]
        
        for i, row_id in enumerate(row_ids):
            nombre_ramo = "Nombre no encontrado"
            nota_final = None
            course_id = "N/A"
            componentes_nota = []
            semestre = "Semestre no encontrado"

            try:
                wait.until(EC.invisibility_of_element_located((By.ID, "sap-ui-blocklayer-popup")))
                current_row = wait.until(EC.element_to_be_clickable((By.ID, row_id)))

                nombre_ramo_span = current_row.find_element(By.XPATH, ".//td[contains(@id, '_cell2')]/span[contains(@class, 'sapMText')]")
                nombre_ramo = nombre_ramo_span.text.strip()
                
                try:
                    semestre_element = current_row.find_element(By.XPATH, ".//td[contains(@id, '_cell1')]/span[contains(@class, 'sapMText')]")
                    semestre_raw = semestre_element.text.strip()
                    year_element = current_row.find_element(By.XPATH, ".//td[@data-sap-ui-column='yrColumn']/span[contains(@class, 'sapMText')]")
                    year_match = re.search(r'\d{4}', year_element.text.strip())
                    year = year_match.group(0) if year_match else str(datetime.now().year)
                    semestre = f"{semestre_raw} {year}"
                except NoSuchElementException:
                    print(f" ❗ No se pudo extraer el semestre o año para '{nombre_ramo}'.")

                print(f"--- Procesando Ramo: '{nombre_ramo}' (ID: {row_id}, Semestre: {semestre}) ---")

                current_row.click()
                wait.until(EC.url_contains("CourseID="))

                if not wait_for_correct_course_page(driver, wait, nombre_ramo):
                    print(f"❌ No se pudo cargar la página correcta para '{nombre_ramo}'. Saltando...")
                    driver.back()
                    wait.until(EC.url_contains("#CompetencyEvidence-display"))
                    wait.until(EC.invisibility_of_element_located((By.ID, "sap-ui-blocklayer-popup")))
                    wait.until(EC.visibility_of_all_elements_located((
                        By.XPATH, "//tr[starts-with(@id, '__item') and contains(@id, 'gradeList-') and contains(@class, 'sapMLIBActionable')]"
                    )))
                    continue

                wait.until(EC.visibility_of_element_located((By.XPATH, "//span[contains(@class, 'overall_col') and text()='Nota final']")))
                print(" ✅ Página de detalles cargada y estabilizada.")

                current_url = driver.current_url
                match = re.search(r"CourseID='(\d+)'", current_url)
                if match:
                    course_id = match.group(1)
                    print(f" ✅ CourseID para '{nombre_ramo}' extraído de URL: {course_id}")
                else:
                    print(f" ❗ No se encontró CourseID en la URL para '{nombre_ramo}'.")
                    course_id = "ID_NO_ENCONTRADO_EN_URL"

                try:
                    nota_final_label_element = driver.find_element(By.XPATH, "//span[contains(@class, 'overall_col') and text()='Nota final']")
                    dynamic_id_part = nota_final_label_element.get_attribute("id").split('-', 1)[1]
                    nota_final_value_xpath = f"//span[contains(@id, '__status4-{dynamic_id_part}-text') and contains(@class, 'sapMObjStatusText')]"
                    nota_final_value_spans = driver.find_elements(By.XPATH, nota_final_value_xpath)

                    if nota_final_value_spans:
                        nota_final = parse_float_from_text(nota_final_value_spans[0].text.strip())
                        print(f" ✅ Nota final extraída: {nota_final}")
                    else:
                        print(f" ❗ Nota final: No se encontró valor numérico o elemento.")
                        nota_final = None

                except (NoSuchElementException, TimeoutException) as e_nota_final:
                    print(f" ❗ No se pudo extraer la nota final de la página de detalles: {e_nota_final}")
                    nota_final = None

                componente_labels_elements = driver.find_elements(By.XPATH, "//span[contains(@class, 'overall_col') and not(text()='Nota final')]")

                for label_element in componente_labels_elements:
                    nombre_comp_raw = label_element.text.strip()

                    if "Asistencia" in nombre_comp_raw:
                        print(f" ✅ Componente '{nombre_comp_raw}' omitido por configuración.")
                        continue

                    porcentaje_comp = parse_percentage_from_text(nombre_comp_raw)
                    nombre_comp = nombre_comp_raw.replace(porcentaje_comp, '').strip() if porcentaje_comp else nombre_comp_raw

                    nota_comp = None
                    try:
                        dynamic_id_part_comp = label_element.get_attribute("id").split('-', 1)[1]
                        nota_comp_value_xpath = f"//span[contains(@id, '__status4-{dynamic_id_part_comp}-text') and contains(@class, 'sapMObjStatusText')]"
                        nota_comp_spans = driver.find_elements(By.XPATH, nota_comp_value_xpath)

                        if nota_comp_spans:
                            nota_comp = parse_float_from_text(nota_comp_spans[0].text.strip())
                            print(f" ✅ Componente '{nombre_comp}' ({porcentaje_comp}): {nota_comp}")
                        else:
                            print(f" ❗ Componente '{nombre_comp}' ({porcentaje_comp}): No se encontró nota visible.")

                    except (NoSuchElementException, TimeoutException) as e_nota_comp:
                        print(f" ❗ Error al extraer nota del componente '{nombre_comp_raw}': {e_nota_comp}")

                    if nombre_comp:
                        componentes_nota.append({
                            "nombre": nombre_comp,
                            "porcentaje": porcentaje_comp,
                            "nota": nota_comp
                        })

                print(f" ✅ Componentes extraídos: {componentes_nota}")

                resultados_finales.append({
                    "nombre": nombre_ramo,
                    "nota_final": nota_final,
                    "id_curso": course_id,
                    "componentes": componentes_nota,
                    "semestre": semestre
                })

                driver.back()
                wait.until(EC.url_contains("#CompetencyEvidence-display"))

                try:
                    wait.until(EC.invisibility_of_element_located((By.ID, "sap-ui-blocklayer-popup")))
                except TimeoutException:
                    pass

                wait.until(EC.visibility_of_all_elements_located((
                    By.XPATH, "//tr[starts-with(@id, '__item') and contains(@id, 'gradeList-') and contains(@class, 'sapMLIBActionable')]"
                )))
                print(" ✅ Volvimos a la lista principal de ramos.")

            except (TimeoutException, NoSuchElementException, WebDriverException) as e_ramo:
                print(f"❌ Error al procesar el ramo '{nombre_ramo}' (ID: {row_id}): {e_ramo}")
                resultados_finales.append({
                    "nombre": nombre_ramo,
                    "nota_final": nota_final,
                    "id_curso": course_id,
                    "componentes": componentes_nota,
                    "semestre": semestre,
                    "error": str(e_ramo)
                })
                try:
                    driver.back()
                    wait.until(EC.url_contains("#CompetencyEvidence-display"))
                    wait.until(EC.invisibility_of_element_located((By.ID, "sap-ui-blocklayer-popup")))
                    wait.until(EC.visibility_of_all_elements_located((
                        By.XPATH, "//tr[starts-with(@id, '__item') and contains(@id, 'gradeList-') and contains(@class, 'sapMLIBActionable')]"
                    )))
                except Exception as e_recovery:
                    print(f" ❗ Fallo al intentar volver a la lista principal: {e_recovery}")
                    break

        compare_and_notify_changes(old_results_map, resultados_finales,
                                   latest_semestre_to_process if json_exists else None,
                                   email_config=email_config)

    except Exception as e_general:
        print(f" ❌ Ocurrió un error inesperado en la función principal: {e_general}")
        if driver:
            try:
                driver.save_screenshot(SCREENSHOT_PATH)
                print(f" 📸 Captura de pantalla del error guardada como '{SCREENSHOT_PATH}'.")
            except Exception as e_ss:
                print(f" ❗ No se pudo guardar la captura de pantalla: {e_ss}")
    finally:
        save_new_results(resultados_finales, old_results_map)
        if driver:
            driver.quit()
            print(" ✅ Navegador cerrado.")
            
        # Regenerar los gráficos automáticamente al finalizar
        try:
            print(" 📊 Regenerando gráficos estadísticos...")
            generate_all_charts()
        except Exception as e_charts:
            print(f" ❗ Error al actualizar los gráficos: {e_charts}")
            
        print("\n✅ Extracción de ramos y sus componentes finalizada.")

if __name__ == "__main__":
    main()
