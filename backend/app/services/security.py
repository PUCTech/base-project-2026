"""Hash e verificação de senha.

Regra que o resto do código depende: senha em texto puro entra aqui e não sai
daqui. Nada fora deste módulo guarda, loga ou compara a senha original.
"""

import base64
import hashlib

import bcrypt


# bcrypt ignora tudo além do 72º byte da senha. Uma senha de 100 caracteres
# teria os 28 últimos descartados em silêncio — e duas senhas com os mesmos 72
# primeiros bytes passariam a ser a mesma senha.
#
# A saída do SHA-256 em base64 tem 44 bytes fixos, qualquer que seja a entrada,
# então o pré-hash elimina o limite sem truncar nada. É a mesma construção do
# `bcrypt_sha256`. O base64 é necessário porque o digest binário pode conter
# um byte 0x00, e o bcrypt trata NUL como fim da senha.
def _prepare(password: str) -> bytes:
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(password: str) -> str:
    """Devolve o hash bcrypt da senha, com salt aleatório embutido."""
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Confere a senha contra o hash, em tempo constante.

    `bcrypt.checkpw` compara os hashes sem short-circuit, então o tempo de
    resposta não revela quantos caracteres estavam certos.
    """
    try:
        return bcrypt.checkpw(_prepare(password), password_hash.encode("utf-8"))
    except ValueError:
        # Hash malformado no banco (registro corrompido ou migração mal feita).
        # Vale como credencial inválida, nunca como acesso liberado.
        return False


# Hash descartável de uma senha qualquer, calculado uma vez na importação.
_DUMMY_HASH = hash_password("senha-que-nao-pertence-a-ninguem")


def waste_time_like_a_verification() -> None:
    """Gasta o mesmo tempo de um `verify_password` real.

    O login chama isto quando o usuário não existe. Sem essa compensação, a
    resposta de "usuário inexistente" volta perceptivelmente mais rápido que a
    de "senha errada" — e essa diferença de tempo é suficiente para enumerar
    quais contas existem, mesmo com as duas respondendo o mesmo 401.
    """
    bcrypt.checkpw(_prepare("qualquer-coisa"), _DUMMY_HASH.encode("utf-8"))
