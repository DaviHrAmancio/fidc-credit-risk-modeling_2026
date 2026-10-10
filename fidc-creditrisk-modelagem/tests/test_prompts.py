from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PROMPTS = RAIZ / "docs" / "prompts_notebooklm"

LIMITE_CHAT = 10_000     # personalização do chat do NotebookLM (reportado em dez/2025)
LIMITE_SLIDES = 2_000    # limite de slides não é publicado: margem conservadora própria


def texto(nome: str) -> str:
    return (PROMPTS / nome).read_text(encoding="utf-8").strip()


def test_instrucao_do_chat_cabe_no_limite():
    assert len(texto("01_instrucao_do_chat.txt")) <= LIMITE_CHAT


def test_prompts_de_slides_sao_curtos():
    assert len(texto("02_slides_completo.txt")) <= LIMITE_SLIDES
    assert len(texto("03_slides_curto.txt")) <= 800


def test_numeros_dos_prompts_estao_no_readme():
    readme = (RAIZ / "README.md").read_text(encoding="utf-8")
    slides = texto("02_slides_completo.txt")
    for numero in ["2,92%", "50,8", "2,0%", "6,3%"]:
        assert numero in slides
        assert numero in readme
