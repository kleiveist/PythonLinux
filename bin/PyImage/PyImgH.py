#----------------------------------------------------------
# Logdatei aktivieren        (log_enabled):
#     True =               Logging wird aktiviert
#     False =              Logging wird deaktiviert
#----------------------------------------------------------
# Mindestobjektgröße        (tolerance):
#     Höhere Werte =       weniger kleine Objekte
#     Niedrigere Werte =   mehr Details erhalten
#     Empfohlener Bereich: 5-50
#----------------------------------------------------------
# Untere Canny-Schwelle     (canny_threshold1):
#     Niedrigere Werte =   mehr Kanten erkannt
#     Höhere Werte =       weniger Hintergrundrauschen
#     Empfohlener Bereich: 50-150
#----------------------------------------------------------
# Obere Canny-Schwelle      (canny_threshold2):
#     Höhere Werte =       weniger Kanten erkannt
#     Niedrigere Werte =   sensitivere Kantenerkennung
#     Empfohlener Bereich: 150-300
#----------------------------------------------------------
# Kernelgröße               (kernel_size):
#     Größere Werte =      stärkere Maskenausdehnung
#     Kleinere Werte =     präzisere Maskenbegrenzung
#     Empfohlener Bereich: 3-7
#----------------------------------------------------------
# Dilatations-Iterationen   (iterations):
#     Höhere Werte =       stärkere Maskenvergrößerung
#     Niedrigere Werte =   subtilere Anpassung
#     Empfohlener Bereich: 1-3
#----------------------------------------------------------
# Gewichtungsfaktor         (weight_factor):
#     Höhere Werte =       stärkere Dunkelpriorisierung
#     Niedrigere Werte =   ausgewogenere Schwellenwerte
#     Empfohlener Bereich: 0.7-0.9
#----------------------------------------------------------
# Schwellenoffset           (dark_threshold_offset):
#     Höhere Werte =       weniger dunkle Bereiche
#     Niedrigere Werte =   mehr dunkle Elemente
#     Empfohlene Anpassung: ±25
#----------------------------------------------------------
# Mindest-Icongröße         (min_icon_size):
#     Höhere Werte =       Filterung kleiner Objekte
#     Niedrigere Werte =   Beibehaltung kleiner Details
#     Empfohlener Bereich: 100-1000
#----------------------------------------------------------
# =====================================================================================
# KONFIGURATION
# =====================================================================================
import os
import pprint
from PIL import Image
import numpy as np
import cv2

SETTINGS = {
    'logging': {
        'log_enabled': False,        # Logging aktivieren/deaktivieren
        'log_file': "extraction_log.txt"  # Logdateiname
    },
    'paths': {
        'input_folder': os.path.abspath(os.getcwd()),  # Automatischer Eingabeordner
        'output_folder': "Img",    # Ausgabeordner
        'supported_formats': ('.png', '.jpg', '.jpeg', '.bmp', '.tiff')  # Unterstützte Dateitypen
    },
    'processing': {
        'tolerance': 10,             # Mindestobjektgröße in Pixeln (5-50)
        'min_icon_size': 500,        # Mindestgröße für Icons (100-1000)
        'kernel_size': 12,           # Größe des Maskenkerns (3-7)
        'iterations': 1,             # Iterationen für Dilatation (1-3)
        'weight_factor': 0.45,       # Gewichtung Dunkelbereich (0.7-0.9)
        'dark_threshold_offset': 45, # Schwellenwert-Offset (±25),
        'canny': {
            'threshold1': 32,        # Untere Canny-Schwelle (50-150)
            'threshold2': 155        # Obere Canny-Schwelle (150-300)
        }
    }
}
# =====================================================================================
# HILFSFUNKTIONEN
# =====================================================================================
def print_settings():
    """Gibt die aktuellen Einstellungen formatiert aus"""
    print("\n" + "="*80)
    print(" AKTIVE KONFIGURATION ".center(80, '='))
    print("="*80)
    
    # Formatierte Ausgabe der Pfade
    print("Dateipfade:")
    print(f"Eingabeordner: {SETTINGS['paths']['input_folder']}")
    print(f"Ausgabeordner: {os.path.join(SETTINGS['paths']['input_folder'], SETTINGS['paths']['output_folder'])}")
    print(f"Unterstützte Formate: {', '.join(SETTINGS['paths']['supported_formats'])}\n")
    
    # Verarbeitungseinstellungen
    print("Verarbeitungsparameter:")
    print(f"• Mindestobjektgröße: {SETTINGS['processing']['tolerance']}px")
    print(f"• Icon-Mindestgröße: {SETTINGS['processing']['min_icon_size']}px")
    print(f"• Dunkelbereichsgewichtung: {SETTINGS['processing']['weight_factor']}")
    print(f"• Canny-Schwellenwerte: {SETTINGS['processing']['canny']['threshold1']}-{SETTINGS['processing']['canny']['threshold2']}")
    
    print("="*80 + "\n")

