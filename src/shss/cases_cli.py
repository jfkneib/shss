"""`shss-cases` : utilitaire pour gerer la base de cas curates
(voir cases.py) independamment d'une session shss -- lister, ajouter,
retirer, tester une demande contre la base, et reconstruire le cache
d'embeddings.
"""

import argparse
import sys
from pathlib import Path

from . import cases as cases_module


def _cmd_list(args):
    cases = cases_module.load_cases()
    if not cases:
        print("(base vide)")
        return 0
    for case in cases:
        requests = case["requests"]
        print(f"{case['id']:<24} {requests[0]}")
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
            cases, args.id, args.request, script, note=args.note or ""
        )
    except ValueError as exc:
        print(f"shss-cases: {exc}", file=sys.stderr)
        return 1

    cases_module.save_cases(cases)
    print(f"cas « {args.id} » ajoute -- lance 'shss-cases reindex' avant de l'utiliser")
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

    matches = cases_module.find_matches(args.query, cases=cases, cache=cache, top_k=args.top)
    if not matches:
        print("aucun match (base ou cache vide)")
        return 0

    for case, score, matched_request in matches:
        print(f"{score * 100:5.1f}%  {case['id']:<24} (proche de : {matched_request!r})")
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

    cache = cases_module.reindex(cases, force=args.force)
    print(f"{len(cache['entries'])} formulation(s) indexee(s) pour {len(cases)} cas")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="shss-cases", description="gere la base de cas curates de shss"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="liste les cas existants")
    p_list.set_defaults(func=_cmd_list)

    p_add = sub.add_parser("add", help="ajoute un cas")
    p_add.add_argument("id", help="identifiant court et stable du cas")
    p_add.add_argument(
        "--request",
        action="append",
        required=True,
        help="formulation d'exemple (repetable pour plusieurs variantes)",
    )
    p_add.add_argument("--script-file", help="fichier contenant le script (sinon : stdin)")
    p_add.add_argument("--note", help="pourquoi ce cas existe (optionnel)")
    p_add.set_defaults(func=_cmd_add)

    p_remove = sub.add_parser("remove", help="retire un cas")
    p_remove.add_argument("id")
    p_remove.set_defaults(func=_cmd_remove)

    p_test = sub.add_parser("test", help="teste une demande contre la base (rien n'est execute)")
    p_test.add_argument("query")
    p_test.add_argument("--top", type=int, default=3)
    p_test.set_defaults(func=_cmd_test)

    p_download = sub.add_parser(
        "download-model", help="telecharge le modele d'embeddings curate (sans Ollama)"
    )
    p_download.set_defaults(func=_cmd_download_model)

    p_reindex = sub.add_parser("reindex", help="reconstruit le cache d'embeddings")
    p_reindex.add_argument(
        "--force",
        action="store_true",
        help="recalcule tout, meme les formulations inchangees",
    )
    p_reindex.set_defaults(func=_cmd_reindex)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
