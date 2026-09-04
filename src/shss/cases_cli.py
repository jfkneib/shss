"""`shss-cases` : utilitaire pour gerer la base de cas curates
(voir cases.py) independamment d'une session shss -- lister, ajouter,
modifier, retirer, tester une demande contre la base, et reconstruire
le cache d'embeddings.

Lance sans argument, il essaie d'ouvrir une interface graphique Tk
(voir cases_gui.py) pour faire tout ca a la souris ; si tkinter n'est
pas installe ou qu'aucun affichage n'est disponible (ex: SSH sans X),
il se rabat sur cette aide en ligne de commande -- rien a configurer,
ca marche dans les deux cas.
"""

import argparse
import sys
from pathlib import Path

from . import cases as cases_module

_EPILOG = """\
exemple complet, du premier cas a son utilisation :

  shss-cases add energie \\
      --request "energie consommee par le pc" \\
      --request "combien consomme mon ordinateur" \\
      --note "le LLM invente n'importe quoi ici"
  (colle le script sur stdin, Ctrl-D pour terminer -- ou --script-file)

  shss-cases reindex          # calcule les embeddings (une fois par changement)
  shss-cases test "quelle est la consommation electrique de ma machine"
  shss-cases list
  shss-cases edit energie --note "nouvelle note"     # sans retoucher le script
  shss-cases remove energie

cas "gabarit" (--stdin) : le contenu entre guillemets de la demande
varie a chaque fois, le script le lit sur stdin au lieu de l'ignorer :

  shss-cases add fix-select --stdin \\
      --request 'corrige moi ma ligne bash : "select | id from t"'
  (le script lit son entree standard, ex: sys.stdin.read() en python)

lance sans argument (juste `shss-cases`), une fenetre s'ouvre si
possible -- sinon ce texte s'affiche.

plusieurs bases separees (systeme, dev, autre...) via un seul reglage :

  export SHSS_CASES_PROFILE=dev
  (va dans ~/.shss/profiles/dev/, cache d'embeddings inclus)
"""


def _cmd_list(args):
    cases = cases_module.load_cases()
    if not cases:
        print("(base vide -- voir 'shss-cases add', ou lance shss-cases sans argument)")
        return 0
    for case in cases:
        requests = case["requests"]
        tags = []
        if case.get("input") == "stdin":
            tags.append("gabarit")
        if "threshold" in case:
            tags.append(f"seuil={case['threshold']}")
        suffix = f"  [{', '.join(tags)}]" if tags else ""
        print(f"{case['id']:<24} {requests[0]}{suffix}")
        for extra in requests[1:]:
            print(f"{'':<24} {extra}")
        if case.get("note"):
            print(f"{'':<24} # {case['note']}")
    return 0


def _cmd_add(args):
    cases = cases_module.load_cases()
    if args.script_file:
        script = Path(args.script_file).read_text(encoding="utf-8")
    else:
        print("(script sur stdin, Ctrl-D pour terminer)", file=sys.stderr)
        script = sys.stdin.read()

    try:
        cases = cases_module.add_case(
            cases,
            args.id,
            args.request,
            script,
            note=args.note or "",
            input_mode="stdin" if args.stdin else None,
            threshold=args.threshold,
        )
    except ValueError as exc:
        print(f"shss-cases: {exc}", file=sys.stderr)
        return 1

    cases_module.save_cases(cases)
    print(f"cas « {args.id} » ajoute -- lance 'shss-cases reindex' avant de l'utiliser")
    return 0


