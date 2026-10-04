"""Dados abertos da CVM: Informe Mensal de FIDC (agregado por fundo/classe).

O que existe (e o que NÃO existe) de dado público
-------------------------------------------------
O informe mensal traz, por fundo/classe e competência: PL, carteira, composição por segmento,
inadimplência por faixa de atraso, provisão (PDD), prazos, substituições/recompras e cotas por
subclasse. Ele NÃO traz devedores (sacados) individuais nem duplicatas individuais. Por isso a
estratégia do projeto é: **calibrar parâmetros agregados com dado real e simular a carteira
micro (sacados) sinteticamente**.

Fonte: ``https://dados.cvm.gov.br/dados/FIDC/DOC/INF_MENSAL/DADOS/inf_mensal_fidc_AAAAMM.zip``
(um zip por competência; anos antigos em ``HIST/inf_mensal_fidc_AAAA.zip``).

AVISO DE VALIDAÇÃO: o layout das colunas mudou com a RCVM 175 e pode mudar de novo. Este módulo
NÃO assume nomes de colunas: ``relatorio_schema`` lista o que existe de verdade e
``extrair_indicadores`` usa expressões regulares configuráveis (``casos/*/config_cvm.json``).
As expressões que acompanham o repositório são um PONTO DE PARTIDA a validar contra o schema.
Para tudo o que é obtido por rede, os testes usam arquivos sintéticos (nenhum teste acessa a CVM).
"""
from __future__ import annotations

import io
import re
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

URL_BASE = "https://dados.cvm.gov.br/dados/FIDC/DOC/INF_MENSAL/DADOS/"


def url_informe(aaaamm: str) -> str:
    if not re.fullmatch(r"\d{6}", aaaamm):
        raise ValueError("competência no formato AAAAMM, ex.: 202604")
    return f"{URL_BASE}inf_mensal_fidc_{aaaamm}.zip"


def normaliza_cnpj(x) -> str:
    """Só dígitos (``65.473.848/0001-83`` -> ``65473848000183``)."""
    return re.sub(r"\D", "", str(x))


def baixar_informe(aaaamm: str, destino: Path, timeout: int = 180, forcar: bool = False) -> Path:
    """Baixa o zip da competência (cache em ``destino``). Precisa de acesso à internet."""
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    arq = destino / f"inf_mensal_fidc_{aaaamm}.zip"
    if arq.exists() and not forcar:
        return arq
    req = urllib.request.Request(url_informe(aaaamm), headers={"User-Agent": "fidc-creditrisk-modelagem"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            dados = r.read()
    except Exception as e:  # noqa: BLE001 - mensagem útil para o usuário
        raise RuntimeError(f"falha ao baixar {url_informe(aaaamm)}: {e}. Verifique a rede e se a "
                           "competência já foi publicada em dados.cvm.gov.br") from e
    zipfile.ZipFile(io.BytesIO(dados)).testzip()  # levanta se o zip estiver corrompido
    tmp = arq.with_suffix(".part")
    tmp.write_bytes(dados)
    tmp.replace(arq)
    return arq


def _ler_csv(zf: zipfile.ZipFile, nome: str, **kw) -> pd.DataFrame:
    with zf.open(nome) as f:
        return pd.read_csv(f, sep=";", encoding="latin-1", dtype=str, **kw)


def _colunas_cnpj(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if "CNPJ" in c.upper()]


def filtrar_cnpj(zip_path: Path, cnpj: str) -> dict[str, pd.DataFrame]:
    """Linhas do fundo/classe em CADA csv do zip (casa por qualquer coluna *CNPJ*)."""
    alvo = normaliza_cnpj(cnpj)
    out = {}
    with zipfile.ZipFile(zip_path) as zf:
        for nome in zf.namelist():
            if not nome.lower().endswith(".csv"):
                continue
            df = _ler_csv(zf, nome)
            cols = _colunas_cnpj(df)
            if not cols:
                continue
            mask = np.zeros(len(df), dtype=bool)
            for c in cols:
                mask |= df[c].map(normaliza_cnpj).to_numpy() == alvo
            if mask.any():
                out[nome] = df[mask].reset_index(drop=True)
    return out


def relatorio_schema(zip_path: Path) -> pd.DataFrame:
    """Tabela (arquivo, coluna, exemplo) de todos os csv do zip, para validar as regex."""
    linhas = []
    with zipfile.ZipFile(zip_path) as zf:
        for nome in zf.namelist():
            if not nome.lower().endswith(".csv"):
                continue
            df = _ler_csv(zf, nome, nrows=3)
            for c in df.columns:
                ex = df[c].dropna().iloc[0] if df[c].notna().any() else ""
                linhas.append({"arquivo": nome, "coluna": c, "exemplo": ex})
    return pd.DataFrame(linhas)


def _numero(s: pd.Series) -> pd.Series:
    """Converte texto numérico da CVM (ponto decimal; tolera vírgula) em float."""
    t = s.astype(str).str.strip().str.replace(",", ".", regex=False)
    return pd.to_numeric(t, errors="coerce")


def extrair_indicadores(tabelas: dict[str, pd.DataFrame], regras: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Aplica as regras de ``config_cvm.json`` às tabelas filtradas de UMA competência.

    ``regras[nome] = {"arquivo": regex_do_nome_do_csv, "colunas": [regex_de_coluna, ...]}``.
    O indicador é a SOMA (sobre as linhas do fundo e as colunas casadas). Devolve
    (indicadores, log): o log lista, por indicador, arquivo e colunas efetivamente usados, para
    que cada número seja rastreável até a coluna da CVM. Sem casamento -> NaN (e log vazio).
    """
    ind, log = [], []
    for nome, r in regras.items():
        padrao_arq = re.compile(r["arquivo"], re.I)
        pads = [re.compile(p, re.I) for p in r["colunas"]]
        total, achou = 0.0, False
        for arq, df in tabelas.items():
            if not padrao_arq.search(arq):
                continue
            cols = [c for c in df.columns if any(p.search(c) for p in pads)]
            for c in cols:
                v = _numero(df[c])
                if v.notna().any():
                    total += float(v.sum())
                    achou = True
                    log.append({"indicador": nome, "arquivo": arq, "coluna": c,
                                "valor_coluna": float(v.sum())})
        ind.append({"indicador": nome, "valor": total if achou else np.nan})
    return pd.DataFrame(ind), pd.DataFrame(log, columns=["indicador", "arquivo", "coluna", "valor_coluna"])


def razoes_derivadas(ind: pd.DataFrame, razoes: dict) -> pd.DataFrame:
    """``razoes[nome] = [numerador, denominador]`` sobre indicadores já extraídos."""
    v = ind.set_index("indicador")["valor"]
    linhas = []
    for nome, (num, den) in razoes.items():
        n, d = v.get(num, np.nan), v.get(den, np.nan)
        linhas.append({"indicador": nome, "valor": n / d if d and not np.isnan(d) and d != 0 else np.nan})
    return pd.DataFrame(linhas)
