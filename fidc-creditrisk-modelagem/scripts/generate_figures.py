"""Gera as figuras de auditoria a partir dos CSVs em outputs/."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
OUT = RAIZ / "outputs"
FIG = RAIZ / "figures"
FIG.mkdir(exist_ok=True)

ROTULOS = {
    "crplus_poisson": "CreditRisk+ (Poisson)",
    "crplus_gamma": "CreditRisk+ (Gamma por setor)",
    "mc_crplus_gamma": "MC do CreditRisk+ (validação)",
    "copula_gaussiana": "Cópula gaussiana",
    "copula_t": "Cópula t",
}
CORES = {
    "crplus_poisson": "#8a8a8a",
    "crplus_gamma": "#1f5fa8",
    "mc_crplus_gamma": "#7fb2e5",
    "copula_gaussiana": "#c0561b",
    "copula_t": "#7a2a8f",
}
ESTILO = {"mc_crplus_gamma": ":"}


def fig_cauda(cen: str, face: float) -> None:
    q = pd.read_csv(OUT / "curvas_quantis.csv")
    q = q[q["cenario"] == cen]
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    for m, g in q.groupby("modelo"):
        ax.plot(1 - g["q"], 100 * g["perda"] / face, label=ROTULOS[m], color=CORES[m],
                ls=ESTILO.get(m, "-"), lw=1.8)
    ax.set_xscale("log")
    ax.invert_xaxis()
    ax.set_xlabel("Probabilidade de excedência (1 − nível)")
    ax.set_ylabel("Perda de crédito do ciclo (% da face)")
    ax.set_title(f"Cauda da distribuição de perdas — cenário {cen}")
    ax.grid(alpha=0.3)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / f"fig_cauda_{cen}.png", dpi=160)
    plt.close(fig)


def fig_subordinacao(cen: str) -> None:
    cv = pd.read_csv(OUT / "curvas_subordinacao.csv")
    cv = cv[(cv["cenario"] == cen) & (cv["modelo"] != "mc_crplus_gamma")]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True)
    for ax, xs, titulo in zip(axes, (True, False), ("com excesso de spread", "sem excesso de spread")):
        for m, g in cv[cv["usar_xs"] == xs].groupby("modelo"):
            y = g["el_senior_taxa"].clip(lower=1e-9)
            ax.plot(100 * g["share_sub"], y, label=ROTULOS[m], color=CORES[m], lw=1.8)
        ax.axhline(1e-4, color="k", lw=0.8, ls="--")
        ax.set_yscale("log")
        ax.set_ylim(1e-8, 2e-2)
        ax.set_xlabel("Subordinação (% do PL)")
        ax.set_title(titulo)
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("EL da sênior por ciclo (log)")
    axes[0].legend(frameon=False, fontsize=8)
    fig.suptitle(f"Subordinação necessária — cenário {cen} (tracejado = alvo)", y=1.0)
    fig.tight_layout()
    fig.savefig(FIG / f"fig_subordinacao_{cen}.png", dpi=160)
    plt.close(fig)


def fig_validacao(cen: str) -> None:
    pmf = pd.read_csv(OUT / f"pmf_crplus_{cen}.csv")
    conv = pd.read_csv(OUT / "convergencia.csv")
    conv = conv[conv["cenario"] == cen]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    ax = axes[0]
    ax.plot(pmf["perda"] / 1e6, pmf["pmf_poisson"], color=CORES["crplus_poisson"], label="Poisson")
    ax.plot(pmf["perda"] / 1e6, pmf["pmf_gamma"], color=CORES["crplus_gamma"], label="Gamma por setor")
    corte = pmf["perda"][np.searchsorted(pmf["pmf_gamma"].cumsum().to_numpy(), 0.9999)] / 1e6
    ax.set_xlim(0, corte)
    ax.set_xlabel("Perda de crédito (R$ milhões)")
    ax.set_ylabel("Probabilidade (por unidade)")
    ax.set_title("pmf pela recursão de Panjer")
    ax.legend(frameon=False)
    ax.grid(alpha=0.3)
    ax = axes[1]
    ax.loglog(conv["n"], conv["rmse"], "o-", color=CORES["crplus_gamma"], label="RMSE da EL (MC)")
    n0, r0 = conv["n"].iloc[0], conv["rmse"].iloc[0]
    ax.loglog(conv["n"], r0 * (conv["n"] / n0) ** -0.5, "k--", lw=1, label="referência n$^{-1/2}$")
    incl = np.polyfit(np.log(conv["n"]), np.log(conv["rmse"]), 1)[0]
    ax.set_title(f"Convergência do MC (inclinação {incl:.3f})")
    ax.set_xlabel("n simulações por bloco")
    ax.set_ylabel("RMSE")
    ax.legend(frameon=False)
    ax.grid(alpha=0.3, which="both")
    fig.suptitle(f"Validação da implementação — cenário {cen}", y=1.0)
    fig.tight_layout()
    fig.savefig(FIG / f"fig_validacao_{cen}.png", dpi=160)
    plt.close(fig)


def fig_lgd(cen: str, face: float) -> None:
    d = pd.read_csv(OUT / "lgd_sensibilidade.csv")
    d = d[d["cenario"] == cen]
    det = d[(d["modelo"] == "crplus_gamma") & (d["lgd_desvio"] == 0)].sort_values("lgd_media")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    ax = axes[0]
    ax.plot(100 * det["lgd_media"], 100 * det["var_0.999"] / face, "o-", color=CORES["crplus_gamma"],
            label="VaR 99,9% (Panjer)")
    ax.plot(100 * det["lgd_media"], 100 * det["el"] / face, "s-", color="#444", label="EL")
    ax.set_xlabel("LGD determinística (%)")
    ax.set_ylabel("Perda do ciclo (% da face)")
    ax.set_title("EL e cauda são lineares na LGD")
    ax.grid(alpha=0.3)
    ax.legend(frameon=False)
    ax = axes[1]
    for m, off in (("mc_crplus_gamma", -0.004), ("copula_gaussiana", 0.004)):
        g = d[d["modelo"] == m].sort_values("lgd_desvio")
        ax.plot(100 * g["lgd_desvio"], 100 * g["var_0.999"] / face, "o-", color=CORES[m], label=ROTULOS[m])
    ax.set_xlabel("Desvio-padrão da LGD Beta (pontos percentuais; média 60%)")
    ax.set_ylabel("VaR 99,9% (% da face) — eixo ampliado")
    ax.set_title("Incerteza de recuperação engorda a cauda")
    ax.grid(alpha=0.3)
    ax.legend(frameon=False, fontsize=8)
    fig.suptitle(f"Sensibilidade à LGD — cenário {cen}", y=1.0)
    fig.tight_layout()
    fig.savefig(FIG / f"fig_lgd_{cen}.png", dpi=160)
    plt.close(fig)


def fig_nu(cen: str, face: float) -> None:
    t = pd.read_csv(OUT / "t_sensibilidade_nu.csv")
    t = t[t["cenario"] == cen].sort_values("nu")
    r = pd.read_csv(OUT / "resumo_perdas.csv")
    r = r[r["cenario"] == cen].set_index("modelo")
    c = pd.read_csv(OUT / "t_calibracao_nu.csv")
    c = c[c["cenario"] == cen].groupby("nu")["viavel"].all()
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    ax.plot(t["nu"], 100 * t["var_0.999"] / face, "o-", color=CORES["copula_t"], label="Cópula t (rho da gaussiana)")
    for m in ("copula_gaussiana", "crplus_gamma"):
        ax.axhline(100 * r.loc[m, "var_0.999"] / face, color=CORES[m], ls="--", label=ROTULOS[m])
    for nu, y in zip(t["nu"], 100 * t["var_0.999"] / face):
        ax.annotate("calibrável" if c.get(nu, False) else "não calibrável", (nu, y), textcoords="offset points",
                    xytext=(6, 6), fontsize=7)
    ax.set_xscale("log")
    ax.set_xlabel("Graus de liberdade ν")
    ax.set_ylabel("VaR 99,9% (% da face)")
    ax.set_title(f"Cauda × hipótese de dependência de cauda — cenário {cen}")
    ax.grid(alpha=0.3)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / f"fig_nu_{cen}.png", dpi=160)
    plt.close(fig)


def main() -> None:
    resumo = pd.read_csv(OUT / "resumo_perdas.csv")
    for cen in resumo["cenario"].unique():
        face = float(resumo[resumo["cenario"] == cen]["face_total"].iloc[0])
        fig_cauda(cen, face)
        fig_subordinacao(cen)
        fig_validacao(cen)
        fig_lgd(cen, face)
        fig_nu(cen, face)
    print("Figuras salvas em", FIG)


if __name__ == "__main__":
    main()
