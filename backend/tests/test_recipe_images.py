"""Testes do upload de fotos de receitas.

As imagens são geradas na hora com o Pillow: nenhum arquivo binário versionado,
e cada teste deixa claro que tipo de imagem está enviando.
"""

from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.services import storage
from tests.helpers import criar_receita


def imagem(formato: str = "PNG", tamanho: tuple[int, int] = (64, 48), exif: bytes | None = None) -> bytes:
    buffer = BytesIO()
    extra = {"exif": exif} if exif else {}
    Image.new("RGB", tamanho, color=(200, 120, 40)).save(buffer, formato, **extra)
    return buffer.getvalue()


def enviar(client, headers, receita_id, conteudo: bytes, nome="foto.png", tipo="image/png"):
    return client.put(
        f"/recipes/{receita_id}/image",
        headers=headers,
        files={"file": (nome, conteudo, tipo)},
    )


def arquivo_da_receita(media_dir: Path, receita: dict) -> Path:
    return media_dir / "recipes" / receita["image_url"].rsplit("/", 1)[-1]


@pytest.fixture
def receita(client: TestClient, auth_headers) -> dict:
    return criar_receita(client, auth_headers)


class TestEnvio:
    @pytest.mark.parametrize("formato", ["PNG", "JPEG", "WEBP"])
    def test_aceita_e_converte_para_webp(self, client: TestClient, auth_headers, receita, media_dir, formato):
        response = enviar(client, auth_headers, receita["id"], imagem(formato))

        assert response.status_code == 200, response.text
        url = response.json()["image_url"]
        assert url.startswith("/media/recipes/") and url.endswith(".webp")
        with Image.open(arquivo_da_receita(media_dir, response.json())) as gravada:
            assert gravada.format == "WEBP"

    def test_ignora_o_nome_enviado_pelo_cliente(self, client: TestClient, auth_headers, receita, media_dir):
        """Um nome com '../' não tem para onde ir: o servidor gera o próprio."""
        response = enviar(client, auth_headers, receita["id"], imagem(), nome="../../app/main.py")

        assert "main" not in response.json()["image_url"]
        assert list((media_dir / "recipes").iterdir()) == [arquivo_da_receita(media_dir, response.json())]

    def test_reduz_imagem_grande(self, client: TestClient, auth_headers, receita, media_dir):
        response = enviar(client, auth_headers, receita["id"], imagem(tamanho=(3200, 1000)))
        with Image.open(arquivo_da_receita(media_dir, response.json())) as gravada:
            assert max(gravada.size) == storage.MAX_DIMENSION

    def test_descarta_o_exif(self, client: TestClient, auth_headers, receita, media_dir):
        """Foto de celular pode trazer a localização GPS de quem tirou."""
        exif = Image.Exif()
        exif[0x010F] = "Fabricante do celular"  # Make
        exif[0x8825] = {2: (23.0, 33.0, 0.0)}  # GPSInfo: latitude
        response = enviar(client, auth_headers, receita["id"], imagem("JPEG", exif=exif.tobytes()))

        with Image.open(arquivo_da_receita(media_dir, response.json())) as gravada:
            assert not gravada.getexif()

    def test_trocar_a_foto_apaga_a_anterior(self, client: TestClient, auth_headers, receita, media_dir):
        primeira = enviar(client, auth_headers, receita["id"], imagem()).json()
        segunda = enviar(client, auth_headers, receita["id"], imagem("JPEG")).json()

        assert not arquivo_da_receita(media_dir, primeira).exists()
        assert arquivo_da_receita(media_dir, segunda).exists()

    def test_aparece_na_listagem(self, client: TestClient, auth_headers, receita):
        enviar(client, auth_headers, receita["id"], imagem())
        assert client.get("/recipes", headers=auth_headers).json()[0]["image_url"]


class TestRecusa:
    def test_arquivo_que_nao_e_imagem_devolve_415(self, client: TestClient, auth_headers, receita):
        """O Content-Type diz image/png, mas é quem envia que escolhe o header."""
        response = enviar(client, auth_headers, receita["id"], b"<?php system($_GET['c']); ?>")
        assert response.status_code == 415

    def test_formato_fora_da_lista_devolve_415(self, client: TestClient, auth_headers, receita):
        response = enviar(client, auth_headers, receita["id"], imagem("GIF"), tipo="image/gif")
        assert response.status_code == 415

    def test_imagem_truncada_devolve_415(self, client: TestClient, auth_headers, receita):
        response = enviar(client, auth_headers, receita["id"], imagem()[:60])
        assert response.status_code == 415

    def test_arquivo_grande_demais_devolve_413(self, client: TestClient, auth_headers, receita, monkeypatch):
        monkeypatch.setattr(storage, "MAX_IMAGE_BYTES", 100)
        response = enviar(client, auth_headers, receita["id"], imagem(tamanho=(200, 200)))
        assert response.status_code == 413

    def test_dimensoes_excessivas_devolvem_415(self, client: TestClient, auth_headers, receita, monkeypatch):
        """Bomba de descompressão: arquivo pequeno, pixels demais."""
        monkeypatch.setattr(storage, "MAX_IMAGE_PIXELS", 1000)
        response = enviar(client, auth_headers, receita["id"], imagem(tamanho=(100, 100)))
        assert response.status_code == 415

    def test_so_o_autor_envia(self, client: TestClient, other_auth_headers, receita, media_dir):
        response = enviar(client, other_auth_headers, receita["id"], imagem())

        assert response.status_code == 403
        # Quem não é autor não chega a gravar nada em disco.
        assert not (media_dir / "recipes").exists() or not any((media_dir / "recipes").iterdir())

    def test_falha_nao_altera_a_foto_atual(self, client: TestClient, auth_headers, receita):
        boa = enviar(client, auth_headers, receita["id"], imagem()).json()["image_url"]
        enviar(client, auth_headers, receita["id"], b"lixo")

        assert client.get(f"/recipes/{receita['id']}", headers=auth_headers).json()["image_url"] == boa


class TestRemocao:
    def test_remover_a_foto(self, client: TestClient, auth_headers, receita, media_dir):
        com_foto = enviar(client, auth_headers, receita["id"], imagem()).json()
        response = client.delete(f"/recipes/{receita['id']}/image", headers=auth_headers)

        assert response.json()["image_url"] is None
        assert not arquivo_da_receita(media_dir, com_foto).exists()

    def test_apagar_a_receita_apaga_a_foto(self, client: TestClient, auth_headers, receita, media_dir):
        com_foto = enviar(client, auth_headers, receita["id"], imagem()).json()
        client.delete(f"/recipes/{receita['id']}", headers=auth_headers)
        assert not arquivo_da_receita(media_dir, com_foto).exists()

    def test_apagar_a_conta_apaga_as_fotos(self, client: TestClient, auth_headers, receita, media_dir):
        com_foto = enviar(client, auth_headers, receita["id"], imagem()).json()
        client.delete("/users/me", headers=auth_headers)
        assert not arquivo_da_receita(media_dir, com_foto).exists()

    @pytest.mark.parametrize("nome", ["../config.py", "main.py", "x.webp", None])
    def test_so_apaga_nomes_gerados_pelo_servidor(self, media_dir, nome):
        """Defesa em profundidade: mesmo que um nome estranho chegue aqui, ele
        não vira um unlink fora do diretório de fotos."""
        alvo = media_dir / "config.py"
        media_dir.mkdir(parents=True, exist_ok=True)
        alvo.write_text("importante")

        storage.delete_recipe_image(nome)
        assert alvo.exists()
