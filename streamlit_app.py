import streamlit as st
import requests
from bs4 import BeautifulSoup
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from PIL import Image as PilImage
import tempfile
import os

# Função que extrai dados do anúncio Mercado Livre
def extrair_dados_anuncio(url, aliquota=0, comissao_webvend=0):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
    except Exception as e:
        return None, f"Erro ao acessar o link: {e}"

    if response.status_code != 200:
        return None, "Erro ao acessar o link."

    soup = BeautifulSoup(response.text, 'html.parser')

    # Título do produto
    titulo_tag = soup.find('h1', class_='ui-pdp-title')
    titulo = titulo_tag.get_text(strip=True) if titulo_tag else "Título não encontrado"

    # Foto principal (URL)
    foto_tag = soup.select_one('figure.ui-pdp-gallery__figure img')
    url_foto = foto_tag['src'] if foto_tag and foto_tag.has_attr('src') else None

    # Preço
    preco_inteiro_tag = soup.find('span', class_='andes-money-amount__fraction')
    preco_centavos_tag = soup.find('span', class_='andes-money-amount__cents')

    if preco_inteiro_tag:
        inteiro = preco_inteiro_tag.text.strip().replace('.', '')
        centavos = preco_centavos_tag.text.strip() if preco_centavos_tag else '00'
        preco_str = f"{inteiro}.{centavos}"
        try:
            preco = float(preco_str)
        except:
            preco = None
    else:
        preco = None

    # Tipo de anúncio
    texto_pagina = soup.get_text().lower()
    if "sem juros" in texto_pagina:
        tipo_anuncio = "Premium"
        comissao_min = 16.5
        comissao_max = 19.0
    else:
        tipo_anuncio = "Clássico"
        comissao_min = 11.5
        comissao_max = 14.0

    # Tarifa fixa
    if preco is not None:
        if preco < 30:
            tarifa_fixa = 6.25
        elif preco < 50:
            tarifa_fixa = 6.50
        elif preco < 79:
            tarifa_fixa = 6.75
        else:
            tarifa_fixa = 20
    else:
        tarifa_fixa = 0

    imposto = preco * (aliquota / 100) if preco else 0
    comissao_webvend_valor = preco * (comissao_webvend / 100) if preco else 0

    if preco is not None:
        liquido_min = preco * (1 - comissao_max / 100) - tarifa_fixa - imposto - comissao_webvend_valor
        liquido_max = preco * (1 - comissao_min / 100) - tarifa_fixa - imposto - comissao_webvend_valor
    else:
        liquido_min = liquido_max = None

    resultado = f"""Título: {titulo}
Preço: R$ {preco:.2f}""" if preco else "Preço não encontrado"

    resultado += f"""
Alíquota imposto: {aliquota:.2f}% (R$ {imposto:.2f})
Comissão Webvend: {comissao_webvend:.2f}% (R$ {comissao_webvend_valor:.2f})"""

    if liquido_min is not None:
        resultado += f"""
Valor líquido estimado: de R$ {liquido_min:.2f} a R$ {liquido_max:.2f}"""
    else:
        resultado += "\nNão foi possível calcular o valor líquido."

    return {
        "titulo": titulo,
        "preco": preco,
        "tipo_anuncio": tipo_anuncio,
        "comissao_min": comissao_min,
        "comissao_max": comissao_max,
        "tarifa_fixa": tarifa_fixa,
        "aliquota": aliquota,
        "imposto": imposto,
        "comissao_webvend_perc": comissao_webvend,
        "comissao_webvend_valor": comissao_webvend_valor,
        "liquido_min": liquido_min,
        "liquido_max": liquido_max,
        "url_foto": url_foto,
        "texto_completo": resultado
    }, None

