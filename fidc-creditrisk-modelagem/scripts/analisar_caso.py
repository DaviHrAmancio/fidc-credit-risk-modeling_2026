"""Análise de um CASO de fundo real: dados observados por classe + ponte com o modelo de perdas.

Uso:
    python scripts/analisar_caso.py                                   # casos/via_multicredito
    python scripts/analisar_caso.py --caso casos/_modelo/config_caso.json --dados meu.csv

Entradas : ``config_caso.json`` + ``dados_observados.csv`` (ao lado da config) + ``outputs/pmf_crplus_*.csv``
           (rode antes ``python pipeline_fidc_creditrisk.py``).
Saídas   : ``outputs_caso/<caso>/`` (csv, RELATORIO.md, metadata.json) e ``figures/caso_<caso>_*.png``.

Natureza de cada bloco (rotulada no relatório e nas figuras):
    OBSERVADO  números da fonte externa (jun/2024 no caso-exemplo), só aritmética sobre eles;
    CALCULADO  contas determinísticas sobre o observado (subordinação, look-through);
    ESTIMADO   proxy do retorno do fundo (pesos de PL, sem fluxos);
    SIMULADO   ponte com a carteira SINTÉTICA do pipeline (cascata de 3 classes sobre a pmf de perdas).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from fidc_risk import __version__  # noqa: E402
from fidc_risk import observado as obs  # noqa: E402
from fidc_risk.metrics import resumo_distribuicao  # noqa: E402
from fidc_risk.waterfall import absorcao_tres_classes, estatisticas_tres_classes  # noqa: E402

ROT = {"senior": "Sênior", "mezanino": "Mezanino", "junior": "Júnior"}
COR = {"senior": "#0b6e6e", "mezanino": "#d98e04", "junior": "#b5301f", "cdi": "#555555"}


def pc(x, n=2):
    return f"{x:.{n}f}%".replace(".", ",")


def num(x, n=2):
    return f"{x:,.{n}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def tabela_md(cab, linhas):
    return "\n".join(["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
                     + ["| " + " | ".join(l) + " |" for l in linhas])


# --------------------------------------------------------------------------------- ponte com o modelo
def ponte_modelo(cfg: dict, sub: pd.DataFrame, met: pd.DataFrame, cls: list[str]):
    """Cascata de 3 classes sobre a pmf de perdas sintética, com a estrutura do fundo (último mês)."""
    m = cfg["modelo"]
    resumo = pd.read_csv(RAIZ / "outputs" / "resumo_perdas.csv")
    ult = sub.iloc[-1]
    s_mez = float(ult["pct_mezanino"]) if "mezanino" in cls else 0.0
    s_jun = float(ult["pct_junior"])
    linhas, quantis, curvas = [], [], []
    for cen in m["cenarios"]:
        pmf = pd.read_csv(RAIZ / m["pmf_arquivo"].format(cenario=cen))
        preco = float(resumo[(resumo["cenario"] == cen) & (resumo["modelo"] == "crplus_gamma")]["preco_total"].iloc[0])
        perda_pl = pmf["perda"].to_numpy(dtype=float) / preco          # perda como fração do PL
        p = pmf[m["coluna_pmf"]].to_numpy(dtype=float)
        est = estatisticas_tres_classes(perda_pl, p, 1.0, s_mez, s_jun)
        est.insert(0, "cenario", cen)
        est["el_anual_aprox_pct_classe"] = est["el_pct_classe"] * m["ciclos_por_ano"]
        prem = met.set_index("classe")["excesso_vs_cdi_pp"] / 100.0
        est["premio_observado_vs_cdi"] = est["classe"].map(prem)
        est["premio_sobre_el_anual"] = np.where(est["el_anual_aprox_pct_classe"] > 1e-12,
                                                est["premio_observado_vs_cdi"] / est["el_anual_aprox_pct_classe"],
                                                np.nan)
        linhas.append(est)
        r = resumo_distribuicao(perda_pl, p, [0.99, 0.999])
        quantis.append({"cenario": cen, "el_pct_pl": r["el"], "var_99_pct_pl": r["var_0.99"],
                        "var_999_pct_pl": r["var_0.999"], "es_999_pct_pl": r["es_0.999"],
                        "mult_junior_sobre_var999": s_jun / r["var_0.999"],
                        "mult_senior_sobre_var999": (s_jun + s_mez) / r["var_0.999"]})
    grade = np.linspace(0.0, 0.70, 141)
    ps, pm, pj = absorcao_tres_classes(grade, 1.0, s_mez, s_jun)
    curva = pd.DataFrame({"perda_carteira_pct_pl": grade, "perda_senior_pct_pl": ps,
                          "perda_mezanino_pct_pl": pm, "perda_junior_pct_pl": pj})
    return pd.concat(linhas, ignore_index=True), pd.DataFrame(quantis), curva, (s_mez, s_jun)


# --------------------------------------------------------------------------------- figuras
def figuras(df, cls, curva, quant, nome, saida: Path):
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    x = pd.PeriodIndex(df["competencia"], freq="M").to_timestamp()

    fig, ax = plt.subplots(figsize=(8, 4.4))
    for c in cls:
        ax.plot(x, obs.acumulado(df[f"rent_{c}_pct"]), marker="o", ms=3.5, color=COR[c], label=ROT[c])
    ax.plot(x, obs.acumulado(df["cdi_pct_mes"]), "--", color=COR["cdi"], label="CDI")
    ax.set_ylabel("retorno acumulado (%)")
    ax.set_title("Retorno acumulado por classe de cota vs CDI  [OBSERVADO]", loc="left", fontsize=11)
    ax.legend(frameon=False)
    fig.text(0.01, 0.01, "fonte: casos/%s/dados_observados.csv" % nome, fontsize=7, color="#666")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(saida / f"caso_{nome}_retorno_acumulado.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.4))
    for c in cls:
        ax.plot(x, df[f"rent_{c}_pct"], marker="o", ms=3.5, color=COR[c], label=ROT[c])
    ax.plot(x, df["cdi_pct_mes"], "--", color=COR["cdi"], label="CDI")
    ax.axhline(0, color="#999", lw=0.6)
    ax.set_ylabel("retorno no mês (%)")
    ax.set_title("Retorno mensal: a sênior acompanha o CDI; a júnior oscila  [OBSERVADO]", loc="left", fontsize=11)
    ax.legend(frameon=False, ncol=4, loc="lower right", fontsize=8)
    fig.text(0.01, 0.01, "fonte: casos/%s/dados_observados.csv" % nome, fontsize=7, color="#666")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(saida / f"caso_{nome}_retorno_mensal.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.4))
    base = np.zeros(len(df))
    for c in ("junior", "mezanino", "senior"):
        if c in cls:
            v = df[f"pl_{c}_mil"].to_numpy(dtype=float) / 1000.0
            ax.bar(x, v, width=22, bottom=base, color=COR[c], label=ROT[c])
            base += v
    ax.set_ylabel("PL (R$ milhões)")
    ax.set_title("PL por classe de cota  [OBSERVADO]", loc="left", fontsize=11)
    ax.legend(frameon=False, ncol=3)
    fig.text(0.01, 0.01, "fonte: casos/%s/dados_observados.csv" % nome, fontsize=7, color="#666")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(saida / f"caso_{nome}_pl_por_classe.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.4))
    for c in ("junior", "mezanino", "senior"):
        if c in cls:
            ax.plot(100 * curva["perda_carteira_pct_pl"], 100 * curva[f"perda_{c}_pct_pl"], color=COR[c], label=ROT[c], lw=2)
    for _, q in quant.iterrows():
        ax.axvline(100 * q["var_999_pct_pl"], ls=":", color="#333")
        ax.text(100 * q["var_999_pct_pl"] + 0.4, 24.0, f"VaR 99,9% {q['cenario']}", rotation=90, fontsize=8, va="bottom")
    ax.set_xlabel("perda de crédito da carteira (% do PL)")
    ax.set_ylabel("perda absorvida pela classe (% do PL do fundo)")
    ax.set_title("Quem absorve a perda: júnior, depois mezanino, depois sênior  [CALCULADO + SIMULADO]", loc="left", fontsize=10)
    ax.legend(frameon=False)
    fig.text(0.01, 0.01, "fonte: outputs_caso/%s/curva_absorcao.csv; VaR da carteira SINTÉTICA (CreditRisk+ Gamma)" % nome,
             fontsize=7, color="#666")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(saida / f"caso_{nome}_absorcao.png", dpi=150)
    plt.close(fig)


# --------------------------------------------------------------------------------- relatório
def relatorio(cfg, df, cls, met, aud, sub, proxy, absor, quant, curva, estrutura) -> str:
    f, fo, rg = cfg["fundo"], cfg["fonte"], cfg.get("regulamento_citado_pela_fonte", {})
    s_mez, s_jun = estrutura
    L = [f"# Caso: {f['nome']}", "",
         f"> **Natureza:** dados OBSERVADOS de fonte externa ({fo['emissor']}, relatório de {fo['data_relatorio']}, "
         f"janela {fo['janela']}) + ponte SIMULADA com a carteira sintética do pipeline. "
         f"**Defasagem:** {fo['defasagem']}. Isto é análise de risco, não recomendação de investimento.", "",
         f"- CNPJ {f['cnpj']}; {f['tipo']}; {f['condominio']}.",
         f"- Administradora: {f['administradora'].rstrip('.')}. Gestora: {f['gestora'].rstrip('.')}. "
         f"Custodiante: {f['custodiante'].rstrip('.')}.",
         f"- Fonte: {fo['url']}", "",
         "## 1. Critérios pedidos (OBSERVADO)", ""]
    cab = ["Classe", "PL fim do período (R$ mil)", "% do PL", "Retorno do último mês", "Retorno 12M", "CDI 12M",
           "% do CDI", "Excesso sobre o CDI (pp)"]
    lin = [[ROT[r["classe"]], num(r["pl_ultimo_mes_mil"], 0), pc(100 * r["pl_pct_do_total"], 1),
            pc(r["rent_ultimo_mes_pct"]), pc(r["rent_acum_pct"]), pc(r["cdi_acum_pct"]),
            pc(r["pct_cdi_acum"], 1), num(r["excesso_vs_cdi_pp"])] for _, r in met.iterrows()]
    L += [tabela_md(cab, lin), "",
          f"PL total no último mês: R$ {num(df['pl_total_mil'].iloc[-1], 0)} mil. "
          f"Cotistas (jun/2024): {cfg['cotistas_jun_2024']['senior']} na sênior e "
          f"{cfg['cotistas_jun_2024']['subordinadas_mezanino_mais_junior']} nas subordinadas (mezanino + júnior). "
          "A fonte não informa se os cotistas da sênior são pessoas físicas (varejo); **não verificado**.", "",
          "![retorno acumulado](../../figures/caso_%s_retorno_acumulado.png)" % cfg["caso"], "",
          "## 2. Sênior × subordinadas: o que os números mostram (OBSERVADO)", ""]
    cab = ["Classe", "Média mensal", "Volatilidade mensal", "Melhor mês", "Pior mês", "Meses negativos",
           "Meses abaixo do CDI", "Maior queda (pico-vale)"]
    lin = [[ROT[r["classe"]], pc(r["media_mensal_pct"]), pc(r["vol_mensal_pct"]), pc(r["melhor_mes_pct"]),
            pc(r["pior_mes_pct"]), str(r["meses_negativos"]), str(r["meses_abaixo_cdi"]), pc(r["max_queda_pct"])]
           for _, r in met.iterrows()]
    m_ = met.set_index("classe")
    acima = [ROT[c] for c in cls if m_.loc[c, "meses_abaixo_cdi"] == 0]
    abaixo = [f"a {ROT[c]} ficou abaixo do CDI em {int(m_.loc[c, 'meses_abaixo_cdi'])} de {len(df)} meses"
              for c in cls if m_.loc[c, "meses_abaixo_cdi"] > 0]
    leit = "Leitura: "
    leit += (f"{' e '.join(acima)} ficaram acima do CDI em todos os {len(df)} meses da janela" if acima
             else "nenhuma classe ficou acima do CDI em todos os meses")
    leit += (f"; {'; '.join(abaixo)}. " if abaixo else ". ")
    leit += ("A oscilação mensal cresce da sênior para a júnior (desvio-padrão de "
             + ", ".join(f"{ROT[c]} {pc(m_.loc[c, 'vol_mensal_pct'])}" for c in cls) + "), junto com o retorno acumulado. "
             "**Doze observações não sustentam inferência estatística** sobre retorno esperado ou risco futuro.")
    L += [tabela_md(cab, lin), "", leit, "",
          "![retorno mensal](../../figures/caso_%s_retorno_mensal.png)" % cfg["caso"], "",
          "## 3. Estrutura de subordinação (CALCULADO a partir do OBSERVADO)", ""]
    u = sub.iloc[-1]
    L += [f"No último mês: sênior {pc(100 * u['pct_senior'], 1)} do PL, mezanino {pc(100 * u['pct_mezanino'], 1)}, "
          f"júnior {pc(100 * u['pct_junior'], 1)}; subordinação total {pc(100 * u['subordinacao_total'], 1)}. "
          f"Na janela, a subordinação total variou de {pc(100 * sub['subordinacao_total'].min(), 1)} a "
          f"{pc(100 * sub['subordinacao_total'].max(), 1)} e a da júnior (% do PL) de "
          f"{pc(100 * sub['pct_junior'].min(), 1)} a {pc(100 * sub['pct_junior'].max(), 1)}. "
          f"O regulamento (segundo a fonte) exige no mínimo {pc(100 * rg.get('subordinacao_minima_pct_pl', float('nan')), 0)} "
          f"de subordinadas e {pc(100 * rg.get('junior_minima_pct_pl', float('nan')), 0)} de júnior; "
          f"benchmarks: sênior {rg.get('benchmark_senior', 'n/d')}, mezanino {rg.get('benchmark_mezanino', 'n/d')}.", "",
          "![PL por classe](../../figures/caso_%s_pl_por_classe.png)" % cfg["caso"], ""]
    cart = cfg.get("carteira_jun_2024_pct_pl")
    if cart:
        pos = cart["maior_fidc_investido"]
        L += ["**Look-through (CALCULADO, aritmética simples).** O fundo é um FIC: investe em cotas de outros FIDCs, e "
              f"{pc(100 * pos, 1)} do PL estava em um único FIDC ({cart['n_fidcs_investidos']} FIDCs no total). "
              f"Se a perda ocorresse só nessa posição, uma queda de {pc(100 * u['pct_junior'] / pos, 1)} no valor dela "
              f"bastaria para zerar a júnior do fundo ({pc(100 * u['pct_junior'], 1)} do PL ÷ {pc(100 * pos, 1)}). "
              "Isto mostra o efeito da concentração; não é uma previsão, e a posição pode ser de cota sênior, mezanino "
              "ou júnior do FIDC investido (a fonte informa só os totais por tipo de cota).", ""]
    L += ["## 4. Ponte com o modelo de risco de crédito (SIMULADO, ilustrativo)", "",
          "A cascata de 3 classes (júnior → mezanino → sênior, sem excesso de spread, leitura conservadora) foi aplicada "
          "à distribuição de perdas **da carteira sintética** de duplicatas do pipeline (CreditRisk+ com setores Gamma), "
          f"usando a estrutura observada no último mês (mezanino {pc(100 * s_mez, 1)}, júnior {pc(100 * s_jun, 1)}). "
          "**Esta carteira não é a dos FIDCs investidos pelo fundo.** A pergunta respondida é: *dado um nível de perda "
          "de crédito de uma carteira de recebíveis comerciais, qual classe a absorve, e o prêmio observado paga por isso?*", ""]
    cab = ["Cenário", "Classe", "Anexação–destacamento (% PL)", "P(perda) no ciclo", "P(zerada) no ciclo",
           "EL no ciclo (% da classe)", "EL anual aprox. (% da classe)", "Prêmio observado vs CDI"]
    lin = []
    for _, r in absor.iterrows():
        lin.append([r["cenario"], ROT[r["classe"]], f"{pc(100 * r['anexacao_pct_pl'], 1)}–{pc(100 * r['destacamento_pct_pl'], 1)}",
                    pc(100 * r["p_perda"], 3), pc(100 * r["p_zerada"], 3), pc(100 * r["el_pct_classe"], 3),
                    pc(100 * r["el_anual_aprox_pct_classe"], 2), pc(100 * r["premio_observado_vs_cdi"], 2)])
    L += [tabela_md(cab, lin), "",
          "*EL anual aprox. = EL do ciclo × ciclos por ano (linear, sem reposição pelo excesso de spread e sem "
          "revolvência do capital). É uma ordem de grandeza. Sem excesso de spread, qualquer perda > 0 atinge a júnior; com ele "
          "(não usado aqui) a P(perda) da júnior seria bem menor.*", ""]
    cab = ["Cenário", "EL carteira (% PL)", "VaR 99% (% PL)", "VaR 99,9% (% PL)", "ES 99,9% (% PL)",
           "Anexação da mezanino ÷ VaR 99,9%", "Anexação da sênior ÷ VaR 99,9%"]
    lin = [[q["cenario"], pc(100 * q["el_pct_pl"], 3), pc(100 * q["var_99_pct_pl"], 2), pc(100 * q["var_999_pct_pl"], 2),
            pc(100 * q["es_999_pct_pl"], 2), num(q["mult_junior_sobre_var999"], 1) + "×", num(q["mult_senior_sobre_var999"], 1) + "×"]
           for _, q in quant.iterrows()]
    L += [tabela_md(cab, lin), "",
          "![absorção](../../figures/caso_%s_absorcao.png)" % cfg["caso"], ""]
    jb = absor[absor["classe"] == "junior"].set_index("cenario")
    sb = absor[absor["classe"] == "senior"].set_index("cenario")
    qq = quant.set_index("cenario")
    exj = m_.loc["junior", "excesso_vs_cdi_pp"]
    exs = m_.loc["senior", "excesso_vs_cdi_pp"]
    cen_l = list(jb.index)
    c0, c1 = cen_l[0], cen_l[-1]
    L += ["### O que isto permite concluir", "",
          f"- **Júnior.** Sem excesso de spread, qualquer perda de crédito atinge primeiro a júnior (por isso a P(perda) dela no ciclo é alta). "
          f"A EL anual aproximada dela é {pc(100 * jb.loc[c0, 'el_anual_aprox_pct_classe'], 1)} da classe no cenário {c0} e "
          f"{pc(100 * jb.loc[c1, 'el_anual_aprox_pct_classe'], 1)} no {c1}, contra um excesso observado de {num(exj, 1)} pp sobre o CDI "
          f"(prêmio ÷ EL anual: {num(jb.loc[c0, 'premio_sobre_el_anual'], 2)}× no {c0} e {num(jb.loc[c1, 'premio_sobre_el_anual'], 2)}× no {c1}). "
          "Ou seja, o prêmio observado da júnior é da ordem da perda esperada do cenário base, e fica abaixo dela no estresse se não houver "
          "reposição por excesso de spread. O prêmio observado já é líquido das perdas realizadas no período e o excesso de spread real "
          "amortece parte da perda: a comparação dá ordem de grandeza, não um teste.",
          f"- **Mezanino e sênior.** A mezanino só perderia com perda da carteira acima de {pc(100 * s_jun, 1)} do PL e a sênior acima de "
          f"{pc(100 * (s_mez + s_jun), 1)}. O VaR 99,9% da carteira sintética é {pc(100 * qq.loc[c0, 'var_999_pct_pl'], 1)} ({c0}) e "
          f"{pc(100 * qq.loc[c1, 'var_999_pct_pl'], 1)} ({c1}) do PL; a P(perda da sênior) simulada é {pc(100 * sb.loc[c1, 'p_perda'], 4)} no {c1}. "
          f"Nesta ponte, portanto, o excesso de {num(exs, 1)} pp da sênior sobre o CDI **não é explicado por perda esperada de crédito**. "
          "Hipóteses não testadas aqui: prêmio de liquidez (cota de FIC com prazo de resgate), complexidade da estrutura, concentração em poucos "
          "FIDCs, risco de contraparte e riscos fora do modelo (diluição, fraude, coobrigação).", "",
          "### O que isto NÃO permite concluir", "",
          "- Não prevê perda nem retorno do fundo real: a carteira simulada é sintética e o dado observado é de jun/2024.",
          "- Não diz que o prêmio da sênior está \"caro\" ou \"barato\" e não é recomendação de compra.",
          "- LGD sistêmica, correlação entre os FIDCs investidos e a hipótese de cauda pesada (cópula t) não entram na ponte; "
          "a conclusão sobre a sênior é sensível a elas (ver `docs/METODOLOGIA.md`).", "",
          "## 5. Auditoria dos dados observados", ""]
    cab = ["Série", "Maior diferença absoluta, recalculado − reportado (pp)", "Diferença no último mês (pp)", "Meses acima da tolerância"]
    lin = [[a["serie"], num(a["max_abs_dif_pp"], 4), num(a["dif_ultimo_mes_pp"], 4), str(a["n_meses_acima_tol"])] for _, a in aud.iterrows()]
    L += [tabela_md(cab, lin), "",
          "O acumulado reportado pela fonte foi recalculado por capitalização composta dos 12 retornos mensais; as diferenças "
          "são de arredondamento (a fonte arredonda a 2 casas). Isto valida a transcrição dos dados, **não** a veracidade da fonte "
          "(a agência declara que não audita as informações recebidas).", "",
          "### Proxy do retorno do fundo (ESTIMADO)", "",
          f"Média das classes ponderada pelo PL do mês anterior: {pc(proxy['acum_proxy_pct'].iloc[-1])} acumulado em "
          f"{len(proxy)} meses (de {proxy['competencia'].iloc[0]} a {proxy['competencia'].iloc[-1]}) contra {pc(proxy['acum_cdi_pct'].iloc[-1])} do CDI no mesmo período. "
          "Ignora captações/resgates dentro do mês; serve só como referência de ordem de grandeza.", ""]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--caso", default=str(RAIZ / "casos" / "via_multicredito" / "config_caso.json"))
    ap.add_argument("--dados", default=None, help="CSV observado (padrão: dados_observados.csv ao lado da config)")
    a = ap.parse_args()

    cfg_p = Path(a.caso)
    cfg = json.loads(cfg_p.read_text(encoding="utf-8"))
    dados_p = Path(a.dados) if a.dados else cfg_p.parent / "dados_observados.csv"
    df = obs.ler_observado(dados_p)
    if len(df) < 2:
        print("o CSV observado está vazio ou tem 1 linha (use casos/via_multicredito como exemplo)", file=sys.stderr)
        return 1
    nome = cfg["caso"]
    cls = obs.classes_presentes(df)
    saida = RAIZ / "outputs_caso" / nome
    saida.mkdir(parents=True, exist_ok=True)
    figdir = RAIZ / "figures"
    figdir.mkdir(exist_ok=True)

    aud = obs.auditoria_acumulado(df)
    met = obs.metricas_classe(df)
    sub = obs.subordinacao(df)
    proxy = obs.retorno_ponderado_proxy(df)
    absor, quant, curva, estrutura = ponte_modelo(cfg, sub, met, cls)

    aud.to_csv(saida / "auditoria_acumulado.csv", index=False)
    met.to_csv(saida / "metricas_por_classe.csv", index=False)
    sub.to_csv(saida / "subordinacao_mensal.csv", index=False)
    proxy.to_csv(saida / "proxy_retorno_fundo.csv", index=False)
    absor.to_csv(saida / "ponte_modelo_por_classe.csv", index=False)
    quant.to_csv(saida / "ponte_modelo_carteira.csv", index=False)
    curva.to_csv(saida / "curva_absorcao.csv", index=False)
    figuras(df, cls, curva, quant, nome, figdir)
    (saida / "RELATORIO.md").write_text(relatorio(cfg, df, cls, met, aud, sub, proxy, absor, quant, curva, estrutura),
                                        encoding="utf-8")
    meta = {"versao": __version__, "caso": nome, "config_sha256": sha(cfg_p), "dados_sha256": sha(dados_p),
            "pmf_sha256": {c: sha(RAIZ / cfg["modelo"]["pmf_arquivo"].format(cenario=c)) for c in cfg["modelo"]["cenarios"]},
            "python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__}
    (saida / "metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OK -> {saida}")
    print(met[["classe", "pl_ultimo_mes_mil", "rent_ultimo_mes_pct", "rent_acum_pct", "pct_cdi_acum"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
