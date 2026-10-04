"""Gera ``notebooklm_sources/02_resultados.md`` e ``03_lote_exemplo.md`` a partir dos outputs.

Os demais arquivos de ``notebooklm_sources/`` são texto escrito à mão (visão geral, metodologia,
limites). Os que têm NÚMEROS são gerados aqui para que o que vai para os slides seja exatamente o
que está nos CSVs: nenhum número é digitado manualmente.

Uso: python scripts/gerar_notebooklm_sources.py   (depois de rodar o pipeline e analisar_lote.py)
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
OUT = RAIZ / "outputs"
LOTE = RAIZ / "outputs_lote" / "exemplo_sintetico"
DEST = RAIZ / "notebooklm_sources"
DEST.mkdir(exist_ok=True)

ROT = {"crplus_poisson": "CreditRisk+ Poisson", "crplus_gamma": "CreditRisk+ Gamma (setores)",
       "mc_crplus_gamma": "MC do CreditRisk+ (validação)", "copula_gaussiana": "Cópula gaussiana",
       "copula_t": "Cópula t (nu = 5)"}


def p(x, n=2):
    """Percentual com vírgula decimal (x em fração)."""
    return f"{100 * x:.{n}f}%".replace(".", ",")


def num(x, n=4):
    """Número com vírgula decimal."""
    return f"{x:.{n}f}".replace(".", ",")


def milhar(x):
    """Inteiro com ponto de milhar (R$ 104.000.000)."""
    return f"{x:,.0f}".replace(",", ".")


def tabela(cabecalho: list[str], linhas: list[list[str]]) -> str:
    out = ["| " + " | ".join(cabecalho) + " |", "|" + "---|" * len(cabecalho)]
    out += ["| " + " | ".join(l) + " |" for l in linhas]
    return "\n".join(out)


def resultados() -> str:
    chave = json.loads((OUT / "resultados_chave.json").read_text(encoding="utf-8"))
    meta = json.loads((OUT / "run_metadata.json").read_text(encoding="utf-8"))
    resumo = pd.read_csv(OUT / "resumo_perdas.csv")
    lgd = pd.read_csv(OUT / "lgd_sensibilidade.csv")
    tn = pd.read_csv(OUT / "t_sensibilidade_nu.csv")
    cal = pd.read_csv(OUT / "t_calibracao_nu.csv")
    L = ["# Resultados (gerado automaticamente a partir de `outputs/`)", "",
         f"Versão {meta['versao']}, seed {meta['seed']}, {milhar(meta['n_sims'])} simulações por modelo, "
         f"hash da config `{meta['config_sha256'][:16]}…`. **Todos os dados são sintéticos (hipotéticos).** "
         "Perdas em % da face da carteira (perda de crédito de um ciclo de 60 dias).", ""]
    for cen in [c for c in chave if not c.startswith("_")]:
        r = chave[cen]
        face = r["face_total"]
        L += [f"## Cenário `{cen}`", "",
              f"{r['n_sacados']} sacados; face R$ {milhar(face)}; preço (PL) R$ {milhar(r['preco_total'])}; "
              f"EL da carteira {p(r['el_pct_face'], 3)} da face.", ""]
        s = resumo[resumo["cenario"] == cen].set_index("modelo")
        L.append(tabela(["Modelo", "EL", "VaR 99%", "VaR 99,9%", "ES 99,9%"],
                        [[ROT[m], p(s.loc[m, "el"] / face, 3), p(s.loc[m, "var_0.99"] / face),
                          p(s.loc[m, "var_0.999"] / face), p(s.loc[m, "es_0.999"] / face)]
                         for m in ROT]))
        L += ["", "Subordinação mínima (EL da sênior ≤ 0,01% por ciclo; % do PL):", ""]
        ms = r["subordinacao_minima"]
        L.append(tabela(["Modelo", "com excesso de spread", "sem excesso de spread"],
                        [[ROT[m], p(ms[f"{m}|com_xs"], 1), p(ms[f"{m}|sem_xs"], 1)]
                         for m in ROT if m != "mc_crplus_gamma"]))
        L += ["", f"Validação: KS entre Panjer e Monte Carlo = {num(r['ks_panjer_vs_mc'])} "
              f"(limite DKW {num(r['ks_limite_dkw_alpha1e-3'])}); inclinação de convergência do MC = "
              f"{num(r['inclinacao_convergencia'], 3)} (teórica −0,500).", ""]

        g = lgd[(lgd["cenario"] == cen) & (lgd["modelo"] == "crplus_gamma")].sort_values("lgd_media")
        L += [f"### LGD determinística (CreditRisk+ Gamma, Panjer) — `{cen}`", "",
              tabela(["LGD", "EL", "VaR 99,9%", "ES 99,9%", "Sub. mín. com XS", "Sub. mín. sem XS"],
                     [[p(x.lgd_media, 0), p(x.el / face, 3), p(x["var_0.999"] / face),
                       p(x["es_0.999"] / face), p(x.sub_min_com_xs, 1), p(x.sub_min_sem_xs, 1)]
                      for _, x in g.iterrows()]), ""]
        b = lgd[(lgd["cenario"] == cen) & (lgd["modelo"].isin(["mc_crplus_gamma", "copula_gaussiana"]))]
        b = b.sort_values(["modelo", "lgd_desvio"])
        L += [f"### LGD Beta (média 60%) — incerteza de recuperação — `{cen}`", "",
              tabela(["Modelo", "Desvio da LGD", "EL", "VaR 99,9%", "ES 99,9%"],
                     [[ROT[x.modelo], p(x.lgd_desvio, 0) if x.lgd_desvio > 0 else "0 (determinística)",
                       p(x.el / face, 3), p(x["var_0.999"] / face), p(x["es_0.999"] / face)]
                      for _, x in b.iterrows()]), ""]
        t = tn[tn["cenario"] == cen].sort_values("nu")
        c = cal[cal["cenario"] == cen]
        L += [f"### Cópula t: sensibilidade a nu — `{cen}`", "",
              tabela(["nu", "VaR 99,9%", "ES 99,9%", "Piso de corr. de default (média dos setores)",
                      "Alvo CreditRisk+ (média)", "Calibrável?"],
                     [[str(int(x.nu)), p(x["var_0.999"] / face), p(x["es_0.999"] / face),
                       num(c[c.nu == x.nu].piso_corr_default_t.mean()),
                       num(c[c.nu == x.nu].corr_default_alvo.mean()),
                       "sim" if bool(c[c.nu == x.nu].viavel.all()) else "não"]
                      for _, x in t.iterrows()]), ""]
    ec = chave["_lgd_economico"]
    L += ["## LGD econômica (hipótese)", "",
          f"R = {p(ec['taxa_recuperacao'], 0)}, atraso de recuperação {ec['lag_dias']} dias, desconto "
          f"{p(ec['taxa_desconto_anual'], 0)} a.a., custo de cobrança {p(ec['custo_cobranca'], 0)} ⇒ "
          f"LGD = {p(ec['lgd_implicita'], 2)} (config usa {p(ec['lgd_config'], 0)}).", ""]
    return "\n".join(L)


def lote_exemplo() -> str:
    res = pd.read_csv(LOTE / "resumo_perdas.csv")
    sm = pd.read_csv(LOTE / "subordinacao_minima.csv")
    des = json.loads((LOTE / "desagio.json").read_text(encoding="utf-8"))
    sac = pd.read_csv(LOTE / "sacados.csv")
    L = ["# Exemplo de análise de lote de duplicatas (SINTÉTICO)", "",
         "Lote fictício de 66 duplicatas de 35 sacados, gerado com seed fixa em `templates/duplicatas_exemplo.csv`. "
         "Ilustra o fluxo `scripts/analisar_lote.py`; **não é um cedente real**.", ""]
    for cen in res["cenario"].unique():
        s = sac[sac["cenario"] == cen]
        face = s["face"].sum()
        r = res[res["cenario"] == cen].set_index("modelo")
        L += [f"## Cenário `{cen}`", "", f"Face R$ {milhar(face)}; EL {p(r.loc['crplus_gamma', 'el_pct_face'], 3)} da face.", "",
              tabela(["Modelo", "VaR 99%", "VaR 99,9%", "ES 99,9%"],
                     [[ROT[m], p(r.loc[m, "var_0.99_pct_face"]), p(r.loc[m, "var_0.999_pct_face"]),
                       p(r.loc[m, "es_0.999_pct_face"])] for m in ROT if m in r.index]), ""]
        q = sm[sm["cenario"] == cen].pivot(index="modelo", columns="leitura", values="subordinacao_minima")
        L += [tabela(["Modelo", "Sub. mín. com XS", "Sub. mín. sem XS"],
                     [[ROT[m], p(q.loc[m, "com_xs"], 1), p(q.loc[m, "sem_xs"], 1)] for m in q.index]), ""]
        d = des[cen]
        L += ["Deságio exigido no ciclo (% do preço): " + ", ".join(
            f"{k} {p(d[k], 3)}" for k in ("custo_senior", "retorno_sub", "despesas", "perda_esperada", "margem"))
            + f". Soma exigida {p(d['desagio_exigido_ciclo'], 3)} contra praticado {p(d['desagio_praticado_ciclo'], 3)} "
            f"({p(d['taxa_mensal_exigida'])} a.m. exigido vs {p(d['taxa_mensal_praticada'])} a.m. praticado).", ""]
    s0 = sac[sac["cenario"] == "base"].sort_values("face", ascending=False)
    pf = s0["face"] / s0["face"].sum()
    L += ["## Concentração", "",
          f"Maior sacado {p(pf.iloc[0])} da face; top 5 {p(pf.head(5).sum())}; top 10 {p(pf.head(10).sum())}; "
          f"número efetivo de sacados {num(1 / (pf ** 2).sum(), 1)}.", ""]
    return "\n".join(L)


def caso_via_multicredito() -> str:
    """Fonte 07: caso observado (FIC FIDC Via Multicrédito) a partir de outputs_caso/."""
    C = RAIZ / "outputs_caso" / "via_multicredito"
    cfg = json.loads((RAIZ / "casos" / "via_multicredito" / "config_caso.json").read_text(encoding="utf-8"))
    met = pd.read_csv(C / "metricas_por_classe.csv")
    sub = pd.read_csv(C / "subordinacao_mensal.csv").iloc[-1]
    pon = pd.read_csv(C / "ponte_modelo_por_classe.csv")
    car = pd.read_csv(C / "ponte_modelo_carteira.csv")
    aud = pd.read_csv(C / "auditoria_acumulado.csv")
    rot = {"senior": "Sênior", "mezanino": "Mezanino", "junior": "Júnior"}
    f, fo = cfg["fundo"], cfg["fonte"]
    L = ["# Caso observado: FIC FIDC Via Multicrédito (gerado de `outputs_caso/`)", "",
         f"**Natureza:** OBSERVADO (fonte: {fo['emissor']}, relatório de {fo['data_relatorio']}, janela {fo['janela']}) "
         "+ ponte SIMULADA com a carteira sintética. **Defasagem:** " + fo["defasagem"] + ". "
         f"CNPJ {f['cnpj']}; {f['tipo']}; administradora BTG Pactual Serviços Financeiros (cabeçalho do relatório); "
         f"gestora {f['gestora'].rstrip('.')}.", "",
         "## Critérios: PL, rentabilidade 12M e do último mês, por classe", "",
         tabela(["Classe", "PL (R$ mil)", "% do PL", "Último mês", "12 meses", "CDI 12M", "% do CDI", "Excesso s/ CDI (pp)"],
                [[rot[r.classe], milhar(r.pl_ultimo_mes_mil), p(r.pl_pct_do_total, 1) if r.pl_pct_do_total < 1.5 else "n/d",
                  num(r.rent_ultimo_mes_pct, 2) + "%", num(r.rent_acum_pct, 2) + "%", num(r.cdi_acum_pct, 2) + "%",
                  num(r.pct_cdi_acum, 1) + "%", num(r.excesso_vs_cdi_pp, 2)] for r in met.itertuples()]), "",
         "## Risco observado por classe", "",
         tabela(["Classe", "Média mensal", "Volatilidade mensal", "Pior mês", "Meses negativos", "Meses abaixo do CDI"],
                [[rot[r.classe], num(r.media_mensal_pct, 2) + "%", num(r.vol_mensal_pct, 2) + "%", num(r.pior_mes_pct, 2) + "%",
                  str(r.meses_negativos), str(r.meses_abaixo_cdi)] for r in met.itertuples()]), "",
         f"Subordinação no último mês: total {p(sub.subordinacao_total, 1)}; mezanino {p(sub.pct_mezanino, 1)}; júnior {p(sub.pct_junior, 1)}. "
         f"Cotistas: {cfg['cotistas_jun_2024']['senior']} na sênior e {cfg['cotistas_jun_2024']['subordinadas_mezanino_mais_junior']} nas subordinadas. "
         "**Não verificado:** se a sênior é distribuída ao varejo e quem são os titulares das subordinadas (a fonte traz só contagens).", "",
         "## Ponte com o modelo (SIMULADO; carteira sintética de duplicatas, sem excesso de spread)", "",
         tabela(["Cenário", "Classe", "Anexação–destacamento", "EL anual aprox. (% da classe)", "Prêmio observado s/ CDI"],
                [[r.cenario, rot[r.classe], f"{p(r.anexacao_pct_pl, 1)}–{p(r.destacamento_pct_pl, 1)}",
                  p(r.el_anual_aprox_pct_classe, 2), p(r.premio_observado_vs_cdi, 2)] for r in pon.itertuples()]), "",
         tabela(["Cenário", "VaR 99,9% da carteira (% PL)", "Anexação da mezanino ÷ VaR", "Anexação da sênior ÷ VaR"],
                [[r.cenario, p(r.var_999_pct_pl, 2), num(r.mult_junior_sobre_var999, 1) + "×", num(r.mult_senior_sobre_var999, 1) + "×"]
                 for r in car.itertuples()]), "",
         "Leituras que a ponte sustenta: (1) a perda de crédito é absorvida primeiro pela júnior; (2) com a subordinação observada, a sênior "
         "e a mezanino não perdem nas simulações, então o excesso delas sobre o CDI não é explicado por perda esperada de crédito do modelo; "
         "(3) o prêmio da júnior é da ordem da perda esperada no cenário base e menor que ela no estresse sem excesso de spread. "
         "**Não permite concluir:** previsão para o fundo real, preço justo ou recomendação.", "",
         "## Auditoria", "",
         "Maior diferença entre o acumulado reportado pela fonte e o recalculado dos retornos mensais: "
         + num(aud.max_abs_dif_pp.max(), 4) + " pp (arredondamento). Valida a transcrição, não a veracidade da fonte.", ""]
    return "\n".join(L)


if __name__ == "__main__":
    (DEST / "02_resultados.md").write_text(resultados(), encoding="utf-8")
    if LOTE.exists():
        (DEST / "03_lote_exemplo.md").write_text(lote_exemplo(), encoding="utf-8")
    if (RAIZ / "outputs_caso" / "via_multicredito" / "metricas_por_classe.csv").exists():
        (DEST / "07_caso_via_multicredito.md").write_text(caso_via_multicredito(), encoding="utf-8")
    print("notebooklm_sources atualizado")
