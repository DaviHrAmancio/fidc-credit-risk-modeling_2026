"""Copia as tabelas de outputs/tabelas_readme.md para dentro dos marcadores do README.

Os blocos <!-- BEGIN:nome --> ... <!-- END:nome --> do README são substituídos pelo texto gerado pelo
pipeline. Assim nenhum número da tabela é digitado à mão; verify_output.py confere a igualdade.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PADRAO = re.compile(r"<!-- BEGIN:(\w+) -->\n(.*?)\n<!-- END:\1 -->", re.S)


def blocos(texto: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in PADRAO.finditer(texto)}


def main() -> int:
    gerado = blocos((RAIZ / "outputs" / "tabelas_readme.md").read_text(encoding="utf-8"))
    alvo = RAIZ / "README.md"
    texto = alvo.read_text(encoding="utf-8")
    faltando = [k for k in blocos(texto) if k not in gerado]
    if faltando:
        print("Marcadores sem tabela gerada:", faltando)
        return 1

    def troca(m: re.Match) -> str:
        return f"<!-- BEGIN:{m.group(1)} -->\n{gerado[m.group(1)]}\n<!-- END:{m.group(1)} -->"

    novo = PADRAO.sub(troca, texto)
    alvo.write_text(novo, encoding="utf-8")
    print("README atualizado:", ", ".join(sorted(blocos(novo))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
