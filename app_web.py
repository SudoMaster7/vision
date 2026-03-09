try:
    import cv2
except Exception:
    cv2 = None

try:
    import mediapipe as mp
except Exception:
    mp = None

try:
    import numpy as np
except Exception:
    np = None
import os
import json
import datetime
try:
    import sounddevice as sd
except Exception:
    sd = None
import time
import threading
from flask import Flask, render_template, Response, jsonify, request, redirect, url_for
from werkzeug.utils import secure_filename

app = Flask(__name__)
CLOUD_MODE = os.getenv("VERCEL") == "1" and bool(os.getenv("VERCEL_URL"))
CV_AVAILABLE = cv2 is not None and mp is not None and np is not None

# --- Locks para thread safety ---
camera_lock = threading.Lock()
estado_lock = threading.Lock()
pintura_lock = threading.Lock()
musica_lock = threading.Lock()

# --- Cache de listagem de câmeras ---
_cameras_cache = []
_cameras_cache_ts = 0
_CAMERAS_CACHE_TTL = 10  # segundos

# --- Configurações MediaPipe ---
try:
    mp_maos = mp.solutions.hands if mp is not None else None
    mp_rosto = mp.solutions.face_mesh if mp is not None else None
    mp_desenho = mp.solutions.drawing_utils if mp is not None else None
    mp_drawing_styles = mp.solutions.drawing_styles if mp is not None else None
except AttributeError:
    mp_maos = mp_rosto = mp_desenho = mp_drawing_styles = None
    CV_AVAILABLE = False

