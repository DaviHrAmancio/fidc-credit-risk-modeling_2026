"""Baixa o Informe Mensal de FIDC da CVM, filtra o fundo e extrai indicadores agregados.

Precisa de INTERNET (o sandbox em que este repositório foi montado não tinha). Uso:
    python scripts/baixar_cvm.py                                   # fundo de casos/pan_auto
    python scripts/baixar_cvm.py --config casos/outro/config_cvm.json
    python scripts/baixar_cvm.py --zips-locais pasta_com_zips/     # sem rede: zips baixados à mão

Saída em ``data/cvm/<cnpj>/`` (ignorada pelo git): csv filtrados por competência,
``schema_report.csv`` (colunas reais), ``indicadores_cvm.csv`` e ``indicadores_log.csv``
(qual coluna da CVM originou cada número).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from fidc_risk import cvm  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(RAIZ / "casos" / "pan_auto" / "config_cvm.json"))
    ap.add_argument("--saida", default=str(RAIZ / "data" / "cvm"))
    ap.add_argument("--zips-locais", default=None, help="pasta com inf_mensal_fidc_AAAAMM.zip já baixados")
    a = ap.parse_args()

    cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
    cnpj = cvm.normaliza_cnpj(cfg["fundo"]["cnpj"])
    base = Path(a.saida) / cnpj
    base.mkdir(parents=True, exist_ok=True)
    inds, logs, schema_gravado = [], [], False

    for comp in cfg["competencias"]:
        try:
            zp = (Path(a.zips_locais) / f"inf_mensal_fidc_{comp}.zip" if a.zips_locais
                  else cvm.baixar_informe(comp, Path(a.saida) / "_zips"))
            if not zp.exists():
                raise FileNotFoundError(zp)
        except Exception as e:  # noqa: BLE001
            print(f"[{comp}] PULADA: {e}", file=sys.stderr)
            continue
        if not schema_gravado:
            cvm.relatorio_schema(zp).to_csv(base / "schema_report.csv", index=False)
            schema_gravado = True
        tabelas = cvm.filtrar_cnpj(zp, cnpj)
        if not tabelas:
            print(f"[{comp}] fundo {cfg['fundo']['cnpj']} NÃO encontrado em nenhuma tabela "
                  "(ainda sem informe, ou o CNPJ está em coluna de classe com outro formato).", file=sys.stderr)
            continue
        pasta = base / comp
        pasta.mkdir(exist_ok=True)
        for nome, df in tabelas.items():
            df.to_csv(pasta / Path(nome).name, index=False)
        ind, log = cvm.extrair_indicadores(tabelas, cfg["regras"])
        der = cvm.razoes_derivadas(ind, cfg.get("razoes", {}))
        ind = pd.concat([ind, der], ignore_index=True)
        ind.insert(0, "competencia", comp)
        log.insert(0, "competencia", comp)
        inds.append(ind)
        logs.append(log)
        print(f"[{comp}] {len(tabelas)} tabelas com o fundo; indicadores sem valor: "
              f"{', '.join(ind[ind['valor'].isna()]['indicador']) or 'nenhum'}")

    if inds:
        pd.concat(inds).to_csv(base / "indicadores_cvm.csv", index=False)
        pd.concat(logs).to_csv(base / "indicadores_log.csv", index=False)
        print(f"OK -> {base}  (valide as regex com schema_report.csv; status: {cfg.get('status_regras', '')[:70]}...)")
        return 0
    print("Nenhuma competência processada.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
