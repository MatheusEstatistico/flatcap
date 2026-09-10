"""
O REDCap de mentira — um servidor HTTP de verdade, para a suíte `e2e`.

Existe uma vez só, e é cumulativo. Os quatro `verificacao_fase*.py` que ele
substituiu eram quatro servidores falsos que ninguém rodava, e uma rede de
proteção acionada só no dia da entrega é cerimônia.

## O que ele enxerga que a suíte offline não enxerga

O `requests` montando o corpo urlencoded, o `typer` interpretando a linha de
comando, o código de saída que o shell recebe e o `entry point` do
`pyproject.toml`. **Foi essa camada que pegou o `fields[0]=`** — e por isso o
servidor daqui reproduz as quatro particularidades que o servidor da Feluma
ensinou, em vez de aceitar qualquer requisição bem-intencionada:

1. **Lista de parâmetros vai separada por vírgula.** A forma indexada
   `fields[0]`, `fields[1]` que o API Playground sugere chega do outro lado
   como um único `fields` com os nomes grudados. O servidor recusa com a
   mensagem literal, para que um retorno acidental àquela forma falhe aqui e
   não em produção.
2. **Erro de aplicação é HTTP 400 com `{"error": "..."}`**, e não exceção de
   rede.
3. **O nome do anexo vem no `Content-Type`** (`; name="..."`), e não no
   `Content-Disposition` como na maioria dos servidores.
4. **`content=file` devolve bytes**, não JSON. E `null` é JSON válido: há um
   modo que devolve corpo nulo, porque ele atravessaria o tratamento de erro
   sem alarme e estouraria três camadas adiante.

## Como se usa

    with servidor_falso.subir(registros=[...], anexos={"42": (nome, bytes)}) as api:
        subprocess.run([..., "--env", api.env(tmp_path)])

`api.url` é o endpoint; `api.chamadas` é a lista do que chegou, para o teste
afirmar sobre o corpo que o `requests` montou — que é a única forma de provar
que o payload sai no formato certo.
"""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

TOKEN = "A" * 32

# A mensagem literal do servidor da Feluma quando a forma indexada é usada. Ela
# está aqui, e não parafraseada, porque é o que o teste de regressão cita.
ERRO_FIELDS_INDEXADOS = (
    'The following values in the parameter "fields" are not valid: '
    "'record_idintromatricula1prof1matricula2aluno2'"
)


@dataclass
class Chamada:
    """
    Uma requisição como ela chegou: o corpo cru e o já decodificado.

    O corpo **cru** importa: é nele que `%5B0%5D` aparece, e um teste que olhe
    só para o dicionário decodificado não veria a forma indexada.
    """

    bruto: str
    campos: dict[str, list[str]]

    @property
    def content(self) -> str:
        return self.campos.get("content", [""])[0]

    def valor(self, chave: str) -> str:
        return self.campos.get(chave, [""])[0]

    def lista(self, chave: str) -> list[str]:
        bruto = self.valor(chave)
        return [parte for parte in bruto.split(",") if parte]


@dataclass
class Api:
    url: str
    chamadas: list[Chamada] = field(default_factory=list)

    def env(self, pasta: Path, root: Path | None = None) -> Path:
        """
        Escreve um `.env` apontando para este servidor, e devolve o caminho.

        É assim que o teste ponta a ponta entrega credenciais ao subprocesso sem
        mexer no ambiente da máquina que roda a suíte.
        """
        pasta = Path(pasta)
        raiz = Path(root) if root is not None else pasta / "FlatCapRoot"
        raiz.mkdir(parents=True, exist_ok=True)
        caminho = pasta / ".env"
        caminho.write_text(
            f"REDCAP_API_URL={self.url}\nREDCAP_TOKEN={TOKEN}\nFLATCAP_ROOT={raiz}\n",
            encoding="utf-8",
            newline="\n",
        )
        return caminho

    def ultima(self, content: str) -> Chamada | None:
        for chamada in reversed(self.chamadas):
            if chamada.content == content:
                return chamada
        return None