# Função para gerar PDF e retornar bytes para download
def gerar_pdf_bytes(produtos, cliente, incluir_links=True):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4
    margem = 2*cm
    try:
        logo_path = "webvend_logo.png"
        logo_img = PilImage.open(logo_path)
        logo_width = 5 * cm
        logo_height = (logo_img.height / logo_img.width) * logo_width
        logo_img = logo_img.resize((int(logo_width), int(logo_height)))
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_logo:
            logo_img.save(tmp_logo.name)
            temp_logo_path = tmp_logo.name
        c.drawImage(temp_logo_path, largura - margem - logo_width, altura - logo_height - 1.5*cm,
                    width=logo_width, height=logo_height, mask='auto')
        os.remove(temp_logo_path)
    except Exception as e:
        print("Erro ao carregar logo na capa:", e)
    c.setFont("Helvetica-Bold", 24)
    c.setFillColorRGB(1, 0.7, 0)
    c.drawString(margem, altura - 5 * cm, "Análise de Produtos")
    c.setStrokeColorRGB(0.5, 0.5, 0.5)
    c.setLineWidth(1)
    c.line(margem, altura - 5.2 * cm, largura - margem, altura - 5.2 * cm)

    c.setFont("Helvetica", 18)
    c.setFillColorRGB(0,0,0)
    c.drawString(margem, altura - 7 * cm, f"Cliente: {cliente}")
    c.showPage()

    def cabecalho_pagina():
        c.setFont("Helvetica-Bold", 12)
        c.setFillColorRGB(0,0,0)
        c.drawString(margem, altura - 1.5 * cm, "Webvend | Análise de Produto")
        try:
            logo_img = PilImage.open("webvend_logo.png")
            w = 3.5 * cm
            h = (logo_img.height / logo_img.width) * w
            logo_img = logo_img.resize((int(w), int(h)))
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_logo:
                logo_img.save(tmp_logo.name)
                temp_logo_path = tmp_logo.name
            c.drawImage(temp_logo_path, largura - margem - w, altura - 1.5 * cm - h / 2,
                        width=w, height=h, mask='auto')
            os.remove(temp_logo_path)
        except Exception as e:
            print("Erro ao desenhar logo em página:", e)
        c.setStrokeColorRGB(0.5, 0.5, 0.5)
        c.setLineWidth(0.5)
        c.line(margem, altura - 1.8 * cm, largura - margem, altura - 1.8 * cm)

    for i, p in enumerate(produtos, start=1):
        cabecalho_pagina()
        y = altura - 2.5 * cm

        c.setFont("Helvetica-Bold", 20)
        c.setFillColorRGB(0, 0, 0.5)
        c.drawString(margem, y, f"Produto {i} de {len(produtos)}")
        y -= 1.2 * cm

        c.setFont("Helvetica-Bold", 16)
        c.drawString(margem, y, p['titulo'])
        y -= 1 * cm

        # Imagem
        if p['url_foto']:
            try:
                img_response = requests.get(p['url_foto'])
                img_data = BytesIO(img_response.content)
                img = PilImage.open(img_data)

                max_largura = largura - 2 * margem
                max_altura = 8 * cm
                img.thumbnail((max_largura, max_altura))

                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmpfile:
                    img.save(tmpfile.name)
                    temp_img_path = tmpfile.name

                x_img = margem
                y_img = y - img.height
                c.drawImage(temp_img_path, x_img, y_img, width=img.width, height=img.height)

                y = y_img - 0.5 * cm
                os.remove(temp_img_path)
            except:
                y -= 1 * cm
        else:
            y -= 1 * cm

        c.setStrokeColorRGB(0.5, 0.5, 0.5)
        c.setLineWidth(0.5)
        c.line(margem, y, largura - margem, y)
        y -= 0.5 * cm

        c.setFont("Helvetica", 11)
        c.setFillColorRGB(0,0,0)
        linhas = p['texto_completo'].split('\n')

        if linhas and linhas[0].startswith("Título:"):
            linhas.pop(0)
        if linhas and linhas[0].startswith("Preço:"):
            linhas.pop(0)

        for line in linhas:
            if y < margem + 3 * cm:
                c.showPage()
                cabecalho_pagina()
                y = altura - 2.5 * cm
                c.setFont("Helvetica", 11)
                c.setFillColorRGB(0,0,0)

            if line.startswith("Valor líquido estimado:"):
                c.setFont("Helvetica-Bold", 12)
                c.setFillColorRGB(0, 0.5, 0)
                text_width = c.stringWidth(line, "Helvetica-Bold", 12)
                padding = 2
                c.setFillColorRGB(0.9, 1, 0.9)
                c.rect(margem - padding, y - 2, text_width + 2 * padding, 14, fill=1, stroke=0)
                c.setFillColorRGB(0, 0.5, 0)
                c.drawString(margem, y, line)
                y -= 1 * cm
                c.setFillColorRGB(0,0,0)
                c.setFont("Helvetica", 11)
            else:
                c.drawString(margem, y, line)
                y -= 0.6 * cm

        if p.get('observacao'):
            c.setFont("Helvetica-Bold", 12)
            c.setFillColorRGB(0, 0, 1)
            c.drawString(margem, y, "Observação:")
            y -= 0.5 * cm
            c.setFont("Helvetica", 11)
            c.setFillColorRGB(0,0,0)
            c.drawString(margem, y, p['observacao'])
            y -= 1 * cm

        if incluir_links and p.get("url_produto"):
            link_text = "Clique para ver o anúncio"
            link_url = p["url_produto"]
            y -= 0.7 * cm
            c.setFillColorRGB(0, 0, 1)
            c.setFont("Helvetica-Bold", 12)
            c.drawString(margem, y, link_text)
            link_width = c.stringWidth(link_text, "Helvetica-Bold", 12)
            c.linkURL(link_url, (margem, y - 2, margem + link_width, y + 12))
            c.setLineWidth(1)
            c.line(margem, y - 1, margem + link_width, y - 1)
            c.setFillColorRGB(0,0,0)
            y -= 1 * cm
        else:
            y -= 0.5 * cm

        c.showPage()

    c.save()
    buffer.seek(0)
    return buffer.getvalue()

