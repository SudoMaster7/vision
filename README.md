# 🖐️ Sistema de Reconhecimento de Gestos e Expressões Faciais (MVP)

Este projeto é um MVP (Minimum Viable Product) de uma aplicação web que utiliza Visão Computacional para detectar gestos das mãos e expressões faciais em tempo real através da webcam. O sistema interpreta os movimentos e exibe feedbacks visuais correspondentes na interface.

## 🚀 Funcionalidades

### 👐 Detecção de Mãos
O sistema é capaz de rastrear até **duas mãos** simultaneamente e identificar:
*   **Gestos:**
    *   ☀️ **Mão Aberta:** Exibe imagem de Sol.
    *   🌑 **Punho Fechado:** Exibe imagem de Lua.
    *   👌 **OK:** Gesto de OK.
    *   👍 **Like (Joinha):** Gesto de aprovação.
    *   ✌️ **Paz e Amor:** Gesto de V.
*   **Orientação:** Identifica se a mão está mostrando a **Palma** ou as **Costas**.
*   **Contagem de Dedos:** Contagem precisa independente da orientação da mão.

### 😀 Detecção de Expressões Faciais
Utilizando a malha facial (Face Mesh), o sistema detecta:
*   😄 **Sorriso:** Baseado na largura da boca.
*   😮 **Surpresa:** Baseado na abertura vertical da boca.

### 💻 Interface Web
*   Desenvolvida com **Flask** (Backend) e **Bootstrap 5** (Frontend).
*   Feed de vídeo em tempo real.
*   Painel de status dinâmico que mostra os gestos detectados por cada mão (Esquerda/Direita).
*   Atualização automática da imagem de resposta sem recarregar a página.

## 🛠️ Tecnologias Utilizadas

*   **Python 3.11**
*   **OpenCV:** Captura e processamento de imagem.
*   **MediaPipe:** Modelos de IA para detecção de mãos e face mesh.
*   **Flask:** Servidor web.
*   **NumPy:** Operações matemáticas.

## 📦 Instalação e Execução

1.  **Pré-requisitos:**
    *   Python 3.11 instalado (Recomendado devido a compatibilidade do MediaPipe).
    *   Webcam conectada.

    > Em máquinas Windows com pasta do projeto em caminho com acentos (ex.: `Área de Trabalho`), o MediaPipe pode falhar ao carregar arquivos internos. Nesse caso, crie o ambiente virtual em um caminho sem acentos (ex.: `C:/venvs/visionsudo311`).

2.  **Crie e ative um ambiente virtual (recomendado):**
    ```bash
    # Windows (PowerShell)
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    ```

    > Se seu projeto estiver em caminho com acento e o MediaPipe falhar, crie o venv fora dessa pasta (ex.: `C:/venvs/visionsudo311`) e use esse Python para executar.

3.  **Instale as dependências:**
    ```bash
    pip install "mediapipe==0.10.21" flask pillow
    ```

4.  **Gere as imagens de feedback (Opcional):**
    Caso as imagens não existam na pasta `static/images`, execute:
    ```bash
    python gerar_novas_imagens.py
    ```

5.  **Execute a aplicação web:**
    ```bash
    # Recomendado (Windows com caminho sem acento)
    C:/venvs/visionsudo311/Scripts/python.exe app_web.py
    ```

    Alternativa (se seu `.venv` local não apresentar erro de MediaPipe):
    ```bash
    python app_web.py
    ```

6.  **Acesse no navegador:**
    Abra `http://127.0.0.1:5000` no seu navegador web.

7.  **Escolha câmera e microfone na interface:**
    * No painel principal, use a seção **Configuração de Dispositivos**.
    * Selecione a câmera e o microfone desejados.
    * Clique em **Salvar dispositivos** para aplicar.
    * A seleção fica salva no navegador e é reaplicada automaticamente ao abrir novamente a página.

8.  **Ative legenda de voz (pt-BR):**
    * Abaixo do vídeo da câmera, clique em **Iniciar legenda**.
    * Permita o uso do microfone no navegador.
    * A transcrição em português (Brasil) aparecerá em tempo real no campo de legenda.
    * O painel mantém um histórico curto das últimas frases com horário.

## ⚠️ Solução rápida para câmera com erro

Se aparecer **Erro na Câmera**:
* Feche outros apps que podem estar usando a webcam (ex.: `app_gui.py`, Zoom, Meet, Teams, OBS).
* Na interface web, troque para outro índice de câmera e clique em **Salvar dispositivos**.
* Recarregue a página após liberar a câmera.

## 🖥️ Execução da versão GUI (Tkinter)

Se quiser usar a interface desktop:

```bash
python app_gui.py
```

Na GUI, você também pode trocar a fonte de vídeo pelos botões de câmera.

## ☁️ Deploy na Vercel (hoje)

Arquivos de deploy já incluídos:
* `requirements.txt`
* `vercel.json`

Passos:
1. Faça push do projeto para o GitHub.
2. Na Vercel, importe o repositório.
3. Root Directory: `vision`.
4. Deploy.

### Observação importante sobre câmera/microfone
Em deploy cloud (Vercel), o servidor **não tem acesso à sua câmera física local**.
Por isso:
* a interface web sobe normalmente;
* o feed usa fallback de imagem;
* seleção de câmera/microfone fica desabilitada no modo cloud.

Para usar câmera real, continue rodando localmente com:

```bash
C:/venvs/visionsudo311/Scripts/python.exe app_web.py
```

## 📂 Estrutura do Projeto

*   `app_web.py`: Código principal da aplicação Flask e lógica de visão computacional.
*   `templates/index.html`: Interface do usuário (HTML/JS).
*   `static/images/`: Imagens geradas para feedback visual.
*   `gerar_novas_imagens.py`: Script utilitário para criar as imagens de resposta.

## 📝 Notas de Desenvolvimento

*   O sistema prioriza gestos de comando (OK, Like) sobre gestos neutros.
*   Expressões faciais fortes (Sorriso/Surpresa) têm prioridade de exibição se as mãos estiverem em posição neutra.
*   Foi implementada uma lógica de correção para contagem de dedos quando a mão está de costas para a câmera.
