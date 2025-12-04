import cv2
import numpy as np
import os

# Diretório de saída
output_dir = 'static/images'
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

def criar_imagem(nome_arquivo, cor_fundo, texto, cor_texto=(0,0,0), desenhar_sol=False, desenhar_lua=False):
    # Criar imagem vazia (altura, largura, canais de cor)
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    img[:] = cor_fundo # Preencher com a cor de fundo
    
    # Desenhos simples
    if desenhar_sol:
        cv2.circle(img, (320, 240), 100, (0, 255, 255), -1) # Círculo amarelo
    
    if desenhar_lua:
        cv2.circle(img, (320, 240), 80, (200, 200, 200), -1) # Círculo cinza

    # Configuração do texto
    font = cv2.FONT_HERSHEY_SIMPLEX
    escala_fonte = 1.5
    espessura = 3
    
    # Calcular tamanho do texto para centralizar
    tamanho_texto = cv2.getTextSize(texto, font, escala_fonte, espessura)[0]
    texto_x = (640 - tamanho_texto[0]) // 2
    texto_y = 400 # Posição Y fixa na parte inferior
    
    # Escrever texto na imagem
    cv2.putText(img, texto, (texto_x, texto_y), font, escala_fonte, cor_texto, espessura)
    
    # Salvar arquivo
    caminho_completo = os.path.join(output_dir, nome_arquivo)
    cv2.imwrite(caminho_completo, img)
    print(f"Gerado: {caminho_completo}")

print("Iniciando geração de imagens...")

# 1. Sol (Mão Aberta)
criar_imagem('sol.jpg', (255, 255, 200), "MAO ABERTA: SOL", desenhar_sol=True)

# 2. Lua (Punho Fechado)
criar_imagem('lua.jpg', (50, 20, 20), "PUNHO FECHADO: LUA", cor_texto=(255,255,255), desenhar_lua=True)

# 3. Neutro (Aguardando)
criar_imagem('neutro.jpg', (240, 240, 240), "AGUARDANDO...", cor_texto=(50, 50, 50))

# 4. OK
criar_imagem('ok.jpg', (200, 255, 200), "GESTO: OK!", cor_texto=(0, 100, 0))

# 5. Like (Joinha)
criar_imagem('like.jpg', (200, 200, 255), "GESTO: LIKE", cor_texto=(0, 0, 255))

# 6. Paz e Amor
criar_imagem('paz.jpg', (255, 200, 255), "PAZ E AMOR", cor_texto=(128, 0, 128))

# 7. Sorriso (Expressão)
criar_imagem('sorriso.jpg', (255, 255, 0), "VOCE ESTA SORRINDO!", cor_texto=(0, 0, 0))

# 8. Surpresa (Expressão)
criar_imagem('surpresa.jpg', (0, 0, 255), "UAU! SURPRESA!", cor_texto=(255, 255, 255))

print("Todas as imagens foram geradas com sucesso!")