# Inicializa a lista de produtos na sessão
if "produtos" not in st.session_state:
    st.session_state.produtos = []

# Função para adicionar produto
def adicionar_produto():
    link = st.session_state.input_link.strip()
    try:
        aliquota = float(st.session_state.input_aliquota.replace(',', '.')) if st.session_state.input_aliquota else 0
    except:
        st.error("Alíquota inválida. Use número válido.")
        return
    try:
        comissao_webvend = float(st.session_state.input_comissao.replace(',', '.')) if st.session_state.input_comissao else 0
    except:
        st.error("Comissão inválida. Use número válido.")
        return

    if not link:
        st.error("Por favor, insira o link do produto.")
        return

    with st.spinner("Buscando dados do produto..."):
        dados, erro = extrair_dados_anuncio(link, aliquota, comissao_webvend)

    if erro:
        st.error(erro)
        return

    dados["url_produto"] = link
    dados["observacao"] = st.session_state.input_observacao.strip()
    st.session_state.produtos.append(dados)
    st.success("Produto adicionado com sucesso!")

# Função para limpar os campos
def limpar_campos():
    st.session_state.input_link = ""
    st.session_state.input_observacao = ""

# Função para remover produtos selecionados
def remover_produtos():
    selecionados_str = st.session_state.selecionados
    if not selecionados_str:
        st.warning("Selecione pelo menos um produto para remover.")
        return
    
    # Pega os índices reais usando o mapa
    indices_para_remover = [idx_map[s] for s in selecionados_str]

    for i in sorted(indices_para_remover, reverse=True):
        del st.session_state.produtos[i]

    st.session_state.selecionados = []
    st.success("Produto(s) removido(s) com sucesso!")

# Layout da página
st.title("Analisador Mercado Livre - Multi Produtos")

cliente = st.text_input("Nome do Cliente:", key="input_cliente")


st.text_input("Link do produto Mercado Livre:", key="input_link")


st.text_input("Alíquota do imposto (%) (ex: 12.5):", key="input_aliquota", max_chars=6)
st.text_input("Comissão Webvend (%) (ex: 10):", key="input_comissao", max_chars=6)
st.text_area("Observação:", key="input_observacao", height=3)
st.button("Adicionar Produto", on_click=lambda: [adicionar_produto(), limpar_campos()])

if st.session_state.produtos:
    st.subheader("Produtos adicionados:")

    # Lista com checkbox para remover
    if "selecionados" not in st.session_state:
        st.session_state.selecionados = []

    # Criar lista de opções com índice
    produtos_options = []
    idx_map = {}  # mapa de string para índice
    for i, p in enumerate(st.session_state.produtos):
        texto = f"{i+1}. {p['titulo']} - R$ {p['preco']:.2f}" if p['preco'] else f"{i+1}. {p['titulo']} - Preço não encontrado"
        produtos_options.append(texto)
        idx_map[texto] = i

    selecionados_str = st.multiselect(
        "Selecione os produtos para remover:",
        options=produtos_options,
        default=st.session_state.selecionados,
        key="selecionados"
)



    st.button("Remover Produtos Selecionados", on_click=remover_produtos)

    st.write("---")
    incluir_links = st.checkbox("Incluir links dos anúncios no PDF?", value=True)

    if st.button("Gerar PDF da Análise"):
        if not cliente.strip():
            st.error("Por favor, informe o nome do cliente antes de gerar o PDF.")
        else:
            pdf_bytes = gerar_pdf_bytes(st.session_state.produtos, cliente, incluir_links)
            st.download_button(
                label="Download do PDF",
                data=pdf_bytes,
                file_name=f"analise_mercadolivre_{cliente.replace(' ', '_')}.pdf",
                mime="application/pdf"
            )
else:
    st.info("Nenhum produto adicionado ainda.")
