"""Testes do hash de senha."""

import bcrypt

from app.services.security import hash_password, verify_password


def test_hash_nao_contem_a_senha_original():
    senha = "senha-de-teste-123"
    assert senha not in hash_password(senha)


def test_senha_correta_e_aceita():
    assert verify_password("senha-de-teste-123", hash_password("senha-de-teste-123"))


def test_senha_errada_e_recusada():
    assert not verify_password("outra-senha", hash_password("senha-de-teste-123"))


def test_hashes_da_mesma_senha_sao_diferentes():
    """Salt aleatório: sem ele, senhas iguais gerariam hashes iguais e um
    vazamento do banco revelaria de imediato quais contas compartilham senha."""
    assert hash_password("mesma-senha") != hash_password("mesma-senha")


def test_senha_acima_do_limite_do_bcrypt_nao_e_truncada():
    """bcrypt ignora tudo além do 72º byte. Sem o pré-hash SHA-256, estas duas
    senhas seriam indistinguíveis — a segunda é a primeira com um sufixo."""
    base = "a" * 72
    hash_da_longa = hash_password(base + "-sufixo-que-o-bcrypt-descartaria")

    assert verify_password(base + "-sufixo-que-o-bcrypt-descartaria", hash_da_longa)
    assert not verify_password(base, hash_da_longa)


def test_sem_o_pre_hash_o_bcrypt_de_fato_truncaria():
    """Documenta o problema que o pré-hash resolve, usando bcrypt cru."""
    hash_cru = bcrypt.hashpw(("a" * 72).encode(), bcrypt.gensalt())
    assert bcrypt.checkpw(("a" * 72 + "qualquer-coisa").encode(), hash_cru)


def test_hash_malformado_nao_libera_acesso():
    assert not verify_password("qualquer-senha", "isto-nao-e-um-hash-bcrypt")