def inicializar_mediapipe():
    if not CV_AVAILABLE or CLOUD_MODE:
        return None, None

    try:
        maos_local = mp_maos.Hands(
            static_image_mode=False,
            max_num_hands=2,
            model_complexity=0,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

        rosto_local = mp_rosto.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

        return maos_local, rosto_local
    except FileNotFoundError as erro:
        mensagem = (
            "\n[ERRO] Falha ao iniciar MediaPipe.\n"
            "No Windows, isso normalmente acontece quando o ambiente virtual está em caminho com acento (ex.: 'Área de Trabalho').\n"
            "Solução recomendada:\n"
            "1) Criar venv em caminho sem acentos, por exemplo: C:/venvs/visionsudo311\n"
            "2) Instalar dependências nele\n"
            "3) Rodar com: C:/venvs/visionsudo311/Scripts/python.exe app_web.py\n"
        )
        raise RuntimeError(mensagem) from erro


maos, rosto = inicializar_mediapipe()

# Instância separada do MediaPipe para Pintura Virtual (thread safety)
def _inicializar_maos_pintura():
    if not CV_AVAILABLE or CLOUD_MODE or mp_maos is None:
        return None
    try:
        return mp_maos.Hands(
            static_image_mode=False,
            max_num_hands=1,
            model_complexity=0,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
    except Exception:
        return None

maos_pintura = _inicializar_maos_pintura()

# Instância separada do MediaPipe para Música Virtual (thread safety)
def _inicializar_maos_musica():
    if not CV_AVAILABLE or CLOUD_MODE or mp_maos is None:
        return None, None
    try:
        m = mp_maos.Hands(
            static_image_mode=False,
            max_num_hands=2,
            model_complexity=0,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        r = mp_rosto.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        ) if mp_rosto is not None else None
        return m, r
    except Exception:
        return None, None

maos_musica, rosto_musica = _inicializar_maos_musica()

# Estado Global
estado_atual = {
    "gesto": "Nenhum",
    "gesto_principal": "Nenhuma mao",
    "expressao": "Neutro",
    "imagem": "neutro.jpg"
}

config_dispositivos = {
    "camera_index": 0,
    "microfone_index": None
}

estado_musica = {
    "gesto_direita": "Nenhum",
    "gesto_esquerda": "Nenhum",
    "pos_direita": {"x": 0.5, "y": 0.5},
    "pos_esquerda": {"x": 0.5, "y": 0.5},
    "expressao": "Neutro",
    "dedos_direita": 0,
    "dedos_esquerda": 0,
    "gesto_combinado": "Nenhum",
    "movimento_direita": "Parado",
    "movimento_esquerda": "Parado",
    "velocidade_direita": 0.0,
    "velocidade_esquerda": 0.0
}

# Histórico de posições para detecção de movimento (últimas N posições do pulso)
_HIST_MAX = 8
_historico_pos = {
    "Right": [],   # lista de (x, y, timestamp)
    "Left": []
}

# --- Mapeamento Gesto → Imagem (configurável) ---
GESTURE_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gesture_config.json")

MAPEAMENTO_PADRAO = {
    "OK": "ok.jpg",
    "LIKE": "like.jpg",
    "Paz e Amor": "paz.jpg",
    "Rock": "like.jpg",
    "Apontando": "neutro.jpg",
    "Mao Aberta": "sol.jpg",
    "Punho Fechado": "lua.jpg",
    "Sorriso": "sorriso.jpg",
    "Surpresa": "surpresa.jpg",
    "Olhos Fechados": "olhos_fechados.jpg",
    "Neutro": "neutro.jpg"
}

def _carregar_mapeamento():
    """Carrega mapeamento de gesture_config.json ou retorna padrão."""
    if os.path.exists(GESTURE_CONFIG_FILE):
        try:
            with open(GESTURE_CONFIG_FILE, "r", encoding="utf-8") as f:
                dados = json.load(f)
            # Mesclar com padrão para garantir todas as chaves
            resultado = dict(MAPEAMENTO_PADRAO)
            resultado.update(dados)
            return resultado
        except Exception:
            pass
    return dict(MAPEAMENTO_PADRAO)

def _salvar_mapeamento(mapeamento):
    """Salva mapeamento em gesture_config.json."""
    with open(GESTURE_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(mapeamento, f, ensure_ascii=False, indent=2)

mapeamento_gestos = _carregar_mapeamento()

cap = None

def _probar_camera_con_timeout(idx, timeout=4.0):
    """Tenta abrir uma câmera com timeout para não travar em CAP_DSHOW."""
    resultado = [False]

    def _tentar():
        try:
            t = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if t.isOpened():
                resultado[0] = True
                t.release()
            else:
                t.release()
        except Exception:
            pass

    th = threading.Thread(target=_tentar, daemon=True)
    th.start()
    th.join(timeout=timeout)
    return resultado[0]

_scan_em_andamento = False

def _scan_cameras_background():
    """Escaneia câmeras em background e atualiza o cache."""
    global _cameras_cache, _cameras_cache_ts, _scan_em_andamento

    if cv2 is None or CLOUD_MODE:
        return

    if _scan_em_andamento:
        return
    _scan_em_andamento = True

    try:
        cameras = []
        idx_ativo = config_dispositivos.get("camera_index", 0)

        # Incluir a câmera ativa sem testar (já sabemos que funciona)
        cameras.append({"index": idx_ativo, "nome": f"Câmera {idx_ativo}"})

        for idx in range(6):  # max 6 câmeras
            if idx == idx_ativo:
                continue
            if _probar_camera_con_timeout(idx, timeout=4.0):
                cameras.append({"index": idx, "nome": f"Câmera {idx}"})

        cameras.sort(key=lambda c: c["index"])
        _cameras_cache = cameras
        _cameras_cache_ts = time.time()
    finally:
        _scan_em_andamento = False

def listar_cameras(max_tentativas=6):
    """Retorna cache de câmeras. Se vazio, retorna a câmera ativa como fallback."""
    global _cameras_cache, _cameras_cache_ts

    if cv2 is None or CLOUD_MODE:
        return []

    # Se tem cache válido, retorna
    if _cameras_cache:
        return _cameras_cache

    # Fallback: retorna pelo menos a câmera ativa
    idx_ativo = config_dispositivos.get("camera_index", 0)
    return [{"index": idx_ativo, "nome": f"Câmera {idx_ativo}"}]

# Iniciar scan de câmeras em background (com delay para dar tempo ao sistema)
def _scan_delayed():
    time.sleep(3)  # esperar backend DirectShow estabilizar
    _scan_cameras_background()

if CV_AVAILABLE and not CLOUD_MODE:
    threading.Thread(target=_scan_delayed, daemon=True).start()

def _tentar_abrir_camera_por_indice(index):
    if cv2 is None or CLOUD_MODE:
        return None

    if index is None:
        return None

    tentativa = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if not tentativa.isOpened():
        tentativa.release()
        tentativa = cv2.VideoCapture(index)

    if not tentativa.isOpened():
        tentativa.release()
        return None

    return tentativa

def listar_microfones():
    if sd is None or CLOUD_MODE:
        return []

    microfones = []
    try:
        dispositivos = sd.query_devices()
        for idx, dispositivo in enumerate(dispositivos):
            if dispositivo.get("max_input_channels", 0) > 0:
                microfones.append({"index": idx, "nome": dispositivo.get("name", f"Microfone {idx}")})
    except Exception:
        microfones = []

    return microfones

def abrir_camera(index, fallback=True):
    global cap

    if cv2 is None or CLOUD_MODE:
        return False

    with camera_lock:
        # Se a mesma câmera já está aberta e funcionando, não re-abrir
        if (index == config_dispositivos["camera_index"]
                and cap is not None and cap.isOpened()):
            return True

        camera_anterior = cap
        nova_cap = _tentar_abrir_camera_por_indice(index)
        indice_em_uso = index

        if nova_cap is None and fallback:
            for camera in listar_cameras():
                idx = camera["index"]
                nova_cap = _tentar_abrir_camera_por_indice(idx)
                if nova_cap is not None:
                    indice_em_uso = idx
                    break

        if nova_cap is None:
            return False

        cap = nova_cap
        config_dispositivos["camera_index"] = indice_em_uso

        if camera_anterior is not None and camera_anterior is not cap:
            camera_anterior.release()

        return True

def aplicar_microfone(index):
    microfones = listar_microfones()
    indices_validos = {item["index"] for item in microfones}

    if index is None:
        config_dispositivos["microfone_index"] = None
        return True

    if index in indices_validos:
        config_dispositivos["microfone_index"] = index
        return True

    return False

def contar_dedos(landmarks, lateralidade="Right", orientacao="Palma"):
    pontas_dedos = [8, 12, 16, 20]
    dedos_levantados = []

    # Polegar
    # A lógica do polegar inverte dependendo se é Palma ou Costas
    if lateralidade == "Right":
        if orientacao == "Palma":
            # Palma: Polegar à esquerda (x menor)
            if landmarks[4].x < landmarks[3].x: 
                dedos_levantados.append(1)
            else:
                dedos_levantados.append(0)
        else: # Costas
            # Costas: Polegar à direita (x maior)
            if landmarks[4].x > landmarks[3].x: 
                dedos_levantados.append(1)
            else:
                dedos_levantados.append(0)
    else: # Left
        if orientacao == "Palma":
            # Palma: Polegar à direita (x maior)
            if landmarks[4].x > landmarks[3].x:
                dedos_levantados.append(1)
            else:
                dedos_levantados.append(0)
        else: # Costas
            # Costas: Polegar à esquerda (x menor)
            if landmarks[4].x < landmarks[3].x:
                dedos_levantados.append(1)
            else:
                dedos_levantados.append(0)

    # Outros dedos
    for ponta in pontas_dedos:
        if landmarks[ponta].y < landmarks[ponta - 2].y:
            dedos_levantados.append(1)
        else:
            dedos_levantados.append(0)

    return sum(dedos_levantados), dedos_levantados

def _calcular_ear(p, pontos_olho):
    """Calcula Eye Aspect Ratio (EAR) para detectar olhos fechados.
    pontos_olho: lista de 6 índices [p1, p2, p3, p4, p5, p6]
    p1-p4 = cantos horizontais, p2-p6 e p3-p5 = pares verticais
    """
    # Distâncias verticais
    v1 = ((p[pontos_olho[1]].x - p[pontos_olho[5]].x)**2 +
          (p[pontos_olho[1]].y - p[pontos_olho[5]].y)**2)**0.5
    v2 = ((p[pontos_olho[2]].x - p[pontos_olho[4]].x)**2 +
          (p[pontos_olho[2]].y - p[pontos_olho[4]].y)**2)**0.5
    # Distância horizontal
    h = ((p[pontos_olho[0]].x - p[pontos_olho[3]].x)**2 +
         (p[pontos_olho[0]].y - p[pontos_olho[3]].y)**2)**0.5
    if h == 0:
        return 0.3  # valor neutro para evitar divisão por zero
    return (v1 + v2) / (2.0 * h)

# Landmarks do Face Mesh para os olhos (índices MediaPipe 468+)
# Olho direito: [33, 160, 158, 133, 153, 144]
# Olho esquerdo: [362, 385, 387, 263, 373, 380]
_OLHO_DIREITO = [33, 160, 158, 133, 153, 144]
_OLHO_ESQUERDO = [362, 385, 387, 263, 373, 380]
_EAR_LIMIAR = 0.18  # abaixo deste valor, olhos estão fechados

def detectar_expressao(face_landmarks):
    # Pontos chave do rosto (MediaPipe Face Mesh)
    # Lábio superior: 13, Lábio inferior: 14
    # Canto esquerdo boca: 61, Canto direito boca: 291
    # Topo rosto: 10, Queixo: 152 (para normalização vertical)
    # Maçã do rosto esq: 234, Maçã do rosto dir: 454 (para normalização horizontal)
    
    p = face_landmarks.landmark
    
    # Altura do rosto (Vertical)
    altura_rosto = p[152].y - p[10].y
    
    # Largura do rosto (Horizontal)
    largura_rosto = p[454].x - p[234].x
    
    # 1. Abertura da boca (Surpresa) - Normalizado pela altura
    abertura_boca = (p[14].y - p[13].y) / altura_rosto
    
    # 2. Largura da boca (Sorriso) - Normalizado pela largura do rosto
    largura_boca = (p[291].x - p[61].x) / largura_rosto
    
    # 3. Detecção de olhos fechados via EAR (Eye Aspect Ratio)
    ear_direito = _calcular_ear(p, _OLHO_DIREITO)
    ear_esquerdo = _calcular_ear(p, _OLHO_ESQUERDO)
    ear_medio = (ear_direito + ear_esquerdo) / 2.0
    
    if abertura_boca > 0.15: 
        return "Surpresa", mapeamento_gestos.get("Surpresa", "surpresa.jpg")
    elif ear_medio < _EAR_LIMIAR:
        return "Olhos Fechados", mapeamento_gestos.get("Olhos Fechados", "olhos_fechados.jpg")
    elif largura_boca > 0.40: # Ajustado: > 40% da largura do rosto
        return "Sorriso", mapeamento_gestos.get("Sorriso", "sorriso.jpg")
    
    return "Neutro", None

def gerar_frames():
    global cap, estado_atual
    
    ultimo_print = 0
    COOLDOWN_PRINT = 3.0 # 3 segundos de intervalo entre prints

    while True:
        # Verificar câmera sob lock
        with camera_lock:
            cam_ok = cap is not None and cap.isOpened()

        if not cam_ok:
            print("Tentando abrir a camera...")
            if not abrir_camera(config_dispositivos["camera_index"], fallback=True):
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(frame, "CAMERA NAO ENCONTRADA", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                with estado_lock:
                    estado_atual["gesto"] = "Erro na Camera"
                    estado_atual["imagem"] = "neutro.jpg"

                ret, buffer = cv2.imencode('.jpg', frame)
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

                time.sleep(1)
                continue

            time.sleep(0.5) # Esperar câmera inicializar
            continue

        # Ler frame sob lock
        with camera_lock:
            if cap is not None:
                sucesso, frame = cap.read()
            else:
                sucesso, frame = False, None

        if not sucesso:
            # Se falhar, envia um frame preto com aviso
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, "CAMERA NAO ENCONTRADA", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            cv2.putText(frame, "Verifique se outra app esta usando a camera", (35, 280), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            
            with estado_lock:
                estado_atual["gesto"] = "Erro na Camera"
                estado_atual["imagem"] = "neutro.jpg"

            with camera_lock:
                if cap is not None:
                    cap.release()
                    cap = None
            
            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            time.sleep(1)
            continue

        # Espelhar frame
        frame = cv2.flip(frame, 1)
        
        # Reduzir para processamento
        frame_small = cv2.resize(frame, (320, 240))
        frame_rgb = cv2.cvtColor(frame_small, cv2.COLOR_BGR2RGB)
        
        # Processar mãos e rosto
        resultados_maos = maos.process(frame_rgb)
        resultados_rosto = rosto.process(frame_rgb)
        
        gesto_detectado = "Nenhuma mao"
        expressao_detectada = "Neutro"
        imagem_nome = "neutro.jpg"
        
        gestos_lista = []
        maior_prioridade = -1
        gesto_principal = "Nenhuma mao"

        # --- Lógica de Mãos ---
        if resultados_maos.multi_hand_landmarks:
            for idx, hand_landmarks in enumerate(resultados_maos.multi_hand_landmarks):
                mp_desenho.draw_landmarks(frame, hand_landmarks, mp_maos.HAND_CONNECTIONS)
                
                # Obter lateralidade (Right/Left)
                lateralidade = "Right"
                if resultados_maos.multi_handedness:
                    # Proteção contra índice fora do alcance (embora raro)
                    if idx < len(resultados_maos.multi_handedness):
                        lateralidade = resultados_maos.multi_handedness[idx].classification[0].label

                # --- Detecção de Orientação (Palma vs Costas) ---
                # P0: Pulso, P5: Base Indicador, P17: Base Mindinho
                p0 = hand_landmarks.landmark[0]
                p5 = hand_landmarks.landmark[5]
                p17 = hand_landmarks.landmark[17]
                
                # Produto vetorial (Cross Product) 2D para determinar a direção
                # V1 = P5 - P0, V2 = P17 - P0
                val_cross = (p5.x - p0.x) * (p17.y - p0.y) - (p5.y - p0.y) * (p17.x - p0.x)
                
                orientacao = ""
                if lateralidade == "Right":
                    orientacao = "Palma" if val_cross > 0 else "Costas"
                else: # Left
                    orientacao = "Palma" if val_cross < 0 else "Costas"

                total_dedos, lista_dedos = contar_dedos(hand_landmarks.landmark, lateralidade, orientacao)

                # Distância OK (Normalizada pelo tamanho da mão aprox)
                escala_mao = ((hand_landmarks.landmark[0].y - hand_landmarks.landmark[9].y)**2 + (hand_landmarks.landmark[0].x - hand_landmarks.landmark[9].x)**2)**0.5
                
                x4, y4 = hand_landmarks.landmark[4].x, hand_landmarks.landmark[4].y
                x8, y8 = hand_landmarks.landmark[8].x, hand_landmarks.landmark[8].y
                distancia_ok = ((x4 - x8)**2 + (y4 - y8)**2)**0.5
                
                # Lógica Like melhorada
                # Polegar para cima: ponta (4) SIGNIFICATIVAMENTE acima da base (2)
                # Usar margem para evitar falsos positivos
                margem_polegar = 0.04  # margem vertical normalizada
                polegar_pra_cima = (hand_landmarks.landmark[4].y < hand_landmarks.landmark[3].y - margem_polegar
                                     and hand_landmarks.landmark[4].y < hand_landmarks.landmark[2].y - margem_polegar)
                
                indicador_fechado = hand_landmarks.landmark[8].y > hand_landmarks.landmark[6].y
                medio_fechado = hand_landmarks.landmark[12].y > hand_landmarks.landmark[10].y
                anelar_fechado = hand_landmarks.landmark[16].y > hand_landmarks.landmark[14].y
                minimo_fechado = hand_landmarks.landmark[20].y > hand_landmarks.landmark[18].y
                
                outros_dedos_fechados = indicador_fechado and medio_fechado and anelar_fechado and minimo_fechado
                
                # Detectar indicador levantado sozinho (Apontar)
                indicador_levantado = lista_dedos[1] == 1
                medio_levantado = lista_dedos[2] == 1
                anelar_levantado = lista_dedos[3] == 1 if len(lista_dedos) > 3 else False
                minimo_levantado = lista_dedos[4] == 1 if len(lista_dedos) > 4 else False

                gesto_temp = f"Dedos: {total_dedos}"
                img_temp = "neutro.jpg"
                prioridade = 0

                # --- Detecção de gestos (ordem de prioridade) ---

                if distancia_ok < (0.18 * escala_mao) and (lista_dedos[2] == 1 or lista_dedos[3] == 1):
                    # OK: polegar e indicador formam círculo
                    gesto_temp = "OK"
                    img_temp = mapeamento_gestos.get("OK", "ok.jpg")
                    prioridade = 6

                    # Funcionalidade: Print ao fazer OK com as Costas da Mão Direita
                    if lateralidade == "Right" and orientacao == "Costas":
                        agora = time.time()
                        if agora - ultimo_print > COOLDOWN_PRINT:
                            if not os.path.exists("screenshots"):
                                os.makedirs("screenshots")
                            
                            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                            filename = f"screenshots/print_{timestamp}.jpg"
                            cv2.imwrite(filename, frame)
                            print(f"\U0001f4f8 Screenshot salvo: {filename}")
                            ultimo_print = agora

                elif polegar_pra_cima and outros_dedos_fechados:
                    # LIKE: polegar para cima, outros fechados
                    gesto_temp = "LIKE"
                    img_temp = mapeamento_gestos.get("LIKE", "like.jpg")
                    prioridade = 5

                elif total_dedos == 2 and indicador_levantado and medio_levantado and not anelar_levantado and not minimo_levantado:
                    # Paz e Amor: indicador + médio levantados
                    gesto_temp = "Paz e Amor"
                    img_temp = mapeamento_gestos.get("Paz e Amor", "paz.jpg")
                    prioridade = 4

                elif indicador_levantado and minimo_levantado and not medio_levantado and not anelar_levantado:
                    # Rock: indicador + mindinho levantados
                    gesto_temp = "Rock"
                    img_temp = mapeamento_gestos.get("Rock", "like.jpg")
                    prioridade = 4

                elif total_dedos == 1 and indicador_levantado:
                    # Apontar: só indicador levantado
                    gesto_temp = "Apontando"
                    img_temp = mapeamento_gestos.get("Apontando", "neutro.jpg")
                    prioridade = 2

                elif total_dedos == 5:
                    # Mão Aberta: todos os dedos levantados
                    gesto_temp = "Mao Aberta"
                    img_temp = mapeamento_gestos.get("Mao Aberta", "sol.jpg")
                    prioridade = 3

                elif outros_dedos_fechados and not polegar_pra_cima:
                    # Punho Fechado: todos os dedos fechados (sem polegar pra cima)
                    gesto_temp = "Punho Fechado"
                    img_temp = mapeamento_gestos.get("Punho Fechado", "lua.jpg")
                    prioridade = 1
                
                gestos_lista.append(f"{lateralidade} ({orientacao}): {gesto_temp}")
                
                if prioridade > maior_prioridade:
                    maior_prioridade = prioridade
                    imagem_nome = img_temp
                    gesto_principal = gesto_temp

        if gestos_lista:
            gesto_detectado = " | ".join(gestos_lista)
        
        # --- Lógica de Rosto (Prioridade sobre Mãos se detectar expressão forte) ---
        if resultados_rosto.multi_face_landmarks:
            for face_landmarks in resultados_rosto.multi_face_landmarks:
                exp, img_exp = detectar_expressao(face_landmarks)
                expressao_detectada = exp

                # Prioriza expressão facial quando não há gesto de mão forte
                if img_exp and gesto_principal in ["Nenhuma mao", "Punho Fechado", "Mao Aberta"] and "Dedos" not in gesto_principal:
                    imagem_nome = img_exp

        # Atualizar estado global
        with estado_lock:
            estado_atual["gesto"] = gesto_detectado
            estado_atual["gesto_principal"] = gesto_principal
            estado_atual["expressao"] = expressao_detectada
            estado_atual["imagem"] = imagem_nome

        # Codificar frame para JPEG
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(0.033)  # ~30 FPS limiter

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    if CLOUD_MODE or not CV_AVAILABLE:
        return redirect(url_for('static', filename='images/neutro.jpg'))
    return Response(gerar_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# --- Lógica de Pintura Virtual ---
canvas_pintura = np.zeros((480, 640, 3), dtype=np.uint8) if np is not None else None
canvas_mascara = np.zeros((480, 640), dtype=np.uint8) if np is not None else None
cor_pincel = (255, 0, 0) # Azul BGR (OpenCV usa BGR)
ponto_anterior = (0, 0)

def gerar_frames_pintura():
    global cap, canvas_pintura, canvas_mascara, cor_pincel, ponto_anterior
    
    mp_instance = maos_pintura if maos_pintura is not None else maos
    
    # Cores disponíveis (BGR)
    cores = [
        ((255, 0, 0), "Azul"),    # Azul
        ((0, 255, 0), "Verde"),   # Verde
        ((0, 0, 255), "Vermelho"),# Vermelho
        ((0, 0, 0), "Borracha")   # Preto (Apagar)
    ]
    
    # Áreas dos botões de cor (x, y, w, h)
    botoes = []
    largura_botao = 100
    for i in range(len(cores)):
        botoes.append( (40 + i * 120, 20, largura_botao, 60) )

    while True:
        # Verificar câmera sob lock
        with camera_lock:
            cam_ok = cap is not None and cap.isOpened()

        if not cam_ok:
            if not abrir_camera(config_dispositivos["camera_index"], fallback=True):
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(frame, "ERRO NA CAMERA", (150, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                ret, buffer = cv2.imencode('.jpg', frame)
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                time.sleep(0.5)
                continue

            time.sleep(0.5)
            continue

        # Ler frame sob lock
        with camera_lock:
            if cap is not None:
                sucesso, frame = cap.read()
            else:
                sucesso, frame = False, None

        if not sucesso:
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, "ERRO NA CAMERA", (150, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

            with camera_lock:
                if cap is not None:
                    cap.release()
                    cap = None

            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            time.sleep(0.5)
            continue

        frame = cv2.flip(frame, 1)
        # Forçar tamanho 640x480 para bater com o canvas
        frame = cv2.resize(frame, (640, 480))
        
        # Downscale para MediaPipe (coordenadas normalizadas 0-1)
        frame_small = cv2.resize(frame, (320, 240))
        frame_rgb = cv2.cvtColor(frame_small, cv2.COLOR_BGR2RGB)
        resultados = mp_instance.process(frame_rgb)
        
        with pintura_lock:
            # Desenhar interface (botões)
            for i, (cor, nome) in enumerate(cores):
                x, y, w, h = botoes[i]
                cor_botao = cor if cor != (0, 0, 0) else (80, 80, 80)
                cv2.rectangle(frame, (x, y), (x+w, y+h), cor_botao, -1)
                cv2.putText(frame, nome, (x+10, y+40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                # Borda branca no botão selecionado
                if cor == cor_pincel:
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 255, 255), 3)

            if resultados.multi_hand_landmarks:
                for hand_landmarks in resultados.multi_hand_landmarks:
                    x8 = int(hand_landmarks.landmark[8].x * 640)
                    y8 = int(hand_landmarks.landmark[8].y * 480)
                    
                    indicador_levantado = hand_landmarks.landmark[8].y < hand_landmarks.landmark[6].y
                    
                    dedos_up = 0
                    if hand_landmarks.landmark[8].y < hand_landmarks.landmark[6].y: dedos_up += 1
                    if hand_landmarks.landmark[12].y < hand_landmarks.landmark[10].y: dedos_up += 1
                    if hand_landmarks.landmark[16].y < hand_landmarks.landmark[14].y: dedos_up += 1
                    if hand_landmarks.landmark[20].y < hand_landmarks.landmark[18].y: dedos_up += 1
                    
                    if dedos_up >= 4: # Mão aberta -> Limpar
                        canvas_pintura = np.zeros((480, 640, 3), dtype=np.uint8)
                        canvas_mascara = np.zeros((480, 640), dtype=np.uint8)
                        cv2.putText(frame, "TELA LIMPA", (250, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                        ponto_anterior = (0, 0)
                    
                    elif indicador_levantado:
                        cor_cursor = cor_pincel if cor_pincel != (0, 0, 0) else (80, 80, 80)
                        cv2.circle(frame, (x8, y8), 10, cor_cursor, -1)
                        
                        if y8 < 100:
                            for i, (bx, by, bw, bh) in enumerate(botoes):
                                if bx < x8 < bx+bw and by < y8 < by+bh:
                                    cor_pincel = cores[i][0]
                                    ponto_anterior = (0, 0)
                        else:
                            if ponto_anterior == (0, 0):
                                ponto_anterior = (x8, y8)
                            
                            if cor_pincel == (0, 0, 0):
                                # Borracha: limpar canvas e máscara com traço mais grosso
                                cv2.line(canvas_pintura, ponto_anterior, (x8, y8), (0, 0, 0), 12)
                                cv2.line(canvas_mascara, ponto_anterior, (x8, y8), 0, 12)
                            else:
                                cv2.line(canvas_pintura, ponto_anterior, (x8, y8), cor_pincel, 5)
                                cv2.line(canvas_mascara, ponto_anterior, (x8, y8), 255, 5)
                            ponto_anterior = (x8, y8)
                    else:
                        ponto_anterior = (0, 0)

            # Mesclar canvas com frame usando máscara explícita
            mascara_3c = cv2.cvtColor(canvas_mascara, cv2.COLOR_GRAY2BGR)
            mascara_inv = cv2.bitwise_not(mascara_3c)
            frame = cv2.bitwise_and(frame, mascara_inv)
            frame = cv2.bitwise_or(frame, cv2.bitwise_and(canvas_pintura, mascara_3c))

        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(0.033)  # ~30 FPS limiter

@app.route('/pintura')
def pintura():
    return render_template('pintura.html')

# --- Lógica de Música Virtual ---

def _classificar_gesto_musica(hand_landmarks, lateralidade):
    """Classifica gesto para a página de música. Retorna (gesto, prioridade, dados_extra)."""
    # Orientação
    p0 = hand_landmarks.landmark[0]
    p5 = hand_landmarks.landmark[5]
    p17 = hand_landmarks.landmark[17]
    val_cross = (p5.x - p0.x) * (p17.y - p0.y) - (p5.y - p0.y) * (p17.x - p0.x)
    if lateralidade == "Right":
        orientacao = "Palma" if val_cross > 0 else "Costas"
    else:
        orientacao = "Palma" if val_cross < 0 else "Costas"

    total_dedos, lista_dedos = contar_dedos(hand_landmarks.landmark, lateralidade, orientacao)

    escala_mao = ((hand_landmarks.landmark[0].y - hand_landmarks.landmark[9].y)**2 +
                  (hand_landmarks.landmark[0].x - hand_landmarks.landmark[9].x)**2)**0.5
    x4, y4 = hand_landmarks.landmark[4].x, hand_landmarks.landmark[4].y
    x8, y8 = hand_landmarks.landmark[8].x, hand_landmarks.landmark[8].y
    distancia_ok = ((x4 - x8)**2 + (y4 - y8)**2)**0.5

    margem_polegar = 0.04
    polegar_pra_cima = (hand_landmarks.landmark[4].y < hand_landmarks.landmark[3].y - margem_polegar
                        and hand_landmarks.landmark[4].y < hand_landmarks.landmark[2].y - margem_polegar)

    indicador_fechado = hand_landmarks.landmark[8].y > hand_landmarks.landmark[6].y
    medio_fechado = hand_landmarks.landmark[12].y > hand_landmarks.landmark[10].y
    anelar_fechado = hand_landmarks.landmark[16].y > hand_landmarks.landmark[14].y
    minimo_fechado = hand_landmarks.landmark[20].y > hand_landmarks.landmark[18].y
    outros_dedos_fechados = indicador_fechado and medio_fechado and anelar_fechado and minimo_fechado

    indicador_levantado = lista_dedos[1] == 1
    medio_levantado = lista_dedos[2] == 1
    anelar_levantado = lista_dedos[3] == 1 if len(lista_dedos) > 3 else False
    minimo_levantado = lista_dedos[4] == 1 if len(lista_dedos) > 4 else False
    polegar_levantado = lista_dedos[0] == 1

    # Dados extras (orientação, ângulo do pulso etc.)
    dados = {"orientacao": orientacao, "dedos": total_dedos, "lista_dedos": lista_dedos}

    # --- Gestos de alta prioridade (comandos) ---
    if distancia_ok < (0.18 * escala_mao) and (lista_dedos[2] == 1 or lista_dedos[3] == 1):
        return "OK", 7, dados

    if polegar_pra_cima and outros_dedos_fechados:
        return "LIKE", 6, dados

    # --- Gesto "Hang Loose" / "Telefone" (polegar + mindinho, outros fechados) ---
    if polegar_levantado and minimo_levantado and indicador_fechado and medio_fechado and anelar_fechado:
        return "Hang Loose", 5, dados

    # --- Rock: indicador + mindinho ---
    if indicador_levantado and minimo_levantado and not medio_levantado and not anelar_levantado:
        return "Rock", 5, dados

    # --- Paz e Amor: indicador + médio ---
    if total_dedos == 2 and indicador_levantado and medio_levantado and not anelar_levantado and not minimo_levantado:
        return "Paz e Amor", 4, dados

    # --- Três dedos: indicador + médio + anelar ---
    if indicador_levantado and medio_levantado and anelar_levantado and not minimo_levantado and not polegar_levantado:
        return "Tres Dedos", 4, dados

    # --- Quatro dedos: indicador + médio + anelar + mindinho (sem polegar) ---
    if indicador_levantado and medio_levantado and anelar_levantado and minimo_levantado and not polegar_levantado:
        return "Quatro Dedos", 3, dados

    # --- Números explícitos (1-5) baseados em contagem de dedos ---
    if total_dedos == 1 and indicador_levantado:
        return "Num1", 3, dados

    if total_dedos == 2 and indicador_levantado and medio_levantado:
        return "Paz e Amor", 4, dados  # já coberto acima

    if total_dedos == 3:
        return "Num3", 3, dados

    if total_dedos == 4:
        return "Num4", 3, dados

    if total_dedos == 5:
        return "Num5", 3, dados

    # --- Mão aberta = 5 (coberto por Num5) ---

    # --- Punho Fechado ---
    if outros_dedos_fechados and not polegar_pra_cima:
        return "Punho Fechado", 1, dados

    return "Nenhum", 0, dados


def _detectar_movimento(lateralidade, x, y):
    """Detecta direção e velocidade do movimento baseado no histórico de posições."""
    global _historico_pos
    agora = time.time()
    hist = _historico_pos.get(lateralidade, [])
    hist.append((x, y, agora))

    # Manter apenas os últimos N pontos
    if len(hist) > _HIST_MAX:
        hist = hist[-_HIST_MAX:]
    _historico_pos[lateralidade] = hist

    if len(hist) < 3:
        return "Parado", 0.0

    # Calcular deslocamento e velocidade entre o ponto mais antigo e o mais recente
    x0, y0, t0 = hist[0]
    x1, y1, t1 = hist[-1]
    dt = t1 - t0
    if dt < 0.05:
        return "Parado", 0.0

    dx = x1 - x0
    dy = y1 - y0
    dist = (dx**2 + dy**2)**0.5
    velocidade = dist / dt

    # Limiar mínimo de movimento (normalizado 0-1)
    if dist < 0.06:
        return "Parado", round(velocidade, 3)

    # Determinar direção dominante
    if abs(dx) > abs(dy):
        direcao = "Direita" if dx > 0 else "Esquerda"
    else:
        direcao = "Baixo" if dy > 0 else "Cima"

    # Movimento circular (variância alta em ambos eixos)
    if dist > 0.1 and abs(dx) > 0.04 and abs(dy) > 0.04:
        # Verificar se é circular: pontos intermediários devem variar em ambos eixos
        xs = [p[0] for p in hist]
        ys = [p[1] for p in hist]
        var_x = max(xs) - min(xs)
        var_y = max(ys) - min(ys)
        if var_x > 0.08 and var_y > 0.08 and abs(var_x - var_y) < 0.15:
            direcao = "Circular"

    # Movimento rápido (swing/shake)
    if velocidade > 1.5:
        direcao = "Rapido " + direcao

    return direcao, round(velocidade, 3)


def _classificar_gesto_combinado(gesto_dir, gesto_esq, mov_dir, mov_esq, vel_dir, vel_esq, dedos_dir, dedos_esq):
    """Detecta gestos combinados de duas mãos."""
    # Ambas mãos com Punho Fechado = "Double Kick"
    if gesto_dir == "Punho Fechado" and gesto_esq == "Punho Fechado":
        return "Double Kick"

    # Ambas mãos abertas (5+5) = "Palmas" (clap)
    if gesto_dir == "Num5" and gesto_esq == "Num5":
        return "Palmas"

    # Rock em ambas = "Double Rock"
    if gesto_dir == "Rock" and gesto_esq == "Rock":
        return "Double Rock"

    # Ambas mãos com Paz e Amor = "Double Peace"
    if gesto_dir == "Paz e Amor" and gesto_esq == "Paz e Amor":
        return "Double Peace"

    # Uma mão Punho + outra Mão Aberta = "Punch Clap"
    if (gesto_dir == "Punho Fechado" and gesto_esq == "Num5") or \
       (gesto_dir == "Num5" and gesto_esq == "Punho Fechado"):
        return "Punch Clap"

    # Ambos apontando = "DJ Mode"
    if gesto_dir == "Num1" and gesto_esq == "Num1":
        return "DJ Mode"

    # Ambas mãos se movendo rápido = "Shake"
    if vel_dir > 1.2 and vel_esq > 1.2:
        return "Shake"

    # Mãos se movendo em direções opostas horizontalmente = "Scratch"
    if ("Esquerda" in mov_dir and "Direita" in mov_esq) or \
       ("Direita" in mov_dir and "Esquerda" in mov_esq):
        if vel_dir > 0.5 and vel_esq > 0.5:
            return "Scratch"

    # Ambas para cima = "Rise"
    if "Cima" in mov_dir and "Cima" in mov_esq and vel_dir > 0.4 and vel_esq > 0.4:
        return "Rise"

    # Ambas para baixo = "Drop"
    if "Baixo" in mov_dir and "Baixo" in mov_esq and vel_dir > 0.4 and vel_esq > 0.4:
        return "Drop"

    # Circular em qualquer mão = "Spin"
    if "Circular" in mov_dir or "Circular" in mov_esq:
        return "Spin"

    # Hang Loose em ambas = "Aloha"
    if gesto_dir == "Hang Loose" and gesto_esq == "Hang Loose":
        return "Aloha"

    # Soma de dedos como controle
    total = dedos_dir + dedos_esq
    if total >= 8 and gesto_dir not in ("OK", "LIKE", "Rock", "Hang Loose") and \
       gesto_esq not in ("OK", "LIKE", "Rock", "Hang Loose"):
        return f"Total {total}"

    return "Nenhum"

def gerar_frames_musica():
    """Gera frames MJPEG para a página de música com detecção de gestos e posição."""
    global cap, estado_musica

    mp_m = maos_musica if maos_musica is not None else maos
    mp_r = rosto_musica if rosto_musica is not None else rosto

    while True:
        with camera_lock:
            cam_ok = cap is not None and cap.isOpened()

        if not cam_ok:
            if not abrir_camera(config_dispositivos["camera_index"], fallback=True):
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(frame, "CAMERA NAO ENCONTRADA", (50, 240),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                ret, buffer = cv2.imencode('.jpg', frame)
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
                time.sleep(1)
                continue
            time.sleep(0.5)
            continue

        with camera_lock:
            if cap is not None:
                sucesso, frame = cap.read()
            else:
                sucesso, frame = False, None

        if not sucesso:
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, "ERRO NA CAMERA", (150, 240),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            with camera_lock:
                if cap is not None:
                    cap.release()
                    cap = None
            ret, buffer = cv2.imencode('.jpg', frame)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            time.sleep(1)
            continue

        frame = cv2.flip(frame, 1)
        frame_small = cv2.resize(frame, (320, 240))
        frame_rgb = cv2.cvtColor(frame_small, cv2.COLOR_BGR2RGB)

        resultados_maos = mp_m.process(frame_rgb)
        resultados_rosto = mp_r.process(frame_rgb) if mp_r is not None else None

        gesto_dir = "Nenhum"
        gesto_esq = "Nenhum"
        pos_dir = {"x": 0.5, "y": 0.5}
        pos_esq = {"x": 0.5, "y": 0.5}
        dedos_dir = 0
        dedos_esq = 0
        expressao = "Neutro"
        mov_dir = "Parado"
        mov_esq = "Parado"
        vel_dir = 0.0
        vel_esq = 0.0

        if resultados_maos.multi_hand_landmarks:
            for idx, hand_landmarks in enumerate(resultados_maos.multi_hand_landmarks):
                # Desenhar landmarks
                mp_desenho.draw_landmarks(frame, hand_landmarks, mp_maos.HAND_CONNECTIONS)

                lateralidade = "Right"
                if resultados_maos.multi_handedness and idx < len(resultados_maos.multi_handedness):
                    lateralidade = resultados_maos.multi_handedness[idx].classification[0].label

                gesto, _, dados = _classificar_gesto_musica(hand_landmarks, lateralidade)
                total = dados.get("dedos", 0)

                wrist = hand_landmarks.landmark[0]
                pos = {"x": round(wrist.x, 3), "y": round(wrist.y, 3)}

                # Detectar movimento
                mov, vel = _detectar_movimento(lateralidade, wrist.x, wrist.y)

                if lateralidade == "Right":
                    gesto_dir = gesto
                    pos_dir = pos
                    dedos_dir = total
                    mov_dir = mov
                    vel_dir = vel
                else:
                    gesto_esq = gesto
                    pos_esq = pos
                    dedos_esq = total
                    mov_esq = mov
                    vel_esq = vel

        # Classificar gesto combinado de duas mãos
        gesto_combinado = _classificar_gesto_combinado(
            gesto_dir, gesto_esq, mov_dir, mov_esq, vel_dir, vel_esq, dedos_dir, dedos_esq
        )

        if resultados_rosto and resultados_rosto.multi_face_landmarks:
            for face_landmarks in resultados_rosto.multi_face_landmarks:
                exp, _ = detectar_expressao(face_landmarks)
                expressao = exp

        # Overlay de info no frame
        h, w = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 52), (0, 0, 0), -1)
        frame = cv2.addWeighted(overlay, 0.6, frame, 0.4, 0)
        info1 = f"D: {gesto_dir} | E: {gesto_esq} | {expressao}"
        info2 = f"Mov D: {mov_dir} | Mov E: {mov_esq}"
        if gesto_combinado != "Nenhum":
            info2 += f" | Combo: {gesto_combinado}"
        cv2.putText(frame, info1, (10, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 255, 200), 1)
        cv2.putText(frame, info2, (10, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 200, 0), 1)

        with musica_lock:
            estado_musica["gesto_direita"] = gesto_dir
            estado_musica["gesto_esquerda"] = gesto_esq
            estado_musica["pos_direita"] = pos_dir
            estado_musica["pos_esquerda"] = pos_esq
            estado_musica["expressao"] = expressao
            estado_musica["dedos_direita"] = dedos_dir
            estado_musica["dedos_esquerda"] = dedos_esq
            estado_musica["gesto_combinado"] = gesto_combinado
            estado_musica["movimento_direita"] = mov_dir
            estado_musica["movimento_esquerda"] = mov_esq
            estado_musica["velocidade_direita"] = vel_dir
            estado_musica["velocidade_esquerda"] = vel_esq

        ret, buffer = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        time.sleep(0.033)

@app.route('/musica')
def musica():
    return render_template('musica.html')

@app.route('/video_feed_musica')
def video_feed_musica():
    if CLOUD_MODE or not CV_AVAILABLE:
        return redirect(url_for('static', filename='images/neutro.jpg'))
    return Response(gerar_frames_musica(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/musica_status')
def musica_status():
    with musica_lock:
        data = dict(estado_musica)
    return jsonify(data)

@app.route('/video_feed_pintura')
def video_feed_pintura():
    if CLOUD_MODE or not CV_AVAILABLE:
        return redirect(url_for('static', filename='images/neutro.jpg'))
    return Response(gerar_frames_pintura(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/current_status')
def current_status():
    with estado_lock:
        data = dict(estado_atual)
    return jsonify(data)

@app.route('/devices')
def devices():
    return jsonify({
        "cameras": listar_cameras(),
        "microfones": listar_microfones(),
        "cloud_mode": CLOUD_MODE,
        "selecionado": {
            "camera_index": config_dispositivos["camera_index"],
            "microfone_index": config_dispositivos["microfone_index"]
        }
    })

@app.route('/rescan_cameras', methods=['POST'])
def rescan_cameras():
    """Dispara re-scan de câmeras em background e retorna status."""
    if CLOUD_MODE:
        return jsonify({"ok": False, "mensagem": "Não disponível no cloud."}), 400
    if _scan_em_andamento:
        return jsonify({"ok": True, "mensagem": "Scan já em andamento, aguarde..."})
    threading.Thread(target=_scan_cameras_background, daemon=True).start()
    return jsonify({"ok": True, "mensagem": "Re-scan iniciado. Recarregue em alguns segundos."})

@app.route('/set_devices', methods=['POST'])
def set_devices():
    if CLOUD_MODE:
        return jsonify({"ok": False, "mensagem": "Seleção de dispositivos não disponível no deploy cloud."}), 400

    dados = request.get_json(silent=True) or {}
    camera_index = dados.get("camera_index", config_dispositivos["camera_index"])
    microfone_index = dados.get("microfone_index", config_dispositivos["microfone_index"])

    try:
        if camera_index is not None:
            camera_index = int(camera_index)
        if microfone_index is not None:
            microfone_index = int(microfone_index)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "mensagem": "Índices inválidos."}), 400

    if camera_index is None:
        camera_index = config_dispositivos["camera_index"]

    if not abrir_camera(camera_index, fallback=False):
        return jsonify({"ok": False, "mensagem": f"Não foi possível abrir a câmera {camera_index}."}), 400

    if not aplicar_microfone(microfone_index):
        return jsonify({"ok": False, "mensagem": "Microfone selecionado é inválido."}), 400

    return jsonify({
        "ok": True,
        "mensagem": "Dispositivos atualizados com sucesso.",
        "selecionado": {
            "camera_index": config_dispositivos["camera_index"],
            "microfone_index": config_dispositivos["microfone_index"]
        }
    })

# --- API de Mapeamento Gesto → Imagem ---

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'}
IMAGES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "images")

def _extensao_permitida(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/list_images')
def list_images():
    """Retorna lista de todas as imagens disponíveis em static/images/."""
    imagens = []
    if os.path.isdir(IMAGES_DIR):
        for f in sorted(os.listdir(IMAGES_DIR)):
            if _extensao_permitida(f):
                imagens.append(f)
    return jsonify({"imagens": imagens})

@app.route('/gesture_images')
def get_gesture_images():
    """Retorna mapeamento atual gesto→imagem + lista de imagens disponíveis."""
    imagens = []
    if os.path.isdir(IMAGES_DIR):
        for f in sorted(os.listdir(IMAGES_DIR)):
            if _extensao_permitida(f):
                imagens.append(f)
    return jsonify({
        "mapeamento": dict(mapeamento_gestos),
        "imagens_disponiveis": imagens,
        "gestos": list(MAPEAMENTO_PADRAO.keys())
    })

@app.route('/gesture_images', methods=['POST'])
def set_gesture_images():
    """Atualiza mapeamento gesto→imagem."""
    global mapeamento_gestos
    dados = request.get_json(silent=True) or {}
    novo_mapeamento = dados.get("mapeamento")
    if not novo_mapeamento or not isinstance(novo_mapeamento, dict):
        return jsonify({"ok": False, "mensagem": "Dados inválidos."}), 400

    # Validar que todas as imagens existem
    for gesto, imagem in novo_mapeamento.items():
        if gesto not in MAPEAMENTO_PADRAO:
            continue  # Ignorar gestos desconhecidos
        caminho = os.path.join(IMAGES_DIR, imagem)
        if not os.path.isfile(caminho):
            return jsonify({"ok": False, "mensagem": f"Imagem '{imagem}' não encontrada."}), 400

    # Atualizar apenas gestos válidos
    for gesto in MAPEAMENTO_PADRAO:
        if gesto in novo_mapeamento:
            mapeamento_gestos[gesto] = novo_mapeamento[gesto]

    _salvar_mapeamento(mapeamento_gestos)
    return jsonify({"ok": True, "mensagem": "Mapeamento salvo com sucesso.", "mapeamento": dict(mapeamento_gestos)})

@app.route('/upload_image', methods=['POST'])
def upload_image():
    """Upload de nova imagem para static/images/."""
    if 'imagem' not in request.files:
        return jsonify({"ok": False, "mensagem": "Nenhum arquivo enviado."}), 400

    arquivo = request.files['imagem']
    if arquivo.filename == '':
        return jsonify({"ok": False, "mensagem": "Nome de arquivo vazio."}), 400

    if not _extensao_permitida(arquivo.filename):
        return jsonify({"ok": False, "mensagem": f"Extensão não permitida. Use: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

    nome_seguro = secure_filename(arquivo.filename)
    if not nome_seguro:
        return jsonify({"ok": False, "mensagem": "Nome de arquivo inválido."}), 400

    # Garantir que o diretório existe
    os.makedirs(IMAGES_DIR, exist_ok=True)

    caminho_destino = os.path.join(IMAGES_DIR, nome_seguro)
    arquivo.save(caminho_destino)
    return jsonify({"ok": True, "mensagem": f"Imagem '{nome_seguro}' enviada com sucesso.", "filename": nome_seguro})

if __name__ == "__main__":
    # Host 0.0.0.0 permite acesso de outros dispositivos na rede
    # debug=False é IMPORTANTE no Windows para não abrir a câmera 2 vezes
    # threaded=True permite servir /devices enquanto /video_feed faz streaming
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)