def _cmd_edit(args):
    cases = cases_module.load_cases()

    script = None
    if args.script_file:
        script = Path(args.script_file).read_text(encoding="utf-8")
    elif args.script_stdin:
        print("(script sur stdin, Ctrl-D pour terminer)", file=sys.stderr)
        script = sys.stdin.read()

    input_mode = None
    if args.stdin:
        input_mode = "stdin"
    elif args.no_stdin:
        input_mode = ""

    threshold = None
    if args.threshold is not None:
        threshold = args.threshold
    elif args.clear_threshold:
        threshold = ""

    try:
        cases = cases_module.update_case(
            cases,
            args.id,
            requests=args.request,
            script=script,
            note=args.note,
            input_mode=input_mode,
            threshold=threshold,
        )
    except KeyError:
        print(f"shss-cases: aucun cas « {args.id} » (utilise 'add' pour en creer un)", file=sys.stderr)
        return 1

    cases_module.save_cases(cases)
    changed = [
        name
        for name, value in (
            ("formulations", args.request),
            ("script", script),
            ("note", args.note),
            ("gabarit", input_mode),
            ("seuil", threshold),
        )
        if value is not None
    ]
    print(f"cas « {args.id} » mis a jour ({', '.join(changed) or 'rien'})")
    if args.request is not None or script is not None:
        print("lance 'shss-cases reindex' : le contenu vectorise a change")
    return 0


def _cmd_remove(args):
    cases = cases_module.load_cases()
    try:
        cases = cases_module.remove_case(cases, args.id)
    except KeyError:
        print(f"shss-cases: aucun cas « {args.id} »", file=sys.stderr)
        return 1

    cases_module.save_cases(cases)
    print(f"cas « {args.id} » retire")
    return 0


def _cmd_test(args):
    cases = cases_module.load_cases()
    cache = cases_module.load_cache()
    if cases_module.is_stale(cases, cache):
        print(
            "shss-cases: le cache d'embeddings n'est pas a jour "
            "(lance 'shss-cases reindex')",
            file=sys.stderr,
        )

    payload, _normalized = cases_module.extract_payload(args.query)
    if payload is not None:
        print(f"contenu entre guillemets detecte : {payload!r}", file=sys.stderr)

    try:
        matches = cases_module.find_matches(args.query, cases=cases, cache=cache, top_k=args.top)
    except FileNotFoundError as exc:
        print(f"shss-cases: {exc}", file=sys.stderr)
        return 1
    if not matches:
        print("aucun match (base ou cache vide)")
        return 0

    for case, score, matched_request in matches:
        seuil = case.get("threshold", cases_module._threshold())
        marque = "-> reutilise" if score >= seuil else "  en dessous du seuil"
        print(
            f"{score * 100:5.1f}%  {case['id']:<24} (seuil {seuil * 100:.0f}%, {marque}) "
            f"proche de : {matched_request!r}"
        )
    return 0


def _cmd_download_model(args):
    existing = Path(cases_module.curated_embed_model_path())
    if existing.is_file():
        print(f"deja present : {existing}")
        return 0

    print(
        f"telechargement du modele d'embeddings (~{cases_module.CURATED_EMBED_MODEL_SIZE_MB} Mo)...",
        file=sys.stderr,
    )
    path = cases_module.download_embedding_model()
    print(f"modele d'embeddings installe : {path}")
    return 0


def _cmd_reindex(args):
    cases = cases_module.load_cases()
    if not cases:
        print("(base vide, rien a indexer)")
        return 0

    try:
        cache = cases_module.reindex(cases, force=args.force)
    except FileNotFoundError as exc:
        print(f"shss-cases: {exc}", file=sys.stderr)
        return 1
    print(f"{len(cache['entries'])} formulation(s) indexee(s) pour {len(cases)} cas")
    return 0


def _cmd_gui(args):
    from . import cases_gui

    if cases_gui.try_run():
        return 0
    print(
        "shss-cases: impossible d'ouvrir l'interface graphique ici "
        "(tkinter absent, ou aucun affichage disponible).",
        file=sys.stderr,
    )
    return 1