def log_message(message):
    """Loggt Meldungen bei aktiviertem Logging"""
    if SETTINGS['logging']['log_enabled']:
        with open(SETTINGS['logging']['log_file'], "a") as log:
            log.write(f"{message}\n")
# =====================================================================================
# HAUPTFUNKTION
# =====================================================================================
def calculate_dark_threshold(gray_image):
    """Berechnet den dynamischen Schwellenwert für dunkle Bereiche"""
    min_b = np.min(gray_image)
    max_b = np.max(gray_image)
    calculated = min_b + SETTINGS['processing']['weight_factor'] * (max_b - min_b)
    return int(calculated + SETTINGS['processing']['dark_threshold_offset'])

def process_image(img_path, output_path):
    """Verarbeitet ein einzelnes Bild"""
    try:
        with Image.open(img_path).convert("RGBA") as img:
            np_img = np.array(img)
            gray = cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2GRAY)
            
            # Dunkelbereichsmaskierung
            dark_threshold = calculate_dark_threshold(gray)
            _, dark_mask = cv2.threshold(gray, dark_threshold, 255, cv2.THRESH_BINARY_INV)
            
            # Kantenerkennung
            edges = cv2.Canny(gray,
                            SETTINGS['processing']['canny']['threshold1'],
                            SETTINGS['processing']['canny']['threshold2'])
            
            # Maskenoptimierung
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, 
                            (SETTINGS['processing']['kernel_size'], 
                             SETTINGS['processing']['kernel_size']))
            edges_dilated = cv2.dilate(edges, kernel, 
                                     iterations=SETTINGS['processing']['iterations'])
            
            # Konturenanalyse
            combined_mask = cv2.bitwise_and(dark_mask, edges_dilated)
            contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, 
                                         cv2.CHAIN_APPROX_SIMPLE)
            filtered_mask = np.zeros_like(combined_mask)
            for cnt in contours:
                if cv2.contourArea(cnt) > SETTINGS['processing']['min_icon_size']:
                    cv2.drawContours(filtered_mask, [cnt], -1, 255, thickness=cv2.FILLED)
            
            # Transparenz anwenden
            np_img[filtered_mask == 0] = (0, 0, 0, 0)
            Image.fromarray(np_img, "RGBA").save(output_path)
            
            log_message(f"Erfolgreich verarbeitet: {os.path.basename(img_path)}")
            return True
            
    except Exception as e:
        error_msg = f"Fehler bei {os.path.basename(img_path)}: {str(e)}"
        log_message(error_msg)
        print(error_msg)
        return False


def run_from_magic(input_dir: str, output_dir: str, silent: bool = False) -> int:
    """Führt PyImgH auf einem Ordner aus (für PyIMagic)."""
    input_dir = os.path.abspath(input_dir)
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    if not silent:
        print(f"[H] Eingang: {input_dir}")
        print(f"[H] Ausgabe: {output_dir}")

    processed_files = 0
    for filename in os.listdir(input_dir):
        if filename.lower().endswith(SETTINGS['paths']['supported_formats']):
            input_path = os.path.join(input_dir, filename)
            output_path = os.path.join(output_dir, filename)
            if process_image(input_path, output_path):
                processed_files += 1

    if not silent:
        print(f"[H] Fertig: {processed_files} Dateien")
    return processed_files
# =====================================================================================
# STARTROUTINE
# =====================================================================================
if __name__ == "__main__":
    print_settings()
    
    # Ordner erstellen
    output_dir = os.path.join(SETTINGS['paths']['input_folder'], 
                            SETTINGS['paths']['output_folder'])
    total = run_from_magic(SETTINGS['paths']['input_folder'], output_dir, silent=True)
    
    print(f"\nVerarbeitung abgeschlossen! {total} Bilder konvertiert.")
    print(f"Ergebnisordner: {output_dir}")