def _manipulador(estado: dict):
    class Manipulador(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args):  # silêncio: a suíte já é barulhenta
            return

        # -- respostas ------------------------------------------------------

        def _responder(self, codigo: int, corpo: bytes, tipo: str) -> None:
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def _json(self, codigo: int, corpo) -> None:
            self._responder(
                codigo, json.dumps(corpo, ensure_ascii=False).encode("utf-8"),
                "application/json; charset=utf-8",
            )

        def _erro(self, mensagem: str) -> None:
            """
            Como o REDCap erra: HTTP 400 com um JSON, não exceção de rede.
            """
            self._json(400, {"error": mensagem})

        # -- despacho -------------------------------------------------------

        def do_POST(self) -> None:  # noqa: N802 - a assinatura é do http.server
            tamanho = int(self.headers.get("Content-Length") or 0)
            bruto = self.rfile.read(tamanho).decode("utf-8")
            campos = parse_qs(bruto, keep_blank_values=True)
            chamada = Chamada(bruto=bruto, campos=campos)
            estado["chamadas"].append(chamada)

            if any("[" in chave for chave in campos):
                # A trava contra a forma indexada. Ela recusa aqui pelo mesmo
                # motivo que o servidor de verdade recusa: para que o defeito
                # apareça na suíte e não no dia do atendimento.
                self._erro(ERRO_FIELDS_INDEXADOS)
                return

            if chamada.valor("token") != TOKEN:
                self._erro("You do not have permission to use the API")
                return

            if estado.get("corpo_nulo"):
                self._json(200, None)
                return

            despacho = {
                "project": self._projeto,
                "record": self._registros,
                "metadata": self._metadados,
                "file": self._arquivo,
            }
            acao = despacho.get(chamada.content)
            if acao is None:
                self._erro(f"The value of 'content' is not valid: {chamada.content!r}")
                return
            acao(chamada)

        # -- os quatro endpoints -------------------------------------------

        def _projeto(self, _chamada: Chamada) -> None:
            self._json(200, estado["projeto"])

        def _registros(self, chamada: Chamada) -> None:
            registros = estado["registros"]
            pedidos = chamada.lista("records")
            if pedidos:
                registros = [r for r in registros if str(r.get("record_id")) in pedidos]
            campos = chamada.lista("fields")
            if campos:
                registros = [{c: r.get(c, "") for c in campos} for r in registros]
            self._json(200, registros)

        def _metadados(self, _chamada: Chamada) -> None:
            self._json(200, estado["metadados"])

        def _arquivo(self, chamada: Chamada) -> None:
            registro = chamada.valor("record")
            anexo = estado["anexos"].get(registro)
            if anexo is None:
                # A frase que o `redcap.py` reconhece como ausência esperada, e
                # não como falha — cliente sem anexo é caso normal do fluxo.
                self._erro(
                    f"There is no file to download for record {registro}"
                )
                return
            nome, conteudo = anexo
            # O nome vai no Content-Type, que é onde o REDCap o põe.
            self._responder(
                200,
                conteudo,
                f'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet; name="{nome}"',
            )

    return Manipulador


PROJETO_PADRAO = {
    "project_id": "1234",
    "project_title": "Assessoria estatística — Feluma",
    "is_longitudinal": "0",
}


@contextmanager
def subir(
    registros: list[dict] | None = None,
    anexos: dict[str, tuple[str, bytes]] | None = None,
    projeto: dict | None = None,
    metadados: list[dict] | None = None,
    corpo_nulo: bool = False,
):
    """
    Sobe o servidor numa porta livre e o derruba no fim, aconteça o que
    acontecer.

    `corpo_nulo=True` faz toda resposta ser `null` — que é JSON válido e
    atravessaria o tratamento de erro sem alarme.
    """
    estado = {
        "registros": registros if registros is not None else [],
        "anexos": anexos or {},
        "projeto": projeto if projeto is not None else PROJETO_PADRAO,
        "metadados": metadados or [],
        "chamadas": [],
        "corpo_nulo": corpo_nulo,
    }
    servidor = HTTPServer(("127.0.0.1", 0), _manipulador(estado))
    porta = servidor.server_address[1]
    thread = threading.Thread(target=servidor.serve_forever, daemon=True)
    thread.start()
    api = Api(url=f"http://127.0.0.1:{porta}/redcap/api/", chamadas=estado["chamadas"])
    try:
        yield api
    finally:
        servidor.shutdown()
        servidor.server_close()
        thread.join(timeout=5)