def build_parser():
    parser = argparse.ArgumentParser(
        prog="shss-cases",
        description="gere la base de cas curates de shss",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="liste les cas existants")
    p_list.set_defaults(func=_cmd_list)

    p_add = sub.add_parser(
        "add",
        help="ajoute un cas",
        description="Ajoute un nouveau cas. Le script vient de --script-file, sinon de stdin.",
    )
    p_add.add_argument("id", help="identifiant court et stable du cas (ex: energie)")
    p_add.add_argument(
        "--request",
        action="append",
        required=True,
        metavar="TEXTE",
        help="formulation d'exemple (repetable : plus il y en a, mieux le cas est retrouve)",
    )
    p_add.add_argument("--script-file", metavar="FICHIER", help="lit le script depuis ce fichier (sinon : stdin)")
    p_add.add_argument("--note", help="pourquoi ce cas existe -- utile en le relisant plus tard (optionnel)")
    p_add.add_argument(
        "--stdin",
        action="store_true",
        help=(
            "cas 'gabarit' : le contenu entre guillemets de la demande varie a "
            "chaque fois (ex: 'corrige ma ligne : \"...\"') et est transmis au "
            "script sur son entree standard, jamais colle dans le code"
        ),
    )
    p_add.add_argument(
        "--threshold",
        type=float,
        metavar="0.0-1.0",
        help=(
            "seuil de confiance propre a ce cas (defaut : SHSS_CASES_THRESHOLD, "
            "0.70) -- un cas gabarit (--stdin) en a souvent besoin d'un plus eleve "
            "(voir 'shss-cases test' pour verifier avant de choisir)"
        ),
    )
    p_add.set_defaults(func=_cmd_add)

    p_edit = sub.add_parser(
        "edit",
        help="modifie un cas existant",
        description=(
            "Modifie un cas deja present : seuls les champs fournis changent, "
            "les autres restent tels quels (--request remplace TOUTES les "
            "formulations d'un coup, pas une seule)."
        ),
    )
    p_edit.add_argument("id")
    p_edit.add_argument(
        "--request",
        action="append",
        metavar="TEXTE",
        help="remplace toutes les formulations existantes (repetable) -- omis : inchangees",
    )
    p_edit.add_argument("--script-file", metavar="FICHIER", help="remplace le script depuis ce fichier")
    p_edit.add_argument("--script-stdin", action="store_true", help="remplace le script depuis stdin (Ctrl-D)")
    p_edit.add_argument("--note", help="remplace la note")
    p_edit.add_argument("--stdin", action="store_true", help="fait de ce cas un gabarit (voir 'add --stdin')")
    p_edit.add_argument("--no-stdin", action="store_true", help="repasse ce cas en cas normal (retire 'input')")
    p_edit.add_argument("--threshold", type=float, metavar="0.0-1.0", help="fixe le seuil propre a ce cas")
    p_edit.add_argument(
        "--clear-threshold", action="store_true", help="retire le seuil propre a ce cas (retour au seuil global)"
    )
    p_edit.set_defaults(func=_cmd_edit)

    p_remove = sub.add_parser("remove", help="retire un cas")
    p_remove.add_argument("id")
    p_remove.set_defaults(func=_cmd_remove)

    p_test = sub.add_parser(
        "test",
        help="teste une demande contre la base (rien n'est execute)",
        description="Montre quels cas matchent une demande, et avec quel score -- pour calibrer avant d'utiliser pour de vrai.",
    )
    p_test.add_argument("query", help="une demande en langage naturel, entre guillemets")
    p_test.add_argument("--top", type=int, default=3, help="nombre de resultats (defaut: 3)")
    p_test.set_defaults(func=_cmd_test)

    p_download = sub.add_parser(
        "download-model", help="telecharge le modele d'embeddings curate (sans Ollama)"
    )
    p_download.set_defaults(func=_cmd_download_model)

    p_reindex = sub.add_parser(
        "reindex",
        help="reconstruit le cache d'embeddings",
        description="A relancer apres tout add/edit/remove qui change une formulation ou un script.",
    )
    p_reindex.add_argument(
        "--force",
        action="store_true",
        help="recalcule tout, meme les formulations inchangees",
    )
    p_reindex.set_defaults(func=_cmd_reindex)

    p_gui = sub.add_parser("gui", help="ouvre l'interface graphique (erreur claire si impossible)")
    p_gui.set_defaults(func=_cmd_gui)

    return parser


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv

    if not argv:
        # Rien demande explicitement : on essaie d'etre pratique plutot
        # que d'exiger de connaitre les sous-commandes par coeur --
        # fenetre si possible, sinon cette meme aide, sans erreur.
        from . import cases_gui

        if cases_gui.try_run():
            return 0
        print(
            "shss-cases: pas d'interface graphique disponible ici "
            "(tkinter absent, ou aucun affichage) -- ligne de commande :\n",
            file=sys.stderr,
        )
        build_parser().print_help()
        return 0

    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
